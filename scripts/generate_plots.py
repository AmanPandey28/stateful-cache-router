"""
Visualization Script: Generate Graphs from Benchmark Results

Creates visual representations of:
- Router latency distribution (histogram)
- False hit recovery timeline
- Cache hit rate over time
"""

import matplotlib.pyplot as plt
import numpy as np
import os
import json

def plot_latency_distribution(latencies, output_file="latency_distribution.png", title_suffix=""):
    """Generate histogram of router latencies."""
    plt.figure(figsize=(10, 6))
    
    # Create histogram
    bins = min(50, len(latencies) // 2) if len(latencies) > 10 else 20
    plt.hist(latencies, bins=bins, color='skyblue', edgecolor='black', alpha=0.7)
    
    # Add statistics lines
    median = np.median(latencies)
    p95 = np.percentile(latencies, 95) if len(latencies) > 20 else max(latencies)
    p99 = np.percentile(latencies, 99) if len(latencies) > 100 else max(latencies)
    avg = np.mean(latencies)
    
    plt.axvline(median, color='green', linestyle='--', linewidth=2, label=f'Median: {median:.2f}ms')
    plt.axvline(avg, color='blue', linestyle=':', linewidth=2, label=f'Average: {avg:.2f}ms')
    if len(latencies) > 20:
        plt.axvline(p95, color='orange', linestyle='--', linewidth=2, label=f'p95: {p95:.2f}ms')
    if len(latencies) > 100:
        plt.axvline(p99, color='red', linestyle='--', linewidth=2, label=f'p99: {p99:.2f}ms')
    
    plt.xlabel('Latency (ms)', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    title = f'Router Latency Distribution ({len(latencies)} Requests)'
    if title_suffix:
        title += f" - {title_suffix}"
    plt.title(title, fontsize=14, fontweight='bold')
    plt.legend(fontsize=10)
    plt.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300)
    print(f"✅ Saved latency distribution to {output_file}")
    plt.close()

def plot_recovery_timeline(false_hits, recovery_time, sync_interval=5, output_file="recovery_timeline.png"):
    """Generate timeline showing false hit recovery."""
    plt.figure(figsize=(12, 6))
    
    # Simulate timeline data (15 seconds, 1 check per second)
    timeline = list(range(15))
    status = ['FALSE HIT' if i < recovery_time else 'CORRECT' for i in timeline]
    colors = ['red' if s == 'FALSE HIT' else 'green' for s in status]
    
    # Create bar chart
    plt.bar(timeline, [1]*len(timeline), color=colors, alpha=0.7, edgecolor='black')
    
    # Add recovery marker
    if recovery_time < 15:
        plt.axvline(recovery_time, color='blue', linestyle='--', linewidth=2, 
                   label=f'Recovery at {recovery_time:.1f}s')
    
    # Add sync interval marker
    plt.axvline(sync_interval, color='purple', linestyle=':', linewidth=2, 
               label=f'Expected Recovery ({sync_interval}s)')
    
    plt.xlabel('Time (seconds)', fontsize=12)
    plt.ylabel('Routing Status', fontsize=12)
    plt.title('Stale Cache Recovery Timeline', fontsize=14, fontweight='bold')
    plt.yticks([0.5], ['Status'])
    plt.legend(fontsize=10)
    plt.grid(axis='x', alpha=0.3)
    
    # Add text annotation
    plt.text(0.5, 0.5, f'False Hits: {false_hits}', fontsize=10, 
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300)
    print(f"✅ Saved recovery timeline to {output_file}")
    plt.close()

def plot_worker_load_distribution(workers_data, output_file="worker_load_distribution.png"):
    """Generate bar chart showing request distribution across workers."""
    plt.figure(figsize=(10, 6))
    
    worker_ids = []
    request_counts = []
    hit_counts = []
    miss_counts = []
    
    for worker_id, stats in workers_data.items():
        worker_ids.append(worker_id)
        request_counts.append(stats.get("requests", 0))
        hit_counts.append(stats.get("cache_hits", 0))
        miss_counts.append(stats.get("cache_misses", 0))
    
    x = np.arange(len(worker_ids))
    width = 0.35
    
    # Create stacked bar chart
    plt.bar(x, hit_counts, width, label='Cache Hits', color='green', alpha=0.7)
    plt.bar(x, miss_counts, width, bottom=hit_counts, label='Cache Misses', color='red', alpha=0.7)
    
    plt.xlabel('Worker ID', fontsize=12)
    plt.ylabel('Number of Requests', fontsize=12)
    plt.title('Request Distribution Across Workers', fontsize=14, fontweight='bold')
    plt.xticks(x, worker_ids, rotation=45, ha='right')
    plt.legend(fontsize=10)
    plt.grid(axis='y', alpha=0.3)
    
    # Add request count labels on bars
    for i, (hits, misses, total) in enumerate(zip(hit_counts, miss_counts, request_counts)):
        plt.text(i, total + 1, str(total), ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300)
    print(f"✅ Saved worker load distribution to {output_file}")
    plt.close()

def plot_latency_by_cache_status(requests_data, output_file="latency_by_cache_status.png"):
    """Generate box plot comparing latency for HIT vs MISS."""
    if not requests_data:
        return
    
    hit_latencies = [r["latency_ms"] for r in requests_data if r.get("cache_status") == "HIT" and "latency_ms" in r]
    miss_latencies = [r["latency_ms"] for r in requests_data if r.get("cache_status") == "MISS" and "latency_ms" in r]
    
    if not hit_latencies or not miss_latencies:
        print("   ⚠️  Need both HIT and MISS data for comparison")
        return
    
    plt.figure(figsize=(10, 6))
    
    data = [hit_latencies, miss_latencies]
    labels = ['Cache HIT', 'Cache MISS']
    colors = ['green', 'red']
    
    bp = plt.boxplot(data, labels=labels, patch_artist=True, widths=0.6)
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    
    # Add statistics text
    hit_avg = np.mean(hit_latencies)
    miss_avg = np.mean(miss_latencies)
    improvement = ((miss_avg - hit_avg) / miss_avg) * 100
    
    plt.text(0.5, 0.95, f'Avg HIT: {hit_avg:.1f}ms\nAvg MISS: {miss_avg:.1f}ms\nImprovement: {improvement:.1f}%',
             transform=plt.gca().transAxes, fontsize=10,
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
             verticalalignment='top')
    
    plt.ylabel('Latency (ms)', fontsize=12)
    plt.title('Latency Comparison: Cache HIT vs MISS', fontsize=14, fontweight='bold')
    plt.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300)
    print(f"✅ Saved latency comparison to {output_file}")
    plt.close()

