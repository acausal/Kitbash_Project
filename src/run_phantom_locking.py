#!/usr/bin/env python3
"""
Phase 2C Week 2 Setup: Generate locked phantoms

Runs 100+ query cycles to lock phantoms (50+ cycles required).
This prepares the data for grain crystallization.

Produces:
- registry/<cartridge>_registry.json files with locked phantom data
- Summary of locked phantoms ready for crystallization
"""

import random
import json
from pathlib import Path
from kitbash_query_engine import CartridgeQueryEngine
from kitbash_registry import DeltaRegistry


def run_phantom_locking(cycles: int = 110, verbose: bool = True):
    """
    Run enough query cycles to lock phantoms for crystallization.
    
    Args:
        cycles: Number of query cycles to run (default 110, enough to lock at 50 threshold)
        verbose: Print detailed output
    
    Returns:
        dict of cartridge_name -> registry for further processing
    """
    
    # Initialize
    engine = CartridgeQueryEngine("./cartridges")
    
    if not engine.cartridges:
        print("X ERROR: No cartridges loaded!")
        print("Run: python setup_phase2b.py")
        return None
    
    # Test queries covering all domains
    test_queries = [
        # Physics
        "force acceleration motion",
        "energy heat temperature",
        "pressure flow dynamics",
        "motion forces Newton",
        "atoms molecules bonds",
        "structure atoms electrons",
        
        # Chemistry
        "atoms molecules bonds",
        "structure atoms electrons",
        "enzyme catalyst reaction",
        "reaction kinetics rate",
        "bonding electrons valence",
        
        # Biology
        "evolution adaptation fitness",
        "DNA genes inheritance",
        "cells mitochondria energy",
        "information genes protein",
        "enzyme catalyst reaction",
        
        # Biochemistry
        "metabolism ATP energy",
        "cells mitochondria energy",
        "information genes protein",
        "enzyme catalyst reaction",
        
        # Thermodynamics
        "energy heat temperature",
        "thermodynamic entropy disorder",
        "pressure flow dynamics",
        
        # Statistics
        "probability statistics inference",
        "data analysis distribution",
        
        # Logic
        "logic reasoning proof",
        "reasoning inference conclusion",
        
        # Neuroscience
        "information genes protein",
        "cells mitochondria energy",
        "structure atoms electrons",
    ]
    
    # Per-cartridge registries (we'll track per cartridge)
    registries = {}
    
    if verbose:
        print("="*70)
        print("PHASE 2C WEEK 2: PHANTOM LOCKING")
        print("="*70)
        print(f"Running {cycles} query cycles to lock phantoms...")
        print(f"(Phantoms lock after 50+ cycles)\n")
    
    # Run cycles
    for cycle_num in range(cycles):
        if verbose and (cycle_num + 1) % 10 == 0:
            print(f"  Cycle {cycle_num + 1}/{cycles}")
        
        # Pick random queries for this cycle
        cycle_queries = random.sample(
            test_queries, 
            min(random.randint(3, 6), len(test_queries))
        )
        
        for query in cycle_queries:
            result = engine.keyword_query(query)
            
            # Track hits by cartridge
            for fact_id in result.fact_ids:
                confidence = result.confidences.get(fact_id, 0.8)
                
                # Find which cartridge this fact is from
                for cart_name, cart in engine.cartridges.items():
                    fact = engine.get_fact(fact_id, cart_name)
                    if fact:
                        # Initialize registry for this cartridge if needed
                        if cart_name not in registries:
                            registries[cart_name] = DeltaRegistry(cart_name)
                        
                        # Record hit
                        registries[cart_name].record_hit(
                            fact_id,
                            query.split(),
                            confidence
                        )
                        break
        
        # Advance all registries by one cycle
        for registry in registries.values():
            registry.advance_cycle()
    
    if verbose:
        print(f"\n  Completed {cycles} cycles!")
    
    return registries


def save_registries(registries: dict, output_dir: str = "./registry"):
    """Save all registries to JSON files."""
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    for cart_name, registry in registries.items():
        filepath = Path(output_dir) / f"{cart_name}_registry.json"
        registry.save(str(filepath))


def summarize_locked_phantoms(registries: dict):
    """Print summary of locked phantoms ready for crystallization."""
    
    print("\n" + "="*70)
    print("PHANTOM LOCKING RESULTS")
    print("="*70)
    
    total_locked = 0
    total_persistent = 0
    total_phantoms = 0
    
    all_stats = []
    
    for cart_name, registry in registries.items():
        locked = [p for p in registry.phantoms.values() if p.status == "locked"]
        persistent = [p for p in registry.phantoms.values() if p.status == "persistent"]
        
        total_locked += len(locked)
        total_persistent += len(persistent)
        total_phantoms += len(registry.phantoms)
        
        all_stats.append({
            "cartridge": cart_name,
            "locked": len(locked),
            "persistent": len(persistent),
            "total": len(registry.phantoms),
            "cycles": registry.cycle_count,
        })
    
    # Print by cartridge
    print("\nPer-cartridge status:")
    print(f"{'Cartridge':<20} {'Locked':<10} {'Persistent':<12} {'Total':<8} {'Cycles':<8}")
    print("-" * 70)
    
    for stat in sorted(all_stats, key=lambda x: x['locked'], reverse=True):
        print(f"{stat['cartridge']:<20} {stat['locked']:<10} {stat['persistent']:<12} {stat['total']:<8} {stat['cycles']:<8}")
    
    print("-" * 70)
    print(f"{'TOTAL':<20} {total_locked:<10} {total_persistent:<12} {total_phantoms:<8}")
    
    # Summary
    print(f"\n✓ Successfully locked {total_locked} phantoms")
    print(f"✓ {total_persistent} phantoms approaching lock")
    print(f"✓ {total_phantoms} total phantoms tracked")
    print(f"✓ Registries saved to: ./registry/")
    
    # Quality check
    avg_confidence = []
    for registry in registries.values():
        for phantom in registry.phantoms.values():
            if phantom.confidence_history:
                avg_confidence.append(phantom._avg_confidence())
    
    if avg_confidence:
        print(f"\nConfidence scores:")
        print(f"  Mean:     {sum(avg_confidence) / len(avg_confidence):.4f}")
        print(f"  Min:      {min(avg_confidence):.4f}")
        print(f"  Max:      {max(avg_confidence):.4f}")
    
    print("\n" + "="*70)


def main():
    """Main execution."""
    registries = run_phantom_locking(cycles=110, verbose=True)
    
    if registries is None:
        print("\nX Setup failed!")
        return False
    
    # Save registries
    save_registries(registries)
    
    # Print summary
    summarize_locked_phantoms(registries)
    
    print("\n✓ Phase 2C Week 2 ready!")
    print("\nNext steps:")
    print("  1. Review locked phantoms above")
    print("  2. Build manual query CLI")
    print("  3. Run axiom_validator on locked phantoms")
    print("  4. Crystallize to ternary grains")
    
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
