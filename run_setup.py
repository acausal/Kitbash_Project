"""Setup PYTHONPATH for Kitbash development."""
import sys
from pathlib import Path

project_root = Path(__file__).parent
src_dir = project_root / "src"

# Set PYTHONPATH to src/ so imports work
sys.path.insert(0, str(src_dir))

# Verify it works
print(f"✓ PYTHONPATH: {src_dir}")

# Test critical imports
try:
    from redis_spotlight import RedisSpotlight
    print("✓ redis_spotlight imports")
except ImportError as e:
    print(f"✗ redis_spotlight: {e}")

try:
    from interfaces.triage_agent import TriageAgent
    print("✓ interfaces imports")
except ImportError as e:
    print(f"✗ interfaces: {e}")

try:
    from orchestration.query_orchestrator import QueryOrchestrator
    print("✓ query_orchestrator imports")
except ImportError as e:
    print(f"✗ query_orchestrator: {e}")

print("\n✅ Setup complete. Ready for Phase 4.1 work.")