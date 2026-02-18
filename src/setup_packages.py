#!/usr/bin/env python3
"""
setup_packages.py - Create __init__.py files for all src/ subdirectories.

Run from src/ to make subdirectories importable as Python packages:
    python setup_packages.py

Safe to re-run - skips existing files, never overwrites content.
Add new directories to PACKAGE_DIRS as the project grows.

Current layout:
    context/        - MambaContextService implementations
    engines/        - InferenceEngine implementations (Grain, Cartridge, BitNet)
    interfaces/     - ABCs (TriageAgent, InferenceEngine, MambaContextService)
    memory/         - ResonanceWeightService (Tier 5 power law decay)
    orchestration/  - QueryOrchestrator (main coordinator)
    routing/        - TriageAgent implementations (RuleBasedTriageAgent)
    registry/       - Grain and phantom registry
    tests/          - Test harness and query suite
"""

from pathlib import Path

# Add new subdirectories here as they're created
PACKAGE_DIRS = [
    "context",
    "engines",
    "interfaces",
    "memory",
    "orchestration",
    "routing",
    "registry",
    "tests",
]

PACKAGE_DOCS = {
    "context":       "Mamba context service implementations.",
    "engines":       "InferenceEngine implementations: Grain, Cartridge, BitNet.",
    "interfaces":    "Abstract base classes: TriageAgent, InferenceEngine, MambaContextService.",
    "memory":        "Resonance weight service - Tier 5 power law decay.",
    "orchestration": "QueryOrchestrator - main query coordination pipeline.",
    "routing":       "TriageAgent implementations.",
    "registry":      "Grain and phantom registry.",
    "tests":         "Phase 3B test harness and query suite.",
}


def main():
    src_dir = Path(__file__).resolve().parent

    print(f"Setting up packages in: {src_dir}\n")

    created_dirs  = []
    created_inits = []
    skipped       = []

    for pkg in PACKAGE_DIRS:
        pkg_dir   = src_dir / pkg
        init_file = pkg_dir / "__init__.py"

        if not pkg_dir.exists():
            pkg_dir.mkdir(parents=True)
            created_dirs.append(pkg)
            print(f"  + Created directory:  {pkg}/")

        if init_file.exists():
            skipped.append(pkg)
            print(f"  ~ Skipped (exists):   {pkg}/__init__.py")
        else:
            doc = PACKAGE_DOCS.get(pkg, f"{pkg} package.")
            init_file.write_text(f'"""{doc}"""\n')
            created_inits.append(pkg)
            print(f"  + Created:            {pkg}/__init__.py")

    print(f"\nDone.")
    print(f"  New directories:  {len(created_dirs)}  {created_dirs if created_dirs else ''}")
    print(f"  New __init__.py:  {len(created_inits)}  {created_inits if created_inits else ''}")
    print(f"  Skipped:          {len(skipped)}")

    if created_dirs or created_inits:
        print("\nPackage-prefixed imports now available, e.g.:")
        print("    from memory.resonance_weights import ResonanceWeightService")
        print("    from orchestration.query_orchestrator import QueryOrchestrator")


if __name__ == "__main__":
    main()
