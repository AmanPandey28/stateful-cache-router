# Testing New Features - What Was Added

## 🔧 Code Changes That Need Testing

### 1. Router Routing Strategies (HIGH PRIORITY) ⚠️

**File**: `router/main.py`

**What was added**:
- `ROUTING_STRATEGY` environment variable support
- `route_round_robin()` function (lines 49-58)
- Round-robin routing logic (lines 74-77)
- Least-loaded routing logic (lines 79-82)
- Thread-safe round-robin state (lines 27-29)

**What to test**:
1. ✅ **Default (cache_aware)** - Should work as before
2. ⚠️ **Round-robin** - Needs testing
3. ⚠️ **Least-loaded** - Needs testing

**How to test**:
```bash
# Test 1: Default cache-aware (should work)
python -m router.main
# In another terminal, send requests and verify cache-aware routing

# Test 2: Round-robin
$env:ROUTING_STRATEGY="round_robin"
python -m router.main
# Send requests - should cycle through workers evenly

# Test 3: Least-loaded
$env:ROUTING_STRATEGY="least_loaded"
python -m router.main
# Send requests - should route to least loaded worker
```

**Expected behavior**:
- Round-robin: Requests should cycle through workers (worker-1, worker-2, worker-3, worker-1, ...)
- Least-loaded: Requests should go to worker with lowest load
- Cache-aware: Should use longest prefix match (default, already working)

---

### 2. Experiment Scripts (MEDIUM PRIORITY)

**Files created**:
- `scripts/experiment_baselines.py` - Baseline experiment framework
- `scripts/experiment_prefix_lengths.py` - Prefix length testing
- `scripts/run_comparison_experiment.py` - Complete comparison tool

**What to test**:
1. ⚠️ **experiment_baselines.py** - Can run but needs router with different strategies
2. ⚠️ **experiment_prefix_lengths.py** - Tests prefix length concept
3. ⚠️ **run_comparison_experiment.py** - Main comparison tool

**How to test**:
```bash
# Make sure router and workers are running first
python -m router.main
python scripts/start_multiple_workers.py

# Then run experiments
python scripts/run_comparison_experiment.py
```

**Expected behavior**:
- Scripts should send requests and collect metrics
- Should save results to JSON files
- Should display comparison tables

---

## 📋 Testing Checklist

### Quick Test (5 minutes)
- [ ] **Test 1**: Default cache-aware routing still works
  ```bash
  python -m router.main
  # Send a few requests, verify cache hits/misses work
  ```

### Round-Robin Test (5 minutes)
- [ ] **Test 2**: Round-robin routing cycles through workers
  ```bash
  $env:ROUTING_STRATEGY="round_robin"
  python -m router.main
  # Send 10 requests, check logs - should see different workers
  ```

### Least-Loaded Test (5 minutes)
- [ ] **Test 3**: Least-loaded routes to lowest load
  ```bash
  $env:ROUTING_STRATEGY="least_loaded"
  python -m router.main
  # Send requests, check logs - should route to least loaded
  ```

### Comparison Experiment (10 minutes)
- [ ] **Test 4**: Run comparison experiment
  ```bash
  # Terminal 1: Router with cache_aware
  python -m router.main
  
  # Terminal 2: Workers
  python scripts/start_multiple_workers.py
  
  # Terminal 3: Run experiment
  python scripts/run_comparison_experiment.py
  ```

---

## 🐛 Potential Issues to Watch For

### 1. Round-Robin
- **Issue**: May not cycle correctly if workers disconnect/reconnect
- **Check**: Worker list should update when workers register
- **Fix**: `route_round_robin()` gets fresh worker list each time

### 2. Least-Loaded
- **Issue**: Load may not be accurate if workers haven't sent heartbeats
- **Check**: Workers should send heartbeats regularly
- **Fix**: Should fall back to first available worker if no load data

### 3. Environment Variable
- **Issue**: Windows PowerShell syntax different from bash
- **Check**: Use `$env:ROUTING_STRATEGY="value"` on Windows
- **Fix**: Or set in Python before starting router

---

## ✅ What's Already Working (No Testing Needed)

These were already implemented and working:
- ✅ Block-based caching
- ✅ Prefix tree routing (cache-aware)
- ✅ Reference counting
- ✅ Priority queue eviction
- ✅ Latency simulation
- ✅ Metrics collection
- ✅ Visualizations

---

## 🚀 Quick Test Script

I can create a simple test script that verifies all three routing strategies work. Would you like me to create that?

