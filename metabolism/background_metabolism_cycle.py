"""
BackgroundMetabolismCycle: Coordinates background maintenance work.

Routes background maintenance decisions through RuleBasedTriageAgent, then
executes the appropriate handler (decay, analyze_split, routine, etc).

MVP focuses on "decay" handler (resonance cleanup via advance_turn).
Other handlers are stubbed for Phase 4.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MaintenancePriority(Enum):
    """Priority levels for background maintenance work."""
    DECAY = "decay"  # Clean up low-weight resonance patterns
    ANALYZE_SPLIT = "analyze_split"  # Check for large cartridges
    ROUTINE = "routine"  # General housekeeping
    DAYDREAM = "daydream"  # Test consistency (Phase 4)
    SLEEP = "sleep"  # Consolidate memory (Phase 4)


@dataclass
class BackgroundTriageRequest:
    """Request passed to triage.route_background()."""
    resonance_patterns: Dict[str, Any]  # Active patterns from ResonanceWeightService
    cartridge_stats: Dict[str, Any]  # Stats from CartridgeEngine
    current_turn: int  # Which turn we're on


@dataclass
class BackgroundTriageDecision:
    """Decision returned by triage.route_background()."""
    priority: str  # One of MaintenancePriority values
    reasoning: str  # Why this priority was chosen
    urgency: float  # 0.0-1.0, for Phase 4 scheduling
    estimated_duration_ms: float = 0.0
    parameters: Dict[str, Any] = None  # Priority-specific config


class BackgroundMetabolismCycle:
    """
    Coordinates background metabolism work.

    Called periodically by MetabolismScheduler (every 100 turns or on-demand).
    Routes through RuleBasedTriageAgent to decide what work to do, then
    delegates to appropriate handler.
    """

    def __init__(
        self,
        triage_agent,  # RuleBasedTriageAgent
        resonance_service,  # ResonanceWeightService
        cartridge_engine=None,  # CartridgeEngine (optional, for stats)
    ):
        """
        Initialize background cycle.

        Args:
            triage_agent: RuleBasedTriageAgent for routing decisions
            resonance_service: ResonanceWeightService for decay work
            cartridge_engine: CartridgeEngine (optional, for cartridge stats)
        """
        self.triage_agent = triage_agent
        self.resonance_service = resonance_service
        self.cartridge_engine = cartridge_engine

        # Registry for maintenance handlers (used by Phase 4)
        self.maintenance_registry: Dict[str, Callable] = {
            MaintenancePriority.DECAY.value: self._handle_decay,
            MaintenancePriority.ANALYZE_SPLIT.value: self._handle_analyze_split,
            MaintenancePriority.ROUTINE.value: self._handle_routine,
        }

        self.work_count = 0

    def run(self) -> Dict[str, Any]:
        """
        Execute one background maintenance cycle.

        Called by HeartbeatService.step(). Flow:
          1. Build BackgroundTriageRequest from current system state
          2. Call triage.route_background() to get decision
          3. Look up handler for priority
          4. Execute handler
          5. Return checkpoint state

        Returns:
            Checkpoint data with priority, work done, etc.
        """
        self.work_count += 1

        # Step 1: Build request
        request = self._build_request()

        # Step 2: Get triage decision
        try:
            decision = self.triage_agent.route_background(request)
        except Exception as e:
            logger.error(f"BackgroundMetabolismCycle.run(): triage failed: {e}")
            return {
                "success": False,
                "priority": "unknown",
                "error": str(e),
                "work_number": self.work_count,
            }

        # Step 3: Look up handler
        handler = self.maintenance_registry.get(decision.priority)
        if not handler:
            logger.warning(
                f"BackgroundMetabolismCycle.run(): no handler for {decision.priority}, "
                f"using default"
            )
            handler = self._handle_routine

        # Step 4: Execute handler
        try:
            result = handler(decision)
            result["priority"] = decision.priority
            result["reasoning"] = decision.reasoning
            result["work_number"] = self.work_count

            if logger.isEnabledFor(logging.INFO):
                logger.info(
                    f"BackgroundMetabolismCycle.run() #{self.work_count}: "
                    f"→ {decision.priority} ({decision.reasoning})"
                )

            return result

        except Exception as e:
            logger.error(
                f"BackgroundMetabolismCycle.run(): handler for {decision.priority} failed: {e}"
            )
            return {
                "success": False,
                "priority": decision.priority,
                "error": str(e),
                "work_number": self.work_count,
            }

    def _build_request(self) -> BackgroundTriageRequest:
        """Build BackgroundTriageRequest from current system state."""
        # Get active resonance patterns
        resonance_patterns = {}
        try:
            if hasattr(self.resonance_service, "weights"):
                for pattern_hash, weight_obj in self.resonance_service.weights.items():
                    weight = self.resonance_service.compute_weight(pattern_hash)
                    resonance_patterns[pattern_hash] = {
                        "weight": weight,
                        "hit_count": getattr(weight_obj, "hit_count", 0),
                    }
        except Exception as e:
            logger.warning(f"Failed to get resonance patterns: {e}")

        # Get cartridge stats
        cartridge_stats = {}
        try:
            if self.cartridge_engine and hasattr(self.cartridge_engine, "cartridges"):
                for domain, cartridge in self.cartridge_engine.cartridges.items():
                    # Estimate size in MB (bytes / 1_000_000)
                    size_bytes = len(str(cartridge))  # Rough estimate
                    cartridge_stats[domain] = {"size_mb": size_bytes / 1_000_000}
        except Exception as e:
            logger.warning(f"Failed to get cartridge stats: {e}")

        return BackgroundTriageRequest(
            resonance_patterns=resonance_patterns,
            cartridge_stats=cartridge_stats,
            current_turn=self.resonance_service.current_turn,
        )

    def _handle_decay(self, decision: BackgroundTriageDecision) -> Dict[str, Any]:
        """
        Handle "decay" priority: clean up low-weight resonance patterns.

        Called by run() when triage decision is "decay".
        Advances the resonance turn, which triggers cleanup of patterns
        below the weight threshold (0.001).
        """
        patterns_before = len(self.resonance_service.weights)

        # Advance turn (triggers cleanup of low-weight patterns)
        self.resonance_service.advance_turn()

        patterns_after = len(self.resonance_service.weights)
        patterns_removed = patterns_before - patterns_after

        return {
            "success": True,
            "action": "resonance_advance_turn",
            "patterns_before": patterns_before,
            "patterns_after": patterns_after,
            "patterns_removed": patterns_removed,
            "estimated_duration_ms": decision.estimated_duration_ms,
        }

    def _handle_analyze_split(
        self, decision: BackgroundTriageDecision
    ) -> Dict[str, Any]:
        """
        Handle "analyze_split" priority: analyze cartridges for splitting.

        Stubbed for MVP. Phase 4 will implement actual cartridge analysis
        and splitting logic. For now, just log and return.
        """
        logger.info(
            f"BackgroundMetabolismCycle: analyze_split queued "
            f"(Phase 4 implementation, skipping for MVP)"
        )

        return {
            "success": True,
            "action": "analyze_split",
            "status": "queued_for_phase_4",
            "estimated_duration_ms": decision.estimated_duration_ms,
        }

    def _handle_routine(self, decision: BackgroundTriageDecision) -> Dict[str, Any]:
        """
        Handle "routine" priority: general housekeeping.

        Stubbed for MVP. Phase 4 will implement custom maintenance scripts.
        For now, just log and return.
        """
        logger.info(
            f"BackgroundMetabolismCycle: routine maintenance queued "
            f"(Phase 4 implementation, skipping for MVP)"
        )

        return {
            "success": True,
            "action": "routine",
            "status": "queued_for_phase_4",
            "estimated_duration_ms": decision.estimated_duration_ms,
        }

    def save_checkpoint(self) -> Dict[str, Any]:
        """
        Save cycle state for pause/resume.

        MVP: minimal checkpoint (just work count and turn number).
        Phase 4: can expand to include pending work queue, etc.
        """
        return {
            "work_count": self.work_count,
            "turn_number": self.resonance_service.current_turn,
        }

    def restore_checkpoint(self, checkpoint: Dict[str, Any]) -> None:
        """
        Restore cycle state from checkpoint.

        Args:
            checkpoint: Data from save_checkpoint()
        """
        self.work_count = checkpoint.get("work_count", 0)
        # Note: turn_number is managed by resonance_service, not directly restored

    def get_stats(self) -> Dict[str, Any]:
        """Get background cycle statistics (for REPL/diagnostics)."""
        return {
            "work_cycles_completed": self.work_count,
            "resonance_patterns": len(self.resonance_service.weights),
            "current_turn": self.resonance_service.current_turn,
        }
