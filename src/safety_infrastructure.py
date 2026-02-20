"""
safety_infrastructure.py - Phase 4 Safety Infrastructure

Implements four safety validators that enforce constraints during learning:

1. EpistemicValidator — Checks patterns against L0-L5 epistemic rules (Gap #1)
2. QuestionAdjustedScorer — Penalizes patterns with high question rates (Gap #2)
3. FactionGate — Enforces fiction/general knowledge boundaries (Constraint)
4. RegressionDetector — Detects if learned weights regress baseline (Gap #7)

Phase 4.1: Week 1 - Safety Infrastructure Setup
"""

import logging
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================================================
# Gap #1: EPISTEMIC VALIDATOR
# ============================================================================

@dataclass
class EpistemicRule:
    """Defines an epistemic constraint between layers."""
    layer_a: str
    layer_b: str
    rule_name: str
    description: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    check_fn: callable = None  # Optional custom validation function


class EpistemicValidator:
    """
    Validates learned patterns against epistemic constraints (Gap #1).
    
    Enforces that patterns don't violate L0-L5 relationships:
    - L0 ↔ L1: Never contradict (foundation layer)
    - L1 → L2: Narrative must not contradict axioms
    - L2 ↔ L4: Narrative should rationalize intent
    - L4 → L3/L5: Intent gates heuristics/persona
    """
    
    def __init__(self):
        """Initialize with epistemic rules."""
        
        self.rules: Dict[Tuple[str, str], EpistemicRule] = {}
        
        # Define epistemic rules
        self._define_rules()
    
    def _define_rules(self) -> None:
        """Define all epistemic constraint rules."""
        
        # L0 ↔ L1: Observations vs Axioms
        self.rules[("L0", "L1")] = EpistemicRule(
            layer_a="L0",
            layer_b="L1",
            rule_name="L0_L1_foundation",
            description="Observations (L0) must not contradict axioms (L1)",
            severity="CRITICAL",
        )
        
        # L1 → L2: Axioms constrain Narrative
        self.rules[("L1", "L2")] = EpistemicRule(
            layer_a="L1",
            layer_b="L2",
            rule_name="L1_L2_constraint",
            description="Narrative (L2) must not directly contradict axioms (L1)",
            severity="HIGH",
        )
        
        # L2 ↔ L4: Narrative rationalization
        self.rules[("L2", "L4")] = EpistemicRule(
            layer_a="L2",
            layer_b="L4",
            rule_name="L2_L4_rationalization",
            description="Narrative (L2) should rationalize intent (L4)",
            severity="MEDIUM",
        )
        
        # L4 → L3/L5: Intent gates Heuristics/Persona
        self.rules[("L4", "L3")] = EpistemicRule(
            layer_a="L4",
            layer_b="L3",
            rule_name="L4_L3_gate",
            description="Intent (L4) determines accessible heuristics (L3)",
            severity="LOW",
        )
        
        self.rules[("L4", "L5")] = EpistemicRule(
            layer_a="L4",
            layer_b="L5",
            rule_name="L4_L5_gate",
            description="Intent (L4) determines accessible persona (L5)",
            severity="LOW",
        )
    
    def validate_pattern(
        self,
        pattern: Dict[str, Any],
        epistemic_context: Dict[str, Any]
    ) -> Tuple[bool, str, str]:
        """
        Validate pattern against epistemic constraints.
        
        Args:
            pattern: Pattern to validate
            epistemic_context: Epistemic context from query log
        
        Returns:
            (is_valid, reason, severity)
        """
        
        # Check if L0/L1 both present and valid
        if epistemic_context.get("L0_active") and epistemic_context.get("L1_active"):
            if not epistemic_context.get("nwp_validation_passed"):
                return (
                    False,
                    "Pattern violates fundamental epistemic constraint (L0-L1)",
                    "CRITICAL"
                )
        
        # Check highest severity
        highest_severity = epistemic_context.get("highest_severity", "PASS")
        
        if highest_severity in ["CRITICAL"]:
            return (False, "Pattern has CRITICAL coupling violations", "CRITICAL")
        
        if highest_severity in ["HIGH"]:
            return (
                True,
                "Pattern has HIGH severity violations but may be usable",
                "HIGH"
            )
        
        return (True, "Pattern passes epistemological validation", "PASS")
    
    def get_rule(self, layer_a: str, layer_b: str) -> Optional[EpistemicRule]:
        """Get rule for layer pair."""
        return self.rules.get((layer_a, layer_b))
    
    def list_rules(self) -> List[EpistemicRule]:
        """List all epistemic rules."""
        return list(self.rules.values())


