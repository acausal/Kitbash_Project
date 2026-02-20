"""
test_redis_spotlight.py - Unit Tests for Epistemic Spotlight Substrate

Tests for redis_spotlight.RedisSpotlight class covering:
  - Query lifecycle (create, destroy, exists, metadata)
  - Spotlight operations (add, get, clear, remove)
  - Event logging and retrieval
  - Structural deltas (recording and filtering)
  - Lua script management (registration, execution)
  - Debugging helpers (query summary, memory estimation)

Run with: pytest src/tests/test_redis_spotlight.py -v

All tests use isolated Redis database (db=1) to avoid conflicts.
Redis must be running locally on 6379 for tests to pass.
"""

import pytest
import json
from datetime import datetime
import redis
from redis import Redis

from redis_spotlight import (
    RedisSpotlight,
    EpistemicLevel,
    create_test_fact,
    create_test_event
)


@pytest.fixture
def redis_client():
    """
    Create test Redis client.
    
    Uses database 1 (separate from production).
    Cleans up before and after each test.
    
    Raises:
        pytest.skip: If Redis not available
    """
    try:
        r = redis.Redis(
            host="localhost",
            port=6379,
            db=1,
            decode_responses=True,
            socket_connect_timeout=2
        )
        r.ping()
    except redis.ConnectionError:
        pytest.skip("Redis not running on localhost:6379")
    
    r.flushdb()  # Clean before
    yield r
    r.flushdb()  # Clean after


@pytest.fixture
def spotlight(redis_client):
    """Create RedisSpotlight instance for each test."""
    return RedisSpotlight(redis_client, prefix="test:spotlight:")


# ============================================================================
# QUERY LIFECYCLE TESTS
# ============================================================================

class TestQueryLifecycle:
    """Test query creation, status updates, and destruction."""
    
    def test_create_query(self, spotlight):
        """Test creating a query and verifying initial state."""
        spotlight.create_query("q1", "What is water?")
        
        assert spotlight.query_exists("q1")
        metadata = spotlight.get_query_metadata("q1")
        assert metadata is not None
        assert metadata["query_id"] == "q1"
        assert metadata["query_text"] == "What is water?"
        assert metadata["status"] == "pending"
    
    def test_create_duplicate_query_raises(self, spotlight):
        """Creating same query twice should raise ValueError."""
        spotlight.create_query("q1", "test")
        
        with pytest.raises(ValueError, match="already exists"):
            spotlight.create_query("q1", "test")
    
    def test_query_status_update(self, spotlight):
        """Test updating query status through lifecycle."""
        spotlight.create_query("q1", "test")
        
        spotlight.set_query_status("q1", "processing")
        metadata = spotlight.get_query_metadata("q1")
        assert metadata["status"] == "processing"
        
        spotlight.set_query_status("q1", "completed")
        metadata = spotlight.get_query_metadata("q1")
        assert metadata["status"] == "completed"
    
    def test_query_auto_expiry(self, spotlight):
        """Test query expires after TTL."""
        spotlight.create_query("q1", "test", lifetime=1)
        assert spotlight.query_exists("q1")
        
        import time
        time.sleep(2)
        
        assert not spotlight.query_exists("q1")
    
    def test_destroy_query(self, spotlight):
        """Test explicit query destruction."""
        spotlight.create_query("q1", "test")
        assert spotlight.query_exists("q1")
        
        spotlight.destroy_query("q1")
        assert not spotlight.query_exists("q1")
    
    def test_custom_metadata(self, spotlight):
        """Test creating query with custom metadata."""
        custom_meta = {"domain": "physics", "user_id": "u123"}
        spotlight.create_query("q1", "test", metadata=custom_meta)
        
        metadata = spotlight.get_query_metadata("q1")
        assert metadata["domain"] == "physics"
        assert metadata["user_id"] == "u123"


# ============================================================================
# SPOTLIGHT OPERATIONS TESTS
# ============================================================================

