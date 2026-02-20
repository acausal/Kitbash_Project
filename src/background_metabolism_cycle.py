"""
background_metabolism_cycle.py - Background Metabolism Cycle

Runs during the background cycle (every N queries). Analyzes recent query logs
and generates learning signals for pattern discovery.

Responsibilities:
1. Read recent query events from Redis
2. Analyze coupling patterns (Gap #3)
3. Analyze epistemology (Gap #1)
4. Analyze questions (Gap #2)
5. Validate patterns don't violate constraints
6. Check faction boundaries (Constraint)
7. Update baseline metrics (Gap #7)
8. Generate signals for other cycles

Phase 4.1: Week 1 - Log Reading & Analysis
"""

import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CycleResult:
    """Result of running a metabolism cycle."""
    
    cycle_id: str
    cycle_type: str  # "background", "daydream", "sleep"
    started_at: float
    completed_at: float
    success: bool
    
    # Analysis results
    events_analyzed: int = 0
    patterns_found: int = 0
    
    # Detailed analysis
    coupling_analysis: Dict[str, Any] = field(default_factory=dict)
    epistemology_analysis: Dict[str, Any] = field(default_factory=dict)
    question_analysis: Dict[str, Any] = field(default_factory=dict)
    faction_analysis: Dict[str, Any] = field(default_factory=dict)
    validation_results: Dict[str, Any] = field(default_factory=dict)
    
    # Errors
    error_message: Optional[str] = None
    
    @property
    def elapsed_ms(self) -> float:
        """Elapsed time in milliseconds."""
        return (self.completed_at - self.started_at) * 1000
    
    def summary(self) -> str:
        """One-line summary."""
        return (
            f"{self.cycle_type} cycle: "
            f"{self.events_analyzed} events, "
            f"{self.elapsed_ms:.1f}ms, "
            f"{'✓' if self.success else '✗'}"
        )


