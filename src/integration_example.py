"""
INTEGRATION EXAMPLE: Week 3 Metabolism Components with QueryOrchestrator

This example shows how HeartbeatService, BackgroundMetabolismCycle, and
MetabolismScheduler integrate with the QueryOrchestrator to implement
the pause/resume model.

Pattern: Query arrives → pause background → run query → resume background
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class TriageRequest:
    """Request to routing logic."""
    user_query: str
    system_state: Dict[str, Any]


@dataclass
class TriageDecision:
    """Routing decision."""
    priority: str
    confidence: float
    layer_sequence: list


@dataclass
class InferenceRequest:
    """Request to inference engine."""
    query: str
    context: Dict[str, Any]


@dataclass
class InferenceResponse:
    """Response from inference engine."""
    answer: str
    confidence: float
    metadata: Dict[str, Any]


class QueryOrchestratorWithMetabolism:
    """
    Simplified QueryOrchestrator showing Week 3 integration.

    This is a SKETCH, not the full implementation. It shows:
      1. Pause/resume via HeartbeatService
      2. Background scheduling via MetabolismScheduler
      3. Integration points for triage routing
    """

    def __init__(
        self,
        triage_agent,
        inference_engines: Dict[str, Any],
        mamba_context_service,
        resonance_service,
        heartbeat_service,
        metabolism_scheduler,
    ):
        """
        Initialize orchestrator with metabolism components.

        Args:
            triage_agent: RuleBasedTriageAgent
            inference_engines: Dict mapping layer names to engines
            mamba_context_service: MambaContextService
            resonance_service: ResonanceWeightService
            heartbeat_service: HeartbeatService (Week 3)
            metabolism_scheduler: MetabolismScheduler (Week 3)
        """
        self.triage_agent = triage_agent
        self.inference_engines = inference_engines
        self.mamba_context_service = mamba_context_service
        self.resonance_service = resonance_service
        self.heartbeat_service = heartbeat_service
        self.metabolism_scheduler = metabolism_scheduler

    def process_query(
        self, user_query: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a user query with pause/resume metabolism.

        Integration pattern:
          1. [Phase 1] Schedule background work
          2. [Phase 2] Triage decides routing (background triage also happens here)
          3. [Phase 3] PAUSE background work (heartbeat.pause())
          4. [Phase 4] Execute inference through engines
          5. [Phase 5] RESUME background work (heartbeat.resume())
          6. [Phase 6] Update resonance patterns
          7. [Phase 7] Advance turn counter

        Args:
            user_query: The question/request
            context: Optional context dict

        Returns:
            Dictionary with answer, confidence, metadata
        """
        if context is None:
            context = {}

        result = {
            "user_query": user_query,
            "answer": None,
            "confidence": 0.0,
            "metadata": {},
        }

        # =====================================================================
        # PHASE 1: Check if background work is due (before we pause)
        # =====================================================================
        # This happens every query, so scheduler can track turns
        background_status = self.metabolism_scheduler.step()
        result["background_status_before"] = background_status

        try:
            # =====================================================================
            # PHASE 2: Get Mamba context
            # =====================================================================
            mamba_context = self.mamba_context_service.get_context(user_query)
            context.update(mamba_context or {})

            # =====================================================================
            # PHASE 2b: Triage decision (happens in foreground)
            # =====================================================================
            triage_request = TriageRequest(
                user_query=user_query,
                system_state={
                    "resonance_patterns": self.resonance_service.get_active_patterns(),
                    "turn": self.heartbeat_service.current_turn,
                },
            )
            triage_decision = self.triage_agent.route(triage_request)
            result["triage_decision"] = {
                "priority": triage_decision.priority,
                "confidence": triage_decision.confidence,
            }

            # =====================================================================
            # PHASE 3: PAUSE background work
            # =====================================================================
            # Query has been routed, now we need to run engines.
            # Don't let background work interfere with latency.
            checkpoint = self.heartbeat_service.pause()
            result["heartbeat_paused_at_turn"] = checkpoint["turn_number"]

            # =====================================================================
            # PHASE 4: Execute inference through layer sequence
            # =====================================================================
            for layer_name in triage_decision.layer_sequence:
                if layer_name not in self.inference_engines:
                    continue

                engine = self.inference_engines[layer_name]
                inference_request = InferenceRequest(query=user_query, context=context)

                try:
                    response = engine.query(inference_request)

                    # Check confidence threshold
                    if response.confidence >= triage_decision.confidence:
                        result["answer"] = response.answer
                        result["confidence"] = response.confidence
                        result["winning_layer"] = layer_name
                        result["metadata"].update(response.metadata)
                        break  # Success!

                except Exception as e:
                    # Engine failed, try next layer
                    result["metadata"][f"error_{layer_name}"] = str(e)
                    continue

            # If no layer succeeded, return fallback
            if result["answer"] is None:
                result["answer"] = "I don't know"
                result["confidence"] = 0.0
                result["winning_layer"] = "fallback"

            # =====================================================================
            # PHASE 5: RESUME background work
            # =====================================================================
            # Query is done, background can resume
            resume_result = self.heartbeat_service.resume()
            result["heartbeat_resumed"] = resume_result["was_already_running"] is False

        finally:
            # Ensure we always resume, even on error
            if self.heartbeat_service.checkpoint:
                self.heartbeat_service.resume()

            # =====================================================================
            # PHASE 6: Update resonance patterns (on success)
            # =====================================================================
            if result["answer"] != "I don't know":
                pattern_hash = hash(user_query) % (10**10)
                self.resonance_service.record_pattern(
                    str(pattern_hash),
                    {
                        "query": user_query,
                        "layer": result.get("winning_layer"),
                        "confidence": result["confidence"],
                    },
                )

            # =====================================================================
            # PHASE 7: Advance turn
            # =====================================================================
            # This triggers resonance cleanup via power law decay
            self.heartbeat_service.advance_turn()
            result["current_turn"] = self.heartbeat_service.current_turn

        return result


