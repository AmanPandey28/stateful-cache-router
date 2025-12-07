"""
Collect results for the current router strategy.
Run this after starting the router with a specific strategy.
"""
import asyncio
import aiohttp
import logging
import json
import time
from typing import Dict
from collections import defaultdict
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

ROUTER_URL = "http://localhost:8000"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CollectResults")


async def detect_strategy() -> str:
    """Try to detect the current routing strategy."""
    # Check environment variable first
    strategy = os.getenv("ROUTING_STRATEGY", "").lower()
    if strategy in ["cache_aware", "round_robin", "least_loaded"]:
        return strategy
    
    # Try to infer from router response
    try:
        async with aiohttp.ClientSession() as session:
            # Send a test request
            async with session.post(
                f"{ROUTER_URL}/v1/completions",
                json={"prompt": "test", "max_tokens": 5},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    cache_status = data.get("cache_status", "")
                    match_length = data.get("match_length", 0)
                    
                    # If it reports cache hits, it's cache_aware
                    if cache_status == "HIT" or (cache_status == "MISS" and match_length == 0):
                        # Can't distinguish round_robin from least_loaded from one request
                        # Default to asking user
                        return None
    except:
        pass
    
    return None


async def collect_results(strategy_name: str, num_requests: int = 50, warmup: int = 10):
    """Collect metrics for the current routing strategy."""
    logger.info(f"\n{'='*70}")
    logger.info(f"Collecting Results for: {strategy_name.upper()}")
    logger.info(f"{'='*70}\n")
    
    results = {
        "strategy": strategy_name,
        "total_requests": num_requests,
        "cache_hits": 0,
        "cache_misses": 0,
        "latencies": [],
        "hit_latencies": [],
        "miss_latencies": [],
        "worker_distribution": defaultdict(int),
        "match_lengths": [],
    }
    
    # RAG-like prompts with shared contexts (to test cache hits)
    shared_contexts = [
        "The following document discusses artificial intelligence and machine learning applications in healthcare. " * 4,
        "This research paper presents findings on large language models and their capabilities. " * 4,
        "The article covers neural network architectures and training methodologies. " * 4,
    ]
    
    user_queries = [
        "What are the main findings?",
        "Summarize the key points.",
        "What are the applications?",
        "Explain the methodology.",
    ]
    
    async with aiohttp.ClientSession() as session:
        # Check if router is running
        try:
            async with session.get(f"{ROUTER_URL}/docs", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                if resp.status != 200:
                    logger.error("Router is not responding. Make sure it's running on port 8000.")
                    return None
        except Exception as e:
            logger.error(f"Cannot connect to router: {e}")
            logger.error("Make sure router is running: python -m router.main")
            return None
        
        # Warmup phase (to populate cache for cache-aware strategy)
        logger.info(f"Warmup phase ({warmup} requests)...")
        for i in range(warmup):
            prompt = shared_contexts[i % len(shared_contexts)] + user_queries[i % len(user_queries)]
            try:
                async with session.post(
                    f"{ROUTER_URL}/v1/completions",
                    json={"prompt": prompt, "max_tokens": 30},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    await resp.json()
            except:
                pass
            await asyncio.sleep(0.1)
        
        logger.info(f"Main collection phase ({num_requests} requests)...")
        # Main collection phase
        for i in range(num_requests):
            # Mix: 70% shared prefix (for cache hits), 30% unique
            if i % 3 != 0:  # 2 out of 3 use shared context
                prompt = shared_contexts[i % len(shared_contexts)] + user_queries[i % len(user_queries)]
            else:
                prompt = f"Unique document {i}. " * 5 + user_queries[i % len(user_queries)]
            
            start = time.time()
            try:
                async with session.post(
                    f"{ROUTER_URL}/v1/completions",
                    json={"prompt": prompt, "max_tokens": 30},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        latency = (time.time() - start) * 1000
                        
                        cache_status = data.get("cache_status", "UNKNOWN")
                        match_length = data.get("match_length", 0)
                        worker = data.get("assigned_worker", "UNKNOWN")
                        
                        results["latencies"].append(latency)
                        results["match_lengths"].append(match_length)
                        results["worker_distribution"][worker] += 1
                        
                        if cache_status == "HIT":
                            results["cache_hits"] += 1
                            results["hit_latencies"].append(latency)
                        else:
                            results["cache_misses"] += 1
                            results["miss_latencies"].append(latency)
                        
                        if (i + 1) % 10 == 0:
                            logger.info(f"  Progress: {i+1}/{num_requests} requests")
                    else:
                        logger.warning(f"Request {i} failed: {resp.status}")
            except Exception as e:
                logger.warning(f"Request {i} error: {e}")
            
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
    
    if results["hit_latencies"]:
        results["avg_hit_latency"] = sum(results["hit_latencies"]) / len(results["hit_latencies"])
    if results["miss_latencies"]:
        results["avg_miss_latency"] = sum(results["miss_latencies"]) / len(results["miss_latencies"])
    
    results["hit_rate"] = (results["cache_hits"] / num_requests * 100) if num_requests > 0 else 0
    results["avg_match_length"] = sum(results["match_lengths"]) / len(results["match_lengths"]) if results["match_lengths"] else 0
    
    # Convert defaultdict to dict for JSON
    results["worker_distribution"] = dict(results["worker_distribution"])
    
    return results


async def main():
    """Main collection function."""
    logger.info("""
╔══════════════════════════════════════════════════════════════════════════════╗
║              STRATEGY RESULTS COLLECTOR                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

This script collects metrics for the current router strategy.
Make sure:
  1. Router is running with the strategy you want to test
  2. Workers are running and registered
  3. Wait a few seconds after starting router for workers to register
    """)
    
    # Try to detect strategy
    strategy = await detect_strategy()
    
    if not strategy:
        logger.info("\nCould not auto-detect strategy. Please specify:")
        logger.info("  1. cache_aware")
        logger.info("  2. round_robin")
        logger.info("  3. least_loaded")
        strategy = input("\nEnter strategy name: ").strip().lower()
        
        if strategy not in ["cache_aware", "round_robin", "least_loaded"]:
            logger.error(f"Invalid strategy: {strategy}")
            return
    else:
        logger.info(f"\nDetected strategy: {strategy}")
        confirm = input("Is this correct? (y/n): ").strip().lower()
        if confirm != 'y':
            logger.info("  1. cache_aware")
            logger.info("  2. round_robin")
            logger.info("  3. least_loaded")
            strategy = input("\nEnter strategy name: ").strip().lower()
    
    # Get number of requests
    try:
        num_req = input("\nNumber of requests to collect (default 50): ").strip()
        num_requests = int(num_req) if num_req else 50
    except:
        num_requests = 50
    
    logger.info(f"\nStarting collection for {strategy} with {num_requests} requests...")
    
    # Verify workers are registered
    logger.info("Checking for registered workers...")
    async with aiohttp.ClientSession() as session:
        workers_found = False
        for attempt in range(5):  # Try up to 5 times
            try:
                # Send a test request to see if workers are registered
                async with session.post(
                    f"{ROUTER_URL}/v1/completions",
                    json={"prompt": "test", "max_tokens": 1},
                    timeout=aiohttp.ClientTimeout(total=3)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        worker = data.get("assigned_worker")
                        if worker and worker != "UNKNOWN":
                            workers_found = True
                            logger.info(f"✅ Workers registered! Found worker: {worker}")
                            break
            except:
                pass
            
            if not workers_found:
                logger.info(f"   Waiting for workers... (attempt {attempt + 1}/5)")
                await asyncio.sleep(1)
        
        if not workers_found:
            logger.warning("⚠️  No workers detected. They may still be registering.")
            logger.warning("   If collection fails, wait a bit longer and try again.")
            response = input("\nContinue anyway? (y/n): ").strip().lower()
            if response != 'y':
                logger.info("Collection cancelled.")
                return
    
    # Collect results
    results = await collect_results(strategy, num_requests=num_requests, warmup=10)
    
    if not results:
        logger.error("Failed to collect results.")
        return
    
    # Save results
    output_file = f"results_{strategy}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    # Display summary
    logger.info(f"\n{'='*70}")
    logger.info(f"Results Summary: {strategy.upper()}")
    logger.info(f"{'='*70}")
    logger.info(f"Total Requests:     {results['total_requests']}")
    logger.info(f"Cache Hits:         {results['cache_hits']}")
    logger.info(f"Cache Misses:       {results['cache_misses']}")
    logger.info(f"Hit Rate:           {results['hit_rate']:.1f}%")
    logger.info(f"Avg Latency:        {results.get('avg_latency', 0):.2f} ms")
    if 'avg_hit_latency' in results:
        logger.info(f"Avg HIT Latency:    {results['avg_hit_latency']:.2f} ms")
    if 'avg_miss_latency' in results:
        logger.info(f"Avg MISS Latency:   {results['avg_miss_latency']:.2f} ms")
    if 'p95_latency' in results:
        logger.info(f"p95 Latency:        {results['p95_latency']:.2f} ms")
    logger.info(f"\nWorker Distribution:")
    for worker, count in results['worker_distribution'].items():
        logger.info(f"  {worker}: {count} requests ({count/results['total_requests']*100:.1f}%)")
    
    logger.info(f"\n💾 Results saved to {output_file}")
    logger.info(f"\n✅ Collection complete! You can now:")
    logger.info(f"   1. Stop the router (Ctrl+C)")
    logger.info(f"   2. Start router with next strategy")
    logger.info(f"   3. Run this script again")
    logger.info(f"   4. After collecting all strategies, run: python scripts/generate_comparison.py")
    logger.info("="*70)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\nCollection interrupted by user.")

