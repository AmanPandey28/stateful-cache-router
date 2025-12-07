"""
Generate comparison table and graph from collected strategy results.
Run this after collecting results for all strategies.
"""
import json
import os
import glob
import sys
from typing import Dict, List
import matplotlib.pyplot as plt
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def load_results() -> Dict[str, Dict]:
    """Load all result files."""
    results = {}
    
    # Look for result files
    result_files = glob.glob("results_*.json")
    
    if not result_files:
        print("❌ No result files found!")
        print("   Expected files: results_cache_aware.json, results_round_robin.json, results_least_loaded.json")
        print("   Run scripts/collect_strategy_results.py first for each strategy.")
        return None
    
    for file in result_files:
        try:
            with open(file, 'r') as f:
                data = json.load(f)
                strategy = data.get('strategy', file.replace('results_', '').replace('.json', ''))
                results[strategy] = data
                print(f"✅ Loaded {file} ({strategy})")
        except Exception as e:
            print(f"⚠️  Error loading {file}: {e}")
    
    return results if results else None


def print_comparison_table(results: Dict[str, Dict]):
    """Print a formatted comparison table."""
    print("\n" + "="*80)
    print("STRATEGY COMPARISON TABLE")
    print("="*80)
    
    # Header
    print(f"{'Strategy':<20} {'Hit Rate':<12} {'Avg Latency':<15} {'p95 Latency':<15} {'Workers':<15}")
    print("-" * 80)
    
    # Strategy names for display
    strategy_names = {
        "cache_aware": "Cache-Aware",
        "round_robin": "Round-Robin",
        "least_loaded": "Least-Loaded"
    }
    
    # Sort by strategy name for consistent display
    sorted_strategies = sorted(results.keys())
    
    for strategy in sorted_strategies:
        r = results[strategy]
        name = strategy_names.get(strategy, strategy.replace('_', '-').title())
        hit_rate = f"{r.get('hit_rate', 0):.1f}%"
        avg_lat = f"{r.get('avg_latency', 0):.2f} ms"
        p95_lat = f"{r.get('p95_latency', 0):.2f} ms" if 'p95_latency' in r else "N/A"
        num_workers = len(r.get('worker_distribution', {}))
        
        print(f"{name:<20} {hit_rate:<12} {avg_lat:<15} {p95_lat:<15} {num_workers:<15}")
    
    print("="*80)
    
    # Detailed breakdown
    print("\n" + "="*80)
    print("DETAILED BREAKDOWN")
    print("="*80)
    
    for strategy in sorted_strategies:
        r = results[strategy]
        name = strategy_names.get(strategy, strategy.replace('_', '-').title())
        
        print(f"\n{name}:")
        print(f"  Total Requests:     {r.get('total_requests', 0)}")
        print(f"  Cache Hits:         {r.get('cache_hits', 0)}")
        print(f"  Cache Misses:       {r.get('cache_misses', 0)}")
        print(f"  Hit Rate:           {r.get('hit_rate', 0):.1f}%")
        print(f"  Avg Latency:        {r.get('avg_latency', 0):.2f} ms")
        if 'avg_hit_latency' in r:
            print(f"  Avg HIT Latency:    {r['avg_hit_latency']:.2f} ms")
        if 'avg_miss_latency' in r:
            print(f"  Avg MISS Latency:   {r['avg_miss_latency']:.2f} ms")
        if 'p95_latency' in r:
            print(f"  p95 Latency:        {r['p95_latency']:.2f} ms")
        if 'p99_latency' in r:
            print(f"  p99 Latency:        {r['p99_latency']:.2f} ms")
        
        print(f"  Worker Distribution:")
        for worker, count in r.get('worker_distribution', {}).items():
            pct = (count / r.get('total_requests', 1)) * 100
            print(f"    {worker}: {count} requests ({pct:.1f}%)")
        
        if r.get('avg_match_length', 0) > 0:
            print(f"  Avg Match Length:   {r['avg_match_length']:.2f} blocks")


