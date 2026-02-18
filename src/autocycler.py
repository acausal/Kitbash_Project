#!/usr/bin/env python3
"""
Autocycler v3: Automatic Query Cycle Runner for Multi-Cartridge Setup
Runs repeated query cycles to generate locked phantoms for Phase 2C crystallization.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Dict
import time
import random

# Import Kitbash modules
try:
    from kitbash_query_engine import CartridgeQueryEngine
    from kitbash_registry import DeltaRegistry
except ImportError as e:
    print(f"Error: Could not import Kitbash modules: {e}")
    print("Make sure you're running from the Kitbash src directory")
    sys.exit(1)


class Autocycler:
    """Automatic query cycle runner for phantom locking (multi-cartridge)."""
    
    def __init__(self, 
                 cartridges_path: str = "./cartridges",
                 registry_dir: str = "./registry",
                 verbose: bool = False):
        """Initialize autocycler for multi-cartridge setup."""
        self.cartridges_path = Path(cartridges_path)
        self.registry_dir = Path(registry_dir)
        self.verbose = verbose
        
        # Ensure registry directory exists
        self.registry_dir.mkdir(exist_ok=True)
        
        self.engine = None
        self.registries = {}  # cartridge_id -> DeltaRegistry
        self.cartridges_loaded = 0
        self.total_queries = 0
        self.total_hits = 0
        self.start_time = None
        
        # Query templates
        self.query_templates = {
            "physics": [
                "temperature heat energy",
                "force motion mechanics",
                "gravity acceleration velocity",
                "waves light sound",
                "matter atoms particles",
            ],
            "chemistry": [
                "atoms elements bonding",
                "reactions oxidation reduction",
                "molecular structure compounds",
                "periodic table elements",
                "electron shells atoms",
            ],
            "biology": [
                "evolution genetics adaptation",
                "cells organisms reproduction",
                "photosynthesis metabolism energy",
                "DNA genetics inheritance",
                "ecosystems organisms environment",
            ],
            "biochemistry": [
                "proteins amino acids folding",
                "enzymes catalysis reactions",
                "ATP energy metabolism",
                "carbohydrates glucose energy",
                "lipids fats membranes",
            ],
            "thermodynamics": [
                "entropy disorder energy",
                "temperature heat transfer",
                "pressure volume gas",
                "phase transitions melting",
                "equilibrium balance systems",
            ],
            "statistics": [
                "probability distribution variance",
                "mean average median mode",
                "correlation regression analysis",
                "hypothesis testing significance",
                "sampling inference population",
            ],
            "formal_logic": [
                "propositions truth logic",
                "inference deduction reasoning",
                "contradiction consistency validity",
                "predicates quantifiers logic",
                "sets relations membership",
            ],
            "engineering": [
                "design systems optimization",
                "materials stress strain",
                "structures stability load",
                "circuits electricity current",
                "mechanics dynamics motion",
            ],
            "neuroscience": [
                "neurons synapses firing",
                "brain regions function",
                "neurotransmitters signaling communication",
                "memory learning plasticity",
                "consciousness awareness perception",
            ],
        }
    
    def load_cartridges(self) -> int:
        """Load all cartridges and create per-cartridge registries."""
        if not self.cartridges_path.exists():
            print(f"Error: Cartridges path not found: {self.cartridges_path}")
            return 0
        
        try:
            self.engine = CartridgeQueryEngine(str(self.cartridges_path))
            self.cartridges_loaded = len(self.engine.cartridges)
            
            if self.cartridges_loaded == 0:
                print(f"Error: No cartridges found in {self.cartridges_path}")
                return 0
            
            # Create or load per-cartridge registries
            for cartridge_name in self.engine.cartridges:
                registry_path = self.registry_dir / f"{cartridge_name}_registry.json"
                
                if registry_path.exists():
                    try:
                        self.registries[cartridge_name] = DeltaRegistry.load(str(registry_path))
                        if self.verbose:
                            print(f"  + Loaded registry: {cartridge_name}")
                    except Exception as e:
                        # Create new if load fails
                        self.registries[cartridge_name] = DeltaRegistry(cartridge_name)
                        if self.verbose:
                            print(f"  + Created new registry: {cartridge_name}")
                else:
                    # Create new registry
                    self.registries[cartridge_name] = DeltaRegistry(cartridge_name)
                    if self.verbose:
                        print(f"  + Created new registry: {cartridge_name}")
            
            return self.cartridges_loaded
        except Exception as e:
            print(f"Error loading cartridges: {e}")
            return 0
    
    def generate_queries(self, count: int) -> List[str]:
        """Generate random queries from templates."""
        queries = []
        all_templates = []
        
        for domain, templates in self.query_templates.items():
            all_templates.extend(templates)
        
        for _ in range(count):
            if random.random() < 0.7:  # 70% single domain
                queries.append(random.choice(all_templates))
            else:  # 30% cross-domain
                num_parts = random.randint(2, 3)
                parts = [random.choice(all_templates) for _ in range(num_parts)]
                combined = " ".join(random.choice(part.split()) for part in parts)
                queries.append(combined)
        
        return queries
    
    def run_cycle(self, cycle_num: int, queries_per_cycle: int) -> int:
        """Run a single query cycle. Returns hits count."""
        cycle_queries = self.generate_queries(queries_per_cycle)
        cycle_hits = 0
        
        for query in cycle_queries:
            try:
                result = self.engine.keyword_query(query)
                
                if result.fact_ids:
                    for fact_id, confidence in result.confidences.items():
                        # Record in all registries (they'll track cross-cartridge hits)
                        for cart_id in self.registries:
                            registry = self.registries[cart_id]
                            # Only record if fact exists in this cartridge
                            if cart_id in self.engine.cartridges:
                                cart = self.engine.cartridges[cart_id]
                                if fact_id in cart.annotations:
                                    registry.record_hit(fact_id, query.split(), confidence)
                                    cycle_hits += 1
                                    self.total_hits += 1
                    
                    if self.verbose:
                        print(f"    Query: '{query}' → {len(result.fact_ids)} hits")
                
                self.total_queries += 1
            except Exception as e:
                if self.verbose:
                    print(f"  ⚠ Query error: {e}")
        
        # Advance cycle in all registries
        for registry in self.registries.values():
            registry.advance_cycle()
        
        return cycle_hits
    
    def get_global_stats(self) -> tuple:
        """Get aggregated stats across all registries."""
        all_locked = []
        all_persistent = []
        all_phantoms = set()
        
        for cart_id, registry in self.registries.items():
            all_locked.extend(registry.get_locked_phantoms())
            all_persistent.extend(registry.get_persistent_phantoms())
            # Use phantoms dict directly
            all_phantoms.update(registry.phantoms.keys())
        
        return len(all_locked), len(all_persistent), len(all_phantoms)
    
    def print_status(self, cycle_num: int):
        """Print current status and phantom statistics."""
        locked_count, persistent_count, phantom_count = self.get_global_stats()
        
        elapsed = time.time() - self.start_time
        qps = self.total_queries / elapsed if elapsed > 0 else 0
        
        print(f"\n{'='*70}")
        print(f"CYCLE {cycle_num:3d} REPORT")
        print(f"{'='*70}")
        print(f"Elapsed time:          {elapsed:7.1f}s")
        print(f"Total queries:         {self.total_queries:7d} ({qps:.1f} queries/sec)")
        print(f"Total hits:            {self.total_hits:7d}")
        print(f"All phantoms tracked:  {phantom_count:7d}")
        print(f"  → Locked (ready):    {locked_count:7d} (50+ cycles stable)")
        print(f"  → Persistent:        {persistent_count:7d} (5+ hits, approaching lock)")
        
        # Show per-cartridge status
        print(f"\nPer-cartridge status:")
        for cart_id, registry in sorted(self.registries.items()):
            locked = len(registry.get_locked_phantoms())
            phantoms = len(registry.phantoms)
            print(f"  {cart_id:20s}: {phantoms:3d} phantoms, {locked:3d} locked")
        
        print(f"{'='*70}\n")
    
    def run(self, num_cycles: int = 50, 
            queries_per_cycle: int = 5,
            report_interval: int = 5) -> bool:
        """Run the autocycler for specified number of cycles."""
        print(f"\n{'='*70}")
        print("AUTOCYCLER V3: PHANTOM LOCKING FOR PHASE 2C")
        print(f"{'='*70}")
        
        # Step 1: Load cartridges
        print("\n1. Loading cartridges...")
        if self.load_cartridges() == 0:
            print("Error: No cartridges loaded")
            return False
        print(f"✓ Loaded {self.cartridges_loaded} cartridges with registries")
        
        # Step 2: Run cycles
        print(f"\n2. Running {num_cycles} query cycles...")
        print(f"   (Reporting every {report_interval} cycles)\n")
        
        self.start_time = time.time()
        
        try:
            for cycle in range(1, num_cycles + 1):
                self.run_cycle(cycle, queries_per_cycle)
                
                if cycle % report_interval == 0 or cycle == 1:
                    self.print_status(cycle)
        
        except KeyboardInterrupt:
            print("\n⚠ Interrupted by user")
            if input("Save registries before exiting? (y/n): ").lower() == 'y':
                self.save_registries()
            return False
        
        except Exception as e:
            print(f"Error during cycle execution: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Step 3: Final report
        print(f"\n{'='*70}")
        print("AUTOCYCLER COMPLETE")
        print(f"{'='*70}")
        
        locked_count, persistent_count, phantom_count = self.get_global_stats()
        
        print(f"\nFinal Statistics:")
        print(f"  Total cycles:          {num_cycles}")
        print(f"  Total queries:         {self.total_queries}")
        print(f"  Total hits:            {self.total_hits}")
        print(f"  All phantoms tracked:  {phantom_count}")
        print(f"  Locked phantoms:       {locked_count} ✓ READY FOR CRYSTALLIZATION")
        print(f"  Persistent phantoms:   {persistent_count}")
        
        if locked_count > 0:
            print(f"\n✓ SUCCESS: {locked_count} phantoms ready for Phase 2C Week 2 crystallization!")
        else:
            print(f"\n⚠ Note: Need more cycles to lock phantoms (requires 50+ stable cycles)")
        
        # Step 4: Save registries
        print(f"\n3. Saving registries...")
        self.save_registries()
        
        print(f"\n{'='*70}\n")
        return True
    
    def save_registries(self):
        """Save all per-cartridge registries."""
        for cart_id, registry in self.registries.items():
            registry_path = self.registry_dir / f"{cart_id}_registry.json"
            try:
                registry.save(str(registry_path))
                if self.verbose:
                    print(f"  ✓ Saved {cart_id}")
            except Exception as e:
                print(f"  ⚠ Error saving {cart_id}: {e}")
        print(f"✓ Registries saved to {self.registry_dir}")


def main():
    """Parse arguments and run autocycler."""
    parser = argparse.ArgumentParser(
        description="Autocycler: Run query cycles to lock phantoms for Phase 2C"
    )
    parser.add_argument("--cycles", type=int, default=50, 
                       help="Number of cycles to run (default: 50)")
    parser.add_argument("--queries-per-cycle", type=int, default=5,
                       help="Queries per cycle (default: 5)")
    parser.add_argument("--report-interval", type=int, default=5,
                       help="Report every N cycles (default: 5)")
    parser.add_argument("--verbose", action="store_true",
                       help="Print detailed output")
    
    args = parser.parse_args()
    
    autocycler = Autocycler(verbose=args.verbose)
    success = autocycler.run(
        num_cycles=args.cycles,
        queries_per_cycle=args.queries_per_cycle,
        report_interval=args.report_interval,
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
