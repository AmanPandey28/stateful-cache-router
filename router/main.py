from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import logging
import os
import httpx
import threading

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
ROUTING_STRATEGY = os.getenv("ROUTING_STRATEGY", "cache_aware").lower()  # cache_aware, round_robin, least_loaded
WORKER_URLS = {}  # Will be populated via heartbeat: {worker_id: base_url}

app = FastAPI(title="Stateful Cache-Aware Router")

# Round-robin state
round_robin_index = 0
round_robin_lock = threading.Lock()

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

def route_round_robin() -> Optional[str]:
    """Round-robin routing: cycle through workers."""
    global round_robin_index
    with round_robin_lock:
        workers = list(cache_map._worker_load.keys())
        if not workers:
            return None
        worker = workers[round_robin_index % len(workers)]
        round_robin_index += 1
        return worker

@app.post("/v1/completions")
async def generate(request: InferenceRequest):
    """
    Simulated inference endpoint.
    Supports multiple routing strategies: cache_aware, round_robin, least_loaded
    """
    # 1. Compute block hashes for the prompt
    block_hashes = tokenizer_utils.compute_block_hashes(request.prompt)
    
    target_worker = None
    match_length = 0
    cache_status = "MISS"
    
    # Route based on strategy
    if ROUTING_STRATEGY == "round_robin":
        # Round-robin: ignore cache, just cycle through workers
        target_worker = route_round_robin()
        logger.info(f"🔄 Round-Robin: Routing to {target_worker}")
        
    elif ROUTING_STRATEGY == "least_loaded":
        # Least-loaded: ignore cache, pick least loaded worker
        target_worker = cache_map.get_least_loaded_worker()
        # Speculatively increase load (will be corrected by next heartbeat)
        if target_worker:
            current_load = cache_map._worker_load.get(target_worker, 0)
            # Estimate: add ~50ms per request (rough estimate)
            cache_map.update_load(target_worker, current_load + 50)
        logger.info(f"⚖️  Least-Loaded: Routing to {target_worker} (load={cache_map._worker_load.get(target_worker, 0)})")
        
    else:  # cache_aware (default)
        # 2. Find worker with longest prefix match using prefix tree
        target_worker, match_length = cache_map.find_longest_prefix_match(block_hashes)
        
        if target_worker and match_length > 0:
            # HIT: Found a worker with matching prefix blocks
            cache_status = "HIT"
            logger.info(
                f"🎯 Cache HIT: {match_length}/{len(block_hashes)} blocks matched "
                f"-> Routing to {target_worker}"
            )
        else:
            # MISS: No matching prefix found, route to least loaded worker
            target_worker = cache_map.get_least_loaded_worker()
            logger.info(
                f"❌ Cache MISS: 0/{len(block_hashes)} blocks matched "
                f"-> Routing to {target_worker}"
            )
            
            if target_worker and block_hashes:
                # Speculatively update map with block sequence (assuming worker will cache it)
                cache_map.update_block_sequence(target_worker, block_hashes)
                logger.info(f"📝 Speculatively cached {len(block_hashes)} blocks on {target_worker}")

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
            "block_hashes": block_hashes,
            "match_length": match_length if cache_status == "HIT" else 0,
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
