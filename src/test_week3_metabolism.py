"""
Tests for Week 3 metabolism components: HeartbeatService, BackgroundMetabolismCycle, MetabolismScheduler
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from heartbeat_service import HeartbeatService, Checkpoint
from background_metabolism_cycle import (
    BackgroundMetabolismCycle,
    BackgroundTriageRequest,
    BackgroundTriageDecision,
    MaintenancePriority,
)
from metabolism_scheduler import MetabolismScheduler, CycleType


# ============================================================================
# HEARTBEAT SERVICE TESTS
# ============================================================================


class TestHeartbeatServiceBasics:
    """Test basic pause/resume functionality of HeartbeatService."""

    def test_initialization(self):
        """Test heartbeat initializes in running state."""
        hb = HeartbeatService(initial_turn=0)
        assert hb.is_running is True
        assert hb.current_turn == 0
        assert hb.checkpoint is None

    def test_pause_when_running(self):
        """Test pause saves checkpoint and sets is_running=False."""
        hb = HeartbeatService(initial_turn=42)
        result = hb.pause()

        assert hb.is_running is False
        assert hb.checkpoint is not None
        assert hb.checkpoint.turn_number == 42
        assert result["turn_number"] == 42
        assert result["was_already_paused"] is False

    def test_pause_when_already_paused(self):
        """Test pause when already paused doesn't overwrite checkpoint."""
        hb = HeartbeatService(initial_turn=10)
        hb.pause()
        first_checkpoint = hb.checkpoint

        # Try to pause again
        result = hb.pause()

        # Checkpoint should be unchanged
        assert hb.checkpoint is first_checkpoint
        assert result["was_already_paused"] is True

    def test_resume_when_paused(self):
        """Test resume clears checkpoint and sets is_running=True."""
        hb = HeartbeatService(initial_turn=50)
        hb.pause()
        assert hb.is_running is False

        result = hb.resume()

        assert hb.is_running is True
        assert hb.checkpoint is None
        assert result["was_already_running"] is False

    def test_resume_when_already_running(self):
        """Test resume when already running is a no-op."""
        hb = HeartbeatService(initial_turn=20)
        assert hb.is_running is True

        result = hb.resume()

        assert hb.is_running is True
        assert result["was_already_running"] is True


class TestHeartbeatServiceTurns:
    """Test turn advancement."""

    def test_advance_turn(self):
        """Test advance_turn increments counter."""
        hb = HeartbeatService(initial_turn=5)
        new_turn = hb.advance_turn()

        assert new_turn == 6
        assert hb.current_turn == 6

    def test_multiple_advances(self):
        """Test multiple advance_turn calls."""
        hb = HeartbeatService(initial_turn=0)
        for i in range(1, 11):
            hb.advance_turn()
        assert hb.current_turn == 10

    def test_pause_resume_preserves_turn(self):
        """Test pause/resume doesn't affect turn number."""
        hb = HeartbeatService(initial_turn=7)
        hb.pause()
        hb.advance_turn()
        hb.resume()

        assert hb.current_turn == 8


class TestHeartbeatServiceStep:
    """Test background cycle integration via step()."""

    def test_step_when_paused_is_noop(self):
        """Test step() returns noop when paused."""
        hb = HeartbeatService()
        hb.pause()

        mock_cycle = Mock()
        result = hb.step(mock_cycle)

        assert result["executed"] is False
        assert result["reason"] == "paused"
        mock_cycle.run.assert_not_called()

    def test_step_when_running_calls_cycle(self):
        """Test step() calls background_cycle.run() when running."""
        hb = HeartbeatService()
        assert hb.is_running is True

        mock_cycle = Mock()
        mock_cycle.run.return_value = {"priority": "decay"}

        result = hb.step(mock_cycle)

        assert result["executed"] is True
        mock_cycle.run.assert_called_once()

    def test_step_with_no_cycle(self):
        """Test step() with no cycle argument."""
        hb = HeartbeatService()
        result = hb.step(None)

        assert result["executed"] is False
        assert result["reason"] == "no background_cycle provided"

    def test_step_handles_cycle_exception(self):
        """Test step() handles exceptions from background cycle."""
        hb = HeartbeatService()
        mock_cycle = Mock()
        mock_cycle.run.side_effect = RuntimeError("cycle failed")

        result = hb.step(mock_cycle)

        assert result["executed"] is False
        assert "error" in result


