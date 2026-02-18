#!/usr/bin/env python3
"""
Debug script: Trace phantom status updates
Shows exactly why phantoms aren't becoming persistent
"""

from kitbash_registry import DeltaRegistry
import statistics

def debug_phantom_status():
    """Test the phantom status logic directly."""
    
    print("\n" + "="*70)
    print("DEBUG: PHANTOM STATUS UPDATE LOGIC")
    print("="*70)
    
    # Create a test registry
    registry = DeltaRegistry("test", persistence_threshold=5, confidence_threshold=0.75)
    
    print(f"\nThresholds:")
    print(f"  persistence_threshold: {registry.persistence_threshold}")
    print(f"  confidence_threshold: {registry.confidence_threshold}")
    
    # Simulate recording 10 hits for fact_id=1
    print(f"\nSimulating 10 query hits for fact_id=1...")
    for i in range(10):
        confidence = 0.90  # High confidence
        registry.record_hit(fact_id=1, query_concepts=["test"], confidence=confidence)
        print(f"  Hit {i+1}: confidence={confidence}, "
              f"hit_count={registry.phantoms[1].hit_count}, "
              f"status={registry.phantoms[1].status}")
    
    # Check the phantom
    phantom = registry.phantoms[1]
    print(f"\nAfter 10 hits:")
    print(f"  hit_count: {phantom.hit_count}")
    print(f"  confidence_history: {phantom.confidence_history}")
    print(f"  avg_confidence: {statistics.mean(phantom.confidence_history):.3f}")
    print(f"  status: {phantom.status}")
    print(f"  Should be persistent? {phantom.hit_count >= 5 and statistics.mean(phantom.confidence_history) >= 0.75}")
    
    # Now call advance_cycle
    print(f"\nCalling advance_cycle()...")
    registry.advance_cycle()
    
    print(f"\nAfter advance_cycle():")
    print(f"  hit_count: {phantom.hit_count} (was reset)")
    print(f"  status: {phantom.status}")
    print(f"  cycle_history: {registry.cycle_history[1]}")
    
    # Check actual registry data from file
    print(f"\n" + "="*70)
    print("DEBUG: CHECK ACTUAL REGISTRY FILES")
    print("="*70)
    
    from pathlib import Path
    import json
    
    registry_dir = Path("./registry")
    registries = list(registry_dir.glob("*_registry.json"))
    
    if registries:
        sample_reg = registries[0]
        print(f"\nLoading {sample_reg.name}...")
        
        with open(sample_reg) as f:
            data = json.load(f)
        
        print(f"  Total phantoms: {len(data['phantoms'])}")
        
        # Show first phantom in detail
        if data['phantoms']:
            first_phantom_id = list(data['phantoms'].keys())[0]
            first_phantom = data['phantoms'][first_phantom_id]
            
            print(f"\nFirst phantom (fact_id={first_phantom_id}):")
            print(f"  hit_count: {first_phantom['hit_count']}")
            print(f"  confidence_history length: {len(first_phantom['confidence_history'])}")
            if first_phantom['confidence_history']:
                avg_conf = statistics.mean(first_phantom['confidence_history'])
                print(f"  avg_confidence: {avg_conf:.3f}")
            print(f"  status: {first_phantom['status']}")
            print(f"  cycle_consistency: {first_phantom['cycle_consistency']:.3f}")
            
            # Check if it should be persistent
            should_be_persistent = (
                len(first_phantom['confidence_history']) >= 5 and
                statistics.mean(first_phantom['confidence_history']) >= 0.75
            )
            print(f"\n  Should be persistent? {should_be_persistent}")
            print(f"    - confidence_history length >= 5? {len(first_phantom['confidence_history']) >= 5}")
            print(f"    - avg_confidence >= 0.75? {statistics.mean(first_phantom['confidence_history']) >= 0.75}")


if __name__ == "__main__":
    debug_phantom_status()
