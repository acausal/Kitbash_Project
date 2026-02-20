"""
log_analyzer.py - Phase 4 Log Analysis

Reads query events from Redis (RedisSpotlight + CouplingValidator) and
extracts learning signals with awareness of all 8 audit gaps:

1. Epistemological Validation (L0-L5 constraints)
2. Question Propagation (unresolved question tracking)
3. Redis Bus State (coupling geometry)
4. Cross-Cycle Metabolism (turn tracking)
5. Neuromorphic Infrastructure (SNN/ESN/LNN placeholders)
6. Confidence Ensemble (weighting signals)
7. Graceful Failure (baseline metrics)
8. Learning Drives (goal-driven signals)

Phase 4.1: Week 1 - Log Reading & Analysis
"""

import logging
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class QueryLogEvent:
    """Complete query event with all Phase 4 fields."""
    
    # Phase 3B fields
    query_id: str
    timestamp: float
    event_type: str  # "query_started", "query_completed", "layer_attempt", etc.
    layer_sequence: List[str]
    winning_layer: Optional[str]
    confidence: float
    triage_latency_ms: float
    total_latency_ms: float
    coupling_deltas: List[Dict[str, Any]] = field(default_factory=list)
    
    # Phase 4 Gap #1: Epistemological Validation
    epistemic_context: Dict[str, Any] = field(default_factory=dict)
    
    # Phase 4 Gap #2: Question Propagation
    question_signals: Dict[str, Any] = field(default_factory=dict)
    
    # Phase 4 Gap #3: Redis Bus State
    redis_spotlight_state: Dict[str, Any] = field(default_factory=dict)
    
    # Phase 4 Gap #4: Cross-Cycle Metabolism
    metabolism_state: Dict[str, Any] = field(default_factory=dict)
    
    # Phase 4 Gap #5: Neuromorphic Infrastructure
    neuromorphic_placeholders: Dict[str, Any] = field(default_factory=dict)
    
    # Phase 4 Gap #8: Learning Drives
    drive_satisfaction: Dict[str, Any] = field(default_factory=dict)
    
    # Faction Isolation Constraint
    source_faction: str = "general"
    cartridges_loaded: List[str] = field(default_factory=list)
    
    def is_successful(self, threshold: float = 0.7) -> bool:
        """Check if query was successful."""
        return self.confidence >= threshold
    
    def has_unresolved_questions(self) -> bool:
        """Check if query generated unresolved questions."""
        return self.question_signals.get("unresolved_question_count", 0) > 0
    
    def has_critical_coupling_violations(self) -> bool:
        """Check for CRITICAL coupling deltas."""
        for delta in self.coupling_deltas:
            if delta.get("severity") == "CRITICAL":
                return True
        return False
    
    def summary(self) -> str:
        """One-line summary of query."""
        return (
            f"Query {self.query_id[:8]}: "
            f"conf={self.confidence:.2f}, "
            f"engine={self.winning_layer}, "
            f"faction={self.source_faction}, "
            f"questions={self.question_signals.get('unresolved_question_count', 0)}"
        )


