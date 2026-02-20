"""
redis_spotlight.py - Epistemic Spotlight Substrate for Phase 3B

Redis-backed query-scoped storage for epistemic layers (L0-L5).

Each query gets six spotlights (one per epistemic level) that live in Redis
with automatic expiry. Facts in spotlights are validated and filtered by
coupling constraints (Phase 3B.3+).

Design principles:
- Query-scoped: Each query's state is isolated, auto-expires
- O(1) operations: All basic operations are Redis-native
- Auditable: Every event logged for Phase 4 metabolism analysis
- Atomic: Lua scripts guarantee consistency (Phase 3B.3+)
- Backward compatible: Can run alongside old Redis patterns

Phase 3B.1 scope:
  ✅ Create/destroy queries
  ✅ Add/get/clear spotlights per layer (L0-L5)
  ✅ Log events during query lifecycle
  ✅ Record structural deltas (contradictions)
  ✅ Manage Lua scripts (for Phase 3B.3)

Phase 3B.3+ scope (future):
  ⏳ Validate coupling constraints (Lua)
  ⏳ Detect structural contradictions
  ⏳ Auto-escalate critical deltas
"""

import json
import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import redis
from redis import Redis

logger = logging.getLogger(__name__)


class EpistemicLevel(Enum):
    """Six epistemic layers (L0-L5) for knowledge organization."""
    L0_EMPIRICAL = "L0_empirical"      # Verified facts (0.90-1.0 confidence)
    L1_AXIOMATIC = "L1_axiomatic"      # Axioms/rules (0.85-0.99 confidence)
    L2_NARRATIVE = "L2_narrative"      # Story/identity (0.60-0.90 confidence)
    L3_HEURISTIC = "L3_heuristic"      # Folk wisdom (0.50-0.80 confidence)
    L4_INTENT = "L4_intent"            # Values/goals (0.40-0.75 confidence)
    L5_MASK = "L5_mask"                # Persona (0.30-0.70 confidence)


