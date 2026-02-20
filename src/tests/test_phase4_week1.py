"""
test_phase4_week1.py - Phase 4.1 Week 1 Test Suite

Comprehensive unit and integration tests for:
- metabolism_state.py
- log_analyzer.py
- background_metabolism_cycle.py
- safety_infrastructure.py

Run with: pytest test_phase4_week1.py -v

Test coverage: 32+ tests across 4 components
"""

import pytest
import logging
from typing import List, Dict, Any
import time

# Import components to test
from metabolism_state import (
    MetabolismState,
    PatternSignal,
    CycleSignal,
    CycleType,
    create_test_state,
)
from log_analyzer import (
    LogAnalyzer,
    QueryLogEvent,
    create_test_event,
)
from background_metabolism_cycle import (
    BackgroundMetabolismCycle,
    CycleResult,
    MockLogAnalyzer,
    MockValidators,
)
from safety_infrastructure import (
    EpistemicValidator,
    QuestionAdjustedScorer,
    FactionGate,
    RegressionDetector,
    SafetyChecker,
)

logger = logging.getLogger(__name__)


# ============================================================================
# METABOLISM STATE TESTS
# ============================================================================

class TestMetabolismState:
    """Test MetabolismState class."""
    
    def test_create_test_state(self):
        """Test creating test state."""
        state = create_test_state()
        assert state is not None
        assert state.current_turn == 100
        assert state.baseline_metrics is not None
    
    def test_record_pattern(self):
        """Test recording a pattern."""
        state = create_test_state()
        
        state.record_pattern(
            "pattern_001",
            {"layer_sequence": ["GRAIN", "CARTRIDGE"], "success_rate": 0.92},
            faction="general"
        )
        
        assert "pattern_001" in state.learned_patterns
        assert state.faction_tags["pattern_001"] == "general"
        assert state.pattern_versions["pattern_001"] == 1
    
    def test_mark_epistemically_valid(self):
        """Test marking pattern as valid."""
        state = create_test_state()
        state.record_pattern("p1", {"success_rate": 0.9})
        
        state.mark_epistemically_valid("p1")
        assert "p1" in state.epistemically_valid_patterns
    
    def test_set_question_adjusted_score(self):
        """Test setting question-adjusted score."""
        state = create_test_state()
        state.record_pattern("p1", {"success_rate": 0.9})
        
        state.set_question_adjusted_score("p1", 0.85)
        assert state.question_adjusted_scores["p1"] == 0.85
    
    def test_add_background_signal(self):
        """Test adding background cycle signal."""
        state = create_test_state()
        
        state.add_background_signal("p1", "success", 0.92, {"queries": 100})
        
        assert len(state.background_signals) == 1
        signal = state.background_signals[0]
        assert signal.pattern_id == "p1"
        assert signal.cycle_origin == CycleType.BACKGROUND
    
    def test_add_daydream_signal_contradiction(self):
        """Test adding daydream contradiction signal."""
        state = create_test_state()
        
        state.add_daydream_signal("p1", "contradiction_found", 0.5, {})
        
        assert "p1" in state.daydream_contradictions
        assert len(state.daydream_signals) == 1
    
    def test_is_pattern_valid(self):
        """Test pattern validity check."""
        state = create_test_state()
        state.record_pattern("p1", {"success_rate": 0.9})
        
        # Not valid yet (not epistemically validated)
        assert not state.is_pattern_valid("p1")
        
        # Mark valid
        state.mark_epistemically_valid("p1")
        assert state.is_pattern_valid("p1")
        
        # Flag it
        state.daydream_contradictions.append("p1")
        assert not state.is_pattern_valid("p1")
    
    def test_get_pattern_status(self):
        """Test getting pattern status."""
        state = create_test_state()
        state.record_pattern("p1", {"success_rate": 0.9})
        state.mark_epistemically_valid("p1")
        
        status = state.get_pattern_status("p1")
        
        assert status["pattern_id"] == "p1"
        assert status["exists"] == True
        assert status["epistemically_valid"] == True
        assert status["version"] == 1
    
    def test_clear_signals(self):
        """Test clearing signal queues."""
        state = create_test_state()
        state.add_background_signal("p1", "success", 0.9, {})
        state.add_daydream_signal("p2", "contradiction_found", 0.5, {})
        
        assert len(state.background_signals) > 0
        assert len(state.daydream_signals) > 0
        
        state.clear_signals()
        
        assert len(state.background_signals) == 0
        assert len(state.daydream_signals) == 0
    
    def test_summary(self):
        """Test state summary."""
        state = create_test_state()
        state.record_pattern("p1", {})
        state.mark_epistemically_valid("p1")
        
        summary = state.summary()
        
        assert summary["patterns_learned"] == 1
        assert summary["patterns_valid"] == 1


