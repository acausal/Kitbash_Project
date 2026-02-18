#!/usr/bin/env python3
"""
Kitbash Manual Query REPL

Interactive knowledge base explorer for Phase 2C Week 2.
Allows querying cartridges and observing:
- Query results and fact details
- Phantom tracking data (hit counts, confidence)
- Confidence scores across cartridges
- Performance metrics (latency, layer response)

Usage:
    python query_repl.py
"""

import time
from pathlib import Path
from typing import Optional, Dict, List
from kitbash_query_engine import CartridgeQueryEngine
from kitbash_registry import DeltaRegistry


class QueryREPL:
    """Interactive query REPL for exploring the knowledge base."""
    
    def __init__(self):
        """Initialize the REPL."""
        self.engine = CartridgeQueryEngine("./cartridges")
        self.registries: Dict[str, DeltaRegistry] = {}
        self.load_registries()
        self.total_queries = 0
        self.total_latency = 0.0
    
    def load_registries(self):
        """Load all per-cartridge registries."""
        registry_dir = Path("./registry")
        if not registry_dir.exists():
            print("Warning: No registry directory found. Phantom data unavailable.")
            return
        
        for registry_file in registry_dir.glob("*_registry.json"):
            cart_name = registry_file.stem.replace("_registry", "")
            try:
                self.registries[cart_name] = DeltaRegistry.load(str(registry_file))
            except Exception as e:
                print(f"Warning: Could not load {registry_file}: {e}")
    
    def print_header(self):
        """Print REPL header and help."""
        print("\n" + "="*70)
        print("KITBASH MANUAL QUERY REPL - Phase 2C Week 2")
        print("="*70)
        print(f"Cartridges loaded: {len(self.engine.cartridges)}")
        print(f"Registries loaded: {len(self.registries)}")
        print(f"Total facts: {sum(len(c.facts) for c in self.engine.cartridges.values())}")
        print("\nCommands:")
        print("  <query>        - Keyword query (e.g., 'energy metabolism ATP')")
        print("  stats          - Show cartridge statistics")
        print("  phantoms       - Show locked phantoms and confidence")
        print("  coverage       - Show fact coverage by cartridge")
        print("  perf           - Show performance metrics")
        print("  help           - Show this help")
        print("  exit/quit      - Exit the REPL")
        print("="*70 + "\n")
    
    def run_query(self, query_text: str):
        """Execute a keyword query and display results."""
        start_time = time.perf_counter()
        result = self.engine.keyword_query(query_text)
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        self.total_queries += 1
        self.total_latency += latency_ms
        
        # Display results
        print(f"\nQuery: '{query_text}'")
        print(f"Latency: {latency_ms:.2f}ms")
        print(f"Hits: {len(result.fact_ids)}\n")
        
        if not result.fact_ids:
            print("  (no matches)\n")
            return
        
        # Show each hit
        for i, fact_id in enumerate(result.fact_ids[:10], 1):  # Show top 10
            confidence = result.confidences.get(fact_id, 0.0)
            
            # Get fact details
            fact_text = None
            cart_name = None
            for cn, cart in self.engine.cartridges.items():
                fact = self.engine.get_fact(fact_id, cn)
                if fact:
                    fact_text = fact.text[:70] + "..." if len(fact.text) > 70 else fact.text
                    cart_name = cn
                    break
            
            # Try to find phantom data for this fact
            phantom_info = ""
            if cart_name and cart_name in self.registries:
                phantom = self.registries[cart_name].phantoms.get(fact_id)
                if phantom:
                    phantom_info = f" | hits={phantom.hit_count} status={phantom.status}"
            
            print(f"  {i}. [{fact_id:5d}] ({confidence:.4f}) {cart_name}")
            print(f"     {fact_text}{phantom_info}")
        
        if len(result.fact_ids) > 10:
            print(f"\n  ... and {len(result.fact_ids) - 10} more results")
        
        print()
    
    def show_phantoms(self):
        """Display locked phantoms and their confidence scores."""
        print("\nLocked Phantoms by Cartridge:")
        print("="*70)
        
        all_locked = []
        
        for cart_name, registry in sorted(self.registries.items()):
            locked = [p for p in registry.phantoms.values() if p.status == "locked"]
            
            if locked:
                print(f"\n{cart_name.upper()} ({len(locked)} locked):")
                print(f"  {'Fact ID':<8} {'Avg Conf':<12} {'Cycles':<8} {'Hit Count':<10}")
                print("  " + "-"*50)
                
                # Sort by average confidence
                for phantom in sorted(locked, key=lambda p: p._avg_confidence(), reverse=True):
                    avg_conf = phantom._avg_confidence()
                    cycles_seen = phantom.last_cycle_seen - phantom.first_cycle_seen
                    print(f"  {phantom.fact_id:<8} {avg_conf:<12.4f} {cycles_seen:<8} {phantom.hit_count:<10}")
            else:
                print(f"\n{cart_name.upper()}: no locked phantoms")
        
        # Summary
        total_locked = sum(
            len([p for p in r.phantoms.values() if p.status == "locked"])
            for r in self.registries.values()
        )
        print(f"\n{'='*70}")
        print(f"Total locked phantoms: {total_locked}")
        print()
    
    def show_stats(self):
        """Display cartridge statistics."""
        print("\nCartridge Statistics:")
        print("="*70)
        
        for cart_name in sorted(self.engine.cartridges.keys()):
            cart = self.engine.cartridges[cart_name]
            registry = self.registries.get(cart_name)
            
            facts = len(cart.facts)
            phantoms = 0
            locked = 0
            
            if registry:
                phantoms = len(registry.phantoms)
                locked = len([p for p in registry.phantoms.values() if p.status == "locked"])
            
            print(f"{cart_name:20} | {facts:3d} facts | {phantoms:3d} phantoms | {locked:3d} locked")
        
        print("="*70 + "\n")
    
    def show_coverage(self):
        """Show fact coverage statistics."""
        print("\nFact Coverage:")
        print("="*70)
        
        total_facts = 0
        total_covered = 0
        
        for cart_name in sorted(self.engine.cartridges.keys()):
            facts = len(self.engine.cartridges[cart_name].facts)
            total_facts += facts
            
            registry = self.registries.get(cart_name)
            covered = len(registry.phantoms) if registry else 0
            total_covered += covered
            
            coverage_pct = (covered / facts * 100) if facts > 0 else 0
            print(f"{cart_name:20} | {covered:3d}/{facts:3d} ({coverage_pct:5.1f}%)")
        
        print("-"*70)
        coverage_pct = (total_covered / total_facts * 100) if total_facts > 0 else 0
        print(f"{'TOTAL':20} | {total_covered:3d}/{total_facts:3d} ({coverage_pct:5.1f}%)")
        print("="*70 + "\n")
    
    def show_perf(self):
        """Display performance metrics."""
        print("\nPerformance Metrics:")
        print("="*70)
        print(f"Total queries executed: {self.total_queries}")
        
        if self.total_queries > 0:
            avg_latency = self.total_latency / self.total_queries
            print(f"Average latency: {avg_latency:.2f}ms")
            print(f"Total latency: {self.total_latency:.2f}ms")
        else:
            print("(No queries executed yet)")
        
        print("="*70 + "\n")
    
    def run(self):
        """Run the interactive REPL."""
        self.print_header()
        
        while True:
            try:
                user_input = input("kitbash> ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ("exit", "quit"):
                    print("\nExiting Kitbash REPL. Goodbye!")
                    break
                elif user_input.lower() == "help":
                    self.print_header()
                elif user_input.lower() == "stats":
                    self.show_stats()
                elif user_input.lower() == "phantoms":
                    self.show_phantoms()
                elif user_input.lower() == "coverage":
                    self.show_coverage()
                elif user_input.lower() == "perf":
                    self.show_perf()
                else:
                    # Treat as query
                    self.run_query(user_input)
            
            except KeyboardInterrupt:
                print("\n\nExiting (Ctrl+C)")
                break
            except Exception as e:
                print(f"\nError: {e}\n")


def main():
    """Main entry point."""
    repl = QueryREPL()
    repl.run()


if __name__ == "__main__":
    main()