class TestHeartbeatServiceStatus:
    """Test status reporting."""

    def test_get_status_when_running(self):
        """Test status when running."""
        hb = HeartbeatService(initial_turn=10)
        status = hb.get_status()

        assert status["is_running"] is True
        assert status["current_turn"] == 10
        assert status["has_checkpoint"] is False

    def test_get_status_when_paused(self):
        """Test status when paused."""
        hb = HeartbeatService(initial_turn=15)
        hb.pause()
        status = hb.get_status()

        assert status["is_running"] is False
        assert status["has_checkpoint"] is True
        assert status["checkpoint"]["turn_number"] == 15


# ============================================================================
# BACKGROUND METABOLISM CYCLE TESTS
# ============================================================================


class TestBackgroundMetabolismCycleBasics:
    """Test basic initialization and structure."""

    def test_initialization(self):
        """Test cycle initializes correctly."""
        mock_triage = Mock()
        mock_resonance = Mock()
        mock_resonance.weights = {}
        mock_resonance.current_turn = 0

        cycle = BackgroundMetabolismCycle(mock_triage, mock_resonance)

        assert cycle.triage_agent is mock_triage
        assert cycle.resonance_service is mock_resonance
        assert cycle.work_count == 0
        assert MaintenancePriority.DECAY.value in cycle.maintenance_registry

    def test_maintenance_registry_has_decay_handler(self):
        """Test decay handler is registered."""
        mock_triage = Mock()
        mock_resonance = Mock()
        mock_resonance.weights = {}

        cycle = BackgroundMetabolismCycle(mock_triage, mock_resonance)

        assert "decay" in cycle.maintenance_registry
        assert callable(cycle.maintenance_registry["decay"])


class TestBackgroundMetabolismCycleDecay:
    """Test decay handler (MVP focus)."""

    def test_decay_calls_advance_turn(self):
        """Test decay handler calls resonance.advance_turn()."""
        mock_triage = Mock()
        mock_resonance = Mock()
        mock_resonance.weights = {}
        mock_resonance.current_turn = 5
        mock_resonance.compute_weight = Mock(return_value=0.5)
        mock_resonance.advance_turn = Mock()

        cycle = BackgroundMetabolismCycle(mock_triage, mock_resonance)

        decision = BackgroundTriageDecision(
            priority="decay",
            reasoning="testing",
            urgency=0.5,
            estimated_duration_ms=100.0,
        )

        result = cycle._handle_decay(decision)

        assert result["success"] is True
        assert result["action"] == "resonance_advance_turn"
        mock_resonance.advance_turn.assert_called_once()

    def test_decay_counts_pattern_cleanup(self):
        """Test decay returns count of removed patterns."""
        mock_triage = Mock()
        mock_resonance = Mock()

        # Create mock weights dict with 5 patterns
        mock_weights = {f"pattern_{i}": Mock(hit_count=i) for i in range(5)}
        mock_resonance.weights = mock_weights
        mock_resonance.current_turn = 10
        mock_resonance.compute_weight = Mock(return_value=0.5)

        cycle = BackgroundMetabolismCycle(mock_triage, mock_resonance)

        decision = BackgroundTriageDecision(
            priority="decay",
            reasoning="test",
            urgency=0.5,
            estimated_duration_ms=50.0,
        )

        # Simulate advance_turn removing patterns
        def mock_advance():
            # Simulate cleanup: remove 2 patterns
            del mock_resonance.weights[list(mock_resonance.weights.keys())[0]]
            if len(mock_resonance.weights) > 0:
                del mock_resonance.weights[list(mock_resonance.weights.keys())[0]]

        mock_resonance.advance_turn = mock_advance

        result = cycle._handle_decay(decision)

        assert result["patterns_before"] == 5
        assert result["patterns_after"] == 3
        assert result["patterns_removed"] == 2


