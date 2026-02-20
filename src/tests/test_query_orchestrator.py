"""
kitbash/tests/test_query_orchestrator.py

Tests for QueryOrchestrator.

Uses lightweight stubs for all dependencies - no Redis, no real engines,
no real triage agent required. Tests cover:

  1. Happy path: single layer hit
  2. Cascade: first layer misses, second hits
  3. Exhaustion: all layers miss → "I don't know."
  4. Engine exception handling (fail-safe cascade)
  5. ESCALATE sentinel behavior
  6. Resonance integration (record + reinforce on repeat)
  7. Turn advancement (one turn per resolved query)
  8. Shannon optional (None = silent skip)
  9. DiagnosticFeed optional (None = no-op)
  10. Metrics accumulation
  11. Unknown engine in layer sequence (skipped, not crashed)
  12. Triage agent failure (safe default applied)
"""

import hashlib
import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, call

# ---- Stub interfaces (mirrors kitbash.interfaces.*) ----------------------
# These stubs allow the test file to run without the full package installed.
# In the real project, replace these with imports from kitbash.interfaces.

@dataclass
class TriageRequest:
    user_query: str
    context: Dict[str, Any]

@dataclass
class TriageDecision:
    layer_sequence: List[str]
    confidence_thresholds: Dict[str, float]
    recommended_cartridges: List[str]
    use_mamba_context: bool
    cache_result: bool
    reasoning: str

@dataclass
class InferenceRequest:
    user_query: str
    context: Optional[Dict[str, Any]] = None
    cartridge_ids: Optional[List[str]] = None

@dataclass
class InferenceResponse:
    answer: Optional[str]
    confidence: float
    sources: List[str]
    latency_ms: float
    engine_name: str

@dataclass
class MambaContextRequest:
    windows: List[str] = field(default_factory=lambda: ["1hour", "1day"])

@dataclass
class MambaContext:
    context_1hour: Dict[str, Any] = field(default_factory=dict)
    context_1day: Dict[str, Any] = field(default_factory=dict)
    context_72hours: Dict[str, Any] = field(default_factory=dict)
    context_1week: Dict[str, Any] = field(default_factory=dict)
    active_topics: List[str] = field(default_factory=list)
    topic_shifts: List[str] = field(default_factory=list)
    hidden_state: Optional[bytes] = None

# Stub classes for metabolism services
class HeartbeatService:
    """Stub for kitbash.metabolism.heartbeat_service.HeartbeatService"""
    def __init__(self, initial_turn: int = 0):
        self._turn_number = initial_turn
        self._is_running = True
    
    @property
    def turn_number(self) -> int:
        return self._turn_number
    
    def pause(self):
        self._is_running = False
    
    def resume(self):
        self._is_running = True
    
    def advance_turn(self):
        self._turn_number += 1

class MetabolismScheduler:
    """Stub for kitbash.metabolism.metabolism_scheduler.MetabolismScheduler"""
    def __init__(self):
        pass
    
    def schedule_background_work(self, *args, **kwargs):
        pass

# ---- Patch kitbash namespace so orchestrator imports resolve ---------------
import sys
import types

def _make_module(name):
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod

# Build stub package tree
for mod_name in [
    "kitbash",
    "kitbash.interfaces",
    "kitbash.interfaces.triage_agent",
    "kitbash.interfaces.inference_engine",
    "kitbash.interfaces.mamba_context_service",
    "kitbash.memory",
    "kitbash.memory.resonance_weights",
    "kitbash.metabolism",
    "kitbash.metabolism.heartbeat_service",
    "kitbash.metabolism.metabolism_scheduler",
]:
    if mod_name not in sys.modules:
        _make_module(mod_name)

# Inject stub classes into interface modules
sys.modules["kitbash.interfaces.triage_agent"].TriageAgent = object
sys.modules["kitbash.interfaces.triage_agent"].TriageRequest = TriageRequest
sys.modules["kitbash.interfaces.triage_agent"].TriageDecision = TriageDecision
sys.modules["kitbash.interfaces.inference_engine"].InferenceEngine = object
sys.modules["kitbash.interfaces.inference_engine"].InferenceRequest = InferenceRequest
sys.modules["kitbash.interfaces.inference_engine"].InferenceResponse = InferenceResponse
sys.modules["kitbash.interfaces.mamba_context_service"].MambaContextService = object
sys.modules["kitbash.interfaces.mamba_context_service"].MambaContextRequest = MambaContextRequest