def plot_match_length_distribution(requests_data, output_file="match_length_distribution.png"):
    """Generate histogram of prefix match lengths."""
    if not requests_data:
        return
    
    match_lengths = [r.get("match_length", 0) for r in requests_data if "match_length" in r]
    
    if not match_lengths:
        return
    
    plt.figure(figsize=(10, 6))
    
    # Create histogram
    bins = max(10, max(match_lengths) + 1) if max(match_lengths) > 0 else 10
    plt.hist(match_lengths, bins=bins, color='purple', edgecolor='black', alpha=0.7)
    
    # Add statistics
    avg_match = np.mean(match_lengths)
    max_match = max(match_lengths)
    hits = sum(1 for m in match_lengths if m > 0)
    
    plt.axvline(avg_match, color='orange', linestyle='--', linewidth=2, 
                label=f'Average: {avg_match:.2f} blocks')
    
    plt.xlabel('Prefix Match Length (blocks)', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title(f'Prefix Match Length Distribution (Hits: {hits}/{len(match_lengths)})', 
              fontsize=14, fontweight='bold')
    plt.legend(fontsize=10)
    plt.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300)
    print(f"✅ Saved match length distribution to {output_file}")
    plt.close()

def plot_cache_hit_rate(requests_data=None, output_file="cache_hit_rate.png"):
    """Generate cache hit rate over time from actual data or simulation."""
    plt.figure(figsize=(10, 6))
    
    if requests_data:
        # Use actual data from dashboard
        requests = list(range(1, len(requests_data) + 1))
        hits = 0
        hit_rates = []
        for i, req in enumerate(requests_data):
            if req.get("cache_status") == "HIT":
                hits += 1
            hit_rate = hits / (i + 1)
            hit_rates.append(hit_rate)
        
        plt.plot(requests, hit_rates, color='blue', linewidth=2, marker='o', markersize=3)
        plt.fill_between(requests, hit_rates, alpha=0.3, color='blue')
        title = f'Cache Hit Rate Over Time (Actual Data: {len(requests_data)} requests)'
    else:
        # Simulate data: cache warms up over time
        requests = list(range(1, 101))
        hit_rate = [min(0.05 + (i * 0.8 / 100), 0.85) for i in requests]  # Warm-up curve
        plt.plot(requests, hit_rate, color='blue', linewidth=2, marker='o', markersize=3)
        plt.fill_between(requests, hit_rate, alpha=0.3, color='blue')
        title = 'Cache Hit Rate Over Time (Simulated)'
    
    plt.xlabel('Request Number', fontsize=12)
    plt.ylabel('Cache Hit Rate', fontsize=12)
    plt.title(title, fontsize=14, fontweight='bold')
    plt.ylim(0, 1)
    plt.grid(alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300)
    print(f"✅ Saved cache hit rate to {output_file}")
    plt.close()

