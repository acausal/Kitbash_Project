"""
kitbash/orchestration/query_orchestrator.py

QueryOrchestrator - the single external entry point for user queries.

Coordinates:
  1. Background work scheduling (every 100 turns)
  2. Mamba context retrieval
  3. Triage routing decision (also routes background work)
  4. PAUSE background work (heartbeat.pause())
  5. Serial engine cascade (fail-safe: exceptions skip to next layer)
  6. RESUME background work (heartbeat.resume())
  7. Resonance pattern recording
  8. Shannon phantom hit recording (optional)
  9. DiagnosticFeed logging (optional, degrades gracefully if Redis down)
  10. Advance turn counter

Turn definition: one completed query resolution.
advance_turn() fires after a final answer is returned - not on every
message exchange during clarification.

Week 3 Integration (Heartbeat & Metabolism):
  - HeartbeatService pauses/resumes background work
  - MetabolismScheduler coordinates timing of background cycles
  - BackgroundMetabolismCycle handles maintenance work
  - Pause happens AFTER triage (before engines) to allow background routing
  - Resume happens in finally block (ensures cleanup on error)

Usage:
    orchestrator = QueryOrchestrator(
        triage_agent=RuleBasedTriageAgent(),
        engines={
            "GRAIN": grain_engine,
            "CARTRIDGE": cartridge_engine,
            "BITNET": bitnet_engine,
        },
        mamba_service=MockMambaService(),
        resonance=ResonanceWeightService(),
        heartbeat=HeartbeatService(),                    # Week 3
        metabolism_scheduler=MetabolismScheduler(...),   # Week 3
        shannon=shannon_orchestrator,   # optional
        diagnostic_feed=feed,           # optional
    )

    result = orchestrator.process_query("what is ATP?", context={})
"""

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from kitbash.interfaces.triage_agent import TriageAgent, TriageRequest, TriageDecision
from kitbash.interfaces.inference_engine import InferenceEngine, InferenceRequest, InferenceResponse
from kitbash.interfaces.mamba_context_service import MambaContextService, MambaContextRequest
from kitbash.memory.resonance_weights import ResonanceWeightService
from kitbash.metabolism.heartbeat_service import HeartbeatService  # Week 3
from kitbash.metabolism.metabolism_scheduler import MetabolismScheduler  # Week 3

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    """
    Final result returned to the caller.

    Fields
    ------
    query_id : str
        UUID for this query resolution. Matches DiagnosticFeed events.
    answer : Optional[str]
        The response text. None only if all layers were exhausted.
    confidence : float
        Confidence of the winning engine, or 0.0 if no answer.
    engine_name : str
        Which engine produced the answer, or "NONE" if exhausted.
    layer_results : List[LayerAttempt]
        Full record of every layer attempted (confidence + latency).
        Empty only on catastrophic failure.
    triage_reasoning : str
        The triage agent's explanation for the chosen layer sequence.
    triage_latency_ms : float
        Time taken by the triage decision alone.
    total_latency_ms : float
        Wall-clock time for the entire process_query() call.
    resonance_pattern_recorded : bool
        Whether this query was recorded to ResonanceWeightService.
    """
    query_id: str
    answer: Optional[str]
    confidence: float
    engine_name: str
    layer_results: List["LayerAttempt"]
    triage_reasoning: str
    triage_latency_ms: float
    total_latency_ms: float
    resonance_pattern_recorded: bool


@dataclass
class LayerAttempt:
    """
    Record of a single engine attempt during cascade.

    Fields
    ------
    engine_name : str
        Name of the engine tried.
    confidence : float
        Confidence returned (0.0 if exception or no answer).
    threshold : float
        The confidence threshold that was required.
    passed : bool
        True if confidence >= threshold and answer was non-None.
    latency_ms : float
        Engine query latency.
    error : Optional[str]
        Exception message if the engine threw, else None.
    """
    engine_name: str
    confidence: float
    threshold: float
    passed: bool
    latency_ms: float
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# No-op diagnostic feed (used when real feed unavailable)
# ---------------------------------------------------------------------------

