#!/usr/bin/env python3
"""
Popcount Distribution Analysis - Standalone Demo

Demonstrates the grain inspection tool's popcount analysis.
"""

from grain_inspection_tool import (
    calculate_popcount,
    calculate_grain_quality,
    analyze_popcount_distribution
)


def demo_with_mock_grains():
    """Demo with mock grain data."""
    import statistics
    from collections import defaultdict

    print("Popcount Distribution Analysis - Mock Data Demo\n")

    # Create mock grains
    mock_grains = []
    for i in range(10):
        grain = {
            'grain_id': f'grain_{i:03d}',
            'cartridge': ['biology', 'chemistry', 'physics'][i % 3],
            'confidence': 0.7 + (i % 10) * 0.03,
            'fact_id': i,
            'delta': {
                'positive': list(range(50 + i * 20)),
                'negative': list(range(30 + i * 10))
            }
        }
        mock_grains.append(grain)

    # Analyze
    all_popcounts = []
    by_cartridge = defaultdict(list)

    print("--- INDIVIDUAL GRAINS ---\n")
    for grain in mock_grains:
        popcount = calculate_popcount(grain)
        quality = calculate_grain_quality(grain)
        all_popcounts.append(popcount)
        by_cartridge[grain['cartridge']].append(popcount)

        print(f"{grain['grain_id']} ({grain['cartridge']})")
        print(f"  Popcount: {popcount} bits")
        print(f"  Confidence: {grain['confidence']:.4f}")
        print(f"  Quality: {quality:.4f}")

    # Summary
    print("\n" + "=" * 80)
    print("POPCOUNT DISTRIBUTION SUMMARY")
    print("=" * 80)
    print(f"\nTotal grains: {len(all_popcounts)}")
    print(f"Min popcount:  {min(all_popcounts)} bits")
    print(f"Max popcount:  {max(all_popcounts)} bits")
    print(f"Mean popcount: {statistics.mean(all_popcounts):.1f} bits")
    print(f"Median:        {statistics.median(all_popcounts):.1f} bits")
    print(f"Stdev:         {statistics.stdev(all_popcounts):.1f} bits")

    # By cartridge
    print(f"\n--- BY CARTRIDGE ---")
    for cart in sorted(by_cartridge.keys()):
        pops = by_cartridge[cart]
        print(f"\n{cart.upper()}:")
        print(f"  Count: {len(pops)}")
        print(f"  Avg:   {statistics.mean(pops):.1f} bits")
        print(f"  Range: {min(pops)}-{max(pops)} bits")

    # Histogram
    print(f"\n--- HISTOGRAM ---\n")
    min_pop = min(all_popcounts)
    max_pop = max(all_popcounts)
    bucket_size = max(1, (max_pop - min_pop) // 8)

    buckets = {}
    for popcount in all_popcounts:
        bucket = (popcount - min_pop) // bucket_size
        buckets[bucket] = buckets.get(bucket, 0) + 1

    max_count = max(buckets.values())
    for i in range(max(buckets.keys()) + 1):
        if i not in buckets:
            continue
        count = buckets[i]
        bar_width = int(30 * count / max_count)
        start = min_pop + i * bucket_size
        end = start + bucket_size - 1
        print(f"{start:3}-{end:3} | {'█' * bar_width} {count}")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    demo_with_mock_grains()
