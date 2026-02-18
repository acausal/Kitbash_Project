"""
Grain Activation Tester & Compression Measurer

Performance validation:
- Test grain loading and ternary lookup latency
- Measure actual vs aspirational performance
- Calculate compression ratio achieved

Phase 2C Week 2 - Metrics & Validation
"""

import time
import json
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timezone


class GrainActivationTester:
    """
    Test crystallized grain activation and lookup performance.
    
    Validates that grains can be loaded and queried with acceptable latency.
    """
    
    def __init__(self, cartridges_dir: str = "./cartridges"):
        self.cartridges_dir = Path(cartridges_dir)
        self.test_results: List[Dict[str, Any]] = []
    
    def test_grain_loading(self, cartridge_id: str, grain_id: str) -> Dict[str, Any]:
        """Test loading a single grain from disk."""
        
        grain_file = (self.cartridges_dir / f"{cartridge_id}.kbc" / 
                     "grains" / f"{grain_id}.json")
        
        result = {
            'grain_id': grain_id,
            'cartridge_id': cartridge_id,
            'grain_file': str(grain_file),
            'file_exists': grain_file.exists(),
            'load_latency_ms': 0,
            'file_size_bytes': 0,
            'success': False,
            'grain_data': None,
        }
        
        if not grain_file.exists():
            return result
        
        # Test loading
        start = time.perf_counter()
        try:
            with open(grain_file, 'r') as f:
                grain_data = json.load(f)
            end = time.perf_counter()
            
            result['load_latency_ms'] = (end - start) * 1000
            result['file_size_bytes'] = grain_file.stat().st_size
            result['grain_data'] = grain_data
            result['success'] = True
        except Exception as e:
            result['error'] = str(e)
        
        self.test_results.append(result)
        return result
    
    def test_ternary_lookup(self, grain_data: Dict[str, Any], 
                           concept: str) -> Dict[str, Any]:
        """Test ternary lookup performance on a loaded grain."""
        
        result = {
            'grain_id': grain_data.get('grain_id'),
            'concept': concept,
            'lookup_latency_ms': 0,
            'value': None,
            'found': False,
            'success': False,
        }
        
        pointer_map = grain_data.get('pointer_map', {})
        
        # Test lookup
        start = time.perf_counter()
        try:
            # Simulate ternary lookup: check positive, negative, void
            value = None
            
            if concept in pointer_map.get('positive_ptrs', {}):
                value = pointer_map['positive_ptrs'][concept]['value']
                result['found'] = True
            elif concept in pointer_map.get('negative_ptrs', {}):
                value = pointer_map['negative_ptrs'][concept]['value']
                result['found'] = True
            elif concept in pointer_map.get('void_ptrs', {}):
                value = pointer_map['void_ptrs'][concept]['value']
                result['found'] = True
            
            end = time.perf_counter()
            
            result['lookup_latency_ms'] = (end - start) * 1000
            result['value'] = value
            result['success'] = True
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def test_all_grains(self, cartridge_id: str) -> Dict[str, Any]:
        """Test all grains in a cartridge."""
        
        grains_dir = self.cartridges_dir / f"{cartridge_id}.kbc" / "grains"
        
        if not grains_dir.exists():
            return {
                'cartridge_id': cartridge_id,
                'grain_count': 0,
                'results': [],
                'summary': {'avg_load_latency_ms': 0, 'max_load_latency_ms': 0},
            }
        
        results = []
        latencies = []
        
        for grain_file in grains_dir.glob("*.json"):
            grain_id = grain_file.stem
            result = self.test_grain_loading(cartridge_id, grain_id)
            results.append(result)
            
            if result['success']:
                latencies.append(result['load_latency_ms'])
        
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        max_latency = max(latencies) if latencies else 0
        
        return {
            'cartridge_id': cartridge_id,
            'grain_count': len(results),
            'results': results,
            'summary': {
                'avg_load_latency_ms': avg_latency,
                'max_load_latency_ms': max_latency,
                'target_latency_ms': 0.5,
                'realistic_latency_ms': 1.0,
            }
        }
    
    def print_summary(self) -> None:
        """Print activation test summary."""
        
        if not self.test_results:
            print("No activation tests performed")
            return
        
        successful = [r for r in self.test_results if r['success']]
        failed = [r for r in self.test_results if not r['success']]
        
        if successful:
            latencies = [r['load_latency_ms'] for r in successful]
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            
            print("\n" + "="*70)
            print("GRAIN ACTIVATION TEST RESULTS")
            print("="*70)
            print(f"Total grains tested: {len(self.test_results)}")
            print(f"Successful: {len(successful)}")
            print(f"Failed: {len(failed)}")
            print(f"\nLatency metrics:")
            print(f"  Average load: {avg_latency:.2f}ms")
            print(f"  Maximum load: {max_latency:.2f}ms")
            print(f"  Target (aspirational): 0.5ms")
            print(f"  Realistic expectation: 1.0-2.0ms on GTX 1060")
            
            # Performance assessment
            if avg_latency < 0.5:
                status = "✓ EXCEEDS aspirational target"
            elif avg_latency < 2.0:
                status = "✓ MEETS realistic expectations"
            else:
                status = "⚠ Exceeds realistic expectations (consider profiling)"
            
            print(f"\nPerformance: {status}")
            print("="*70 + "\n")