# ============================================================================
# LOG ANALYZER TESTS
# ============================================================================

class TestQueryLogEvent:
    """Test QueryLogEvent dataclass."""
    
    def test_create_test_event(self):
        """Test creating test event."""
        event = create_test_event()
        
        assert event is not None
        assert event.query_id == "test_q1"
        assert event.confidence == 0.85
        assert event.source_faction == "general"
    
    def test_is_successful(self):
        """Test success check."""
        event = create_test_event()
        
        assert event.is_successful(threshold=0.7) == True
        assert event.is_successful(threshold=0.9) == False
    
    def test_has_unresolved_questions(self):
        """Test question check."""
        event = create_test_event()
        assert event.has_unresolved_questions() == False
        
        event.question_signals["unresolved_question_count"] = 2
        assert event.has_unresolved_questions() == True
    
    def test_has_critical_coupling_violations(self):
        """Test critical violation check."""
        event = create_test_event()
        assert event.has_critical_coupling_violations() == False
        
        event.coupling_deltas.append({
            "layer_a": "L1",
            "layer_b": "L2",
            "severity": "CRITICAL",
            "delta_magnitude": 0.9,
        })
        assert event.has_critical_coupling_violations() == True


class TestLogAnalyzer:
    """Test LogAnalyzer class."""
    
    def test_analyze_events(self):
        """Test batch analysis of events."""
        analyzer = LogAnalyzer(None, None)
        events = [create_test_event(f"q{i}") for i in range(10)]
        
        analysis = analyzer.analyze_events(events)
        
        assert analysis["event_count"] == 10
        assert analysis["success_rate"] == 1.0  # All test events succeed
        assert "faction_distribution" in analysis


# ============================================================================
# BACKGROUND METABOLISM CYCLE TESTS
# ============================================================================

