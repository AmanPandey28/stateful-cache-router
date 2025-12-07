"""
Quick test script to verify all routing strategies work correctly.
"""
import asyncio
import aiohttp
import logging
import sys
import os

ROUTER_URL = "http://localhost:8000"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RoutingTest")


async def test_routing_strategy(strategy_name: str, num_requests: int = 10):
    """Test a specific routing strategy."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing {strategy_name.upper()} Routing")
    logger.info(f"{'='*60}\n")
    
    worker_distribution = {}
    
    async with aiohttp.ClientSession() as session:
        for i in range(num_requests):
            prompt = f"Test prompt {i}. " * 5  # Long enough to create blocks
            
            try:
                async with session.post(
                    f"{ROUTER_URL}/v1/completions",
                    json={"prompt": prompt, "max_tokens": 20},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        worker = data.get("assigned_worker", "UNKNOWN")
                        cache_status = data.get("cache_status", "UNKNOWN")
                        
                        worker_distribution[worker] = worker_distribution.get(worker, 0) + 1
                        
                        logger.info(f"Request {i+1}: Worker={worker}, Cache={cache_status}")
                    else:
                        logger.error(f"Request {i+1} failed: {resp.status}")
            except Exception as e:
                logger.error(f"Request {i+1} error: {e}")
            
            await asyncio.sleep(0.2)  # Small delay
    
    # Display results
    logger.info(f"\n{'='*60}")
    logger.info(f"{strategy_name.upper()} Results:")
    logger.info(f"{'='*60}")
    logger.info(f"Total requests: {num_requests}")
    logger.info(f"Worker distribution:")
    for worker, count in worker_distribution.items():
        logger.info(f"  {worker}: {count} requests ({count/num_requests*100:.1f}%)")
    
    return worker_distribution


async def main():
    """Run tests for all routing strategies."""
    logger.info("""
╔══════════════════════════════════════════════════════════════════════════════╗
║              ROUTING STRATEGY TEST                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

This script tests all three routing strategies.
Make sure router is running with the strategy you want to test.

To test different strategies:
  1. Start router with: ROUTING_STRATEGY=cache_aware python -m router.main
  2. Run this script
  3. Restart router with: ROUTING_STRATEGY=round_robin python -m router.main
  4. Run this script again
  5. Restart router with: ROUTING_STRATEGY=least_loaded python -m router.main
  6. Run this script again

Or test one strategy at a time.
    """)
    
    # Check if router is running
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ROUTER_URL}/docs", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                if resp.status != 200:
                    logger.error("Router is not responding. Make sure it's running on port 8000.")
                    return
    except Exception as e:
        logger.error(f"Cannot connect to router: {e}")
        logger.error("Make sure router is running: python -m router.main")
        return
    
    # Get current strategy from environment or ask user
    current_strategy = os.getenv("ROUTING_STRATEGY", "cache_aware")
    
    logger.info(f"\nCurrent ROUTING_STRATEGY environment variable: {current_strategy}")
    logger.info("(If router was started without this, it defaults to 'cache_aware')")
    
    input("\nPress Enter to start testing (make sure router is running with desired strategy)...")
    
    # Test current strategy
    await test_routing_strategy(current_strategy, num_requests=10)
    
    logger.info("\n" + "="*60)
    logger.info("Test complete!")
    logger.info("="*60)
    logger.info("\nTo test other strategies:")
    logger.info("  1. Stop the router (Ctrl+C)")
    logger.info("  2. Start with: $env:ROUTING_STRATEGY='round_robin'; python -m router.main")
    logger.info("  3. Run this script again")
    logger.info("="*60)


if __name__ == "__main__":
    asyncio.run(main())

