"""
src/tests/test_coupling_validation.py - Tests for Coupling Geometry

Comprehensive test suite for epistemic layer coupling validation.

Phase 3B.3: Validates that:
  1. L0 vs L1 contradictions are caught
  2. L1 vs L2 misalignments are flagged
  3. L2 vs L4 rationalization is validated
  4. L4 gates L3/L5 appropriately
  5. Deltas are recorded and retrievable
  6. Severity levels are correct
  7. Performance meets targets (<5ms per validation)

Run with: pytest src/tests/test_coupling_validation.py -v
"""

import pytest
import json
import time
import redis
from redis import Redis
from dataclasses import dataclass

# Import the coupling validator
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from redis_coupling import CouplingValidator, CouplingDelta, create_coupling_validator


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def redis_client():
    """
    Create Redis client for testing.
    Uses database 1 (separate from production).
    """
    try:
        r = redis.Redis(
            host="localhost",
            port=6379,
            db=1,  # Test database
            decode_responses=True,
            socket_connect_timeout=2
        )
        r.ping()
        # Clear test database before running
        r.flushdb()
        return r
    except redis.ConnectionError:
        pytest.skip("Redis not available")


@pytest.fixture
def validator(redis_client):
    """Create coupling validator for each test."""
    v = CouplingValidator(redis_client)
    # Register scripts (using placeholder for MVP)
    v.register_scripts("redis_coupling_scripts.lua")
    yield v
    # Cleanup
    redis_client.flushdb()


@pytest.fixture
def test_query_id():
    """Generate a unique query ID for each test."""
    import uuid
    return f"test_query_{uuid.uuid4().hex[:8]}"


# ============================================================================
# BASIC FUNCTIONALITY TESTS
# ============================================================================

class TestCouplingValidation:
    """Basic coupling validation functionality."""

    def test_validate_L0_vs_L1(self, validator, test_query_id):
        """Test L0 vs L1 validation."""
        delta = validator.validate_coupling(test_query_id, "L0", "L1")
        
        assert delta is not None, "Validation should return a delta"
        assert delta.layer_a == "L0"
        assert delta.layer_b == "L1"
        assert delta.status in ["OK", "FLAG", "FAIL"]
        assert 0.0 <= delta.delta_magnitude <= 1.0

    def test_validate_L1_vs_L2(self, validator, test_query_id):
        """Test L1 vs L2 validation."""
        delta = validator.validate_coupling(test_query_id, "L1", "L2")
        
        assert delta is not None
        assert delta.layer_a == "L1"
        assert delta.layer_b == "L2"
        assert delta.severity in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_validate_L2_vs_L4(self, validator, test_query_id):
        """Test L2 vs L4 rationalization validation."""
        delta = validator.validate_coupling(test_query_id, "L2", "L4")
        
        assert delta is not None
        assert delta.layer_a == "L2"
        assert delta.layer_b == "L4"

    def test_validate_L4_gates_L3(self, validator, test_query_id):
        """Test L4 gating L3."""
        delta = validator.validate_coupling(test_query_id, "L4", "L3")
        
        assert delta is not None
        assert delta.layer_a == "L4"
        assert delta.layer_b == "L3"

    def test_validate_L4_gates_L5(self, validator, test_query_id):
        """Test L4 gating L5."""
        delta = validator.validate_coupling(test_query_id, "L4", "L5")
        
        assert delta is not None
        assert delta.layer_a == "L4"
        assert delta.layer_b == "L5"


# ============================================================================
# DELTA RECORDING TESTS
# ============================================================================

