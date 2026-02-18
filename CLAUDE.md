# CLAUDE.md — Working with Kitbash

This document explains how to effectively collaborate with Claude on Kitbash development. Read this before asking Claude to make changes.

---

## Project Overview

**Kitbash** is a knowledge orchestration system that retrieves facts from epistemologically-layered knowledge bases. It's currently at **Phase 3B MVP** and being expanded to **Extended MVP** (Phase 3C–3I).

### What It Does
- Routes queries through a layered cascade: **GRAIN** (crystallized facts, <1ms) → **CARTRIDGE** (domain knowledge, <200ms) → **ESCALATE** (future reasoning)
- Maintains an epistemological stack (L0 empirical facts, L1 narrative knowledge, L2+ reasoning)
- Coordinates background work through a metabolism cycle (heartbeat, resonance tracking, grain crystallization)
- Designed to integrate with external systems (SillyTavern, etc.) via HTTP API

### Current State
- ✅ Query orchestrator working
- ✅ 45-query test suite passing
- ✅ GRAIN/CARTRIDGE cascade functional
- ❌ FastAPI HTTP wrapper (not built yet)
- ❌ SillyTavern integration (blocked on HTTP wrapper)
- ❌ Rich cartridge content (10 domains exist but sparse)

---

## Development Environment

### Setup
```bash
cd /home/user/Kitbash_Project
python3.10 -m venv venv
source venv/bin/activate
# Install dependencies (if needed — most are already in the repo)
pip install -r requirements.txt  # if it exists
```

### Running the Test Suite
```bash
cd src/tests
python query_test_harness.py
```

**Expected output:**
- 45 queries processed
- 42 answered (some intentionally fail)
- All tests pass, no crashes
- Latencies <200ms per query

**This is your single source of truth.** If the test suite passes, the change is good. If it fails, fix it.

### Project Structure
```
Kitbash_Project/
├── src/                      # Core implementation
│   ├── engines/              # Inference engines (GRAIN, CARTRIDGE, etc.)
│   ├── cartridges/           # Knowledge domains (10 pre-built)
│   ├── orchestration/        # QueryOrchestrator (central router)
│   ├── routing/              # Triage logic
│   ├── memory/               # Resonance weights, caching
│   ├── registry/             # Knowledge indices
│   ├── tests/                # Test harness & queries
│   └── interfaces/           # Abstract base classes
├── metabolism/               # Background work coordination
├── kitbash/                  # Python package structure
├── docs/                     # Technical documentation
└── CLAUDE.md                 # This file
```

---

## The Immediate Ask: Phase 3C (FastAPI HTTP Wrapper)

This is the blocking task. Everything else depends on it.