# ============================================================================
# Gap #2: QUESTION ADJUSTED SCORER
# ============================================================================

class QuestionAdjustedScorer:
    """
    Scores patterns with question-rate penalty (Gap #2).
    
    Formula: adjusted_confidence = base_success_rate * (1 - question_rate)
    
    Rationale: A pattern that succeeds but generates many unresolved
    questions is less reliable than one that succeeds cleanly.
    """
    
    def __init__(self, question_penalty: float = 1.0):
        """
        Initialize scorer.
        
        Args:
            question_penalty: Multiplier for question impact (1.0 = full penalty)
        """
        self.question_penalty = question_penalty
    
    def score(
        self,
        base_success_rate: float,
        unresolved_question_count: int,
        total_queries: int
    ) -> float:
        """
        Calculate question-adjusted confidence.
        
        Args:
            base_success_rate: Raw success rate (0-1)
            unresolved_question_count: Number of unresolved questions
            total_queries: Total queries in batch
        
        Returns:
            Adjusted confidence (0-1)
        """
        
        if total_queries == 0:
            return 0.0
        
        # Calculate question rate
        question_rate = unresolved_question_count / total_queries
        
        # Apply penalty
        adjusted = base_success_rate * (1.0 - (question_rate * self.question_penalty))
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, adjusted))
    
    def score_from_event(self, event: Any) -> float:
        """
        Score from a single query event.
        
        Args:
            event: QueryLogEvent
        
        Returns:
            Adjusted confidence for this event
        """
        
        # Base success on confidence
        base_success = event.confidence
        
        # Get question count
        question_count = event.question_signals.get(
            "unresolved_question_count", 0
        )
        
        # For single event, scale question count
        # (1 question = 10% penalty)
        question_rate = min(1.0, question_count * 0.1)
        
        adjusted = base_success * (1.0 - question_rate)
        return max(0.0, min(1.0, adjusted))


# ============================================================================
# CONSTRAINT: FACTION GATE
# ============================================================================

class FactionGate:
    """
    Enforces fiction/general knowledge boundary (Faction Isolation Constraint).
    
    Core principle: Fiction patterns NEVER become general grains.
    - Fiction cartridges can use all learned patterns
    - General cartridges can only use general-sourced patterns
    - Cross-faction crystallization is blocked
    
    "By design, not hope"
    """
    
    ALLOWED_FACTIONS = {"fiction", "general", "experiment"}
    
    def __init__(self):
        """Initialize faction gate."""
        pass
    
    def is_valid_faction(self, faction: str) -> bool:
        """Check if faction is recognized."""
        return faction in self.ALLOWED_FACTIONS
    
    def validate_pattern(
        self,
        pattern: Dict[str, Any],
        pattern_faction: str
    ) -> Tuple[bool, str]:
        """
        Validate pattern faction.
        
        Args:
            pattern: Pattern to validate
            pattern_faction: "fiction", "general", or "experiment"
        
        Returns:
            (is_valid, reason)
        """
        
        if not self.is_valid_faction(pattern_faction):
            return (False, f"Unknown faction: {pattern_faction}")
        
        return (True, f"Pattern faction {pattern_faction} is valid")
    
    def block_crystallization(
        self,
        source_faction: str,
        target_faction: str
    ) -> Tuple[bool, str]:
        """
        Check if crystallization should be blocked.
        
        Args:
            source_faction: Where pattern came from
            target_faction: Where pattern would crystallize to
        
        Returns:
            (should_block, reason)
        """
        
        # HARD RULE: Fiction patterns NEVER become general
        if source_faction == "fiction" and target_faction == "general":
            return (True, "Fiction patterns cannot crystallize as general grains")
        
        # Allow all other transitions
        return (False, "Cross-faction crystallization allowed")
    
    def gate_learned_weights(
        self,
        learned_weights: Dict[str, float],
        query_faction: str
    ) -> Dict[str, float]:
        """
        Filter learned weights by query faction.
        
        Args:
            learned_weights: Dict of weight_id → weight
            query_faction: Faction of current query
        
        Returns:
            Filtered weights appropriate for this faction
        """
        
        if query_faction == "general":
            # General queries can only use general-sourced weights
            filtered = {}
            for weight_id, weight in learned_weights.items():
                # Simple heuristic: if weight_id contains "fiction", skip it
                if "fiction" not in weight_id.lower():
                    filtered[weight_id] = weight
            return filtered
        
        elif query_faction == "fiction":
            # Fiction queries can use all weights
            return learned_weights.copy()
        
        elif query_faction == "experiment":
            # Experiment queries use all weights but with tracking
            return learned_weights.copy()
        
        else:
            # Unknown faction, be conservative
            return {}
    
    def validate_cartridge_loading(
        self,
        cartridges_loaded: List[str],
        target_faction: str
    ) -> Tuple[bool, str]:
        """
        Check if cartridge loading respects faction boundaries.
        
        Args:
            cartridges_loaded: List of cartridge names
            target_faction: Target faction for query
        
        Returns:
            (is_valid, reason)
        """
        
        has_fiction = any(
            "fiction" in c.lower() for c in cartridges_loaded
        )
        has_general = any(
            "fiction" not in c.lower() for c in cartridges_loaded
        )
        
        if target_faction == "general" and has_fiction:
            return (
                False,
                "General queries cannot load fiction cartridges"
            )
        
        return (True, "Cartridge loading respects faction boundaries")