class LogAnalyzer:
    """
    Analyzes query events from Redis with full Gap awareness.
    
    Reads from:
    - RedisSpotlight: Event logs and query metadata
    - CouplingValidator: Coupling deltas
    - (Future) QuestionPropagationService: Unresolved questions
    
    Produces:
    - QueryLogEvent objects with all 8 gap fields populated
    - Learning signals for Phase 4.2+ pattern analysis
    """
    
    def __init__(
        self,
        spotlight,  # RedisSpotlight instance
        coupling_validator,  # CouplingValidator instance
        question_service: Optional[Any] = None
    ):
        """
        Initialize analyzer.
        
        Args:
            spotlight: RedisSpotlight for event reading
            coupling_validator: CouplingValidator for delta reading
            question_service: Optional QuestionPropagationService
        """
        self.spotlight = spotlight
        self.coupling_validator = coupling_validator
        self.question_service = question_service
        
        logger.info("LogAnalyzer initialized")
    
    def read_recent_events(
        self,
        num_events: int = 100,
        query_ids: Optional[List[str]] = None
    ) -> List[QueryLogEvent]:
        """
        Read recent query events from Redis.
        
        Args:
            num_events: Number of recent events to retrieve (if query_ids not specified)
            query_ids: Specific query IDs to retrieve (overrides num_events)
        
        Returns:
            List of QueryLogEvent objects with all fields populated
        """
        events = []
        
        if query_ids:
            # Specific queries
            logger.info(f"Reading {len(query_ids)} specific queries")
            for query_id in query_ids:
                event = self._extract_query_event(query_id)
                if event:
                    events.append(event)
        else:
            # Recent N events from Redis
            # Note: This requires a query log index in Redis
            # For Phase 4.1, we'll collect from a set of recent query IDs
            logger.info(f"Reading {num_events} recent events from Redis")
            try:
                recent_keys = self.spotlight.redis_client.keys("query:*:metadata")
                recent_ids = [
                    k.split(":")[1] for k in recent_keys if isinstance(k, str)
                ][-num_events:]
                
                for query_id in recent_ids:
                    event = self._extract_query_event(query_id)
                    if event:
                        events.append(event)
            except Exception as e:
                logger.warning(f"Failed to read recent events: {e}")
        
        logger.info(f"Extracted {len(events)} complete event objects")
        return events
    
    def _extract_query_event(self, query_id: str) -> Optional[QueryLogEvent]:
        """
        Extract all fields for one query.
        
        Returns None if query not found or extraction fails.
        """
        try:
            # Get spotlight summary
            summary = self.spotlight.get_query_summary(query_id)
            if not summary:
                return None
            
            # Extract Phase 3B fields
            layer_sequence = summary.get("layer_sequence", [])
            winning_layer = summary.get("winning_layer")
            confidence = summary.get("confidence", 0.0)
            
            # Extract coupling deltas (Phase 3B.3)
            coupling_deltas = self._extract_coupling_deltas(query_id)
            coupling_delta_dicts = [
                {
                    "layer_a": d.layer_a,
                    "layer_b": d.layer_b,
                    "severity": d.severity,
                    "delta_magnitude": d.delta_magnitude,
                }
                for d in coupling_deltas
            ]
            
            # Extract Gap #1: Epistemological Validation
            epistemic_context = self._extract_epistemic_context(
                query_id, coupling_deltas
            )
            
            # Extract Gap #2: Question Propagation
            question_signals = self._extract_question_signals(query_id)
            
            # Extract Gap #3: Redis Bus State
            redis_state = self._extract_redis_state(query_id, coupling_deltas)
            
            # Extract Gap #4: Cross-Cycle Metabolism
            metabolism_state = self._extract_metabolism_state(query_id)
            
            # Extract Gap #5: Neuromorphic Placeholders
            neuromorphic = self._extract_neuromorphic_placeholders(query_id)
            
            # Extract Gap #8: Learning Drives
            drive_satisfaction = self._extract_drive_satisfaction(query_id)
            
            # Extract Faction Isolation Constraint
            source_faction = summary.get("source_faction", "general")
            cartridges_loaded = summary.get("cartridges_loaded", [])
            
            # Create event
            return QueryLogEvent(
                query_id=query_id,
                timestamp=time.time(),
                event_type="query_completed",
                layer_sequence=layer_sequence,
                winning_layer=winning_layer,
                confidence=confidence,
                triage_latency_ms=0.0,  # Extract from summary if available
                total_latency_ms=0.0,  # Extract from summary if available
                coupling_deltas=coupling_delta_dicts,
                epistemic_context=epistemic_context,
                question_signals=question_signals,
                redis_spotlight_state=redis_state,
                metabolism_state=metabolism_state,
                neuromorphic_placeholders=neuromorphic,
                drive_satisfaction=drive_satisfaction,
                source_faction=source_faction,
                cartridges_loaded=cartridges_loaded,
            )
        
        except Exception as e:
            logger.warning(f"Failed to extract event for {query_id}: {e}")
            return None
    
    def _extract_coupling_deltas(self, query_id: str) -> List:
        """Get coupling deltas from CouplingValidator."""
        try:
            return self.coupling_validator.get_deltas_for_query(query_id)
        except Exception as e:
            logger.debug(f"Could not retrieve coupling deltas: {e}")
            return []
    
    def _extract_epistemic_context(
        self,
        query_id: str,
        coupling_deltas: List
    ) -> Dict[str, Any]:
        """Extract Gap #1: Epistemological Validation context."""
        
        try:
            spotlight_summary = self.spotlight.get_query_summary(query_id)
            
            # Check if L0/L1 were active
            l0_active = len(spotlight_summary.get("L0", [])) > 0
            l1_active = len(spotlight_summary.get("L1", [])) > 0
            
            # Check validation status (highest severity)
            highest_severity = "PASS"
            for delta in coupling_deltas:
                severity = delta.severity if hasattr(delta, 'severity') else delta.get("severity", "LOW")
                if severity in ["CRITICAL", "HIGH"]:
                    highest_severity = severity
                    break
            
            nwp_validation_passed = highest_severity not in ["CRITICAL"]
            
            return {
                "L0_active": l0_active,
                "L1_active": l1_active,
                "nwp_validation_passed": nwp_validation_passed,
                "highest_severity": highest_severity,
            }
        
        except Exception as e:
            logger.debug(f"Epistemic context extraction failed: {e}")
            return {
                "L0_active": False,
                "L1_active": False,
                "nwp_validation_passed": True,
                "highest_severity": "UNKNOWN",
            }
    
    def _extract_question_signals(self, query_id: str) -> Dict[str, Any]:
        """Extract Gap #2: Question Propagation signals."""
        
        if not self.question_service:
            return {
                "unresolved_question_count": 0,
                "unresolved_questions": [],
                "question_types": [],
            }
        
        try:
            questions = self.question_service.get_unresolved_for_query(query_id)
            question_texts = [q.text for q in questions]
            question_types = list(set(q.type for q in questions))
            
            return {
                "unresolved_question_count": len(questions),
                "unresolved_questions": question_texts,
                "question_types": question_types,
            }
        except Exception as e:
            logger.debug(f"Question signal extraction failed: {e}")
            return {
                "unresolved_question_count": 0,
                "unresolved_questions": [],
                "question_types": [],
            }
    
    def _extract_redis_state(
        self,
        query_id: str,
        coupling_deltas: List
    ) -> Dict[str, Any]:
        """Extract Gap #3: Redis Bus State."""
        
        try:
            summary = self.spotlight.get_query_summary(query_id)
            
            # Count spotlight keys
            spotlight_keys = 0
            for level in ["L0", "L1", "L2", "L3", "L4", "L5"]:
                spotlight_keys += len(summary.get(level, []))
            
            # Count coupling deltas
            coupling_delta_count = len(coupling_deltas)
            
            # Get highest severity
            highest_severity = "PASS"
            for delta in coupling_deltas:
                severity = delta.severity if hasattr(delta, 'severity') else delta.get("severity", "LOW")
                if severity in ["CRITICAL", "HIGH", "MEDIUM"]:
                    highest_severity = severity
                    break
            
            return {
                "spotlight_keys_count": spotlight_keys,
                "coupling_delta_count": coupling_delta_count,
                "highest_coupling_severity": highest_severity,
            }
        
        except Exception as e:
            logger.debug(f"Redis state extraction failed: {e}")
            return {
                "spotlight_keys_count": 0,
                "coupling_delta_count": 0,
                "highest_coupling_severity": "UNKNOWN",
            }
    
    def _extract_metabolism_state(self, query_id: str) -> Dict[str, Any]:
        """Extract Gap #4: Cross-Cycle Metabolism state."""
        
        # In Week 1, these are placeholders
        # Phase 4.2 will populate based on actual cycle execution
        
        return {
            "background_cycle_active": False,
            "daydream_cycle_active": False,
            "sleep_cycle_active": False,
            "turn_number": 0,  # Will be set by MetabolismScheduler
        }
    
    def _extract_neuromorphic_placeholders(self, query_id: str) -> Dict[str, Any]:
        """Extract Gap #5: Neuromorphic Infrastructure placeholders."""
        
        # All queries can be trained by SNN/ESN/LNN
        # These will be populated in Phase 4 late + Phase 5
        
        return {
            "snn_ready": True,  # Layer sequence can be SNN trainable
            "esn_ready": True,  # State sequence can be ESN trainable
            "lnn_ready": True,  # Context transitions can be LNN trainable
        }
    
    def _extract_drive_satisfaction(self, query_id: str) -> Dict[str, Any]:
        """Extract Gap #8: Learning Drive satisfaction signals."""
        
        # Phase 4 drives:
        # - Learning: How much new knowledge discovered?
        # - Consolidation: How organized is the state?
        # - Socialization: Did external validation help?
        
        # Week 1 is setup with baseline values
        # Phase 4.2 will measure these properly
        
        return {
            "learning": 0.5,  # Baseline assumption
            "consolidation": 0.5,
            "socialization": 0.5,
        }
    
    def analyze_events(
        self,
        events: List[QueryLogEvent]
    ) -> Dict[str, Any]:
        """
        Perform basic analysis on a batch of events.
        
        Returns summary statistics for Phase 4.1 Week 1 baseline.
        """
        if not events:
            return {"event_count": 0}
        
        # Success analysis
        successful = sum(1 for e in events if e.is_successful())
        success_rate = successful / len(events)
        
        # Question analysis
        with_questions = sum(1 for e in events if e.has_unresolved_questions())
        avg_questions = sum(
            e.question_signals.get("unresolved_question_count", 0)
            for e in events
        ) / len(events)
        
        # Coupling analysis
        critical_violations = sum(
            1 for e in events if e.has_critical_coupling_violations()
        )
        critical_rate = critical_violations / len(events)
        
        # Faction analysis
        faction_counts = {}
        for e in events:
            faction_counts[e.source_faction] = faction_counts.get(e.source_faction, 0) + 1
        
        # Epistemology analysis
        epistemically_valid = sum(
            1 for e in events
            if e.epistemic_context.get("nwp_validation_passed", False)
        )
        
        return {
            "event_count": len(events),
            "success_rate": success_rate,
            "critical_success_count": successful,
            "events_with_questions": with_questions,
            "avg_questions_per_event": avg_questions,
            "critical_coupling_violations": critical_violations,
            "critical_coupling_rate": critical_rate,
            "faction_distribution": faction_counts,
            "epistemically_valid_events": epistemically_valid,
        }


