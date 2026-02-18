"""
Kitbash Redis Schema
Fast cache layer for reflex path - CMS resonance, grain lookups, ghost signals

The Redis layer is the "L3 cache" for the system:
- CMS (Cache Management System): Tracks query resonance with time decay
- Grain signatures: Pre-computed hashes for fast ternary lookup
- Ghost signals: High-resonance patterns ready to activate grains
- Metrics: Query statistics and performance tracking

All operations target <1ms latency for the reflex path.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
import hashlib
import json


# ============================================================================
# DATA STRUCTURES
# ============================================================================

class RedisNamespace(Enum):
    """Namespace prefixes for different data types."""
    CMS = "cms"          # Cache Management System (resonance)
    GRAIN = "grain"      # Grain signatures and lookups
    GHOST = "ghost"      # Ghost signals (speculative activation)
    HAT = "hat"          # Context/persona tracking
    METRICS = "metrics"  # Performance tracking


@dataclass
class CMSRecord:
    """Single CMS entry - tracks query resonance."""
    query_hash: str      # SHA256 of query
    access_count: int    # Total accesses
    last_accessed: str   # ISO timestamp
    resonance_score: float  # time-decayed relevance
    grain_ids: List[int]  # Associated grain IDs


@dataclass
class GrainSignature:
    """Cached grain metadata for fast lookup."""
    grain_id: int
    axiom_link: str      # Which axiom does this validate?
    popcount_signature: int  # For ternary matching
    weight: float        # Ternary weight (1.58-bit)
    last_accessed: str


# ============================================================================
# REDIS SCHEMA SPECIFICATION
# ============================================================================

class RedisSchemaSpec:
    """
    Complete Redis key-value schema for Kitbash reflex path.
    
    Design principles:
    - All operations O(1) or O(log N)
    - Memory budget: ~36MB for realistic load
    - TTL on most keys to prevent growth
    - Flat structure (avoid deep nesting)
    """
    
    # ========================================================================
    # CMS (CACHE MANAGEMENT SYSTEM) - Query Resonance
    # ========================================================================
    
    @staticmethod
    def cms_record_key(query_hash: str) -> str:
        """
        Key: cms:<query_hash>
        Value: JSON with access_count, last_accessed, resonance_score
        Type: STRING
        TTL: 86400s (24 hours)
        Size: ~500 bytes
        Access: GET/SET
        
        Used for: Query frequency tracking, speculative activation
        Example: cms:a1b2c3d4e5f6 → {"count": 47, "score": 0.87, ...}
        """
        return f"{RedisNamespace.CMS.value}:{query_hash}"
    
    @staticmethod
    def cms_grain_list_key(query_hash: str) -> str:
        """
        Key: cms:<query_hash>:grains
        Value: Sorted set of grain IDs by recency
        Type: ZSET (score = timestamp)
        TTL: 86400s
        Size: ~200 bytes
        Access: ZREVRANGE (get top 3)
        
        Used for: Fast grain activation on high-resonance queries
        Example: cms:a1b2c3d4e5f6:grains → {grain_1: 1707000000, grain_2: 1707000100}
        """
        return f"{RedisNamespace.CMS.value}:{query_hash}:grains"
    
    @staticmethod
    def cms_resonance_decay_key(query_hash: str) -> str:
        """
        Key: cms:<query_hash>:resonance
        Value: Counter that decays by 0.9 per cycle
        Type: FLOAT
        TTL: 432000s (5 days)
        Access: INCR / DECR / GETSET
        
        Used for: Exponential decay of query importance
        Formula: resonance = count * (0.9 ^ cycles_elapsed)
        Example: cms:a1b2c3d4e5f6:resonance → 0.726
        """
        return f"{RedisNamespace.CMS.value}:{query_hash}:resonance"
    
    # ========================================================================
    # GRAIN SIGNATURES - Fast Ternary Lookup
    # ========================================================================
    
    @staticmethod
    def grain_signature_key(grain_id: int) -> str:
        """
        Key: grain:<grain_id>:sig
        Value: JSON with popcount, axiom_link, weight
        Type: STRING
        TTL: None (permanent)
        Size: ~200 bytes
        Access: GET (single lookup)
        
        Used for: Fast ternary resolution in <0.5ms
        Example: grain:42:sig → {"popcount": 156, "axiom": "thermodynamics", "weight": 1.58}
        """
        return f"{RedisNamespace.GRAIN.value}:{grain_id}:sig"
    
    @staticmethod
    def grain_bits_plus_key(grain_id: int) -> str:
        """
        Key: grain:<grain_id>:bits:+
        Value: Bit array (binary string or hex)
        Type: STRING (binary)
        TTL: None
        Size: ~1KB per grain (256-bit fingerprint)
        Access: GET + bitwise operations (in application)
        
        Used for: Bimodal XOR during context switching
        Example: grain:42:bits:+ → "binary data..."
        """
        return f"{RedisNamespace.GRAIN.value}:{grain_id}:bits:+"
    
    @staticmethod
    def grain_bits_minus_key(grain_id: int) -> str:
        """
        Key: grain:<grain_id>:bits:-
        Value: Bit array (binary string or hex)
        Type: STRING (binary)
        TTL: None
        Size: ~1KB per grain
        Access: GET + XOR
        
        Used for: Negative weight bit-slicing
        Example: grain:42:bits:- → "binary data..."
        """
        return f"{RedisNamespace.GRAIN.value}:{grain_id}:bits:-"
    
    @staticmethod
    def grain_index_key() -> str:
        """
        Key: grain:index
        Value: Sorted set of all grain IDs by creation time
        Type: ZSET (score = timestamp)
        TTL: None
        Size: ~50 bytes per grain
        Access: ZRANGE / ZCARD (inventory)
        
        Used for: Grain inventory and lifecycle tracking
        Example: grain:index → {grain_1: 1706000000, grain_2: 1706000100, ...}
        """
        return f"{RedisNamespace.GRAIN.value}:index"
    
    # ========================================================================
    # GHOST SIGNALS - Speculative Activation
    # ========================================================================
    
    @staticmethod
    def ghost_signal_key(query_hash: str) -> str:
        """
        Key: ghost:<query_hash>
        Value: Top-3 grain IDs to warm (comma-separated)
        Type: STRING
        TTL: 3600s (1 hour)
        Size: ~50 bytes
        Access: GET (speculative load)
        
        Used for: L3 cache warming on high-resonance queries
        Example: ghost:a1b2c3d4e5f6 → "42,17,88"
        """
        return f"{RedisNamespace.GHOST.value}:{query_hash}"
    
    @staticmethod
    def ghost_activation_counter() -> str:
        """
        Key: ghost:activations
        Value: Counter of successful speculative activations
        Type: INT (counter)
        TTL: None
        Access: INCR / GET
        
        Used for: Measuring cache warming effectiveness
        Example: ghost:activations → 12847
        """
        return f"{RedisNamespace.GHOST.value}:activations"
    
    # ========================================================================
    # HAT (CONTEXT) TRACKING - Persona/Behavioral Mode
    # ========================================================================
    
    @staticmethod
    def hat_current_key() -> str:
        """
        Key: hat:current
        Value: Current active hat/persona name
        Type: STRING
        TTL: None
        Access: GET / SET
        
        Used for: Context switching via XOR masks
        Example: hat:current → "analytical"
        """
        return f"{RedisNamespace.HAT.value}:current"
    
    @staticmethod
    def hat_mask_key(hat_name: str) -> str:
        """
        Key: hat:<name>:mask
        Value: XOR mask for this hat (binary)
        Type: STRING (binary)
        TTL: None
        Size: ~1KB (256-bit mask)
        Access: GET (context switch)
        
        Used for: Instant grain reinterpretation via XOR
        Example: hat:analytical:mask → "binary data..."
        """
        return f"{RedisNamespace.HAT.value}:{hat_name}:mask"
    
    # ========================================================================
    # METRICS - Performance Tracking
    # ========================================================================
    
    @staticmethod
    def metrics_query_count_key() -> str:
        """
        Key: metrics:queries:count
        Value: Total queries processed this cycle
        Type: INT
        TTL: None
        Access: INCR / GET / RESET
        
        Used for: Query rate tracking
        Example: metrics:queries:count → 4827
        """
        return f"{RedisNamespace.METRICS.value}:queries:count"
    
    @staticmethod
    def metrics_latency_key(percentile: str) -> str:
        """
        Key: metrics:latency:<percentile>
        Value: Response latency in milliseconds
        Type: FLOAT
        TTL: None
        Access: SET / GET
        
        Used for: Performance monitoring
        Example: metrics:latency:p95 → 8.3, metrics:latency:p99 → 12.7
        """
        return f"{RedisNamespace.METRICS.value}:latency:{percentile}"
    
    @staticmethod
    def metrics_grain_lookup_key() -> str:
        """
        Key: metrics:grains:lookups
        Value: Counter of grain signature lookups
        Type: INT
        TTL: None
        Access: INCR / GET
        
        Used for: Reflex path efficiency measurement
        Example: metrics:grains:lookups → 38472
        """
        return f"{RedisNamespace.METRICS.value}:grains:lookups"
    
    @staticmethod
    def metrics_cache_hit_key() -> str:
        """
        Key: metrics:cache:hits
        Value: Counter of CMS cache hits
        Type: INT
        TTL: None
        Access: INCR / GET
        
        Used for: Cache effectiveness measurement
        Example: metrics:cache:hits → 3847
        """
        return f"{RedisNamespace.METRICS.value}:cache:hits"


# ============================================================================
# MEMORY BUDGET CALCULATOR
# ============================================================================

class MemoryBudget:
    """
    Calculate memory usage for realistic loads.
    
    Assumptions:
    - 10,000 active queries
    - 1,000 grains
    - 256-bit (32-byte) fingerprints
    """
    
    @staticmethod
    def estimate_total_mb() -> float:
        """Estimate total Redis memory usage in MB."""
        
        # CMS records
        cms_count = 10000
        cms_record_size = 0.5  # KB per record
        cms_grain_list_size = 0.2  # KB per list
        cms_resonance_size = 0.01  # KB per float
        cms_total = (cms_record_size + cms_grain_list_size + cms_resonance_size) * cms_count / 1024
        
        # Grain signatures
        grain_count = 1000
        grain_sig_size = 0.2  # KB per signature
        grain_plus_size = 1.0  # KB (256-bit + 256-bit)
        grain_minus_size = 1.0  # KB
        grain_index_size = 0.05  # KB per grain in index
        grain_total = (grain_sig_size + grain_plus_size + grain_minus_size) * grain_count / 1024
        grain_total += grain_index_size * grain_count / 1024
        
        # Ghost signals
        ghost_count = 1000
        ghost_signal_size = 0.05  # KB (just grain IDs)
        ghost_total = ghost_signal_size * ghost_count / 1024
        
        # Hat tracking
        hat_count = 10
        hat_mask_size = 1.0  # KB per hat (256-bit)
        hat_total = (hat_mask_size * hat_count + 0.01) / 1024
        
        # Metrics (negligible)
        metrics_total = 0.01
        
        total_mb = cms_total + grain_total + ghost_total + hat_total + metrics_total
        return round(total_mb, 1)


# ============================================================================
# EXAMPLE SCHEMA USAGE
# ============================================================================

def example_schema():
    """Show how the schema is used."""
    
    print("Redis Schema Example Usage\n")
    
    # CMS query resonance
    print("1. CMS Record:")
    query_hash = "a1b2c3d4e5f6"
    key = RedisSchemaSpec.cms_record_key(query_hash)
    print(f"   Key: {key}")
    print(f"   Value: {{'count': 47, 'score': 0.87, 'last_accessed': '2026-02-12T20:00:00Z'}}")
    print(f"   Operations: GET/SET, TTL: 86400s\n")
    
    # Grain signature
    print("2. Grain Signature:")
    grain_id = 42
    key = RedisSchemaSpec.grain_signature_key(grain_id)
    print(f"   Key: {key}")
    print(f"   Value: {{'popcount': 156, 'axiom': 'thermodynamics', 'weight': 1.58}}")
    print(f"   Operations: GET (O(1)), TTL: None\n")
    
    # Grain bits
    print("3. Grain Bit Arrays:")
    key_plus = RedisSchemaSpec.grain_bits_plus_key(grain_id)
    key_minus = RedisSchemaSpec.grain_bits_minus_key(grain_id)
    print(f"   Key (+): {key_plus}")
    print(f"   Key (-): {key_minus}")
    print(f"   Value: (binary data, 256 bits each)")
    print(f"   Operations: GET + XOR for ternary lookup\n")
    
    # Ghost signal
    print("4. Ghost Signal:")
    key = RedisSchemaSpec.ghost_signal_key(query_hash)
    print(f"   Key: {key}")
    print(f"   Value: '42,17,88'")
    print(f"   Operations: GET (speculative grain load), TTL: 3600s\n")
    
    # Hat mask
    print("5. Hat Context:")
    hat_name = "analytical"
    key = RedisSchemaSpec.hat_current_key()
    mask_key = RedisSchemaSpec.hat_mask_key(hat_name)
    print(f"   Current: {key}")
    print(f"   Mask: {mask_key}")
    print(f"   Operations: SET for context switch, XOR for reinterpretation\n")
    
    # Metrics
    print("6. Performance Metrics:")
    print(f"   Query count: {RedisSchemaSpec.metrics_query_count_key()}")
    print(f"   P95 latency: {RedisSchemaSpec.metrics_latency_key('p95')}")
    print(f"   Cache hits: {RedisSchemaSpec.metrics_cache_hit_key()}")
    print(f"   Operations: INCR/GET for counters\n")
    
    # Memory budget
    print("Memory Budget Estimate:")
    total_mb = MemoryBudget.estimate_total_mb()
    print(f"   Total Redis memory: ~{total_mb}MB")
    print(f"   (For 10,000 active queries + 1,000 grains)")


# ============================================================================
# ACTUAL REDIS CLIENT WRAPPER (sketch)
# ============================================================================

class RedisClient:
    """
    Lightweight Redis client wrapper implementing the schema.
    
    In production, use redis-py or aioredis.
    This is a specification sketch showing intended usage patterns.
    """
    
    def __init__(self, host: str = "localhost", port: int = 6379):
        """Initialize (would connect to actual Redis in production)."""
        self.host = host
        self.port = port
        # In real implementation: self.r = redis.Redis(...)
    
    def cms_record_get(self, query_hash: str) -> Optional[Dict]:
        """Get CMS record for query."""
        key = RedisSchemaSpec.cms_record_key(query_hash)
        # In real implementation: return json.loads(self.r.get(key))
        return None  # Placeholder
    
    def cms_record_set(self, query_hash: str, data: Dict) -> None:
        """Set CMS record."""
        key = RedisSchemaSpec.cms_record_key(query_hash)
        # In real implementation: self.r.setex(key, 86400, json.dumps(data))
        pass
    
    def grain_signature_get(self, grain_id: int) -> Optional[Dict]:
        """Get grain signature."""
        key = RedisSchemaSpec.grain_signature_key(grain_id)
        # In real implementation: return json.loads(self.r.get(key))
        return None
    
    def ghost_signal_get(self, query_hash: str) -> List[int]:
        """Get ghost signals (grain IDs to activate)."""
        key = RedisSchemaSpec.ghost_signal_key(query_hash)
        # In real implementation:
        # data = self.r.get(key)
        # return [int(x) for x in data.split(",")] if data else []
        return []
    
    def hat_context_switch(self, new_hat: str) -> None:
        """Switch to different context/persona."""
        key = RedisSchemaSpec.hat_current_key()
        # In real implementation: self.r.set(key, new_hat)
        pass
    
    def metrics_record_query(self, latency_ms: float) -> None:
        """Record query metrics."""
        # In real implementation:
        # self.r.incr(RedisSchemaSpec.metrics_query_count_key())
        # self.r.set(RedisSchemaSpec.metrics_latency_key("last"), latency_ms)
        pass


if __name__ == "__main__":
    example_schema()
    
    print("\n" + "="*60)
    print("Redis Schema Specification Complete")
    print("="*60)
    print(f"\nMemory estimates:")
    print(f"  Total: {MemoryBudget.estimate_total_mb()}MB")
    print(f"  Per 1000 queries: ~3.8MB")
    print(f"  Per 100 grains: ~2.1MB")
    print(f"\nPerformance targets:")
    print(f"  CMS lookup: O(1) <1ms")
    print(f"  Grain signature: O(1) <1ms")
    print(f"  Ghost activation: O(1) <1ms")
    print(f"  Total reflex path: <0.5ms")
