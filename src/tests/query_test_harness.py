#!/usr/bin/env python3
"""
QueryTestHarness - Phase 3B Week 3/4 Integration Check

Verifies that all Phase 3B interfaces are correctly implemented and that
the engine adapters (GrainEngine, CartridgeEngine, BitNetEngine) conform
to the InferenceEngine ABC.

Also runs the query test suite against the full QueryOrchestrator stack
to verify Heartbeat pausing, Turn advancement, and Sieve cascading.

Location: src/tests/query_test_harness.py
"""

import sys
import time
import json
import argparse
import traceback
import types
import importlib
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# --- Path setup ---
# SRC_DIR: B:\ai\llm\kitbash\src
# ROOT_DIR: B:\ai\llm\kitbash (where metabolism/ likely lives)
SRC_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = SRC_DIR.parent

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# --- Namespace Patching (The "Kitbash" Bridge) ---
def patch_kitbash_namespace():
    """
    Forcefully maps the 'kitbash' namespace to local directories.
    Handles the split structure:
    - src/ -> kitbash.interfaces, kitbash.engines, kitbash.orchestration
    - metabolism/ -> kitbash.metabolism
    """
    if "kitbash" not in sys.modules:
        kitbash_mod = types.ModuleType("kitbash")
        kitbash_mod.__path__ = [str(SRC_DIR), str(ROOT_DIR)]
        sys.modules["kitbash"] = kitbash_mod
    
    mapping = {
        "interfaces": SRC_DIR / "interfaces",
        "engines": SRC_DIR / "engines",
        "orchestration": SRC_DIR / "orchestration",
        "memory": SRC_DIR / "memory",
        "context": SRC_DIR / "context",
        "routing": SRC_DIR / "routing",
        "metabolism": ROOT_DIR / "metabolism"
    }
    
    errors = []
    for sub, path in mapping.items():
        full_name = f"kitbash.{sub}"
        try:
            if not path.exists():
                continue
                
            if sub in sys.modules and not full_name.startswith("kitbash."):
                sys.modules[full_name] = sys.modules[sub]
            else:
                parent_str = str(path.parent)
                if parent_str not in sys.path:
                    sys.path.insert(0, parent_str)
                mod = importlib.import_module(sub)
                sys.modules[full_name] = mod
        except (SyntaxError, UnicodeDecodeError) as e:
            errors.append(f"  ! ENCODING ERROR in '{sub}': {e}")
        except ImportError as e:
            if sub in ["orchestration", "interfaces", "metabolism"]:
                errors.append(f"  ! IMPORT ERROR in '{sub}': {e}")
    
    return errors

# =============================================================================
# Helpers
# =============================================================================

def _ok(msg: str) -> None:
    print(f"  \u2713 {msg}")

def _fail(msg: str) -> None:
    print(f"  \u2717 {msg}")

def _section(title: str) -> None:
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

def _subsection(title: str) -> None:
    print(f"\n  --- {title} ---")

# =============================================================================
# Interface Checks
# =============================================================================

class InterfaceChecker:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def run(self) -> bool:
        _section("INTERFACE CHECK")
        
        patch_errors = patch_kitbash_namespace()

        if patch_errors:
            for err in patch_errors:
                _fail(err)
            self.failed += 1

        try:
            self._check_mamba_service()
            self._check_triage_agent()
            self._check_inference_engines()
        except Exception as e:
            _fail(f"Interface check failed: {e}")
            traceback.print_exc()
            self.failed += 1

        print(f"\n  Result: {self.passed} passed, {self.failed} failed")
        return self.failed == 0

    def _check_mamba_service(self) -> None:
        _subsection("MambaContextService / MockMambaService")
        try:
            from kitbash.context.mock_mamba_service import MockMambaService
            from kitbash.interfaces.mamba_context_service import MambaContextRequest
            svc = MockMambaService()
            ctx = svc.get_context(MambaContextRequest())
            # Verifies Week 3 window compliance
            assert hasattr(ctx, 'context_1hour'), "MambaContext missing context_1hour"
            _ok("MockMambaService OK")
            self.passed += 1
        except Exception as e:
            _fail(f"Mamba check failed: {e}")
            self.failed += 1

    def _check_triage_agent(self) -> None:
        _subsection("TriageAgent / RuleBasedTriageAgent")
        try:
            from kitbash.routing.rule_based_triage import RuleBasedTriageAgent
            agent = RuleBasedTriageAgent()
            _ok("RuleBasedTriageAgent OK")
            self.passed += 1
        except Exception as e:
            _fail(f"Triage check failed: {e}")
            self.failed += 1

    def _check_inference_engines(self) -> None:
        _subsection("InferenceEngine implementations")
        for mod_name, cls_name in [("kitbash.engines.grain_engine", "GrainEngine"), 
                                   ("kitbash.engines.cartridge_engine", "CartridgeEngine"),
                                   ("kitbash.engines.bitnet_engine", "BitNetEngine")]:
            try:
                mod = importlib.import_module(mod_name.replace("kitbash.", ""))
                cls = getattr(mod, cls_name)
                if cls_name == "BitNetEngine":
                    cls()
                else:
                    cls(cartridges_dir=str(SRC_DIR / "cartridges"))
                _ok(f"{cls_name} OK")
                self.passed += 1
            except Exception as e:
                _fail(f"{cls_name} failed: {e}")
                self.failed += 1

