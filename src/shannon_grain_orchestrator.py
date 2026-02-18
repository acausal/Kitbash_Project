"""
Shannon Grain Orchestrator
Phase 2A: End-to-end grain crystallization pipeline

Coordinates:
1. Phantom tracking (DeltaRegistry integration)
2. Axiom validation (3-rule quality gates)
3. Ternary crush (compression to grains)
4. Grain activation (L3 cache loading)

Output: Crystallized grains ready for reflex deployment
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

from shannon_grain import (
    PhantomTracker, PhantomCandidate, GrainRegistry, GrainMetadata, GrainState
)
from axiom_validator import AxiomValidator, ValidationRule
from ternary_crush import TernaryCrush
from grain_activation import GrainActivation, Hat


# ============================================================================
# CRYSTALLIZATION PIPELINE
# ============================================================================

class ShannonGrainOrchestrator:
    """
    End-to-end orchestration of grain crystallization.
    
    Pipeline:
    1. Track phantoms (persistent patterns)
    2. Detect harmonic lock (50+ cycles stable)
    3. Validate with axiom rules
    4. Crystallize to grains
    5. Activate in L3 cache
    """
    
    def __init__(self, cartridge_id: str, storage_path: str = "./grains"):
        """Initialize orchestrator"""
        self.cartridge_id = cartridge_id
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Core components
        self.phantom_tracker = PhantomTracker(cartridge_id)
        self.axiom_validator = AxiomValidator()
        self.ternary_crusher = TernaryCrush()
        self.grain_registry = GrainRegistry(cartridge_id, str(self.storage_path))
        self.grain_activation = GrainActivation(max_cache_mb=1.0)
        
        # Statistics
        self.crystallization_stats = {
            "total_phantoms_tracked": 0,
            "total_phantoms_locked": 0,
            "total_validated": 0,
            "total_crystallized": 0,
            "total_activated": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
    
    # ========================================================================
    # PHASE 1: PHANTOM TRACKING
    # ========================================================================
    
    def record_phantom_hit(self, fact_ids: set, concepts: List[str],
                          confidence: float) -> None:
        """
        Record a phantom hit (called during query execution).
        
        This integrates with DeltaRegistry - when facts are accessed together
        with high confidence, they form phantoms.
        """
        self.phantom_tracker.record_phantom_hit(
            fact_ids=fact_ids,
            concepts=concepts,
            confidence=confidence
        )
        self.crystallization_stats["total_phantoms_tracked"] += 1
    
    def advance_cycle(self) -> None:
        """
        Advance metabolic cycle (call every ~100 queries).
        
        Detects harmonic locks and identifies grains ready for crystallization.
        """
        self.phantom_tracker.advance_cycle()
    
    # ========================================================================
    # PHASE 2: AXIOM VALIDATION
    # ========================================================================
    
    def get_crystallization_candidates(self) -> List[PhantomCandidate]:
        """
        Get phantoms ready for crystallization.
        
        Returns:
            Locked phantoms (50+ cycles, high consistency)
        """
        locked = self.phantom_tracker.get_locked_phantoms()
        self.crystallization_stats["total_phantoms_locked"] += len(locked)
        return locked
    
    def validate_candidates(self, phantoms: List[PhantomCandidate]) -> Dict:
        """
        Validate phantoms against axiom rules.
        
        Returns:
            Validation report with ready-to-crystallize list
        """
        existing_grains = list(self.grain_registry.grains.values())
        
        validation_report = self.axiom_validator.validate_batch(
            phantoms,
            existing_grains=existing_grains
        )
        
        self.crystallization_stats["total_validated"] += len(phantoms)
        
        return validation_report
    
    # ========================================================================
    # PHASE 3: CRYSTALLIZATION
    # ========================================================================
    
    def crystallize_grains(self, validated_phantoms: List[Dict]) -> List[GrainMetadata]:
        """
        Crystallize validated phantoms into grains.
        
        Args:
            validated_phantoms: List of {phantom_id, fact_ids, confidence}
            
        Returns:
            List of created GrainMetadata objects
        """
        grains = []
        
        for phantom_info in validated_phantoms:
            # Retrieve phantom
            phantom = self._find_phantom(phantom_info["phantom_id"])
            if not phantom:
                continue
            
            # Crush to ternary grain
            grain = self.ternary_crusher.crystallize_grain(
                phantom,
                axiom_ids=[f"axiom_{phantom.cartridge_id}"],
            )
            
            # Mark as crystallized
            grain.state = GrainState.CRYSTALLIZED
            grain.crystallized_at = datetime.now(timezone.utc).isoformat()
            
            # Store in registry
            self.grain_registry.add_grain(grain)
            self.grain_registry.save_grain(grain)
            
            grains.append(grain)
            self.crystallization_stats["total_crystallized"] += 1
        
        return grains
    
    # ========================================================================
    # PHASE 4: ACTIVATION
    # ========================================================================
    
    def activate_grains(self, grains: List[GrainMetadata]) -> Dict:
        """
        Load crystallized grains into L3 cache for reflex path.
        
        Returns:
            Activation report
        """
        # Update grain states
        for grain in grains:
            self.grain_registry.update_grain_state(grain.grain_id, GrainState.ACTIVE)
        
        # Load into L3 cache
        activation_report = self.grain_activation.activate_grains(grains)
        
        self.crystallization_stats["total_activated"] += activation_report["loaded"]
        
        return activation_report
    
    # ========================================================================
    # END-TO-END PIPELINE
    # ========================================================================
    
    def run_crystallization_cycle(self) -> Dict:
        """
        Run complete crystallization cycle.
        
        Steps:
        1. Get locked phantoms
        2. Validate with axiom rules
        3. Crystallize to grains
        4. Activate in L3 cache
        
        Returns:
            Complete report
        """
        cycle_start = time.time()
        
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase_1_phantoms": {},
            "phase_2_validation": {},
            "phase_3_crystallization": {},
            "phase_4_activation": {},
            "total_latency_ms": 0,
        }
        
        # Phase 1: Get candidates
        t1_start = time.time()
        candidates = self.get_crystallization_candidates()
        report["phase_1_phantoms"] = {
            "locked_count": len(candidates),
            "latency_ms": round((time.time() - t1_start) * 1000, 2),
        }
        
        if not candidates:
            report["verdict"] = "No phantoms ready for crystallization"
            return report
        
        # Phase 2: Validate
        t2_start = time.time()
        validation_report = self.validate_candidates(candidates)
        ready_to_crystallize = validation_report["crystallization_ready"]
        report["phase_2_validation"] = {
            "total_validated": validation_report["total_phantoms"],
            "passed_all_rules": len(ready_to_crystallize),
            "rejection_rate": round(validation_report["summary"]["rejection_rate"], 3),
            "latency_ms": round((time.time() - t2_start) * 1000, 2),
        }
        
        if not ready_to_crystallize:
            report["phase_3_crystallization"] = {"grains_created": 0}
            report["phase_4_activation"] = {"loaded": 0, "failed": 0}
            report["verdict"] = "All candidates rejected by validation"
            return report
        
        # Phase 3: Crystallize
        t3_start = time.time()
        crystallized_grains = self.crystallize_grains(ready_to_crystallize)
        report["phase_3_crystallization"] = {
            "grains_created": len(crystallized_grains),
            "total_size_mb": sum(g.size_mb() for g in crystallized_grains),
            "avg_grain_size_bytes": sum(
                len(g.bit_array_plus) + len(g.bit_array_minus)
                for g in crystallized_grains
            ) / len(crystallized_grains) if crystallized_grains else 0,
            "latency_ms": round((time.time() - t3_start) * 1000, 2),
        }
        
        # Phase 4: Activate
        t4_start = time.time()
        activation_report = self.activate_grains(crystallized_grains)
        report["phase_4_activation"] = {
            "loaded": activation_report["loaded"],
            "failed": activation_report["failed"],
            "cache_utilization_percent": activation_report["cache_stats"]["utilization_percent"],
            "latency_ms": round((time.time() - t4_start) * 1000, 2),
        }
        
        # Calculate total latency
        total_latency = time.time() - cycle_start
        report["total_latency_ms"] = round(total_latency * 1000, 2)
        
        # Final verdict
        if crystallized_grains:
            report["verdict"] = f"✅ CRYSTALLIZATION SUCCESS - {len(crystallized_grains)} grains created and activated"
        else:
            report["verdict"] = "❌ CRYSTALLIZATION FAILED"
        
        return report
    
    # ========================================================================
    # UTILITIES
    # ========================================================================
    
    def _find_phantom(self, phantom_id: str) -> Optional[PhantomCandidate]:
        """Find phantom by ID"""
        for phantom in self.phantom_tracker.phantoms.values():
            if phantom.phantom_id == phantom_id:
                return phantom
        return None
    
    def get_stats(self) -> Dict:
        """Get orchestrator statistics"""
        stats = self.crystallization_stats.copy()
        stats.update({
            "phantom_tracker": self.phantom_tracker.get_stats(),
            "grain_registry": self.grain_registry.get_stats(),
            "activation": self.grain_activation.get_stats(),
        })
        return stats
    
    def save_report(self, report: Dict, filepath: str) -> None:
        """Save crystallization report to JSON"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(report, f, indent=2)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print("Shannon Grain Orchestrator - Full Pipeline Test\n")
    print("=" * 70)
    
    # Initialize orchestrator
    orchestrator = ShannonGrainOrchestrator("test_cartridge")
    
    # Simulate phantom tracking over 60 cycles
    print("\nPhase 1: Phantom Tracking (simulating 60 cycles)")
    print("-" * 70)
    
    for cycle in range(60):
        # Simulate 5 queries per cycle
        for i in range(5):
            orchestrator.record_phantom_hit(
                fact_ids={1, 2, 3},
                concepts=["test", "example"],
                confidence=0.85 + (i * 0.02)
            )
        
        orchestrator.advance_cycle()
        
        if (cycle + 1) % 10 == 0:
            stats = orchestrator.phantom_tracker.get_stats()
            print(f"  Cycle {cycle + 1}: {stats['persistent_count']} persistent, {stats['locked_count']} locked")
    
    # Run crystallization cycle
    print("\nPhase 2-4: Validation → Crystallization → Activation")
    print("-" * 70)
    
    report = orchestrator.run_crystallization_cycle()
    
    # Print report
    print(f"\nCrystallization Report:")
    print(f"  Phase 1 (Tracking): {report['phase_1_phantoms']['locked_count']} locked phantoms")
    print(f"  Phase 2 (Validation): {report['phase_2_validation']['passed_all_rules']} passed validation")
    print(f"  Phase 3 (Crystallization): {report['phase_3_crystallization']['grains_created']} grains created")
    print(f"  Phase 4 (Activation): {report['phase_4_activation']['loaded']} grains activated")
    print(f"\nTotal Latency: {report['total_latency_ms']:.2f}ms")
    print(f"Verdict: {report['verdict']}")
    
    # Final stats
    print("\nFinal Statistics:")
    orchestrator_stats = orchestrator.get_stats()
    print(f"  Total crystallized: {orchestrator_stats['total_crystallized']}")
    print(f"  Total activated: {orchestrator_stats['total_activated']}")
    print(f"  Cache utilization: {orchestrator_stats['activation']['cache']['utilization_percent']}%")
    
    print("\n" + "=" * 70)
    print("✅ Orchestrator test complete")
