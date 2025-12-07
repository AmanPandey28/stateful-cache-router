# Least-Loaded Routing Issue Analysis

## The Problem

You're absolutely right! If least-loaded routing is working correctly, it should **distribute requests across workers** based on their load, not send everything to one worker.

## Why This Happened

Looking at the code, there are two issues:

### Issue 1: Load Updates Are Delayed

1. **Workers send heartbeats every 1 second** (`scripts/mock_worker.py:454`)
2. **Requests come in faster** (every 0.1-0.2 seconds in the test)
3. **Router doesn't know load increased** until next heartbeat

### Issue 2: Tie-Breaking Problem

When all workers have the same load (e.g., all start at 0):
- `min()` returns the **first worker** in the list
- Python's `min()` is stable - on ties, it returns the first occurrence
- So if all workers have `load=0`, it always picks the first one

### What Actually Happened

1. All workers start with `load=0` (or not initialized)
2. First request → router picks first worker (all have load=0)
3. Worker gets request, load increases
4. **But router doesn't know yet** (heartbeat is 1 second away)
5. Next request → router still sees all workers at load=0 → picks first again
6. This repeats for all 50 requests

## The Fix

We need to:
1. **Update load immediately** when routing (speculative load increase)
2. **Better tie-breaking** (round-robin on ties)
3. **Or faster heartbeats** (but this adds overhead)

Let me fix this:

