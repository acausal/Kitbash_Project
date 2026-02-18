"""
Grain Activation - Load crystallized grains into L3 cache for reflex path
Phase 2A: Sub-0.5ms ternary weight lookup via bit-sliced operations

Purpose: Make grain lookups fast enough for reflex response (<0.5ms).

Strategy:
- Load active grains into L3 cache
- Use bit-sliced ternary operations (XOR + POPCOUNT)
- Implement fast lookup with context switching via hat masks
"""

import time
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from shannon_grain import GrainMetadata, GrainState


# ============================================================================
# HAT CONTEXT SYSTEM
# ============================================================================

class Hat(Enum):
    """Behavioral context/persona modes"""
    ANALYTICAL = "analytical"      # Logical, precise
    CREATIVE = "creative"          # Imaginative, exploratory
    EMPATHETIC = "empathetic"      # Social, relationship-focused
    DELIBERATIVE = "deliberative"  # Thoughtful, careful
    NEUTRAL = "neutral"            # Default, balanced


@dataclass
class HatContext:
    """Context mask for instant grain reinterpretation"""
    hat_name: Hat
    xor_mask: bytes      # 256-bit XOR mask
    description: str = ""
    
    def apply(self, bits: bytes) -> bytes:
        """Apply XOR mask to bits for context switching"""
        if len(bits) != len(self.xor_mask):
            raise ValueError(f"Bit length mismatch: {len(bits)} vs {len(self.xor_mask)}")
        
        # XOR each byte
        result = bytearray(len(bits))
        for i in range(len(bits)):
            result[i] = bits[i] ^ self.xor_mask[i]
        
        return bytes(result)


class HatRegistry:
    """Manages available hats and their context masks"""
    
    def __init__(self):
        """Initialize with default hats"""
        self.hats: Dict[Hat, HatContext] = {}
        self.current_hat = Hat.NEUTRAL
        
        # Create default hat masks (would be learned in real system)
        self._init_default_hats()
    
    def _init_default_hats(self) -> None:
        """Initialize default hat contexts with synthetic masks"""
        # Each hat gets a different XOR mask (32 bytes = 256 bits)
        
        hat_seeds = {
            Hat.ANALYTICAL: b"analytical_context_mask_seed_001",
            Hat.CREATIVE: b"creative_context_mask_seed_00002",
            Hat.EMPATHETIC: b"empathetic_context_mask_seed_003",
            Hat.DELIBERATIVE: b"deliberative_context_mask_seed_04",
            Hat.NEUTRAL: b"neutral_context_mask_seed_00005",
        }
        
        for hat, seed in hat_seeds.items():
            # Expand seed to 32 bytes (256 bits)
            mask_hash = hashlib.sha256(seed).digest()
            # Use first 32 bytes (sha256 gives exactly 32 bytes)
            
            self.hats[hat] = HatContext(
                hat_name=hat,
                xor_mask=mask_hash,
                description=f"Context mask for {hat.value} mode"
            )
    
    def set_current_hat(self, hat: Hat) -> None:
        """Switch to a different hat"""
        if hat not in self.hats:
            raise ValueError(f"Hat not found: {hat.value}")
        self.current_hat = hat
    
    def get_current_context(self) -> HatContext:
        """Get current hat context"""
        return self.hats[self.current_hat]


# ============================================================================
# TERNARY LOOKUP ENGINE
# ============================================================================

@dataclass
class TernaryLookupResult:
    """Result of ternary weight lookup"""
    grain_id: str
    popcount_positive: int      # Count of +1 weights
    popcount_negative: int      # Count of -1 weights
    ternary_value: float        # (+1 count - -1 count) / total
    confidence: float           # Confidence in this result
    latency_ms: float          # Lookup time
    context_hat: Hat           # Which context was used


class TernaryLookupEngine:
    """
    Fast ternary weight lookup using bit-sliced operations.
    
    Algorithm:
    1. Get grain's bit arrays (+ and -)
    2. Apply hat context XOR mask
    3. Count set bits (popcount)
    4. Compute ternary value
    
    Target: <0.5ms per lookup
    """
    
    def __init__(self, hat_registry: HatRegistry):
        """Initialize lookup engine with hat context"""
        self.hat_registry = hat_registry
    
    def lookup(self, grain: GrainMetadata, 
               apply_context: bool = True) -> TernaryLookupResult:
        """
        Perform ternary lookup for a grain.
        
        Args:
            grain: Grain to lookup
            apply_context: Whether to apply hat context XOR
            
        Returns:
            TernaryLookupResult with latency measurement
        """
        start_time = time.perf_counter()
        
        # Get bit arrays
        bits_pos = grain.bit_array_plus
        bits_neg = grain.bit_array_minus
        
        # Apply context if requested
        if apply_context:
            context = self.hat_registry.get_current_context()
            bits_pos = context.apply(bits_pos)
            bits_neg = context.apply(bits_neg)
            current_hat = context.hat_name
        else:
            current_hat = Hat.NEUTRAL
        
        # Count set bits (popcount)
        popcount_pos = self._popcount_bytes(bits_pos)
        popcount_neg = self._popcount_bytes(bits_neg)
        
        # Compute ternary value
        total_set = popcount_pos + popcount_neg
        if total_set == 0:
            ternary_value = 0.0
            confidence = 0.0
        else:
            ternary_value = (popcount_pos - popcount_neg) / total_set
            # Confidence = how "strong" the signal is
            # (high popcount = strong, low = weak)
            confidence = min(1.0, total_set / grain.num_bits)
        
        elapsed = (time.perf_counter() - start_time) * 1000  # Convert to ms
        
        return TernaryLookupResult(
            grain_id=grain.grain_id,
            popcount_positive=popcount_pos,
            popcount_negative=popcount_neg,
            ternary_value=ternary_value,
            confidence=confidence,
            latency_ms=elapsed,
            context_hat=current_hat,
        )
    
    @staticmethod
    def _popcount_bytes(data: bytes) -> int:
        """Count number of set bits in byte array"""
        count = 0
        for byte in data:
            # Count bits set in this byte
            b = byte
            while b:
                count += b & 1
                b >>= 1
        return count


# ============================================================================
# L3 CACHE ACTIVATION
# ============================================================================

class GrainL3Cache:
    """
    In-memory L3 cache for active grains.
    Keeps hot grains loaded for fast reflex lookups.
    
    Capacity: Target ~1MB (can hold ~1000 grains at 250 bytes each)
    """
    
    def __init__(self, max_size_mb: float = 1.0):
        """
        Initialize L3 cache.
        
        Args:
            max_size_mb: Maximum cache size in MB
        """
        self.max_size_mb = max_size_mb
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        
        # Cache storage
        self.cached_grains: Dict[str, GrainMetadata] = {}
        self.current_size_bytes = 0
        
        # Stats
        self.hits = 0
        self.misses = 0
        self.evictions = 0
    
    def load_grain(self, grain: GrainMetadata) -> bool:
        """
        Load a grain into cache.
        
        Returns:
            True if loaded successfully, False if cache full and no eviction possible
        """
        grain_size = len(grain.bit_array_plus) + len(grain.bit_array_minus)
        
        # Check if already cached
        if grain.grain_id in self.cached_grains:
            return True
        
        # Check if adding exceeds capacity
        if self.current_size_bytes + grain_size > self.max_size_bytes:
            # Try to evict least recently used
            if not self._evict_lru(grain_size):
                return False
        
        # Add to cache
        self.cached_grains[grain.grain_id] = grain
        self.current_size_bytes += grain_size
        
        return True
    
    def get_grain(self, grain_id: str) -> Optional[GrainMetadata]:
        """
        Retrieve grain from cache.
        
        Returns:
            Grain if cached, None otherwise
        """
        if grain_id in self.cached_grains:
            self.hits += 1
            return self.cached_grains[grain_id]
        
        self.misses += 1
        return None
    
    def _evict_lru(self, needed_bytes: int) -> bool:
        """
        Evict least recently used grain(s) to make space.
        
        Simple strategy: evict grains in order until enough space.
        """
        freed = 0
        evicted = []
        
        for grain_id in list(self.cached_grains.keys()):
            grain = self.cached_grains[grain_id]
            grain_size = len(grain.bit_array_plus) + len(grain.bit_array_minus)
            
            freed += grain_size
            evicted.append(grain_id)
            self.evictions += len(evicted)
            
            if freed >= needed_bytes:
                break
        
        # Remove evicted grains
        for grain_id in evicted:
            del self.cached_grains[grain_id]
            grain = self.cached_grains.get(grain_id)
            if grain:
                self.current_size_bytes -= len(grain.bit_array_plus) + len(grain.bit_array_minus)
        
        return freed >= needed_bytes
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "cached_grains": len(self.cached_grains),
            "current_size_mb": round(self.current_size_bytes / (1024 * 1024), 2),
            "max_size_mb": self.max_size_mb,
            "utilization_percent": round(100 * self.current_size_bytes / self.max_size_bytes, 1),
            "hit_rate": round(self.hits / (self.hits + self.misses), 3) if (self.hits + self.misses) > 0 else 0,
            "total_hits": self.hits,
            "total_misses": self.misses,
            "evictions": self.evictions,
        }