# ============================================================================
# EXAMPLE: Simulating a few queries
# ============================================================================


def example_usage():
    """
    Show how the metabolism system works over multiple queries.

    Simulates:
      - 10 queries arriving
      - Background work running every 100 turns (never in this example)
      - Heartbeat pausing/resuming for each query
    """
    from unittest.mock import Mock

    # Mock the dependencies
    mock_triage = Mock()
    mock_triage.route.return_value = TriageRequest(
        user_query="test",
        system_state={},
    )
    # Actually set proper return
    mock_triage_decision = Mock()
    mock_triage_decision.priority = "decay"
    mock_triage_decision.confidence = 0.75
    mock_triage_decision.layer_sequence = ["grain", "cartridge"]
    mock_triage.route.return_value = mock_triage_decision

    # Mock engines
    mock_grain_engine = Mock()
    mock_grain_engine.query.return_value = InferenceResponse(
        answer="Carbon is element 6",
        confidence=0.95,
        metadata={"source": "grain", "latency_ms": 0.5},
    )

    mock_mamba = Mock()
    mock_mamba.get_context.return_value = {"context_token": "value"}

    # Import real components
    from heartbeat_service import HeartbeatService
    from background_metabolism_cycle import BackgroundMetabolismCycle
    from metabolism_scheduler import MetabolismScheduler

    # Create real components
    mock_resonance = Mock()
    mock_resonance.weights = {}
    mock_resonance.current_turn = 0
    mock_resonance.compute_weight = Mock(return_value=0.5)
    mock_resonance.get_active_patterns = Mock(return_value={})
    mock_resonance.record_pattern = Mock()
    mock_resonance.advance_turn = Mock()

    heartbeat = HeartbeatService(initial_turn=0)

    mock_background_cycle = Mock()
    mock_background_cycle.run = Mock(return_value={"priority": "decay"})

    scheduler = MetabolismScheduler(mock_background_cycle, heartbeat, background_interval=100)

    # Create orchestrator
    orchestrator = QueryOrchestratorWithMetabolism(
        triage_agent=mock_triage,
        inference_engines={"grain": mock_grain_engine},
        mamba_context_service=mock_mamba,
        resonance_service=mock_resonance,
        heartbeat_service=heartbeat,
        metabolism_scheduler=scheduler,
    )

    # Simulate 10 queries
    print("\n" + "=" * 80)
    print("SIMULATING 10 QUERIES WITH METABOLISM PAUSING")
    print("=" * 80)

    for i in range(10):
        print(f"\n--- Query {i+1} ---")

        result = orchestrator.process_query(f"What is carbon?")

        print(f"  Turn: {result['current_turn']}")
        print(f"  Answer: {result['answer'][:50]}...")
        print(f"  Confidence: {result['confidence']:.2f}")
        print(f"  Heartbeat paused: {result['heartbeat_paused_at_turn']}")
        print(f"  Heartbeat resumed: {result['heartbeat_resumed']}")

        # Check if background was due
        if result["background_status_before"]["cycles_executed"]:
            print(f"  ⚠️  Background work executed this turn!")

    print("\n" + "=" * 80)
    print("FINAL STATUS")
    print("=" * 80)
    print(f"Current turn: {heartbeat.current_turn}")
    print(f"Background cycles completed: {scheduler.background_runs}")
    print(f"Heartbeat running: {heartbeat.is_running}")
    print(f"Resonance patterns recorded: {mock_resonance.record_pattern.call_count}")
    print()


if __name__ == "__main__":
    example_usage()