### What Needs to Be Built
A FastAPI application that wraps `QueryOrchestrator` and exposes these endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/query` | POST | Single query: `{"query": "what is X?"}` → `{answer, confidence, source_engine}` |
| `/api/batch_query` | POST | Multiple queries: `{"queries": [...]}` → list of results |
| `/health` | GET | Service health: `{status, uptime, engines_available}` |
| `/info` | GET | Service info: `{version, cartridges_loaded, grain_count, etc}` |

### Success Criteria for Phase 3C
- [ ] FastAPI app scaffolded and runs without crashes
- [ ] All 45 test queries pass through `/api/query`
- [ ] `/health` and `/info` endpoints work
- [ ] Request validation (reject malformed input gracefully)
- [ ] Response serialization matches spec
- [ ] HTTP overhead doesn't add >10ms latency per query
- [ ] API documentation auto-generated (Swagger/OpenAPI)
- [ ] Can start service with single command: `python main.py` or similar

### Implementation Notes
- QueryOrchestrator is in `src/orchestration/` — import and call it directly
- It returns a `QueryResult` object; serialize to JSON
- Use Pydantic models for request/response validation
- Add basic logging (just print to stdout is fine for now)
- No Redis or complex async yet — keep it simple
- Consider startup handlers to verify cartridges are loaded

---

## Key Constraints: The Things Not to Break

### 1. The Epistemological Stack is Sacred
**L0 (GRAIN):** Crystallized facts, immutable, high confidence (0.90+)
**L1 (CARTRIDGE):** Domain knowledge, searchable, medium confidence (0.70+)
**L2+:** Future (BITNET, LLM) — not implemented yet

**Rule:** Lower layers are sources of truth. Never let upper layers corrupt lower layer confidence scores. If something seems wrong with the epistemological levels, **ask before changing**.

### 2. The Triage & Routing System
- `RuleBasedTriageAgent` decides which engines to try
- Current sequence: GRAIN → CARTRIDGE → ESCALATE
- Confidence thresholds: consensus=0.85, escalation=0.60
- **Don't touch this unless explicitly asked.** The routing sequence is sacred.

### 3. Background Work Coordination
- `HeartbeatService` pauses/resumes background work around user queries
- `ResonanceWeightService` tracks query patterns (Ebbinghaus decay)
- These coordinate through `QueryOrchestrator.pause_background_work()` / `resume_background_work()`
- **Don't refactor this logic without discussion.** It's delicate.

### 4. QueryOrchestrator Interface
- Don't break the external API: `orchestrator.query(query_text, metadata)`
- This interface is what external systems (SillyTavern) will call
- If you need to change it, discuss first — it affects integration

### 5. Import Paths
- Use relative imports: `from kitbash.engines import GrainEngine`
- All engines/services are in the `kitbash/` namespace
- If something is missing, it's probably not in the repo — don't assume

### 6. Configuration & Hardcoded Paths
- Paths are currently hardcoded (cartridges_dir, etc.)
- **Phase 3F will make this configurable.** For now, don't change it unless necessary
- If you need to add a new path, hardcode it and note TODO for Phase 3F

---

## What NOT to Do

❌ **Don't refactor the orchestrator** — it's the beating heart of the system
❌ **Don't add new engines or layers** — that's Phase 4+ work
❌ **Don't experimentally modify confidence thresholds** — they're tuned
❌ **Don't add dependencies without checking** — they may already exist
❌ **Don't try to optimize latency** before we have real load data
❌ **Don't touch the epistemological levels** without discussion
❌ **Don't add hot-reloading, async parallelization, or fancy features** — that's beyond Extended MVP

---

## Testing & Validation

### Before Committing
Always run the test suite:
```bash
cd src/tests
python query_test_harness.py
```

**Must pass.** If it doesn't, fix the issue before committing.

### What Passes = What's Good
The 45-query test suite is the source of truth. If all tests pass:
- The change is valid
- Latencies are acceptable
- No crashes or exceptions
- Behavior is correct

### If You're Unsure
- **Run the test suite** — it will tell you
- **Check latencies** — if they're still <200ms, you're good
- **Read the error message** — they're designed to be informative

---

## Extended MVP Roadmap

After Phase 3C, here's what comes next:

### Sequential (Each Depends on Previous)
1. **Phase 3C:** FastAPI HTTP wrapper ← **START HERE**
2. **Phase 3D:** SillyTavern integration (depends on HTTP service)
3. **Phase 3I:** Documentation (after everything else is done)

### Parallel (Can Run Concurrently with 3D+)
- **Phase 3E:** Cartridge content expansion (add 500–1000 facts per domain)
- **Phase 3F:** Configuration system (YAML, env vars, startup checks)
- **Phase 3G:** Observability & debugging (structured logging, tracing)
- **Phase 3H:** Edge case handling & robustness (malformed input, timeouts, graceful degradation)

**Timeline:** ~6–8 weeks total for Extended MVP (solo development, focused work).

### Extended MVP Success Criteria
✅ Kitbash is a running HTTP service
✅ SillyTavern can call it and use results
✅ Knowledge bases are rich enough for real use
✅ Configuration is declarative (no code changes)
✅ Logs show what's happening
✅ Edge cases don't crash the service
✅ 100+ query test suite passes reliably

---

## When to Ask for Guidance

### Ask Before:
- Refactoring the orchestrator or routing logic
- Modifying epistemological levels or confidence thresholds
- Adding new engines, layers, or major features
- Changing the QueryOrchestrator interface
- Adding new dependencies
- Making a destructive git operation (force push, hard reset, etc.)

### Go Ahead Without Asking:
- Fixing bugs in the test suite
- Implementing Phase 3C endpoints (FastAPI wrapper)
- Adding new test queries
- Improving error messages or logging
- Expanding cartridge content
- Adding docstrings or comments (if they clarify existing code)
- Fixing import path issues

### Always Run Tests After:
- Any change to engines or orchestration logic
- Any change that might affect query routing or results
- Any change that touches confidence scores or result filtering

---

## Key Resources

### Code Documentation
- `src/readme.md` — Overview of core modules
- `src/engines/engines.md` — How the inference engines work
- `src/orchestration/orchestration.md` — QueryOrchestrator design
- `src/routing/routing.md` — Triage and routing logic
- `src/cartridges/carts.md` — Cartridge format and structure
- `src/tests/tests.md` — Test harness documentation

### In-Code References
- `src/tests/query_test_harness.py` — The ground truth for expected behavior
- `src/orchestration/query_orchestrator_week3.py` — The orchestrator (study this)
- `src/engines/grain_engine.py` — Fast GRAIN lookups
- `src/engines/cartridge_engine.py` — Keyword search in CARTRIDGE

### Docstring Style
Use Google style docstrings:
```python
def query(self, query_text: str, metadata: dict) -> QueryResult:
    """Route a query through the cascade.

    Args:
        query_text: The user's question
        metadata: Optional context (source, user_id, etc.)

    Returns:
        QueryResult with answer, confidence, and source_engine

    Raises:
        ValueError: If query_text is empty
    """
