from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import logging
import os
import httpx

from .tokenizer_utils import TokenizerUtils
from .cache_map import GlobalCacheMap

# Configure logging with detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Router")

# Environment configuration
PROXY_MODE = os.getenv("PROXY_MODE", "false").lower() == "true"
WORKER_URLS = {}  # Will be populated via heartbeat: {worker_id: base_url}

app = FastAPI(title="Stateful Cache-Aware Router")

# Global instances
tokenizer_utils = TokenizerUtils() # Defaults to gpt2 for demo
cache_map = GlobalCacheMap()

class InferenceRequest(BaseModel):
    prompt: str
    max_tokens: int = 100
    prefix_len: Optional[int] = None # New field for explicit prefix length

class EvictionReport(BaseModel):
    worker_id: str
    evicted_hashes: List[str]

class Heartbeat(BaseModel):
    worker_id: str
    current_load: int
    worker_url: Optional[str] = None  # Base URL for proxy mode

@app.post("/v1/completions")
async def generate(request: InferenceRequest):
    """
    Simulated inference endpoint.
    In a real system, this would proxy to the chosen vLLM worker.
    """
    # 1. Compute Prefix Hash
    # Use explicit prefix_len if provided, otherwise use a smart default (e.g., 64 tokens)
    # This prevents "Whole Prompt Hashing" which kills cache hit rates for Chat/RAG.
    effective_prefix_len = request.prefix_len if request.prefix_len is not None else 64
    prefix_hash = tokenizer_utils.compute_prefix_hash(request.prompt, effective_prefix_len)
    
    # 2. Query Cache Map
    candidates = cache_map.get_workers_for_prefix(prefix_hash)
    
    target_worker = None
    cache_status = "MISS"
    
    if candidates:
        # HIT: Route to least loaded among candidates
        target_worker = cache_map.get_least_loaded_worker(candidates)
        cache_status = "HIT"
        logger.info(f"🎯 Cache HIT for hash {prefix_hash[:8]}... -> Routing to {target_worker}")
    else:
        # MISS: Route to globally least loaded
        target_worker = cache_map.get_least_loaded_worker()
        logger.info(f"❌ Cache MISS for hash {prefix_hash[:8]}... -> Routing to {target_worker}")
        
        if target_worker:
            # Speculatively update map (assuming worker will cache it)
            cache_map.update(target_worker, prefix_hash)
            logger.info(f"📝 Speculatively cached {prefix_hash[:8]}... on {target_worker}")

    if not target_worker:
        raise HTTPException(status_code=503, detail="No workers available")

    # 3. Proxy Request (Mode-dependent)
    if PROXY_MODE and target_worker in WORKER_URLS:
        # Real proxy mode: forward to actual vLLM worker
        worker_url = WORKER_URLS[target_worker]
        logger.info(f"🔄 Proxying request to {worker_url}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{worker_url}/v1/completions",
                    json=request.dict()
                )
                return response.json()
            except Exception as e:
                logger.error(f"❌ Proxy failed: {e}")
                raise HTTPException(status_code=502, detail=f"Worker unreachable: {e}")
    else:
        # Simulation mode: return routing decision
        return {
            "assigned_worker": target_worker,
            "status": "forwarded",
            "prefix_hash": prefix_hash,
            "cache_status": cache_status
        }

@app.post("/internal/eviction")
async def report_eviction(report: EvictionReport):
    """Endpoint for workers to report evicted blocks."""
    for h in report.evicted_hashes:
        cache_map.evict(report.worker_id, h)
        logger.info(f"🗑️  EVICTION: {h[:8]}... from {report.worker_id}")
    logger.info(f"Processed eviction report from {report.worker_id}: {len(report.evicted_hashes)} hashes")
    return {"status": "ok"}

@app.post("/internal/heartbeat")
async def heartbeat(hb: Heartbeat):
    """Endpoint for workers to report load."""
    cache_map.update_load(hb.worker_id, hb.current_load)
    
    # Store worker URL for proxy mode
    if hb.worker_url:
        WORKER_URLS[hb.worker_id] = hb.worker_url
        logger.info(f"💓 Heartbeat from {hb.worker_id} (load={hb.current_load}, url={hb.worker_url})")
    else:
        logger.info(f"💓 Heartbeat from {hb.worker_id} (load={hb.current_load})")
    
    return {"status": "ok"}

class SyncReport(BaseModel):
    worker_id: str
    active_hashes: List[str]

@app.post("/internal/sync")
async def sync_state(report: SyncReport):
    """
    Endpoint for workers to fully reconcile their cache state.
    This fixes the 'Phantom Cache' problem by removing stale entries.
    """
    cache_map.sync_worker_state(report.worker_id, report.active_hashes)
    logger.info(f"🔄 SYNC: {report.worker_id} reported {len(report.active_hashes)} active hashes")
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