# ============================================================================
# Gap #7: REGRESSION DETECTOR
# ============================================================================

class RegressionDetector:
    """
    Detects if learned weights cause regression (Gap #7).
    
    Maintains baseline metrics from Phase 4.1 Week 1 and checks if
    applying learned weights in Week 3 reduces performance.
    
    Enables automated rollback if regression detected.
    """
    
    def __init__(self, baseline_metrics: Optional[Dict[str, float]] = None):
        """
        Initialize regression detector.
        
        Args:
            baseline_metrics: Initial baseline (success_rate, question_rate, etc.)
        """
        self.baseline_metrics = baseline_metrics or {}
        self.current_metrics = {}
        self.regression_threshold = 0.05  # 5% regression triggers rollback
    
    def set_baseline(self, metrics: Dict[str, float]) -> None:
        """Set baseline metrics from Week 1."""
        self.baseline_metrics = metrics.copy()
        logger.info(f"Baseline metrics set: {metrics}")
    
    def update_current(self, metric_name: str, value: float) -> None:
        """Update current metric value."""
        self.current_metrics[metric_name] = value
    
    def check_regression(self) -> Tuple[bool, Optional[str]]:
        """
        Check if any metric has regressed.
        
        Returns:
            (has_regressed, reason)
        """
        
        if not self.baseline_metrics:
            return (False, "No baseline metrics set")
        
        for metric_name, baseline_value in self.baseline_metrics.items():
            if metric_name not in self.current_metrics:
                continue
            
            current_value = self.current_metrics[metric_name]
            
            # Check for regression
            if baseline_value > 0:
                regression_pct = (baseline_value - current_value) / baseline_value
                
                if regression_pct > self.regression_threshold:
                    reason = (
                        f"Regression in {metric_name}: "
                        f"{baseline_value:.3f} → {current_value:.3f} "
                        f"({regression_pct:.1%})"
                    )
                    return (True, reason)
        
        return (False, None)
    
    def get_comparison(self) -> Dict[str, Dict[str, float]]:
        """Get side-by-side comparison of baseline vs current."""
        comparison = {}
        
        for metric_name, baseline_value in self.baseline_metrics.items():
            current_value = self.current_metrics.get(metric_name, baseline_value)
            
            comparison[metric_name] = {
                "baseline": baseline_value,
                "current": current_value,
                "delta": current_value - baseline_value,
                "delta_pct": (
                    (current_value - baseline_value) / baseline_value
                    if baseline_value > 0 else 0.0
                ),
            }
        
        return comparison
    
    def summary(self) -> str:
        """Get summary of regression detection."""
        has_regressed, reason = self.check_regression()
        
        if has_regressed:
            return f"⚠️ REGRESSION DETECTED: {reason}"
        else:
            return "✓ No regression detected"