class CompressionMeasurer:
    """
    Measure compression achieved through ternary crystallization.
    
    Compares registry JSON size vs. crystallized grain size.
    """
    
    def __init__(self, registry_dir: str = "./registry",
                 cartridges_dir: str = "./cartridges"):
        self.registry_dir = Path(registry_dir)
        self.cartridges_dir = Path(cartridges_dir)
    
    def measure_compression(self, cartridge_id: str) -> Dict[str, Any]:
        """Measure compression for a single cartridge."""
        
        # Original size: registry JSON
        registry_file = self.registry_dir / f"{cartridge_id}_registry.json"
        original_size = 0
        
        if registry_file.exists():
            original_size = registry_file.stat().st_size
        
        # Crystallized size: all grain files
        grains_dir = self.cartridges_dir / f"{cartridge_id}.kbc" / "grains"
        crystallized_size = 0
        grain_count = 0
        
        if grains_dir.exists():
            for grain_file in grains_dir.glob("*.json"):
                crystallized_size += grain_file.stat().st_size
                grain_count += 1
        
        # Calculate metrics
        compression_ratio = 0
        space_saved = 0
        
        if original_size > 0:
            space_saved = original_size - crystallized_size
            compression_ratio = (space_saved / original_size) * 100
        
        return {
            'cartridge_id': cartridge_id,
            'original_size_bytes': original_size,
            'crystallized_size_bytes': crystallized_size,
            'space_saved_bytes': space_saved,
            'compression_ratio_percent': compression_ratio,
            'grain_count': grain_count,
            'bits_per_grain': (crystallized_size * 8) / grain_count if grain_count > 0 else 0,
        }
    
    def measure_all_cartridges(self) -> Dict[str, Any]:
        """Measure compression for all cartridges."""
        
        results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'cartridges': {},
            'summary': {
                'total_original_size': 0,
                'total_crystallized_size': 0,
                'total_space_saved': 0,
                'average_compression_ratio': 0,
                'target_compression_ratio': 93.75,
            }
        }
        
        # Get all registry files
        for registry_file in self.registry_dir.glob("*_registry.json"):
            cartridge_id = registry_file.stem.replace('_registry', '')
            
            metrics = self.measure_compression(cartridge_id)
            results['cartridges'][cartridge_id] = metrics
            
            results['summary']['total_original_size'] += metrics['original_size_bytes']
            results['summary']['total_crystallized_size'] += metrics['crystallized_size_bytes']
            results['summary']['total_space_saved'] += metrics['space_saved_bytes']
        
        # Calculate averages
        if results['cartridges']:
            ratios = [m['compression_ratio_percent'] 
                     for m in results['cartridges'].values()]
            results['summary']['average_compression_ratio'] = (
                sum(ratios) / len(ratios) if ratios else 0
            )
        
        return results
    
    def print_summary(self, results: Dict[str, Any]) -> None:
        """Print compression summary."""
        
        print("\n" + "="*70)
        print("COMPRESSION MEASUREMENT REPORT")
        print("="*70)
        
        print(f"\nTarget compression ratio: {results['summary']['target_compression_ratio']:.2f}%")
        print(f"Achieved compression ratio: {results['summary']['average_compression_ratio']:.2f}%")
        
        print(f"\nPer-cartridge breakdown:")
        print(f"{'Cartridge':<20} {'Original':<12} {'Crystallized':<14} {'Ratio':<10} {'Grains':<8}")
        print("-"*70)
        
        for cart_id, metrics in sorted(results['cartridges'].items()):
            orig = metrics['original_size_bytes']
            cryst = metrics['crystallized_size_bytes']
            ratio = metrics['compression_ratio_percent']
            grains = metrics['grain_count']
            
            print(f"{cart_id:<20} {orig:<12,} {cryst:<14,} {ratio:<10.1f}% {grains:<8}")
        
        print("-"*70)
        total_orig = results['summary']['total_original_size']
        total_cryst = results['summary']['total_crystallized_size']
        total_saved = results['summary']['total_space_saved']
        
        print(f"{'TOTAL':<20} {total_orig:<12,} {total_cryst:<14,} "
              f"{results['summary']['average_compression_ratio']:<10.1f}%")
        
        print(f"\nSpace saved: {total_saved:,} bytes")
        print("="*70 + "\n")
    
    def save_report(self, output_file: str = "./phase2c_compression_report.json") -> None:
        """Save compression report to JSON."""
        
        results = self.measure_all_cartridges()
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
