import asyncio
import aiohttp
import logging
import random
import time
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from router.tokenizer_utils import TokenizerUtils

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Benchmark")

ROUTER_URL = "http://localhost:8000"
WORKER_ID = "worker-benchmark"

async def run_benchmark():
    logger.info("Starting End-to-End Benchmark...")
    
    tokenizer = TokenizerUtils()
    prompt = "The quick brown fox jumps over the lazy dog."
    # Default prefix len is 64, but our prompt is short, so it will hash the whole thing if we don't specify.
    # Let's be explicit for the test.
    prefix_len = 10 
    prefix_hash = tokenizer.compute_prefix_hash(prompt, prefix_len)
    logger.info(f"Target Prefix Hash: {prefix_hash}")

    async with aiohttp.ClientSession() as session:
        # 1. Register Worker (Heartbeat)
        logger.info("1. Registering Worker...")
        await session.post(f"{ROUTER_URL}/internal/heartbeat", json={"worker_id": WORKER_ID, "current_load": 0})
        
        # 2. Send Request A (Cache Miss -> Speculative Update)
        logger.info("2. Sending Request A (Expect Cache Miss)...")
        payload = {"prompt": prompt, "prefix_len": prefix_len}
        async with session.post(f"{ROUTER_URL}/v1/completions", json=payload) as resp:
            data = await resp.json()
            logger.info(f"Response A: {data}")
            assert data["assigned_worker"] == WORKER_ID, f"Expected {WORKER_ID}, got {data['assigned_worker']}"
            
        # Wait for router to update map (it's speculative, so immediate)
        
        # 3. Send Request B (Cache Hit)
        logger.info("3. Sending Request B (Expect Cache Hit)...")
        # Increase load on our worker to see if it still picks it (Sticky)
        await session.post(f"{ROUTER_URL}/internal/heartbeat", json={"worker_id": WORKER_ID, "current_load": 10})
        
        # Register a second worker with lower load to prove stickiness
        WORKER_2 = "worker-benchmark-2"
        await session.post(f"{ROUTER_URL}/internal/heartbeat", json={"worker_id": WORKER_2, "current_load": 0})
        
        async with session.post(f"{ROUTER_URL}/v1/completions", json=payload) as resp:
            data = await resp.json()
            logger.info(f"Response B: {data}")
            # It should still pick WORKER_ID because it has the cache, even though WORKER_2 is empty.
            # (Assuming Sticky-Least-Loaded logic prioritizes cache over load for small load diffs)
            # Actually, our current logic is:
            # candidates = get_workers_for_prefix()
            # if candidates: return least_loaded(candidates)
            # So if WORKER_ID is the ONLY candidate, it MUST pick it.
            assert data["assigned_worker"] == WORKER_ID, f"Expected {WORKER_ID} (Cache Hit), got {data['assigned_worker']}"

        # 4. Simulate Eviction
        logger.info("4. Simulating Eviction...")
        eviction_payload = {"worker_id": WORKER_ID, "evicted_hashes": [prefix_hash]}
        await session.post(f"{ROUTER_URL}/internal/eviction", json=eviction_payload)
        
        # 5. Send Request C (Cache Miss -> Load Balanced)
        logger.info("5. Sending Request C (Expect Cache Miss -> Load Balanced)...")
        async with session.post(f"{ROUTER_URL}/v1/completions", json=payload) as resp:
            data = await resp.json()
            logger.info(f"Response C: {data}")
            # Now that WORKER_ID evicted it, it's a global miss.
            # WORKER_2 has load 0, WORKER_ID has load 10.
            # Should pick WORKER_2.
            assert data["assigned_worker"] == WORKER_2, f"Expected {WORKER_2} (Load Balanced), got {data['assigned_worker']}"

    logger.info("Benchmark Passed! \u2705")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
