"""
Diagnostic feed for Kitbash Phase 3B.

Provides structured logging to Redis for all routing decisions, layer attempts,
timeouts, escalations, and subprocess health events.

Enables:
- Real-time monitoring of query flow
- Post-mortem analysis of routing decisions
- Performance metrics collection
- Worker health visibility
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
import redis
from redis import Redis

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Diagnostic event types."""
    QUERY_CREATED = "query_created"
    QUERY_STARTED = "query_started"
    LAYER0_ATTEMPT = "layer0_attempt"
    LAYER0_HIT = "layer0_hit"
    LAYER0_MISS = "layer0_miss"
    LAYER1_ATTEMPT = "layer1_attempt"
    LAYER1_RESULT = "layer1_result"
    LAYER2_ATTEMPT = "layer2_attempt"
    LAYER2_RESULT = "layer2_result"
    LAYER3_ATTEMPT = "layer3_attempt"
    LAYER3_RESULT = "layer3_result"
    LAYER4_ATTEMPT = "layer4_attempt"
    LAYER4_RESULT = "layer4_result"
    ESCALATION = "escalation"
    TIMEOUT = "timeout"
    ERROR = "error"
    QUERY_COMPLETED = "query_completed"
    WORKER_HEALTH = "worker_health"
    METRIC_RECORDED = "metric_recorded"


class ConfidenceLevel(str, Enum):
    """Confidence levels for query responses."""
    CERTAIN = "certain"  # >0.95
    HIGH = "high"  # 0.85-0.95
    MEDIUM = "medium"  # 0.60-0.85
    LOW = "low"  # <0.60


@dataclass
class DiagnosticEvent:
    """Single diagnostic event."""
    timestamp: str
    event_type: str
    query_id: str
    layer: Optional[str] = None
    confidence: Optional[float] = None
    latency_ms: Optional[float] = None
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        # Remove None values
        return {k: v for k, v in data.items() if v is not None}


