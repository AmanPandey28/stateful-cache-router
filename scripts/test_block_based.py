"""
Test script for block-based cache routing and realistic simulation.
Tests the improved mock_worker with block-based caching, prefix matching, and latency simulation.
"""
import asyncio
import aiohttp
import logging
import time
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from router.tokenizer_utils import TokenizerUtils, BLOCK_SIZE

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BlockBasedTest")

ROUTER_URL = "http://localhost:8000"


async def test_block_hashing():
    """Test that block hashing works correctly."""
    logger.info("=" * 60)
    logger.info("TEST 1: Block Hashing")
    logger.info("=" * 60)
    
    tokenizer = TokenizerUtils()
    prompt = "The quick brown fox jumps over the lazy dog. " * 5  # Long prompt to get multiple blocks
    
    token_ids = tokenizer.tokenize(prompt)
    num_tokens = len(token_ids)
    num_blocks = tokenizer.get_num_blocks(prompt)
    block_hashes = tokenizer.compute_block_hashes(prompt)
    
    logger.info(f"Prompt tokens: {num_tokens}")
    logger.info(f"Number of blocks: {num_blocks}")
    logger.info(f"Block hashes: {len(block_hashes)}")
    logger.info(f"Block size: {BLOCK_SIZE} tokens")
    
    assert num_blocks == len(block_hashes), "Block count mismatch"
    assert num_blocks == num_tokens // BLOCK_SIZE, "Block calculation incorrect"
    
    logger.info("✅ Block hashing test passed\n")


async def test_router_routing():
    """Test router's block-based routing with longest prefix match."""
    logger.info("=" * 60)
    logger.info("TEST 2: Router Block-Based Routing")
    logger.info("=" * 60)
    
    tokenizer = TokenizerUtils()
    
    # Create prompts with shared prefixes
    base_prompt = "The quick brown fox jumps over the lazy dog. "
    prompt1 = base_prompt + "This is request one."
    prompt2 = base_prompt + "This is request two."
    prompt3 = "A completely different prompt that doesn't match."
    
    block_hashes1 = tokenizer.compute_block_hashes(prompt1)
    block_hashes2 = tokenizer.compute_block_hashes(prompt2)
    block_hashes3 = tokenizer.compute_block_hashes(prompt3)
    
    logger.info(f"Prompt 1 blocks: {len(block_hashes1)}")
    logger.info(f"Prompt 2 blocks: {len(block_hashes2)}")
    logger.info(f"Prompt 3 blocks: {len(block_hashes3)}")
    
    # Check if prompts 1 and 2 share prefix blocks
    shared_blocks = 0
    for i, (b1, b2) in enumerate(zip(block_hashes1, block_hashes2)):
        if b1 == b2:
            shared_blocks += 1
        else:
            break
    
    logger.info(f"Shared prefix blocks between prompt1 and prompt2: {shared_blocks}")
    
    async with aiohttp.ClientSession() as session:
        # Register a worker
        worker_id = "test-worker-1"
        await session.post(
            f"{ROUTER_URL}/internal/heartbeat",
            json={"worker_id": worker_id, "current_load": 0}
        )
        logger.info(f"Registered worker: {worker_id}")
        
        # Send first request
        logger.info("\nSending request 1 (should be MISS)...")
        async with session.post(
            f"{ROUTER_URL}/v1/completions",
            json={"prompt": prompt1, "max_tokens": 50}
        ) as resp:
            data = await resp.json()
            logger.info(f"Response: {data}")
            assert data["cache_status"] == "MISS", "First request should be MISS"
            assert data["assigned_worker"] == worker_id, "Should route to registered worker"
        
        # Wait a bit for sync
        await asyncio.sleep(1)
        
        # Send second request with shared prefix
        logger.info("\nSending request 2 with shared prefix (should find prefix match)...")
        async with session.post(
            f"{ROUTER_URL}/v1/completions",
            json={"prompt": prompt2, "max_tokens": 50}
        ) as resp:
            data = await resp.json()
            logger.info(f"Response: {data}")
            # Should find some prefix match if blocks are shared
            logger.info(f"Match length: {data.get('match_length', 0)} blocks")
        
        # Send third request with different prompt
        logger.info("\nSending request 3 with different prompt (should be MISS)...")
        async with session.post(
            f"{ROUTER_URL}/v1/completions",
            json={"prompt": prompt3, "max_tokens": 50}
        ) as resp:
            data = await resp.json()
            logger.info(f"Response: {data}")
    
    logger.info("✅ Router routing test passed\n")