class TestBackgroundMetabolismCycle:
    """Test BackgroundMetabolismCycle class."""
    
    def test_execute_basic(self):
        """Test basic cycle execution."""
        cycle = BackgroundMetabolismCycle(
            MockLogAnalyzer(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
        )
        
        result = cycle.execute(num_events=10)
        
        assert result.success == True
        assert result.events_analyzed == 10
        assert result.cycle_type == "background"
    
    def test_cycle_result_summary(self):
        """Test cycle result summary."""
        cycle = BackgroundMetabolismCycle(
            MockLogAnalyzer(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
        )
        
        result = cycle.execute(num_events=5)
        summary = result.summary()
        
        assert "background cycle" in summary
        assert "5 events" in summary
    
    def test_coupling_analysis(self):
        """Test coupling pattern analysis."""
        cycle = BackgroundMetabolismCycle(
            MockLogAnalyzer(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
        )
        
        result = cycle.execute(num_events=10)
        
        assert "total_deltas" in result.coupling_analysis
        assert "severity_distribution" in result.coupling_analysis
    
    def test_epistemology_analysis(self):
        """Test epistemology analysis."""
        cycle = BackgroundMetabolismCycle(
            MockLogAnalyzer(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
        )
        
        result = cycle.execute(num_events=10)
        
        assert "validation_success_rate" in result.epistemology_analysis
        assert "L0_L1_both_present" in result.epistemology_analysis
    
    def test_question_analysis(self):
        """Test question analysis."""
        cycle = BackgroundMetabolismCycle(
            MockLogAnalyzer(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
        )
        
        result = cycle.execute(num_events=10)
        
        assert "average_questions_per_event" in result.question_analysis
        assert "question_rate" in result.question_analysis
    
    def test_faction_analysis(self):
        """Test faction boundary analysis."""
        cycle = BackgroundMetabolismCycle(
            MockLogAnalyzer(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
        )
        
        result = cycle.execute(num_events=10)
        
        assert "faction_distribution" in result.faction_analysis
        assert result.faction_analysis["faction_separation_clean"] == True


# ============================================================================
# SAFETY INFRASTRUCTURE TESTS
# ============================================================================

class TestEpistemicValidator:
    """Test EpistemicValidator class."""
    
    def test_validate_pattern_valid(self):
        """Test validating a valid pattern."""
        validator = EpistemicValidator()
        
        pattern = {"id": "p1"}
        context = {
            "L0_active": True,
            "L1_active": True,
            "nwp_validation_passed": True,
            "highest_severity": "PASS",
        }
        
        is_valid, reason, severity = validator.validate_pattern(pattern, context)
        
        assert is_valid == True
        assert severity == "PASS"
    
    def test_validate_pattern_critical_violation(self):
        """Test pattern with CRITICAL violation."""
        validator = EpistemicValidator()
        
        pattern = {"id": "p1"}
        context = {
            "L0_active": True,
            "L1_active": True,
            "nwp_validation_passed": False,
            "highest_severity": "CRITICAL",
        }
        
        is_valid, reason, severity = validator.validate_pattern(pattern, context)
        
        assert is_valid == False
        assert severity == "CRITICAL"
    
    def test_list_rules(self):
        """Test listing epistemic rules."""
        validator = EpistemicValidator()
        rules = validator.list_rules()
        
        assert len(rules) >= 5
        assert any(r.rule_name == "L0_L1_foundation" for r in rules)


class TestQuestionAdjustedScorer:
    """Test QuestionAdjustedScorer class."""
    
    def test_score_no_questions(self):
        """Test scoring with no questions."""
        scorer = QuestionAdjustedScorer()
        
        score = scorer.score(
            base_success_rate=0.90,
            unresolved_question_count=0,
            total_queries=100
        )
        
        assert score == pytest.approx(0.90)
    
    def test_score_with_questions(self):
        """Test scoring with unresolved questions."""
        scorer = QuestionAdjustedScorer()
        
        score = scorer.score(
            base_success_rate=0.90,
            unresolved_question_count=10,
            total_queries=100
        )
        
        # question_rate = 10/100 = 0.1
        # adjusted = 0.90 * (1 - 0.1) = 0.81
        assert score == pytest.approx(0.81)
    
    def test_score_from_event(self):
        """Test scoring from event."""
        scorer = QuestionAdjustedScorer()
        event = create_test_event()
        event.confidence = 0.80
        event.question_signals["unresolved_question_count"] = 1
        
        score = scorer.score_from_event(event)
        
        # 1 question = 0.1 penalty, so 0.80 * (1 - 0.1) = 0.72
        assert score == pytest.approx(0.72)


class TestFactionGate:
    """Test FactionGate class."""
    
    def test_valid_factions(self):
        """Test faction validation."""
        gate = FactionGate()
        
        assert gate.is_valid_faction("fiction") == True
        assert gate.is_valid_faction("general") == True
        assert gate.is_valid_faction("experiment") == True
        assert gate.is_valid_faction("unknown") == False
    
    def test_block_fiction_to_general(self):
        """Test blocking fiction→general crystallization."""
        gate = FactionGate()
        
        should_block, reason = gate.block_crystallization("fiction", "general")
        
        assert should_block == True
        assert "Fiction" in reason
    
    def test_allow_general_to_general(self):
        """Test allowing general→general crystallization."""
        gate = FactionGate()
        
        should_block, reason = gate.block_crystallization("general", "general")
        
        assert should_block == False
    
    def test_gate_learned_weights_general_query(self):
        """Test filtering weights for general query."""
        gate = FactionGate()
        
        weights = {
            "general_weight_1": 1.2,
            "fiction_weight_1": 0.8,
            "general_weight_2": 1.1,
        }
        
        filtered = gate.gate_learned_weights(weights, "general")
        
        assert "general_weight_1" in filtered
        assert "general_weight_2" in filtered
        assert "fiction_weight_1" not in filtered
    
    def test_validate_cartridge_loading(self):
        """Test cartridge loading validation."""
        gate = FactionGate()
        
        # General query loading fiction cartridges: INVALID
        valid, reason = gate.validate_cartridge_loading(
            ["physics_fiction.kbc"],
            "general"
        )
        assert valid == False
        
        # General query loading general cartridges: VALID
        valid, reason = gate.validate_cartridge_loading(
            ["physics.kbc"],
            "general"
        )
        assert valid == True


class TestRegressionDetector:
    """Test RegressionDetector class."""
    
    def test_set_baseline(self):
        """Test setting baseline metrics."""
        detector = RegressionDetector()
        
        baseline = {
            "success_rate": 0.85,
            "question_rate": 0.1,
        }
        
        detector.set_baseline(baseline)
        
        assert detector.baseline_metrics == baseline
    
    def test_no_regression(self):
        """Test when no regression occurs."""
        detector = RegressionDetector()
        detector.set_baseline({"success_rate": 0.85})
        
        # Update to same or better
        detector.update_current("success_rate", 0.86)
        
        has_regressed, reason = detector.check_regression()
        
        assert has_regressed == False
    
    def test_detect_regression(self):
        """Test detecting regression."""
        detector = RegressionDetector()
        detector.set_baseline({"success_rate": 0.85})
        
        # Regress by 6% (threshold is 5%)
        detector.update_current("success_rate", 0.799)
        
        has_regressed, reason = detector.check_regression()
        
        assert has_regressed == True
        assert "success_rate" in reason
    
    def test_get_comparison(self):
        """Test getting baseline/current comparison."""
        detector = RegressionDetector()
        detector.set_baseline({"success_rate": 0.85, "question_rate": 0.1})
        detector.update_current("success_rate", 0.82)
        detector.update_current("question_rate", 0.12)
        
        comparison = detector.get_comparison()
        
        assert "success_rate" in comparison
        assert comparison["success_rate"]["baseline"] == 0.85
        assert comparison["success_rate"]["current"] == 0.82


class TestSafetyChecker:
    """Test SafetyChecker composite."""
    
    def test_validate_pattern_all_pass(self):
        """Test pattern validation when all checks pass."""
        checker = SafetyChecker()
        
        pattern = {"id": "p1"}
        event = create_test_event()
        
        result = checker.validate_pattern(pattern, event)
        
        assert result["valid"] == True
        assert "epistemology" in result["checks"]
        assert "questions" in result["checks"]
        assert "faction" in result["checks"]
    
    def test_validate_pattern_epistemology_fail(self):
        """Test pattern validation failing epistemology check."""
        checker = SafetyChecker()
        
        pattern = {"id": "p1"}
        event = create_test_event()
        event.epistemic_context["nwp_validation_passed"] = False
        event.epistemic_context["highest_severity"] = "CRITICAL"
        
        result = checker.validate_pattern(pattern, event)
        
        assert result["valid"] == False


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests across components."""
    
    def test_full_week1_workflow(self):
        """Test complete Week 1 workflow."""
        
        # 1. Create metabolism state
        state = create_test_state()
        
        # 2. Run background cycle
        cycle = BackgroundMetabolismCycle(
            MockLogAnalyzer(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
            metabolism_state=state,
        )
        result = cycle.execute(num_events=10, turn_number=100)
        
        # 3. Verify cycle completed
        assert result.success == True
        assert result.events_analyzed == 10
        
        # 4. Verify state updated
        assert state.current_turn == 100
        
        # 5. Record patterns
        state.record_pattern(
            "p1",
            {"layer_sequence": ["GRAIN", "CARTRIDGE"], "success_rate": 0.92},
            faction="general"
        )
        
        # 6. Run safety checks
        checker = SafetyChecker()
        event = create_test_event()
        validation = checker.validate_pattern({"id": "p1"}, event)
        
        assert validation["valid"] == True
    
    def test_faction_isolation_constraint(self):
        """Test that faction isolation is enforced throughout."""
        
        # Create events with different factions
        fiction_event = create_test_event("q1")
        fiction_event.source_faction = "fiction"
        
        general_event = create_test_event("q2")
        general_event.source_faction = "general"
        
        # Analyze with faction awareness
        analyzer = LogAnalyzer(None, None)
        events = [fiction_event, general_event]
        analysis = analyzer.analyze_events(events)
        
        assert analysis["faction_distribution"]["fiction"] == 1
        assert analysis["faction_distribution"]["general"] == 1
        
        # Gate should block fiction→general
        gate = FactionGate()
        blocked, _ = gate.block_crystallization("fiction", "general")
        assert blocked == True


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance tests for Week 1 components."""
    
    def test_cycle_execution_latency(self):
        """Test that cycle executes within acceptable latency."""
        cycle = BackgroundMetabolismCycle(
            MockLogAnalyzer(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
        )
        
        result = cycle.execute(num_events=100)
        
        # Should complete in <1 second
        assert result.elapsed_ms < 1000
        logger.info(f"Cycle executed in {result.elapsed_ms:.1f}ms")
    
    def test_validator_latency(self):
        """Test that validators are fast."""
        validator = EpistemicValidator()
        
        start = time.time()
        for i in range(100):
            validator.validate_pattern(
                {"id": f"p{i}"},
                {"L0_active": True, "L1_active": True, "nwp_validation_passed": True}
            )
        elapsed_ms = (time.time() - start) * 1000
        
        # 100 validations should be <50ms
        assert elapsed_ms < 50
        logger.info(f"100 validations in {elapsed_ms:.1f}ms")


# ============================================================================
# TEST CONFIGURATION
# ============================================================================

@pytest.fixture(autouse=True)
def setup_logging():
    """Setup logging for tests."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(name)s - %(levelname)s - %(message)s"
    )


if __name__ == "__main__":
    """Run tests with pytest."""
    pytest.main([__file__, "-v", "--tb=short"])
