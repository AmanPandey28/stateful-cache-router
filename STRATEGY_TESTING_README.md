# Routing Strategy Comparison Testing Guide

This guide explains how to test and compare the three routing strategies: Cache-Aware, Round-Robin, and Least-Loaded.

## Prerequisites

- Python 3.7+ installed
- Required packages: `pip install -r requirements.txt`
- Router and worker code in the project directory

## Overview

You'll need **3 terminal windows**:
- **Terminal 1**: Workers (keep running for all tests)
- **Terminal 2**: Router (restart for each strategy)
- **Terminal 3**: Collection script (run after each router start)

## Step-by-Step Instructions

### Step 1: Start Workers (Do This Once)

**Terminal 1 - Start Workers:**
```bash
python scripts/start_multiple_workers.py
```

**Keep this terminal running!** Workers will stay active for all strategy tests.

You should see workers starting up. Wait until you see 3 workers running.

---

### Step 2: Test Cache-Aware Strategy (Default)

**Terminal 2 - Start Router:**
```bash
python -m router.main
```

**Wait 10-15 seconds** for workers to register. Watch the router logs - you should see:
```
💓 Heartbeat from worker-XXXX (load=0)
🔄 SYNC: worker-XXXX reported X active hashes
```

**Terminal 3 - Collect Results:**
```bash
python scripts/collect_strategy_results.py
```

When prompted:
- **Strategy**: Type `cache_aware` (or press Enter if auto-detected)
- **Number of requests**: Type `50` (or press Enter for default)

The script will:
- Run a warmup phase (10 requests)
- Collect metrics (50 requests)
- Save results to `results_cache_aware.json`
- Display a summary

**Stop the router** (Ctrl+C in Terminal 2)

**Wait 5 seconds** before starting the next router.

---

### Step 3: Test Round-Robin Strategy

**Terminal 2 - Start Router (Round-Robin):**
```bash
$env:ROUTING_STRATEGY="round_robin"
python -m router.main
```

**Wait 10-15 seconds** for workers to reconnect and register. Check router logs for heartbeats.

**Terminal 3 - Collect Results:**
```bash
python scripts/collect_strategy_results.py
```

When prompted:
- **Strategy**: Type `round_robin`
- **Number of requests**: Type `50` (or press Enter for default)

This creates: `results_round_robin.json`

**Stop the router** (Ctrl+C in Terminal 2)

**Wait 5 seconds** before starting the next router.

---

### Step 4: Test Least-Loaded Strategy

**Terminal 2 - Start Router (Least-Loaded):**
```bash
$env:ROUTING_STRATEGY="least_loaded"
python -m router.main
```

**Wait 10-15 seconds** for workers to reconnect and register.

**Terminal 3 - Collect Results:**
```bash
python scripts/collect_strategy_results.py
```

When prompted:
- **Strategy**: Type `least_loaded`
- **Number of requests**: Type `50` (or press Enter for default)

This creates: `results_least_loaded.json`

**Stop the router** (Ctrl+C in Terminal 2)

---

### Step 5: Generate Comparison

**Terminal 3 - Generate Comparison:**
```bash
python scripts/generate_comparison.py
```

This will:
- ✅ Load all result files (`results_*.json`)
- ✅ Print a comparison table to console
- ✅ Generate `strategy_comparison.png` (visual graph)
- ✅ Save `strategy_comparison_summary.json` (combined results)

---

## Expected Output Files

After completing all steps, you should have:

1. `results_cache_aware.json` - Cache-aware strategy results
2. `results_round_robin.json` - Round-robin strategy results
3. `results_least_loaded.json` - Least-loaded strategy results
4. `strategy_comparison.png` - Visual comparison graph (4 charts)
5. `strategy_comparison_summary.json` - Combined results

---

## Quick Reference

### Terminal Setup

```
Terminal 1: Workers (keep running)
Terminal 2: Router (restart for each strategy)
Terminal 3: Collection script (run after each router)
```

### Commands Summary

```bash
# 1. Start workers (once, keep running)
python scripts/start_multiple_workers.py

# 2. For each strategy:
#    a. Start router
python -m router.main  # or with ROUTING_STRATEGY env var
#    b. Wait 10-15 seconds
#    c. Collect results
python scripts/collect_strategy_results.py
#    d. Stop router (Ctrl+C)
#    e. Wait 5 seconds

# 3. Generate comparison (after all strategies)
python scripts/generate_comparison.py
```

---

## Troubleshooting

### Workers Not Connecting?

**Symptoms:**
- Connection errors in worker logs
- No heartbeats in router logs
- Router shows "No workers available"