def generate_comparison_graph(results: Dict[str, Dict]):
    """Generate comparison graphs."""
    strategy_names = {
        "cache_aware": "Cache-Aware",
        "round_robin": "Round-Robin",
        "least_loaded": "Least-Loaded"
    }
    
    strategies = sorted(results.keys())
    names = [strategy_names.get(s, s.replace('_', '-').title()) for s in strategies]
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Routing Strategy Comparison', fontsize=16, fontweight='bold')
    
    # 1. Hit Rate Comparison
    ax1 = axes[0, 0]
    hit_rates = [results[s].get('hit_rate', 0) for s in strategies]
    bars1 = ax1.bar(names, hit_rates, color=['#2ecc71', '#e74c3c', '#e74c3c'])
    ax1.set_ylabel('Hit Rate (%)', fontsize=11)
    ax1.set_title('Cache Hit Rate', fontsize=12, fontweight='bold')
    ax1.set_ylim(0, max(100, max(hit_rates) * 1.2))
    ax1.grid(axis='y', alpha=0.3)
    
    # Add value labels on bars
    for bar, rate in zip(bars1, hit_rates):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{rate:.1f}%', ha='center', va='bottom', fontweight='bold')
    
    # 2. Average Latency Comparison
    ax2 = axes[0, 1]
    avg_latencies = [results[s].get('avg_latency', 0) for s in strategies]
    bars2 = ax2.bar(names, avg_latencies, color=['#3498db', '#3498db', '#3498db'])
    ax2.set_ylabel('Latency (ms)', fontsize=11)
    ax2.set_title('Average Latency', fontsize=12, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    
    # Add value labels
    for bar, lat in zip(bars2, avg_latencies):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{lat:.2f}ms', ha='center', va='bottom', fontweight='bold')
    
    # 3. p95 Latency Comparison
    ax3 = axes[1, 0]
    p95_latencies = [results[s].get('p95_latency', 0) for s in strategies if 'p95_latency' in results[s]]
    p95_names = [names[i] for i, s in enumerate(strategies) if 'p95_latency' in results[s]]
    if p95_latencies:
        bars3 = ax3.bar(p95_names, p95_latencies, color=['#9b59b6', '#9b59b6', '#9b59b6'])
        ax3.set_ylabel('Latency (ms)', fontsize=11)
        ax3.set_title('p95 Latency', fontsize=12, fontweight='bold')
        ax3.grid(axis='y', alpha=0.3)
        
        # Add value labels
        for bar, lat in zip(bars3, p95_latencies):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{lat:.2f}ms', ha='center', va='bottom', fontweight='bold')
    else:
        ax3.text(0.5, 0.5, 'No p95 latency data', ha='center', va='center', transform=ax3.transAxes)
        ax3.set_title('p95 Latency', fontsize=12, fontweight='bold')
    
    # 4. Worker Distribution
    ax4 = axes[1, 1]
    num_workers = [len(results[s].get('worker_distribution', {})) for s in strategies]
    bars4 = ax4.bar(names, num_workers, color=['#f39c12', '#f39c12', '#f39c12'])
    ax4.set_ylabel('Number of Workers', fontsize=11)
    ax4.set_title('Workers Used', fontsize=12, fontweight='bold')
    ax4.grid(axis='y', alpha=0.3)
    
    # Add value labels
    for bar, num in zip(bars4, num_workers):
        height = bar.get_height()
        ax4.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(num)}', ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    
    # Save figure
    output_file = "strategy_comparison.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n📊 Comparison graph saved to {output_file}")
    
    return output_file


def main():
    """Main function."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║              STRATEGY COMPARISON GENERATOR                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Load results
    results = load_results()
    
    if not results:
        return
    
    print(f"\n✅ Loaded {len(results)} strategy result(s)")
    
    # Print comparison table
    print_comparison_table(results)
    
    # Generate graph
    try:
        generate_comparison_graph(results)
    except ImportError:
        print("\n⚠️  matplotlib not available. Skipping graph generation.")
        print("   Install with: pip install matplotlib")
    except Exception as e:
        print(f"\n⚠️  Error generating graph: {e}")
    
    # Save combined results
    output_file = "strategy_comparison_summary.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Combined results saved to {output_file}")
    
    print("\n" + "="*80)
    print("✅ Comparison complete!")
    print("="*80)


if __name__ == "__main__":
    main()

