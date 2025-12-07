# Step-by-Step Guide: Testing All Routing Strategies

## Overview

This guide walks you through testing each routing strategy separately and generating a comparison table and graph.

## Prerequisites

- Router code with strategy support
- Workers running
- Python environment with required packages

## Step-by-Step Instructions

### Step 1: Start Workers (Do this once, keep them running)

**Terminal 1 - Start Workers:**
```bash
python scripts/start_multiple_workers.py
```

**Keep this terminal running!** Workers will stay active for all strategy tests.

---

### Step 2: Test Cache-Aware Strategy

**Terminal 2 - Start Router (Cache-Aware):**
```bash
python -m router.main
```
*(Cache-aware is the default, so no environment variable needed)*

**Wait 5-10 seconds** for workers to register with the router.

**Terminal 3 - Collect Results:**
```bash
python scripts/collect_strategy_results.py
```

When prompted:
- Strategy: `cache_aware` (or press Enter if auto-detected)
- Number of requests: `50` (or press Enter for default)

**This will create:** `results_cache_aware.json`

**Stop the router** (Ctrl+C in Terminal 2)

---

### Step 3: Test Round-Robin Strategy

**Terminal 2 - Start Router (Round-Robin):**
```bash
$env:ROUTING_STRATEGY="round_robin"
python -m router.main
```

**Wait 5-10 seconds** for workers to register.

**Terminal 3 - Collect Results:**
```bash
python scripts/collect_strategy_results.py
```

When prompted:
- Strategy: `round_robin` (or press Enter if auto-detected)
- Number of requests: `50` (or press Enter for default)

**This will create:** `results_round_robin.json`

**Stop the router** (Ctrl+C in Terminal 2)

---

### Step 4: Test Least-Loaded Strategy

**Terminal 2 - Start Router (Least-Loaded):**
```bash
$env:ROUTING_STRATEGY="least_loaded"
python -m router.main
```

**Wait 5-10 seconds** for workers to register.

**Terminal 3 - Collect Results:**
```bash
python scripts/collect_strategy_results.py
```

When prompted:
- Strategy: `least_loaded` (or press Enter if auto-detected)
- Number of requests: `50` (or press Enter for default)

**This will create:** `results_least_loaded.json`

**Stop the router** (Ctrl+C in Terminal 2)

---

### Step 5: Generate Comparison

**Terminal 3 - Generate Comparison:**
```bash
python scripts/generate_comparison.py
```

**This will:**
- ✅ Print a comparison table to console
- ✅ Generate `strategy_comparison.png` (graph)
- ✅ Save `strategy_comparison_summary.json` (combined results)

---

## Expected Output Files

After completing all steps, you should have:

1. `results_cache_aware.json` - Cache-aware strategy results
2. `results_round_robin.json` - Round-robin strategy results
3. `results_least_loaded.json` - Least-loaded strategy results
4. `strategy_comparison.png` - Visual comparison graph
5. `strategy_comparison_summary.json` - Combined results

---

## Quick Reference

### Terminal Setup

- **Terminal 1**: Workers (keep running)
- **Terminal 2**: Router (restart for each strategy)
- **Terminal 3**: Collection script (run after each router start)

### Commands Summary

```bash
# 1. Start workers (once)
python scripts/start_multiple_workers.py

# 2. For each strategy:
#    a. Start router with strategy
python -m router.main  # or with ROUTING_STRATEGY env var
#    b. Collect results
python scripts/collect_strategy_results.py
#    c. Stop router (Ctrl+C)

# 3. Generate comparison (after all strategies)
python scripts/generate_comparison.py
```

---

## Troubleshooting

### Workers not registering?
- Wait 5-10 seconds after starting router
- Check router logs for heartbeat messages
- Verify workers are still running

### No results file created?
- Check that router is running when you run collection script
- Verify workers are registered (check router logs)
- Make sure you're in the project root directory

### Comparison script shows "No result files found"?
- Make sure you've collected results for at least one strategy
- Check that `results_*.json` files exist in the project root
- Verify file names match: `results_cache_aware.json`, etc.

---

## Tips

1. **Keep workers running** - No need to restart them between strategies
2. **Wait for registration** - Give workers 5-10 seconds to register with router
3. **Use same number of requests** - For fair comparison, use the same number (e.g., 50) for all strategies
4. **Check router logs** - They show which strategy is active and routing decisions

---

## What the Results Show

- **Hit Rate**: Percentage of requests that found cached blocks (cache-aware only)
- **Avg Latency**: Average routing latency in milliseconds
- **p95 Latency**: 95th percentile latency
- **Worker Distribution**: How requests were distributed across workers
- **Match Length**: Average prefix match length (cache-aware only)

---

Good luck with your testing! 🚀

