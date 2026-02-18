#!/usr/bin/env python3
"""
Integration test: Cartridges â†’ Queries â†’ DeltaRegistry â†’ Phantom Tracking
Simulates Phase 2B query stream and tracks Phase 2C phantoms.
"""

from kitbash_query_engine import CartridgeQueryEngine
from kitbash_registry import DeltaRegistry
import random


def test_integration():
    """
    1. Load cartridges
    2. Run simulated query stream
    3. Track hits in DeltaRegistry
    4. Show Phase 2C phantom tracking results
    """
    
    # Initialize
    engine = CartridgeQueryEngine("./cartridges")
    registry = DeltaRegistry("all_cartridges")
    
    # Check if any cartridges loaded
    if not engine.cartridges:
        print("X ERROR: No cartridges loaded!")
        print("\nMake sure to run: python build_phase2b_cartridges.py")
        return False
    
    # Simulated queries (like what users would ask)
    test_queries = [
        "force acceleration motion",
        "energy heat temperature",
        "atoms molecules bonds",
        "evolution adaptation fitness",
        "DNA genes inheritance",
        "cells mitochondria energy",
        "logic reasoning proof",
        "probability statistics inference",
        "pressure flow dynamics",
        "metabolism ATP energy",
        "enzyme catalyst reaction",
        "structure atoms electrons",
        "motion forces Newton",
        "thermodynamic entropy disorder",
        "information genes protein",
    ]
    
    print("="*70)
    print("PHASE 2B CARTRIDGE INTEGRATION TEST")
    print("="*70)
    
    # Run 10 query cycles
    for cycle in range(10):
        print(f"\n--- Cycle {cycle + 1} ---")
        
        # Pick random queries for this cycle
        cycle_queries = random.sample(test_queries, min(5, len(test_queries)))
        
        for query in cycle_queries:
            result = engine.keyword_query(query)
            print(f"Query: '{query}' -> {len(result.fact_ids)} hits")
            
            # Record each hit in registry
            for fact_id in result.fact_ids:
                confidence = result.confidences[fact_id]
                
                # Find which cartridge this fact is from
                cart_name = "unknown"
                for cn, cart in engine.cartridges.items():
                    fact = engine.get_fact(fact_id, cn)
                    if fact:
                        cart_name = cn
                        break
                
                registry.record_hit(fact_id, cart_name, confidence)
        
        registry.advance_cycle()
    
    # Statistics
    print("\n" + "="*70)
    print("STATISTICS")
    print("="*70)
    
    stats = engine.get_cartridge_stats()
    print(f"Cartridges loaded: {len(engine.cartridges)}")
    print(f"Cartridge breakdown:")
    total_facts = 0
    for cart_name in sorted(stats.keys()):
        count = stats[cart_name]
        total_facts += count
        print(f"  - {cart_name}: {count} facts")
    
    print(f"\nTotal facts available: {total_facts}")
    print(f"Total query cycles: {registry.cycle_count}")
    print(f"Total phantoms tracked: {len(registry.phantoms)}")
    
    # PHANTOM TRACKING (PHASE 2C WEEK 1)
    print("\n" + "="*70)
    print("PHANTOM TRACKING (PHASE 2C WEEK 1)")
    print("="*70)
    
    # Get locked phantoms (crystallization candidates)
    locked = registry.get_locked_phantoms()
    
    print(f"\n+ Locked phantoms (ready for crystallization): {len(locked)}")
    
    if len(locked) > 0:
        print("\nTop locked phantoms:\n")
        for i, phantom in enumerate(locked[:10], 1):
            avg_conf = phantom._avg_confidence()
            print(f"  {i:2d}. Fact {phantom.fact_id:3d}: "
                  f"{phantom.hit_count:2d} hits | "
                  f"conf={avg_conf:.2f} | "
                  f"consistency={phantom.cycle_consistency:.2f}")
        
        if len(locked) > 10:
            print(f"\n  ... and {len(locked) - 10} more locked phantoms")
    else:
        print("\n  (None locked yet - need more query cycles)")
    
    # Persistent (approaching lock) phantoms
    persistent = registry.get_persistent_phantoms()
    print(f"\n+ Persistent phantoms (approaching lock): {len(persistent)}")
    
    # Phase 2B readiness check
    print("\n" + "="*70)
    print("PHASE 2B READINESS CHECK")
    print("="*70)
    
    checks = [
        ("Cartridges loaded", len(engine.cartridges) >= 6),
        ("Total facts available", total_facts >= 200),
        ("Query engine working", len(registry.phantoms) > 0),
        ("DeltaRegistry tracking", registry.cycle_count >= 10),
    ]
    
    all_pass = True
    for check_name, passed in checks:
        status = "+" if passed else "X"
        print(f"  {status} {check_name}")
        if not passed:
            all_pass = False
    
    # Phase 2C readiness check (informational - requires 50+ cycles for locked phantoms)
    print("\n" + "="*70)
    print("PHASE 2C WEEK 1 READINESS (Informational)")
    print("="*70)
    
    phase2c_checks = [
        ("Phantom tracking active", len(registry.phantoms) > 0),
        ("Phantoms detected", len(registry.phantoms) >= 10),
        ("Cycles completed", registry.cycle_count >= 10),
    ]
    
    phase2c_pass = True
    for check_name, passed in phase2c_checks:
        status = "+" if passed else "X"
        print(f"  {status} {check_name}")
        if not passed:
            phase2c_pass = False
    
    # Note on locked phantoms (requires longer running)
    print(f"\nLocked phantoms: {len(locked)} (requires 50+ cycles to lock)")
    print(f"Persistent phantoms: {len(persistent)} (approaching lock threshold)")
    
    # Final status
    print("\n" + "="*70)
    if all_pass:
        print("+ PHASE 2B READY")
    else:
        print("X PHASE 2B NOT READY")
    
    if phase2c_pass:
        print("+ PHASE 2C WEEK 1 FOUNDATION READY")
        print(f"  Next: Run 50+ cycles for phantom locking (Phase 2C Week 2)")
    else:
        print("X PHASE 2C WEEK 1 NEEDS MORE DATA")
        print(f"  Current phantoms: {len(registry.phantoms)}")
    print("="*70)
    
    # Phase 2B completion is what matters for this milestone
    return all_pass


if __name__ == "__main__":
    success = test_integration()
    exit(0 if success else 1)