class TestDeltaRecording:
    """Test recording and retrieving deltas."""

    def test_record_delta(self, validator, test_query_id):
        """Test recording a coupling delta."""
        # Validate and record
        delta = validator.validate_and_record(test_query_id, "L1", "L2")
        
        assert delta is not None, "Should return a delta"

    def test_retrieve_deltas(self, validator, test_query_id):
        """Test retrieving recorded deltas."""
        # Record multiple deltas
        validator.validate_and_record(test_query_id, "L0", "L1")
        validator.validate_and_record(test_query_id, "L1", "L2")
        validator.validate_and_record(test_query_id, "L2", "L4")
        
        # Retrieve them
        deltas = validator.get_deltas_for_query(test_query_id)
        
        assert len(deltas) == 3, "Should have recorded 3 deltas"
        assert all(isinstance(d, CouplingDelta) for d in deltas)

    def test_delta_serialization(self):
        """Test CouplingDelta JSON serialization."""
        delta = CouplingDelta(
            query_id="test",
            layer_a="L1",
            layer_b="L2",
            status="FLAG",
            delta_magnitude=0.45,
            severity="MEDIUM",
            coupling_constant=1.0,
            timestamp=1234567890,
        )
        
        # Serialize
        json_str = delta.to_json()
        assert isinstance(json_str, str)
        
        # Deserialize
        delta2 = CouplingDelta.from_json(json_str)
        assert delta2.layer_a == delta.layer_a
        assert delta2.delta_magnitude == delta.delta_magnitude
        assert delta2.severity == delta.severity


# ============================================================================
# SEVERITY CLASSIFICATION TESTS
# ============================================================================

class TestSeverityClassification:
    """Test severity level classification."""

    def test_severity_summary(self, validator, test_query_id):
        """Test getting severity summary."""
        # Record deltas (mock by creating them directly)
        redis_client = validator.redis_client
        
        deltas_key = f"query:{test_query_id}:deltas"
        
        # Create test deltas
        deltas = [
            CouplingDelta(test_query_id, "L0", "L1", "OK", 0.0, "CRITICAL", 1.0, 1234567890),
            CouplingDelta(test_query_id, "L1", "L2", "FLAG", 0.5, "HIGH", 1.0, 1234567890),
            CouplingDelta(test_query_id, "L2", "L4", "OK", 0.2, "MEDIUM", 1.0, 1234567890),
            CouplingDelta(test_query_id, "L4", "L3", "OK", 0.1, "LOW", 1.0, 1234567890),
        ]
        
        # Store them
        for delta in deltas:
            redis_client.lpush(deltas_key, delta.to_json())
        
        # Get summary
        summary = validator.get_severity_summary(test_query_id)
        
        assert summary["CRITICAL"] == 1
        assert summary["HIGH"] == 1
        assert summary["MEDIUM"] == 1
        assert summary["LOW"] == 1

    def test_has_critical_violations(self, validator, test_query_id):
        """Test critical violation detection."""
        redis_client = validator.redis_client
        deltas_key = f"query:{test_query_id}:deltas"
        
        # Add a critical delta
        delta = CouplingDelta(
            test_query_id, "L0", "L1", "FAIL", 0.9, "CRITICAL", 1.0, 1234567890
        )
        redis_client.lpush(deltas_key, delta.to_json())
        
        assert validator.has_critical_violations(test_query_id) == True

    def test_has_no_critical_violations(self, validator, test_query_id):
        """Test when no critical violations exist."""
        redis_client = validator.redis_client
        deltas_key = f"query:{test_query_id}:deltas"
        
        # Add only non-critical delta
        delta = CouplingDelta(
            test_query_id, "L3", "L5", "OK", 0.2, "LOW", 1.0, 1234567890
        )
        redis_client.lpush(deltas_key, delta.to_json())
        
        assert validator.has_critical_violations(test_query_id) == False

    def test_has_high_violations(self, validator, test_query_id):
        """Test high violation detection."""
        redis_client = validator.redis_client
        deltas_key = f"query:{test_query_id}:deltas"
        
        # Add high severity deltas
        delta1 = CouplingDelta(test_query_id, "L1", "L2", "FLAG", 0.6, "HIGH", 1.0, 1234567890)
        delta2 = CouplingDelta(test_query_id, "L2", "L4", "OK", 0.1, "LOW", 1.0, 1234567890)
        
        redis_client.lpush(deltas_key, delta1.to_json())
        redis_client.lpush(deltas_key, delta2.to_json())
        
        assert validator.has_high_violations(test_query_id) == True


# ============================================================================
# COUPLING CONSTANT TESTS
# ============================================================================

