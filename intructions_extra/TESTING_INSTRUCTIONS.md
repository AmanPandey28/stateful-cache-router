# Testing Instructions - Routing Strategies

## Quick Answer

**Yes, you need to test each strategy separately:**

1. **Start router** with strategy 1
2. **Start workers** (same workers work for all strategies)
3. **Run test script** to collect results
4. **Stop router**, start with strategy 2
5. **Workers keep running** (no need to restart)
6. **Run test script** again
7. Repeat for strategy 3

## Detailed Process

### Option 1: Automated Testing (Recommended)

I created `scripts/test_all_strategies.py` that guides you through everything:

```bash
# Just run this script - it will guide you
python scripts/test_all_strategies.py
```

The script will:
- Tell you when to start router with each strategy
- Wait for you to confirm
- Run tests automatically
- Save separate results for each strategy
- Show comparison at the end

### Option 2: Manual Testing

#### Step 1: Test Cache-Aware (Default)

**Terminal 1 - Router:**
```bash
python -m router.main
```

**Terminal 2 - Workers:**
```bash
python scripts/start_multiple_workers.py
```

**Terminal 3 - Test:**
```bash
python scripts/test_routing_strategies.py
# Or use results_dashboard.py to collect metrics
```

**Save results:**
- Results will be in `dashboard_results.json` or similar
- Rename it to `results_cache_aware.json` for comparison

#### Step 2: Test Round-Robin

**Terminal 1 - Router (STOP the old one, start new):**
```bash
# Stop old router (Ctrl+C)
$env:ROUTING_STRATEGY="round_robin"
python -m router.main
```

**Terminal 2 - Workers:**
```bash
# Keep workers running, or restart if needed
python scripts/start_multiple_workers.py
```

**Terminal 3 - Test:**
```bash
python scripts/test_routing_strategies.py
```

**Save results:**
- Rename to `results_round_robin.json`

#### Step 3: Test Least-Loaded

**Terminal 1 - Router (STOP the old one, start new):**
```bash
# Stop old router (Ctrl+C)
$env:ROUTING_STRATEGY="least_loaded"
python -m router.main
```

**Terminal 2 - Workers:**
```bash
# Keep workers running
```

**Terminal 3 - Test:**
```bash
python scripts/test_routing_strategies.py
```

**Save results:**
- Rename to `results_least_loaded.json`

## What Gets Tested

For each strategy, the script collects:
- ✅ Cache hit rate
- ✅ Average latency
- ✅ HIT vs MISS latencies
- ✅ Worker distribution (load balancing)
- ✅ Request routing patterns

## Expected Results

### Cache-Aware
- **Hit Rate**: 35-50% (with RAG-like workloads)
- **Worker Distribution**: Uneven (routes to workers with cache)
- **Latency**: Lower for HITs

### Round-Robin
- **Hit Rate**: 0% (doesn't use cache)
- **Worker Distribution**: Even (cycles through workers)
- **Latency**: Higher (no cache benefits)

### Least-Loaded
- **Hit Rate**: 0% (doesn't use cache)
- **Worker Distribution**: Based on load (routes to least loaded)
- **Latency**: Higher (no cache benefits)

## Quick Test (5 minutes per strategy)

If you just want to verify they work:

```bash
# For each strategy:
# 1. Start router with that strategy
# 2. Start workers
# 3. Send a few requests manually
# 4. Check router logs to see routing behavior
```

## Full Test (15-20 minutes total)

For complete comparison with metrics:

```bash
# Use the automated script
python scripts/test_all_strategies.py
```

This will:
- Test all 3 strategies
- Collect 50 requests per strategy
- Save results to `strategy_comparison_results.json`
- Show comparison table

## Tips

1. **Workers can stay running** - They register with each new router
2. **Router must restart** - Different strategy needs new router instance
3. **Wait for registration** - Give workers 3-5 seconds to register
4. **Use same workload** - Use similar prompts for fair comparison

## Files Created

After testing, you'll have:
- `strategy_comparison_results.json` - All results (if using automated script)
- Or separate files: `results_cache_aware.json`, `results_round_robin.json`, `results_least_loaded.json`