class RedisSpotlight:
    """
    Query-scoped epistemic spotlight substrate.
    
    Manages six parallel spotlights (one per epistemic layer) for each query.
    Facts in spotlights are organized by confidence level and later validated
    against coupling constraints.
    
    Key features:
    - Query-scoped isolation (no interference between queries)
    - Automatic TTL expiry (cleanup after query completion)
    - Event logging (audit trail for Phase 4 learning)
    - Structural delta detection (contradiction tracking)
    - Lua script management (for Phase 3B.3+ coupling validation)
    
    Memory efficiency:
    - Typical spotlight: ~1KB per query × 6 layers = 6KB
    - 1000 concurrent queries: ~6MB active
    - Query state auto-expires, no manual cleanup needed
    """
    
    def __init__(
        self,
        redis_client: Redis,
        default_query_lifetime: int = 3600,
        prefix: str = "spotlight:"
    ):
        """
        Initialize spotlight substrate.
        
        Args:
            redis_client: Redis connection (e.g., redis.Redis())
            default_query_lifetime: Query state TTL in seconds (default 1 hour)
            prefix: Redis key prefix for all spotlight keys
        
        Raises:
            redis.ConnectionError: If Redis is not available
        """
        self.redis = redis_client
        self.default_lifetime = default_query_lifetime
        self.prefix = prefix
        self.lua_scripts = {}  # SHA -> script mapping
        
        # Validate Redis connection
        try:
            self.redis.ping()
            logger.info(f"Redis spotlight initialized (prefix: {prefix})")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    # ========================================================================
    # QUERY LIFECYCLE
    # ========================================================================
    
    def create_query(
        self,
        query_id: str,
        query_text: str,
        metadata: Optional[Dict[str, Any]] = None,
        lifetime: Optional[int] = None
    ) -> None:
        """
        Create a new query and initialize all six spotlights.
        
        Args:
            query_id: Unique query identifier (e.g., "q_001")
            query_text: The query text
            metadata: Optional additional metadata
            lifetime: TTL in seconds (uses default if None)
        
        Raises:
            ValueError: If query_id already exists (prevent duplicates)
        """
        if self.query_exists(query_id):
            raise ValueError(f"Query {query_id} already exists")
        
        lifetime = lifetime or self.default_lifetime
        
        # Store metadata
        metadata_obj = {
            "query_id": query_id,
            "query_text": query_text,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "lifetime": lifetime,
            **(metadata or {})
        }
        
        key = f"{self.prefix}{query_id}:metadata"
        self.redis.setex(key, lifetime, json.dumps(metadata_obj))
        
        # Initialize all six spotlights (empty, with TTL)
        for layer in EpistemicLevel:
            key = f"{self.prefix}{query_id}:{layer.value}"
            self.redis.delete(key)  # Ensure clean slate
            self.redis.expire(key, lifetime)
        
        # Initialize event log
        key = f"{self.prefix}{query_id}:events"
        self.redis.delete(key)
        self.redis.expire(key, lifetime)
        
        logger.debug(f"Created query {query_id} (lifetime: {lifetime}s)")
    
    def query_exists(self, query_id: str) -> bool:
        """Check if query state still exists in Redis."""
        key = f"{self.prefix}{query_id}:metadata"
        return bool(self.redis.exists(key))
    
    def get_query_metadata(self, query_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve query metadata (creation time, status, etc.)."""
        key = f"{self.prefix}{query_id}:metadata"
        data = self.redis.get(key)
        return json.loads(data) if data else None
    
    def set_query_status(self, query_id: str, status: str) -> None:
        """
        Update query status (pending → processing → completed).
        
        Args:
            query_id: Query identifier
            status: New status string
        """
        metadata = self.get_query_metadata(query_id)
        if metadata:
            metadata["status"] = status
            metadata["updated_at"] = datetime.now().isoformat()
            key = f"{self.prefix}{query_id}:metadata"
            ttl = self.redis.ttl(key)
            self.redis.setex(key, ttl, json.dumps(metadata))
    
    def destroy_query(self, query_id: str) -> None:
        """
        Explicitly destroy query state (cleanup before or instead of TTL).
        
        Called after query is complete and results are logged to files.
        Frees Redis memory immediately instead of waiting for TTL.
        
        Args:
            query_id: Query identifier
        """
        pattern = f"{self.prefix}{query_id}:*"
        for key in self.redis.scan_iter(pattern):
            self.redis.delete(key)
        
        logger.debug(f"Destroyed query {query_id}")
    
    # ========================================================================
    # SPOTLIGHT OPERATIONS
    # ========================================================================
    
    def add_to_spotlight(
        self,
        query_id: str,
        layer: EpistemicLevel,
        fact: Dict[str, Any]
    ) -> None:
        """
        Add a fact to a spotlight layer.
        
        Args:
            query_id: Query identifier
            layer: Epistemic layer (L0-L5)
            fact: Fact object (must be JSON-serializable)
                  Should include: id, content, confidence, source, etc.
        
        Raises:
            ValueError: If query doesn't exist
        
        Note:
            - Facts stored in LIFO order (newest first)
            - Duplicates allowed (Phase 4 will deduplicate)
            - Each fact should have an 'id' field (auto-generated if missing)
        """
        if not self.query_exists(query_id):
            raise ValueError(f"Query {query_id} does not exist")
        
        key = f"{self.prefix}{query_id}:{layer.value}"
        
        # Ensure fact has minimal required fields
        if "id" not in fact:
            fact["id"] = str(uuid.uuid4())
        if "added_at" not in fact:
            fact["added_at"] = datetime.now().isoformat()
        
        self.redis.lpush(key, json.dumps(fact))
        logger.debug(f"Added fact {fact.get('id')} to {query_id}:{layer.value}")
    
    def get_spotlight(
        self,
        query_id: str,
        layer: EpistemicLevel,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all facts in a spotlight layer.
        
        Args:
            query_id: Query identifier
            layer: Epistemic layer
            limit: Max facts to return (None = all)
        
        Returns:
            List of facts, ordered by insertion (newest first)
        """
        key = f"{self.prefix}{query_id}:{layer.value}"
        
        if limit:
            raw = self.redis.lrange(key, 0, limit - 1)
        else:
            raw = self.redis.lrange(key, 0, -1)
        
        return [json.loads(item) for item in raw]
    
    def clear_spotlight(self, query_id: str, layer: EpistemicLevel) -> int:
        """
        Remove all facts from a spotlight.
        
        Called by Triage Agent after filtering decisions to reset a layer
        before adding approved facts.
        
        Args:
            query_id: Query identifier
            layer: Epistemic layer
        
        Returns:
            Number of facts removed
        """
        key = f"{self.prefix}{query_id}:{layer.value}"
        count = self.redis.llen(key)
        self.redis.delete(key)
        
        logger.debug(f"Cleared {count} facts from {query_id}:{layer.value}")
        return count
    
    def remove_from_spotlight(
        self,
        query_id: str,
        layer: EpistemicLevel,
        fact_id: str
    ) -> bool:
        """
        Remove a specific fact from a spotlight by ID.
        
        Args:
            query_id: Query identifier
            layer: Epistemic layer
            fact_id: Fact to remove (by 'id' field)
        
        Returns:
            True if removed, False if not found
        """
        key = f"{self.prefix}{query_id}:{layer.value}"
        facts = self.get_spotlight(query_id, layer)
        
        # Find and remove
        for i, fact in enumerate(facts):
            if fact.get("id") == fact_id:
                # Rebuild list without this fact
                self.clear_spotlight(query_id, layer)
                for f in facts[:i] + facts[i+1:]:
                    self.redis.rpush(key, json.dumps(f))
                logger.debug(f"Removed fact {fact_id} from {query_id}:{layer.value}")
                return True
        
        return False
    
    def get_all_spotlights(self, query_id: str) -> Dict[str, List[Dict]]:
        """Retrieve all six spotlights for a query."""
        return {
            layer.value: self.get_spotlight(query_id, layer)
            for layer in EpistemicLevel
        }
    
    # ========================================================================
    # LIFECYCLE EVENTS
    # ========================================================================
    
    def log_event(
        self,
        query_id: str,
        event_type: str,
        **kwargs
    ) -> None:
        """
        Log a query lifecycle event.
        
        Args:
            query_id: Query identifier
            event_type: Event category (e.g., 'grain_search', 'triage_gate')
            **kwargs: Event-specific data
        
        Example:
            spotlight.log_event(query_id, 'triage_gate', 
                              layer='L0', 
                              approved=5, 
                              blocked=2)
        """
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            **kwargs
        }
        
        key = f"{self.prefix}{query_id}:events"
        self.redis.lpush(key, json.dumps(event))
        
        logger.debug(f"Logged event {event_type} for {query_id}")
    
    def get_events(self, query_id: str) -> List[Dict[str, Any]]:
        """Retrieve all events for a query (newest first)."""
        key = f"{self.prefix}{query_id}:events"
        raw = self.redis.lrange(key, 0, -1)
        return [json.loads(item) for item in raw]
    
    def get_events_by_type(
        self,
        query_id: str,
        event_type: str
    ) -> List[Dict[str, Any]]:
        """Filter events by type (e.g., get all 'triage_gate' events)."""
        all_events = self.get_events(query_id)
        return [e for e in all_events if e.get("type") == event_type]
    
    # ========================================================================
    # STRUCTURAL DELTAS (Contradictions)
    # ========================================================================
    
    def record_delta(
        self,
        query_id: str,
        layer_a: str,
        layer_b: str,
        conflict_description: str,
        severity: str = "medium"
    ) -> str:
        """
        Record a structural delta (contradiction between layers).
        
        Called by coupling validation scripts when constraints are violated.
        Deltas are queryable for Phase 4 metabolism analysis.
        
        Args:
            query_id: Query identifier
            layer_a: Layer name (e.g., "L0_empirical")
            layer_b: Layer name (e.g., "L2_narrative")
            conflict_description: Human-readable conflict description
            severity: "low" | "medium" | "critical"
        
        Returns:
            Delta ID (for reference/tracking)
        """
        delta_id = str(uuid.uuid4())
        delta = {
            "delta_id": delta_id,
            "timestamp": datetime.now().isoformat(),
            "layer_a": layer_a,
            "layer_b": layer_b,
            "conflict": conflict_description,
            "severity": severity,
            "resolution": "unresolved"
        }
        
        key = f"{self.prefix}{query_id}:deltas"
        self.redis.lpush(key, json.dumps(delta))
        
        logger.warning(f"Delta {delta_id}: {layer_a} vs {layer_b} - {conflict_description}")
        return delta_id
    
    def get_deltas(self, query_id: str) -> List[Dict[str, Any]]:
        """Retrieve all deltas for a query."""
        key = f"{self.prefix}{query_id}:deltas"
        raw = self.redis.lrange(key, 0, -1)
        return [json.loads(item) for item in raw]
    
    def get_deltas_by_severity(
        self,
        query_id: str,
        severity: str
    ) -> List[Dict[str, Any]]:
        """Filter deltas by severity (e.g., get all "critical" deltas)."""
        all_deltas = self.get_deltas(query_id)
        return [d for d in all_deltas if d.get("severity") == severity]
    
    def has_critical_deltas(self, query_id: str) -> bool:
        """Check if query has any critical-severity deltas."""
        critical = self.get_deltas_by_severity(query_id, "critical")
        return len(critical) > 0
    
    # ========================================================================
    # LUA SCRIPT MANAGEMENT
    # ========================================================================
    
    def register_lua_script(self, name: str, script: str) -> str:
        """
        Load a Lua script into Redis and cache SHA.
        
        Used for Phase 3B.3+ coupling validation. Scripts are loaded once
        and executed via evalsha (more efficient than eval).
        
        Args:
            name: Script name (for reference, e.g., "validate_l1_against_l0")
            script: Lua script code
        
        Returns:
            Script SHA (used for evalsha)
        """
        sha = self.redis.script_load(script)
        self.lua_scripts[name] = sha
        logger.info(f"Loaded Lua script '{name}' (SHA: {sha[:8]}...)")
        return sha
    
    def execute_lua_script(
        self,
        script_name: str,
        keys: List[str],
        args: List[Any]
    ) -> Any:
        """
        Execute a registered Lua script.
        
        Args:
            script_name: Name of registered script
            keys: Redis keys to pass to script
            args: Arguments to pass to script
        
        Returns:
            Script result
        
        Raises:
            ValueError: If script not found
        """
        sha = self.lua_scripts.get(script_name)
        if not sha:
            raise ValueError(f"Unknown script: {script_name}")
        
        return self.redis.evalsha(sha, len(keys), *keys, *args)
    
    # ========================================================================
    # ANALYSIS & DEBUGGING
    # ========================================================================
    
    def get_query_summary(self, query_id: str) -> Dict[str, Any]:
        """
        Get a summary of query state for debugging.
        
        Returns overview of all spotlights, events, deltas for diagnosis.
        
        Args:
            query_id: Query identifier
        
        Returns:
            Dictionary with query status overview
        """
        metadata = self.get_query_metadata(query_id) or {}
        spotlights = self.get_all_spotlights(query_id)
        events = self.get_events(query_id)
        deltas = self.get_deltas(query_id)
        
        return {
            "query_id": query_id,
            "status": metadata.get("status", "unknown"),
            "query_text": metadata.get("query_text", ""),
            "created_at": metadata.get("created_at", ""),
            "spotlights": {
                layer: len(facts) for layer, facts in spotlights.items()
            },
            "event_count": len(events),
            "delta_count": len(deltas),
            "critical_deltas": len(self.get_deltas_by_severity(query_id, "critical")),
            "recent_events": [
                {"type": e.get("type"), "timestamp": e.get("timestamp")}
                for e in events[:5]  # Most recent 5
            ],
            "recent_deltas": [
                {"conflict": d.get("conflict"), "severity": d.get("severity")}
                for d in deltas[:3]  # Most recent 3
            ]
        }
    
    def estimate_memory(self) -> Dict[str, int]:
        """
        Estimate Redis memory usage.
        
        Returns dictionary of memory stats from Redis INFO command.
        
        Returns:
            Dictionary with memory information
        """
        info = self.redis.info("memory")
        return {
            "used_memory_bytes": info.get("used_memory", 0),
            "used_memory_peak_bytes": info.get("used_memory_peak", 0),
            "used_memory_rss_bytes": info.get("used_memory_rss", 0),
            "estimated_mb": round(info.get("used_memory", 0) / (1024 * 1024), 1)
        }


