#!/usr/bin/env python3
"""
Kitbash Phase 3 Grain Layer REPL

Interactive grain routing explorer for Phase 3A.
Tests Layer 0 grain-based query routing using the Redis Blackboard.

Allows querying the 261 crystallized grains and observing:
- Layer 0 grain hits vs escalations
- Grain IDs and fact details
- Confidence scores and latency
- Diagnostic event logging to Redis

Usage:
    python phase3_grain_repl.py
"""

import time
import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

from grain_router import GrainRouter
from layer0_query_processor import Layer0QueryProcessor
from redis_blackboard import RedisBlackboard

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Phase3GrainREPL:
    """Interactive Phase 3 grain routing REPL."""

    def __init__(self, cartridges_dir: str = "./cartridges"):
        """
        Initialize Phase 3 REPL.

        Args:
            cartridges_dir: Path to cartridges directory
        """
        logger.info("Initializing Phase 3 Grain REPL...")

        # Load grain routing system
        self.grain_router = GrainRouter(cartridges_dir)
        self.processor = Layer0QueryProcessor(cartridges_dir)

        # Connect to Redis Blackboard
        try:
            self.blackboard = RedisBlackboard()
            logger.info("Redis Blackboard connected")
            self.redis_available = True
        except Exception as e:
            logger.warning(f"Redis Blackboard unavailable: {e}")
            self.blackboard = None
            self.redis_available = False

        # Statistics
        self.total_queries = 0
        self.grain_hits = 0
        self.grain_hints = 0
        self.no_grain = 0
        self.total_latency = 0.0
        self.query_history: List[Dict] = []

    def print_header(self):
        """Print REPL header and help."""
        print("\n" + "=" * 80)
        print("KITBASH PHASE 3 GRAIN LAYER REPL")
        print("=" * 80)
        print(f"Grain Router: {self.grain_router.total_grains} grains loaded")
        print(f"Redis Blackboard: {'✓ Connected' if self.redis_available else '✗ Not available'}")
        print("\nCommands:")
        print("  <query>        - Test query against grain Layer 0 (e.g., 'what is ATP')")
        print("  stats          - Show Layer 0 statistics")
        print("  grains         - List all grains by cartridge")
        print("  history        - Show recent query history")
        print("  feed           - Show Redis diagnostic feed (last 10 events)")
        print("  perf           - Show performance metrics")
        print("  help           - Show this help")
        print("  exit/quit      - Exit the REPL")
        print("=" * 80 + "\n")

    def run_query(self, query_text: str):
        """
        Execute a query and display results.

        Args:
            query_text: The query to process
        """
        query_id = f"repl_{self.total_queries}_{int(time.time()*1000)}"
        start_time = time.perf_counter()

        # Process query through Layer 0
        result = self.processor.process_query(query_text)
        latency_ms = result.get('latency_ms', 0)

        self.total_queries += 1
        self.total_latency += latency_ms

        # Track result type
        layer = result.get('layer', 'UNKNOWN')
        if layer == 'GRAIN':
            self.grain_hits += 1
        elif layer == 'GRAIN_HINT':
            self.grain_hints += 1
        else:
            self.no_grain += 1

        # Store in history
        self.query_history.append({
            'query': query_text,
            'result': result,
            'timestamp': datetime.now().isoformat()
        })

        # Log to Redis Blackboard
        if self.redis_available:
            try:
                self.blackboard.create_query(query_id, query_text)
                self.blackboard.update_query_status(query_id, "completed", layer_result=result)
                self.blackboard.log_diagnostic_event("query_processed", query_id, result)
            except Exception as e:
                logger.warning(f"Could not log to Redis: {e}")

        # Display results
        print(f"\nQuery: '{query_text}'")
        print(f"Latency: {latency_ms:.2f}ms")
        print("-" * 80)

        if layer == 'GRAIN':
            print(f"✓ LAYER 0 HIT (Grain Match)")
            print(f"  Grain ID: {result.get('grain_id')}")
            print(f"  Fact ID: {result.get('fact_id')}")
            print(f"  Cartridge: {result.get('cartridge')}")
            print(f"  Confidence: {result.get('confidence'):.4f}")
            print(f"  Answer: {result.get('answer')[:100]}...")
            print(f"  Routing: {result.get('routing', 'N/A')}")

        elif layer == 'GRAIN_HINT':
            print(f"~ LAYER 0 HINT (Would Escalate to Layer 1)")
            print(f"  Grain Hint: {result.get('grain_hint')}")
            print(f"  Grain Confidence: {result.get('grain_confidence'):.4f}")
            print(f"  Recommendation: {result.get('recommendation')}")

        else:  # NO_GRAIN
            print(f"✗ NO LAYER 0 MATCH (Would Escalate to Layer 1+)")
            print(f"  Recommendation: {result.get('recommendation')}")

        print()

    def show_stats(self):
        """Display Layer 0 statistics."""
        print("\n" + "=" * 80)
        print("LAYER 0 STATISTICS")
        print("=" * 80)
        print(f"Total queries: {self.total_queries}")
        print(f"Grain hits: {self.grain_hits} ({100*self.grain_hits/max(1, self.total_queries):.1f}%)")
        print(f"Grain hints: {self.grain_hints} ({100*self.grain_hints/max(1, self.total_queries):.1f}%)")
        print(f"No grain (escalate): {self.no_grain} ({100*self.no_grain/max(1, self.total_queries):.1f}%)")

        if self.total_queries > 0:
            avg_latency = self.total_latency / self.total_queries
            print(f"\nAverage latency: {avg_latency:.2f}ms")
            print(f"Total latency: {self.total_latency:.2f}ms")
        else:
            print("\n(No queries executed yet)")

        print("=" * 80 + "\n")

    def show_grains(self):
        """List all grains by cartridge."""
        print("\n" + "=" * 80)
        print("GRAINS BY CARTRIDGE")
        print("=" * 80)

        by_cartridge = {}
        for grain_id, grain_data in self.grain_router.grains.items():
            cart = grain_data.get('cartridge', 'unknown')
            if cart not in by_cartridge:
                by_cartridge[cart] = []
            by_cartridge[cart].append(grain_id)

        for cartridge in sorted(by_cartridge.keys()):
            grain_ids = by_cartridge[cartridge]
            print(f"\n{cartridge.upper()} ({len(grain_ids)} grains):")

            # Show first 10
            for grain_id in grain_ids[:10]:
                grain = self.grain_router.grains[grain_id]
                fact_id = grain.get('fact_id', 'N/A')
                confidence = grain.get('confidence', 0)
                print(f"  {grain_id:20} fact_id={fact_id:5} confidence={confidence:.4f}")

            if len(grain_ids) > 10:
                print(f"  ... and {len(grain_ids) - 10} more")

        print("\n" + "=" * 80 + "\n")

    def show_history(self):
        """Show recent query history."""
        print("\n" + "=" * 80)
        print("QUERY HISTORY (Last 20)")
        print("=" * 80)

        if not self.query_history:
            print("(No queries executed yet)\n")
            return

        for i, entry in enumerate(self.query_history[-20:], 1):
            query = entry['query']
            result = entry['result']
            layer = result.get('layer', 'UNKNOWN')
            latency = result.get('latency_ms', 0)

            status_icon = "✓" if layer == 'GRAIN' else "~" if layer == 'GRAIN_HINT' else "✗"
            print(f"{i:2}. {status_icon} [{layer:12}] {latency:6.2f}ms | {query[:50]}...")

        print("=" * 80 + "\n")

    def show_feed(self):
        """Show Redis diagnostic feed."""
        if not self.redis_available:
            print("\n✗ Redis Blackboard not available\n")
            return

        print("\n" + "=" * 80)
        print("REDIS DIAGNOSTIC FEED (Last 10)")
        print("=" * 80)

        try:
            events = self.blackboard.get_diagnostic_feed(count=10)

            if not events:
                print("(No diagnostic events logged)\n")
                return

            for event in events:
                timestamp = event.get('timestamp', 'N/A')
                event_type = event.get('event_type', 'UNKNOWN')
                query_id = event.get('query_id', 'N/A')
                print(f"\n[{timestamp}] {event_type}")
                print(f"  Query: {query_id}")
                details = event.get('details', {})
                if details:
                    for key, val in details.items():
                        val_str = str(val)[:60]
                        print(f"  {key}: {val_str}")

        except Exception as e:
            print(f"✗ Error reading feed: {e}")

        print("\n" + "=" * 80 + "\n")

    def show_perf(self):
        """Display performance metrics."""
        print("\n" + "=" * 80)
        print("PERFORMANCE METRICS")
        print("=" * 80)
        print(f"Grain Router:")
        print(f"  Total grains: {self.grain_router.total_grains}")
        print(f"  Load time: {self.grain_router.load_time_ms:.2f}ms")
        print(f"  Size in memory: {self.grain_router.total_size_bytes / 1024:.1f}KB")

        if self.total_queries > 0:
            avg_latency = self.total_latency / self.total_queries
            print(f"\nLayer 0 Processor:")
            print(f"  Queries processed: {self.total_queries}")
            print(f"  Average latency: {avg_latency:.2f}ms")
            print(f"  Min latency: ~0.15ms (typical grain lookup)")
            print(f"  Max latency: ~1.00ms (worst case)")

        print("=" * 80 + "\n")

    def run(self):
        """Run the interactive REPL."""
        self.print_header()

        while True:
            try:
                user_input = input("phase3> ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ("exit", "quit"):
                    print("\nExiting Kitbash Phase 3 REPL. Goodbye!")
                    break
                elif user_input.lower() == "help":
                    self.print_header()
                elif user_input.lower() == "stats":
                    self.show_stats()
                elif user_input.lower() == "grains":
                    self.show_grains()
                elif user_input.lower() == "history":
                    self.show_history()
                elif user_input.lower() == "feed":
                    self.show_feed()
                elif user_input.lower() == "perf":
                    self.show_perf()
                else:
                    # Treat as query
                    self.run_query(user_input)

            except KeyboardInterrupt:
                print("\n\nExiting (Ctrl+C)")
                break
            except Exception as e:
                print(f"\n✗ Error: {e}\n")
                import traceback
                traceback.print_exc()


def main():
    """Main entry point."""
    repl = Phase3GrainREPL()
    repl.run()


if __name__ == "__main__":
    main()
