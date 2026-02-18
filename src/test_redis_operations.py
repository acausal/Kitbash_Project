"""
Unit tests for Redis blackboard operations - Phase 3B infrastructure.

Validates:
- Redis connection and basic operations
- Query state management (create, retrieve, update)
- Query queue operations (enqueue, dequeue)
- Grain storage and retrieval
- Diagnostic event logging
- Worker health tracking
- Metrics collection
- Configuration loading
"""

import pytest
import logging
import json
from datetime import datetime, timedelta
import redis

from redis_blackboard import RedisBlackboard
from diagnostic_feed import DiagnosticFeed
from config import ConfigLoader, get_config

logger = logging.getLogger(__name__)


class TestRedisConnection:
    """Test Redis connectivity."""

    def test_redis_connection(self):
        """Verify Redis is running and accessible."""
        try:
            r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
            r.ping()
            logger.info("✅ Redis connection successful")
        except redis.ConnectionError:
            pytest.skip("Redis not running on localhost:6379")

    def test_redis_set_get(self):
        """Test basic Redis set/get operations."""
        r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
        r.set("test_key", "test_value")
        value = r.get("test_key")
        assert value == "test_value"
        r.delete("test_key")
        logger.info("✅ Redis set/get operations work")


class TestRedisBlackboard:
    """Test RedisBlackboard query management."""

    @pytest.fixture
    def blackboard(self):
        """Create fresh blackboard for each test."""
        bb = RedisBlackboard(prefix="test:kitbash:")
        bb.flush_all()  # Clean slate
        yield bb
        bb.flush_all()

    def test_query_creation(self, blackboard):
        """Test creating and retrieving a query."""
        query_id = "q_test_001"
        query_text = "What is AI?"

        blackboard.create_query(query_id, query_text)
        query = blackboard.get_query(query_id)

        assert query is not None
        assert query["query_id"] == query_id
        assert query["query_text"] == query_text
        assert query["status"] == "pending"
        logger.info("✅ Query creation works")

    def test_query_update_status(self, blackboard):
        """Test updating query status."""
        query_id = "q_test_002"
        blackboard.create_query(query_id, "Test query")

        blackboard.update_query_status(
            query_id,
            "layer0_hit",
            {"confidence": 0.99}
        )

        query = blackboard.get_query(query_id)
        assert query["status"] == "layer0_hit"
        assert len(query["layer_attempts"]) == 1
        logger.info("✅ Query status update works")

    def test_query_queue(self, blackboard):
        """Test enqueueing and dequeueing queries."""
        # Enqueue
        blackboard.enqueue_query("q1")
        blackboard.enqueue_query("q2")
        blackboard.enqueue_query("q3")

        assert blackboard.queue_length() == 3

        # Dequeue (FIFO order)
        q = blackboard.dequeue_query()
        assert q == "q1"
        assert blackboard.queue_length() == 2

        logger.info("✅ Query queue operations work")

    def test_query_delete(self, blackboard):
        """Test deleting a query."""
        query_id = "q_delete_test"
        blackboard.create_query(query_id, "Test")

        assert blackboard.get_query(query_id) is not None
        blackboard.delete_query(query_id)
        assert blackboard.get_query(query_id) is None

        logger.info("✅ Query deletion works")


class TestGrainManagement:
    """Test grain storage and retrieval."""

    @pytest.fixture
    def blackboard(self):
        bb = RedisBlackboard(prefix="test:kitbash:")
        bb.flush_all()
        yield bb
        bb.flush_all()

    def test_store_and_retrieve_grain(self, blackboard):
        """Test storing and retrieving a grain."""
        fact_id = "fact_001"
        grain_data = {
            "ternary": [1, -1, 0, 1],
            "meaning": "Paris is the capital of France",
            "confidence": 0.99,
        }

        blackboard.store_grain(fact_id, grain_data)
        retrieved = blackboard.get_grain(fact_id)

        assert retrieved is not None
        assert retrieved["meaning"] == grain_data["meaning"]
        assert retrieved["confidence"] == 0.99
        logger.info("✅ Grain storage and retrieval works")

    def test_grain_exists(self, blackboard):
        """Test checking grain existence."""
        fact_id = "fact_002"

        assert not blackboard.grain_exists(fact_id)

        blackboard.store_grain(fact_id, {"data": "test"})
        assert blackboard.grain_exists(fact_id)

        logger.info("✅ Grain existence check works")

    def test_list_grains(self, blackboard):
        """Test listing grains."""
        blackboard.store_grain("fact_001", {"data": "test1"})
        blackboard.store_grain("fact_002", {"data": "test2"})
        blackboard.store_grain("fact_003", {"data": "test3"})

        grains = blackboard.list_grains()
        assert len(grains) == 3
        assert "fact_001" in grains

        logger.info("✅ Grain listing works")

    def test_grain_count(self, blackboard):
        """Test counting grains."""
        blackboard.store_grain("f1", {})
        blackboard.store_grain("f2", {})

        assert blackboard.grain_count() == 2
        logger.info("✅ Grain counting works")