# ============================================================================
# HELPER FUNCTIONS (for tests and examples)
# ============================================================================

def create_test_fact(
    fact_id: str,
    content: str,
    layer: str = "L0_empirical",
    confidence: float = 0.95,
    source: str = "test_source"
) -> Dict[str, Any]:
    """
    Helper to create a test fact object.
    
    Args:
        fact_id: Unique fact identifier
        content: Fact content/description
        layer: Epistemic layer
        confidence: Confidence level (0.0-1.0)
        source: Where this fact came from
    
    Returns:
        Fact dictionary (JSON-serializable)
    """
    return {
        "id": fact_id,
        "content": content,
        "layer": layer,
        "confidence": confidence,
        "source": source,
        "created_at": datetime.now().isoformat()
    }


def create_test_event(
    event_type: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Helper to create a test event object.
    
    Args:
        event_type: Event category
        **kwargs: Additional event fields
    
    Returns:
        Event dictionary (JSON-serializable)
    """
    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "type": event_type,
        **kwargs
    }


if __name__ == "__main__":
    """Quick sanity check of core operations."""
    import sys
    
    try:
        # Test Redis connection
        r = redis.Redis(host="localhost", port=6379, db=1, decode_responses=True)
        r.ping()
        print("✅ Redis connection OK")
        
        # Test spotlight
        spotlight = RedisSpotlight(r, prefix="test:spotlight:")
        
        # Create query
        spotlight.create_query("test_q1", "What is water?")
        assert spotlight.query_exists("test_q1"), "Query creation failed"
        print("✅ Query creation OK")
        
        # Add fact
        fact = create_test_fact("f1", "Water boils at 100°C")
        spotlight.add_to_spotlight("test_q1", EpistemicLevel.L0_EMPIRICAL, fact)
        facts = spotlight.get_spotlight("test_q1", EpistemicLevel.L0_EMPIRICAL)
        assert len(facts) == 1, "Fact addition failed"
        print("✅ Spotlight operations OK")
        
        # Log event
        spotlight.log_event("test_q1", "test_event", data="test_data")
        events = spotlight.get_events("test_q1")
        assert len(events) == 1, "Event logging failed"
        print("✅ Event logging OK")
        
        # Cleanup
        spotlight.destroy_query("test_q1")
        assert not spotlight.query_exists("test_q1"), "Query destruction failed"
        print("✅ Query destruction OK")
        
        print("\n✅ All sanity checks passed!")
        print("RedisSpotlight is ready to use.")
        sys.exit(0)
        
    except redis.ConnectionError:
        print("❌ Redis not running on localhost:6379")
        print("Start Redis with: redis-server")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Sanity check failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
