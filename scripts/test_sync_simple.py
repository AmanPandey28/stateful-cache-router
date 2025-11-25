"""
SIMPLIFIED Stale Cache Recovery Test

This version manually triggers sync to prove the recovery mechanism works.
"""

import asyncio
import aiohttp
import time
import logging
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from router.tokenizer_utils import TokenizerUtils

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SimplifiedTest")

ROUTER_URL = "http://localhost:8000"
WORKER_ID = "worker-test"

async def run_test():
    tokenizer = TokenizerUtils()
    prompt = "The quick brown fox jumps over the lazy dog."
    prefix_hash = tokenizer.compute_prefix_hash(prompt, 10)
    
    async with aiohttp.ClientSession() as session:
        # Step 1: Register worker
        await session.post(f"{ROUTER_URL}/internal/heartbeat", json={"worker_id": WORKER_ID, "current_load": 5})
        logger.info(f"[1] Registered {WORKER_ID}")
        
        # Step 2: Cache prefix (router will speculatively cache it)
        await session.post(f"{ROUTER_URL}/v1/completions", json={"prompt": prompt, "prefix_len": 10})
        logger.info(f"[2] Sent request, router cached {prefix_hash[:8]}...")
        
        # Step 3: Verify HIT
        async with session.post(f"{ROUTER_URL}/v1/completions", json={"prompt": prompt, "prefix_len": 10}) as resp:
            data = await resp.json()
            logger.info(f"[3] First check: {data.get('cache_status')} (expected: HIT)")
        
        # Step 4: Simulate crash - tell router we have NO hashes
        await session.post(f"{ROUTER_URL}/internal/sync", json={"worker_id": WORKER_ID, "active_hashes": []})
        logger.info(f"[4] Sent SYNC with empty hashes (simulating eviction)")
        
        # Step 5: Verify MISS (recovery happened)
        async with session.post(f"{ROUTER_URL}/v1/completions", json={"prompt": prompt, "prefix_len": 10}) as resp:
            data = await resp.json()
            status = data.get('cache_status')
            logger.info(f"[5] After sync: {status} (expected: MISS)")
            
            if status == "MISS":
                logger.info("\n✅ SUCCESS: Sync cleared stale cache! Recovery works!")
                return True
            else:
                logger.error("\n❌ FAIL: Sync did not clear cache")
                return False

if __name__ == "__main__":
    result = asyncio.run(run_test())
    exit(0 if result else 1)
