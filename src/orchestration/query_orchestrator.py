"""
kitbash/orchestration/query_orchestrator.py

QueryOrchestrator - the single external entry point for user queries.

Coordinates:
  1. Background work scheduling (via MetabolismScheduler)
  2. Mamba context retrieval (temporal windows)
  3. Triage routing decision (also routes background work)
  4. PAUSE background work (heartbeat.pause())
  5. Serial engine cascade (Complexity Sieve)
  6. RESUME background work (heartbeat.resume())
  7. Resonance pattern recording & Turn Sync
  8. Advance turn counter

Phase 3B MVP: GRAIN → CARTRIDGE only
Phase 4+: Add BITNET, LLM, specialists

Standardized for Phase 3B MVP.
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
from kitbash.metabolism.heartbeat_service import HeartbeatService
from kitbash.metabolism.metabolism_scheduler import MetabolismScheduler

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    """Final result returned to the caller."""
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
    """Record of a single engine attempt during cascade."""
    engine_name: str
    confidence: float
    threshold: float
    passed: bool
    latency_ms: float
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# No-op diagnostic feed
# ---------------------------------------------------------------------------

class _NoOpDiagnosticFeed:
    """Silent stand-in for DiagnosticFeed when Redis is unavailable."""
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
    
    Phase 3B MVP: Cascades through GRAIN → CARTRIDGE
    Phase 4+: Will add BITNET, LLM, specialists
    """

    FALLBACK_THRESHOLDS: Dict[str, float] = {
        "GRAIN":     0.90,
        "CARTRIDGE": 0.70,
        # Phase 4+:
        # "BITNET":    0.75,
        # "SPECIALIST": 0.65,
        # "LLM":       0.0,
    }

    ESCALATE_SENTINEL = "ESCALATE"

    def __init__(
        self,
        triage_agent: TriageAgent,
        engines: Dict[str, InferenceEngine],
        mamba_service: MambaContextService,
        resonance: ResonanceWeightService,
        heartbeat: Optional[HeartbeatService] = None,
        metabolism_scheduler: Optional[MetabolismScheduler] = None,
        shannon=None,
        diagnostic_feed=None,
    ) -> None:
        self.triage_agent = triage_agent
        self.engines = engines
        self.mamba_service = mamba_service
        self.resonance = resonance
        self.shannon = shannon

        # Week 3 Metabolism components
        self.heartbeat = heartbeat or HeartbeatService(initial_turn=0)
        self.metabolism_scheduler = metabolism_scheduler

        self.feed = self._init_feed(diagnostic_feed)

        self._metrics: Dict[str, Any] = {
            "queries_total": 0,
            "queries_answered": 0,
            "queries_exhausted": 0,
            "layer_hits": {},
            "layer_attempts": {},
            "triage_latencies_ms": [],
            "total_latencies_ms": [],
            "heartbeat_pauses": 0,
            "metabolism_cycles_run": 0,
        }

    def process_query(
        self,
        user_query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> QueryResult:
        """
        Process a user query through the full orchestration pipeline.
        """
        query_id = str(uuid.uuid4())
        total_start = time.perf_counter()
        context = context or {}

        self.feed.log_query_created(query_id, user_query)
        self.feed.log_query_started(query_id)

        # PHASE 1: Metabolism check
        if self.metabolism_scheduler:
            try:
                # Sync turn to scheduler before checking if work is due
                self.metabolism_scheduler.current_turn = self.heartbeat.turn_number
                bg_status = self.metabolism_scheduler.step()
                if bg_status.get("executed"):
                    self._metrics["metabolism_cycles_run"] += 1
            except Exception as e:
                logger.warning(f"Metabolism scheduler failed: {e}")
                self.feed.log_error(query_id, "METABOLISM_SCHEDULER", str(e))

        # PHASE 2: Context retrieval
        mamba_context = self._get_mamba_context(user_query, context)
        context["mamba_context"] = mamba_context

        # PHASE 3: Triage
        triage_start = time.perf_counter()
        decision = self._get_triage_decision(user_query, context, query_id)
        triage_latency = (time.perf_counter() - triage_start) * 1000

        # PHASE 4: PAUSE background work
        if self.heartbeat:
            try:
                self.heartbeat.pause(priority="query_exec")
                self._metrics["heartbeat_pauses"] += 1
            except Exception as e:
                logger.warning(f"Heartbeat pause failed: {e}")
                self.feed.log_error(query_id, "HEARTBEAT_PAUSE", str(e))

        try:
            # PHASE 5: Engine cascade
            layer_results: List[LayerAttempt] = []
            winning_response: Optional[InferenceResponse] = None

            for layer_name in decision.layer_sequence:
                if layer_name == self.ESCALATE_SENTINEL:
                    break

                if layer_name not in self.engines:
                    logger.warning(f"Layer {layer_name} missing from engines.")
                    continue

                threshold = decision.confidence_thresholds.get(
                    layer_name, self.FALLBACK_THRESHOLDS.get(layer_name, 0.5)
                )

                attempt, response = self._attempt_layer(
                    layer_name, threshold, user_query, context, decision, query_id
                )
                layer_results.append(attempt)
                self._record_layer_metric(layer_name, attempt)

                if attempt.passed:
                    winning_response = response
                    break

            # PHASE 6: Finalize response
            total_latency = (time.perf_counter() - total_start) * 1000
            pattern_recorded = False

            if winning_response and winning_response.answer:
                answer = winning_response.answer
                confidence = winning_response.confidence
                engine_name = winning_response.engine_name

                # Record pattern to resonance
                pattern_hash = self._hash_query(user_query)
                if pattern_hash in self.resonance.weights:
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

                if self.shannon:
                    self._record_phantom_hit(winning_response, user_query)

                self.feed.log_query_completed(query_id, engine_name, confidence, total_latency)
                self._metrics["queries_answered"] += 1
            else:
                answer = "I don't know."
                confidence = 0.0
                engine_name = "NONE"
                self.feed.log_query_completed(query_id, "NONE", 0.0, total_latency)
                self._metrics["queries_exhausted"] += 1

            self._metrics["queries_total"] += 1
            self._metrics["triage_latencies_ms"].append(triage_latency)
            self._metrics["total_latencies_ms"].append(total_latency)

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
            # PHASE 7 & 8: Resume & Advance Clock
            if self.heartbeat:
                try:
                    self.heartbeat.resume()
                    # Advance the master clock
                    new_turn = self.heartbeat.advance_turn()
                    
                    # Sync turn across stateful services
                    if hasattr(self.resonance, 'current_turn'):
                        self.resonance.current_turn = new_turn
                    if hasattr(self.triage_agent, 'current_turn'):
                        self.triage_agent.current_turn = new_turn
                        
                except Exception as e:
                    logger.warning(f"Turn advancement failed: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Return session-level performance metrics."""
        lats = self._metrics["total_latencies_ms"]
        
        def percentile(data, p):
            if not data: return 0.0
            sorted_data = sorted(data)
            return sorted_data[min(int(len(sorted_data) * p / 100), len(sorted_data) - 1)]

        return {
            "queries_total": self._metrics["queries_total"],
            "queries_answered": self._metrics["queries_answered"],
            "queries_exhausted": self._metrics["queries_exhausted"],
            "latency": {
                "total_p50_ms": percentile(lats, 50),
                "total_p95_ms": percentile(lats, 95),
                "total_avg_ms": sum(lats) / len(lats) if lats else 0.0,
            },
            "layer_hits": dict(self._metrics["layer_hits"]),
            "resonance_turn": getattr(self.resonance, 'current_turn', 0),
            "heartbeat_pauses": self._metrics["heartbeat_pauses"],
            "metabolism_cycles_run": self._metrics["metabolism_cycles_run"],
        }

    def _get_mamba_context(self, user_query: str, context: Dict) -> Any:
        try:
            req = MambaContextRequest(
                user_id=context.get("user_id"),
                session_id=context.get("session_id"),
                include_conversation_history=True
            )
            return self.mamba_service.get_context(req)
        except Exception as e:
            logger.warning(f"Mamba retrieval failed: {e}")
            return None

    def _get_triage_decision(self, user_query: str, context: Dict, query_id: str) -> TriageDecision:
        try:
            return self.triage_agent.route(TriageRequest(user_query=user_query, context=context))
        except Exception as e:
            logger.error(f"Triage failed: {e}. Using fallback.")
            return TriageDecision(
                layer_sequence=["GRAIN", "CARTRIDGE", "ESCALATE"],
                confidence_thresholds={"GRAIN": 0.90, "CARTRIDGE": 0.70}
            )

    def _attempt_layer(self, layer_name: str, threshold: float, user_query: str, 
                       context: Dict, decision: TriageDecision, query_id: str) -> tuple:
        engine = self.engines[layer_name]
        start = time.perf_counter()
        try:
            req = InferenceRequest(
                user_query=user_query,
                context=context,
                cartridge_ids=getattr(decision, 'recommended_cartridges', None)
            )
            resp = engine.query(req)
            latency = (time.perf_counter() - start) * 1000
            passed = resp is not None and resp.answer is not None and resp.confidence >= threshold
            
            return LayerAttempt(
                engine_name=layer_name, confidence=resp.confidence if resp else 0.0,
                threshold=threshold, passed=passed, latency_ms=latency
            ), resp
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return LayerAttempt(
                engine_name=layer_name, confidence=0.0, threshold=threshold,
                passed=False, latency_ms=latency, error=str(e)
            ), None

    def _record_phantom_hit(self, response: InferenceResponse, user_query: str) -> None:
        try:
            fact_ids = {int(src) for src in response.sources if str(src).isdigit()}
            concepts = [w.lower() for w in user_query.split() if len(w) > 3]
            self.shannon.record_phantom_hit(fact_ids=fact_ids, concepts=concepts, confidence=response.confidence)
        except: pass

    def _record_layer_metric(self, layer_name: str, attempt: LayerAttempt) -> None:
        self._metrics["layer_attempts"][layer_name] = self._metrics["layer_attempts"].get(layer_name, 0) + 1
        if attempt.passed:
            self._metrics["layer_hits"][layer_name] = self._metrics["layer_hits"].get(layer_name, 0) + 1

    @staticmethod
    def _hash_query(user_query: str) -> str:
        return hashlib.sha256(user_query.strip().lower().encode()).hexdigest()

    @staticmethod
    def _init_feed(diagnostic_feed) -> Any:
        if diagnostic_feed is None: return _NoOpDiagnosticFeed()
        return diagnostic_feed