class TestSpotlightOperations:
    """Test adding, retrieving, and removing facts from spotlights."""
    
    def test_add_to_spotlight(self, spotlight):
        """Test adding a single fact to a spotlight."""
        spotlight.create_query("q1", "test")
        fact = create_test_fact("f1", "Water boils at 100°C")
        
        spotlight.add_to_spotlight("q1", EpistemicLevel.L0_EMPIRICAL, fact)
        
        facts = spotlight.get_spotlight("q1", EpistemicLevel.L0_EMPIRICAL)
        assert len(facts) == 1
        assert facts[0]["id"] == "f1"
        assert facts[0]["content"] == "Water boils at 100°C"
    
    def test_add_multiple_facts(self, spotlight):
        """Test adding multiple facts to same spotlight."""
        spotlight.create_query("q1", "test")
        
        for i in range(5):
            fact = create_test_fact(f"f{i}", f"Fact {i}")
            spotlight.add_to_spotlight("q1", EpistemicLevel.L0_EMPIRICAL, fact)
        
        facts = spotlight.get_spotlight("q1", EpistemicLevel.L0_EMPIRICAL)
        assert len(facts) == 5
    
    def test_spotlight_lifo_order(self, spotlight):
        """Test facts retrieved in LIFO order (newest first)."""
        spotlight.create_query("q1", "test")
        
        fact1 = create_test_fact("f1", "First")
        fact2 = create_test_fact("f2", "Second")
        fact3 = create_test_fact("f3", "Third")
        
        spotlight.add_to_spotlight("q1", EpistemicLevel.L0_EMPIRICAL, fact1)
        spotlight.add_to_spotlight("q1", EpistemicLevel.L0_EMPIRICAL, fact2)
        spotlight.add_to_spotlight("q1", EpistemicLevel.L0_EMPIRICAL, fact3)
        
        facts = spotlight.get_spotlight("q1", EpistemicLevel.L0_EMPIRICAL)
        assert facts[0]["id"] == "f3"  # Most recent first
        assert facts[1]["id"] == "f2"
        assert facts[2]["id"] == "f1"
    
    def test_clear_spotlight(self, spotlight):
        """Test clearing all facts from a spotlight."""
        spotlight.create_query("q1", "test")
        
        for i in range(5):
            fact = create_test_fact(f"f{i}", f"Fact {i}")
            spotlight.add_to_spotlight("q1", EpistemicLevel.L0_EMPIRICAL, fact)
        
        assert len(spotlight.get_spotlight("q1", EpistemicLevel.L0_EMPIRICAL)) == 5
        
        count = spotlight.clear_spotlight("q1", EpistemicLevel.L0_EMPIRICAL)
        assert count == 5
        assert len(spotlight.get_spotlight("q1", EpistemicLevel.L0_EMPIRICAL)) == 0
    
    def test_remove_specific_fact(self, spotlight):
        """Test removing a specific fact by ID."""
        spotlight.create_query("q1", "test")
        
        f1 = create_test_fact("f1", "Fact 1")
        f2 = create_test_fact("f2", "Fact 2")
        f3 = create_test_fact("f3", "Fact 3")
        
        for f in [f1, f2, f3]:
            spotlight.add_to_spotlight("q1", EpistemicLevel.L0_EMPIRICAL, f)
        
        removed = spotlight.remove_from_spotlight("q1", EpistemicLevel.L0_EMPIRICAL, "f2")
        assert removed is True
        
        facts = spotlight.get_spotlight("q1", EpistemicLevel.L0_EMPIRICAL)
        assert len(facts) == 2
        assert all(f["id"] != "f2" for f in facts)
    
    def test_remove_nonexistent_fact(self, spotlight):
        """Test removing fact that doesn't exist returns False."""
        spotlight.create_query("q1", "test")
        
        fact = create_test_fact("f1", "Fact 1")
        spotlight.add_to_spotlight("q1", EpistemicLevel.L0_EMPIRICAL, fact)
        
        removed = spotlight.remove_from_spotlight("q1", EpistemicLevel.L0_EMPIRICAL, "f_nonexistent")
        assert removed is False
    
    def test_all_spotlights_isolated(self, spotlight):
        """Test facts in L0 don't appear in L1, etc."""
        spotlight.create_query("q1", "test")
        
        f0 = create_test_fact("f0", "L0 fact", layer="L0_empirical")
        f1 = create_test_fact("f1", "L1 fact", layer="L1_axiomatic")
        
        spotlight.add_to_spotlight("q1", EpistemicLevel.L0_EMPIRICAL, f0)
        spotlight.add_to_spotlight("q1", EpistemicLevel.L1_AXIOMATIC, f1)
        
        l0_facts = spotlight.get_spotlight("q1", EpistemicLevel.L0_EMPIRICAL)
        l1_facts = spotlight.get_spotlight("q1", EpistemicLevel.L1_AXIOMATIC)
        
        assert len(l0_facts) == 1 and l0_facts[0]["id"] == "f0"
        assert len(l1_facts) == 1 and l1_facts[0]["id"] == "f1"
    
    def test_get_all_spotlights(self, spotlight):
        """Test retrieving all six spotlights at once."""
        spotlight.create_query("q1", "test")
        
        # Add one fact to each layer
        for i, layer in enumerate(EpistemicLevel):
            fact = create_test_fact(f"f{i}", f"Fact in {layer.value}")
            spotlight.add_to_spotlight("q1", layer, fact)
        
        all_spotlights = spotlight.get_all_spotlights("q1")
        
        assert len(all_spotlights) == 6
        for layer in EpistemicLevel:
            assert layer.value in all_spotlights
            assert len(all_spotlights[layer.value]) == 1
    
    def test_spotlight_with_limit(self, spotlight):
        """Test getting spotlight with limit parameter."""
        spotlight.create_query("q1", "test")
        
        for i in range(10):
            fact = create_test_fact(f"f{i}", f"Fact {i}")
            spotlight.add_to_spotlight("q1", EpistemicLevel.L0_EMPIRICAL, fact)
        
        # Get only first 3
        facts = spotlight.get_spotlight("q1", EpistemicLevel.L0_EMPIRICAL, limit=3)
        assert len(facts) == 3