# Inject stubs for metabolism services
sys.modules["kitbash.metabolism.heartbeat_service"].HeartbeatService = HeartbeatService
sys.modules["kitbash.metabolism.metabolism_scheduler"].MetabolismScheduler = MetabolismScheduler

# Inject real ResonanceWeightService
import importlib.util, os
# resonance_weights.py is in src/memory/, not src/tests/
rws_path = os.path.join(os.path.dirname(__file__), "..", "memory", "resonance_weights.py")
spec = importlib.util.spec_from_file_location("kitbash.memory.resonance_weights", rws_path)
rws_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rws_mod)
sys.modules["kitbash.memory.resonance_weights"] = rws_mod
ResonanceWeightService = rws_mod.ResonanceWeightService

# Now import the orchestrator (all its imports will resolve via stubs above)
# query_orchestrator.py is in src/orchestration/, not src/tests/
import importlib.util
orch_path = os.path.join(os.path.dirname(__file__), "..", "orchestration", "query_orchestrator.py")
spec2 = importlib.util.spec_from_file_location("query_orchestrator", orch_path)
orch_mod = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(orch_mod)

QueryOrchestrator = orch_mod.QueryOrchestrator
QueryResult = orch_mod.QueryResult
LayerAttempt = orch_mod.LayerAttempt
_NoOpDiagnosticFeed = orch_mod._NoOpDiagnosticFeed


# ---------------------------------------------------------------------------
# Stub builders
# ---------------------------------------------------------------------------

def make_engine(name, answer=None, confidence=0.0, raises=False):
    """Build a stub InferenceEngine."""
    class StubEngine:
        engine_name = name
        def query(self, request):
            if raises:
                raise RuntimeError(f"{name} engine exploded")
            return InferenceResponse(
                answer=answer,
                confidence=confidence,
                sources=["src_1"],
                latency_ms=1.0,
                engine_name=name,
            )
    return StubEngine()


def make_triage(sequence, thresholds=None, raises=False):
    """Build a stub TriageAgent."""
    class StubTriage:
        def route(self, request):
            if raises:
                raise RuntimeError("triage exploded")
            return TriageDecision(
                layer_sequence=sequence,
                confidence_thresholds=thresholds or {},
                recommended_cartridges=[],
                use_mamba_context=False,
                cache_result=True,
                reasoning="test routing",
            )
    return StubTriage()


def make_mamba():
    """Build a stub MambaContextService."""
    class StubMamba:
        def get_context(self, request):
            return MambaContext(active_topics=[])
    return StubMamba()


def make_orchestrator(
    sequence=None,
    thresholds=None,
    engines=None,
    resonance=None,
    shannon=None,
    feed=None,
    triage_raises=False,
):
    sequence = sequence or ["GRAIN", "CARTRIDGE", "ESCALATE"]
    engines = engines or {
        "GRAIN": make_engine("GRAIN", answer=None, confidence=0.0),
        "CARTRIDGE": make_engine("CARTRIDGE", answer=None, confidence=0.0),
    }
    return QueryOrchestrator(
        triage_agent=make_triage(sequence, thresholds, raises=triage_raises),
        engines=engines,
        mamba_service=make_mamba(),
        resonance=resonance or ResonanceWeightService(),
        shannon=shannon,
        diagnostic_feed=feed,
    )


def sha256(text):
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


# ---------------------------------------------------------------------------
# 1. Happy path - single layer hit
# ---------------------------------------------------------------------------

class TestHappyPath:

    def test_single_layer_hit_returns_answer(self):
        orch = make_orchestrator(
            sequence=["GRAIN", "ESCALATE"],
            thresholds={"GRAIN": 0.90},
            engines={"GRAIN": make_engine("GRAIN", answer="ATP is energy", confidence=0.95)},
        )
        result = orch.process_query("what is ATP?")
        assert result.answer == "ATP is energy"
        assert result.confidence == pytest.approx(0.95)
        assert result.engine_name == "GRAIN"

    def test_result_has_query_id(self):
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
        )
        result = orch.process_query("test")
        assert len(result.query_id) == 36  # UUID4 format

    def test_layer_results_recorded(self):
        orch = make_orchestrator(
            sequence=["GRAIN"],
            thresholds={"GRAIN": 0.90},
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
        )
        result = orch.process_query("test")
        assert len(result.layer_results) == 1
        assert result.layer_results[0].engine_name == "GRAIN"
        assert result.layer_results[0].passed is True

    def test_triage_reasoning_propagated(self):
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
        )
        result = orch.process_query("test")
        assert result.triage_reasoning == "test routing"

    def test_triage_latency_measured(self):
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
        )
        result = orch.process_query("test")
        assert result.triage_latency_ms >= 0.0

    def test_total_latency_measured(self):
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
        )
        result = orch.process_query("test")
        assert result.total_latency_ms > 0.0