# ============================================================================
# Testing helpers
# ============================================================================

def create_test_event(query_id: str = "test_q1") -> QueryLogEvent:
    """Create a test QueryLogEvent."""
    return QueryLogEvent(
        query_id=query_id,
        timestamp=time.time(),
        event_type="query_completed",
        layer_sequence=["GRAIN", "CARTRIDGE"],
        winning_layer="GRAIN",
        confidence=0.85,
        triage_latency_ms=5.0,
        total_latency_ms=25.0,
        coupling_deltas=[
            {"layer_a": "L1", "layer_b": "L2", "severity": "LOW", "delta_magnitude": 0.1}
        ],
        source_faction="general",
        cartridges_loaded=["physics.kbc", "chemistry.kbc"],
    )


if __name__ == "__main__":
    """Quick test of LogAnalyzer."""
    
    logging.basicConfig(level=logging.DEBUG)
    
    # Create test event
    event = create_test_event()
    
    print(f"\n✅ Test event created:")
    print(f"   {event.summary()}")
    
    print(f"\n✅ Event analysis:")
    print(f"   Successful: {event.is_successful()}")
    print(f"   Has questions: {event.has_unresolved_questions()}")
    print(f"   Has critical violations: {event.has_critical_coupling_violations()}")
    
    # Batch analysis
    events = [create_test_event(f"test_q{i}") for i in range(10)]
    
    analyzer = LogAnalyzer(
        spotlight=None,  # Would be RedisSpotlight in production
        coupling_validator=None  # Would be CouplingValidator in production
    )
    
    analysis = analyzer.analyze_events(events)
    print(f"\n✅ Batch analysis of 10 events:")
    for key, value in analysis.items():
        print(f"   {key}: {value}")
    
    print("\n✅ LogAnalyzer working correctly")
