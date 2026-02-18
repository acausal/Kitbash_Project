#!/usr/bin/env python3
"""
Diagnostic Metrics Feed for Kitbash

Logs comprehensive routing decisions with visual feedback.
Captures all query analysis for optimization and debugging.

Phase 3A Component
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class DiagnosticMetricsFeed:
    """
    Logs and displays query routing decisions.

    Captures:
    - Layer 0 hits vs escalations
    - Confidence scores and thresholds
    - Grain IDs, fact IDs, cartridge info
    - Latency measurements
    - Query difficulty classification
    """

    def __init__(self, output_file: str = "diagnostics.jsonl"):
        """
        Initialize metrics feed.

        Args:
            output_file: Path to append diagnostic events
        """
        self.output_file = Path(output_file)
        self.metrics: List[Dict[str, Any]] = []
        self.session_start = datetime.now()

        # Statistics
        self.total_queries = 0
        self.layer0_hits = 0
        self.layer0_escalations = 0
        self.no_grain_matches = 0

    def log_query_result(self, query_text: str, result: Dict[str, Any]) -> None:
        """
        Log a query result with comprehensive metrics.

        Args:
            query_text: The original query
            result: Result dict from Layer0QueryProcessor
        """
        self.total_queries += 1

        # Classify result
        layer = result.get('layer', 'UNKNOWN')
        if layer == 'GRAIN':
            self.layer0_hits += 1
            classification = 'L0_HIT'
        elif layer == 'GRAIN_HINT':
            self.layer0_escalations += 1
            classification = 'L0_HINT'
        else:
            self.no_grain_matches += 1
            classification = 'ESCALATE'

        # Build diagnostic record
        metric = {
            'timestamp': datetime.now().isoformat(),
            'query_id': f"q_{self.total_queries:06d}",
            'query_text': query_text,
            'query_length': len(query_text),
            'classification': classification,
            'layer': layer,
            'latency_ms': result.get('latency_ms', 0),
            'confidence': result.get('confidence', 0),
            'grain_id': result.get('grain_id'),
            'fact_id': result.get('fact_id'),
            'cartridge': result.get('cartridge'),
            'routing': result.get('routing'),
        }

        self.metrics.append(metric)

        # Append to file (for streaming analysis)
        try:
            with open(self.output_file, 'a') as f:
                f.write(json.dumps(metric) + '\n')
        except Exception as e:
            logger.error(f"Could not write to {self.output_file}: {e}")

    def format_result_display(self, query_text: str, result: Dict[str, Any]) -> str:
        """
        Format a query result for terminal display.

        Args:
            query_text: The original query
            result: Result dict from Layer0QueryProcessor

        Returns:
            Formatted string for display
        """
        layer = result.get('layer', 'UNKNOWN')
        latency = result.get('latency_ms', 0)

        # Status icon
        if layer == 'GRAIN':
            icon = "✓"
            status = "LAYER 0 HIT"
            style = "\033[92m"  # Green
        elif layer == 'GRAIN_HINT':
            icon = "~"
            status = "GRAIN HINT"
            style = "\033[93m"  # Yellow
        else:
            icon = "✗"
            status = "ESCALATE"
            style = "\033[94m"  # Blue

        reset = "\033[0m"

        # Build output
        lines = [
            f"{style}{icon} {status}{reset}",
            f"  Query: \"{query_text}\"",
            f"  Latency: {latency:.2f}ms",
        ]

        if layer == 'GRAIN':
            confidence = result.get('confidence', 0)
            grain_id = result.get('grain_id', 'N/A')
            fact_id = result.get('fact_id', 'N/A')
            cartridge = result.get('cartridge', 'N/A')

            lines.extend([
                f"  Confidence: {confidence:.4f}",
                f"  Grain: {grain_id}",
                f"  Fact: {fact_id}",
                f"  Cartridge: {cartridge}",
                f"  ✓ Return to user (reflex)",
            ])

        elif layer == 'GRAIN_HINT':
            confidence = result.get('grain_confidence', 0)
            hint = result.get('grain_hint', 'N/A')

            lines.extend([
                f"  Grain confidence: {confidence:.4f}",
                f"  Hint: {hint}",
                f"  → Escalate to Layer 1 with hint",
            ])

        else:  # NO_GRAIN
            lines.extend([
                f"  → Escalate to Layer 1+ (standard lookup)",
            ])

        return '\n'.join(lines)

    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics across all logged queries.

        Returns:
            Dictionary with aggregated metrics
        """
        if not self.metrics:
            return {
                'total_queries': 0,
                'layer0_hits': 0,
                'layer0_escalations': 0,
                'no_grain_matches': 0,
                'hit_rate': 0.0,
                'avg_latency_ms': 0.0,
                'avg_confidence': 0.0,
            }

        # Calculate averages
        latencies = [m['latency_ms'] for m in self.metrics]
        confidences = [m['confidence'] for m in self.metrics if m['confidence'] > 0]

        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        # Calculate hit rate
        hit_rate = (self.layer0_hits + self.layer0_escalations) / max(1, self.total_queries)

        return {
            'total_queries': self.total_queries,
            'layer0_hits': self.layer0_hits,
            'layer0_escalations': self.layer0_escalations,
            'no_grain_matches': self.no_grain_matches,
            'hit_rate': hit_rate,
            'hit_rate_pct': hit_rate * 100,
            'avg_latency_ms': avg_latency,
            'avg_confidence': avg_confidence,
            'min_latency_ms': min(latencies) if latencies else 0,
            'max_latency_ms': max(latencies) if latencies else 0,
        }

    def print_summary(self) -> None:
        """Print summary statistics to console."""
        stats = self.get_summary_stats()

        print("\n" + "=" * 80)
        print("DIAGNOSTIC METRICS SUMMARY")
        print("=" * 80)
        print(f"Total queries: {stats['total_queries']}")
        print(f"Layer 0 hits: {stats['layer0_hits']} ({100*stats['layer0_hits']/max(1, stats['total_queries']):.1f}%)")
        print(f"Layer 0 hints (escalate): {stats['layer0_escalations']} ({100*stats['layer0_escalations']/max(1, stats['total_queries']):.1f}%)")
        print(f"No grain match: {stats['no_grain_matches']} ({100*stats['no_grain_matches']/max(1, stats['total_queries']):.1f}%)")
        print()
        print(f"Overall hit rate (L0+): {stats['hit_rate_pct']:.1f}%")
        print(f"Average latency: {stats['avg_latency_ms']:.2f}ms")
        print(f"Latency range: {stats['min_latency_ms']:.2f}ms - {stats['max_latency_ms']:.2f}ms")
        print(f"Average confidence: {stats['avg_confidence']:.4f}")
        print("=" * 80 + "\n")

    def export_csv(self, output_file: str = "diagnostics.csv") -> None:
        """
        Export metrics to CSV for analysis.

        Args:
            output_file: Path to export CSV
        """
        import csv

        if not self.metrics:
            logger.warning("No metrics to export")
            return

        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    'timestamp', 'query_id', 'query_text', 'query_length',
                    'classification', 'layer', 'latency_ms', 'confidence',
                    'grain_id', 'fact_id', 'cartridge', 'routing'
                ]
            )
            writer.writeheader()
            writer.writerows(self.metrics)

        logger.info(f"Exported metrics to {output_file}")

    def get_hit_rate_by_length(self) -> Dict[str, float]:
        """
        Analyze hit rate by query length.

        Returns:
            Dictionary mapping length ranges to hit rates
        """
        if not self.metrics:
            return {}

        # Bucket by query length
        buckets = {
            'short (1-20)': [],
            'medium (21-50)': [],
            'long (51+)': [],
        }

        for metric in self.metrics:
            length = metric['query_length']

            if length <= 20:
                bucket = 'short (1-20)'
            elif length <= 50:
                bucket = 'medium (21-50)'
            else:
                bucket = 'long (51+)'

            is_hit = metric['classification'] in ('L0_HIT', 'L0_HINT')
            buckets[bucket].append(is_hit)

        # Calculate hit rates
        result = {}
        for bucket, hits in buckets.items():
            if hits:
                hit_rate = sum(hits) / len(hits)
                result[bucket] = hit_rate

        return result

    def get_grain_distribution(self) -> Dict[str, int]:
        """
        Get distribution of queries across grains.

        Returns:
            Dictionary mapping grain_id to query count
        """
        distribution = {}

        for metric in self.metrics:
            grain_id = metric.get('grain_id')
            if grain_id:
                distribution[grain_id] = distribution.get(grain_id, 0) + 1

        return distribution

    def get_cartridge_distribution(self) -> Dict[str, int]:
        """
        Get distribution of queries across cartridges.

        Returns:
            Dictionary mapping cartridge to query count
        """
        distribution = {}

        for metric in self.metrics:
            cartridge = metric.get('cartridge')
            if cartridge:
                distribution[cartridge] = distribution.get(cartridge, 0) + 1

        return distribution


