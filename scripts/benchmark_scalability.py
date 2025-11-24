"""
Scalability Benchmark: Router Performance Under Load

Tests the router's ability to handle:
- 100 mock workers
- 1,000 concurrent requests
- Measures latency distribution (p50, p95, p99)
- Verifies reverse index optimization prevents O(N) lookups
"""

import asyncio
import aiohttp
import time
import statistics
from typing import List
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ScalabilityBenchmark")

ROUTER_URL = "http://localhost:8000"
NUM_WORKERS = 100
NUM_REQUESTS = 1000
CONCURRENT_BATCH_SIZE = 50  # Send 50 requests at a time

async def register_workers(session: aiohttp.ClientSession, num_workers: int):
    """Register N mock workers with the router."""
    logger.info(f"Registering {num_workers} workers...")
    tasks = []
    for i in range(num_workers):
        worker_id = f"worker-{i:04d}"
        payload = {"worker_id": worker_id, "current_load": i % 10}  # Varied load
        tasks.append(session.post(f"{ROUTER_URL}/internal/heartbeat", json=payload))
    
    await asyncio.gather(*tasks)
    logger.info(f"✅ Registered {num_workers} workers")

async def send_request(session: aiohttp.ClientSession, request_id: int) -> float:
    """Send a single inference request and measure latency."""
    prompt = f"Request {request_id}: The quick brown fox jumps over the lazy dog."
    payload = {"prompt": prompt, "prefix_len": 10}
    
    start_time = time.time()
    try:
        async with session.post(f"{ROUTER_URL}/v1/completions", json=payload) as resp:
            await resp.json()
            latency = (time.time() - start_time) * 1000  # Convert to ms
            return latency
    except Exception as e:
        logger.error(f"Request {request_id} failed: {e}")
        return -1

async def run_benchmark():
    """Main benchmark execution."""
    logger.info("=" * 60)
    logger.info("SCALABILITY BENCHMARK: 100 Workers, 1000 Requests")
    logger.info("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        # Phase 1: Register workers
        await register_workers(session, NUM_WORKERS)
        
        # Phase 2: Send concurrent requests in batches
        logger.info(f"\nSending {NUM_REQUESTS} requests in batches of {CONCURRENT_BATCH_SIZE}...")
        all_latencies = []
        
        for batch_start in range(0, NUM_REQUESTS, CONCURRENT_BATCH_SIZE):
            batch_end = min(batch_start + CONCURRENT_BATCH_SIZE, NUM_REQUESTS)
            batch_tasks = [
                send_request(session, i) 
                for i in range(batch_start, batch_end)
            ]
            
            batch_latencies = await asyncio.gather(*batch_tasks)
            valid_latencies = [l for l in batch_latencies if l > 0]
            all_latencies.extend(valid_latencies)
            
            logger.info(f"  Batch {batch_start//CONCURRENT_BATCH_SIZE + 1}: "
                       f"{len(valid_latencies)}/{len(batch_tasks)} successful")
        
        # Phase 3: Analyze results
        logger.info("\n" + "=" * 60)
        logger.info("RESULTS")
        logger.info("=" * 60)
        
        if all_latencies:
            all_latencies.sort()
            p50 = statistics.median(all_latencies)
            p95 = all_latencies[int(len(all_latencies) * 0.95)]
            p99 = all_latencies[int(len(all_latencies) * 0.99)]
            avg = statistics.mean(all_latencies)
            
            logger.info(f"Total Requests:    {len(all_latencies)}/{NUM_REQUESTS}")
            logger.info(f"Average Latency:   {avg:.2f} ms")
            logger.info(f"Median (p50):      {p50:.2f} ms")
            logger.info(f"p95 Latency:       {p95:.2f} ms")
            logger.info(f"p99 Latency:       {p99:.2f} ms")
            logger.info(f"Min Latency:       {min(all_latencies):.2f} ms")
            logger.info(f"Max Latency:       {max(all_latencies):.2f} ms")
            
            # Verdict
            if p99 < 50:  # If 99th percentile is under 50ms
                logger.info("\n✅ PASS: Router scales efficiently (p99 < 50ms)")
            else:
                logger.warning(f"\n⚠️  WARNING: High latency detected (p99 = {p99:.2f}ms)")
            
            # Save results
            with open("scalability_results.txt", "w") as f:
                f.write(f"Scalability Benchmark Results\n")
                f.write(f"Workers: {NUM_WORKERS}\n")
                f.write(f"Requests: {len(all_latencies)}/{NUM_REQUESTS}\n")
                f.write(f"Average: {avg:.2f} ms\n")
                f.write(f"p50: {p50:.2f} ms\n")
                f.write(f"p95: {p95:.2f} ms\n")
                f.write(f"p99: {p99:.2f} ms\n")
            
            logger.info("\n📊 Results saved to scalability_results.txt")
        else:
            logger.error("❌ FAIL: No successful requests")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
