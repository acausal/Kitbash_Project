"""
phase4_tester.py - Phase 4.1 Testing & Demo Interface

Simple CLI to test Phase 4.1 components:
- Query Redis for recent events
- Run background metabolism cycle
- Check safety validators
- Inspect MetabolismState

Usage:
    python phase4_tester.py [command] [args]
    
Commands:
    analyze NUM_EVENTS      Run cycle analyzing N recent events
    validate PATTERN_ID     Check pattern against all safety constraints
    status                  Show current metabolism state
    baseline                Show baseline metrics
    test                    Run quick demo

Run with: python phase4_tester.py demo
"""

import sys
import logging
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# Import Phase 4 components
try:
    from metabolism_state import MetabolismState, create_test_state, CycleType
    from log_analyzer import LogAnalyzer, create_test_event
    from background_metabolism_cycle import (
        BackgroundMetabolismCycle,
        MockLogAnalyzer,
        MockValidators,
    )
    from safety_infrastructure import (
        EpistemicValidator,
        QuestionAdjustedScorer,
        FactionGate,
        RegressionDetector,
        SafetyChecker,
    )
    logger.info("✓ All Phase 4 components imported")
except ImportError as e:
    logger.error(f"✗ Failed to import Phase 4 components: {e}")
    sys.exit(1)


