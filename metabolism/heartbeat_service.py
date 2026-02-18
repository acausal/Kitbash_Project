"""
kitbash/metabolism/heartbeat_service.py

HeartbeatService — manages the pause/resume lifecycle for background metabolism.

In Kitbash, background maintenance (Resonance Decay, Analyze Split) must be 
shielded from query execution to protect the sub-millisecond Layer 0 latency.

The QueryOrchestrator calls pause() before firing engines and resume() 
immediately after. This service ensures that if a background cycle was 
interrupted, it saves a minimal checkpoint to resume safely later.

Standardized for Phase 3B Week 4.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class Checkpoint:
    """
    Minimal state required to resume a background cycle.
    """
    turn_number: int
    interrupted_priority: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

class HeartbeatService:
    """
    Coordinates the 'heartbeat' of the system.
    
    Attributes
    ----------
    turn_number : int
        The master system clock. Increments once per resolved query.
    is_running : bool
        True if the background metabolism is currently allowed to execute.
    checkpoint : Optional[Checkpoint]
        Stored state from the last pause event.
    """

    def __init__(self, initial_turn: int = 0):
        self._turn_number = initial_turn
        self._is_running = True
        self._checkpoint: Optional[Checkpoint] = None
        
        logger.info(f"HeartbeatService initialized at turn {self._turn_number}")

    @property
    def turn_number(self) -> int:
        """The current system turn count (Standardized name)."""
        return self._turn_number

    @property
    def current_turn(self) -> int:
        """Alias for turn_number for backward compatibility with Week 2/3 REPL."""
        return self._turn_number

    @property
    def is_running(self) -> bool:
        """Whether background work is currently active."""
        return self._is_running

    def pause(self, priority: Optional[str] = None) -> Dict[str, Any]:
        """
        Save state and pause background work.

        Called when a query arrives. Saves current turn and the last priority
        that was being processed.

        Returns
        -------
        dict
            Checkpoint data (for logging/diagnostics)
        """
        if not self._is_running:
            # Already paused, return existing checkpoint info
            if self._checkpoint:
                return {
                    "turn_number": self._checkpoint.turn_number,
                    "interrupted_priority": self._checkpoint.interrupted_priority,
                    "was_already_paused": True,
                }
            return {"error": "Already paused, no checkpoint"}

        # Save checkpoint
        self._checkpoint = Checkpoint(
            turn_number=self._turn_number,
            interrupted_priority=priority,
        )
        self._is_running = False

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"HeartbeatService.pause(): saved checkpoint at turn {self._turn_number}"
            )

        return {
            "turn_number": self._turn_number,
            "interrupted_priority": priority,
            "was_already_paused": False,
        }

    def resume(self) -> Dict[str, Any]:
        """
        Restore state and resume background work.

        Called when a query completes (typically in finally block).
        Restores from checkpoint and allows background cycle to continue.

        Returns
        -------
        dict
            Information about resumed state
        """
        if self._is_running:
            # Already running, nothing to do
            return {"was_already_running": True, "turn_number": self._turn_number}

        # Clear checkpoint and resume
        checkpoint_data = {
            "turn_number": self._checkpoint.turn_number if self._checkpoint else None,
            "interrupted_priority": (
                self._checkpoint.interrupted_priority if self._checkpoint else None
            ),
        }

        self._checkpoint = None
        self._is_running = True

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"HeartbeatService.resume(): background work resumed at turn {self._turn_number}"
            )

        return {
            "was_already_running": False,
            "checkpoint_data": checkpoint_data,
        }

    def step(self, background_cycle: Optional[Any] = None) -> Dict[str, Any]:
        """
        Execute one step of background work (if running and not paused).

        Called by MetabolismScheduler. If paused, this is a no-op.
        If running, calls background_cycle.run() to do the work.

        Args:
            background_cycle: BackgroundMetabolismCycle instance to call

        Returns:
            Information about what was executed
        """
        if not self._is_running:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("HeartbeatService.step(): paused, skipping background work")
            return {"executed": False, "reason": "paused"}

        if background_cycle is None:
            return {"executed": False, "reason": "no background_cycle provided"}

        try:
            # Run the background cycle
            result = background_cycle.run()

            # Record what priority was just executed (restored from previous implementation)
            if result and isinstance(result, dict) and "priority" in result:
                if self._checkpoint:
                    self._checkpoint.interrupted_priority = result["priority"]

            return {
                "executed": True,
                "turn": self._turn_number,
                "cycle_result": result,
            }
        except Exception as e:
            logger.error(f"HeartbeatService.step(): background cycle failed: {e}")
            return {"executed": False, "error": str(e)}

    def advance_turn(self) -> int:
        """
        Increments the system turn counter.
        
        Called by QueryOrchestrator in Phase 8 (finally block).
        """
        self._turn_number += 1
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"HeartbeatService.advance_turn(): now at turn {self._turn_number}")
        return self._turn_number

    def get_status(self) -> Dict[str, Any]:
        """Returns the full state of the heartbeat for diagnostics."""
        return {
            "is_running": self._is_running,
            "turn_number": self._turn_number,
            "current_turn": self._turn_number,  # Alias
            "has_checkpoint": self._checkpoint is not None,
            "checkpoint": {
                "turn_number": self._checkpoint.turn_number,
                "interrupted_priority": self._checkpoint.interrupted_priority,
            } if self._checkpoint else None
        }