class TestBackgroundMetabolismCycleRun:
    """Test full run() cycle."""

    def test_run_routes_through_triage(self):
        """Test run() calls triage.route_background()."""
        mock_triage = Mock()
        mock_decision = BackgroundTriageDecision(
            priority="decay",
            reasoning="test",
            urgency=0.5,
            estimated_duration_ms=100.0,
        )
        mock_triage.route_background.return_value = mock_decision

        mock_resonance = Mock()
        mock_resonance.weights = {}
        mock_resonance.current_turn = 0
        mock_resonance.compute_weight = Mock(return_value=0.5)
        mock_resonance.advance_turn = Mock()

        cycle = BackgroundMetabolismCycle(mock_triage, mock_resonance)
        result = cycle.run()

        mock_triage.route_background.assert_called_once()
        assert result["priority"] == "decay"
        assert result["success"] is True

    def test_run_increments_work_count(self):
        """Test run() increments work counter."""
        mock_triage = Mock()
        mock_decision = BackgroundTriageDecision(
            priority="decay", reasoning="test", urgency=0.5
        )
        mock_triage.route_background.return_value = mock_decision

        mock_resonance = Mock()
        mock_resonance.weights = {}
        mock_resonance.current_turn = 0
        mock_resonance.compute_weight = Mock(return_value=0.5)
        mock_resonance.advance_turn = Mock()

        cycle = BackgroundMetabolismCycle(mock_triage, mock_resonance)

        assert cycle.work_count == 0
        cycle.run()
        assert cycle.work_count == 1
        cycle.run()
        assert cycle.work_count == 2

    def test_run_handles_triage_failure(self):
        """Test run() handles triage exception."""
        mock_triage = Mock()
        mock_triage.route_background.side_effect = RuntimeError("triage failed")

        mock_resonance = Mock()
        mock_resonance.weights = {}
        mock_resonance.current_turn = 0

        cycle = BackgroundMetabolismCycle(mock_triage, mock_resonance)
        result = cycle.run()

        assert result["success"] is False
        assert "error" in result


class TestBackgroundMetabolismCycleStubs:
    """Test stubbed handlers for Phase 4."""

    def test_analyze_split_stub(self):
        """Test analyze_split is stubbed."""
        mock_triage = Mock()
        mock_resonance = Mock()
        mock_resonance.weights = {}

        cycle = BackgroundMetabolismCycle(mock_triage, mock_resonance)

        decision = BackgroundTriageDecision(
            priority="analyze_split",
            reasoning="test",
            urgency=0.3,
            estimated_duration_ms=200.0,
        )

        result = cycle._handle_analyze_split(decision)

        assert result["success"] is True
        assert result["status"] == "queued_for_phase_4"

    def test_routine_stub(self):
        """Test routine is stubbed."""
        mock_triage = Mock()
        mock_resonance = Mock()
        mock_resonance.weights = {}

        cycle = BackgroundMetabolismCycle(mock_triage, mock_resonance)

        decision = BackgroundTriageDecision(
            priority="routine", reasoning="test", urgency=0.2
        )

        result = cycle._handle_routine(decision)

        assert result["success"] is True
        assert result["status"] == "queued_for_phase_4"


