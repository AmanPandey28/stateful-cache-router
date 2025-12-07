"""
Prefix Length Experiment
Tests different prefix lengths to find optimal hash size
"""
import asyncio
import aiohttp
import logging
import time
import json
from typing import List, Dict
from collections import defaultdict
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

ROUTER_URL = "http://localhost:8000"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PrefixLengthExperiment")


async def test_prefix_length(prefix_length_tokens: int, num_requests: int = 50):
    """Test routing with a specific prefix length."""
    logger.info(f"\nTesting prefix length: {prefix_length_tokens} tokens")
    
    results = {
        "prefix_length_tokens": prefix_length_tokens,
        "cache_hits": 0,
        "cache_misses": 0,
        "latencies": [],
        "match_lengths": [],
    }
    
    # Create prompts with shared prefixes (simulating RAG)
    base_context = "The following document discusses artificial intelligence and machine learning. " * 5
    user_queries = [
        "What is the main topic?",
        "Explain the key concepts.",
        "Summarize the findings.",
        "What are the applications?",
    ]
    
    async with aiohttp.ClientSession() as session:
        for i in range(num_requests):
            # Mix shared and unique prompts
            if i % 2 == 0:  # Even: shared prefix
                prompt = base_context + random.choice(user_queries)
            else:  # Odd: unique
                prompt = f"Unique document {i}. " * 3 + random.choice(user_queries)
            
            start = time.time()
            try:
                # Note: router currently uses block-based hashing, not prefix_len
                # This experiment would require router modification to support prefix_len parameter
                async with session.post(
                    f"{ROUTER_URL}/v1/completions",
                    json={"prompt": prompt, "max_tokens": 50, "prefix_len": prefix_length_tokens},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        latency = (time.time() - start) * 1000
                        
                        results["latencies"].append(latency)
                        results["match_lengths"].append(data.get("match_length", 0))
                        
                        if data.get("cache_status") == "HIT":
                            results["cache_hits"] += 1
                        else:
                            results["cache_misses"] += 1
            except Exception as e:
                logger.error(f"Request {i} failed: {e}")
            
            await asyncio.sleep(0.1)
    
    # Calculate statistics
    if results["latencies"]:
        results["avg_latency"] = sum(results["latencies"]) / len(results["latencies"])
        results["hit_rate"] = (results["cache_hits"] / num_requests) * 100
        results["avg_match_length"] = sum(results["match_lengths"]) / len(results["match_lengths"]) if results["match_lengths"] else 0
    
    return results


async def run_prefix_length_experiment():
    """Test different prefix lengths."""
    logger.info("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    PREFIX LENGTH EXPERIMENT                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

Testing different prefix lengths to find optimal hash size.
Note: Current implementation uses block-based hashing (16 tokens per block).
This experiment tests the concept of prefix length tuning.
    """)
    
    # Test different prefix lengths (in tokens)
    # Note: In block-based system, this translates to number of blocks
    prefix_lengths = [16, 32, 64, 128, 256]  # tokens (1, 2, 4, 8, 16 blocks)
    
    all_results = {}
    
    for prefix_len in prefix_lengths:
        results = await test_prefix_length(prefix_len, num_requests=50)
        all_results[f"{prefix_len}_tokens"] = results
        
        logger.info(f"  Prefix {prefix_len} tokens: "
                   f"Hit Rate: {results.get('hit_rate', 0):.1f}%, "
                   f"Avg Latency: {results.get('avg_latency', 0):.2f}ms")
    
    # Save results
    with open("prefix_length_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    
    # Display summary
    logger.info("\n" + "="*60)
    logger.info("PREFIX LENGTH COMPARISON")
    logger.info("="*60)
    for prefix_len in prefix_lengths:
        key = f"{prefix_len}_tokens"
        if key in all_results:
            r = all_results[key]
            logger.info(f"\n{prefix_len} tokens ({prefix_len//16} blocks):")
            logger.info(f"  Hit Rate:        {r.get('hit_rate', 0):.1f}%")
            logger.info(f"  Avg Latency:     {r.get('avg_latency', 0):.2f} ms")
            logger.info(f"  Avg Match:       {r.get('avg_match_length', 0):.2f} blocks")
    
    logger.info(f"\n💾 Results saved to prefix_length_results.json")
    logger.info("\n" + "="*60)


if __name__ == "__main__":
    import random
    asyncio.run(run_prefix_length_experiment())

