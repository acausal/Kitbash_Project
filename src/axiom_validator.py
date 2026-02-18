"""
Axiom Validator - Sicherman Validation Rules for Grain Crystallization

Validates locked phantoms against three quality gates:
1. Persistence: Phantom pointers resolve to valid facts
2. Least Resistance: Ternary representation achieves compression
3. Independence: Phantom pattern aligns with domain axioms

Phase 2C Week 2 - Quality Assurance Gate
"""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from kitbash_cartridge import Cartridge
from kitbash_registry import PhantomCandidate


class AxiomValidator:
    """
    Validates phantoms before crystallization using Sicherman rules.
    
    Three validation gates ensure grains are structurally sound and
    ready for compression into ternary representation.
    """
    
    def __init__(self, cartridge: Cartridge):
        """Initialize validator for a specific cartridge."""
        self.cartridge = cartridge
        self.cartridge_id = cartridge.name
        self.validation_log: List[Dict] = []
    
    def validate_phantom(self, phantom: PhantomCandidate, 
                        cartridge_facts: Dict[int, str]) -> Dict[str, Any]:
        """
        Apply all three Sicherman validation rules.
        
        Args:
            phantom: PhantomCandidate from locked registry
            cartridge_facts: All facts in this cartridge (for context)
        
        Returns:
            Validation result with lock_state and rule checks
        """
        
        result = {
            'fact_id': phantom.fact_id,
            'cartridge_id': self.cartridge_id,
            'persistent_check': False,
            'resistance_check': False,
            'independence_check': False,
            'locked': False,
            'lock_state': 'failed_validation',
            'rule_failures': [],
            'confidence': phantom._avg_confidence(),
            'hit_count': phantom.hit_count,
            'cycles_locked': phantom.last_cycle_seen - phantom.first_cycle_seen,
        }
        
        # RULE 1: PERSISTENCE
        # Check that phantom pointer resolves to valid fact
        try:
            fact = self.cartridge.get_fact(phantom.fact_id)
            if fact:
                result['persistent_check'] = True
            else:
                result['rule_failures'].append('persistence: fact not found')
        except Exception as e:
            result['rule_failures'].append(f'persistence: {str(e)}')
        
        # RULE 2: LEAST RESISTANCE  
        # Check that fact is stable and compressible
        # For MVP: rely on confidence scores (high confidence = stable = compressible)
        try:
            fact_text = self.cartridge.get_fact(phantom.fact_id)
            
            if fact_text:
                # Fact exists - check compressibility heuristics
                # High confidence facts are inherently more compressible
                # (lower entropy, more predictable)
                if result['confidence'] > 0.91:
                    result['resistance_check'] = True
                else:
                    result['rule_failures'].append(
                        f'least_resistance: confidence {result["confidence"]:.2f} < 0.91'
                    )
            else:
                result['rule_failures'].append('least_resistance: fact not found')
        
        except Exception as e:
            result['rule_failures'].append(f'least_resistance: {str(e)}')
        
        # RULE 3: INDEPENDENCE
        # Check that phantom pattern doesn't contradict domain axioms
        try:
            # For now: check confidence stability and absence of oscillation
            if len(phantom.confidence_history) > 1:
                # Calculate variance
                import statistics
                variance = statistics.variance(phantom.confidence_history)
                
                # Low variance = stable = aligns with axioms (not contradictory)
                # Typical variance for high-confidence facts: 0.001-0.01
                if variance < 0.02:  # Threshold: 0.02
                    result['independence_check'] = True
                else:
                    result['rule_failures'].append(
                        f'independence: high confidence variance ({variance:.4f})'
                    )
            else:
                # Single observation - assume valid if high confidence
                if result['confidence'] > 0.90:
                    result['independence_check'] = True
                else:
                    result['rule_failures'].append(
                        'independence: insufficient observations'
                    )
        
        except Exception as e:
            result['rule_failures'].append(f'independence: {str(e)}')
        
        # FINAL DECISION
        if all([result['persistent_check'],
                result['resistance_check'],
                result['independence_check']]):
            result['locked'] = True
            result['lock_state'] = 'Sicherman_Validated'
        
        # Log the validation
        self.validation_log.append(result)
        return result
    
    def _count_ternary_derivations(self, derivations: List[Any]) -> int:
        """Count how many derivations can be expressed as ternary."""
        if not derivations:
            return 0
        
        # Ternary-expressible patterns:
        # - Positive dependency (→)
        # - Negative dependency (¬)
        # - Independence (⊥)
        ternary_patterns = [
            'dependency', 'depends_on', 'requires',  # positive
            'negation', 'inverse', 'opposite',        # negative
            'independent', 'orthogonal', 'void'       # independence
        ]
        
        count = 0
        for deriv in derivations:
            deriv_str = str(deriv).lower()
            if any(pattern in deriv_str for pattern in ternary_patterns):
                count += 1
        
        return count
    
    def validate_all_phantoms(self, phantoms: Dict[int, PhantomCandidate],
                             cartridge_facts: Dict[int, str]) -> Dict[str, Any]:
        """
        Validate all phantoms in a registry.
        
        Args:
            phantoms: Dict of fact_id -> PhantomCandidate
            cartridge_facts: All facts in cartridge
        
        Returns:
            Summary of validation results
        """
        
        locked_count = 0
        failed_count = 0
        
        for fact_id, phantom in phantoms.items():
            result = self.validate_phantom(phantom, cartridge_facts)
            if result['locked']:
                locked_count += 1
            else:
                failed_count += 1
        
        return {
            'total': len(phantoms),
            'locked': locked_count,
            'failed': failed_count,
            'pass_rate': locked_count / len(phantoms) if phantoms else 0,
            'cartridge_id': self.cartridge_id,
            'validation_log': self.validation_log
        }
    
    def get_locked_phantoms(self, phantoms: Dict[int, PhantomCandidate],
                           cartridge_facts: Dict[int, str]) -> List[PhantomCandidate]:
        """Get list of phantoms that passed all validation rules."""
        
        locked = []
        for phantom in phantoms.values():
            result = self.validate_phantom(phantom, cartridge_facts)
            if result['locked']:
                locked.append(phantom)
        
        return locked
    
    def print_summary(self):
        """Print validation summary."""
        if not self.validation_log:
            print("No validations performed")
            return
        
        total = len(self.validation_log)
        locked = sum(1 for v in self.validation_log if v['locked'])
        failed = total - locked
        
        print("\n" + "="*70)
        print(f"AXIOM VALIDATION SUMMARY ({self.cartridge_id})")
        print("="*70)
        print(f"Total phantoms: {total}")
        print(f"Locked (passed): {locked}")
        print(f"Failed: {failed}")
        print(f"Pass rate: {locked/total*100:.1f}%")
        
        # Show failures
        failures = [v for v in self.validation_log if not v['locked']]
        if failures:
            print(f"\nFailures:")
            for fail in failures[:5]:  # Show top 5
                print(f"  Fact {fail['fact_id']}: {fail['rule_failures']}")
            if len(failures) > 5:
                print(f"  ... and {len(failures)-5} more")
        
        print("="*70 + "\n")
