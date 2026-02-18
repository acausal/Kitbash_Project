"""
Layer 0 Query Processor - Grain-based reflex routing

Integrates GrainRouter into the query processing pipeline.
Adds Layer 0 (grain lookup) before existing Layer 1-5 logic.

Phase 3A Component
"""

import time
from typing import Dict, Any, Optional, List
from grain_router import GrainRouter


class Layer0QueryProcessor:
    """
    Query processor with grain-based Layer 0.
    
    Architecture:
    ```
    Query Input
        ↓
    Layer 0: Grain Lookup (GrainRouter)
        ├─ Found + high confidence? → Return
        ├─ Found + medium confidence? → Hint to Layer 1
        ├─ Not found? → Continue to Layer 1
        └─ Low confidence? → Skip
        ↓
    Layers 1-5: Existing cartridge + LLM logic
        ↓
    Response Output
    ```
    """
    
    def __init__(self, cartridges_dir: str = "./cartridges"):
        """
        Initialize Layer 0 processor.
        
        Args:
            cartridges_dir: Path to cartridges directory
        """
        self.grain_router = GrainRouter(cartridges_dir)
        self.cartridges_dir = cartridges_dir
        
        # Statistics
        self.query_count = 0
        self.layer0_hits = 0
        self.layer0_escalations = 0
        self.total_latency = 0.0
    
    def process_query(self, user_query: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Process query with Layer 0 grain routing.
        
        Args:
            user_query: User's natural language query
            context: Optional context (hat, user, etc.)
        
        Returns:
            Response with routing information
        """
        start_time = time.perf_counter()
        
        self.query_count += 1
        
        # Layer 0: Try grain lookup
        grain_result = self._layer0_grain_lookup(user_query)
        
        if grain_result['found']:
            self.layer0_hits += 1
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            self.total_latency += latency_ms
            
            return {
                'answer': grain_result['answer'],
                'confidence': grain_result['confidence'],
                'layer': 'GRAIN',
                'grain_id': grain_result['grain_id'],
                'fact_id': grain_result['fact_id'],
                'cartridge': grain_result['cartridge'],
                'latency_ms': latency_ms,
                'routing': grain_result['routing_decision'],
            }
        
        # Layer 0 provided hint but not direct answer
        if grain_result['grain_hint']:
            self.layer0_escalations += 1
            
            # Continue to Layer 1, but pass grain hint
            # (This would integrate with existing query processor)
            latency_ms = (time.perf_counter() - start_time) * 1000
            self.total_latency += latency_ms
            
            return {
                'layer': 'GRAIN_HINT',
                'grain_hint': grain_result['grain_hint'],
                'grain_confidence': grain_result['grain_confidence'],
                'recommendation': 'Use grain info to guide Layer 1+ search',
                'latency_ms': latency_ms,
                'note': 'Would escalate to Layer 1 in full pipeline',
            }
        
        # No grain match - would continue to Layer 1-5
        latency_ms = (time.perf_counter() - start_time) * 1000
        self.total_latency += latency_ms
        
        return {
            'layer': 'NO_GRAIN',
            'grain_found': False,
            'recommendation': 'Continue to Layer 1+ (existing logic)',
            'latency_ms': latency_ms,
            'note': 'Would escalate to Layer 1 in full pipeline',
        }
    
    def _layer0_grain_lookup(self, user_query: str) -> Dict[str, Any]:
        """
        Perform Layer 0 grain lookup.
        
        Args:
            user_query: User's natural language query
        
        Returns:
            Lookup result with found flag and optional answer
        """
        result = {
            'found': False,
            'grain_hint': None,
            'grain_confidence': 0.0,
            'answer': None,
            'confidence': 0.0,
            'grain_id': None,
            'fact_id': None,
            'cartridge': None,
            'routing_decision': None,
        }
        
        # Simple heuristic: try to extract fact_id from query
        # In real system, would use more sophisticated concept extraction
        fact_id = self._extract_fact_id(user_query)
        
        if fact_id is None:
            # Try semantic search across all grains
            grains = self._search_grains_by_concept(user_query)
            
            if grains:
                # Use top grain
                grain = grains[0]
                fact_id = grain.get('fact_id')
        
        # Look up grain
        if fact_id is not None:
            grain = self.grain_router.lookup(fact_id)
            
            if grain:
                # Get routing decision
                routing_decision = self.grain_router.get_routing_decision(grain)
                confidence = grain.get('confidence', 0.0)
                
                result['grain_id'] = grain.get('grain_id')
                result['fact_id'] = fact_id
                result['cartridge'] = grain.get('cartridge_source')
                result['routing_decision'] = routing_decision
                result['grain_confidence'] = confidence
                
                # Determine if we can answer directly or need to escalate
                if routing_decision['use_grain']:
                    if routing_decision['layer_recommendation'] == 0:
                        # High confidence - answer directly
                        result['found'] = True
                        result['answer'] = self._format_grain_answer(grain, user_query)
                        result['confidence'] = confidence
                    else:
                        # Medium confidence - hint to Layer 1+
                        result['grain_hint'] = grain
        
        return result
    
    def _extract_fact_id(self, user_query: str) -> Optional[int]:
        """
        Try to extract fact_id from query.
        
        Very simple: looks for "fact 42" or similar patterns.
        In real system, would be more sophisticated.
        
        Args:
            user_query: User query
        
        Returns:
            Fact ID if found, None otherwise
        """
        # Check if query contains explicit fact reference
        # e.g., "What about fact 42?" or "Tell me about fact_id 42"
        import re
        
        match = re.search(r'fact[_\s]+(?:id)?[:\s]*(\d+)', user_query, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        
        return None
    
    def _search_grains_by_concept(self, user_query: str) -> List[Dict[str, Any]]:
        """
        Search grains by query concepts.
        
        Args:
            user_query: User query
        
        Returns:
            List of grain data sorted by relevance
        """
        # Extract simple keywords (in real system, use NLP)
        concepts = user_query.lower().split()
        
        # Search using grain router
        search_results = self.grain_router.search_grains(concepts)
        
        # Return top matches
        top_grains = []
        for grain_id, score in search_results[:5]:  # Top 5
            grain = self.grain_router.grains.get(grain_id)
            if grain:
                top_grains.append(grain)
        
        return top_grains
    
    def _format_grain_answer(self, grain: Dict[str, Any], user_query: str) -> str:
        """
        Format a grain-based answer.
        
        Args:
            grain: Grain data
            user_query: Original user query
        
        Returns:
            Formatted answer string
        """
        fact_id = grain.get('fact_id')
        confidence = grain.get('confidence', 0.0)
        grain_id = grain.get('grain_id')
        cartridge = grain.get('cartridge_source')
        
        return (
            f"[Layer 0 - Crystallized Grain Response]\n"
            f"Grain ID: {grain_id}\n"
            f"Fact ID: {fact_id}\n"
            f"Cartridge: {cartridge}\n"
            f"Confidence: {confidence:.4f}\n"
            f"(From crystallized knowledge at high confidence)"
        )
    
    def print_statistics(self) -> None:
        """Print query processing statistics."""
        print("\n" + "="*70)
        print("LAYER 0 QUERY STATISTICS")
        print("="*70)
        print(f"Total queries: {self.query_count}")
        print(f"Layer 0 direct hits: {self.layer0_hits}")
        print(f"Layer 0 hints (escalated): {self.layer0_escalations}")
        
        if self.query_count > 0:
            hit_rate = (self.layer0_hits / self.query_count) * 100
            print(f"Direct hit rate: {hit_rate:.1f}%")
            
            avg_latency = self.total_latency / self.query_count
            print(f"Average latency: {avg_latency:.2f}ms")
        
        print("="*70 + "\n")


# Testing and demonstration
if __name__ == "__main__":
    print("Initializing Layer 0 Query Processor...")
    processor = Layer0QueryProcessor('./cartridges')
    
    print(f"✓ Initialized with {processor.grain_router.total_grains} grains")
    
    # Test queries
    test_queries = [
        "Tell me about fact 1",
        "What is fact_id 42?",
        "energy metabolism",
        "physics",
        "Can you explain something?",
    ]
    
    print("\nTesting Layer 0 query processing:")
    print("="*70)
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        
        result = processor.process_query(query)
        
        print(f"Layer: {result['layer']}")
        print(f"Latency: {result['latency_ms']:.2f}ms")
        
        if result['layer'] == 'GRAIN':
            print(f"✓ Direct answer from grain {result['grain_id']}")
            print(f"  Confidence: {result['confidence']:.4f}")
            print(f"  Cartridge: {result['cartridge']}")
        elif result['layer'] == 'GRAIN_HINT':
            print(f"→ Grain hint provided for Layer 1+")
            print(f"  Grain confidence: {result['grain_confidence']:.4f}")
        else:
            print(f"→ No grain match, escalate to Layer 1+")
    
    print("\n" + "="*70)
    processor.print_statistics()
    
    print("✓ Layer 0 Query Processor ready for integration")
