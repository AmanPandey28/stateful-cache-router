"""
Complete Comparison Experiment
Runs all three routing strategies and compares results
"""
import asyncio
import aiohttp
import logging
import time
import json
import subprocess
import sys
import os
from typing import Dict, List
from collections import defaultdict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

ROUTER_URL = "http://localhost:8000"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ComparisonExperiment")


async def run_strategy_experiment(strategy: str, num_requests: int = 100, warmup: int = 10):
    """Run experiment with a specific routing strategy."""
    logger.info(f"\n{'='*70}")
    logger.info(f"Testing Strategy: {strategy.upper()}")
    logger.info(f"{'='*70}\n")
    
    results = {
        "strategy": strategy,
        "total_requests": num_requests,
        "cache_hits": 0,
        "cache_misses": 0,
        "latencies": [],
        "hit_latencies": [],
        "miss_latencies": [],
        "worker_distribution": defaultdict(int),
        "match_lengths": [],
    }
    
    # RAG-like prompts with shared contexts
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
        # Warmup phase (to populate cache)
        logger.info(f"Warmup phase ({warmup} requests)...")
        for i in range(warmup):
            prompt = random.choice(shared_contexts) + random.choice(user_queries)
            try:
                async with session.post(
                    f"{ROUTER_URL}/v1/completions",
                    json={"prompt": prompt, "max_tokens": 50},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    await resp.json()
            except:
                pass
            await asyncio.sleep(0.1)
        
        logger.info(f"Main experiment phase ({num_requests} requests)...")
        # Main experiment
        for i in range(num_requests):
            # Mix: 70% shared prefix (simulating RAG), 30% unique
            if random.random() < 0.7:
                prompt = random.choice(shared_contexts) + random.choice(user_queries)
            else:
                prompt = f"Unique document {i}. " * 5 + random.choice(user_queries)
            
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
                        
                        if (i + 1) % 25 == 0:
                            logger.info(f"  Progress: {i+1}/{num_requests} requests")
            except Exception as e:
                logger.warning(f"Request {i} failed: {e}")
            
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
    
    return results


async def run_all_strategies():
    """Run experiments for all routing strategies."""
    logger.info("""
╔══════════════════════════════════════════════════════════════════════════════╗
║              ROUTING STRATEGY COMPARISON EXPERIMENT                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

This experiment compares:
  1. Cache-Aware Routing (our approach)
  2. Round-Robin (baseline)
  3. Least-Loaded (baseline)

⚠️  IMPORTANT: You need to restart the router with different ROUTING_STRATEGY
   environment variable for each strategy.

Example:
  ROUTING_STRATEGY=cache_aware python -m router.main
  ROUTING_STRATEGY=round_robin python -m router.main
  ROUTING_STRATEGY=least_loaded python -m router.main
    """)
    
    input("Press Enter when router is running with cache_aware strategy...")
    
    strategies = ["cache_aware", "round_robin", "least_loaded"]
    all_results = {}
    
    for strategy in strategies:
        logger.info(f"\n⚠️  Make sure router is running with: ROUTING_STRATEGY={strategy}")
        input(f"Press Enter to run {strategy} experiment...")
        
        results = await run_strategy_experiment(strategy, num_requests=100, warmup=20)
        all_results[strategy] = results
        
        logger.info(f"\n✅ {strategy.upper()} Results:")
        logger.info(f"   Hit Rate:        {results['hit_rate']:.1f}%")
        logger.info(f"   Avg Latency:     {results['avg_latency']:.2f} ms")
        if 'avg_hit_latency' in results:
            logger.info(f"   Avg HIT Latency:  {results['avg_hit_latency']:.2f} ms")
        if 'avg_miss_latency' in results:
            logger.info(f"   Avg MISS Latency: {results['avg_miss_latency']:.2f} ms")
    
    # Save all results
    with open("comparison_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    
    # Display comparison table
    logger.info("\n" + "="*70)
    logger.info("COMPARISON SUMMARY")
    logger.info("="*70)
    logger.info(f"\n{'Strategy':<20} {'Hit Rate':<12} {'Avg Latency':<15} {'p95 Latency':<15}")
    logger.info("-" * 70)
    
    for strategy in strategies:
        if strategy in all_results:
            r = all_results[strategy]
            logger.info(f"{strategy:<20} {r['hit_rate']:>6.1f}%     {r['avg_latency']:>8.2f} ms    {r.get('p95_latency', 0):>8.2f} ms")
    
    logger.info(f"\n💾 Full results saved to comparison_results.json")
    logger.info("\n" + "="*70)


if __name__ == "__main__":
    import random
    asyncio.run(run_all_strategies())