```

---

## Git Workflow

### Branch
- Develop on the assigned feature branch (e.g., `claude/add-claude-documentation-7as8V`)
- Commit with clear, descriptive messages
- Push when work is complete

### Commit Messages
- Be specific: "Add FastAPI endpoint for /api/query" not "Update code"
- Explain why, not what: "Use Pydantic for request validation to catch malformed input early" not "Added Pydantic import"
- Reference the phase: "Phase 3C: Add /health endpoint"

### Example
```
git add src/main.py
git commit -m "Phase 3C: Add FastAPI application with /api/query endpoint

- Wrap QueryOrchestrator in async endpoint
- Use Pydantic for request/response validation
- Log query execution time for debugging"
```

---

## Debugging & Troubleshooting

### Query Fails to Answermsg
1. Check if it's in the 45-query test suite (if yes, it's expected to fail)
2. Run the query directly through `QueryOrchestrator` to see what each engine returns
3. Check cartridge content — the domain might not have the fact
4. Check confidence scores — the answer might be below thresholds

### Latency Issues
1. Time each engine separately (GRAIN, CARTRIDGE)
2. Check if it's the cascade order (correct, fastest first)
3. GRAIN should be <1ms; CARTRIDGE <200ms
4. If not, measure and investigate

### Crashes or Exceptions
1. Read the traceback — it's informative
2. Check for malformed query input
3. Verify all cartridges are loaded at startup
4. Run the test suite — if it still passes, it's a new edge case

### Configuration/Import Issues
1. Check paths are correct relative to working directory
2. Verify all engines are importable from `kitbash/`
3. Check that cartridges are in the expected location
4. Read the import error — Python usually tells you what's wrong

---

## Final Notes

**You're building the bridge between Kitbash and the outside world.** Phase 3C is the most important milestone — once it works, everything else becomes possible.

**Trust the test suite.** If it passes, you're good. If it fails, fix it. Don't override it or ignore it.

**Ask questions when unsure.** The constraints exist to protect the system; violating them could break things that aren't obvious from a single change.

**Iterate based on feedback.** After Phase 3C, real usage will show what needs to be fixed or improved. Don't over-engineer.

Good luck, and welcome to Kitbash. 🚀
