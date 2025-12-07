"""
Quick test script - starts router and worker, then runs a simple test.
For manual testing, use separate terminals as described in TESTING.md
"""
import asyncio
import aiohttp
import logging
import time
import subprocess
import sys
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("QuickTest")

ROUTER_URL = "http://localhost:8000"


async def wait_for_router(max_wait=10):
    """Wait for router to be ready."""
    logger.info("Waiting for router to start...")
    for i in range(max_wait):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{ROUTER_URL}/docs", timeout=aiohttp.ClientTimeout(total=1)) as resp:
                    if resp.status == 200:
                        logger.info("✅ Router is ready!")
                        return True
        except:
            pass
        await asyncio.sleep(1)
    return False


async def simple_test():
    """Run a simple end-to-end test."""
    logger.info("\n" + "=" * 60)
    logger.info("QUICK TEST: Block-Based Cache Routing")
    logger.info("=" * 60 + "\n")
    
    if not await wait_for_router():
        logger.error("❌ Router is not running!")
        logger.info("Please start the router first:")
        logger.info("  Terminal 1: python -m router.main")
        logger.info("  Terminal 2: python scripts/mock_worker.py")
        return
    
    # Wait a bit for worker to register
    logger.info("Waiting for worker to register...")
    await asyncio.sleep(3)
    
    async with aiohttp.ClientSession() as session:
        # Test 1: Send a request
        logger.info("\n📤 Test 1: Sending request (should be MISS)...")
        prompt = "The quick brown fox jumps over the lazy dog."
        
        try:
            async with session.post(
                f"{ROUTER_URL}/v1/completions",
                json={"prompt": prompt, "max_tokens": 50},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"✅ Response received:")
                    logger.info(f"   Worker: {data.get('assigned_worker')}")
                    logger.info(f"   Status: {data.get('cache_status')}")
                    logger.info(f"   Blocks: {len(data.get('block_hashes', []))}")
                    logger.info(f"   Match: {data.get('match_length', 0)} blocks")
                else:
                    logger.error(f"❌ Router returned status {resp.status}")
        except asyncio.TimeoutError:
            logger.error("❌ Request timed out")
        except Exception as e:
            logger.error(f"❌ Error: {e}")
        
        # Test 2: Send same request again (might be HIT after sync)
        logger.info("\n📤 Test 2: Sending same request again...")
        await asyncio.sleep(2)  # Wait for sync
        
        try:
            async with session.post(
                f"{ROUTER_URL}/v1/completions",
                json={"prompt": prompt, "max_tokens": 50},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"✅ Response received:")
                    logger.info(f"   Worker: {data.get('assigned_worker')}")
                    logger.info(f"   Status: {data.get('cache_status')}")
                    logger.info(f"   Match: {data.get('match_length', 0)} blocks")
                    if data.get('match_length', 0) > 0:
                        logger.info("   🎯 Found prefix match!")
        except Exception as e:
            logger.error(f"❌ Error: {e}")
        
        # Test 3: Check worker heartbeat
        logger.info("\n📤 Test 3: Checking worker status...")
        # This is just informational - we can't directly query workers
        logger.info("   Check mock_worker.py logs for task processing")
    
    logger.info("\n" + "=" * 60)
    logger.info("Quick test completed!")
    logger.info("=" * 60)
    logger.info("\nFor more comprehensive tests, run:")
    logger.info("  python scripts/test_block_based.py")
    logger.info("\nFor detailed testing guide, see TESTING.md")


if __name__ == "__main__":
    logger.info("""
    ╔══════════════════════════════════════════════════════════════╗
    ║         Block-Based Cache Router - Quick Test                ║
    ╚══════════════════════════════════════════════════════════════╝
    
    This script tests the router and worker integration.
    
    PREREQUISITES:
    1. Start the router:    python -m router.main
    2. Start a worker:       python scripts/mock_worker.py
    
    Then run this script to test the integration.
    """)
    
    asyncio.run(simple_test())