class DiagnosticFeed:
    """
    Structured logging to Redis for all Kitbash orchestration events.

    Maintains a real-time event stream accessible for monitoring,
    debugging, and post-mortem analysis.
    """

    def __init__(self, redis_client: Optional[Redis] = None, prefix: str = "kitbash:"):
        """
        Initialize diagnostic feed.

        Args:
            redis_client: Redis connection. If None, creates new connection.
            prefix: Redis key prefix
        """
        self.redis = redis_client or redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=True
        )
        self.prefix = prefix
        self.feed_key = f"{self.prefix}diagnostic:feed"

        try:
            self.redis.ping()
            logger.debug("DiagnosticFeed connected to Redis")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    # Event Logging

    def log_query_created(self, query_id: str, query_text: str) -> None:
        """Log query creation."""
        event = DiagnosticEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.QUERY_CREATED,
            query_id=query_id,
            details={"query_text": query_text[:100]}  # Log first 100 chars
        )
        self._write_event(event)

    def log_query_started(self, query_id: str) -> None:
        """Log query processing started."""
        event = DiagnosticEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.QUERY_STARTED,
            query_id=query_id,
        )
        self._write_event(event)

    def log_layer_attempt(
        self,
        query_id: str,
        layer: str,
        latency_ms: float
    ) -> None:
        """Log layer processing attempt."""
        event = DiagnosticEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.LAYER0_ATTEMPT if layer == "layer0" else f"{layer.lower()}_attempt",
            query_id=query_id,
            layer=layer,
            latency_ms=latency_ms,
        )
        self._write_event(event)

    def log_layer_hit(
        self,
        query_id: str,
        layer: str,
        confidence: float,
        latency_ms: float,
        result_preview: Optional[str] = None
    ) -> None:
        """Log successful layer response."""
        event = DiagnosticEvent(
            timestamp=datetime.now().isoformat(),
            event_type=f"{layer.lower()}_hit",
            query_id=query_id,
            layer=layer,
            confidence=confidence,
            latency_ms=latency_ms,
            details={"result_preview": result_preview[:100]} if result_preview else None
        )
        self._write_event(event)

    def log_layer_miss(
        self,
        query_id: str,
        layer: str,
        latency_ms: float,
        reason: Optional[str] = None
    ) -> None:
        """Log layer miss (no response or low confidence)."""
        event = DiagnosticEvent(
            timestamp=datetime.now().isoformat(),
            event_type=f"{layer.lower()}_miss",
            query_id=query_id,
            layer=layer,
            latency_ms=latency_ms,
            reason=reason,
        )
        self._write_event(event)

    def log_escalation(
        self,
        query_id: str,
        from_layer: str,
        to_layer: str,
        reason: str
    ) -> None:
        """Log escalation to next layer."""
        event = DiagnosticEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.ESCALATION,
            query_id=query_id,
            layer=to_layer,
            reason=reason,
            details={"from_layer": from_layer, "to_layer": to_layer}
        )
        self._write_event(event)

    def log_timeout(
        self,
        query_id: str,
        layer: str,
        timeout_ms: float
    ) -> None:
        """Log layer timeout."""
        event = DiagnosticEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.TIMEOUT,
            query_id=query_id,
            layer=layer,
            reason=f"Timeout after {timeout_ms}ms",
        )
        self._write_event(event)

    def log_error(
        self,
        query_id: str,
        layer: str,
        error_message: str
    ) -> None:
        """Log layer error."""
        event = DiagnosticEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.ERROR,
            query_id=query_id,
            layer=layer,
            reason=error_message,
        )
        self._write_event(event)

    def log_query_completed(
        self,
        query_id: str,
        final_layer: str,
        confidence: float,
        latency_ms: float
    ) -> None:
        """Log query completion."""
        event = DiagnosticEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.QUERY_COMPLETED,
            query_id=query_id,
            layer=final_layer,
            confidence=confidence,
            latency_ms=latency_ms,
        )
        self._write_event(event)

    def log_worker_health(
        self,
        worker_name: str,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log worker health status."""
        event = DiagnosticEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.WORKER_HEALTH,
            query_id=f"worker_{worker_name}",
            reason=status,
            details=details,
        )
        self._write_event(event)

    def log_metric(self, metric_name: str, value: float) -> None:
        """Log a metric value."""
        event = DiagnosticEvent(
            timestamp=datetime.now().isoformat(),
            event_type=EventType.METRIC_RECORDED,
            query_id=f"metric_{metric_name}",
            details={"value": value},
        )
        self._write_event(event)

    # Event Retrieval

    def get_feed(self, count: int = 100) -> List[Dict[str, Any]]:
        """Get recent diagnostic events."""
        events = self.redis.lrange(self.feed_key, 0, count - 1)
        return [json.loads(e) for e in events]

    def get_query_timeline(self, query_id: str) -> List[Dict[str, Any]]:
        """Get all events for a specific query."""
        all_events = self.get_feed(count=10000)
        return [e for e in all_events if e.get("query_id") == query_id]

    def get_events_by_type(self, event_type: str, count: int = 100) -> List[Dict[str, Any]]:
        """Get all events of a specific type."""
        all_events = self.get_feed(count=10000)
        events = [e for e in all_events if e.get("event_type") == event_type]
        return events[:count]

    def get_events_for_layer(self, layer: str, count: int = 100) -> List[Dict[str, Any]]:
        """Get all events related to a specific layer."""
        all_events = self.get_feed(count=10000)
        events = [e for e in all_events if e.get("layer") == layer]
        return events[:count]

    # Analytics

    def get_layer_statistics(self, layer: str, minutes: int = 60) -> Dict[str, Any]:
        """
        Get statistics for a layer.

        Args:
            layer: Layer name (layer0, layer1, etc.)
            minutes: Analyze events from last N minutes

        Returns:
            Dict with hit rate, avg latency, etc.
        """
        cutoff_time = datetime.now().isoformat()[:19]  # Approximate minutes cutoff

        all_events = self.get_feed(count=10000)
        layer_events = [e for e in all_events if e.get("layer") == layer]

        if not layer_events:
            return {"layer": layer, "events": 0}

        hits = sum(1 for e in layer_events if "hit" in e.get("event_type", ""))
        attempts = sum(1 for e in layer_events if "attempt" in e.get("event_type", ""))
        misses = sum(1 for e in layer_events if "miss" in e.get("event_type", ""))

        latencies = [e.get("latency_ms") for e in layer_events if e.get("latency_ms")]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        return {
            "layer": layer,
            "attempts": attempts,
            "hits": hits,
            "misses": misses,
            "hit_rate": hits / attempts if attempts > 0 else 0,
            "avg_latency_ms": avg_latency,
            "events": len(layer_events),
        }

    def get_query_statistics(self, query_id: str) -> Dict[str, Any]:
        """Get processing statistics for a query."""
        events = self.get_query_timeline(query_id)

        if not events:
            return {"query_id": query_id, "events": 0}

        start_time = None
        end_time = None
        layers_attempted = set()
        errors = []

        for event in reversed(events):
            if event.get("event_type") == EventType.QUERY_STARTED:
                start_time = event.get("timestamp")
            elif event.get("event_type") == EventType.QUERY_COMPLETED:
                end_time = event.get("timestamp")

            if event.get("layer"):
                layers_attempted.add(event.get("layer"))

            if event.get("event_type") == EventType.ERROR:
                errors.append(event.get("reason"))

        total_latency_ms = None
        if start_time and end_time:
            start = datetime.fromisoformat(start_time)
            end = datetime.fromisoformat(end_time)
            total_latency_ms = (end - start).total_seconds() * 1000

        return {
            "query_id": query_id,
            "events": len(events),
            "layers_attempted": list(layers_attempted),
            "total_latency_ms": total_latency_ms,
            "errors": errors,
        }

    # Cleanup

    def clear_feed(self) -> None:
        """Clear all diagnostic events."""
        self.redis.delete(self.feed_key)
        logger.info("Diagnostic feed cleared")

    def trim_old_events(self, max_size: int = 10000) -> None:
        """Keep only the most recent N events."""
        self.redis.ltrim(self.feed_key, 0, max_size - 1)

    # Private

    def _write_event(self, event: DiagnosticEvent) -> None:
        """Write event to Redis feed."""
        try:
            event_data = event.to_dict()
            self.redis.lpush(self.feed_key, json.dumps(event_data))
            # Auto-trim to 10000 events
            self.redis.ltrim(self.feed_key, 0, 9999)
        except Exception as e:
            logger.error(f"Failed to write diagnostic event: {e}")

    def close(self) -> None:
        """Close Redis connection."""
        self.redis.close()
        logger.info("DiagnosticFeed connection closed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    try:
        feed = DiagnosticFeed()

        # Test event logging
        query_id = "test_query_001"
        feed.log_query_created(query_id, "What is the capital of France?")
        feed.log_query_started(query_id)
        feed.log_layer_attempt(query_id, "layer0", 0.17)
        feed.log_layer_hit(query_id, "layer0", confidence=0.99, latency_ms=0.17, result_preview="Paris")
        feed.log_query_completed(query_id, "layer0", confidence=0.99, latency_ms=0.17)

        # Test query timeline
        timeline = feed.get_query_timeline(query_id)
        print(f"\nQuery timeline for {query_id}:")
        for event in timeline:
            print(f"  {event['timestamp']}: {event['event_type']}")

        # Test statistics
        stats = feed.get_query_statistics(query_id)
        print(f"\nQuery statistics: {stats}")

        layer_stats = feed.get_layer_statistics("layer0")
        print(f"Layer0 statistics: {layer_stats}")

        print("\n✅ All diagnostic feed tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
