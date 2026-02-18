#!/usr/bin/env python3
"""
Phase 2B Cartridge Builder
Builds all domain cartridges from markdown data files
Handles duplicate content hashes and proper index initialization
"""

import sys
import shutil
from pathlib import Path
from kitbash_builder import CartridgeBuilder
from kitbash_cartridge import EpistemicLevel


# Data files to cartridge mappings
CARTRIDGE_SPECS = [
    ("physics", "physics_basics.md", EpistemicLevel.L0_EMPIRICAL, "Physics fundamentals - universal laws"),
    ("chemistry", "chemistry_basics.md", EpistemicLevel.L0_EMPIRICAL, "Chemistry - atomic structure, bonding, reactions"),
    ("biology", "biology_basics.md", EpistemicLevel.L1_NARRATIVE, "Biology - organisms, genetics, evolution"),
    ("biochemistry", "biochemistry_basics.md", EpistemicLevel.L1_NARRATIVE, "Biochemistry - molecular biology, metabolism"),
    ("thermodynamics", "thermodynamics_basics.md", EpistemicLevel.L0_EMPIRICAL, "Thermodynamics - energy, entropy, laws"),
    ("statistics", "statistics_basics.md", EpistemicLevel.L2_AXIOMATIC, "Statistics - distributions, hypothesis testing"),
    ("formal_logic", "formal_logic_basics.md", EpistemicLevel.L2_AXIOMATIC, "Formal logic - propositional, predicate calculus"),
    ("engineering", "engineering_basics.md", EpistemicLevel.L2_AXIOMATIC, "Engineering - disciplines, methods, design"),
    ("neuroscience", "neuroscience_basics.md", EpistemicLevel.L1_NARRATIVE, "Neuroscience - brain, neurons, cognition"),
]


def build_cartridge(name: str, data_file: str, epistemic_level: EpistemicLevel, description: str) -> bool:
    """
    Build a single cartridge from markdown data.
    Handles re-runs by clearing existing cartridges first.
    
    Args:
        name: Cartridge name
        data_file: Path to markdown data file
        epistemic_level: Epistemological level for facts
        description: Description for manifest
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Check data file exists
        data_path = Path(data_file)
        if not data_path.exists():
            print(f"       âœ- Data file not found: {data_file}")
            return False
        
        # Remove existing cartridge if it exists (clean rebuild)
        cartridge_path = Path("./cartridges") / f"{name}.kbc"
        if cartridge_path.exists():
            shutil.rmtree(cartridge_path)
        
        # Create and build cartridge
        builder = CartridgeBuilder(name, "./cartridges")
        builder.build()
        
        # Load from markdown with epistemic level
        builder.from_markdown(data_file)
        
        # Update manifest with description
        if builder.cart.manifest is None:
            builder.cart.manifest = {}
        builder.cart.manifest["description"] = description
        builder.cart.manifest["epistemic_level"] = epistemic_level.name
        
        # Save cartridge
        builder.save()
        
        return True
        
    except Exception as e:
        print(f"       âœ- ERROR: {type(e).__name__}: {str(e)}")
        return False


def main():
    """Build all cartridges."""
    print("\n" + "="*70)
    print("PHASE 2B CARTRIDGE BUILD")
    print("="*70)
    
    # Ensure cartridges directory exists
    Path("./cartridges").mkdir(exist_ok=True)
    
    successful = 0
    failed = 0
    
    # Build each cartridge
    for idx, (name, data_file, level, desc) in enumerate(CARTRIDGE_SPECS, 1):
        print(f"\n[{idx}/{len(CARTRIDGE_SPECS)}] Building: {name}")
        print(f"       Data: ./{data_file}")
        
        if build_cartridge(name, data_file, level, desc):
            successful += 1
            print(f"âœ“ Cartridge '{name}' built successfully")
        else:
            failed += 1
    
    # Summary
    print("\n" + "="*70)
    print("BUILD SUMMARY")
    print("="*70)
    print(f"Successful: {successful}/{len(CARTRIDGE_SPECS)}")
    print(f"Failed: {failed}/{len(CARTRIDGE_SPECS)}")
    print(f"Cartridge directory: ./cartridges/")
    
    if failed > 0:
        print(f"\nâœ- {failed} cartridge(s) failed to build")
        print("   Check that all data files exist in current directory")
        return False
    
    print("\nâœ“ All cartridges built successfully!")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