class Phase4Tester:
    """Interface for testing Phase 4.1 components."""
    
    def __init__(self):
        """Initialize tester with all components."""
        
        self.state = create_test_state()
        self.cycle = BackgroundMetabolismCycle(
            MockLogAnalyzer(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
            MockValidators(),
            metabolism_state=self.state,
        )
        self.checker = SafetyChecker()
        self.faction_gate = FactionGate()
        self.regression_detector = RegressionDetector()
        
        logger.info("✓ Phase4Tester initialized")
    
    def analyze_events(self, num_events: int = 10) -> None:
        """
        Run background cycle on N events.
        
        Args:
            num_events: Number of events to analyze
        """
        print(f"\n{'='*70}")
        print(f"ANALYZING {num_events} EVENTS")
        print(f"{'='*70}\n")
        
        result = self.cycle.execute(num_events=num_events, turn_number=100)
        
        print(f"✓ Cycle Result: {result.summary()}\n")
        
        # Coupling analysis
        print("COUPLING DELTAS:")
        coupling = result.coupling_analysis
        print(f"  Total deltas: {coupling.get('total_deltas', 0)}")
        print(f"  Severity distribution: {coupling.get('severity_distribution', {})}")
        if coupling.get('top_conflicting_pairs'):
            print(f"  Top conflicts:")
            for pair_info in coupling['top_conflicting_pairs'][:3]:
                print(f"    {pair_info['pair']}: {pair_info['high_critical_count']} high/critical")
        
        # Epistemology analysis
        print("\nEPISTEMOLOGY:")
        epi = result.epistemology_analysis
        print(f"  L0+L1 present: {epi.get('L0_L1_both_present', 0)}/{epi.get('total_events', 0)}")
        print(f"  Validation passed: {epi.get('nwp_validation_passed', 0)}/{epi.get('total_events', 0)}")
        print(f"  Success rate: {epi.get('validation_success_rate', 0):.1%}")
        
        # Question analysis
        print("\nQUESTIONS:")
        ques = result.question_analysis
        print(f"  Total unresolved: {ques.get('total_unresolved_questions', 0)}")
        print(f"  Avg per event: {ques.get('average_questions_per_event', 0):.2f}")
        print(f"  Question rate: {ques.get('question_rate', 0):.1%}")
        
        # Faction analysis
        print("\nFACTION BOUNDARIES:")
        faction = result.faction_analysis
        print(f"  Distribution: {faction.get('faction_distribution', {})}")
        print(f"  Clean separation: {faction.get('faction_separation_clean', True)}")
        
        print(f"\n{'='*70}\n")
    
    def validate_pattern(self, pattern_id: str = "p1") -> None:
        """
        Validate pattern against all safety checks.
        
        Args:
            pattern_id: Pattern to validate
        """
        print(f"\n{'='*70}")
        print(f"VALIDATING PATTERN: {pattern_id}")
        print(f"{'='*70}\n")
        
        # Create test pattern and event
        pattern = {
            "id": pattern_id,
            "layer_sequence": ["GRAIN", "CARTRIDGE"],
            "success_rate": 0.92,
        }
        
        event = create_test_event(f"q_{pattern_id}")
        
        # Run safety checks
        result = self.checker.validate_pattern(pattern, event)
        
        print(f"Overall valid: {result['valid']}\n")
        
        # Epistemology
        epi_check = result['checks'].get('epistemology', {})
        print(f"EPISTEMOLOGY: {'✓' if epi_check.get('valid') else '✗'}")
        print(f"  Reason: {epi_check.get('reason', 'N/A')}")
        print(f"  Severity: {epi_check.get('severity', 'N/A')}")
        
        # Questions
        ques_check = result['checks'].get('questions', {})
        print(f"\nQUESTIONS:")
        print(f"  Adjusted confidence: {ques_check.get('adjusted_confidence', 0):.3f}")
        print(f"  Unresolved count: {ques_check.get('unresolved_count', 0)}")
        
        # Faction
        faction_check = result['checks'].get('faction', {})
        print(f"\nFACTION: {'✓' if faction_check.get('valid') else '✗'}")
        print(f"  Faction: {faction_check.get('faction', 'N/A')}")
        print(f"  Reason: {faction_check.get('reason', 'N/A')}")
        
        # Regression
        regression_check = result['checks'].get('regression', {})
        print(f"\nREGRESSION: {'⚠️ DETECTED' if regression_check.get('has_regression') else '✓ None'}")
        print(f"  Reason: {regression_check.get('reason', 'No regression')}")
        
        print(f"\n{'='*70}\n")
    
    def show_status(self) -> None:
        """Show current metabolism state."""
        print(f"\n{'='*70}")
        print(f"METABOLISM STATE")
        print(f"{'='*70}\n")
        
        summary = self.state.summary()
        
        print(f"Current turn: {summary['current_turn']}")
        print(f"Patterns learned: {summary['patterns_learned']}")
        print(f"Patterns valid: {summary['patterns_valid']}")
        print(f"Patterns questioned: {summary['patterns_questioned']}")
        print(f"Daydream flags: {summary['daydream_flags']}")
        print(f"Sleep consolidations: {summary['sleep_consolidations']}")
        print(f"Pending signals: {summary['pending_signals']}")
        print(f"Learned deltas: {summary['learned_deltas']}")
        
        print(f"\n{'='*70}\n")
    
    def show_baseline(self) -> None:
        """Show baseline metrics for rollback."""
        print(f"\n{'='*70}")
        print(f"BASELINE METRICS (for rollback detection)")
        print(f"{'='*70}\n")
        
        baseline = self.state.baseline_metrics
        
        if not baseline:
            print("No baseline metrics set yet.\n")
            return
        
        for metric_name, value in baseline.items():
            print(f"{metric_name}: {value:.3f}")
        
        print(f"\n{'='*70}\n")
    
    def demo_workflow(self) -> None:
        """Run complete demo workflow."""
        print("\n" + "="*70)
        print("PHASE 4.1 WEEK 1 DEMO")
        print("="*70)
        
        print("\n1. Analyze 20 events from Redis...")
        self.analyze_events(num_events=20)
        
        print("2. Validate test pattern...")
        self.validate_pattern("demo_pattern_1")
        
        print("3. Show metabolism state...")
        self.show_status()
        
        print("4. Show baseline metrics...")
        self.show_baseline()
        
        print("✅ Demo complete!\n")
    
    def interactive_menu(self) -> None:
        """Interactive menu for testing."""
        print("\n" + "="*70)
        print("PHASE 4.1 INTERACTIVE TESTER")
        print("="*70)
        print("""
Commands:
  analyze N    - Analyze N recent events
  validate ID  - Validate pattern with ID
  status       - Show metabolism state
  baseline     - Show baseline metrics
  demo         - Run full demo
  help         - Show this menu
  quit         - Exit
""")
        
        while True:
            try:
                cmd = input("\n> ").strip().split()
                
                if not cmd:
                    continue
                
                command = cmd[0].lower()
                
                if command == "analyze":
                    num = int(cmd[1]) if len(cmd) > 1 else 10
                    self.analyze_events(num)
                
                elif command == "validate":
                    pattern_id = cmd[1] if len(cmd) > 1 else "test_pattern"
                    self.validate_pattern(pattern_id)
                
                elif command == "status":
                    self.show_status()
                
                elif command == "baseline":
                    self.show_baseline()
                
                elif command == "demo":
                    self.demo_workflow()
                
                elif command == "help":
                    print("""
Commands:
  analyze N    - Analyze N recent events
  validate ID  - Validate pattern with ID
  status       - Show metabolism state
  baseline     - Show baseline metrics
  demo         - Run full demo
  help         - Show this menu
  quit         - Exit
""")
                
                elif command == "quit":
                    print("✓ Exiting\n")
                    break
                
                else:
                    print(f"Unknown command: {command}")
            
            except (IndexError, ValueError) as e:
                print(f"Error: {e}")
            except KeyboardInterrupt:
                print("\n✓ Exiting\n")
                break
            except Exception as e:
                logger.error(f"Error: {e}")


def main():
    """Main entry point."""
    
    tester = Phase4Tester()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "demo":
            tester.demo_workflow()
        
        elif command == "analyze":
            num = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            tester.analyze_events(num)
        
        elif command == "validate":
            pattern_id = sys.argv[2] if len(sys.argv) > 2 else "test"
            tester.validate_pattern(pattern_id)
        
        elif command == "status":
            tester.show_status()
        
        elif command == "baseline":
            tester.show_baseline()
        
        elif command == "help":
            print(__doc__)
        
        else:
            print(f"Unknown command: {command}\n")
            print(__doc__)
    
    else:
        # Interactive mode
        tester.interactive_menu()


if __name__ == "__main__":
    main()