# ---------------------------------------------------------------------------
# 2. Cascade - first miss, second hit
# ---------------------------------------------------------------------------

class TestCascade:

    def test_cascades_to_second_layer(self):
        orch = make_orchestrator(
            sequence=["GRAIN", "CARTRIDGE", "ESCALATE"],
            thresholds={"GRAIN": 0.90, "CARTRIDGE": 0.70},
            engines={
                "GRAIN": make_engine("GRAIN", answer=None, confidence=0.0),
                "CARTRIDGE": make_engine("CARTRIDGE", answer="From cartridge", confidence=0.80),
            },
        )
        result = orch.process_query("test query")
        assert result.answer == "From cartridge"
        assert result.engine_name == "CARTRIDGE"

    def test_both_layers_recorded(self):
        orch = make_orchestrator(
            sequence=["GRAIN", "CARTRIDGE", "ESCALATE"],
            thresholds={"GRAIN": 0.90, "CARTRIDGE": 0.70},
            engines={
                "GRAIN": make_engine("GRAIN", answer=None, confidence=0.0),
                "CARTRIDGE": make_engine("CARTRIDGE", answer="answer", confidence=0.80),
            },
        )
        result = orch.process_query("test")
        assert len(result.layer_results) == 2
        assert result.layer_results[0].engine_name == "GRAIN"
        assert result.layer_results[0].passed is False
        assert result.layer_results[1].engine_name == "CARTRIDGE"
        assert result.layer_results[1].passed is True

    def test_confidence_below_threshold_causes_miss(self):
        """Engine returns an answer but confidence is below threshold - should miss."""
        orch = make_orchestrator(
            sequence=["GRAIN", "ESCALATE"],
            thresholds={"GRAIN": 0.90},
            engines={
                "GRAIN": make_engine("GRAIN", answer="something", confidence=0.50),
            },
        )
        result = orch.process_query("test")
        # Falls through to ESCALATE → exhausted
        assert result.answer == "I don't know."
        assert result.engine_name == "NONE"


# ---------------------------------------------------------------------------
# 3. Exhaustion - all layers miss
# ---------------------------------------------------------------------------

class TestExhaustion:

    def test_exhausted_returns_i_dont_know(self):
        orch = make_orchestrator(
            sequence=["GRAIN", "CARTRIDGE", "ESCALATE"],
            thresholds={"GRAIN": 0.90, "CARTRIDGE": 0.70},
            engines={
                "GRAIN": make_engine("GRAIN", answer=None, confidence=0.0),
                "CARTRIDGE": make_engine("CARTRIDGE", answer=None, confidence=0.0),
            },
        )
        result = orch.process_query("unanswerable query")
        assert result.answer == "I don't know."
        assert result.confidence == 0.0
        assert result.engine_name == "NONE"

    def test_exhausted_does_not_record_resonance(self):
        resonance = ResonanceWeightService()
        orch = make_orchestrator(
            engines={"GRAIN": make_engine("GRAIN")},
            resonance=resonance,
        )
        orch.process_query("unanswerable")
        assert len(resonance.weights) == 0
        assert resonance.current_turn == 1  # turn still advances

    def test_exhausted_still_advances_turn(self):
        resonance = ResonanceWeightService()
        orch = make_orchestrator(resonance=resonance)
        orch.process_query("unanswerable")
        assert resonance.current_turn == 1


# ---------------------------------------------------------------------------
# 4. Engine exception handling
# ---------------------------------------------------------------------------

class TestEngineExceptions:

    def test_exception_skips_to_next_layer(self):
        orch = make_orchestrator(
            sequence=["GRAIN", "CARTRIDGE", "ESCALATE"],
            thresholds={"GRAIN": 0.90, "CARTRIDGE": 0.70},
            engines={
                "GRAIN": make_engine("GRAIN", raises=True),
                "CARTRIDGE": make_engine("CARTRIDGE", answer="fallback", confidence=0.80),
            },
        )
        result = orch.process_query("test")
        assert result.answer == "fallback"
        assert result.engine_name == "CARTRIDGE"

    def test_exception_recorded_in_layer_results(self):
        orch = make_orchestrator(
            sequence=["GRAIN", "ESCALATE"],
            engines={"GRAIN": make_engine("GRAIN", raises=True)},
        )
        result = orch.process_query("test")
        assert result.layer_results[0].error is not None
        assert "exploded" in result.layer_results[0].error

    def test_all_engines_exception_returns_i_dont_know(self):
        orch = make_orchestrator(
            sequence=["GRAIN", "CARTRIDGE", "ESCALATE"],
            engines={
                "GRAIN": make_engine("GRAIN", raises=True),
                "CARTRIDGE": make_engine("CARTRIDGE", raises=True),
            },
        )
        result = orch.process_query("test")
        assert result.answer == "I don't know."


