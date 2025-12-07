# Testing Guide for Block-Based Cache Router

This guide explains how to test the improved block-based cache routing system.

## Prerequisites

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Make sure you have Python 3.8+ installed.

## Quick Start Testing

### Step 1: Start the Router

Open Terminal 1:
```bash
python -m router.main
```

You should see:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 2: Start a Mock Worker

Open Terminal 2:
```bash
python scripts/mock_worker.py
```

You should see:
```
INFO: Starting Mock Worker: worker-XXXX
INFO: Cache capacity: 924 blocks (14784 tokens)
INFO: Loaded lightweight model for token generation
```

### Step 3: Run Tests

Open Terminal 3:
```bash
python scripts/test_block_based.py
```

This will run comprehensive tests including:
- Block hashing verification
- Router block-based routing
- Cache eviction
- Latency simulation
- Mock worker integration

## Manual Testing

### Test 1: Basic Request Routing

```bash
# Send a request to the router
curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "The quick brown fox jumps over the lazy dog.",
    "max_tokens": 50
  }'
```

Expected response:
```json
{
  "assigned_worker": "worker-XXXX",
  "status": "forwarded",
  "block_hashes": ["hash1", "hash2", ...],
  "match_length": 0,
  "cache_status": "MISS"
}
```

### Test 2: Prefix Matching

Send the same request twice:
```bash
# First request (MISS)
curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"prompt": "The quick brown fox", "max_tokens": 50}'

# Second request with shared prefix (should find match)
curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"prompt": "The quick brown fox jumps over", "max_tokens": 50}'
```

The second request should show `match_length > 0` if blocks are shared.

### Test 3: Check Worker State

Monitor the mock worker logs to see:
- Block allocation
- Cache hits/misses
- Latency calculations
- Task completion

Example log output:
```
INFO: Added task req-1: blocks=3, cached=0, to_compute=3
INFO: Task req-1 completed: prefill_blocks=0/3, decode_tokens=45, total_latency=1250.50ms
```

### Test 4: Cache Eviction

1. Send multiple requests to fill up cache
2. Watch for eviction messages in worker logs:
```
INFO: Evicted block: abc12345...
```

3. Check router logs for eviction reports:
```
INFO: 🗑️  EVICTION: abc12345... from worker-XXXX
```

## Testing Block-Based Features

### Verify Block Hashing

```python
from router.tokenizer_utils import TokenizerUtils

tokenizer = TokenizerUtils()
prompt = "The quick brown fox jumps over the lazy dog. " * 5

block_hashes = tokenizer.compute_block_hashes(prompt)
print(f"Number of blocks: {len(block_hashes)}")
print(f"Block hashes: {block_hashes[:3]}...")  # First 3 blocks
```

### Verify Prefix Matching

The router uses a prefix tree to find the longest matching prefix. Test with:

```python
# Two prompts with shared prefix
prompt1 = "The quick brown fox jumps over the lazy dog. Request one."
prompt2 = "The quick brown fox jumps over the lazy dog. Request two."

# Both should share the first few blocks
# Router will find the longest match
```

### Verify Reference Counting

1. Send two requests with the same prefix
2. Both should use the same cached blocks
3. When both complete, blocks become evictable
4. Check that blocks are only evicted when ref_count = 0

### Verify Latency Calculations

Monitor mock_worker logs for latency breakdown:
- **Prefill latency**: `PREFILL_BASE_MS + (blocks_to_compute * PREFILL_PER_BLOCK_MS)`
- **Decode latency**: `decode_tokens * DECODE_PER_TOKEN_MS`

Example:
```
Prefill: 5.0ms + (3 blocks * 2.5ms) = 12.5ms
Decode: 50 tokens * 15.0ms = 750ms
Total: 762.5ms
```

## Running Existing Benchmarks

### Basic Benchmark
```bash
# Terminal 1: Router
python -m router.main

# Terminal 2: Benchmark
python scripts/benchmark.py
```

### Scalability Test
```bash
# Terminal 1: Router
python -m router.main

# Terminal 2: Scalability test
python scripts/benchmark_scalability.py
```

## Troubleshooting

### Router not starting
- Check if port 8000 is already in use
- Verify all dependencies are installed: `pip install -r requirements.txt`

### Mock worker not connecting
- Ensure router is running first
- Check ROUTER_URL in mock_worker.py matches router address
- Check firewall settings

### No cache hits
- Wait for sync cycle (5 seconds)
- Ensure requests share enough tokens to create matching blocks
- Check that blocks are being synced: look for sync messages in router logs

### Import errors
- Make sure you're running from project root
- Install missing packages: `pip install transformers torch` (optional, for token generation)

## Expected Behavior

### Cache Hit Flow
1. Request arrives with prompt
2. Router computes block hashes
3. Router finds longest prefix match in prefix tree
4. Routes to worker with most matching blocks
5. Worker uses cached blocks (fast prefill)
6. Worker generates decode tokens

### Cache Miss Flow
1. Request arrives with prompt
2. Router computes block hashes
3. No matching prefix found
4. Routes to least loaded worker
5. Worker allocates new blocks
6. Worker computes prefill (slower)
7. Worker generates decode tokens

### Eviction Flow
1. Request completes
2. Blocks marked as evictable (but not evicted due to prefix caching)
3. When new blocks needed and cache full:
   - Priority queue finds oldest evictable block
   - Block evicted (ref_count = 0)
   - Eviction reported to router
4. Router updates prefix tree

## Performance Metrics to Monitor

1. **Cache Hit Rate**: Percentage of requests that find cached blocks
2. **Average Latency**: Total request latency (prefill + decode)
3. **Block Utilization**: How many of 924 blocks are in use
4. **Eviction Rate**: How often blocks are evicted
5. **Prefix Match Length**: Average number of matching blocks

## Next Steps

- Run longer benchmarks to see cache warming
- Test with multiple workers
- Monitor latency distributions
- Test edge cases (very long prompts, many concurrent requests)