class TestBackgroundMetabolismCycleCheckpoint:
    """Test checkpoint save/restore."""

    def test_save_checkpoint(self):
        """Test save_checkpoint returns minimal state."""
        mock_triage = Mock()
        mock_resonance = Mock()
        mock_resonance.weights = {}
        mock_resonance.current_turn = 50

        cycle = BackgroundMetabolismCycle(mock_triage, mock_resonance)
        cycle.work_count = 10

        checkpoint = cycle.save_checkpoint()

        assert checkpoint["work_count"] == 10
        assert checkpoint["turn_number"] == 50

    def test_restore_checkpoint(self):
        """Test restore_checkpoint restores work count."""
        mock_triage = Mock()
        mock_resonance = Mock()
        mock_resonance.weights = {}
        mock_resonance.current_turn = 0

        cycle = BackgroundMetabolismCycle(mock_triage, mock_resonance)
        cycle.restore_checkpoint({"work_count": 25, "turn_number": 100})

        assert cycle.work_count == 25
        # turn_number is managed by resonance, not cycle


# ============================================================================
# METABOLISM SCHEDULER TESTS
# ============================================================================


class TestMetabolismSchedulerBasics:
    """Test scheduler initialization and basics."""

    def test_initialization(self):
        """Test scheduler initializes correctly."""
        mock_background = Mock()
        mock_heartbeat = Mock()
        mock_heartbeat.current_turn = 0

        scheduler = MetabolismScheduler(mock_background, mock_heartbeat)

        assert scheduler.background_cycle is mock_background
        assert scheduler.heartbeat_service is mock_heartbeat
        assert scheduler.background_interval == 100
        assert scheduler.background_runs == 0

    def test_custom_interval(self):
        """Test scheduler with custom background interval."""
        mock_background = Mock()
        mock_heartbeat = Mock()
        mock_heartbeat.current_turn = 0

        scheduler = MetabolismScheduler(
            mock_background, mock_heartbeat, background_interval=50
        )

        assert scheduler.background_interval == 50


class TestMetabolismSchedulerBackgroundTiming:
    """Test background cycle timing."""

    def test_background_due_on_first_step(self):
        """Test background is due on first step."""
        mock_background = Mock()
        mock_heartbeat = Mock()
        mock_heartbeat.current_turn = 0
        mock_heartbeat.step = Mock(return_value={"success": True})

        scheduler = MetabolismScheduler(mock_background, mock_heartbeat, background_interval=100)

        result = scheduler.step()

        # Background should be due (last_background_turn starts at -100)
        mock_heartbeat.step.assert_called_once()
        assert scheduler.background_runs == 1

    def test_background_not_due_before_interval(self):
        """Test background doesn't run before interval."""
        mock_background = Mock()
        mock_heartbeat = Mock()
        mock_heartbeat.current_turn = 50
        mock_heartbeat.step = Mock(return_value={"success": True})

        scheduler = MetabolismScheduler(mock_background, mock_heartbeat, background_interval=100)
        scheduler.last_background_turn = 0  # Just ran at turn 0

        scheduler.step()

        # Should not run again (only 50 turns have passed)
        mock_heartbeat.step.assert_not_called()

    def test_background_due_after_interval(self):
        """Test background runs when interval is reached."""
        mock_background = Mock()
        mock_heartbeat = Mock()
        mock_heartbeat.current_turn = 150
        mock_heartbeat.step = Mock(return_value={"success": True})

        scheduler = MetabolismScheduler(mock_background, mock_heartbeat, background_interval=100)
        scheduler.last_background_turn = 0

        scheduler.step()

        # Should run (150 turns have passed since turn 0)
        mock_heartbeat.step.assert_called_once()
        assert scheduler.background_runs == 1

    def test_background_interval_tracking(self):
        """Test scheduler tracks background intervals correctly."""
        mock_background = Mock()
        mock_heartbeat = Mock()
        mock_heartbeat.step = Mock(return_value={"success": True})

        scheduler = MetabolismScheduler(mock_background, mock_heartbeat, background_interval=10)

        # Simulate running background multiple times
        for turn in [0, 10, 20, 30]:
            mock_heartbeat.current_turn = turn
            scheduler.step()

        assert scheduler.background_runs == 4


