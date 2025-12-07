# Least-Loaded Routing Fix

## Problem Identified

You were absolutely right! The least-loaded strategy was sending all requests to one worker because:

1. **Load updates are delayed**: Workers send heartbeats every 1 second, but requests come faster
2. **Tie-breaking issue**: When all workers have same load (e.g., 0), `min()` always picks the first one
3. **No immediate load tracking**: Router doesn't know a worker got a request until next heartbeat

## Fix Applied

### 1. Round-Robin Tie-Breaking
- When multiple workers have the same minimum load, use round-robin
- Cycles through tied workers instead of always picking the first

### 2. Speculative Load Update
- When routing to a worker, immediately add estimated load (~50ms)
- This prevents all requests going to the same worker
- Actual load will be corrected by the next heartbeat

## Expected Behavior After Fix

**Least-Loaded should now:**
- Distribute requests across workers based on load
- Use round-robin when loads are equal
- Balance load more effectively

## Testing

Re-run the test:
```bash
$env:ROUTING_STRATEGY="least_loaded"
python -m router.main
# In another terminal:
python scripts/test_routing_strategies.py
```

You should now see requests distributed across workers, not all to one worker.