# ============================================================================
# EVENT LOGGING TESTS
# ============================================================================

class TestEvents:
    """Test event logging and retrieval."""
    
    def test_log_single_event(self, spotlight):
        """Test logging a single event."""
        spotlight.create_query("q1", "test")
        spotlight.log_event("q1", "grain_search", layer="L0", hits=5)
        
        events = spotlight.get_events("q1")
        assert len(events) == 1
        assert events[0]["type"] == "grain_search"
        assert events[0]["layer"] == "L0"
        assert events[0]["hits"] == 5
    
    def test_log_multiple_events(self, spotlight):
        """Test logging sequence of events."""
        spotlight.create_query("q1", "test")
        
        spotlight.log_event("q1", "grain_search", layer="L0")
        spotlight.log_event("q1", "cartridge_load", domain="physics")
        spotlight.log_event("q1", "triage_gate", approved=3, blocked=2)
        
        events = spotlight.get_events("q1")
        assert len(events) == 3
        assert events[0]["type"] == "triage_gate"  # LIFO
        assert events[2]["type"] == "grain_search"
    
    def test_get_events_by_type(self, spotlight):
        """Test filtering events by type."""
        spotlight.create_query("q1", "test")
        
        spotlight.log_event("q1", "grain_search", layer="L0")
        spotlight.log_event("q1", "grain_search", layer="L1")
        spotlight.log_event("q1", "triage_gate", approved=5)
        
        grain_events = spotlight.get_events_by_type("q1", "grain_search")
        assert len(grain_events) == 2
        
        triage_events = spotlight.get_events_by_type("q1", "triage_gate")
        assert len(triage_events) == 1
    
    def test_event_structure(self, spotlight):
        """Test event has required fields."""
        spotlight.create_query("q1", "test")
        spotlight.log_event("q1", "test_event", data="test_data")
        
        events = spotlight.get_events("q1")
        event = events[0]
        
        assert "event_id" in event
        assert "timestamp" in event
        assert "type" in event
        assert event["type"] == "test_event"
        assert event["data"] == "test_data"


