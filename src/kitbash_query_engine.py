"""
Query Engine for Cartridges
Provides a unified interface to query cartridges and return hits.
"""

import json
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional
from kitbash_cartridge import Cartridge


class QueryResult:
    """Result of a query against a cartridge."""
    
    def __init__(self, query_text: str, fact_ids: Set[int], 
                 confidences: Dict[int, float], source: str = ""):
        self.query_text = query_text
        self.fact_ids = fact_ids
        self.confidences = confidences  # fact_id -> confidence
        self.source = source
        self.avg_confidence = (
            sum(confidences.values()) / len(confidences) 
            if confidences else 0.0
        )
    
    def __repr__(self):
        return f"QueryResult(query='{self.query_text}', hits={len(self.fact_ids)}, confidence={self.avg_confidence:.2f})"


class CartridgeQueryEngine:
    """
    Query engine for multiple cartridges.
    Uses the built-in Cartridge.query() method for keyword search.
    """
    
    def __init__(self, cartridge_dir: str = "./cartridges"):
        self.cartridge_dir = Path(cartridge_dir)
        self.cartridges: Dict[str, Cartridge] = {}
        self.load_all_cartridges()
    
    def load_all_cartridges(self):
        """Load all .kbc directories as cartridges."""
        if not self.cartridge_dir.exists():
            print(f"Cartridge directory not found: {self.cartridge_dir}")
            return
        
        for kbc_path in self.cartridge_dir.glob("*.kbc"):
            cart_name = kbc_path.stem
            try:
                cart = Cartridge(cart_name, str(self.cartridge_dir))
                cart.load()
                # Get fact count from metadata
                fact_count = cart.metadata.get('health', {}).get('fact_count', 0)
                self.cartridges[cart_name] = cart
                print(f"[OK] Loaded cartridge: {cart_name} ({fact_count} facts)")
            except Exception as e:
                print(f"[FAIL] {cart_name}: {e}")
    
    def keyword_query(self, query_text: str, cartridge_name: str = None) -> QueryResult:
        """
        Query using Cartridge.query() method across facts.
        
        Args:
            query_text: Words to search for (space-separated)
            cartridge_name: Specific cartridge, or None to search all
        
        Returns:
            QueryResult with matching fact IDs and confidences
        """
        matching_facts = {}
        
        # Search specified cartridge or all
        carts_to_search = (
            {cartridge_name: self.cartridges[cartridge_name]} 
            if cartridge_name and cartridge_name in self.cartridges
            else self.cartridges
        )
        
        for cart_name, cart in carts_to_search.items():
            # Use Cartridge's built-in query method
            fact_ids = cart.query(query_text, log_access=True)
            
            # Get confidence for each result fact
            for fact_id in fact_ids:
                if fact_id in cart.annotations:
                    # annotations[fact_id] is an AnnotationMetadata object
                    confidence = cart.annotations[fact_id].confidence
                else:
                    confidence = 0.8
                
                matching_facts[fact_id] = confidence
        
        return QueryResult(query_text, set(matching_facts.keys()), 
                          matching_facts, cartridge_name or "all")
    
    def get_fact(self, fact_id: int, cartridge_name: str) -> Optional[str]:
        """Retrieve a single fact by ID."""
        if cartridge_name not in self.cartridges:
            return None
        return self.cartridges[cartridge_name].get_fact(fact_id)
    
    def get_fact_confidence(self, fact_id: int, cartridge_name: str) -> float:
        """Get confidence for a fact."""
        if cartridge_name not in self.cartridges:
            return 0.0
        cart = self.cartridges[cartridge_name]
        if fact_id in cart.annotations:
            return cart.annotations[fact_id].confidence
        return 0.8
    
    def get_cartridge_stats(self) -> Dict[str, int]:
        """Get fact count for each loaded cartridge."""
        stats = {}
        for cart_name, cart in self.cartridges.items():
            fact_count = cart.metadata.get('health', {}).get('fact_count', 0)
            stats[cart_name] = fact_count
        return stats


# Example usage
if __name__ == "__main__":
    engine = CartridgeQueryEngine("./cartridges")
    
    # Test queries
    queries = [
        "force acceleration motion",
        "DNA genes protein",
        "energy heat temperature",
        "logic reasoning truth",
    ]
    
    for query in queries:
        result = engine.keyword_query(query)
        print(f"\nQuery: {result.query_text}")
        print(f"Hits: {len(result.fact_ids)}, Avg Confidence: {result.avg_confidence:.2f}")