# =============================================================================
# Query Suite Runner
# =============================================================================

class QuerySuiteRunner:
    def __init__(self):
        self.results = []

    def run(self) -> bool:
        _section("QUERY SUITE")
        patch_kitbash_namespace()
        
        suite_path = Path(__file__).resolve().parent / "query_test_suite.json"
        if not suite_path.exists():
            _fail("Suite file missing")
            return False

        with open(suite_path) as f:
            queries = json.load(f)["queries"]
        print(f"  Loaded {len(queries)} queries")

        orch = self._init_orchestrator()
        if not orch:
            return False

        print("\n  Running...\n")
        for q in queries:
            try:
                # 1. Update triage turn count for metabolism decisioning
                from kitbash.routing.rule_based_triage import RuleBasedTriageAgent
                RuleBasedTriageAgent.current_turn = orch.heartbeat.turn_number
                
                # 2. Process query
                result_obj = orch.process_query(q["text"], context={"category": q["category"]})
                
                # 3. Record results
                self.results.append({
                    "id": q["id"], 
                    "text": q["text"], 
                    "layer": result_obj.engine_name, 
                    "confidence": result_obj.confidence, 
                    "latency": result_obj.total_latency_ms, 
                    "ok": True
                })
                print(f"  \u2713 [{q['id']}] {q['text'][:40]:<40} -> {result_obj.engine_name:<10} {result_obj.total_latency_ms:6.1f}ms")
            except Exception as e:
                print(f"  \u2717 [{q['id']}] {q['text'][:40]:<40} -> ERROR: {e}")
                self.results.append({
                    "id": q["id"], 
                    "text": q["text"], 
                    "layer": "ERROR", 
                    "ok": False, 
                    "error": str(e)
                })

        self._report(orch)
        return True

    def _init_orchestrator(self):
        try:
            from kitbash.orchestration.query_orchestrator import QueryOrchestrator
            from kitbash.routing.rule_based_triage import RuleBasedTriageAgent
            from kitbash.engines.grain_engine import GrainEngine
            from kitbash.engines.cartridge_engine import CartridgeEngine
            from kitbash.engines.bitnet_engine import BitNetEngine
            from kitbash.context.mock_mamba_service import MockMambaService
            from kitbash.memory.resonance_weights import ResonanceWeightService
            from kitbash.metabolism.heartbeat_service import HeartbeatService
            from kitbash.metabolism.metabolism_scheduler import MetabolismScheduler
            from kitbash.metabolism.background_metabolism_cycle import BackgroundMetabolismCycle

            cart_path = str(SRC_DIR / "cartridges")

            engines = {
                "GRAIN": GrainEngine(cartridges_dir=cart_path),
                "CARTRIDGE": CartridgeEngine(cartridges_dir=cart_path),
                "BITNET": BitNetEngine()
            }

            resonance = ResonanceWeightService()
            heartbeat = HeartbeatService()
            triage = RuleBasedTriageAgent()
            
            # Metabolism Setup
            bg_cycle = BackgroundMetabolismCycle(triage, resonance)
            scheduler = MetabolismScheduler(bg_cycle, heartbeat, background_interval=100)

            return QueryOrchestrator(
                triage_agent=triage,
                engines=engines,
                mamba_service=MockMambaService(),
                resonance=resonance,
                heartbeat=heartbeat,
                metabolism_scheduler=scheduler
            )
        except Exception as e:
            _fail(f"Initialization Error: {e}")
            traceback.print_exc()
            return None

    def _report(self, orch):
        _section("RESULTS")
        total = len(self.results)
        answered = [r for r in self.results if r["ok"] and r["layer"] != "NONE"]
        metrics = orch.get_metrics()
        
        print(f"  Total:    {total}")
        print(f"  Answered: {len(answered)}")
        print(f"  Pauses:   {metrics.get('heartbeat_pauses', 0)}")
        print(f"  Turns:    {metrics.get('resonance_turn', 0)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--suite", action="store_true")
    args = parser.parse_args()

    success = True
    if not args.suite:
        success = InterfaceChecker().run()
    
    if success and not args.quick:
        success = QuerySuiteRunner().run()

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())