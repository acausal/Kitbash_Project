"""
kitbash/tests/test_resonance_weights.py

Tests for ResonanceWeightService (Tier 5 decay).

Covers:
  - Basic weight computation (formula correctness)
  - Pattern lifecycle (record, reinforce, cleanup)
  - Turn advancement and pruning
  - Base vs spacing-sensitive reinforcement
  - Promotion candidate detection
  - Edge cases
"""

import math
import pytest
from kitbash.memory.resonance_weights import (
    ResonanceWeightService,
    ResonanceWeight,
    DEFAULT_INITIAL_STABILITY,
    DEFAULT_STABILITY_GROWTH,
    DEFAULT_CLEANUP_THRESHOLD,
    PROMOTION_HIT_COUNT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_service(**kwargs) -> ResonanceWeightService:
    """Create a service with optional overrides."""
    return ResonanceWeightService(**kwargs)


def approx(value: float, rel: float = 1e-6) -> pytest.approx:
    return pytest.approx(value, rel=rel)


# ---------------------------------------------------------------------------
# 1. Formula correctness
# ---------------------------------------------------------------------------

class TestWeightFormula:
    """Verify weight = e^(-age / S) at known values."""

    def test_weight_at_age_zero(self):
        """Freshly recorded pattern has weight 1.0."""
        svc = make_service()
        svc.record_pattern("p1", {})
        assert svc.compute_weight("p1") == approx(1.0)

    def test_weight_at_age_one(self):
        """After 1 turn with S=3.0: weight = e^(-1/3) ≈ 0.7165."""
        svc = make_service(initial_stability=3.0)
        svc.record_pattern("p1", {})
        svc.advance_turn()
        expected = math.exp(-1 / 3.0)
        assert svc.compute_weight("p1") == approx(expected)

    def test_weight_at_age_three(self):
        """After 3 turns with S=3.0: weight = e^(-1) ≈ 0.3679."""
        svc = make_service(initial_stability=3.0)
        svc.record_pattern("p1", {})
        for _ in range(3):
            svc.advance_turn()
        expected = math.exp(-1.0)
        assert svc.compute_weight("p1") == approx(expected)

    def test_weight_at_age_ten(self):
        """After 10 turns with S=3.0: weight = e^(-10/3) ≈ 0.0357."""
        svc = make_service(initial_stability=3.0)
        svc.record_pattern("p1", {})
        for _ in range(10):
            svc.advance_turn()
        expected = math.exp(-10 / 3.0)
        assert svc.compute_weight("p1") == approx(expected)

    def test_weight_unknown_pattern_is_zero(self):
        """Unknown pattern returns 0.0, not an exception."""
        svc = make_service()
        assert svc.compute_weight("nonexistent") == 0.0

    def test_weight_uses_last_reinforced_turn_not_created_turn(self):
        """Age is measured from last_reinforced_turn, not created_turn."""
        svc = make_service(initial_stability=3.0)
        svc.record_pattern("p1", {})
        # Advance 5 turns
        for _ in range(5):
            svc.advance_turn()
        # Reinforce - age resets to 0
        svc.reinforce_pattern("p1")
        # Weight should be 1.0 (age=0) right after reinforcement,
        # regardless of how many turns have passed since creation.
        assert svc.compute_weight("p1") == approx(1.0)


# ---------------------------------------------------------------------------
# 2. Pattern lifecycle
# ---------------------------------------------------------------------------

class TestPatternLifecycle:

    def test_record_creates_pattern(self):
        svc = make_service()
        svc.record_pattern("p1", {"query": "test"})
        assert "p1" in svc.weights

    def test_record_is_idempotent(self):
        """Recording same hash twice does not overwrite existing entry."""
        svc = make_service(initial_stability=3.0)
        svc.record_pattern("p1", {"query": "first"})
        # Advance a turn so state is non-trivial
        svc.advance_turn()
        original_turn = svc.weights["p1"].last_reinforced_turn
        svc.record_pattern("p1", {"query": "second"})
        assert svc.weights["p1"].last_reinforced_turn == original_turn
        assert svc.weights["p1"].metadata["query"] == "first"

    def test_record_with_custom_initial_stability(self):
        """Pattern recorded with custom S₀ uses that value."""
        svc = make_service(initial_stability=3.0)
        svc.record_pattern("p1", {}, initial_stability=10.0)
        assert svc.weights["p1"].stability == approx(10.0)

    def test_record_metadata_stored(self):
        svc = make_service()
        meta = {"query": "what is ATP?", "entities": ["ATP"]}
        svc.record_pattern("p1", meta)
        assert svc.weights["p1"].metadata == meta

    def test_reinforce_increments_hit_count(self):
        svc = make_service()
        svc.record_pattern("p1", {})
        svc.reinforce_pattern("p1")
        svc.reinforce_pattern("p1")
        assert svc.weights["p1"].hit_count == 2

    def test_reinforce_unknown_pattern_is_silent(self):
        """Reinforcing a nonexistent hash does not raise."""
        svc = make_service()
        svc.reinforce_pattern("ghost")  # should not raise

    def test_reinforce_resets_age_anchor(self):
        """last_reinforced_turn moves to current_turn on reinforcement."""
        svc = make_service()
        svc.record_pattern("p1", {})
        for _ in range(5):
            svc.advance_turn()
        svc.reinforce_pattern("p1")
        assert svc.weights["p1"].last_reinforced_turn == svc.current_turn

    def test_reinforce_grows_stability(self):
        svc = make_service(initial_stability=3.0, stability_growth=2.0)
        svc.record_pattern("p1", {})
        svc.reinforce_pattern("p1")
        assert svc.weights["p1"].stability == approx(6.0)
        svc.reinforce_pattern("p1")
        assert svc.weights["p1"].stability == approx(12.0)


# ---------------------------------------------------------------------------
# 3. Turn advancement and cleanup
# ---------------------------------------------------------------------------

class TestTurnAdvancement:

    def test_advance_increments_turn(self):
        svc = make_service()
        assert svc.current_turn == 0
        svc.advance_turn()
        assert svc.current_turn == 1
        svc.advance_turn()
        assert svc.current_turn == 2

    def test_cleanup_removes_expired_patterns(self):
        """Pattern below cleanup_threshold is removed on advance_turn."""
        # Set a tiny stability so pattern dies quickly
        svc = make_service(initial_stability=0.1, cleanup_threshold=0.001)
        svc.record_pattern("p1", {})
        # e^(-age/0.1) < 0.001  when age > 0.1 * ln(1000) ≈ 0.69 → dies at turn 1
        svc.advance_turn()
        assert "p1" not in svc.weights

    def test_cleanup_does_not_remove_live_patterns(self):
        """Pattern well above threshold survives."""
        svc = make_service(initial_stability=3.0, cleanup_threshold=0.001)
        svc.record_pattern("p1", {})
        svc.advance_turn()
        assert "p1" in svc.weights

    def test_reinforced_pattern_survives_longer(self):
        """Reinforcement extends survival beyond unreinforced baseline."""
        svc = make_service(initial_stability=3.0, stability_growth=2.0, cleanup_threshold=0.001)
        svc.record_pattern("p1", {})
        # Reinforce once - S becomes 6.0, survives ~41 turns
        svc.reinforce_pattern("p1")
        # Advance 25 turns - would kill unreinforced (dies ~21 turns)
        for _ in range(25):
            svc.advance_turn()
        assert "p1" in svc.weights

    def test_multiple_patterns_independent_decay(self):
        """Two patterns with different creation times decay independently."""
        svc = make_service(initial_stability=3.0)
        svc.record_pattern("early", {})
        for _ in range(5):
            svc.advance_turn()
        svc.record_pattern("late", {})
        # "early" is 5 turns older than "late"
        w_early = svc.compute_weight("early")
        w_late = svc.compute_weight("late")
        assert w_late > w_early


# ---------------------------------------------------------------------------
# 4. Active pattern queries
# ---------------------------------------------------------------------------

class TestGetActivePatterns:

    def test_fresh_patterns_are_active(self):
        svc = make_service()
        svc.record_pattern("p1", {})
        svc.record_pattern("p2", {})
        active = svc.get_active_patterns(threshold=0.3)
        assert "p1" in active
        assert "p2" in active

    def test_decayed_patterns_not_active(self):
        svc = make_service(initial_stability=0.5)
        svc.record_pattern("p1", {})
        # Advance enough to drop below 0.3
        # e^(-age/0.5) < 0.3  when age > 0.5 * ln(1/0.3) ≈ 0.60 → gone at turn 1
        svc.advance_turn()
        active = svc.get_active_patterns(threshold=0.3)
        assert "p1" not in active

    def test_threshold_zero_returns_all(self):
        svc = make_service(initial_stability=3.0)
        svc.record_pattern("p1", {})
        svc.record_pattern("p2", {})
        for _ in range(15):
            svc.advance_turn()
        # Both are low-weight but above 0.0
        active = svc.get_active_patterns(threshold=0.0)
        assert "p1" in active
        assert "p2" in active


# ---------------------------------------------------------------------------
# 5. Spacing-sensitive reinforcement
# ---------------------------------------------------------------------------

class TestSpacingSensitive:

    def test_spacing_sensitive_off_by_default(self):
        svc = make_service()
        assert svc.spacing_sensitive is False

    def test_spacing_sensitive_gives_larger_boost_when_decayed(self):
        """
        Two services: same pattern, same reinforcements, different timing.
        In spacing-sensitive mode, the pattern reinforced while nearly faded
        should have higher stability than the one reinforced while still hot.
        """
        # Pattern reinforced immediately (still hot, weight ≈ 1.0)
        svc_hot = make_service(initial_stability=3.0, stability_growth=2.0, spacing_sensitive=True)
        svc_hot.record_pattern("p", {})
        # No delay - reinforce immediately
        svc_hot.reinforce_pattern("p")
        s_hot = svc_hot.weights["p"].stability

        # Pattern reinforced after significant decay
        svc_cold = make_service(initial_stability=3.0, stability_growth=2.0, spacing_sensitive=True)
        svc_cold.record_pattern("p", {})
        # Advance 15 turns - weight is very low
        for _ in range(15):
            svc_cold.current_turn += 1  # bypass advance_turn pruning
        svc_cold.reinforce_pattern("p")
        s_cold = svc_cold.weights["p"].stability

        assert s_cold > s_hot

    def test_spacing_sensitive_base_mode_same_growth(self):
        """In base mode, stability growth is identical regardless of timing."""
        svc1 = make_service(initial_stability=3.0, stability_growth=2.0, spacing_sensitive=False)
        svc1.record_pattern("p", {})
        svc1.reinforce_pattern("p")

        svc2 = make_service(initial_stability=3.0, stability_growth=2.0, spacing_sensitive=False)
        svc2.record_pattern("p", {})
        for _ in range(15):
            svc2.current_turn += 1
        svc2.reinforce_pattern("p")

        assert svc1.weights["p"].stability == approx(svc2.weights["p"].stability)


# ---------------------------------------------------------------------------
# 6. Promotion candidates
# ---------------------------------------------------------------------------

class TestPromotionCandidates:

    def test_no_candidates_below_threshold(self):
        svc = make_service()
        svc.record_pattern("p1", {})
        svc.reinforce_pattern("p1")
        svc.reinforce_pattern("p1")
        # hit_count = 2, PROMOTION_HIT_COUNT = 3 → not yet a candidate
        assert "p1" not in svc.get_promotion_candidates()

    def test_candidate_at_threshold(self):
        svc = make_service()
        svc.record_pattern("p1", {})
        for _ in range(PROMOTION_HIT_COUNT):
            svc.reinforce_pattern("p1")
        assert "p1" in svc.get_promotion_candidates()

    def test_spaced_candidate_has_higher_stability(self):
        """
        In spacing-sensitive mode, a pattern promoted via spaced reinforcements
        has higher stability than one promoted via clustered hits.
        """
        # Clustered: all reinforcements in the same turn
        svc_clustered = make_service(initial_stability=3.0, stability_growth=2.0, spacing_sensitive=True)
        svc_clustered.record_pattern("p", {})
        for _ in range(PROMOTION_HIT_COUNT):
            svc_clustered.reinforce_pattern("p")
        s_clustered = svc_clustered.weights["p"].stability

        # Spaced: reinforcements separated by decay
        svc_spaced = make_service(initial_stability=3.0, stability_growth=2.0, spacing_sensitive=True)
        svc_spaced.record_pattern("p", {})
        for _ in range(PROMOTION_HIT_COUNT):
            for _ in range(10):
                svc_spaced.current_turn += 1  # decay without pruning
            svc_spaced.reinforce_pattern("p")
        s_spaced = svc_spaced.weights["p"].stability

        assert s_spaced > s_clustered


# ---------------------------------------------------------------------------
# 7. Diagnostics
# ---------------------------------------------------------------------------

class TestGetStats:

    def test_stats_empty_service(self):
        svc = make_service()
        stats = svc.get_stats()
        assert stats["current_turn"] == 0
        assert stats["total_patterns"] == 0
        assert stats["active_patterns"] == 0
        assert stats["cruft_ratio"] == 0.0
        assert stats["top_patterns"] == []

    def test_stats_reflects_pattern_state(self):
        svc = make_service(initial_stability=3.0)
        svc.record_pattern("p1", {"query": "alpha"})
        svc.record_pattern("p2", {"query": "beta"})
        stats = svc.get_stats()
        assert stats["total_patterns"] == 2
        assert stats["active_patterns"] == 2  # both fresh
        assert len(stats["top_patterns"]) == 2

    def test_cruft_ratio_after_decay(self):
        """After decay, cruft ratio increases."""
        svc = make_service(initial_stability=3.0)
        svc.record_pattern("p1", {})
        svc.record_pattern("p2", {})
        # Advance enough that at least one drops below 0.3
        for _ in range(5):
            svc.advance_turn()
        stats = svc.get_stats()
        # At age=5 with S=3.0: e^(-5/3) ≈ 0.19 → below 0.3 threshold
        assert stats["cruft_ratio"] > 0.0


# ---------------------------------------------------------------------------
# 8. Integration scenario
# ---------------------------------------------------------------------------

class TestIntegrationScenario:

    def test_topic_resurfaces_after_fading(self):
        """
        Simulate a topic mentioned early, fading, then resurfacing.
        After resurfacing, weight should be 1.0 (just reinforced).
        Pattern should be a promotion candidate if reinforced enough times.
        """
        svc = make_service(initial_stability=3.0, stability_growth=2.0)

        # Turn 0: topic introduced
        svc.record_pattern("PLA_material", {"query": "PLA filament"})
        assert svc.compute_weight("PLA_material") == approx(1.0)

        # Turns 1–10: topic fades
        for _ in range(10):
            svc.advance_turn()
        weight_faded = svc.compute_weight("PLA_material")
        assert weight_faded < 0.1

        # Turn 11: topic resurfaces → reinforce
        svc.reinforce_pattern("PLA_material")
        assert svc.compute_weight("PLA_material") == approx(1.0)

        # Stability has grown: pattern will now last longer
        assert svc.weights["PLA_material"].stability == approx(6.0)
        assert svc.weights["PLA_material"].hit_count == 1

        # Resurface twice more → promotion candidate
        svc.reinforce_pattern("PLA_material")
        svc.reinforce_pattern("PLA_material")
        assert "PLA_material" in svc.get_promotion_candidates()

    def test_orchestrator_usage_pattern(self):
        """
        Simulate the QueryOrchestrator call sequence:
          1. record_pattern on successful answer
          2. advance_turn after final answer returned
          3. reinforce_pattern on repeat topic
        """
        svc = make_service()

        # Query 1 resolved: record and advance
        svc.record_pattern("hash_abc", {"query": "what is ATP?"})
        svc.advance_turn()
        assert svc.current_turn == 1

        # Query 2 on different topic: advance
        svc.record_pattern("hash_def", {"query": "explain glycolysis"})
        svc.advance_turn()
        assert svc.current_turn == 2

        # Query 3: ATP topic returns → reinforce
        svc.reinforce_pattern("hash_abc")
        svc.advance_turn()
        assert svc.current_turn == 3
        assert svc.weights["hash_abc"].hit_count == 1
        # Reinforced at turn 2, advance_turn called after → age=1 when we check
        # weight = e^(-1 / S) where S = initial_stability (3.0) * stability_growth (2.0) = 6.0
        expected = math.exp(-1 / 6.0)
        assert svc.compute_weight("hash_abc") == approx(expected)