class _NoOpDiagnosticFeed:
    """
    Silent stand-in for DiagnosticFeed when Redis is unavailable.
    Implements the same method signatures so the orchestrator
    never needs to branch on feed availability.
    """
    def log_query_created(self, *a, **kw): pass
    def log_query_started(self, *a, **kw): pass
    def log_layer_attempt(self, *a, **kw): pass
    def log_layer_hit(self, *a, **kw): pass
    def log_layer_miss(self, *a, **kw): pass
    def log_escalation(self, *a, **kw): pass
    def log_error(self, *a, **kw): pass
    def log_query_completed(self, *a, **kw): pass
    def log_metric(self, *a, **kw): pass


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class QueryOrchestrator:
    """
    Main coordinator for user-facing queries.

    Parameters
    ----------
    triage_agent : TriageAgent
        Decides which engines to try and in what order.
    engines : Dict[str, InferenceEngine]
        Map of engine name → engine. Keys must match what TriageDecision
        layer_sequence produces (e.g. "GRAIN", "CARTRIDGE", "BITNET").
    mamba_service : MambaContextService
        Provides temporal context. MockMambaService is fine for MVP.
    resonance : ResonanceWeightService
        Records and ages query patterns. Required.
    shannon : optional
        ShannonGrainOrchestrator instance. If None, phantom hit recording
        is silently skipped.
    diagnostic_feed : optional
        DiagnosticFeed instance. If None (or if Redis is down at construction
        time), falls back to _NoOpDiagnosticFeed - queries still process.
    """

    # Default confidence thresholds used when a layer appears in the sequence
    # but has no entry in TriageDecision.confidence_thresholds.
    FALLBACK_THRESHOLDS: Dict[str, float] = {
        "GRAIN":     0.90,
        "CARTRIDGE": 0.70,
        "BITNET":    0.75,
        "SPECIALIST": 0.65,
        "LLM":       0.0,
    }

    # The sentinel layer name that signals "give up, no engine can answer".
    ESCALATE_SENTINEL = "ESCALATE"

    def __init__(
        self,
        triage_agent: TriageAgent,
        engines: Dict[str, InferenceEngine],
        mamba_service: MambaContextService,
        resonance: ResonanceWeightService,
        heartbeat: Optional[HeartbeatService] = None,  # Week 3
        metabolism_scheduler: Optional[MetabolismScheduler] = None,  # Week 3
        shannon=None,
        diagnostic_feed=None,
    ) -> None:
        self.triage_agent = triage_agent
        self.engines = engines
        self.mamba_service = mamba_service
        self.resonance = resonance
        self.shannon = shannon

        # Week 3: Metabolism components (optional for backward compatibility)
        self.heartbeat = heartbeat or HeartbeatService(initial_turn=0)
        self.metabolism_scheduler = metabolism_scheduler

        # Wrap the feed: use no-op if None or if the provided feed is broken.
        self.feed = self._init_feed(diagnostic_feed)

        # Cumulative session metrics (inspectable from REPL).
        self._metrics: Dict[str, Any] = {
            "queries_total": 0,
            "queries_answered": 0,
            "queries_exhausted": 0,
            "layer_hits": {},       # engine_name → count
            "layer_attempts": {},   # engine_name → count
            "triage_latencies_ms": [],
            "total_latencies_ms": [],
            "heartbeat_pauses": 0,  # Week 3: track pauses
            "metabolism_cycles_run": 0,  # Week 3: track background work
        }

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def process_query(
        self,
        user_query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> QueryResult:
        """
        Process a user query through the full orchestration pipeline.

        Week 3 Flow:
          1. Check if background work is due (scheduler.step())
          2. Get Mamba context
          3. Triage decision (routes foreground + background work)
          4. PAUSE background work (heartbeat.pause()) - before engines
          5. Execute inference cascade
          6. RESUME background work (heartbeat.resume()) - in finally
          7. Update resonance patterns
          8. Advance turn counter

        This is the single external entry point for user-facing queries.
        Do not call engine.query() directly in production code - go through here.

        Parameters
        ----------
        user_query : str
            Raw query text from the user or REPL.
        context : dict, optional
            Caller-supplied context. Will be merged with Mamba context.
            Can include: session_id, user_id, conversation_history, etc.

        Returns
        -------
        QueryResult
            Always returns a result. If all layers fail, answer is
            "I don't know." and confidence is 0.0.
        """
        query_id = str(uuid.uuid4())
        total_start = time.perf_counter()
        context = context or {}

        self.feed.log_query_created(query_id, user_query)
        self.feed.log_query_started(query_id)

        # =====================================================================
        # PHASE 1: Check if background work is due (Week 3)
        # =====================================================================
        background_status = {}
        if self.metabolism_scheduler:
            try:
                background_status = self.metabolism_scheduler.step()
                if background_status.get("cycles_executed"):
                    self._metrics["metabolism_cycles_run"] += 1
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"QueryOrchestrator: background status: {background_status}"
                    )
            except Exception as e:
                logger.warning(f"Metabolism scheduler failed: {e}")
                self.feed.log_error(query_id, "METABOLISM_SCHEDULER", str(e))

        # =====================================================================
        # PHASE 2: Mamba context
        # =====================================================================
        mamba_context = self._get_mamba_context(user_query, context)
        context["mamba_context"] = mamba_context

        # =====================================================================
        # PHASE 3: Triage (also routes background work)
        # =====================================================================
        triage_start = time.perf_counter()
        decision = self._get_triage_decision(user_query, context, query_id)
        triage_latency = (time.perf_counter() - triage_start) * 1000

        logger.debug(
            "Triage decision for %s: %s (%.2fms)",
            query_id, decision.layer_sequence, triage_latency
        )

        # =====================================================================
        # PHASE 4: PAUSE background work (Week 3) - before engines
        # =====================================================================
        heartbeat_checkpoint = {}
        if self.heartbeat:
            try:
                heartbeat_checkpoint = self.heartbeat.pause()
                self._metrics["heartbeat_pauses"] += 1
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Heartbeat paused: {heartbeat_checkpoint}")
            except Exception as e:
                logger.warning(f"Heartbeat pause failed: {e}")
                self.feed.log_error(query_id, "HEARTBEAT_PAUSE", str(e))

        try:
            # ===================================================================
            # PHASE 5: Engine cascade
            # ===================================================================
            layer_results: List[LayerAttempt] = []
            winning_response: Optional[InferenceResponse] = None

            for layer_name in decision.layer_sequence:

                # ESCALATE sentinel - give up cleanly.
                if layer_name == self.ESCALATE_SENTINEL:
                    logger.info("Query %s reached ESCALATE sentinel.", query_id)
                    break

                # Unknown engine - log and skip rather than crash.
                if layer_name not in self.engines:
                    logger.warning(
                        "Layer %s in triage sequence but not in engines dict - skipping.",
                        layer_name
                    )
                    continue

                threshold = decision.confidence_thresholds.get(
                    layer_name,
                    self.FALLBACK_THRESHOLDS.get(layer_name, 0.5)
                )

                attempt, response = self._attempt_layer(
                    layer_name, threshold, user_query, context, decision, query_id
                )
                layer_results.append(attempt)
                self._record_layer_metric(layer_name, attempt)

                if attempt.passed:
                    winning_response = response
                    break

                # Log escalation to next layer (skip if this was the last).
                next_layers = [
                    l for l in decision.layer_sequence[
                        decision.layer_sequence.index(layer_name) + 1:
                    ]
                    if l != self.ESCALATE_SENTINEL
                ]
                if next_layers:
                    self.feed.log_escalation(
                        query_id,
                        from_layer=layer_name,
                    to_layer=next_layers[0],
                    reason=f"confidence {attempt.confidence:.2f} < threshold {threshold:.2f}"
                    if not attempt.error else f"engine error: {attempt.error}",
                )

            # ===================================================================
            # PHASE 6: Build result
            # ===================================================================
            total_latency = (time.perf_counter() - total_start) * 1000

            if winning_response and winning_response.answer:
                answer = winning_response.answer
                confidence = winning_response.confidence
                engine_name = winning_response.engine_name

                # Record pattern to resonance (before advancing turn).
                pattern_hash = self._hash_query(user_query)
                existing = pattern_hash in self.resonance.weights
                if existing:
                    self.resonance.reinforce_pattern(pattern_hash)
                else:
                    self.resonance.record_pattern(
                        pattern_hash,
                        metadata={
                            "query": user_query[:200],
                            "engine": engine_name,
                            "query_id": query_id,
                        },
                    )
                pattern_recorded = True

                # Shannon phantom hit (optional integration).
                if self.shannon is not None:
                    self._record_phantom_hit(winning_response, user_query)

                self.feed.log_query_completed(
                    query_id, engine_name, confidence, total_latency
                )
                self._metrics["queries_answered"] += 1

            else:
                answer = "I don't know."
                confidence = 0.0
                engine_name = "NONE"
                pattern_recorded = False
                self.feed.log_query_completed(query_id, "NONE", 0.0, total_latency)
                self._metrics["queries_exhausted"] += 1

            # Update top-level metrics.
            self._metrics["queries_total"] += 1
            self._metrics["triage_latencies_ms"].append(triage_latency)
            self._metrics["total_latencies_ms"].append(total_latency)

            # Log aggregate metrics to feed.
            self.feed.log_metric("triage_latency_ms", triage_latency)
            self.feed.log_metric("total_latency_ms", total_latency)

            return QueryResult(
                query_id=query_id,
                answer=answer,
                confidence=confidence,
                engine_name=engine_name,
                layer_results=layer_results,
                triage_reasoning=decision.reasoning,
                triage_latency_ms=triage_latency,
                total_latency_ms=total_latency,
                resonance_pattern_recorded=pattern_recorded,
            )

        finally:
            # ===================================================================
            # PHASE 7: RESUME background work (Week 3) - in finally
            # ===================================================================
            if self.heartbeat:
                try:
                    resume_result = self.heartbeat.resume()
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Heartbeat resumed: {resume_result}")
                except Exception as e:
                    logger.warning(f"Heartbeat resume failed: {e}")
                    self.feed.log_error(query_id, "HEARTBEAT_RESUME", str(e))

            # ===================================================================
            # PHASE 8: Advance turn counter
            # ===================================================================
            if self.heartbeat:
                try:
                    new_turn = self.heartbeat.advance_turn()
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Advance turn: now at turn {new_turn}")
                except Exception as e:
                    logger.warning(f"Heartbeat advance_turn failed: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """
        Return session-level performance metrics.

        Used by the REPL 'resonance' and 'metabolism' commands, and by
        test_week2.py for latency verification.

        Returns a snapshot dict - not a live reference.
        """
        lats = self._metrics["total_latencies_ms"]
        triage_lats = self._metrics["triage_latencies_ms"]

        def percentile(data, p):
            if not data:
                return 0.0
            sorted_data = sorted(data)
            idx = int(len(sorted_data) * p / 100)
            return sorted_data[min(idx, len(sorted_data) - 1)]

        snapshot = {
            "queries_total": self._metrics["queries_total"],
            "queries_answered": self._metrics["queries_answered"],
            "queries_exhausted": self._metrics["queries_exhausted"],
            "answer_rate": (
                self._metrics["queries_answered"] / self._metrics["queries_total"]
                if self._metrics["queries_total"] > 0 else 0.0
            ),
            "latency": {
                "total_p50_ms": percentile(lats, 50),
                "total_p95_ms": percentile(lats, 95),
                "total_p99_ms": percentile(lats, 99),
                "total_avg_ms": sum(lats) / len(lats) if lats else 0.0,
                "triage_p50_ms": percentile(triage_lats, 50),
                "triage_p95_ms": percentile(triage_lats, 95),
                "triage_avg_ms": sum(triage_lats) / len(triage_lats) if triage_lats else 0.0,
            },
            "layer_hits": dict(self._metrics["layer_hits"]),
            "layer_attempts": dict(self._metrics["layer_attempts"]),
            "layer_hit_rates": {
                engine: (
                    self._metrics["layer_hits"].get(engine, 0) /
                    self._metrics["layer_attempts"][engine]
                )
                for engine in self._metrics["layer_attempts"]
                if self._metrics["layer_attempts"][engine] > 0
            },
            "resonance_turn": self.resonance.current_turn,
            "resonance_active_patterns": len(
                self.resonance.get_active_patterns(threshold=0.3)
            ),
            # Week 3: Metabolism metrics
            "heartbeat_pauses": self._metrics["heartbeat_pauses"],
            "metabolism_cycles_run": self._metrics["metabolism_cycles_run"],
            "heartbeat_status": self.heartbeat.get_status() if self.heartbeat else None,
            "metabolism_scheduler_status": (
                self.metabolism_scheduler.get_status() 
                if self.metabolism_scheduler else None
            ),
        }
        return snapshot

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _get_mamba_context(self, user_query: str, context: Dict) -> Any:
        """Retrieve Mamba context. Returns None on failure (non-fatal)."""
        try:
            req = MambaContextRequest()
            return self.mamba_service.get_context(req)
        except Exception as e:
            logger.warning("Mamba context retrieval failed: %s", e)
            return None

    def _get_triage_decision(
        self, user_query: str, context: Dict, query_id: str
    ) -> TriageDecision:
        """
        Call triage agent. On exception, return a safe default decision
        (GRAIN → CARTRIDGE → ESCALATE) rather than crashing.
        """
        try:
            request = TriageRequest(
                user_query=user_query,
                context=context,
            )
            return self.triage_agent.route(request)
        except Exception as e:
            logger.error("Triage agent failed for %s: %s - using default sequence.", query_id, e)
            self.feed.log_error(query_id, "TRIAGE", str(e))
            from kitbash.interfaces.triage_agent import TriageDecision
            return TriageDecision(
                layer_sequence=["GRAIN", "CARTRIDGE", "ESCALATE"],
                confidence_thresholds={"GRAIN": 0.90, "CARTRIDGE": 0.70},
                recommended_cartridges=[],
                use_mamba_context=False,
                cache_result=True,
                reasoning="Triage agent failed - using safe default",
            )

    def _attempt_layer(
        self,
        layer_name: str,
        threshold: float,
        user_query: str,
        context: Dict,
        decision: TriageDecision,
        query_id: str,
    ) -> tuple:  # (LayerAttempt, Optional[InferenceResponse])
        """
        Try a single engine. Always returns a LayerAttempt - never raises.

        Fail-safe cascade: if the engine throws, the attempt is recorded
        as a miss and the cascade continues to the next layer.
        """
        engine = self.engines[layer_name]
        engine_start = time.perf_counter()

        self.feed.log_layer_attempt(query_id, layer_name, 0.0)  # latency filled below

        try:
            inference_req = InferenceRequest(
                user_query=user_query,
                context=context,
                cartridge_ids=decision.recommended_cartridges or None,
            )
            response = engine.query(inference_req)
            latency = (time.perf_counter() - engine_start) * 1000

            passed = (
                response is not None
                and response.answer is not None
                and response.confidence >= threshold
            )

            if passed:
                self.feed.log_layer_hit(
                    query_id, layer_name,
                    response.confidence, latency,
                    result_preview=response.answer,
                )
            else:
                reason = (
                    f"confidence {response.confidence:.2f} below threshold {threshold:.2f}"
                    if response and response.answer
                    else "no answer returned"
                )
                self.feed.log_layer_miss(query_id, layer_name, latency, reason=reason)

            return LayerAttempt(
                engine_name=layer_name,
                confidence=response.confidence if response else 0.0,
                threshold=threshold,
                passed=passed,
                latency_ms=latency,
            ), response

        except Exception as e:
            latency = (time.perf_counter() - engine_start) * 1000
            logger.warning("Engine %s raised exception for %s: %s", layer_name, query_id, e)
            self.feed.log_error(query_id, layer_name, str(e))
            self.feed.log_layer_miss(query_id, layer_name, latency, reason=f"exception: {e}")

            return LayerAttempt(
                engine_name=layer_name,
                confidence=0.0,
                threshold=threshold,
                passed=False,
                latency_ms=latency,
                error=str(e),
            ), None

    def _record_phantom_hit(
        self, response: InferenceResponse, user_query: str
    ) -> None:
        """
        Call Shannon's record_phantom_hit. Silent on failure - Shannon
        being unavailable must never affect query responses.
        """
        try:
            # Convert string source IDs to a set for Shannon's interface.
            fact_ids = set()
            for src in response.sources:
                try:
                    fact_ids.add(int(src))
                except (ValueError, TypeError):
                    pass  # grain_ids and non-integer sources are silently skipped

            # Extract simple concepts from the query (MVP: whitespace split,
            # filtered to words >3 chars). Phase 4 can swap in NLP extraction.
            concepts = [
                w.lower() for w in user_query.split()
                if len(w) > 3
            ]

            self.shannon.record_phantom_hit(
                fact_ids=fact_ids,
                concepts=concepts,
                confidence=response.confidence,
            )
        except Exception as e:
            logger.warning("Shannon phantom hit recording failed: %s", e)

    def _record_layer_metric(self, layer_name: str, attempt: LayerAttempt) -> None:
        """Update internal hit/attempt counters."""
        if layer_name not in self._metrics["layer_attempts"]:
            self._metrics["layer_attempts"][layer_name] = 0
            self._metrics["layer_hits"][layer_name] = 0
        self._metrics["layer_attempts"][layer_name] += 1
        if attempt.passed:
            self._metrics["layer_hits"][layer_name] += 1

    @staticmethod
    def _hash_query(user_query: str) -> str:
        """
        Produce a stable SHA-256 hex digest for a query string.
        Used as the pattern_hash key in ResonanceWeightService.
        """
        return hashlib.sha256(user_query.strip().lower().encode()).hexdigest()

    @staticmethod
    def _init_feed(diagnostic_feed) -> Any:
        """
        Return the provided DiagnosticFeed, or a no-op if None or broken.

        The DiagnosticFeed constructor raises redis.ConnectionError if Redis
        is unavailable. We catch that here so the orchestrator can be
        constructed without Redis being present.
        """
        if diagnostic_feed is None:
            return _NoOpDiagnosticFeed()
        try:
            # Probe: if the feed has already been constructed it's fine.
            # If not (caller passed a class), instantiate it.
            if callable(diagnostic_feed) and not hasattr(diagnostic_feed, 'log_query_created'):
                return diagnostic_feed()
            return diagnostic_feed
        except Exception as e:
            logger.warning(
                "DiagnosticFeed unavailable (%s) - using no-op feed. "
                "Queries will still process normally.", e
            )
            return _NoOpDiagnosticFeed()