**Solution:**
1. Make sure router is running **before** starting workers
2. Wait 10-15 seconds after starting router
3. Check router logs for heartbeats
4. If still not working, restart workers

### 0% Cache Hit Rate?

**Symptoms:**
- All strategies show 0% hit rate
- Workers are connected (heartbeats visible)

**Possible Causes:**
1. **Timing**: Test ran before cache was populated
   - **Fix**: Wait longer after warmup (15-20 seconds)
   
2. **Prompt Mismatch**: Test prompts don't match cached blocks
   - **Fix**: This is expected for round-robin and least-loaded (they don't use cache)
   - For cache-aware: Make sure warmup and test use similar prompts

3. **Cache Cleared**: Workers cleared cache between tests
   - **Fix**: This is normal when restarting router

**Note**: 0% hit rate is **expected** for round-robin and least-loaded strategies. Only cache-aware should show hits.

### Router Won't Start?

**Symptoms:**
- Port 8000 already in use
- "Address already in use" error

**Solution:**
```bash
# Check what's using port 8000
netstat -ano | findstr :8000

# Kill the process (replace <PID> with actual process ID)
taskkill /PID <PID> /F

# Then start router again
python -m router.main
```

### Workers Disconnect When Stopping Router?

**This is normal!** When you stop the router:
- Workers lose connection (expected)
- You'll see connection errors in worker logs (normal)
- Workers will automatically reconnect when you start a new router
- Wait 10-15 seconds after starting new router for reconnection

### Collection Script Can't Find Router?

**Symptoms:**
- "Cannot connect to router" error
- "Router is not responding"

**Solution:**
1. Make sure router is running
2. Check router is on `http://localhost:8000`
3. Wait a few seconds after starting router
4. Test manually: `curl http://localhost:8000/docs`

---

## What to Look For

### Good Signs ✅

- Router logs show heartbeats every second
- Router logs show sync messages every 5 seconds
- No connection errors (after initial connection)
- Cache-aware shows > 0% hit rate (after warmup)
- Results files are created successfully

### Bad Signs ❌

- Persistent connection errors
- No heartbeats in router logs
- Router not responding
- All strategies show 0% hit rate (for cache-aware, this might indicate timing issue)

---

## Understanding Results

### Cache Hit Rate
- **Cache-Aware**: Should be > 0% (typically 30-60% with RAG-like workloads)
- **Round-Robin**: Should be 0% (doesn't use cache)
- **Least-Loaded**: Should be 0% (doesn't use cache)

### Latency
- **Cache-Aware**: Lower latency for HITs vs MISSes
- **Round-Robin**: Consistent latency (no cache benefits)
- **Least-Loaded**: Should route to least loaded worker

### Worker Distribution
- **Cache-Aware**: Uneven (routes to workers with cache)
- **Round-Robin**: Even distribution (cycles through workers)
- **Least-Loaded**: Based on load (routes to least loaded)

---

## Tips

1. **Keep workers running** - No need to restart them between strategies
2. **Wait for registration** - Give workers 10-15 seconds to register with router
3. **Watch router logs** - They show which strategy is active and routing decisions
4. **Use same number of requests** - For fair comparison, use 50 requests for all strategies
5. **Check results files** - Verify `results_*.json` files are created after each test

---

## Example Workflow

```bash
# Terminal 1: Start workers (keep running)
python scripts/start_multiple_workers.py

# Terminal 2: Test Cache-Aware
python -m router.main
# Wait 15 seconds, then in Terminal 3:
python scripts/collect_strategy_results.py  # Enter: cache_aware, 50
# Stop router (Ctrl+C), wait 5 seconds

# Terminal 2: Test Round-Robin
$env:ROUTING_STRATEGY="round_robin"
python -m router.main
# Wait 15 seconds, then in Terminal 3:
python scripts/collect_strategy_results.py  # Enter: round_robin, 50
# Stop router (Ctrl+C), wait 5 seconds

# Terminal 2: Test Least-Loaded
$env:ROUTING_STRATEGY="least_loaded"
python -m router.main
# Wait 15 seconds, then in Terminal 3:
python scripts/collect_strategy_results.py  # Enter: least_loaded, 50
# Stop router (Ctrl+C)

# Terminal 3: Generate comparison
python scripts/generate_comparison.py
```

---

## Need Help?

If you encounter issues:
1. Check the troubleshooting section above
2. Verify router and workers are running
3. Check router logs for heartbeats and sync messages
4. Make sure you're waiting long enough for workers to register
5. Verify result files are being created

---

**Good luck with your testing!** 🚀