# ============================================================================
# STRUCTURAL DELTA TESTS
# ============================================================================

class TestDeltas:
    """Test structural delta recording and retrieval."""
    
    def test_record_delta(self, spotlight):
        """Test recording a structural delta."""
        spotlight.create_query("q1", "test")
        
        delta_id = spotlight.record_delta(
            "q1",
            "L0_empirical",
            "L2_narrative",
            "L0 says X, L2 says not-X",
            severity="critical"
        )
        
        assert delta_id is not None
        deltas = spotlight.get_deltas("q1")
        assert len(deltas) == 1
        assert deltas[0]["layer_a"] == "L0_empirical"
        assert deltas[0]["severity"] == "critical"
        assert deltas[0]["delta_id"] == delta_id
    
    def test_multiple_deltas(self, spotlight):
        """Test recording multiple deltas."""
        spotlight.create_query("q1", "test")
        
        spotlight.record_delta("q1", "L0", "L1", "Conflict 1", severity="low")
        spotlight.record_delta("q1", "L1", "L2", "Conflict 2", severity="critical")
        spotlight.record_delta("q1", "L2", "L4", "Conflict 3", severity="medium")
        
        deltas = spotlight.get_deltas("q1")
        assert len(deltas) == 3
    
    def test_get_deltas_by_severity(self, spotlight):
        """Test filtering deltas by severity."""
        spotlight.create_query("q1", "test")
        
        spotlight.record_delta("q1", "L0", "L1", "C1", severity="low")
        spotlight.record_delta("q1", "L0", "L1", "C2", severity="critical")
        spotlight.record_delta("q1", "L0", "L1", "C3", severity="critical")
        spotlight.record_delta("q1", "L0", "L1", "C4", severity="medium")
        
        critical = spotlight.get_deltas_by_severity("q1", "critical")
        assert len(critical) == 2
        
        low = spotlight.get_deltas_by_severity("q1", "low")
        assert len(low) == 1
    
    def test_has_critical_deltas(self, spotlight):
        """Test checking for critical deltas."""
        spotlight.create_query("q1", "test")
        
        assert not spotlight.has_critical_deltas("q1")
        
        spotlight.record_delta("q1", "L0", "L1", "Low severity", severity="low")
        assert not spotlight.has_critical_deltas("q1")
        
        spotlight.record_delta("q1", "L0", "L1", "Critical", severity="critical")
        assert spotlight.has_critical_deltas("q1")


# ============================================================================
# LUA SCRIPT TESTS
# ============================================================================

class TestLuaScripts:
    """Test Lua script registration and execution."""
    
    def test_register_lua_script(self, spotlight):
        """Test registering a Lua script."""
        script = "return redis.call('PING')"
        
        sha = spotlight.register_lua_script("test_ping", script)
        assert sha is not None
        assert spotlight.lua_scripts.get("test_ping") == sha
    
    def test_execute_lua_script(self, spotlight):
        """Test executing a registered Lua script."""
        script = "return {1, 2, 3}"
        
        spotlight.register_lua_script("test_array", script)
        result = spotlight.execute_lua_script("test_array", [], [])
        
        assert result == [1, 2, 3]
    
    def test_execute_unknown_script_raises(self, spotlight):
        """Test executing unknown script raises ValueError."""
        with pytest.raises(ValueError, match="Unknown script"):
            spotlight.execute_lua_script("nonexistent", [], [])


# ============================================================================
# DEBUGGING & SUMMARY TESTS
# ============================================================================