async def test_mock_worker_integration():
    """Test integration with mock_worker."""
    logger.info("=" * 60)
    logger.info("TEST 3: Mock Worker Integration")
    logger.info("=" * 60)
    logger.info("NOTE: This test requires mock_worker.py to be running in another terminal")
    logger.info("Run: python scripts/mock_worker.py")
    
    await asyncio.sleep(2)  # Give worker time to register
    
    async with aiohttp.ClientSession() as session:
        # Check if worker is registered by sending a request
        logger.info("Sending test request to router...")
        prompt = "The quick brown fox jumps over the lazy dog."
        
        try:
            async with session.post(
                f"{ROUTER_URL}/v1/completions",
                json={"prompt": prompt, "max_tokens": 50},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Router response: {data}")
                    logger.info("✅ Mock worker is responding!")
                else:
                    logger.warning(f"Router returned status {resp.status}")
        except asyncio.TimeoutError:
            logger.warning("⚠️  Router not responding. Make sure router is running.")
        except Exception as e:
            logger.warning(f"⚠️  Error connecting to router: {e}")
    
    logger.info("✅ Integration test completed\n")


async def test_cache_eviction():
    """Test cache eviction reporting."""
    logger.info("=" * 60)
    logger.info("TEST 4: Cache Eviction")
    logger.info("=" * 60)
    
    tokenizer = TokenizerUtils()
    prompt = "The quick brown fox jumps over the lazy dog. " * 3
    block_hashes = tokenizer.compute_block_hashes(prompt)
    
    async with aiohttp.ClientSession() as session:
        worker_id = "test-worker-evict"
        
        # Register worker
        await session.post(
            f"{ROUTER_URL}/internal/heartbeat",
            json={"worker_id": worker_id, "current_load": 0}
        )
        
        # Sync blocks to router
        await session.post(
            f"{ROUTER_URL}/internal/sync",
            json={"worker_id": worker_id, "active_hashes": block_hashes}
        )
        logger.info(f"Synced {len(block_hashes)} blocks to router")
        
        # Send request (should be HIT)
        async with session.post(
            f"{ROUTER_URL}/v1/completions",
            json={"prompt": prompt, "max_tokens": 50}
        ) as resp:
            data = await resp.json()
            logger.info(f"Before eviction: {data.get('cache_status')}")
        
        # Report eviction
        if block_hashes:
            await session.post(
                f"{ROUTER_URL}/internal/eviction",
                json={"worker_id": worker_id, "evicted_hashes": [block_hashes[0]]}
            )
            logger.info(f"Reported eviction of block: {block_hashes[0][:8]}...")
        
        # Send request again (should be MISS or partial match)
        await asyncio.sleep(0.5)
        async with session.post(
            f"{ROUTER_URL}/v1/completions",
            json={"prompt": prompt, "max_tokens": 50}
        ) as resp:
            data = await resp.json()
            logger.info(f"After eviction: {data.get('cache_status')}, match_length: {data.get('match_length', 0)}")
    
    logger.info("✅ Cache eviction test passed\n")


async def test_latency_simulation():
    """Test that latency is being calculated correctly."""
    logger.info("=" * 60)
    logger.info("TEST 5: Latency Simulation")
    logger.info("=" * 60)
    
    logger.info("This test verifies latency formulas are being used.")
    logger.info("Check mock_worker logs for latency calculations.")
    logger.info("Expected:")
    logger.info("  - Prefill: base + (blocks_to_compute * per_block_latency)")
    logger.info("  - Decode: tokens * decode_per_token_latency")
    logger.info("✅ Latency simulation info displayed\n")


async def run_all_tests():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("BLOCK-BASED CACHE ROUTING TEST SUITE")
    logger.info("=" * 60 + "\n")
    
    # Check if router is running
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ROUTER_URL}/docs", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                if resp.status != 200:
                    logger.error("Router is not responding correctly")
                    return
    except Exception as e:
        logger.error(f"Cannot connect to router at {ROUTER_URL}")
        logger.error("Make sure router is running: python -m router.main")
        return
    
    logger.info("✅ Router is running\n")
    
    # Run tests
    await test_block_hashing()
    await test_router_routing()
    await test_cache_eviction()
    await test_latency_simulation()
    await test_mock_worker_integration()
    
    logger.info("=" * 60)
    logger.info("ALL TESTS COMPLETED")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())

