# Understanding Cache Hits and Misses

## How to See Cache Hits

### The Problem
You're seeing all MISS responses because:
1. **Prompts are too short** - Need 16+ tokens (about 20+ words) to create a block
2. **Different prompts** - Each unique prompt creates different blocks
3. **Need to repeat** - Must send the SAME prompt twice to see a HIT

### Solution: Test Cache Hits

#### Step 1: Send a LONG prompt
```
> s
Enter prompt: The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog.
```
**Result:** ❌ MISS (0 blocks matched) - First time, no cache

#### Step 2: Send the EXACT SAME prompt again
```
> s
Enter prompt: The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog.
```
**Result:** ✅ HIT (1+ blocks matched) - Found cached blocks!

### Understanding the Output

**Cache Status:**
- ✅ **HIT** = Found cached blocks (faster response)
- ❌ **MISS** = No cached blocks (slower response)

**Match Length:**
- `0 blocks` = MISS (nothing cached)
- `1+ blocks` = HIT (found matching blocks)

**Blocks:**
- Total number of blocks in the request
- Each block = 16 tokens

## Where Results Are Saved

### 1. `results_dashboard.py` Results
**File:** `dashboard_results.json`
**Location:** Project root directory
**When saved:** When you press Ctrl+C to stop the dashboard

**Contains:**
- Total requests
- Cache hit/miss counts
- Hit rate percentage
- Latency statistics (avg, min, max)
- Worker statistics
- All request history

**To view:**
```bash
# After stopping dashboard, check:
cat dashboard_results.json
# or open in any text editor
```

### 2. `display_metrics.py` Results
**File:** `metrics.json`
**Location:** Project root directory
**When saved:** When you type `e` (export) command

**Contains:**
- Request count
- Cache statistics
- Recent requests (last 10)

## Quick Test Guide

### Test Cache Hits in display_metrics.py

1. **Start system:**
   ```bash
   # Terminal 1: Router
   python -m router.main
   
   # Terminal 2: Worker
   python scripts/mock_worker.py
   ```

2. **Run display_metrics:**
   ```bash
   # Terminal 3
   python scripts/display_metrics.py
   ```

3. **Send long prompt:**
   ```
   > s
   Enter prompt: The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog.
   ```
   Result: ❌ MISS (first time)

4. **Send SAME prompt again:**
   ```
   > s
   Enter prompt: The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog.
   ```
   Result: ✅ HIT (found cache!)

5. **View metrics:**
   ```
   > d
   ```
   Should show cache hits > 0

6. **Export:**
   ```
   > e
   ```
   Saves to `metrics.json`

## Using results_dashboard.py (Automatic)

This tool automatically sends requests and collects data:

```bash
python scripts/results_dashboard.py
# Choose option 1 for continuous monitoring
```

**Results saved when you press Ctrl+C:**
- File: `dashboard_results.json`
- Location: Project root
- Contains: Complete metrics and all request data

## Tips

1. **Long prompts** = More blocks = Better caching
2. **Repeat prompts** = See cache hits
3. **Wait 5 seconds** = Let sync complete between requests
4. **Check router logs** = See block sync messages
5. **Multiple workers** = Better load balancing visualization

## Example Session

```
> s
Enter prompt: Once upon a time in a galaxy far far away. Once upon a time in a galaxy far far away.
📤 Sending request: 'Once upon a time in a galaxy far far away. Once upon a time...'
❌ Cache MISS: 0 blocks matched (out of 2 total blocks)
   💡 Tip: Send the SAME prompt again to see a HIT!

> s
Enter prompt: Once upon a time in a galaxy far far away. Once upon a time in a galaxy far far away.
📤 Sending request: 'Once upon a time in a galaxy far far away. Once upon a time...'
✅ Cache HIT: 2 blocks matched (out of 2 total blocks)
   💡 This prompt found cached blocks! Latency should be lower.

> d
💾 Cache Statistics:
   Cache Hits:         1
   Cache Misses:       1
   Hit Rate:          50.0%
```