# ============================================================================
# GRAIN ACTIVATION ORCHESTRATOR
# ============================================================================

class GrainActivation:
    """
    Orchestrate grain activation: load → cache → lookup.
    """
    
    def __init__(self, max_cache_mb: float = 1.0):
        """Initialize activation system"""
        self.hat_registry = HatRegistry()
        self.lookup_engine = TernaryLookupEngine(self.hat_registry)
        self.l3_cache = GrainL3Cache(max_cache_mb)
        
        # Activation stats
        self.total_lookups = 0
        self.successful_lookups = 0
    
    def activate_grains(self, grains: List[GrainMetadata]) -> Dict:
        """
        Activate multiple grains (load into cache).
        
        Returns:
            Status report
        """
        loaded = 0
        failed = 0
        
        for grain in grains:
            if self.l3_cache.load_grain(grain):
                loaded += 1
            else:
                failed += 1
        
        return {
            "total_requested": len(grains),
            "loaded": loaded,
            "failed": failed,
            "cache_stats": self.l3_cache.get_cache_stats(),
        }
    
    def lookup(self, grain_id: str, apply_context: bool = True) -> Optional[TernaryLookupResult]:
        """
        Perform ternary lookup for a grain.
        
        Returns:
            TernaryLookupResult if successful, None if grain not cached
        """
        self.total_lookups += 1
        
        # Check cache
        grain = self.l3_cache.get_grain(grain_id)
        if not grain:
            return None
        
        # Perform lookup
        result = self.lookup_engine.lookup(grain, apply_context)
        self.successful_lookups += 1
        
        return result
    
    def switch_context(self, hat: Hat) -> None:
        """Switch to a different behavioral context"""
        self.hat_registry.set_current_hat(hat)
    
    def get_stats(self) -> Dict:
        """Get activation statistics"""
        return {
            "total_lookups": self.total_lookups,
            "successful_lookups": self.successful_lookups,
            "lookup_success_rate": round(self.successful_lookups / self.total_lookups, 3) if self.total_lookups > 0 else 0,
            "cache": self.l3_cache.get_cache_stats(),
            "current_context": self.hat_registry.current_hat.value,
        }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print("Grain Activation Examples\n")
    
    # Create test grains
    grain1 = GrainMetadata(
        grain_id="grain_001",
        source_phantom_id="phantom_001",
        cartridge_id="test",
        num_bits=256,
        bits_positive=77,
        bits_negative=51,
        bit_array_plus=b"\xFF" * 32,  # All bits set for demo
        bit_array_minus=b"\x00" * 32,
    )
    grain1.state = GrainState.ACTIVE
    
    # Initialize activation system
    print("1. Initializing Grain Activation System")
    activation = GrainActivation(max_cache_mb=1.0)
    
    # Activate grains
    print(f"\n2. Activating grain: {grain1.grain_id}")
    activation_result = activation.activate_grains([grain1])
    print(f"   Loaded: {activation_result['loaded']}")
    print(f"   Cache utilization: {activation_result['cache_stats']['utilization_percent']}%")
    
    # Perform lookups
    print(f"\n3. Performing ternary lookups")
    for hat in [Hat.NEUTRAL, Hat.ANALYTICAL, Hat.CREATIVE]:
        activation.switch_context(hat)
        result = activation.lookup(grain1.grain_id)
        
        if result:
            print(f"   Context: {hat.value}")
            print(f"     Popcount(+): {result.popcount_positive}, Popcount(-): {result.popcount_negative}")
            print(f"     Ternary value: {result.ternary_value:.3f}, Confidence: {result.confidence:.3f}")
            print(f"     Latency: {result.latency_ms:.4f}ms")
    
    # Final stats
    print(f"\n4. Activation System Statistics")
    stats = activation.get_stats()
    print(f"   Total lookups: {stats['total_lookups']}")
    print(f"   Successful: {stats['successful_lookups']}")
    print(f"   Success rate: {stats['lookup_success_rate']:.1%}")
    print(f"   Cache hit rate: {stats['cache']['hit_rate']:.1%}")
