#!/usr/bin/env python3
"""
Phase 2C Week 2: Grain Crystallization Pipeline Orchestrator

Coordinates all steps: validation → crushing → crystallization → 
activation testing → compression measurement

Master script for complete Phase 2C Week 2 closure.
"""

import json
from pathlib import Path
from typing import Dict, List, Any

from kitbash_cartridge import Cartridge
from kitbash_query_engine import CartridgeQueryEngine
from kitbash_registry import DeltaRegistry

from axiom_validator import AxiomValidator
from ternary_crush import TernaryCrush
from grain_crystallizer import GrainCrystallizer, GrainCrystallizationReport
from grain_activation_tester import GrainActivationTester, CompressionMeasurer


class CrystallizationOrchestrator:
    """
    Master orchestrator for grain crystallization pipeline.
    
    Steps:
    1. Load locked phantoms from registries
    2. Validate phantoms (Sicherman rules)
    3. Crush to ternary representation
    4. Crystallize to grain files
    5. Test grain activation
    6. Measure compression
    """
    
    def __init__(self, cartridges_dir: str = "./cartridges",
                 registry_dir: str = "./registry"):
        """Initialize orchestrator."""
        self.cartridges_dir = cartridges_dir
        self.registry_dir = registry_dir
        self.engine = CartridgeQueryEngine(cartridges_dir)
        self.results = {
            'validation': {},
            'crystallization': {},
            'activation': {},
            'compression': {},
        }
    
    def run_full_pipeline(self) -> Dict[str, Any]:
        """
        Run complete crystallization pipeline.
        
        Returns:
            Summary results from all stages
        """
        
        print("="*70)
        print("PHASE 2C WEEK 2: GRAIN CRYSTALLIZATION PIPELINE")
        print("="*70)
        
        # Step 1: Load registries
        registries = self._load_registries()
        print(f"\n✓ Loaded {len(registries)} registries")
        
        # Process each cartridge
        for cartridge_id, registry in registries.items():
            print(f"\n" + "="*70)
            print(f"Processing: {cartridge_id}")
            print("="*70)
            
            # Load cartridge
            if cartridge_id not in self.engine.cartridges:
                print(f"⚠ Cartridge {cartridge_id} not loaded, skipping")
                continue
            
            cartridge = self.engine.cartridges[cartridge_id]
            
            # Step 2: Validate phantoms
            locked_phantoms, validation_results = self._validate_phantoms(
                cartridge, registry
            )
            self.results['validation'][cartridge_id] = {
                'total': len(registry.phantoms),
                'locked': len(locked_phantoms),
                'validation_results': validation_results,
            }
            
            print(f"\n✓ Validation: {len(locked_phantoms)}/{len(registry.phantoms)} passed")
            
            if not locked_phantoms:
                print("  (No phantoms passed validation, skipping crystallization)")
                continue
            
            # Step 3: Crush to ternary
            crushed_grains = self._crush_phantoms(
                cartridge, locked_phantoms, validation_results
            )
            print(f"✓ Crushing: {len(crushed_grains)} grains crushed")
            
            # Step 4: Crystallize to files
            crystal_result = self._crystallize_grains(crushed_grains, cartridge_id)
            self.results['crystallization'][cartridge_id] = crystal_result
            print(f"✓ Crystallization: {crystal_result['grain_count']} grains saved")
            
            # Step 5: Test activation
            activation_result = self._test_activation(cartridge_id)
            self.results['activation'][cartridge_id] = activation_result
            print(f"✓ Activation test: {len(activation_result['results'])} grains tested")
            
            # Step 6: Measure compression
            compression = self._measure_compression(cartridge_id)
            self.results['compression'][cartridge_id] = compression
            print(f"✓ Compression: {compression['compression_ratio_percent']:.1f}% reduction")
        
        # Final report
        self._generate_final_report()
        
        return self.results
    
    def _load_registries(self) -> Dict[str, DeltaRegistry]:
        """Load all per-cartridge registries from disk."""
        
        registries = {}
        registry_dir = Path(self.registry_dir)
        
        if not registry_dir.exists():
            print("✗ Registry directory not found")
            return registries
        
        for registry_file in registry_dir.glob("*_registry.json"):
            cartridge_id = registry_file.stem.replace('_registry', '')
            try:
                registry = DeltaRegistry.load(str(registry_file))
                registries[cartridge_id] = registry
            except Exception as e:
                print(f"⚠ Could not load {cartridge_id}: {e}")
        
        return registries
    
    def _validate_phantoms(self, cartridge: Cartridge,
                          registry: DeltaRegistry) -> tuple:
        """Validate all phantoms using Sicherman rules."""
        
        validator = AxiomValidator(cartridge)
        
        locked_phantoms = []
        validation_results = {}
        
        for fact_id, phantom in registry.phantoms.items():
            result = validator.validate_phantom(phantom, cartridge.facts)
            validation_results[fact_id] = result
            
            if result['locked']:
                locked_phantoms.append(phantom)
        
        return locked_phantoms, validation_results
    
    def _crush_phantoms(self, cartridge: Cartridge,
                       locked_phantoms: List,
                       validation_results: Dict) -> List[Dict]:
        """Crush validated phantoms to ternary grains."""
        
        crusher = TernaryCrush(cartridge)
        crushed = []
        
        for phantom in locked_phantoms:
            try:
                val_result = validation_results[phantom.fact_id]
                grain = crusher.crush_phantom(phantom, val_result)
                crushed.append(grain)
            except Exception as e:
                print(f"  ⚠ Could not crush phantom {phantom.fact_id}: {e}")
        
        return crushed
    
    def _crystallize_grains(self, crushed_grains: List[Dict],
                           cartridge_id: str) -> Dict:
        """Crystallize grains to disk."""
        
        crystallizer = GrainCrystallizer(self.cartridges_dir)
        result = crystallizer.crystallize_grains(crushed_grains, cartridge_id)
        
        return result
    
    def _test_activation(self, cartridge_id: str) -> Dict:
        """Test grain activation and latency."""
        
        tester = GrainActivationTester(self.cartridges_dir)
        result = tester.test_all_grains(cartridge_id)
        
        return result
    
    def _measure_compression(self, cartridge_id: str) -> Dict:
        """Measure compression ratio."""
        
        measurer = CompressionMeasurer(self.registry_dir, self.cartridges_dir)
        result = measurer.measure_compression(cartridge_id)
        
        return result
    
    def _generate_final_report(self) -> None:
        """Generate and display final report."""
        
        print("\n" + "="*70)
        print("PHASE 2C WEEK 2: FINAL CRYSTALLIZATION REPORT")
        print("="*70)
        
        # Validation summary
        total_phantoms = 0
        total_locked = 0
        
        print("\nVALIDATION RESULTS:")
        for cart_id, val_result in self.results['validation'].items():
            total = val_result['total']
            locked = val_result['locked']
            total_phantoms += total
            total_locked += locked
            pass_rate = (locked / total * 100) if total > 0 else 0
            print(f"  {cart_id:<20} {locked:3d}/{total:3d} ({pass_rate:5.1f}%)")
        
        print(f"  {'TOTAL':<20} {total_locked:3d}/{total_phantoms:3d} "
              f"({total_locked/total_phantoms*100:5.1f}%)")
        
        # Crystallization summary
        total_grains = 0
        print("\nCRYSTALLIZATION RESULTS:")
        for cart_id, cryst_result in self.results['crystallization'].items():
            grains = cryst_result['grain_count']
            total_grains += grains
            print(f"  {cart_id:<20} {grains:3d} grains saved")
        print(f"  {'TOTAL':<20} {total_grains:3d} grains")
        
        # Activation summary
        print("\nACTIVATION TEST RESULTS:")
        total_tested = 0
        for cart_id, act_result in self.results['activation'].items():
            tested = act_result['grain_count']
            total_tested += tested
            avg_latency = act_result['summary']['avg_load_latency_ms']
            print(f"  {cart_id:<20} {tested:3d} grains, {avg_latency:.2f}ms avg latency")
        print(f"  {'TOTAL':<20} {total_tested:3d} grains tested")
        
        # Compression summary
        print("\nCOMPRESSION RESULTS:")
        total_original = 0
        total_crystallized = 0
        
        for cart_id, comp_result in self.results['compression'].items():
            orig = comp_result['original_size_bytes']
            cryst = comp_result['crystallized_size_bytes']
            ratio = comp_result['compression_ratio_percent']
            total_original += orig
            total_crystallized += cryst
            print(f"  {cart_id:<20} {orig:>10,} → {cryst:>10,} ({ratio:5.1f}%)")
        
        if total_original > 0:
            overall_ratio = (1 - total_crystallized / total_original) * 100
            print(f"  {'TOTAL':<20} {total_original:>10,} → {total_crystallized:>10,} ({overall_ratio:5.1f}%)")
            print(f"\n  Target compression: 93.75%")
            print(f"  Achieved compression: {overall_ratio:.2f}%")
        
        print("\n" + "="*70)
        print("PHASE 2C WEEK 2 COMPLETE ✓")
        print("="*70)
        
        # Save reports
        self._save_reports()
    
    def _save_reports(self) -> None:
        """Save detailed reports to JSON files."""
        
        # Orchestrator results
        report_file = Path("phase2c_orchestration_report.json")
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n✓ Full results saved to: {report_file}")


def main():
    """Main entry point."""
    
    orchestrator = CrystallizationOrchestrator()
    results = orchestrator.run_full_pipeline()
    
    print("\nCrystallization pipeline complete!")
    print("Next: Phase 3 - Layer 0 Reflex Routing Integration")


if __name__ == "__main__":
    main()
