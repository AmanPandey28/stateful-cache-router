"""
Stale Cache Window Benchmark: Consistency Guarantee Measurement

Tests the router's anti-entropy sync mechanism:
- Simulates worker crash (stops eviction reports but keeps heartbeat)
- Measures "False Hit" window before sync loop recovers
- Verifies 5-second recovery guarantee
"""

import asyncio
import aiohttp
import time
import logging
import os
import sys

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from router.tokenizer_utils import TokenizerUtils

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("StaleCacheBenchmark")

ROUTER_URL = "http://localhost:8000"
WORKER_ID = "worker-stale-test"
SYNC_INTERVAL = 5  # Router's sync interval in seconds

class StaleCacheSimulator:
    def __init__(self):
        self.tokenizer = TokenizerUtils()
        self.active_hashes = set()
        self.sync_running = False
        
    async def sync_loop(self, session: aiohttp.ClientSession):
        """Periodic sync loop (mimics real worker)."""
        while self.sync_running:
            try:
                payload = {
                    "worker_id": WORKER_ID,
                    "active_hashes": list(self.active_hashes)
                }
                await session.post(f"{ROUTER_URL}/internal/sync", json=payload)
                logger.info(f"[SYNC] Sent sync: {len(self.active_hashes)} active hashes")
            except Exception as e:
                logger.error(f"Sync failed: {e}")
            
            await asyncio.sleep(SYNC_INTERVAL)
    
    async def register_worker(self, session: aiohttp.ClientSession):
        """Register worker with router."""
        payload = {"worker_id": WORKER_ID, "current_load": 5}
        await session.post(f"{ROUTER_URL}/internal/heartbeat", json=payload)
        logger.info(f"[OK] Registered {WORKER_ID}")
    
    async def cache_prefix(self, session: aiohttp.ClientSession, prompt: str, prefix_len: int) -> str:
        """Simulate caching a prefix and return its hash."""
        prefix_hash = self.tokenizer.compute_prefix_hash(prompt, prefix_len)
        self.active_hashes.add(prefix_hash)
        
        # Send request to router (which will speculatively cache it)
        payload = {"prompt": prompt, "prefix_len": prefix_len}
        await session.post(f"{ROUTER_URL}/v1/completions", json=payload)
        
        logger.info(f"[CACHE] Cached prefix: {prefix_hash[:8]}...")
        return prefix_hash
    
    async def evict_prefix(self, session: aiohttp.ClientSession, prefix_hash: str, send_report: bool = True):
        """Evict a prefix (optionally without reporting)."""
        self.active_hashes.discard(prefix_hash)
        
        if send_report:
            # Normal eviction: send report
            payload = {"worker_id": WORKER_ID, "evicted_hashes": [prefix_hash]}
            await session.post(f"{ROUTER_URL}/internal/eviction", json=payload)
            logger.info(f"[EVICT] Evicted {prefix_hash[:8]}... (reported)")
        else:
            # Crash simulation: evict locally but don't report
            logger.warning(f"[CRASH] Evicted {prefix_hash[:8]}... (NOT reported)")
    
    async def check_routing(self, session: aiohttp.ClientSession, prompt: str, prefix_len: int) -> str:
        """Send request and check which worker was assigned."""
        payload = {"prompt": prompt, "prefix_len": prefix_len}
        async with session.post(f"{ROUTER_URL}/v1/completions", json=payload) as resp:
            data = await resp.json()
            return data.get("assigned_worker"), data.get("cache_status")

async def run_benchmark():
    """Main benchmark execution."""
    logger.info("=" * 60)
    logger.info("STALE CACHE WINDOW BENCHMARK")
    logger.info("=" * 60)
    
    simulator = StaleCacheSimulator()
    prompt = "The quick brown fox jumps over the lazy dog."
    prefix_len = 10
    
    async with aiohttp.ClientSession() as session:
        # Phase 1: Setup
        await simulator.register_worker(session)
        simulator.sync_running = True
        sync_task = asyncio.create_task(simulator.sync_loop(session))
        
        # Phase 2: Cache a prefix
        logger.info("\n--- Phase 1: Cache Prefix ---")
        prefix_hash = await simulator.cache_prefix(session, prompt, prefix_len)
        await asyncio.sleep(1)  # Let router process
        
        # Verify cache hit
        worker, status = await simulator.check_routing(session, prompt, prefix_len)
        logger.info(f"Routing check: {worker} (status={status})")
        assert status == "HIT", "Expected cache HIT"
        
        # Phase 3: Simulate crash (evict without reporting)
        logger.info("\n--- Phase 2: Simulate Crash ---")
        await simulator.evict_prefix(session, prefix_hash, send_report=False)
        
        # Phase 4: Measure false hit window
        logger.info("\n--- Phase 3: Measure False Hit Window ---")
        false_hits = 0
        start_time = time.time()
        recovery_time = None
        
        for i in range(15):  # Check for 15 seconds (3x sync interval)
            await asyncio.sleep(1)
            worker, status = await simulator.check_routing(session, prompt, prefix_len)
            elapsed = time.time() - start_time
            
            if status == "HIT":
                false_hits += 1
                logger.warning(f"  [{elapsed:.1f}s] [FALSE HIT] detected (routed to {worker})")
            else:
                if recovery_time is None:
                    recovery_time = elapsed
                logger.info(f"  [{elapsed:.1f}s] [OK] Correctly routed as MISS")
        
        # Phase 5: Results
        logger.info("\n" + "=" * 60)
        logger.info("RESULTS")
        logger.info("=" * 60)
        logger.info(f"False Hits Detected:  {false_hits}")
        if recovery_time:
            logger.info(f"Recovery Time:        {recovery_time:.1f}s")
        else:
            logger.info(f"Recovery Time:        NOT RECOVERED (still seeing false hits)")
        logger.info(f"Expected Recovery:    <= {SYNC_INTERVAL}s")
        
        if recovery_time and recovery_time <= SYNC_INTERVAL + 1:  # +1s tolerance
            logger.info(f"\n[PASS] Recovery within {SYNC_INTERVAL}s guarantee")
        else:
            if recovery_time:
                logger.error(f"\n[FAIL] Recovery took {recovery_time:.1f}s (expected <={SYNC_INTERVAL}s)")
            else:
                logger.error(f"\n[FAIL] System did not recover within test window (15s)")
        
        # Save results
        with open("stale_cache_results.txt", "w") as f:
            f.write(f"Stale Cache Window Benchmark Results\n")
            f.write(f"False Hits: {false_hits}\n")
            if recovery_time:
                f.write(f"Recovery Time: {recovery_time:.1f}s\n")
            else:
                f.write(f"Recovery Time: NOT RECOVERED\n")
            f.write(f"Expected: <={SYNC_INTERVAL}s\n")
        
        logger.info("\n[RESULTS] Saved to stale_cache_results.txt")
        
        # Cleanup
        simulator.sync_running = False
        sync_task.cancel()

if __name__ == "__main__":
    asyncio.run(run_benchmark())