# ---------------------------------------------------------------------------
# 5. ESCALATE sentinel
# ---------------------------------------------------------------------------

class TestEscalateSentinel:

    def test_escalate_stops_cascade_immediately(self):
        """ESCALATE before CARTRIDGE means CARTRIDGE is never tried."""
        orch = make_orchestrator(
            sequence=["GRAIN", "ESCALATE", "CARTRIDGE"],
            thresholds={"GRAIN": 0.90},
            engines={
                "GRAIN": make_engine("GRAIN", answer=None, confidence=0.0),
                "CARTRIDGE": make_engine("CARTRIDGE", answer="should not appear", confidence=0.99),
            },
        )
        result = orch.process_query("test")
        assert result.answer == "I don't know."
        # Only GRAIN was attempted
        assert len(result.layer_results) == 1
        assert result.layer_results[0].engine_name == "GRAIN"


# ---------------------------------------------------------------------------
# 6. Resonance integration
# ---------------------------------------------------------------------------

class TestResonanceIntegration:

    def test_successful_query_records_pattern(self):
        resonance = ResonanceWeightService()
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
            resonance=resonance,
        )
        orch.process_query("what is ATP?")
        expected_hash = sha256("what is ATP?")
        assert expected_hash in resonance.weights

    def test_repeat_query_reinforces_pattern(self):
        resonance = ResonanceWeightService()
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
            resonance=resonance,
        )
        orch.process_query("what is ATP?")
        orch.process_query("what is ATP?")
        expected_hash = sha256("what is ATP?")
        assert resonance.weights[expected_hash].hit_count == 1

    def test_turn_advances_once_per_query(self):
        resonance = ResonanceWeightService()
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
            resonance=resonance,
        )
        orch.process_query("query one")
        orch.process_query("query two")
        orch.process_query("query three")
        assert resonance.current_turn == 3

    def test_resonance_recorded_flagged_in_result(self):
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
        )
        result = orch.process_query("test")
        assert result.resonance_pattern_recorded is True

    def test_failed_query_resonance_not_recorded(self):
        result = make_orchestrator().process_query("unanswerable")
        assert result.resonance_pattern_recorded is False


# ---------------------------------------------------------------------------
# 7. Shannon optional
# ---------------------------------------------------------------------------

class TestShannonIntegration:

    def test_shannon_none_does_not_crash(self):
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
            shannon=None,
        )
        result = orch.process_query("test")
        assert result.answer == "yes"

    def test_shannon_called_on_success(self):
        shannon = MagicMock()
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
            shannon=shannon,
        )
        orch.process_query("what is ATP?")
        shannon.record_phantom_hit.assert_called_once()

    def test_shannon_not_called_on_failure(self):
        shannon = MagicMock()
        orch = make_orchestrator(
            sequence=["GRAIN", "ESCALATE"],
            engines={"GRAIN": make_engine("GRAIN", answer=None, confidence=0.0)},
            shannon=shannon,
        )
        orch.process_query("unanswerable")
        shannon.record_phantom_hit.assert_not_called()

    def test_shannon_exception_does_not_crash_orchestrator(self):
        shannon = MagicMock()
        shannon.record_phantom_hit.side_effect = RuntimeError("Shannon exploded")
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
            shannon=shannon,
        )
        # Should not raise
        result = orch.process_query("test")
        assert result.answer == "yes"


# ---------------------------------------------------------------------------
# 8. DiagnosticFeed optional
# ---------------------------------------------------------------------------

class TestDiagnosticFeedOptional:

    def test_none_feed_uses_noop(self):
        orch = make_orchestrator(feed=None)
        assert isinstance(orch.feed, _NoOpDiagnosticFeed)

    def test_none_feed_does_not_crash(self):
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
            feed=None,
        )
        result = orch.process_query("test")
        assert result.answer == "yes"

    def test_feed_events_called_on_success(self):
        feed = MagicMock()
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
            feed=feed,
        )
        orch.process_query("test")
        feed.log_query_created.assert_called_once()
        feed.log_query_started.assert_called_once()
        feed.log_query_completed.assert_called_once()

    def test_feed_error_logged_on_engine_exception(self):
        feed = MagicMock()
        orch = make_orchestrator(
            sequence=["GRAIN", "ESCALATE"],
            engines={"GRAIN": make_engine("GRAIN", raises=True)},
            feed=feed,
        )
        orch.process_query("test")
        feed.log_error.assert_called()