class TestDiagnosticLogging:
    """Test diagnostic event logging."""

    @pytest.fixture
    def feed(self):
        feed = DiagnosticFeed(prefix="test:kitbash:")
        feed.clear_feed()
        yield feed
        feed.clear_feed()

    def test_log_query_events(self, feed):
        """Test logging query lifecycle events."""
        query_id = "q_001"

        feed.log_query_created(query_id, "Test query")
        feed.log_query_started(query_id)
        feed.log_layer_hit(query_id, "layer0", confidence=0.99, latency_ms=0.17)
        feed.log_query_completed(query_id, "layer0", confidence=0.99, latency_ms=0.17)

        timeline = feed.get_query_timeline(query_id)
        assert len(timeline) == 4

        event_types = [e["event_type"] for e in timeline]
        assert "query_created" in event_types
        assert "query_completed" in event_types

        logger.info("✅ Query event logging works")

    def test_log_layer_events(self, feed):
        """Test logging layer processing events."""
        query_id = "q_layer_test"

        feed.log_layer_attempt(query_id, "layer0", 0.17)
        feed.log_layer_hit(query_id, "layer0", confidence=0.95, latency_ms=0.17)

        events = feed.get_events_for_layer("layer0")
        assert len(events) >= 2

        logger.info("✅ Layer event logging works")

    def test_log_escalation(self, feed):
        """Test logging escalation events."""
        query_id = "q_escalate"

        feed.log_layer_miss(query_id, "layer0", 0.5)
        feed.log_escalation(query_id, "layer0", "layer1", "Low confidence")
        feed.log_layer_attempt(query_id, "layer1", 5.0)

        timeline = feed.get_query_timeline(query_id)
        escalation_events = [e for e in timeline if e["event_type"] == "escalation"]

        assert len(escalation_events) == 1
        logger.info("✅ Escalation logging works")

    def test_get_feed(self, feed):
        """Test retrieving diagnostic feed."""
        feed.log_query_created("q1", "Query 1")
        feed.log_query_created("q2", "Query 2")
        feed.log_query_created("q3", "Query 3")

        all_events = feed.get_feed(count=10)
        assert len(all_events) >= 3

        logger.info("✅ Diagnostic feed retrieval works")

    def test_layer_statistics(self, feed):
        """Test collecting layer statistics."""
        # Simulate layer0 events
        for i in range(10):
            query_id = f"q_{i}"
            feed.log_layer_attempt(query_id, "layer0", 0.2)
            if i < 8:  # 8 hits, 2 misses
                feed.log_layer_hit(query_id, "layer0", 0.95, 0.2)
            else:
                feed.log_layer_miss(query_id, "layer0", 0.2, "Low confidence")

        stats = feed.get_layer_statistics("layer0")
        assert stats["attempts"] == 10
        assert stats["hits"] == 8
        assert stats["misses"] == 2
        assert stats["hit_rate"] == 0.8

        logger.info(f"✅ Layer statistics work: {stats}")

    def test_query_statistics(self, feed):
        """Test collecting query statistics."""
        query_id = "q_stats"

        feed.log_query_created(query_id, "Test")
        feed.log_query_started(query_id)
        feed.log_layer_attempt(query_id, "layer0", 0.2)
        feed.log_layer_hit(query_id, "layer0", 0.99, 0.2)
        feed.log_query_completed(query_id, "layer0", 0.99, 0.2)

        stats = feed.get_query_statistics(query_id)
        assert stats["query_id"] == query_id
        assert "layer0" in stats["layers_attempted"]

        logger.info("✅ Query statistics work")