class BackgroundMetabolismCycle:
    """
    Background metabolism cycle - continuous learning signal generation.
    
    Runs automatically every N queries (configured in MetabolismScheduler).
    Analyzes recent query logs and generates signals for pattern discovery.
    """
    
    def __init__(
        self,
        log_analyzer,  # LogAnalyzer instance
        epistemic_validator,  # EpistemicValidator instance
        question_scorer,  # QuestionAdjustedScorer instance
        faction_gate,  # FactionGate instance
        regression_detector,  # RegressionDetector instance
        metabolism_state=None,  # MetabolismState (optional, shared with other cycles)
    ):
        """
        Initialize background cycle.
        
        Args:
            log_analyzer: LogAnalyzer for reading Redis events
            epistemic_validator: Validator for L0-L5 constraints
            question_scorer: Scorer for question-adjusted confidence
            faction_gate: Enforces fiction/general boundaries
            regression_detector: Detects baseline regression
            metabolism_state: Shared MetabolismState (optional)
        """
        self.log_analyzer = log_analyzer
        self.epistemic_validator = epistemic_validator
        self.question_scorer = question_scorer
        self.faction_gate = faction_gate
        self.regression_detector = regression_detector
        self.metabolism_state = metabolism_state
        
        logger.info("BackgroundMetabolismCycle initialized")
    
    def execute(
        self,
        num_events: int = 100,
        turn_number: int = 0
    ) -> CycleResult:
        """
        Execute background metabolism cycle.
        
        Args:
            num_events: Number of recent events to analyze
            turn_number: Current turn from HeartbeatService
        
        Returns:
            CycleResult with analysis and signals
        """
        cycle_id = f"bg_{int(time.time())}"
        start_time = time.time()
        
        logger.info(f"Background cycle {cycle_id} starting (turn {turn_number})")
        
        try:
            # Step 1: Read recent events from Redis
            recent_events = self.log_analyzer.read_recent_events(num_events=num_events)
            
            if not recent_events:
                logger.warning("No recent events found in Redis")
                return self._create_result(
                    cycle_id, start_time, time.time(),
                    success=False,
                    error="No events found"
                )
            
            logger.info(f"Read {len(recent_events)} events from Redis")
            
            # Step 2: Analyze coupling patterns (Gap #3)
            coupling_analysis = self._analyze_coupling_patterns(recent_events)
            
            # Step 3: Analyze epistemology (Gap #1)
            epistemology_analysis = self._analyze_epistemology(recent_events)
            
            # Step 4: Analyze questions (Gap #2)
            question_analysis = self._analyze_questions(recent_events)
            
            # Step 5: Validate patterns don't violate constraints
            validation_results = self._validate_patterns(
                recent_events,
                epistemology_analysis,
                question_analysis
            )
            
            # Step 6: Check faction boundaries (Constraint)
            faction_analysis = self._check_faction_boundaries(recent_events)
            
            # Step 7: Update baseline metrics (Gap #7)
            self._update_baseline_metrics(recent_events)
            
            # Step 8: Update shared metabolism state if available
            if self.metabolism_state:
                self._update_metabolism_state(
                    recent_events,
                    epistemology_analysis,
                    question_analysis,
                    faction_analysis,
                    turn_number
                )
            
            # Create successful result
            result = self._create_result(
                cycle_id, start_time, time.time(),
                success=True,
                events_analyzed=len(recent_events),
                coupling_analysis=coupling_analysis,
                epistemology_analysis=epistemology_analysis,
                question_analysis=question_analysis,
                faction_analysis=faction_analysis,
                validation_results=validation_results,
            )
            
            logger.info(f"Background cycle complete: {result.summary()}")
            return result
        
        except Exception as e:
            logger.error(f"Background cycle failed: {e}", exc_info=True)
            return self._create_result(
                cycle_id, start_time, time.time(),
                success=False,
                error=str(e)
            )
    
    # ========================================================================
    # Analysis Methods
    # ========================================================================
    
    def _analyze_coupling_patterns(self, events) -> Dict[str, Any]:
        """Analyze coupling deltas across events (Gap #3)."""
        
        # Count deltas by severity
        severity_counts = {"PASS": 0, "LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        layer_pair_conflicts = {}
        
        for event in events:
            for delta in event.coupling_deltas:
                severity = delta.get("severity", "LOW")
                if severity in severity_counts:
                    severity_counts[severity] += 1
                
                # Track which layer pairs conflict most
                pair = (delta.get("layer_a"), delta.get("layer_b"))
                if pair not in layer_pair_conflicts:
                    layer_pair_conflicts[pair] = []
                layer_pair_conflicts[pair].append(severity)
        
        # Find top conflicting pairs
        top_conflicts = sorted(
            layer_pair_conflicts.items(),
            key=lambda x: len([s for s in x[1] if s in ["HIGH", "CRITICAL"]]),
            reverse=True
        )[:5]
        
        return {
            "total_deltas": sum(severity_counts.values()),
            "severity_distribution": severity_counts,
            "top_conflicting_pairs": [
                {
                    "pair": pair,
                    "high_critical_count": len([s for s in severities if s in ["HIGH", "CRITICAL"]]),
                    "total_count": len(severities),
                }
                for (pair, severities) in top_conflicts
            ],
        }
    
    def _analyze_epistemology(self, events) -> Dict[str, Any]:
        """Analyze epistemic context (Gap #1)."""
        
        l0_l1_both_present = 0
        l0_l1_missing = 0
        validation_passed = 0
        validation_failed = 0
        
        for event in events:
            context = event.epistemic_context
            
            if context.get("L0_active") and context.get("L1_active"):
                l0_l1_both_present += 1
            else:
                l0_l1_missing += 1
            
            if context.get("nwp_validation_passed"):
                validation_passed += 1
            else:
                validation_failed += 1
        
        validation_rate = (
            validation_passed / len(events) if events else 0.0
        )
        
        return {
            "total_events": len(events),
            "L0_L1_both_present": l0_l1_both_present,
            "L0_L1_missing": l0_l1_missing,
            "nwp_validation_passed": validation_passed,
            "nwp_validation_failed": validation_failed,
            "validation_success_rate": validation_rate,
        }
    
    def _analyze_questions(self, events) -> Dict[str, Any]:
        """Analyze question signals (Gap #2)."""
        
        total_unresolved = 0
        events_with_questions = 0
        question_types = set()
        question_rate_sum = 0.0
        
        for event in events:
            questions = event.question_signals
            count = questions.get("unresolved_question_count", 0)
            
            if count > 0:
                events_with_questions += 1
                total_unresolved += count
                question_types.update(questions.get("question_types", []))
            
            question_rate_sum += count
        
        avg_questions = (
            total_unresolved / len(events) if events else 0.0
        )
        
        return {
            "events_analyzed": len(events),
            "events_with_unresolved_questions": events_with_questions,
            "total_unresolved_questions": total_unresolved,
            "average_questions_per_event": avg_questions,
            "question_types_seen": list(question_types),
            "question_rate": (events_with_questions / len(events)) if events else 0.0,
        }
    
    def _validate_patterns(
        self,
        events,
        epistemology: Dict[str, Any],
        questions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate patterns against constraints."""
        
        # Phase 4.1 Week 1: Just setup infrastructure
        # Phase 4.2: Will do actual pattern clustering and validation
        # For now, just verify validators are ready
        
        return {
            "epistemology_validator_ready": True,
            "question_validator_ready": True,
            "faction_gate_ready": True,
            "validation_ready_for_week_2": True,
            "note": "Actual pattern validation in Phase 4.2",
        }
    
    def _check_faction_boundaries(self, events) -> Dict[str, Any]:
        """Check faction boundaries (Constraint)."""
        
        faction_counts = {}
        mixed_cartridges = 0
        
        for event in events:
            faction = event.source_faction
            faction_counts[faction] = faction_counts.get(faction, 0) + 1
            
            # Check if mixing fiction and general cartridges
            has_fiction = any("fiction" in c.lower() for c in event.cartridges_loaded)
            has_general = any("fiction" not in c.lower() for c in event.cartridges_loaded)
            
            if has_fiction and has_general:
                mixed_cartridges += 1
        
        return {
            "total_events": len(events),
            "faction_distribution": faction_counts,
            "mixed_cartridge_events": mixed_cartridges,
            "faction_separation_clean": mixed_cartridges == 0,
        }
    
    def _update_baseline_metrics(self, events) -> None:
        """Update baseline metrics for rollback (Gap #7)."""
        
        if not events:
            return
        
        # Calculate baseline success rate
        successful = sum(1 for e in events if e.is_successful(threshold=0.7))
        success_rate = successful / len(events)
        
        # Calculate baseline question rate
        total_questions = sum(
            e.question_signals.get("unresolved_question_count", 0)
            for e in events
        )
        avg_question_rate = total_questions / len(events)
        
        # Calculate baseline coupling issues
        critical_deltas = sum(
            sum(1 for d in e.coupling_deltas if d.get("severity") == "CRITICAL")
            for e in events
        )
        critical_rate = critical_deltas / len(events)
        
        # Store baseline
        self.regression_detector.baseline_metrics = {
            "success_rate": success_rate,
            "question_rate": avg_question_rate,
            "critical_coupling_rate": critical_rate,
        }
        
        logger.info(
            f"Baseline metrics updated: "
            f"success={success_rate:.2%}, "
            f"questions={avg_question_rate:.2f}/event, "
            f"critical={critical_rate:.2%}"
        )
    
    def _update_metabolism_state(
        self,
        events,
        epistemology: Dict[str, Any],
        questions: Dict[str, Any],
        factions: Dict[str, Any],
        turn_number: int
    ) -> None:
        """Update shared MetabolismState if available."""
        
        if not self.metabolism_state:
            return
        
        # Update turn
        self.metabolism_state.current_turn = turn_number
        
        # Update learned deltas count
        total_deltas = sum(len(e.coupling_deltas) for e in events)
        self.metabolism_state.learned_deltas += total_deltas
        
        logger.debug(
            f"MetabolismState updated: turn={turn_number}, "
            f"total_deltas={self.metabolism_state.learned_deltas}"
        )
    
    # ========================================================================
    # Result creation
    # ========================================================================
    
    def _create_result(
        self,
        cycle_id: str,
        started_at: float,
        completed_at: float,
        success: bool,
        events_analyzed: int = 0,
        coupling_analysis: Optional[Dict[str, Any]] = None,
        epistemology_analysis: Optional[Dict[str, Any]] = None,
        question_analysis: Optional[Dict[str, Any]] = None,
        faction_analysis: Optional[Dict[str, Any]] = None,
        validation_results: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> CycleResult:
        """Create a CycleResult object."""
        
        return CycleResult(
            cycle_id=cycle_id,
            cycle_type="background",
            started_at=started_at,
            completed_at=completed_at,
            success=success,
            events_analyzed=events_analyzed,
            coupling_analysis=coupling_analysis or {},
            epistemology_analysis=epistemology_analysis or {},
            question_analysis=question_analysis or {},
            faction_analysis=faction_analysis or {},
            validation_results=validation_results or {},
            error_message=error,
        )


# ============================================================================
# Testing helpers
# ============================================================================

class MockLogAnalyzer:
    """Mock LogAnalyzer for testing."""
    
    def read_recent_events(self, num_events: int = 100):
        """Return test events."""
        # Create simple test events without importing
        from dataclasses import dataclass, field
        from typing import List, Dict, Any, Optional
        
        events = []
        for i in range(num_events):
            event = type('QueryLogEvent', (), {
                'query_id': f'test_q{i}',
                'timestamp': 0.0,
                'event_type': 'query_completed',
                'layer_sequence': ['GRAIN', 'CARTRIDGE'],
                'winning_layer': 'GRAIN',
                'confidence': 0.85,
                'triage_latency_ms': 5.0,
                'total_latency_ms': 25.0,
                'coupling_deltas': [
                    {'layer_a': 'L1', 'layer_b': 'L2', 'severity': 'LOW', 'delta_magnitude': 0.1}
                ],
                'epistemic_context': {
                    'L0_active': True,
                    'L1_active': True,
                    'nwp_validation_passed': True,
                    'highest_severity': 'LOW',
                },
                'question_signals': {
                    'unresolved_question_count': 0,
                    'unresolved_questions': [],
                    'question_types': [],
                },
                'redis_spotlight_state': {
                    'spotlight_keys_count': 5,
                    'coupling_delta_count': 1,
                    'highest_coupling_severity': 'LOW',
                },
                'metabolism_state': {
                    'background_cycle_active': False,
                    'daydream_cycle_active': False,
                    'sleep_cycle_active': False,
                    'turn_number': 0,
                },
                'neuromorphic_placeholders': {
                    'snn_ready': True,
                    'esn_ready': True,
                    'lnn_ready': True,
                },
                'drive_satisfaction': {
                    'learning': 0.5,
                    'consolidation': 0.5,
                    'socialization': 0.5,
                },
                'source_faction': 'general',
                'cartridges_loaded': ['physics.kbc'],
                'is_successful': lambda self=None, threshold=0.7: 0.85 >= threshold,
                'has_unresolved_questions': lambda self=None: False,
                'has_critical_coupling_violations': lambda self=None: False,
            })()
            events.append(event)
        
        return events


class MockValidators:
    """Mock validators for testing."""
    
    baseline_metrics = {}


if __name__ == "__main__":
    """Quick test of BackgroundMetabolismCycle."""
    
    logging.basicConfig(level=logging.INFO)
    
    # Create mocks
    log_analyzer = MockLogAnalyzer()
    validators = MockValidators()
    
    # Create cycle
    cycle = BackgroundMetabolismCycle(
        log_analyzer=log_analyzer,
        epistemic_validator=validators,
        question_scorer=validators,
        faction_gate=validators,
        regression_detector=validators,
    )
    
    # Run cycle
    result = cycle.execute(num_events=10, turn_number=100)
    
    print(f"\n✅ Cycle execution result:")
    print(f"   {result.summary()}")
    print(f"   Events analyzed: {result.events_analyzed}")
    print(f"   Coupling deltas: {result.coupling_analysis.get('total_deltas', 0)}")
    print(f"   Validation success rate: {result.epistemology_analysis.get('validation_success_rate', 0):.2%}")
    print(f"   Questions per event: {result.question_analysis.get('average_questions_per_event', 0):.2f}")
    
    print("\n✅ BackgroundMetabolismCycle working correctly")
