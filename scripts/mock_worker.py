import asyncio
import aiohttp
import logging
import sys
import random
from router.tokenizer_utils import TokenizerUtils

# Add the parent directory to sys.path to import router and vllm_patch
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from vllm_patch.vllm.engine.eviction_reporter import EvictionReporter
except ImportError:
    # Fallback if running from root
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MockWorker")

ROUTER_URL = "http://localhost:8000"
WORKER_ID = f"worker-{random.randint(1000, 9999)}"

async def sync_loop(worker_id: str, active_hashes: set):
    """Periodically sync state with router."""
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                payload = {
                    "worker_id": worker_id,
                    "active_hashes": list(active_hashes)
                }
                async with session.post(f"{ROUTER_URL}/internal/sync", json=payload) as resp:
                    if resp.status != 200:
                        logger.error(f"Sync failed: {resp.status}")
            except Exception as e:
                logger.error(f"Sync error: {e}")
            
            await asyncio.sleep(5) # Sync every 5 seconds

async def main():
    logger.info(f"Starting Mock Worker: {WORKER_ID}")
    
    # Initialize Reporter
    reporter = EvictionReporter(ROUTER_URL, WORKER_ID)
    await reporter.start()
    
    tokenizer = TokenizerUtils()
    
    # Simulate "Caching" a prefix
    prompt = "The quick brown fox jumps over the lazy dog."
    prefix_hash = tokenizer.compute_prefix_hash(prompt)
    
    # Maintain local state of what we have cached
    active_hashes = {prefix_hash}
    logger.info(f"Simulating cache for hash: {prefix_hash}")
    
    # Start Sync Loop
    sync_task = asyncio.create_task(sync_loop(WORKER_ID, active_hashes))
    
    # Send a heartbeat to register
    async with aiohttp.ClientSession() as session:
        await session.post(f"{ROUTER_URL}/internal/heartbeat", json={"worker_id": WORKER_ID, "current_load": 5})
    
    logger.info("Sent heartbeat. Sync loop running...")
    await asyncio.sleep(10)
    
    # Simulate Eviction
    logger.info(f"Evicting hash: {prefix_hash}")
    reporter.add_evicted_hash(prefix_hash)
    active_hashes.remove(prefix_hash) # Update local state so next sync reflects this
    
    logger.info("Waiting for reporter to flush and sync to update...")
    await asyncio.sleep(6) # Wait for flush and next sync
    
    sync_task.cancel()
    await reporter.stop()
    logger.info("Mock Worker finished.")

if __name__ == "__main__":
    asyncio.run(main())
