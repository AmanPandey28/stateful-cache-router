# Running Multiple Workers

To see load balancing and multi-worker behavior, you need to run multiple worker instances.

## Quick Start

### Option 1: Use the Helper Script (Recommended)

```bash
# Start 3 workers automatically
python scripts/start_multiple_workers.py

# Or specify number of workers
python scripts/start_multiple_workers.py -n 5
```

This will start multiple workers in separate console windows (Windows) or processes (Linux/Mac).

### Option 2: Manual Start (Multiple Terminals)

**Terminal 1: Router**
```bash
python -m router.main
```

**Terminal 2: Worker 1**
```bash
python scripts/mock_worker.py
```

**Terminal 3: Worker 2**
```bash
python scripts/mock_worker.py
```

**Terminal 4: Worker 3**
```bash
python scripts/mock_worker.py
```

**Terminal 5: Dashboard**
```bash
python scripts/results_dashboard.py
# Choose option 1 for continuous monitoring
```

## What You'll See

With multiple workers, the dashboard will show:

```
👷 Worker Statistics (3 worker(s)):
   worker-1234:
      Requests: 8 (33.3% of total)
      Avg Latency: 245.32 ms
      Cache Hits: 5
      Cache Misses: 3
   worker-5678:
      Requests: 9 (37.5% of total)
      Avg Latency: 251.67 ms
      Cache Hits: 6
      Cache Misses: 3
   worker-9012:
      Requests: 7 (29.2% of total)
      Avg Latency: 248.91 ms
      Cache Hits: 4
      Cache Misses: 3
```

## Testing Load Balancing

1. **Start router and 3 workers**
2. **Run dashboard** and send requests
3. **Observe**:
   - Requests distributed across workers
   - Load balancing based on cache state
   - Cache-aware routing (HITs go to worker with cache)

## Expected Behavior

- **Cache MISS**: Router routes to least loaded worker
- **Cache HIT**: Router routes to worker with matching blocks (even if slightly more loaded)
- **Load Distribution**: Requests should be distributed across workers
- **Cache Locality**: Repeated prompts should hit the same worker (sticky routing)

## Troubleshooting

**Only seeing one worker?**
- Make sure multiple worker processes are actually running
- Check router logs for multiple worker heartbeats
- Restart workers if needed

**Workers not balancing?**
- Check that all workers are registered (see router logs)
- Verify workers are sending heartbeats
- Check load values in router logs

