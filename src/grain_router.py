"""
GrainRouter - Layer 0 Grain Routing System

Loads crystallized grains and provides O(1) lookup for query routing.
Bridges between query concepts and crystallized Shannon grains.

Phase 3A Component
"""

import json
import time
from pathlib import Path
from typing import Dict, Optional, List, Any
from collections import defaultdict


class GrainRouter:
    """
    Routes queries to crystallized grains for Layer 0 reflex responses.
    
    Responsibilities:
    - Load all 261 crystallized grains from disk
    - Index grains by fact_id, cartridge, and concepts
    - Provide O(1) grain lookup by fact_id
    - Return routing decisions with confidence
    
    Performance:
    - Load time: ~1-2 seconds (all grains at startup)
    - Lookup time: <1ms (hash table)
    """
    
    def __init__(self, cartridges_dir: str = "./cartridges"):
        """
        Initialize GrainRouter.
        
        Args:
            cartridges_dir: Path to cartridges directory
        """
        self.cartridges_dir = Path(cartridges_dir)
        
        # Indices
        self.grains: Dict[str, Dict[str, Any]] = {}  # grain_id -> grain data
        self.grain_by_fact: Dict[int, str] = {}  # fact_id -> grain_id
        self.grain_by_cartridge: Dict[str, List[str]] = defaultdict(list)  # cartridge -> [grain_ids]
        self.grain_by_confidence: List[tuple] = []  # [(confidence, grain_id), ...] sorted desc
        
        # Statistics
        self.load_time_ms = 0
        self.total_grains = 0
        self.total_size_bytes = 0
        
        # Load all grains
        self._load_grains()
    
    def _load_grains(self) -> None:
        """Load all crystallized grains from disk."""
        start_time = time.perf_counter()
        
        # Find all grain files
        grain_count = 0
        duplicates = []
        
        for cartridge_dir in self.cartridges_dir.glob("*.kbc"):
            grains_dir = cartridge_dir / "grains"
            
            if not grains_dir.exists():
                continue
            
            cartridge_id = cartridge_dir.name.replace('.kbc', '')
            
            for grain_file in grains_dir.glob("*.json"):
                try:
                    with open(grain_file, 'r') as f:
                        grain = json.load(f)
                    
                    grain_id = grain.get('grain_id')
                    if not grain_id:
                        continue
                    
                    # Check for duplicate grain_id
                    if grain_id in self.grains:
                        duplicates.append((grain_id, cartridge_id, grain_file.name))
                        continue
                    
                    # Store grain
                    self.grains[grain_id] = grain
                    
                    # Index by fact_id
                    fact_id = grain.get('fact_id')
                    if fact_id is not None:
                        self.grain_by_fact[fact_id] = grain_id
                    
                    # Index by cartridge
                    self.grain_by_cartridge[cartridge_id].append(grain_id)
                    
                    # Track confidence
                    confidence = grain.get('confidence', 0.0)
                    self.grain_by_confidence.append((confidence, grain_id))
                    
                    # Statistics
                    grain_count += 1
                    self.total_size_bytes += grain_file.stat().st_size
                
                except Exception as e:
                    print(f"Warning: Could not load grain {grain_file}: {e}")
        
        # Report duplicates
        if duplicates:
            print(f"\nWarning: Found {len(duplicates)} duplicate grain_ids (skipped):")
            for grain_id, cartridge, filename in duplicates[:10]:  # Show first 10
                print(f"  - {grain_id} in {cartridge}/{filename}")
            if len(duplicates) > 10:
                print(f"  ... and {len(duplicates) - 10} more")
        
        # Sort by confidence (descending)
        self.grain_by_confidence.sort(reverse=True, key=lambda x: x[0])
        
        # Calculate statistics
        self.load_time_ms = (time.perf_counter() - start_time) * 1000
        self.total_grains = grain_count
    
    def lookup(self, fact_id: int) -> Optional[Dict[str, Any]]:
        """
        Look up a grain by fact_id.
        
        Args:
            fact_id: Fact identifier
        
        Returns:
            Grain data if found, None otherwise
        """
        grain_id = self.grain_by_fact.get(fact_id)
        if grain_id:
            return self.grains.get(grain_id)
        return None
    
    def lookup_by_grain_id(self, grain_id: str) -> Optional[Dict[str, Any]]:
        """
        Look up a grain by grain_id.
        
        Args:
            grain_id: Grain identifier (sg_XXXXXXXX)
        
        Returns:
            Grain data if found, None otherwise
        """
        return self.grains.get(grain_id)
    
    def lookup_by_cartridge(self, cartridge_id: str) -> List[Dict[str, Any]]:
        """
        Get all grains in a cartridge.
        
        Args:
            cartridge_id: Cartridge name
        
        Returns:
            List of grain data
        """
        grain_ids = self.grain_by_cartridge.get(cartridge_id, [])
        return [self.grains[gid] for gid in grain_ids if gid in self.grains]
    
    def get_top_confidence_grains(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get grains sorted by confidence (highest first).
        
        Args:
            limit: Maximum number of grains to return
        
        Returns:
            List of grain data sorted by confidence
        """
        return [
            self.grains[grain_id]
            for confidence, grain_id in self.grain_by_confidence[:limit]
            if grain_id in self.grains
        ]
    
    def search_grains(self, query_concepts: List[str]) -> List[tuple]:
        """
        Search for grains matching query concepts.
        
        This is a simple search that looks for grains with matching
        delta relationships. More sophisticated search would use
        semantic similarity.
        
        Args:
            query_concepts: Keywords from the query
        
        Returns:
            List of (grain_id, match_score) sorted by score descending
        """
        results = []
        
        for grain_id, grain in self.grains.items():
            # Score based on confidence (simple heuristic)
            # More sophisticated: match query concepts to delta
            score = grain.get('confidence', 0.0)
            
            # Bonus if grain has derivations
            delta = grain.get('delta', {})
            derivation_count = (
                len(delta.get('positive', [])) +
                len(delta.get('negative', [])) +
                len(delta.get('void', []))
            )
            if derivation_count > 0:
                score += 0.05  # Bonus for structured grains
            
            results.append((grain_id, score))
        
        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results
    
    def get_routing_decision(self, grain: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get routing recommendation from a grain.
        
        Determines which layer to use and with what confidence.
        
        Args:
            grain: Grain data
        
        Returns:
            Routing decision with confidence and recommendation
        """
        confidence = grain.get('confidence', 0.0)
        
        # Routing logic
        if confidence >= 0.95:
            return {
                'use_grain': True,
                'confidence': confidence,
                'layer_recommendation': 0,  # Use grain directly
                'rationale': 'Very high confidence - use grain',
            }
        elif confidence >= 0.85:
            return {
                'use_grain': True,
                'confidence': confidence,
                'layer_recommendation': 1,  # Use grain as hint for Layer 1
                'rationale': 'High confidence - use grain with Layer 1 verification',
            }
        elif confidence >= 0.75:
            return {
                'use_grain': True,
                'confidence': confidence,
                'layer_recommendation': 2,  # Use grain as hint for Layer 2+
                'rationale': 'Moderate confidence - use grain with cartridge lookup',
            }
        else:
            return {
                'use_grain': False,
                'confidence': confidence,
                'layer_recommendation': 3,  # Skip grain, go to Layer 3+
                'rationale': 'Low confidence - skip grain, use standard routing',
            }
    
    def print_statistics(self) -> None:
        """Print router statistics."""
        print("\n" + "="*70)
        print("GRAIN ROUTER STATISTICS")
        print("="*70)
        print(f"Grains loaded: {self.total_grains}")
        print(f"Total storage: {self.total_size_bytes:,} bytes")
        print(f"Average grain size: {self.total_size_bytes / self.total_grains if self.total_grains else 0:.0f} bytes")
        print(f"Load time: {self.load_time_ms:.1f}ms")
        
        # Cartridge breakdown
        print(f"\nCartridges ({len(self.grain_by_cartridge)}):")
        for cart_id in sorted(self.grain_by_cartridge.keys()):
            count = len(self.grain_by_cartridge[cart_id])
            print(f"  {cart_id:20} | {count:3d} grains")
        
        # Confidence distribution
        if self.grain_by_confidence:
            confidences = [c for c, _ in self.grain_by_confidence]
            min_conf = min(confidences)
            max_conf = max(confidences)
            avg_conf = sum(confidences) / len(confidences)
            
            print(f"\nConfidence distribution:")
            print(f"  Min: {min_conf:.4f}")
            print(f"  Avg: {avg_conf:.4f}")
            print(f"  Max: {max_conf:.4f}")
        
        print("="*70 + "\n")


# Example usage and testing
if __name__ == "__main__":
    print("Initializing GrainRouter...")
    router = GrainRouter('./cartridges')
    
    print(f"âœ“ Loaded {router.total_grains} grains in {router.load_time_ms:.1f}ms")
    
    # Print statistics
    router.print_statistics()
    
    # Test lookups
    print("\nTesting grain lookups:")
    
    # Find a sample grain
    if router.grain_by_fact:
        sample_fact_id = next(iter(router.grain_by_fact.keys()))
        grain = router.lookup(sample_fact_id)
        
        if grain:
            print(f"\n1. Lookup by fact_id {sample_fact_id}:")
            print(f"   Grain ID: {grain.get('grain_id')}")
            print(f"   Confidence: {grain.get('confidence', 0):.4f}")
            print(f"   Cartridge: {grain.get('cartridge_source')}")
            
            # Get routing decision
            decision = router.get_routing_decision(grain)
            print(f"\n2. Routing decision:")
            print(f"   Use grain: {decision['use_grain']}")
            print(f"   Confidence: {decision['confidence']:.4f}")
            print(f"   Layer recommendation: {decision['layer_recommendation']}")
            print(f"   Rationale: {decision['rationale']}")
    
    # Test top confidence grains
    print(f"\n3. Top 5 confidence grains:")
    top_grains = router.get_top_confidence_grains(5)
    for i, grain in enumerate(top_grains, 1):
        print(f"   {i}. {grain.get('grain_id'):15} "
              f"(confidence: {grain.get('confidence', 0):.4f}, "
              f"fact: {grain.get('fact_id')})")
    
    print("\nâœ“ GrainRouter ready for Layer 0 integration")