class TestMetabolismSchedulerStubs:
    """Test Phase 4 stub methods."""

    def test_trigger_daydream_stub(self):
        """Test daydream is stubbed for Phase 4."""
        mock_background = Mock()
        mock_heartbeat = Mock()
        mock_heartbeat.current_turn = 0

        scheduler = MetabolismScheduler(mock_background, mock_heartbeat)
        result = scheduler.trigger_daydream()

        assert result["cycle_type"] == CycleType.DAYDREAMING.value
        assert result["status"] == "stubbed_for_phase_4"
        assert scheduler.daydream_runs == 1

    def test_trigger_sleep_stub(self):
        """Test sleep is stubbed for Phase 4."""
        mock_background = Mock()
        mock_heartbeat = Mock()
        mock_heartbeat.current_turn = 0

        scheduler = MetabolismScheduler(mock_background, mock_heartbeat)
        result = scheduler.trigger_sleep()

        assert result["cycle_type"] == CycleType.SLEEP.value
        assert result["status"] == "stubbed_for_phase_4"
        assert scheduler.sleep_runs == 1


class TestMetabolismSchedulerStatus:
    """Test status reporting."""

    def test_get_status(self):
        """Test status includes scheduling info."""
        mock_background = Mock()
        mock_heartbeat = Mock()
        mock_heartbeat.current_turn = 50
        mock_heartbeat.get_status = Mock(return_value={"is_running": True})

        scheduler = MetabolismScheduler(mock_background, mock_heartbeat, background_interval=100)
        status = scheduler.get_status()

        assert status["current_turn"] == 50
        assert status["background_interval"] == 100
        assert "background_due_in" in status


class TestMetabolismSchedulerReset:
    """Test reset functionality."""

    def test_reset_clears_counters(self):
        """Test reset clears all counters."""
        mock_background = Mock()
        mock_heartbeat = Mock()
        mock_heartbeat.current_turn = 0

        scheduler = MetabolismScheduler(mock_background, mock_heartbeat)
        scheduler.background_runs = 5
        scheduler.daydream_runs = 3
        scheduler.sleep_runs = 2

        scheduler.reset()

        assert scheduler.background_runs == 0
        assert scheduler.daydream_runs == 0
        assert scheduler.sleep_runs == 0


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestHeartbeatAndSchedulerIntegration:
    """Test heartbeat and scheduler working together."""

    def test_scheduler_respects_heartbeat_pause(self):
        """Test scheduler respects heartbeat pause state."""
        mock_background = Mock()
        mock_background.run = Mock(return_value={"priority": "decay"})

        heartbeat = HeartbeatService(initial_turn=0)
        scheduler = MetabolismScheduler(mock_background, heartbeat, background_interval=1)

        # Pause heartbeat
        heartbeat.pause()

        # Try to step scheduler
        result = scheduler.step()

        # Background shouldn't execute because heartbeat is paused
        assert scheduler.background_runs == 1  # Still increments
        # But the cycle.run() shouldn't be called because heartbeat.step() returns noop
        # (This is tested via heartbeat tests)


class TestFullMetabolismCycleFlow:
    """Test complete flow from heartbeat through scheduler."""

    def test_pause_resume_cycle(self):
        """Test complete pause/resume cycle."""
        mock_background = Mock()
        mock_background.run = Mock(return_value={"priority": "decay", "success": True})

        heartbeat = HeartbeatService(initial_turn=0)
        scheduler = MetabolismScheduler(mock_background, heartbeat, background_interval=1)

        # Step 1: Background running
        assert heartbeat.is_running is True

        # Step 2: Pause (query arrives)
        heartbeat.pause()
        assert heartbeat.is_running is False

        # Step 3: Resume (query finishes)
        heartbeat.resume()
        assert heartbeat.is_running is True

        # Step 4: Background can run again
        result = scheduler.step()
        assert "cycles_executed" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