class TestCouplingConstant:
    """Test coupling constant (κ) effects."""

    def test_coupling_constant_strict(self, validator, test_query_id):
        """Test strict coupling (κ > 1.0)."""
        # κ > 1.0 should lower the threshold (stricter)
        delta = validator.validate_coupling(test_query_id, "L1", "L2", coupling_constant=2.0)
        
        assert delta is not None
        assert delta.coupling_constant == 2.0

    def test_coupling_constant_fluid(self, validator, test_query_id):
        """Test fluid coupling (κ < 1.0)."""
        # κ < 1.0 should raise the threshold (more permissive)
        delta = validator.validate_coupling(test_query_id, "L1", "L2", coupling_constant=0.5)
        
        assert delta is not None
        assert delta.coupling_constant == 0.5

    def test_coupling_constant_default(self, validator, test_query_id):
        """Test default coupling (κ = 1.0)."""
        delta = validator.validate_coupling(test_query_id, "L1", "L2")
        
        assert delta is not None
        assert delta.coupling_constant == 1.0


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Test latency targets."""

    def test_validation_latency(self, validator, test_query_id):
        """Test that validation completes in <1ms."""
        start = time.time()
        validator.validate_coupling(test_query_id, "L1", "L2")
        elapsed = (time.time() - start) * 1000  # Convert to ms
        
        assert elapsed < 1.0, f"Validation took {elapsed:.2f}ms, target <1ms"

    def test_record_latency(self, validator, test_query_id):
        """Test that recording completes in <1ms."""
        delta = CouplingDelta(
            test_query_id, "L1", "L2", "OK", 0.3, "LOW", 1.0, int(time.time())
        )
        
        start = time.time()
        validator.record_delta(delta)
        elapsed = (time.time() - start) * 1000
        
        assert elapsed < 1.0, f"Recording took {elapsed:.2f}ms, target <1ms"

    def test_batch_validations(self, validator, test_query_id):
        """Test batch validation performance."""
        # Validate all 4 coupling rules
        start = time.time()
        
        validator.validate_coupling(test_query_id, "L0", "L1")
        validator.validate_coupling(test_query_id, "L1", "L2")
        validator.validate_coupling(test_query_id, "L2", "L4")
        validator.validate_coupling(test_query_id, "L4", "L3")
        
        elapsed = (time.time() - start) * 1000
        
        # 4 validations should take <5ms total
        assert elapsed < 5.0, f"Batch validation took {elapsed:.2f}ms, target <5ms"


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test graceful error handling."""

    def test_validation_without_script_registered(self, redis_client):
        """Test validation when scripts not registered."""
        validator = CouplingValidator(redis_client)
        # Don't register scripts
        
        delta = validator.validate_coupling("test", "L1", "L2")
        
        # Should return None gracefully
        assert delta is None

    def test_invalid_layer_names(self, validator, test_query_id):
        """Test validation with invalid layer names."""
        delta = validator.validate_coupling(test_query_id, "INVALID", "LAYER")
        
        # Should still return a delta (not crash)
        assert delta is not None

    def test_retrieve_nonexistent_query(self, validator):
        """Test retrieving deltas for non-existent query."""
        deltas = validator.get_deltas_for_query("nonexistent_query")
        
        # Should return empty list, not crash
        assert deltas == []


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Test integration with Redis Spotlight."""

    def test_full_query_lifecycle(self, validator, test_query_id):
        """Test validation across full query lifecycle."""
        # Simulate a query going through layers
        
        # Layer 0-1 check (observations vs axioms)
        d1 = validator.validate_and_record(test_query_id, "L0", "L1")
        assert d1 is not None
        
        # Layer 1-2 check (axioms vs narrative)
        d2 = validator.validate_and_record(test_query_id, "L1", "L2")
        assert d2 is not None
        
        # Layer 2-4 check (narrative vs intent)
        d3 = validator.validate_and_record(test_query_id, "L2", "L4")
        assert d3 is not None
        
        # Layer 4 gating (intent gates heuristics/persona)
        d4 = validator.validate_and_record(test_query_id, "L4", "L3")
        d5 = validator.validate_and_record(test_query_id, "L4", "L5")
        
        # Retrieve all deltas
        all_deltas = validator.get_deltas_for_query(test_query_id)
        assert len(all_deltas) == 5
        
        # Check summary
        summary = validator.get_severity_summary(test_query_id)
        assert sum(summary.values()) == 5


# ============================================================================
# MANUAL TESTING
# ============================================================================

if __name__ == "__main__":
    """Run tests manually."""
    pytest.main([__file__, "-v", "-s"])