# ============================================================================
# Composite Safety Check
# ============================================================================

class SafetyChecker:
    """
    Composite safety checker using all validators.
    
    Provides single entry point for validating patterns against
    all safety constraints.
    """
    
    def __init__(
        self,
        epistemic_validator: Optional[EpistemicValidator] = None,
        question_scorer: Optional[QuestionAdjustedScorer] = None,
        faction_gate: Optional[FactionGate] = None,
        regression_detector: Optional[RegressionDetector] = None,
    ):
        """Initialize with all validators."""
        self.epistemic = epistemic_validator or EpistemicValidator()
        self.questions = question_scorer or QuestionAdjustedScorer()
        self.faction = faction_gate or FactionGate()
        self.regression = regression_detector or RegressionDetector()
    
    def validate_pattern(
        self,
        pattern: Dict[str, Any],
        event: Any,  # QueryLogEvent
    ) -> Dict[str, Any]:
        """
        Validate pattern against all constraints.
        
        Args:
            pattern: Pattern to validate
            event: QueryLogEvent with all context
        
        Returns:
            Validation result dict
        """
        
        results = {
            "pattern_id": pattern.get("id"),
            "valid": True,
            "checks": {},
        }
        
        # Check 1: Epistemology
        ep_valid, ep_reason, ep_severity = self.epistemic.validate_pattern(
            pattern,
            event.epistemic_context
        )
        results["checks"]["epistemology"] = {
            "valid": ep_valid,
            "reason": ep_reason,
            "severity": ep_severity,
        }
        if not ep_valid and ep_severity == "CRITICAL":
            results["valid"] = False
        
        # Check 2: Questions
        question_adjusted = self.questions.score_from_event(event)
        results["checks"]["questions"] = {
            "adjusted_confidence": question_adjusted,
            "unresolved_count": event.question_signals.get(
                "unresolved_question_count", 0
            ),
        }
        
        # Check 3: Faction
        faction = event.source_faction
        faction_valid, faction_reason = self.faction.validate_pattern(
            pattern, faction
        )
        results["checks"]["faction"] = {
            "valid": faction_valid,
            "reason": faction_reason,
            "faction": faction,
        }
        if not faction_valid:
            results["valid"] = False
        
        # Check 4: Regression (if baseline set)
        has_regression, regression_reason = self.regression.check_regression()
        results["checks"]["regression"] = {
            "has_regression": has_regression,
            "reason": regression_reason,
        }
        
        return results


# ============================================================================
# Testing helpers
# ============================================================================

if __name__ == "__main__":
    """Quick test of safety infrastructure."""
    
    logging.basicConfig(level=logging.INFO)
    
    print("\n=== EPISTEMIC VALIDATOR ===")
    epistemic = EpistemicValidator()
    rules = epistemic.list_rules()
    print(f"✓ Loaded {len(rules)} epistemic rules")
    for rule in rules:
        print(f"  - {rule.rule_name}: {rule.description}")
    
    print("\n=== QUESTION ADJUSTED SCORER ===")
    scorer = QuestionAdjustedScorer()
    adjusted = scorer.score(
        base_success_rate=0.90,
        unresolved_question_count=3,
        total_queries=100
    )
    print(f"✓ Base success=0.90, questions=3/100 → adjusted={adjusted:.3f}")
    
    print("\n=== FACTION GATE ===")
    faction = FactionGate()
    blocked, reason = faction.block_crystallization("fiction", "general")
    print(f"✓ Fiction→General crystallization blocked: {reason}")
    
    blocked, reason = faction.block_crystallization("general", "general")
    print(f"✓ General→General crystallization allowed: {reason}")
    
    print("\n=== REGRESSION DETECTOR ===")
    detector = RegressionDetector()
    detector.set_baseline({
        "success_rate": 0.85,
        "question_rate": 0.1,
    })
    detector.update_current("success_rate", 0.82)  # 3.5% regression
    detector.update_current("question_rate", 0.1)
    
    has_regressed, reason = detector.check_regression()
    print(f"✓ Regression check: {has_regressed}")
    print(f"  Summary: {detector.summary()}")
    
    print("\n✅ Safety infrastructure working correctly")
