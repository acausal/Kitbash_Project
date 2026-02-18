"""
Shannon Grain Core Implementation
Phase 2A: Grain crystallization from persistent phantoms

Components:
- PhantomCandidate: Persistent query patterns (5+ hits, high confidence)
- HarmonicLock: Pattern stability detection (50+ cycles)
- GrainMetadata: Grain structure (ternary weights + axiom links)
- GrainRegistry: Persistence + indexing for crystallized grains
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum
import statistics


# ============================================================================
# ENUMS & TYPES
# ============================================================================

class EpistemicLevel(Enum):
    """Knowledge hierarchy levels from spec"""
    L0_EMPIRICAL = 0    # Physics, logic, math (immutable)
    L1_NARRATIVE = 1    # World facts, history (append-only)
    L2_AXIOMATIC = 2    # Behavioral rules, identity (metabolic)
    L3_PERSONA = 3      # Beliefs, dialogue, noise (ephemeral)


class GrainState(Enum):
    """Grain lifecycle state"""
    CANDIDATE = "candidate"      # Phantom considered for crystallization
    LOCKED = "locked"            # Harmonic lock detected, ready to crystallize
    CRYSTALLIZED = "crystallized" # Formally converted to grain
    ACTIVE = "active"            # Loaded in L3 cache
    ARCHIVED = "archived"        # Stored but not active


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class PhantomCandidate:
    """
    A query pattern that appears persistently.
    Becomes a grain candidate when locked (50+ cycles, high consistency).
    """
    phantom_id: str           # Unique identifier
    fact_ids: Set[int]        # Which facts are queried together
    cartridge_id: str         # Source cartridge
    hit_count: int = 0        # Total hits this cycle
    hit_history: List[int] = field(default_factory=list)  # Hits per cycle
    confidence_scores: List[float] = field(default_factory=list)
    query_concepts: List[str] = field(default_factory=list)
    
    # Cycle tracking
    first_cycle_seen: int = 0
    last_cycle_seen: int = 0
    cycle_consistency: float = 0.0    # Stability metric (0-1)
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Status
    status: str = "transient"  # transient, persistent, locked
    epistemic_level: EpistemicLevel = EpistemicLevel.L2_AXIOMATIC
    
    def avg_confidence(self) -> float:
        """Average confidence across all hits"""
        if not self.confidence_scores:
            return 0.0
        return statistics.mean(self.confidence_scores)
    
    def is_persistent(self, min_hits: int = 5, min_confidence: float = 0.75) -> bool:
        """Check if phantom meets persistence criteria"""
        return (self.hit_count >= min_hits and 
                self.avg_confidence() >= min_confidence)
    
    def is_locked(self, min_cycles: int = 50, min_consistency: float = 0.8) -> bool:
        """Check if phantom has achieved harmonic lock"""
        cycles_stable = len(self.hit_history) >= min_cycles
        consistency_high = self.cycle_consistency >= min_consistency
        return cycles_stable and consistency_high
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "phantom_id": self.phantom_id,
            "fact_ids": list(self.fact_ids),
            "cartridge_id": self.cartridge_id,
            "hit_count": self.hit_count,
            "hit_history": self.hit_history[-50:],  # Last 50 cycles only
            "avg_confidence": self.avg_confidence(),
            "query_concepts": self.query_concepts,
            "cycles_stable": len(self.hit_history),
            "cycle_consistency": round(self.cycle_consistency, 4),
            "status": self.status,
            "epistemic_level": self.epistemic_level.name,
        }


@dataclass
class GrainMetadata:
    """
    A crystallized grain: compressed representation of a persistent pattern.
    Stores ternary weights instead of full embeddings (90% size reduction).
    """
    grain_id: str                     # Unique identifier
    source_phantom_id: str            # Which phantom crystallized into this
    cartridge_id: str                 # Source cartridge
    
    # Ternary representation
    num_bits: int = 256               # Bit-sliced representation size
    bits_positive: int = 0            # Count of +1 weights
    bits_negative: int = 0            # Count of -1 weights
    bits_void: int = 0                # Count of 0 (unset) weights
    
    # Axiom linkage (points to which rules this validates)
    axiom_ids: List[str] = field(default_factory=list)
    evidence_hash: str = ""           # SHA-256 of supporting observations
    
    # Quality metrics
    internal_hamming: float = 0.0     # Avg distance between cluster members
    weight_skew: float = 0.0          # Std dev / mean of weights
    avg_confidence: float = 0.0       # Avg confidence of source observations
    observation_count: int = 0        # How many observations formed this
    
    # Lifecycle
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    crystallized_at: str = ""
    state: GrainState = GrainState.CANDIDATE
    epistemic_level: EpistemicLevel = EpistemicLevel.L2_AXIOMATIC
    
    # Cache
    bit_array_plus: bytes = b""       # Actual bit array for +1 weights
    bit_array_minus: bytes = b""      # Actual bit array for -1 weights
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "grain_id": self.grain_id,
            "source_phantom_id": self.source_phantom_id,
            "cartridge_id": self.cartridge_id,
            "num_bits": self.num_bits,
            "weight_distribution": {
                "positive": self.bits_positive,
                "negative": self.bits_negative,
                "void": self.bits_void,
            },
            "axiom_ids": self.axiom_ids,
            "quality_metrics": {
                "internal_hamming": round(self.internal_hamming, 3),
                "weight_skew": round(self.weight_skew, 3),
                "avg_confidence": round(self.avg_confidence, 3),
                "observation_count": self.observation_count,
            },
            "state": self.state.value,
            "epistemic_level": self.epistemic_level.name,
            "size_bytes": len(self.bit_array_plus) + len(self.bit_array_minus),
        }
    
    def size_mb(self) -> float:
        """Size in megabytes"""
        return (len(self.bit_array_plus) + len(self.bit_array_minus)) / (1024 * 1024)


# ============================================================================
# PHANTOM TRACKING (Extension to DeltaRegistry)
# ============================================================================

class PhantomTracker:
    """
    Tracks persistent query patterns and detects harmonic lock.
    Integrates with DeltaRegistry to identify crystallization candidates.
    """
    
    def __init__(self, cartridge_id: str, 
                 persistence_threshold: int = 5,
                 confidence_threshold: float = 0.75,
                 harmonic_lock_cycles: int = 50):
        """Initialize phantom tracker."""
        self.cartridge_id = cartridge_id
        self.persistence_threshold = persistence_threshold
        self.confidence_threshold = confidence_threshold
        self.harmonic_lock_cycles = harmonic_lock_cycles
        
        # Phantom storage
        self.phantoms: Dict[str, PhantomCandidate] = {}
        self.cycle_count = 0
        
        # Stats
        self.total_hits = 0
    
    def record_phantom_hit(self, fact_ids: Set[int], concepts: List[str],
                          confidence: float, epistemic_level: EpistemicLevel = EpistemicLevel.L2_AXIOMATIC) -> None:
        """
        Record a phantom hit (called when facts are accessed together).
        
        Args:
            fact_ids: Set of fact IDs accessed in this query
            concepts: Query concepts
            confidence: Confidence in the match
            epistemic_level: Which epistemic level this fact belongs to
        """
        # Create phantom key from sorted fact IDs
        phantom_key = "|".join(str(f) for f in sorted(fact_ids))
        
        # Create or update phantom
        if phantom_key not in self.phantoms:
            phantom_id = hashlib.sha256(phantom_key.encode()).hexdigest()[:16]
            self.phantoms[phantom_key] = PhantomCandidate(
                phantom_id=phantom_id,
                fact_ids=fact_ids,
                cartridge_id=self.cartridge_id,
                first_cycle_seen=self.cycle_count,
                epistemic_level=epistemic_level,
            )
        
        phantom = self.phantoms[phantom_key]
        phantom.hit_count += 1
        phantom.confidence_scores.append(confidence)
        phantom.query_concepts.extend(concepts)
        phantom.last_cycle_seen = self.cycle_count
        
        self.total_hits += 1
        
        # Update status
        self._update_phantom_status(phantom)
    
    def _update_phantom_status(self, phantom: PhantomCandidate) -> None:
        """Update phantom status based on hits and consistency"""
        if phantom.hit_count >= self.persistence_threshold:
            avg_conf = statistics.mean(phantom.confidence_scores)
            if avg_conf >= self.confidence_threshold:
                phantom.status = "persistent"
            else:
                phantom.status = "transient"
        else:
            phantom.status = "transient"
    
    def advance_cycle(self) -> None:
        """
        Advance to next metabolic cycle.
        Detects harmonic locks and records cycle history.
        """
        self.cycle_count += 1
        
        # Record hit counts and detect locks
        for phantom in self.phantoms.values():
            if phantom.status == "persistent":
                phantom.hit_history.append(phantom.hit_count)
                self._check_harmonic_lock(phantom)
            
            # Reset for next cycle
            phantom.hit_count = 0
    
    def _check_harmonic_lock(self, phantom: PhantomCandidate) -> None:
        """
        Detect harmonic lock (pattern is stable over many cycles).
        Lock = pattern appears consistently for 50+ cycles.
        """
        if len(phantom.hit_history) < self.harmonic_lock_cycles:
            return  # Not enough cycles yet
        
        # Check last 50 cycles for consistency
        recent = phantom.hit_history[-self.harmonic_lock_cycles:]
        
        # Calculate consistency (low variance = high consistency)
        try:
            hit_variance = statistics.variance(recent)
            # Normalize: lower variance = higher consistency
            hit_consistency = 1.0 - min(hit_variance / 10.0, 1.0)
        except:
            hit_consistency = 0.0
        
        # Calculate confidence consistency
        confidence_consistency = 1.0 - min(statistics.variance(phantom.confidence_scores) / 0.25, 1.0) \
            if len(phantom.confidence_scores) > 1 else 0.0
        
        # Harmonic lock achieved if both are consistent
        overall_consistency = (hit_consistency + confidence_consistency) / 2.0
        phantom.cycle_consistency = overall_consistency
        
        if hit_consistency > 0.8 and confidence_consistency > 0.8:
            phantom.status = "locked"
    
    def get_persistent_phantoms(self) -> List[PhantomCandidate]:
        """Get all persistent phantoms (5+ hits, high confidence)"""
        return [p for p in self.phantoms.values() if p.status == "persistent"]
    
    def get_locked_phantoms(self) -> List[PhantomCandidate]:
        """Get all locked phantoms (ready for crystallization)"""
        return [p for p in self.phantoms.values() if p.status == "locked"]
    
    def get_stats(self) -> Dict:
        """Get tracker statistics"""
        persistent = self.get_persistent_phantoms()
        locked = self.get_locked_phantoms()
        
        return {
            "cartridge_id": self.cartridge_id,
            "cycle_count": self.cycle_count,
            "total_hits": self.total_hits,
            "total_phantoms": len(self.phantoms),
            "persistent_count": len(persistent),
            "locked_count": len(locked),
            "crystallization_ready": len(locked),
            "avg_phantom_hits": statistics.mean([p.hit_count for p in self.phantoms.values()]) if self.phantoms else 0,
        }
    
    def save(self, filepath: str) -> None:
        """Save phantom tracker to JSON"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "cartridge_id": self.cartridge_id,
            "cycle_count": self.cycle_count,
            "total_hits": self.total_hits,
            "phantoms": {
                key: phantom.to_dict()
                for key, phantom in self.phantoms.items()
            },
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, filepath: str) -> "PhantomTracker":
        """Load phantom tracker from JSON"""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        with open(path) as f:
            data = json.load(f)
        
        tracker = cls(data["cartridge_id"])
        tracker.cycle_count = data.get("cycle_count", 0)
        tracker.total_hits = data.get("total_hits", 0)
        
        # Note: Reloading loses exact phantom objects, would need more elaborate deserialization
        # For now, just reconstruct basic stats
        return tracker


