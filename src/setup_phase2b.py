#!/usr/bin/env python3
"""
Phase 2B Setup Master Script
Handles cartridge building and integration testing in sequence.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a shell command and report status."""
    print("\n" + "="*70)
    print(f"{description}")
    print("="*70)
    
    result = subprocess.run(cmd, shell=True)
    
    if result.returncode != 0:
        print(f"\nX FAILED: {description}")
        return False
    else:
        print(f"\n+ SUCCESS: {description}")
        return True


def check_files():
    """Verify all required files exist."""
    required_files = [
        "physics_basics.md",
        "biology_basics.md",
        "biochemistry_basics.md",
        "thermodynamics_basics.md",
        "statistics_basics.md",
        "formal_logic_basics.md",
        "engineering_basics.md",
        "neuroscience_basics.md",
        "kitbash_cartridge.py",
        "kitbash_builder.py",
        "build_phase2b_cartridges.py",
        "kitbash_query_engine.py",
        "test_cartridge_integration.py",
    ]
    
    print("\n" + "="*70)
    print("CHECKING REQUIRED FILES")
    print("="*70)
    
    missing = []
    for filename in required_files:
        path = Path(filename)
        if path.exists():
            print(f"+ {filename}")
        else:
            print(f"X {filename} - NOT FOUND")
            missing.append(filename)
    
    if missing:
        print(f"\nX Missing {len(missing)} file(s):")
        for f in missing:
            print(f"  - {f}")
        return False
    
    print("\n+ All required files found!")
    return True


def main():
    """Main execution flow."""
    print("\n" + "="*70)
    print("PHASE 2B CARTRIDGE PREPARATION - MASTER SETUP")
    print("="*70)
    
    # Step 1: Check files
    if not check_files():
        print("\nX Setup aborted - missing required files")
        sys.exit(1)
    
    # Step 2: Create directories
    print("\n" + "="*70)
    print("CREATING DIRECTORIES")
    print("="*70)
    
    Path("cartridges").mkdir(exist_ok=True)
    Path("registry").mkdir(exist_ok=True)
    print("+ Created cartridges/ directory")
    print("+ Created registry/ directory")
    
    # Step 3: Build cartridges
    if not run_command(
        "python build_phase2b_cartridges.py",
        "BUILDING CARTRIDGES FROM DATA FILES"
    ):
        print("\nX Setup aborted - cartridge build failed")
        sys.exit(1)
    
    # Step 4: Run integration test
    if not run_command(
        "python test_cartridge_integration.py",
        "RUNNING INTEGRATION TEST"
    ):
        print("\nX Integration test failed")
        sys.exit(1)
    
    # Summary
    print("\n" + "="*70)
    print("SETUP COMPLETE")
    print("="*70)
    print("""
+ All cartridges built successfully
+ Query engine tested
+ DeltaRegistry working
+ Phase 2B ready to begin

Next steps:
  1. Review cartridge statistics above
  2. Check registry/delta_registry.json
  3. Proceed to Phase 2B proper
""")


if __name__ == "__main__":
    main()
