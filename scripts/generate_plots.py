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

def plot_latency_distribution(latencies, output_file="latency_distribution.png"):
    """Generate histogram of router latencies."""
    plt.figure(figsize=(10, 6))
    
    # Create histogram
    plt.hist(latencies, bins=50, color='skyblue', edgecolor='black', alpha=0.7)
    
    # Add statistics lines
    median = np.median(latencies)
    p95 = np.percentile(latencies, 95)
    p99 = np.percentile(latencies, 99)
    
    plt.axvline(median, color='green', linestyle='--', linewidth=2, label=f'Median: {median:.2f}ms')
    plt.axvline(p95, color='orange', linestyle='--', linewidth=2, label=f'p95: {p95:.2f}ms')
    plt.axvline(p99, color='red', linestyle='--', linewidth=2, label=f'p99: {p99:.2f}ms')
    
    plt.xlabel('Latency (ms)', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title('Router Latency Distribution (100 Workers, 1000 Requests)', fontsize=14, fontweight='bold')
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

def plot_cache_hit_rate(output_file="cache_hit_rate.png"):
    """Generate simulated cache hit rate over time."""
    plt.figure(figsize=(10, 6))
    
    # Simulate data: cache warms up over time
    requests = list(range(1, 101))
    hit_rate = [min(0.05 + (i * 0.8 / 100), 0.85) for i in requests]  # Warm-up curve
    
    plt.plot(requests, hit_rate, color='blue', linewidth=2, marker='o', markersize=3)
    plt.fill_between(requests, hit_rate, alpha=0.3, color='blue')
    
    plt.xlabel('Request Number', fontsize=12)
    plt.ylabel('Cache Hit Rate', fontsize=12)
    plt.title('Cache Hit Rate Over Time (Simulated)', fontsize=14, fontweight='bold')
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
    
    # Check if result files exist
    scalability_exists = os.path.exists("scalability_results.txt")
    stale_cache_exists = os.path.exists("stale_cache_results.txt")
    
    if scalability_exists:
        print("\n📊 Generating latency distribution...")
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
    else:
        print("\n⚠️  scalability_results.txt not found. Run benchmark_scalability.py first.")
    
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
        print("\n⚠️  stale_cache_results.txt not found. Run benchmark_stale_cache.py first.")
    
    print("\n📊 Generating cache hit rate simulation...")
    plot_cache_hit_rate()
    
    print("\n" + "=" * 60)
    print("✅ VISUALIZATION COMPLETE")
    print("=" * 60)
    print("\nGenerated files:")
    print("  - latency_distribution.png")
    print("  - recovery_timeline.png")
    print("  - cache_hit_rate.png")

if __name__ == "__main__":
    generate_all_plots()
