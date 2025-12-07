"""
Baseline Comparison Experiments
Compares Cache-Aware Routing vs Round-Robin vs Least-Loaded
"""
import asyncio
import aiohttp
import logging
import time
import json
import random
from typing import List, Dict
from collections import defaultdict
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

ROUTER_URL = "http://localhost:8000"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BaselineExperiment")


class BaselineRouter:
    """Simulates different routing strategies for comparison."""
    
    def __init__(self, strategy: str = "cache_aware"):
        self.strategy = strategy
        self.worker_loads = {}  # worker_id -> current_load
        self.round_robin_index = {}  # For round-robin
        self.worker_list = []
    
    async def get_worker_loads(self):
        """Fetch current worker loads from router."""
        # In real implementation, would query router's internal state
        # For now, we'll infer from requests
        pass
    
    def route_round_robin(self, workers: List[str]) -> str:
        """Round-robin routing: cycle through workers."""
        if not workers:
            return None
        
        if not self.worker_list:
            self.worker_list = workers.copy()
        
        # Get next worker in round-robin order
        if "rr_index" not in self.round_robin_index:
            self.round_robin_index["rr_index"] = 0
        
        worker = self.worker_list[self.round_robin_index["rr_index"]]
        self.round_robin_index["rr_index"] = (self.round_robin_index["rr_index"] + 1) % len(self.worker_list)
        
        return worker
    
    def route_least_loaded(self, workers: List[str], loads: Dict[str, float]) -> str:
        """Least-loaded routing: pick worker with lowest load."""
        if not workers:
            return None
        
        valid_workers = [w for w in workers if w in loads]
        if not valid_workers:
            return workers[0] if workers else None
        
        return min(valid_workers, key=lambda w: loads.get(w, float('inf')))
    
    def route_cache_aware(self, workers: List[str], loads: Dict[str, float]) -> str:
        """Cache-aware routing: prefer workers with cache, then least loaded."""
        # This is what the actual router does
        # For simulation, we'll use the router's decision
        return self.route_least_loaded(workers, loads)


async def run_baseline_experiment(strategy: str, num_requests: int = 100):
    """Run experiment with a specific routing strategy."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Running {strategy.upper()} Baseline")
    logger.info(f"{'='*60}\n")
    
    results = {
        "strategy": strategy,
        "requests": [],
        "cache_hits": 0,
        "cache_misses": 0,
        "latencies": [],
        "worker_distribution": defaultdict(int),
    }
    
    # Test prompts with shared prefixes (simulating RAG)
    base_prompts = [
        "The following is a document about artificial intelligence. " * 3,
        "This article discusses machine learning and deep learning. " * 3,
        "The research paper presents findings on neural networks. " * 3,
    ]
    
    async with aiohttp.ClientSession() as session:
        for i in range(num_requests):
            # Simulate RAG: sometimes use same prefix, sometimes different
            if random.random() < 0.6:  # 60% chance of shared prefix
                prompt = random.choice(base_prompts) + f"User question {i}."
            else:
                prompt = f"Unique prompt {i}. " * 2
            
            start = time.time()
            try:
                async with session.post(
                    f"{ROUTER_URL}/v1/completions",
                    json={"prompt": prompt, "max_tokens": 50},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        latency = (time.time() - start) * 1000
                        
                        request_result = {
                            "request_id": i,
                            "cache_status": data.get("cache_status", "UNKNOWN"),
                            "match_length": data.get("match_length", 0),
                            "worker": data.get("assigned_worker", "UNKNOWN"),
                            "latency_ms": latency,
                        }
                        
                        results["requests"].append(request_result)
                        results["latencies"].append(latency)
                        results["worker_distribution"][request_result["worker"]] += 1
                        
                        if request_result["cache_status"] == "HIT":
                            results["cache_hits"] += 1
                        else:
                            results["cache_misses"] += 1
                        
                        if (i + 1) % 20 == 0:
                            logger.info(f"  Processed {i+1}/{num_requests} requests...")
            except Exception as e:
                logger.error(f"Request {i} failed: {e}")
            
            # Small delay between requests
            await asyncio.sleep(0.1)
    
    # Calculate statistics
    if results["latencies"]:
        results["avg_latency"] = sum(results["latencies"]) / len(results["latencies"])
        results["min_latency"] = min(results["latencies"])
        results["max_latency"] = max(results["latencies"])
        sorted_lat = sorted(results["latencies"])
        results["p50_latency"] = sorted_lat[len(sorted_lat)//2]
        if len(sorted_lat) > 10:
            results["p95_latency"] = sorted_lat[int(len(sorted_lat)*0.95)]
            results["p99_latency"] = sorted_lat[int(len(sorted_lat)*0.99)]
    
    results["hit_rate"] = (results["cache_hits"] / len(results["requests"]) * 100) if results["requests"] else 0
    
    return results


async def run_all_baselines():
    """Run all baseline experiments and compare."""
    logger.info("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    BASELINE COMPARISON EXPERIMENTS                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

This will compare:
  1. Cache-Aware Routing (our approach)
  2. Round-Robin (baseline)
  3. Least-Loaded (baseline)

Note: Round-Robin and Least-Loaded require router modifications.
For now, we'll run Cache-Aware and document the comparison framework.
    """)
    
    # Run cache-aware experiment (current implementation)
    cache_aware_results = await run_baseline_experiment("cache_aware", num_requests=100)
    
    # Save results
    with open("baseline_results.json", "w") as f:
        json.dump({
            "cache_aware": cache_aware_results,
            "note": "Round-robin and least-loaded baselines require router modifications"
        }, f, indent=2)
    
    # Display comparison
    logger.info("\n" + "="*60)
    logger.info("RESULTS SUMMARY")
    logger.info("="*60)
    logger.info(f"\nCache-Aware Routing:")
    logger.info(f"  Total Requests:    {len(cache_aware_results['requests'])}")
    logger.info(f"  Cache Hits:         {cache_aware_results['cache_hits']}")
    logger.info(f"  Cache Misses:       {cache_aware_results['cache_misses']}")
    logger.info(f"  Hit Rate:           {cache_aware_results['hit_rate']:.1f}%")
    logger.info(f"  Avg Latency:        {cache_aware_results.get('avg_latency', 0):.2f} ms")
    logger.info(f"  p50 Latency:        {cache_aware_results.get('p50_latency', 0):.2f} ms")
    if 'p95_latency' in cache_aware_results:
        logger.info(f"  p95 Latency:        {cache_aware_results['p95_latency']:.2f} ms")
    
    logger.info(f"\n💾 Results saved to baseline_results.json")
    logger.info("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(run_all_baselines())