class TestWorkerHealth:
    """Test worker health tracking."""

    @pytest.fixture
    def blackboard(self):
        bb = RedisBlackboard(prefix="test:kitbash:")
        bb.flush_all()
        yield bb
        bb.flush_all()

    def test_set_worker_health(self, blackboard):
        """Test setting worker health status."""
        blackboard.set_worker_health(
            "bitnet",
            "healthy",
            {"load": 0.5, "processed_queries": 100}
        )

        health = blackboard.get_worker_health("bitnet")
        assert health is not None
        assert health["status"] == "healthy"
        assert health["details"]["load"] == 0.5

        logger.info("✅ Worker health tracking works")

    def test_all_workers_health(self, blackboard):
        """Test retrieving all worker health statuses."""
        blackboard.set_worker_health("bitnet", "healthy")
        blackboard.set_worker_health("cartridge", "degraded", {"reason": "high load"})
        blackboard.set_worker_health("kobold", "dead", {"reason": "no response"})

        all_health = blackboard.all_workers_healthy()
        assert all_health["bitnet"] == "healthy"
        assert all_health["cartridge"] == "degraded"
        assert all_health["kobold"] == "dead"

        logger.info("✅ All workers health retrieval works")


class TestMetricsCollection:
    """Test metrics collection."""

    @pytest.fixture
    def blackboard(self):
        bb = RedisBlackboard(prefix="test:kitbash:")
        bb.flush_all()
        yield bb
        bb.flush_all()

    def test_record_metric(self, blackboard):
        """Test recording metrics."""
        blackboard.record_metric("layer0_latency_ms", 0.17)
        blackboard.record_metric("layer0_latency_ms", 0.19)
        blackboard.record_metric("layer0_latency_ms", 0.16)

        metrics = blackboard.get_metrics("layer0_latency_ms", minutes=60)
        assert len(metrics) == 3

        logger.info("✅ Metrics recording works")

    def test_metric_percentile(self, blackboard):
        """Test calculating metric percentiles."""
        for i in range(100):
            blackboard.record_metric("test_metric", float(i))

        p50 = blackboard.get_metric_percentile("test_metric", 50, minutes=60)
        assert p50 is not None
        assert 40 < p50 < 60  # Should be around 50

        p95 = blackboard.get_metric_percentile("test_metric", 95, minutes=60)
        assert p95 > p50

        logger.info(f"✅ Metric percentiles work: p50={p50}, p95={p95}")


class TestConfiguration:
    """Test configuration loading."""

    def test_config_loader_defaults(self):
        """Test config loader with defaults."""
        loader = ConfigLoader(config_path="nonexistent.yaml")
        config = loader.get()

        assert config.redis.host == "localhost"
        assert config.redis.port == 6379

        logger.info("✅ Config defaults work")

    def test_config_load_yaml(self):
        """Test loading YAML configuration."""
        loader = ConfigLoader(config_path="./kitbash_config.yaml")
        config = loader.get()

        assert config.redis is not None
        assert len(config.layers) > 0
        assert len(config.workers) > 0

        logger.info("✅ YAML config loading works")

    def test_config_validation(self):
        """Test config validation with Pydantic."""
        loader = ConfigLoader()
        config = loader.get()

        # Thresholds should be between 0 and 1
        assert 0 <= config.performance.consensus_confidence_threshold <= 1
        assert 0 <= config.performance.escalation_confidence_threshold <= 1

        logger.info("✅ Config validation works")


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_query_flow(self):
        """Test full query processing flow with blackboard and diagnostics."""
        # Setup
        bb = RedisBlackboard(prefix="test:kitbash:")
        feed = DiagnosticFeed(prefix="test:kitbash:")
        bb.flush_all()
        feed.clear_feed()

        query_id = "integration_test_001"

        # Simulate full query flow
        bb.create_query(query_id, "What is the capital of France?")
        feed.log_query_created(query_id, "What is the capital of France?")

        bb.enqueue_query(query_id)
        assert bb.queue_length() == 1

        feed.log_query_started(query_id)
        bb.update_query_status(query_id, "started")

        # Layer 0 attempt
        feed.log_layer_attempt(query_id, "layer0", 0.17)
        feed.log_layer_hit(query_id, "layer0", 0.99, 0.17, "Paris")

        bb.update_query_status(query_id, "layer0_hit", {"confidence": 0.99})
        feed.log_query_completed(query_id, "layer0", 0.99, 0.17)

        # Verify state
        query = bb.get_query(query_id)
        assert query["status"] == "layer0_hit"

        timeline = feed.get_query_timeline(query_id)
        assert len(timeline) >= 4

        dequeued = bb.dequeue_query()
        assert dequeued == query_id

        bb.flush_all()
        feed.clear_feed()

        logger.info("✅ Full query flow integration test passed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__, "-v", "-s"])
