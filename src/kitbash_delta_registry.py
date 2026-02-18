"""
Delta Registry: Tracks query statistics over time.
Used by Shannon Grain crystallization to detect patterns.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Set, List, Tuple
from collections import defaultdict
import json
from pathlib import Path


@dataclass
class QueryStatistics:
    """Statistics for a single fact_id over time."""
    fact_id: int
    cartridge_name: str
    hit_count: int = 0           # How many times queried
    total_confidence: float = 0.0 # Sum of confidences
    first_hit_cycle: int = 0
    last_hit_cycle: int = 0
    cycles_active: int = 0        # How many cycles had hits


class DeltaRegistry:
    """
    Tracks query hits over time. Feeds phantom tracking.
    """
    
    def __init__(self, storage_path: str = "./registry"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
        # Current cycle
        self.current_cycle = 0
        
        # fact_id -> QueryStatistics
        self.fact_stats: Dict[int, QueryStatistics] = {}
        
        # Track hits in current cycle
        self.current_cycle_hits: List[Tuple[int, float]] = []
    
    def record_hit(self, fact_id: int, cartridge_name: str, confidence: float):
        """
        Record that a fact was retrieved.
        
        Args:
            fact_id: ID of the fact
            cartridge_name: Which cartridge it came from
            confidence: Confidence of the hit (0-1)
        """
        # Create or update stats
        if fact_id not in self.fact_stats:
            self.fact_stats[fact_id] = QueryStatistics(
                fact_id=fact_id,
                cartridge_name=cartridge_name
            )
        
        stats = self.fact_stats[fact_id]
        stats.hit_count += 1
        stats.total_confidence += confidence
        stats.last_hit_cycle = self.current_cycle
        
        if stats.first_hit_cycle == 0:
            stats.first_hit_cycle = self.current_cycle
        
        # Track for current cycle
        self.current_cycle_hits.append((fact_id, confidence))
    
    def advance_cycle(self):
        """
        Move to next cycle (e.g., end of query batch or hour).
        Updates active cycle count.
        """
        for fact_id, conf in self.current_cycle_hits:
            if fact_id in self.fact_stats:
                self.fact_stats[fact_id].cycles_active += 1
        
        self.current_cycle += 1
        self.current_cycle_hits = []
    
    def get_fact_stats(self, fact_id: int) -> QueryStatistics:
        """Get statistics for a fact."""
        return self.fact_stats.get(fact_id)
    
    def get_hot_facts(self, top_k: int = 20) -> List[QueryStatistics]:
        """Get the K most frequently hit facts."""
        sorted_facts = sorted(
            self.fact_stats.values(),
            key=lambda s: s.hit_count,
            reverse=True
        )
        return sorted_facts[:top_k]
    
    def get_average_confidence(self, fact_id: int) -> float:
        """Get average confidence for a fact across all hits."""
        stats = self.fact_stats.get(fact_id)
        if not stats or stats.hit_count == 0:
            return 0.0
        return stats.total_confidence / stats.hit_count
    
    def save(self):
        """Persist registry to disk."""
        data = {
            'current_cycle': self.current_cycle,
            'facts': {
                str(fid): asdict(stats) 
                for fid, stats in self.fact_stats.items()
            }
        }
        registry_file = self.storage_path / "delta_registry.json"
        with open(registry_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load(self):
        """Load registry from disk."""
        registry_file = self.storage_path / "delta_registry.json"
        if not registry_file.exists():
            return
        
        with open(registry_file, 'r') as f:
            data = json.load(f)
        
        self.current_cycle = data['current_cycle']
        for fid_str, stats_dict in data['facts'].items():
            fact_id = int(fid_str)
            stats = QueryStatistics(**stats_dict)
            self.fact_stats[fact_id] = stats


# Example usage
if __name__ == "__main__":
    registry = DeltaRegistry()
    
    # Simulate query hits
    for cycle in range(10):
        # Simulate some queries
        registry.record_hit(1, "physics", 0.95)
        registry.record_hit(2, "physics", 0.90)
        registry.record_hit(1, "physics", 0.92)  # Repeat
        registry.record_hit(5, "chemistry", 0.87)
        registry.record_hit(8, "biology", 0.91)
        registry.record_hit(2, "physics", 0.89)  # Another repeat
        
        registry.advance_cycle()
    
    # Check what we recorded
    print("Hot facts:")
    for stats in registry.get_hot_facts(10):
        avg_conf = registry.get_average_confidence(stats.fact_id)
        print(f"  Fact {stats.fact_id}: {stats.hit_count} hits, "
              f"avg conf={avg_conf:.2f}, cycles_active={stats.cycles_active}")
    
    # Save for later use
    registry.save()
    print("\n✓ Registry saved")
