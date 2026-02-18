#!/usr/bin/env python3
"""
Phase 3A Testing Suite

Tests for:
1. GrainRouter loading and lookup
2. Layer 0 query processing
3. Routing decisions
4. End-to-end integration

Run: python test_phase3a.py
"""

import time
import json
from pathlib import Path
from typing import List, Dict, Any


class TestPhase3A:
    """Comprehensive Phase 3A testing."""
    
    def __init__(self):
        """Initialize test suite."""
        self.passed = 0
        self.failed = 0
        self.tests_run = 0
    
    def test_grain_router_loading(self):
        """Test 1: GrainRouter loads all grains."""
        print("\n" + "="*70)
        print("TEST 1: GrainRouter Loading")
        print("="*70)
        
        try:
            from grain_router import GrainRouter
            
            start = time.perf_counter()
            router = GrainRouter('./cartridges')
            load_time = (time.perf_counter() - start) * 1000
            
            self.tests_run += 1
            
            # Assertions
            assert router.total_grains > 0, "No grains loaded"
            assert len(router.grains) > 0, "Grain dict empty"
            assert len(router.grains) == router.total_grains, "Grain count mismatch with total_grains"
            assert len(router.grain_by_fact) > 0, "No facts indexed"
            assert len(router.grain_by_fact) <= len(router.grains), "More facts than grains (duplicate fact_ids)"
            
            print(f"âœ“ Loaded {router.total_grains} grains")
            print(f"âœ“ Load time: {load_time:.1f}ms")
            print(f"âœ“ Total storage: {router.total_size_bytes:,} bytes")
            print(f"âœ“ Average grain: {router.total_size_bytes / router.total_grains:.0f} bytes")
            
            self.passed += 1
            return True
        
        except AssertionError as e:
            print(f"âœ- FAILED: {e}")
            self.failed += 1
            return False
        except Exception as e:
            print(f"âœ- ERROR: {e}")
            self.failed += 1
            return False
    
    def test_grain_lookup(self):
        """Test 2: GrainRouter fact_id lookup."""
        print("\n" + "="*70)
        print("TEST 2: Grain Lookup by Fact ID")
        print("="*70)
        
        try:
            from grain_router import GrainRouter
            
            router = GrainRouter('./cartridges')
            
            # Get first fact_id
            test_fact_id = next(iter(router.grain_by_fact.keys()))
            
            # Look it up
            grain = router.lookup(test_fact_id)
            
            self.tests_run += 1
            
            assert grain is not None, "Grain lookup returned None"
            assert grain['fact_id'] == test_fact_id, "Grain fact_id mismatch"
            assert 'grain_id' in grain, "Missing grain_id"
            assert 'confidence' in grain, "Missing confidence"
            
            print(f"âœ“ Looked up fact_id {test_fact_id}")
            print(f"âœ“ Found grain: {grain['grain_id']}")
            print(f"âœ“ Confidence: {grain['confidence']:.4f}")
            print(f"âœ“ Cartridge: {grain.get('cartridge_source')}")
            
            self.passed += 1
            return True
        
        except AssertionError as e:
            print(f"âœ- FAILED: {e}")
            self.failed += 1
            return False
        except Exception as e:
            print(f"âœ- ERROR: {e}")
            self.failed += 1
            return False
    
    def test_routing_decisions(self):
        """Test 3: Routing decisions based on confidence."""
        print("\n" + "="*70)
        print("TEST 3: Routing Decisions")
        print("="*70)
        
        try:
            from grain_router import GrainRouter
            
            router = GrainRouter('./cartridges')
            
            # Get grains with different confidences
            top_grains = router.get_top_confidence_grains(10)
            
            self.tests_run += 1
            
            assert len(top_grains) > 0, "No top grains returned"
            
            decisions = []
            for grain in top_grains[:3]:
                decision = router.get_routing_decision(grain)
                decisions.append(decision)
                
                assert 'use_grain' in decision, "Missing use_grain"
                assert 'layer_recommendation' in decision, "Missing layer_recommendation"
            
            print(f"âœ“ Tested {len(decisions)} routing decisions")
            
            for i, decision in enumerate(decisions, 1):
                conf = decision['confidence']
                use = "USE" if decision['use_grain'] else "SKIP"
                layer = decision['layer_recommendation']
                print(f"  {i}. Confidence {conf:.4f} â†’ {use} grain (layer {layer})")
            
            self.passed += 1
            return True
        
        except AssertionError as e:
            print(f"âœ- FAILED: {e}")
            self.failed += 1
            return False
        except Exception as e:
            print(f"âœ- ERROR: {e}")
            self.failed += 1
            return False
    
    def test_layer0_processor(self):
        """Test 4: Layer 0 query processor."""
        print("\n" + "="*70)
        print("TEST 4: Layer 0 Query Processor")
        print("="*70)
        
        try:
            from layer0_query_processor import Layer0QueryProcessor
            
            processor = Layer0QueryProcessor('./cartridges')
            
            self.tests_run += 1
            
            # Test query
            result = processor.process_query("Tell me about fact 1")
            
            assert 'layer' in result, "Missing layer in result"
            assert 'latency_ms' in result, "Missing latency in result"
            
            print(f"âœ“ Processed query successfully")
            print(f"âœ“ Layer: {result['layer']}")
            print(f"âœ“ Latency: {result['latency_ms']:.2f}ms")
            
            if result['layer'] == 'GRAIN':
                print(f"âœ“ Direct grain hit: {result['grain_id']}")
            
            self.passed += 1
            return True
        
        except AssertionError as e:
            print(f"âœ- FAILED: {e}")
            self.failed += 1
            return False
        except Exception as e:
            print(f"âœ- ERROR: {e}")
            self.failed += 1
            return False
    
    def test_cartridge_indexing(self):
        """Test 5: Grains indexed by cartridge."""
        print("\n" + "="*70)
        print("TEST 5: Cartridge Indexing")
        print("="*70)
        
        try:
            from grain_router import GrainRouter
            
            router = GrainRouter('./cartridges')
            
            self.tests_run += 1
            
            # Check cartridge indexing
            assert len(router.grain_by_cartridge) > 0, "No cartridges indexed"
            
            total_indexed = sum(len(g) for g in router.grain_by_cartridge.values())
            assert total_indexed == router.total_grains, "Indexing count mismatch"
            
            print(f"âœ“ Indexed grains in {len(router.grain_by_cartridge)} cartridges")
            
            for cart_id in sorted(router.grain_by_cartridge.keys()):
                count = len(router.grain_by_cartridge[cart_id])
                print(f"  {cart_id:20} | {count:3d} grains")
            
            self.passed += 1
            return True
        
        except AssertionError as e:
            print(f"âœ- FAILED: {e}")
            self.failed += 1
            return False
        except Exception as e:
            print(f"âœ- ERROR: {e}")
            self.failed += 1
            return False
    
    def test_confidence_distribution(self):
        """Test 6: Confidence distribution analysis."""
        print("\n" + "="*70)
        print("TEST 6: Confidence Distribution")
        print("="*70)
        
        try:
            from grain_router import GrainRouter
            
            router = GrainRouter('./cartridges')
            
            self.tests_run += 1
            
            confidences = [g.get('confidence', 0.0) for g in router.grains.values()]
            
            assert len(confidences) > 0, "No confidences found"
            
            min_conf = min(confidences)
            max_conf = max(confidences)
            avg_conf = sum(confidences) / len(confidences)
            
            # Check quality
            assert avg_conf > 0.9, f"Average confidence too low: {avg_conf:.4f}"
            assert min_conf > 0.85, f"Minimum confidence too low: {min_conf:.4f}"
            
            print(f"âœ“ Confidence statistics:")
            print(f"  Min: {min_conf:.4f}")
            print(f"  Avg: {avg_conf:.4f}")
            print(f"  Max: {max_conf:.4f}")
            print(f"âœ“ All grains > 0.85 confidence")
            
            # Distribution buckets
            buckets = {
                '>= 0.95': len([c for c in confidences if c >= 0.95]),
                '0.90-0.95': len([c for c in confidences if 0.90 <= c < 0.95]),
                '< 0.90': len([c for c in confidences if c < 0.90]),
            }
            
            print(f"âœ“ Distribution:")
            for bucket, count in buckets.items():
                pct = (count / len(confidences)) * 100
                print(f"  {bucket}: {count} grains ({pct:.1f}%)")
            
            self.passed += 1
            return True
        
        except AssertionError as e:
            print(f"âœ- FAILED: {e}")
            self.failed += 1
            return False
        except Exception as e:
            print(f"âœ- ERROR: {e}")
            self.failed += 1
            return False
    
    def run_all_tests(self):
        """Run all tests."""
        print("\n" + "="*70)
        print("PHASE 3A TEST SUITE")
        print("="*70)
        
        self.test_grain_router_loading()
        self.test_grain_lookup()
        self.test_routing_decisions()
        self.test_layer0_processor()
        self.test_cartridge_indexing()
        self.test_confidence_distribution()
        
        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Tests run: {self.tests_run}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        
        if self.failed == 0:
            print("\nâœ“ ALL TESTS PASSED")
            print("âœ“ Phase 3A ready for full integration")
        else:
            print(f"\nâœ- {self.failed} tests failed")
        
        print("="*70 + "\n")
        
        return self.failed == 0


if __name__ == "__main__":
    tester = TestPhase3A()
    success = tester.run_all_tests()
    exit(0 if success else 1)
