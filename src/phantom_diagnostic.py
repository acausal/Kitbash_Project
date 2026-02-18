#!/usr/bin/env python3
"""
Phantom Diagnostic: Inspect registry phantoms in detail
Shows why phantoms aren't locking
"""

from pathlib import Path
from kitbash_registry import DeltaRegistry
import statistics

def diagnose_registry(registry_path: str):
    """Analyze a single registry in detail."""
    registry = DeltaRegistry.load(registry_path)
    
    print(f"\n{'='*70}")
    print(f"Registry: {Path(registry_path).stem}")
    print(f"{'='*70}")
    print(f"Total cycles: {registry.cycle_count}")
    print(f"Total phantoms: {len(registry.phantoms)}")
    print()
    
    # Group by status
    by_status = {"none": [], "transient": [], "persistent": [], "locked": []}
    for fact_id, phantom in registry.phantoms.items():
        by_status[phantom.status].append((fact_id, phantom))
    
    # Print summary
    for status in ["locked", "persistent", "transient", "none"]:
        count = len(by_status[status])
        print(f"{status:12s}: {count:3d}")
    
    print()
    
    # Show details for persistent and locked
    if by_status["persistent"]:
        print("PERSISTENT PHANTOMS (approaching lock):")
        for fact_id, phantom in by_status["persistent"][:5]:
            avg_conf = statistics.mean(phantom.confidence_history) if phantom.confidence_history else 0
            cycles_in_history = len(registry.cycle_history[fact_id])
            print(f"  fact_id={fact_id:4d}: "
                  f"hits={phantom.hit_count:2d}, "
                  f"avg_conf={avg_conf:.3f}, "
                  f"cycles_in_history={cycles_in_history}, "
                  f"consistency={phantom.cycle_consistency:.3f}")
        if len(by_status["persistent"]) > 5:
            print(f"  ... and {len(by_status['persistent']) - 5} more")
    
    if by_status["locked"]:
        print("\nLOCKED PHANTOMS (ready for crystallization):")
        for fact_id, phantom in by_status["locked"][:10]:
            avg_conf = statistics.mean(phantom.confidence_history) if phantom.confidence_history else 0
            cycles_in_history = len(registry.cycle_history[fact_id])
            print(f"  fact_id={fact_id:4d}: "
                  f"hits={phantom.hit_count:2d}, "
                  f"avg_conf={avg_conf:.3f}, "
                  f"cycles_in_history={cycles_in_history}, "
                  f"consistency={phantom.cycle_consistency:.3f}")
    
    # Show top 5 transients by hit count
    if by_status["transient"]:
        print("\nTOP 5 TRANSIENT PHANTOMS (high activity, not persistent yet):")
        sorted_transient = sorted(by_status["transient"], 
                                 key=lambda x: x[1].hit_count, 
                                 reverse=True)[:5]
        for fact_id, phantom in sorted_transient:
            avg_conf = statistics.mean(phantom.confidence_history) if phantom.confidence_history else 0
            print(f"  fact_id={fact_id:4d}: "
                  f"hits={phantom.hit_count:2d}, "
                  f"avg_conf={avg_conf:.3f}, "
                  f"confidence_threshold={registry.confidence_threshold}")
    
    print()


def main():
    """Run diagnostics on all registries."""
    registry_dir = Path("./registry")
    
    if not registry_dir.exists():
        print("Registry directory not found")
        return
    
    registries = list(registry_dir.glob("*_registry.json"))
    
    if not registries:
        print("No registries found")
        return
    
    print(f"\n{'='*70}")
    print("PHANTOM DIAGNOSTIC REPORT")
    print(f"Found {len(registries)} registries")
    print(f"{'='*70}")
    
    # Global stats
    total_locked = 0
    total_persistent = 0
    total_phantoms = 0
    total_cycles = 0
    
    for registry_path in sorted(registries):
        try:
            registry = DeltaRegistry.load(str(registry_path))
            total_locked += len(registry.get_locked_phantoms())
            total_persistent += len(registry.get_persistent_phantoms())
            total_phantoms += len(registry.phantoms)
            total_cycles += registry.cycle_count
            
            diagnose_registry(str(registry_path))
        except Exception as e:
            print(f"Error loading {registry_path}: {e}")
    
    # Global summary
    print(f"\n{'='*70}")
    print("GLOBAL SUMMARY")
    print(f"{'='*70}")
    print(f"Total cycles:      {total_cycles}")
    print(f"Total phantoms:    {total_phantoms}")
    print(f"Persistent:        {total_persistent}")
    print(f"Locked:            {total_locked}")
    print()
    
    # Analysis
    print("ANALYSIS:")
    if total_locked == 0:
        print("⚠ No locked phantoms yet")
        if total_persistent == 0:
            print("  → Phantoms aren't reaching 'persistent' status")
            print("  → Check: Are confidence scores > 0.75?")
            print("  → Or: Are hit counts < 5?")
        else:
            print("  → Phantoms are persistent but need more stable cycles")
            print(f"  → Run {50 - total_cycles // len(registries)} more cycles")
    else:
        print(f"✓ {total_locked} phantoms ready for crystallization!")
    
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()
