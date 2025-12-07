"""
Real-time Metrics Display for Block-Based Cache Router
Displays current system state, performance metrics, and cache statistics.
"""
import asyncio
import aiohttp
import time
import json
from collections import defaultdict
from typing import Dict, List
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

ROUTER_URL = "http://localhost:8000"


class MetricsCollector:
    """Collects and displays system metrics."""
    
    def __init__(self):
        self.request_history: List[Dict] = []
        self.worker_stats: Dict[str, Dict] = {}
        self.cache_stats = {
            "total_blocks": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "evictions": 0,
        }
        self.start_time = time.time()
    
    async def fetch_router_state(self) -> Dict:
        """Fetch current router state (simulated - would need router API)."""
        # In a real system, router would expose metrics endpoint
        return {}
    
    async def send_test_request(self, prompt: str) -> Dict:
        """Send a test request and collect metrics."""
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
                        
                        result = {
                            "timestamp": time.time(),
                            "latency_ms": latency,
                            "cache_status": data.get("cache_status", "UNKNOWN"),
                            "match_length": data.get("match_length", 0),
                            "worker": data.get("assigned_worker", "UNKNOWN"),
                            "blocks": len(data.get("block_hashes", [])),
                        }
                        
                        # Update stats
                        if result["cache_status"] == "HIT":
                            self.cache_stats["cache_hits"] += 1
                        else:
                            self.cache_stats["cache_misses"] += 1
                        
                        self.request_history.append(result)
                        return result
            except Exception as e:
                return {"error": str(e)}
        return {}
    
    def display_summary(self):
        """Display summary statistics."""
        print("\n" + "=" * 80)
        print("BLOCK-BASED CACHE ROUTER - METRICS SUMMARY")
        print("=" * 80)
        
        # System uptime
        uptime = time.time() - self.start_time
        print(f"\n⏱️  System Uptime: {uptime:.1f} seconds")
        
        # Request statistics
        if self.request_history:
            latencies = [r["latency_ms"] for r in self.request_history if "latency_ms" in r]
            if latencies:
                print(f"\n📊 Request Statistics:")
                print(f"   Total Requests:    {len(self.request_history)}")
                print(f"   Average Latency:   {sum(latencies)/len(latencies):.2f} ms")
                print(f"   Min Latency:       {min(latencies):.2f} ms")
                print(f"   Max Latency:       {max(latencies):.2f} ms")
                if len(latencies) > 1:
                    sorted_lat = sorted(latencies)
                    p50 = sorted_lat[len(sorted_lat)//2]
                    p95 = sorted_lat[int(len(sorted_lat)*0.95)]
                    p99 = sorted_lat[int(len(sorted_lat)*0.99)]
                    print(f"   p50 Latency:       {p50:.2f} ms")
                    print(f"   p95 Latency:       {p95:.2f} ms")
                    print(f"   p99 Latency:       {p99:.2f} ms")
        
        # Cache statistics
        total_requests = self.cache_stats["cache_hits"] + self.cache_stats["cache_misses"]
        if total_requests > 0:
            hit_rate = (self.cache_stats["cache_hits"] / total_requests) * 100
            print(f"\n💾 Cache Statistics:")
            print(f"   Cache Hits:         {self.cache_stats['cache_hits']}")
            print(f"   Cache Misses:      {self.cache_stats['cache_misses']}")
            print(f"   Hit Rate:          {hit_rate:.1f}%")
            print(f"   Evictions:         {self.cache_stats['evictions']}")
        
        # Recent requests
        if self.request_history:
            print(f"\n📋 Recent Requests (last 5):")
            for req in self.request_history[-5:]:
                if "error" not in req:
                    status_icon = "✅" if req.get("cache_status") == "HIT" else "❌"
                    print(f"   {status_icon} {req.get('cache_status', 'UNKNOWN'):4s} | "
                          f"Match: {req.get('match_length', 0):2d} blocks | "
                          f"Latency: {req.get('latency_ms', 0):6.2f} ms | "
                          f"Worker: {req.get('worker', 'UNKNOWN')}")
        
        print("\n" + "=" * 80)
    
    def export_json(self, filename: str = "metrics.json"):
        """Export metrics to JSON file."""
        data = {
            "uptime_seconds": time.time() - self.start_time,
            "request_count": len(self.request_history),
            "cache_stats": self.cache_stats,
            "recent_requests": self.request_history[-10:],  # Last 10
        }
        
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        
        print(f"\n💾 Metrics exported to {filename}")


async def interactive_metrics():
    """Interactive metrics collection and display."""
    collector = MetricsCollector()
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║          Block-Based Cache Router - Real-Time Metrics Display                ║
╚══════════════════════════════════════════════════════════════════════════════╝

Commands:
  [s]end - Send a test request
  [d]isplay - Show current metrics
  [e]xport - Export metrics to JSON
  [q]uit - Exit

Press Enter to start...
    """)
    input()
    
    test_prompts = [
        "The quick brown fox jumps over the lazy dog.",
        "Once upon a time in a galaxy far far away.",
        "To be or not to be, that is the question.",
    ]
    
    while True:
        try:
            cmd = input("\n> ").strip().lower()
            
            if cmd == "q" or cmd == "quit":
                break
            elif cmd == "s" or cmd == "send":
                prompt = input("Enter prompt (or press Enter for random): ").strip()
                if not prompt:
                    import random
                    prompt = random.choice(test_prompts)
                
                print(f"\n📤 Sending request: '{prompt[:50]}...'")
                result = await collector.send_test_request(prompt)
                if "error" not in result:
                    status = result.get('cache_status', 'UNKNOWN')
                    match = result.get('match_length', 0)
                    blocks = result.get('blocks', 0)
                    
                    if status == "HIT":
                        print(f"✅ Cache HIT: {match} blocks matched (out of {blocks} total blocks)")
                        print(f"   💡 This prompt found cached blocks! Latency should be lower.")
                    else:
                        print(f"❌ Cache MISS: 0 blocks matched (out of {blocks} total blocks)")
                        print(f"   💡 Tip: Send the SAME prompt again to see a HIT!")
                        print(f"   💡 Tip: Use longer prompts (20+ words) to create blocks")
                else:
                    print(f"❌ Error: {result['error']}")
            
            elif cmd == "d" or cmd == "display":
                collector.display_summary()
                print("\n💡 Cache Status Guide:")
                print("   ✅ HIT = Found cached blocks (faster, lower latency)")
                print("   ❌ MISS = No cached blocks (slower, higher latency)")
                print("   Match Length = How many blocks matched (0 = MISS, >0 = HIT)")
                print("\n💡 To see cache hits:")
                print("   1. Send a LONG prompt (20+ words) to create blocks")
                print("   2. Send the SAME prompt again - should show HIT")
            
            elif cmd == "e" or cmd == "export":
                collector.export_json()
            
            elif cmd == "":
                # Auto-refresh
                collector.display_summary()
            
            else:
                print("Unknown command. Use [s]end, [d]isplay, [e]xport, or [q]uit")
        
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
    
    # Final summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    collector.display_summary()
    collector.export_json()


if __name__ == "__main__":
    asyncio.run(interactive_metrics())

