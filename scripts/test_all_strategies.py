"""
Automated test script that tests all routing strategies and collects separate results.
This script will guide you through testing each strategy one by one.
"""
import asyncio
import aiohttp
import logging
import json
import time
from typing import Dict, List
from collections import defaultdict
import os
import sys

ROUTER_URL = "http://localhost:8000"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("StrategyTest")


async def test_strategy(strategy_name: str, num_requests: int = 50, warmup: int = 10):
    """Test a specific routing strategy and collect metrics."""
    logger.info(f"\n{'='*70}")
    logger.info(f"Testing {strategy_name.upper()} Strategy")
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
        
        logger.info(f"Main test phase ({num_requests} requests)...")
        # Main test phase
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


async def check_router_running():
    """Check if router is running."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ROUTER_URL}/docs", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                return resp.status == 200
    except:
        return False


async def main():
    """Main test runner."""
    logger.info("""
╔══════════════════════════════════════════════════════════════════════════════╗
║         AUTOMATED ROUTING STRATEGY COMPARISON TEST                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

This script will test all three routing strategies:
  1. Cache-Aware (default)
  2. Round-Robin
  3. Least-Loaded

For each strategy, you need to:
  1. Start the router with that strategy
  2. Start workers (if not already running)
  3. Run this script
  4. Results will be saved separately

The script will guide you through each step.
    """)
    
    strategies = [
        ("cache_aware", "Cache-Aware (default)"),
        ("round_robin", "Round-Robin"),
        ("least_loaded", "Least-Loaded"),
    ]
    
    all_results = {}
    
    for strategy_key, strategy_name in strategies:
        logger.info(f"\n{'='*70}")
        logger.info(f"Testing: {strategy_name}")
        logger.info(f"{'='*70}\n")
        
        logger.info(f"📋 Instructions for {strategy_name}:")
        logger.info(f"   1. Open a NEW terminal")
        logger.info(f"   2. Start router with: $env:ROUTING_STRATEGY='{strategy_key}'; python -m router.main")
        if strategy_key == "cache_aware":
            logger.info(f"      (Or just: python -m router.main)")
        logger.info(f"   3. In ANOTHER terminal, start workers:")
        logger.info(f"      python scripts/start_multiple_workers.py")
        logger.info(f"   4. Wait for workers to register (about 5 seconds)")
        logger.info(f"   5. Come back here and press Enter")
        logger.info("")
        
        input(f"Press Enter when router is running with {strategy_name} and workers are started...")
        
        # Check if router is running
        if not await check_router_running():
            logger.error("❌ Router is not running or not accessible!")
            logger.error("   Make sure router is running on http://localhost:8000")
            logger.error("   Skipping this strategy...\n")
            continue
        
        logger.info("✅ Router is running. Starting test...\n")
        
        # Wait a bit for workers to register
        logger.info("Waiting 3 seconds for workers to register...")
        await asyncio.sleep(3)
        
        # Run test
        results = await test_strategy(strategy_key, num_requests=50, warmup=10)
        all_results[strategy_key] = results
        
        # Display results
        logger.info(f"\n{'='*70}")
        logger.info(f"{strategy_name.upper()} Results:")
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
        
        logger.info(f"\n💾 Results saved for {strategy_name}")
        
        if strategy_key != strategies[-1][0]:  # Not the last one
            logger.info("\n" + "="*70)
            logger.info("Next: Stop the router (Ctrl+C) and start with next strategy")
            logger.info("="*70)
            input("\nPress Enter when ready for next strategy (or Ctrl+C to exit)...")
    
    # Save all results
    output_file = "strategy_comparison_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)
    
    # Display comparison
    logger.info("\n" + "="*70)
    logger.info("COMPARISON SUMMARY")
    logger.info("="*70)
    logger.info(f"\n{'Strategy':<20} {'Hit Rate':<12} {'Avg Latency':<15} {'p95 Latency':<15}")
    logger.info("-" * 70)
    
    for strategy_key, strategy_name in strategies:
        if strategy_key in all_results:
            r = all_results[strategy_key]
            logger.info(f"{strategy_name:<20} {r['hit_rate']:>6.1f}%     {r.get('avg_latency', 0):>8.2f} ms    {r.get('p95_latency', 0):>8.2f} ms")
    
    logger.info(f"\n💾 All results saved to {output_file}")
    logger.info("="*70)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\nTest interrupted by user. Partial results may be saved.")
        logger.info("You can run the script again to continue testing.")

