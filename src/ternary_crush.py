"""
Ternary Crush - Compress phantoms to ternary grain representation

Converts high-entropy phantoms (~1000 bits context) into 
1.58-bit ternary grains (~32 bits core + metadata).

Phase 2C Week 2 - Crystallization Core
"""

import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from kitbash_cartridge import Cartridge
from kitbash_registry import PhantomCandidate


@dataclass
class TernaryDelta:
    """Ternary relationship representation."""
    positive: List[str]  # Dependencies (+1): what this depends on
    negative: List[str]  # Negations (-1): what contradicts this
    void: List[str]      # Independence (0): what's orthogonal


class TernaryCrush:
    """
    Compress validated phantoms to ternary grain representation.
    
    Strategy:
    - Extract top 5 derivations from fact annotations
    - Map to ternary relationships {-1, 0, 1}
    - Build pointer map for O(1) lookup
    - Calculate 1.58-bit weight encoding
    """
    
    def __init__(self, cartridge: Cartridge):
        """Initialize crusher for a specific cartridge."""
        self.cartridge = cartridge
        self.cartridge_id = cartridge.name
    
    def crush_phantom(self, phantom: PhantomCandidate,
                     validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crush a validated phantom into ternary grain.
        
        Args:
            phantom: PhantomCandidate from registry
            validation_result: Result from AxiomValidator
        
        Returns:
            Ternary grain structure ready for crystallization
        """
        
        if not validation_result.get('locked'):
            raise ValueError(f"Cannot crush unvalidated phantom {phantom.fact_id}")
        
        # Get fact content
        fact_text = self.cartridge.get_fact(phantom.fact_id)
        if not fact_text:
            raise ValueError(f"Fact {phantom.fact_id} not found in cartridge")
        
        # Extract derivations
        try:
            fact_obj = self.cartridge.get_fact_object(phantom.fact_id)
            derivations = fact_obj.derivations if fact_obj else []
        except:
            derivations = []
        
        # Map to ternary
        ternary_delta = self._extract_ternary_delta(fact_text, derivations)
        
        # Build pointer map (fast lookup structure)
        pointer_map = self._build_pointer_map(phantom, ternary_delta)
        
        # Calculate weight (1.58-bit equivalent)
        weight = self._calculate_weight(ternary_delta)
        
        # Generate grain ID (deterministic from fact)
        grain_id = self._generate_grain_id(phantom.fact_id, self.cartridge_id)
        
        return {
            'grain_id': grain_id,
            'fact_id': phantom.fact_id,
            'cartridge_id': self.cartridge_id,
            'delta': {
                'positive': ternary_delta.positive,
                'negative': ternary_delta.negative,
                'void': ternary_delta.void,
            },
            'weight': weight,
            'pointer_map': pointer_map,
            'confidence': validation_result['confidence'],
            'cycles_locked': validation_result['cycles_locked'],
            'fact_snippet': fact_text[:100],  # For debugging
        }
    
    def _extract_ternary_delta(self, fact_text: str,
                              derivations: List[Any]) -> TernaryDelta:
        """
        Extract ternary relationships from fact and derivations.
        
        Strategy: Parse fact text and derivations for relationship keywords,
        classify as positive (dependencies), negative (contradictions),
        or void (independence).
        """
        
        positive = []
        negative = []
        void = []
        
        # Extract from derivations (structured)
        for deriv in derivations:
            if not deriv:
                continue
            
            deriv_str = str(deriv).lower()
            deriv_type = deriv.get('type', '') if isinstance(deriv, dict) else ''
            target = deriv.get('target', '') if isinstance(deriv, dict) else ''
            
            # Classify by type
            if 'dependency' in deriv_type or 'requires' in deriv_type:
                if target:
                    positive.append(target)
            elif 'negation' in deriv_type or 'inverse' in deriv_type:
                if target:
                    negative.append(target)
            elif 'independent' in deriv_type or 'orthogonal' in deriv_type:
                if target:
                    void.append(target)
            elif 'boundary' in deriv_type:
                # Boundary conditions = constraints (negative/restriction)
                if target:
                    negative.append(f"constrained_by:{target}")
        
        # Extract from fact text (unstructured) - keyword heuristics
        fact_lower = fact_text.lower()
        
        # Keywords suggesting dependency
        dep_keywords = ['requires', 'depends on', 'needs', 'causes', 'leads to', 
                       'enables', 'triggers', 'necessary for', 'sufficient for']
        for kw in dep_keywords:
            if kw in fact_lower:
                # Extract concept after keyword
                idx = fact_lower.find(kw)
                snippet = fact_text[idx:idx+50].strip()
                if snippet not in positive:
                    positive.append(f"inferred:{snippet[:30]}")
        
        # Keywords suggesting negation
        neg_keywords = ['not', 'cannot', 'opposite', 'contradicts', 'conflicts',
                       'incompatible', 'prevents', 'blocks', 'inhibits', 'never']
        for kw in neg_keywords:
            if kw in fact_lower:
                idx = fact_lower.find(kw)
                snippet = fact_text[idx:idx+50].strip()
                if snippet not in negative:
                    negative.append(f"inferred:{snippet[:30]}")
        
        # Keywords suggesting independence
        indep_keywords = ['independent', 'orthogonal', 'unrelated', 'separate',
                         'parallel', 'distinct', 'isolated']
        for kw in indep_keywords:
            if kw in fact_lower:
                idx = fact_lower.find(kw)
                snippet = fact_text[idx:idx+50].strip()
                if snippet not in void:
                    void.append(f"inferred:{snippet[:30]}")
        
        # Limit to top N per category for compression
        positive = self._rank_and_limit(positive, 3)
        negative = self._rank_and_limit(negative, 2)
        void = self._rank_and_limit(void, 2)
        
        return TernaryDelta(
            positive=positive,
            negative=negative,
            void=void
        )
    
    def _rank_and_limit(self, items: List[str], limit: int) -> List[str]:
        """Rank by specificity and limit to top N."""
        if not items:
            return []
        
        # Remove duplicates, rank by length (longer = more specific)
        unique = list(dict.fromkeys(items))  # Remove duplicates, preserve order
        unique = sorted(unique, key=len, reverse=True)
        return unique[:limit]
    
    def _build_pointer_map(self, phantom: PhantomCandidate,
                          ternary: TernaryDelta) -> Dict[str, Any]:
        """
        Build pointer map for O(1) relationship lookup.
        
        Maps concept names to bit positions for fast ternary resolution.
        """
        
        pointer_map = {
            'positive_ptrs': {},
            'negative_ptrs': {},
            'void_ptrs': {},
            'access_pattern': {
                'hit_count': phantom.hit_count,
                'confidence': phantom._avg_confidence(),
                'first_seen': phantom.first_cycle_seen,
                'last_seen': phantom.last_cycle_seen,
            }
        }
        
        # Assign bit positions (0-indexed)
        bit_pos = 0
        
        for concept in ternary.positive:
            pointer_map['positive_ptrs'][concept] = {
                'bit_position': bit_pos,
                'value': 1,  # Positive relation
            }
            bit_pos += 1
        
        for concept in ternary.negative:
            pointer_map['negative_ptrs'][concept] = {
                'bit_position': bit_pos,
                'value': -1,  # Negative relation
            }
            bit_pos += 1
        
        for concept in ternary.void:
            pointer_map['void_ptrs'][concept] = {
                'bit_position': bit_pos,
                'value': 0,  # Independence
            }
            bit_pos += 1
        
        pointer_map['total_bits'] = bit_pos
        
        return pointer_map
    
    def _calculate_weight(self, ternary: TernaryDelta) -> float:
        """
        Calculate 1.58-bit weight encoding.
        
        Weight = log2(3) * bit_count
        Since ternary (3 states), each position = 1.58 bits
        """
        
        total_concepts = (len(ternary.positive) + 
                         len(ternary.negative) + 
                         len(ternary.void))
        
        # 1 ternary position = log2(3) ≈ 1.585 bits
        weight = total_concepts * 1.585
        
        return round(weight, 2)
    
    def _generate_grain_id(self, fact_id: int, cartridge_id: str) -> str:
        """Generate deterministic grain ID from fact identity."""
        
        # Hash-based ID: sg_XXXXXXXX
        hash_input = f"{cartridge_id}:{fact_id}".encode()
        hash_obj = hashlib.sha256(hash_input)
        hex_hash = hash_obj.hexdigest()[:8]
        
        return f"sg_{hex_hash.upper()}"
    
    def crush_all_phantoms(self, 
                          phantoms: Dict[int, PhantomCandidate],
                          validation_results: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Crush all validated phantoms to ternary grains.
        
        Args:
            phantoms: Dict of fact_id -> PhantomCandidate
            validation_results: Dict of fact_id -> validation result
        
        Returns:
            List of crushed grain structures
        """
        
        grains = []
        
        for fact_id, phantom in phantoms.items():
            # Get validation result for this phantom
            val_result = validation_results.get(fact_id)
            
            if val_result and val_result.get('locked'):
                try:
                    grain = self.crush_phantom(phantom, val_result)
                    grains.append(grain)
                except Exception as e:
                    print(f"Warning: Could not crush phantom {fact_id}: {e}")
        
        return grains
    
    def print_compression_stats(self, original_size: int, crushed_grains: List[Dict]) -> None:
        """Print compression statistics."""
        
        if not crushed_grains:
            print("No grains crushed")
            return
        
        crushed_size = sum(len(json.dumps(g)) for g in crushed_grains)
        compression_ratio = (1 - crushed_size / original_size) * 100 if original_size else 0
        
        print("\n" + "="*70)
        print("TERNARY CRUSH COMPRESSION REPORT")
        print("="*70)
        print(f"Original registry size: {original_size:,} bytes")
        print(f"Crushed grain size: {crushed_size:,} bytes")
        print(f"Compression achieved: {compression_ratio:.1f}%")
        print(f"Grains created: {len(crushed_grains)}")
        
        avg_weight = sum(g.get('weight', 0) for g in crushed_grains) / len(crushed_grains)
        print(f"Average grain weight: {avg_weight:.2f} bits")
        print("="*70 + "\n")
