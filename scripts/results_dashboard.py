"""
Comprehensive Results Dashboard
Displays real-time and historical metrics for the block-based cache router system.
"""
import asyncio
import aiohttp
import time
import json
from datetime import datetime
from collections import defaultdict, deque
from typing import Dict, List
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

ROUTER_URL = "http://localhost:8000"


class Dashboard:
    """Real-time dashboard for system metrics."""
    
    def __init__(self):
        self.metrics_history = deque(maxlen=100)  # Keep last 100 data points
        self.requests = []
        self.workers = {}
        self.start_time = time.time()
    
    async def collect_metrics(self):
        """Collect metrics from router and workers."""
        async with aiohttp.ClientSession() as session:
            # Send a test request to get current state
            try:
                async with session.post(
                    f"{ROUTER_URL}/v1/completions",
                    json={"prompt": "Test request for metrics", "max_tokens": 10},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "timestamp": time.time(),
                            "cache_status": data.get("cache_status", "UNKNOWN"),
                            "match_length": data.get("match_length", 0),
                            "blocks": len(data.get("block_hashes", [])),
                            "worker": data.get("assigned_worker", "UNKNOWN"),
                        }
            except:
                pass
        return None
    
    def display_header(self):
        """Display dashboard header."""
        print("\n" + "=" * 100)
        print(" " * 30 + "BLOCK-BASED CACHE ROUTER - RESULTS DASHBOARD")
        print("=" * 100)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Uptime: {time.time() - self.start_time:.1f} seconds")
        print("=" * 100)
    
    def display_cache_stats(self):
        """Display cache statistics."""
        if not self.requests:
            print("\n📊 Cache Statistics: No data collected yet")
            return
        
        hits = sum(1 for r in self.requests if r.get("cache_status") == "HIT")
        misses = sum(1 for r in self.requests if r.get("cache_status") == "MISS")
        total = len(self.requests)
        
        hit_rate = (hits / total * 100) if total > 0 else 0
        avg_match = sum(r.get("match_length", 0) for r in self.requests) / total if total > 0 else 0
        avg_blocks = sum(r.get("blocks", 0) for r in self.requests) / total if total > 0 else 0
        
        print("\n💾 Cache Statistics:")
        print(f"   Total Requests:     {total}")
        print(f"   Cache Hits:         {hits} ({hit_rate:.1f}%)")
        print(f"   Cache Misses:       {misses} ({100-hit_rate:.1f}%)")
        print(f"   Avg Match Length:   {avg_match:.1f} blocks")
        print(f"   Avg Blocks/Request: {avg_blocks:.1f} blocks")
    
    def display_latency_stats(self):
        """Display latency statistics."""
        latencies = [r["latency_ms"] for r in self.requests if "latency_ms" in r]
        
        if not latencies:
            print("\n⏱️  Latency Statistics: No data collected yet")
            return
        
        latencies.sort()
        print("\n⏱️  Latency Statistics:")
        print(f"   Average:  {sum(latencies)/len(latencies):.2f} ms")
        print(f"   Median:   {latencies[len(latencies)//2]:.2f} ms")
        print(f"   Min:      {min(latencies):.2f} ms")
        print(f"   Max:      {max(latencies):.2f} ms")
        if len(latencies) > 10:
            print(f"   p95:      {latencies[int(len(latencies)*0.95)]:.2f} ms")
            print(f"   p99:      {latencies[int(len(latencies)*0.99)]:.2f} ms")
    
    def display_recent_activity(self):
        """Display recent request activity."""
        if not self.requests:
            print("\n📋 Recent Activity: No requests yet")
            return
        
        print("\n📋 Recent Requests (last 10):")
        print("   Status | Match | Blocks | Latency  | Worker")
        print("   " + "-" * 60)
        
        for req in self.requests[-10:]:
            status = req.get("cache_status", "UNKNOWN")
            icon = "✅ HIT " if status == "HIT" else "❌ MISS"
            match = req.get("match_length", 0)
            blocks = req.get("blocks", 0)
            latency = req.get("latency_ms", 0)
            worker = req.get("worker", "UNKNOWN")[:15]
            
            print(f"   {icon} | {match:5d} | {blocks:6d} | {latency:7.2f} | {worker}")
    
    async def get_all_workers(self):
        """Get list of all registered workers from router."""
        # Note: Router doesn't expose this endpoint yet, but we can infer from requests
        # In a real system, router would have /internal/workers endpoint
        return list(self.workers.keys())
    
    def display_worker_stats(self):
        """Display worker statistics."""
        if not self.workers:
            print("\n👷 Worker Statistics: No worker data")
            print("   💡 Tip: Start multiple workers to see load balancing")
            return
        
        print(f"\n👷 Worker Statistics ({len(self.workers)} worker(s)):")
        if len(self.workers) == 1:
            print("   ⚠️  Only one worker detected. Start multiple workers to test load balancing.")
            print("   💡 Run: python scripts/start_multiple_workers.py")
        
        for worker_id, stats in self.workers.items():
            requests = stats.get('requests', 0)
            total_requests = len(self.requests)
            percentage = (requests / total_requests * 100) if total_requests > 0 else 0
            print(f"   {worker_id}:")
            print(f"      Requests: {requests} ({percentage:.1f}% of total)")
            print(f"      Avg Latency: {stats.get('avg_latency', 0):.2f} ms")
            print(f"      Cache Hits: {sum(1 for r in self.requests if r.get('worker') == worker_id and r.get('cache_status') == 'HIT')}")
            print(f"      Cache Misses: {sum(1 for r in self.requests if r.get('worker') == worker_id and r.get('cache_status') == 'MISS')}")
    
    def display_summary(self):
        """Display full dashboard."""
        self.display_header()
        self.display_cache_stats()
        self.display_latency_stats()
        self.display_recent_activity()
        self.display_worker_stats()
        print("\n" + "=" * 100)
    
    async def run_continuous(self, interval: float = 5.0):
        """Run continuous monitoring."""
        print("Starting continuous monitoring (press Ctrl+C to stop)...")
        
        test_prompts = [
            "The quick brown fox jumps over the lazy dog. " * 2,
            "Once upon a time in a galaxy far far away. " * 2,
            "To be or not to be, that is the question. " * 2,
        ]
        
        import random
        request_count = 0
        export_done = False
        
        try:
            while True:
                # Send a test request
                prompt = random.choice(test_prompts)
                async with aiohttp.ClientSession() as session:
                    start = time.time()
                    try:
                        async with session.post(
                            f"{ROUTER_URL}/v1/completions",
                            json={"prompt": prompt, "max_tokens": 50},
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                latency = (time.time() - start) * 1000
                                
                                request = {
                                    "timestamp": time.time(),
                                    "cache_status": data.get("cache_status", "UNKNOWN"),
                                    "match_length": data.get("match_length", 0),
                                    "blocks": len(data.get("block_hashes", [])),
                                    "worker": data.get("assigned_worker", "UNKNOWN"),
                                    "latency_ms": latency,
                                }
                                
                                self.requests.append(request)
                                request_count += 1
                                
                                # Update worker stats
                                worker_id = request["worker"]
                                if worker_id not in self.workers:
                                    self.workers[worker_id] = {"requests": 0, "latencies": []}
                                self.workers[worker_id]["requests"] += 1
                                self.workers[worker_id]["latencies"].append(latency)
                                self.workers[worker_id]["avg_latency"] = sum(
                                    self.workers[worker_id]["latencies"]
                                ) / len(self.workers[worker_id]["latencies"])
                    except Exception as e:
                        pass
                
                # Display dashboard every N requests or on interval
                if request_count % 3 == 0:
                    import os
                    os.system('cls' if os.name == 'nt' else 'clear')  # Clear screen
                    self.display_summary()
                    print(f"\n🔄 Auto-refreshing every {interval}s... (Requests: {request_count})")
                
                await asyncio.sleep(interval)
        
        except (KeyboardInterrupt, asyncio.CancelledError):
            if not export_done:
                print("\n\nStopping monitoring...")
                self.display_summary()
                
                # Export results
                try:
                    filename = self.export_results()
                    print(f"\n💾 Results saved to: {filename}")
                    print(f"   Location: {os.path.abspath(filename)}")
                    export_done = True
                except Exception as e:
                    print(f"\n⚠️  Error exporting results: {e}")
            # Don't re-raise, allow clean exit
        finally:
            # Ensure export happens even if exception occurs
            if not export_done and self.requests:
                try:
                    filename = self.export_results()
                    print(f"\n💾 Results saved to: {filename}")
                except:
                    pass
    
    def export_results(self, filename: str = "dashboard_results.json"):
        """Export results to JSON."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": time.time() - self.start_time,
            "total_requests": len(self.requests),
            "cache_stats": {
                "hits": sum(1 for r in self.requests if r.get("cache_status") == "HIT"),
                "misses": sum(1 for r in self.requests if r.get("cache_status") == "MISS"),
                "hit_rate_percent": (sum(1 for r in self.requests if r.get("cache_status") == "HIT") / len(self.requests) * 100) if self.requests else 0,
            },
            "latency_stats": {
                "avg": sum(r["latency_ms"] for r in self.requests if "latency_ms" in r) / len(self.requests) if self.requests else 0,
                "min": min((r["latency_ms"] for r in self.requests if "latency_ms" in r), default=0),
                "max": max((r["latency_ms"] for r in self.requests if "latency_ms" in r), default=0),
            },
            "workers": self.workers,
            "recent_requests": self.requests[-20:],
            "all_requests": self.requests,  # Include all requests for analysis
        }
        
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        
        print(f"\n💾 Results exported to {filename}")
        return filename


async def main():
    """Main entry point."""
    dashboard = Dashboard()
    
    try:
        print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║              Block-Based Cache Router - Results Dashboard                    ║
╚══════════════════════════════════════════════════════════════════════════════╝

Choose mode:
  [1] Continuous monitoring (auto-refresh) - Exports on Ctrl+C
  [2] Single snapshot - Collects 5 requests and exports immediately
  [3] Interactive mode - Exports on quit

💡 Results are saved to: dashboard_results.json (in project root)

Enter choice (1-3): """, end="")
        
        choice = input().strip()
        
        if choice == "1":
            await dashboard.run_continuous(interval=5.0)
        elif choice == "2":
            # Send a few requests then display
            print("\nCollecting data...")
            for _ in range(5):
                await dashboard.collect_metrics()
                await asyncio.sleep(1)
            dashboard.display_summary()
            # Export results
            filename = dashboard.export_results()
            print(f"\n💾 Results saved to: {filename}")
            print(f"   Location: {os.path.abspath(filename)}")
        elif choice == "3":
            # Interactive mode
            while True:
                try:
                    cmd = input("\n> ").strip().lower()
                    if cmd == "q" or cmd == "quit":
                        break
                    elif cmd == "d" or cmd == "display":
                        dashboard.display_summary()
                    elif cmd == "e" or cmd == "export":
                        dashboard.export_results()
                    elif cmd.startswith("req "):
                        prompt = cmd[4:]
                        # Send request
                        async with aiohttp.ClientSession() as session:
                            start = time.time()
                            async with session.post(
                                f"{ROUTER_URL}/v1/completions",
                                json={"prompt": prompt, "max_tokens": 50},
                            ) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    latency = (time.time() - start) * 1000
                                    request = {
                                        "cache_status": data.get("cache_status"),
                                        "match_length": data.get("match_length", 0),
                                        "blocks": len(data.get("block_hashes", [])),
                                        "worker": data.get("assigned_worker"),
                                        "latency_ms": latency,
                                    }
                                    dashboard.requests.append(request)
                                    print(f"✅ {request['cache_status']} | "
                                          f"Match: {request['match_length']} blocks | "
                                          f"Latency: {latency:.2f}ms")
                    else:
                        print("Commands: [d]isplay, [e]xport, req <prompt>, [q]uit")
                except KeyboardInterrupt:
                    break
            dashboard.display_summary()
            dashboard.export_results()
        else:
            print("Invalid choice")
    except (KeyboardInterrupt, asyncio.CancelledError):
        # Ensure export happens even if interrupted
        if dashboard.requests:
            print("\n\nExporting results before exit...")
            try:
                filename = dashboard.export_results()
                print(f"💾 Results saved to: {filename}")
            except Exception as e:
                print(f"⚠️  Error exporting: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExiting...")