class TestQuerySummary:
    """Test query summary and debugging helpers."""
    
    def test_get_query_summary(self, spotlight):
        """Test getting a query summary."""
        spotlight.create_query("q1", "What is water?")
        
        fact = create_test_fact("f1", "Water boils at 100°C")
        spotlight.add_to_spotlight("q1", EpistemicLevel.L0_EMPIRICAL, fact)
        spotlight.log_event("q1", "grain_search", hits=1)
        spotlight.record_delta("q1", "L0", "L2", "Conflict", severity="medium")
        
        summary = spotlight.get_query_summary("q1")
        
        assert summary["query_id"] == "q1"
        assert summary["status"] == "pending"
        assert summary["spotlights"]["L0_empirical"] == 1
        assert summary["event_count"] == 1
        assert summary["delta_count"] == 1
        assert summary["critical_deltas"] == 0
    
    def test_query_summary_empty_query(self, spotlight):
        """Test summary on empty query."""
        spotlight.create_query("q1", "test")
        
        summary = spotlight.get_query_summary("q1")
        
        assert summary["query_id"] == "q1"
        assert all(count == 0 for count in summary["spotlights"].values())
        assert summary["event_count"] == 0
        assert summary["delta_count"] == 0
    
    def test_estimate_memory(self, spotlight):
        """Test memory estimation."""
        memory = spotlight.estimate_memory()
        
        assert "used_memory_bytes" in memory
        assert "used_memory_peak_bytes" in memory
        assert "estimated_mb" in memory
        assert memory["used_memory_bytes"] >= 0


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_full_query_lifecycle(self, spotlight):
        """Test complete query lifecycle from creation to destruction."""
        # Create
        spotlight.create_query("q1", "What is water?")
        assert spotlight.query_exists("q1")
        
        # Add facts
        for i in range(3):
            fact = create_test_fact(f"f{i}", f"Fact {i}")
            spotlight.add_to_spotlight("q1", EpistemicLevel.L0_EMPIRICAL, fact)
        
        # Log events
        spotlight.log_event("q1", "grain_search", count=3)
        spotlight.log_event("q1", "triage_gate", approved=2)
        
        # Record deltas
        spotlight.record_delta("q1", "L0", "L2", "Contradiction", severity="low")
        
        # Verify state
        summary = spotlight.get_query_summary("q1")
        assert summary["spotlights"]["L0_empirical"] == 3
        assert summary["event_count"] == 2
        assert summary["delta_count"] == 1
        
        # Destroy
        spotlight.destroy_query("q1")
        assert not spotlight.query_exists("q1")
    
    def test_multiple_concurrent_queries(self, spotlight):
        """Test multiple queries don't interfere."""
        queries = ["q1", "q2", "q3"]
        
        for q_id in queries:
            spotlight.create_query(q_id, f"Query {q_id}")
            for i in range(3):
                fact = create_test_fact(f"f{i}", f"Fact for {q_id}")
                spotlight.add_to_spotlight(q_id, EpistemicLevel.L0_EMPIRICAL, fact)
        
        # Verify isolation
        for q_id in queries:
            facts = spotlight.get_spotlight(q_id, EpistemicLevel.L0_EMPIRICAL)
            assert len(facts) == 3
            summary = spotlight.get_query_summary(q_id)
            assert summary["query_id"] == q_id
    
    def test_all_layers_together(self, spotlight):
        """Test adding facts to all six layers."""
        spotlight.create_query("q1", "test")
        
        layers_with_facts = {}
        for layer in EpistemicLevel:
            fact = create_test_fact(f"f_{layer.value}", f"Fact in {layer.value}")
            spotlight.add_to_spotlight("q1", layer, fact)
            layers_with_facts[layer.value] = 1
        
        all_spotlights = spotlight.get_all_spotlights("q1")
        
        for layer_name, expected_count in layers_with_facts.items():
            assert len(all_spotlights[layer_name]) == expected_count