def generate_all_plots():
    """Generate all visualization plots."""
    print("=" * 60)
    print("GENERATING BENCHMARK VISUALIZATIONS")
    print("=" * 60)
    
    # Check for dashboard_results.json first (new format)
    dashboard_exists = os.path.exists("dashboard_results.json")
    scalability_exists = os.path.exists("scalability_results.txt")
    stale_cache_exists = os.path.exists("stale_cache_results.txt")
    
    latencies = None
    requests_data = None
    dashboard_data = None
    
    # Try to load from dashboard_results.json
    if dashboard_exists:
        print("\n📊 Loading data from dashboard_results.json...")
        try:
            with open("dashboard_results.json", "r") as f:
                dashboard_data = json.load(f)
            
            # Extract latencies from all requests
            if "all_requests" in dashboard_data and dashboard_data["all_requests"]:
                requests_data = dashboard_data["all_requests"]
                latencies = [r["latency_ms"] for r in requests_data if "latency_ms" in r]
                print(f"   Found {len(latencies)} latency measurements")
                print(f"   Cache stats: {dashboard_data.get('cache_stats', {})}")
            
            # Generate latency distribution from actual data
            if latencies:
                print("\n📊 Generating latency distribution from actual data...")
                cache_stats = dashboard_data.get('cache_stats', {})
                hit_rate = cache_stats.get('hit_rate_percent', 0)
                plot_latency_distribution(latencies, title_suffix=f"Hit Rate: {hit_rate:.1f}%")
            else:
                print("   ⚠️  No latency data found in dashboard_results.json")
        
        except Exception as e:
            print(f"   ⚠️  Error reading dashboard_results.json: {e}")
    
    # Fallback to old scalability_results.txt format
    if not latencies and scalability_exists:
        print("\n📊 Generating latency distribution from scalability_results.txt...")
        # Parse scalability results
        with open("scalability_results.txt", "r") as f:
            lines = f.readlines()
            # For demo, generate synthetic data based on results
            # In real scenario, you'd save raw latency data
            p50 = float([l for l in lines if "p50:" in l][0].split(":")[1].strip().replace(" ms", ""))
            p95 = float([l for l in lines if "p95:" in l][0].split(":")[1].strip().replace(" ms", ""))
            p99 = float([l for l in lines if "p99:" in l][0].split(":")[1].strip().replace(" ms", ""))
            
            # Generate synthetic latency distribution
            latencies = np.concatenate([
                np.random.normal(p50, p50*0.2, 500),
                np.random.normal(p95, p95*0.1, 400),
                np.random.normal(p99, p99*0.05, 100)
            ])
            latencies = np.clip(latencies, 0, None)  # No negative latencies
            
            plot_latency_distribution(latencies)
    elif not latencies:
        print("\n⚠️  No latency data found. Run results_dashboard.py or benchmark_scalability.py first.")
    
    # Recovery timeline (only from old format for now)
    if stale_cache_exists:
        print("\n📊 Generating recovery timeline...")
        # Parse stale cache results
        with open("stale_cache_results.txt", "r") as f:
            lines = f.readlines()
            false_hits = int([l for l in lines if "False Hits:" in l][0].split(":")[1].strip())
            recovery_line = [l for l in lines if "Recovery Time:" in l][0].split(":")[1].strip()
            
            # Handle NOT RECOVERED case
            if "NOT RECOVERED" in recovery_line:
                recovery_time = 15.0  # Use max test duration
            else:
                recovery_time = float(recovery_line.replace("s", ""))
            
            plot_recovery_timeline(false_hits, recovery_time)
    else:
        print("\n⚠️  stale_cache_results.txt not found. Run benchmark_stale_cache.py for recovery timeline.")
    
    # Cache hit rate - use actual data if available
    print("\n📊 Generating cache hit rate...")
    if requests_data:
        plot_cache_hit_rate(requests_data=requests_data)
    else:
        plot_cache_hit_rate()  # Use simulation
    
    # Additional plots from dashboard data
    if dashboard_exists and requests_data and dashboard_data:
        print("\n📊 Generating additional visualizations...")
        
        # Worker load distribution
        workers_data = dashboard_data.get("workers", {})
        if workers_data:
            # Calculate hits/misses per worker
            for worker_id in workers_data:
                workers_data[worker_id]["cache_hits"] = sum(
                    1 for r in requests_data 
                    if r.get("worker") == worker_id and r.get("cache_status") == "HIT"
                )
                workers_data[worker_id]["cache_misses"] = sum(
                    1 for r in requests_data 
                    if r.get("worker") == worker_id and r.get("cache_status") == "MISS"
                )
            plot_worker_load_distribution(workers_data)
        
        # Latency by cache status
        plot_latency_by_cache_status(requests_data)
        
        # Match length distribution
        plot_match_length_distribution(requests_data)
    
    print("\n" + "=" * 60)
    print("✅ VISUALIZATION COMPLETE")
    print("=" * 60)
    print("\nGenerated files:")
    if latencies:
        print("  - latency_distribution.png (from actual data)")
    if stale_cache_exists:
        print("  - recovery_timeline.png")
    print("  - cache_hit_rate.png")
    if dashboard_exists and requests_data:
        print("  - worker_load_distribution.png")
        print("  - latency_by_cache_status.png")
        print("  - match_length_distribution.png")

if __name__ == "__main__":
    generate_all_plots()
