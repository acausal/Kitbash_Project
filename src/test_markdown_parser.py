#!/usr/bin/env python3
"""Test enhanced markdown parser with frontmatter and temporal bounds"""

from kitbash_builder import CartridgeBuilder
from pathlib import Path


def test_yaml_frontmatter():
    """Test YAML frontmatter parsing"""
    markdown = """---
cartridge_name: TestPhysics
epistemic_level: L0_EMPIRICAL
domain: Physics
description: Test cartridge
tags: [test, physics]
baseline_confidence: 0.95
---

# Physics
- Newton's Law | Source | 0.99
"""
    
    # Write test file
    test_file = Path("test_frontmatter.md")
    test_file.write_text(markdown)
    
    try:
        builder = CartridgeBuilder("test_physics")
        builder.build()
        builder.from_markdown(str(test_file))
        
        # Check manifest
        assert builder.cart.manifest['description'] == 'Test cartridge'
        assert builder.cart.manifest['epistemic_level'] == 'L0_EMPIRICAL'
        assert builder.cart.manifest['baseline_confidence'] == 0.95
        assert 'physics' in builder.cart.manifest['tags']
        
        print("✓ YAML frontmatter parsing works")
        return True
    finally:
        test_file.unlink(missing_ok=True)


def test_temporal_bounds():
    """Test temporal bounds parsing"""
    test_cases = [
        ("eternal", None, None),
        ("2025-02-12 to 2028-01-20", "2025-02-12", "2028-01-20"),
        ("2025 to 2030", "2025-01-01", "2030-12-31"),
        ("past to 2025", None, "2025-12-31"),
        ("2030 to future", "2030-01-01", None),
        ("~5_billion_years", "2026-02-13", None),  # approximate
        ("sometime", "2026-02-13", None),  # unbounded future
    ]
    
    builder = CartridgeBuilder("test")
    builder.build()
    
    for input_str, expected_start_year, expected_end_year in test_cases:
        result = builder._parse_temporal_bounds(input_str)
        
        if expected_start_year is None:
            assert result['start'] is None, f"Failed: {input_str} -> start should be None"
        else:
            assert result['start'].startswith(expected_start_year), f"Failed: {input_str} -> start mismatch"
        
        if expected_end_year is None:
            assert result['end'] is None, f"Failed: {input_str} -> end should be None"
        else:
            assert result['end'].startswith(expected_end_year), f"Failed: {input_str} -> end mismatch"
        
        print(f"  ✓ {input_str:30s} -> {result['start']}/{result['end']}")
    
    print("✓ Temporal bounds parsing works")
    return True


def test_full_roundtrip():
    """Test full markdown parsing with frontmatter + temporal bounds"""
    markdown = """---
cartridge_name: Physics
epistemic_level: L0_EMPIRICAL
domain: Physics
description: Physical laws
baseline_confidence: 0.96
---

# Classical Mechanics
- Newton's First Law | Newton | 0.99 | eternal
- Newton's Second Law | Newton | 0.99 | eternal

# Future Events
- Sun will explode | Astronomy | 0.92 | ~5_billion_years
"""
    
    test_file = Path("test_roundtrip.md")
    test_file.write_text(markdown)
    
    try:
        builder = CartridgeBuilder("physics_test")
        builder.build()
        builder.from_markdown(str(test_file))
        builder.save()
        
        # Check facts loaded
        assert builder.fact_count == 3, f"Expected 3 facts, got {builder.fact_count}"
        
        # Check manifest
        assert builder.cart.manifest['epistemic_level'] == 'L0_EMPIRICAL'
        assert builder.cart.manifest['baseline_confidence'] == 0.96
        
        # Check annotations
        for fact_id, ann in builder.cart.annotations.items():
            if fact_id in [1, 2]:  # Newton's laws
                assert ann.temporal_validity_start is None
                assert ann.temporal_validity_end is None
            elif fact_id == 3:  # Sun exploding
                assert ann.temporal_validity_start is not None
                assert ann.temporal_validity_end is None
        
        print("✓ Full roundtrip works")
        return True
    finally:
        test_file.unlink(missing_ok=True)
        import shutil
        shutil.rmtree("cartridges/physics_test.kbc", ignore_errors=True)


if __name__ == "__main__":
    print("Testing Enhanced Markdown Parser\n")
    
    all_pass = True
    all_pass &= test_yaml_frontmatter()
    all_pass &= test_temporal_bounds()
    all_pass &= test_full_roundtrip()
    
    print("\n" + "="*70)
    if all_pass:
        print("✓ All parser tests passed")
    else:
        print("✗ Some tests failed")
    print("="*70)