# ---------------------------------------------------------------------------
# 9. Metrics accumulation
# ---------------------------------------------------------------------------

class TestMetrics:

    def test_queries_total_increments(self):
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
        )
        orch.process_query("q1")
        orch.process_query("q2")
        metrics = orch.get_metrics()
        assert metrics["queries_total"] == 2

    def test_answered_vs_exhausted_counted(self):
        grain_engine = make_engine("GRAIN", answer="yes", confidence=0.95)
        empty_engine = make_engine("GRAIN", answer=None, confidence=0.0)

        orch1 = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": grain_engine},
        )
        orch1.process_query("answered")
        m1 = orch1.get_metrics()
        assert m1["queries_answered"] == 1
        assert m1["queries_exhausted"] == 0

        orch2 = make_orchestrator(
            sequence=["GRAIN", "ESCALATE"],
            engines={"GRAIN": empty_engine},
        )
        orch2.process_query("exhausted")
        m2 = orch2.get_metrics()
        assert m2["queries_answered"] == 0
        assert m2["queries_exhausted"] == 1

    def test_layer_hit_rate_calculated(self):
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
        )
        orch.process_query("q1")
        orch.process_query("q2")
        metrics = orch.get_metrics()
        assert metrics["layer_hit_rates"]["GRAIN"] == pytest.approx(1.0)

    def test_latency_percentiles_present(self):
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
        )
        for _ in range(5):
            orch.process_query("q")
        metrics = orch.get_metrics()
        assert "total_p50_ms" in metrics["latency"]
        assert "total_p95_ms" in metrics["latency"]
        assert "triage_avg_ms" in metrics["latency"]

    def test_resonance_turn_in_metrics(self):
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
        )
        orch.process_query("q1")
        orch.process_query("q2")
        metrics = orch.get_metrics()
        assert metrics["resonance_turn"] == 2


# ---------------------------------------------------------------------------
# 10. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_unknown_engine_in_sequence_is_skipped(self):
        """Engine in layer_sequence but not in engines dict - skip, don't crash."""
        orch = make_orchestrator(
            sequence=["GHOST_ENGINE", "CARTRIDGE", "ESCALATE"],
            thresholds={"CARTRIDGE": 0.70},
            engines={
                "CARTRIDGE": make_engine("CARTRIDGE", answer="fallback", confidence=0.80),
            },
        )
        result = orch.process_query("test")
        assert result.answer == "fallback"

    def test_triage_failure_uses_safe_default(self):
        """Triage exception → safe default GRAIN→CARTRIDGE→ESCALATE."""
        orch = make_orchestrator(
            triage_raises=True,
            engines={
                "GRAIN": make_engine("GRAIN", answer=None, confidence=0.0),
                "CARTRIDGE": make_engine("CARTRIDGE", answer="safe answer", confidence=0.80),
            },
        )
        result = orch.process_query("test")
        assert result.answer == "safe answer"

    def test_empty_query_string_handled(self):
        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": make_engine("GRAIN", answer="yes", confidence=0.95)},
        )
        result = orch.process_query("")
        assert isinstance(result, QueryResult)

    def test_context_passed_through_to_engine(self):
        """Context provided by caller should reach the engine."""
        received_context = {}

        class ContextCapturingEngine:
            engine_name = "GRAIN"
            def query(self, request):
                received_context.update(request.context or {})
                return InferenceResponse(
                    answer="captured", confidence=0.95,
                    sources=[], latency_ms=0.0, engine_name="GRAIN"
                )

        orch = make_orchestrator(
            sequence=["GRAIN"],
            engines={"GRAIN": ContextCapturingEngine()},
        )
        orch.process_query("test", context={"session_id": "abc123"})
        assert received_context.get("session_id") == "abc123"

    def test_hash_is_case_and_whitespace_normalised(self):
        """Same logical query should hash identically regardless of case/whitespace."""
        h1 = QueryOrchestrator._hash_query("What is ATP?")
        h2 = QueryOrchestrator._hash_query("what is atp?")
        h3 = QueryOrchestrator._hash_query("  what is atp?  ")
        assert h1 == h2 == h3