def demonstrate_metrics_feed():
    """Demonstrate the metrics feed with sample queries."""
    feed = DiagnosticMetricsFeed()

    # Sample results
    sample_queries = [
        {
            'query': 'what is ATP',
            'result': {
                'layer': 'GRAIN',
                'confidence': 0.9559,
                'grain_id': 'sg_93386D2A',
                'fact_id': 42,
                'cartridge': 'biochemistry',
                'latency_ms': 0.18,
                'routing': 'direct_return'
            }
        },
        {
            'query': 'explain photosynthesis',
            'result': {
                'layer': 'GRAIN',
                'confidence': 0.8821,
                'grain_id': 'sg_A8F12C44',
                'fact_id': 127,
                'cartridge': 'biology',
                'latency_ms': 0.19,
                'routing': 'direct_return'
            }
        },
        {
            'query': 'how does physics relate to consciousness',
            'result': {
                'layer': 'NO_GRAIN',
                'latency_ms': 0.15,
            }
        },
    ]

    print("\nDiagnostic Metrics Feed - Sample Output\n")

    for item in sample_queries:
        feed.log_query_result(item['query'], item['result'])
        display = feed.format_result_display(item['query'], item['result'])
        print(display)
        print()

    feed.print_summary()

    # Show distributions
    print(f"Grains used: {feed.get_grain_distribution()}")
    print(f"Cartridges used: {feed.get_cartridge_distribution()}")
    print(f"Hit rate by query length: {feed.get_hit_rate_by_length()}")


if __name__ == "__main__":
    demonstrate_metrics_feed()