# ============================================================================
# GRAIN REGISTRY
# ============================================================================

class GrainRegistry:
    """
    Centralized registry of crystallized grains.
    Manages grain storage, lookup, and lifecycle.
    """
    
    def __init__(self, cartridge_id: str, storage_path: str = "./grains"):
        """Initialize grain registry"""
        self.cartridge_id = cartridge_id
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory grain index
        self.grains: Dict[str, GrainMetadata] = {}
        self.grain_state_index: Dict[GrainState, Set[str]] = {
            state: set() for state in GrainState
        }
    
    def add_grain(self, grain: GrainMetadata) -> None:
        """Add a grain to the registry"""
        self.grains[grain.grain_id] = grain
        self.grain_state_index[grain.state].add(grain.grain_id)
    
    def update_grain_state(self, grain_id: str, new_state: GrainState) -> None:
        """Update grain state (e.g., CANDIDATE → CRYSTALLIZED)"""
        if grain_id not in self.grains:
            raise KeyError(f"Grain not found: {grain_id}")
        
        grain = self.grains[grain_id]
        old_state = grain.state
        
        # Remove from old state index
        self.grain_state_index[old_state].discard(grain_id)
        
        # Update and re-index
        grain.state = new_state
        self.grain_state_index[new_state].add(grain_id)
    
    def get_grains_by_state(self, state: GrainState) -> List[GrainMetadata]:
        """Get all grains in a specific state"""
        grain_ids = self.grain_state_index[state]
        return [self.grains[gid] for gid in grain_ids]
    
    def get_active_grains(self) -> List[GrainMetadata]:
        """Get all active grains (in L3 cache)"""
        return self.get_grains_by_state(GrainState.ACTIVE)
    
    def get_crystallized_grains(self) -> List[GrainMetadata]:
        """Get all crystallized grains"""
        active = set(g.grain_id for g in self.get_grains_by_state(GrainState.ACTIVE))
        crystallized = self.get_grains_by_state(GrainState.CRYSTALLIZED)
        return crystallized + [self.grains[gid] for gid in active if gid not in active]
    
    def save_grain(self, grain: GrainMetadata) -> Path:
        """Save a grain to disk"""
        grain_path = self.storage_path / f"{grain.grain_id}.json"
        
        # Save metadata (bits stored separately)
        metadata = grain.to_dict()
        with open(grain_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Save bit arrays if present
        if grain.bit_array_plus:
            bits_plus_path = self.storage_path / f"{grain.grain_id}.plus.bin"
            with open(bits_plus_path, 'wb') as f:
                f.write(grain.bit_array_plus)
        
        if grain.bit_array_minus:
            bits_minus_path = self.storage_path / f"{grain.grain_id}.minus.bin"
            with open(bits_minus_path, 'wb') as f:
                f.write(grain.bit_array_minus)
        
        return grain_path
    
    def get_stats(self) -> Dict:
        """Get registry statistics"""
        return {
            "cartridge_id": self.cartridge_id,
            "total_grains": len(self.grains),
            "by_state": {
                state.value: len(grain_ids)
                for state, grain_ids in self.grain_state_index.items()
            },
            "total_storage_mb": sum(g.size_mb() for g in self.grains.values()),
            "avg_grain_size_bytes": statistics.mean([len(g.bit_array_plus) + len(g.bit_array_minus) 
                                                      for g in self.grains.values()]) if self.grains else 0,
        }


if __name__ == "__main__":
    # Example usage
    print("Shannon Grain Core Module")
    print("\nPhantom Tracking Example:")
    
    tracker = PhantomTracker("test_cartridge")
    
    # Simulate some phantom hits
    for cycle in range(5):
        for i in range(3):
            tracker.record_phantom_hit(
                fact_ids={1, 2, 3},
                concepts=["test", "example"],
                confidence=0.85 + (i * 0.05)
            )
        tracker.advance_cycle()
        print(f"  Cycle {cycle + 1}: {tracker.get_stats()}")
    
    print(f"\nPersistent phantoms: {len(tracker.get_persistent_phantoms())}")
    print(f"Locked phantoms: {len(tracker.get_locked_phantoms())}")
    
    print("\nGrain Registry Example:")
    registry = GrainRegistry("test_cartridge")
    
    grain = GrainMetadata(
        grain_id="grain_001",
        source_phantom_id="phantom_001",
        cartridge_id="test_cartridge",
    )
    registry.add_grain(grain)
    print(f"Registry stats: {registry.get_stats()}")
