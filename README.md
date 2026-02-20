# Kitbash: Externalizing LLM Context for Improved Coherence and Auditability

**Status:** MVP Phase 3B/3C (Proof of Concept)  
**License:** MIT  
**Python:** 3.10+

---

## Problem Statement

Current LLM applications face several interconnected problems:

### 1. Token Window Pressure
LLMs allocate tokens for both **content** and **metacognition**:
- Tracking conversation state and coherence
- Maintaining constraints and rules
- Managing context switching and knowledge boundaries
- Reasoning about what to attend to

This overhead limits how much actual task content fits in the window. Kitbash tests whether moving this metacognitive work *outside* the LLM's context window—into deterministic, observable infrastructure—can reduce token pressure.

### 2. Limited Auditability
LLM responses are largely opaque. While interpretability research helps, it's difficult to understand:
- Why a particular fact was selected or ignored
- How constraints were applied (or violated)
- Whether the response is coherent with prior statements
- What information shaped a conclusion

Kitbash logs every routing decision, constraint check, and synthesis step, making the full decision trace available for analysis.

### 3. Hallucination Mitigation
LLMs can confidently generate plausible-sounding but false information. Contributing factors:
- No persistent, queryable fact store (only prompt context)
- No validation layer checking consistency with known facts
- No distinction between empirical facts and speculative reasoning

Kitbash separates facts into epistemic layers (observations, axioms, narrative) with coupling constraints. Queries are routed through validated cartridges before synthesis.

### 4. Context Fragmentation in Multi-Project Workflows
Users switching between projects (fiction/research/general knowledge) risk:
- Facts from one context contaminating another
- Loss of project-specific constraints
- Inability to maintain separate knowledge boundaries

Kitbash isolates knowledge by faction (`*_general`, `*_fiction`, `*_experiment`) and switches cartridges based on explicit context.

### 5. Limited Observability of Reasoning State
Phase 4 "metabolism" (learning cycles) requires understanding *why* a routing decision worked or failed. Without observable decision traces:
- Learning signals are sparse
- No way to correlate routing quality with outcomes
- Can't replay or counterfactually analyze decisions

Kitbash logs query lifecycle events to Redis (observable) and files (permanent archive), enabling offline analysis.

---

## Technical Approach

### Core Architecture: Externalizing Metacognition

Rather than asking the LLM to manage context, constraints, and routing, Kitbash separates concerns:

```
Query Input
    ↓
Grain/Cartridge Search (disk-based indices, deterministic)
    ↓
Redis Bus (multi-layer attention spotlights, Lua constraint checking)
    ↓
Triage Agent (BitNet routing orchestrator, deterministic rules)
    ↓
BitNet Synthesis (compress spotlight → structured context)
    ↓
BitMamba Context Service (temporal state snapshots, optional)
    ↓
LLM (fresh context, no metacognitive overhead)
    ↓
Response Logging (Redis → structured files for analysis)
```

**Key design choices:**

1. **Local-first, no external services** — All processing runs on consumer hardware (6GB VRAM target)
2. **Deterministic baseline** — Start with explicit rules (Lua on Redis) before adding learned components
3. **Logs-first methodology** — Capture everything first, analyze later. No optimization until we understand what matters
4. **Immutable facts, mutable routing** — Grain cartridges are write-once. Only routing weights and spotlight selections change during learning

### Redis as Active Cognition Substrate

Redis is not a cache layer. It's the **working memory** where the system thinks:

- **Multi-layer spotlights** (L0-L5) represent attention state for each epistemic layer
- **Lua scripts** execute coupling constraints atomically (no race conditions)
- **Structural deltas** (contradictions) are queryable events
- **Query lifecycle events** logged for Phase 4 analysis

See `REDIS_BUS_ARCHITECTURE.md` for details.

### Grain Cartridge System

Facts are organized into **cartridges** by domain and faction:

```
{domain}_{faction}.kbc/
├── facts.db (SQLite, raw facts with metadata)
├── annotations.jsonl (epistemic level, confidence, sources)
├── indices/ (keyword, semantic, frequency)
└── grains/ (crystallized fact clusters, 250 bytes each)
```

**Factions:**
- `*_general` — Grounded facts, axioms (always loaded)
- `*_fiction` — Narrative, speculative (project-scoped)
- `*_experiment` — Hypotheses, preliminary findings (research-scoped)

**Grain crystallization** (Phase 4) compresses high-confidence fact clusters into ternary-encoded structures (~250 bytes each) for fast lookup and pattern matching.

### Epistemic Layers (Design Prepared, Phase 5 Implementation)

The system is architecturally prepared for coupling geometry between six epistemic layers:

| Layer | Content | Confidence | Role |
|-------|---------|-----------|------|
| **L0** | Observations | 0.90–0.99 | Anchor point for validation |
| **L1** | Axioms | 0.95–0.99 | Constraints on lower layers |
| **L2** | Narrative | 0.60–0.90 | Story/project context |
| **L3** | Heuristics | 0.50–0.80 | Folk wisdom, analogies |
| **L4** | Intent | 0.40–0.75 | Character/user modeling |
| **L5** | Persona | 0.30–0.70 | Communication style |

L0–L1 constrain L2–L5. MVP implements basic routing by layer; Phase 5 adds full coupling geometry. See `EPISTEMIC_STACK_PHASE5.md` for complete design.

---

## What This Addresses

### ✅ Token Window Pressure
- LLM receives pre-curated, synthesized context (no raw facts, no metadata overhead)
- Routing/constraint logic happens outside the window
- **Result:** More tokens available for actual task content

### ✅ Auditability
- Every routing decision logged: grain selected, why, confidence
- Constraint checks visible: which axioms gated which heuristics
- Spotlight state snapshotted: what was "active" during query
- **Result:** Full decision trace available for post-hoc analysis

### ✅ Hallucination Mitigation
- Facts sourced from validated cartridges, not generated
- Synthesis layer structures context as explicit assertions
- Coupling constraints prevent contradictions between layers
- **Result:** Fewer false facts injected into LLM context

### ✅ Context Fragmentation
- Cartridge loading gated by `project_context`
- Factions separate fact domains (`_general` vs `_fiction` vs `_experiment`)
- Fresh spotlight per query (no carryover between contexts)
- **Result:** Isolated knowledge boundaries, clean context switching

### ✅ Observability for Learning
- Comprehensive logging: what was searched, what was selected, why
- Structured format: queryable events, not text logs
- Deterministic replay: can rerun same query with different routing decisions
- **Result:** Phase 4 metabolism has signal for learning what routing works

---

## What This Does NOT Claim

- **Solves hallucination entirely** — Reduces the attack surface; doesn't eliminate LLM generation errors
- **Perfect coherence** — Coupling geometry is a structural safeguard, not a guarantee
- **Automatic learning** — Phase 4 is speculative; implementation will reveal what actually works
- **Beats large models at large-scale tasks** — Designed for coherence + auditability, not raw capability
- **Replaces transformer attention** — Complements it; the LLM is still a core component

---

## MVP Status & Architecture Phases

### Phase 3B (Current)
- ✅ Grain router (keyword search, 0.17ms lookups on 261 crystallized grains)
- ✅ Cartridge system (facts.db + annotations, faction-based loading)
- ✅ Query orchestrator (locks MVP pipeline: search → synthesis → injection → logging)
- ✅ Comprehensive logging (query lifecycle, routing decisions, constraint checks)
- 🔄 Redis bus integration (partial; full multi-layer spotlight design ready, implementation in progress)

### Phase 3C (Next)
- Distributed Redis (multi-device coordination)
- BitMamba integration (optional, temporal context service)
- Performance optimization (latency benchmarks, index optimization)

### Phase 4 (Future)
- **Metabolism & learning** — Analyze logs, discover routing patterns, build learning signals
- **Grain reorganization** — Auto-crystallization of high-frequency fact patterns
- **Neural routing** (optional) — SNNs as secondary routing layer if deterministic rules insufficient
- **Dissonance handling** — Detect and escalate contradictions between layers

### Phase 5 (Speculative)
- **Full epistemic coupling** — NWP symbolic language, complete layer validation
- **Self-narrative** — TVTropes-indexed life events, self-understanding
- **Neuromorphic learning** — ESNs for temporal dynamics, LNNs for context transitions

See `KITBASH_DESIGN_SPACE_ROADMAP.md` for decision framework (when to use deterministic vs. probabilistic approaches).

---

## Performance Targets

| Component | Latency | Notes |
|-----------|---------|-------|
| Grain search | <20ms | Index-based, deterministic |
| Cartridge query | <10ms | SQL indices on facts.db |
| Redis spotlight update | <5ms | Lua scripts, atomic |
| BitNet synthesis | <50ms | Fast classification, deterministic |
| Full query (pre-LLM) | <100ms | Goal: <200ms including I/O |

LLM inference time dominates; goal is to keep orchestration negligible.

---

## Hardware Assumptions

- **CPU:** 4+ cores (BitNet routing, synthesis)
- **RAM:** 6GB minimum (grain caches, spotlight state)
- **GPU (optional):** 6GB VRAM for BitMamba (SSM context service)
- **Storage:** SQLite cartridges (~10-50MB each), grain files (~5MB per crystallized set)

Runs on consumer hardware (tested on 1060 / 1070 Ti rigs). No cloud dependencies.

---

## Observability & Reproducibility

### Logging
```
logs/
├── YYYY-MM-DD/
│   ├── query_traces.jsonl (full lifecycle per query)
│   ├── routing_decisions.jsonl (grain/cartridge selection + confidence)
│   ├── constraint_checks.jsonl (coupling validation results)
│   ├── synthesis_outputs.jsonl (spotlight → context block)
│   └── structural_deltas.jsonl (contradictions detected)
```

All logging is **append-only JSONL**, structured for analysis.

### Reproducibility
- Deterministic routing (same query → same grains selected)
- Queryable decision traces (can answer "why was grain X selected?")
- Deterministic replay (can re-run query with different routing weights for counterfactual analysis)

---

## Current Limitations

### MVP Constraints
1. **No learned routing yet** — Grain/cartridge selection is deterministic (keyword search)
2. **No real-time metabolism** — Phase 4 learning is offline batch processing
3. **No epistemic validation** — Coupling constraints designed but not fully implemented
4. **Limited temporal state** — BitMamba integration still in progress
5. **No distributed consensus** — Single-instance only (Phase 3C adds Redis distribution)

### Design Constraints (By Choice)
1. **No LLM fine-tuning** — System works with off-the-shelf models
2. **No external APIs** — All processing local (for auditability and cost)
3. **No fancy compression** — Grains are ternary-encoded but simple; no deep compression
4. **No adaptive prompting** — Synthesis templates are static (Phase 4 may learn templates)

---

## Use Cases

### ✅ Well-Suited
- **Multi-project workflows** — Fiction/research/general knowledge separation
- **Coherence-critical systems** — Finance, legal, medical (where contradictions are costly)
- **Learning/research** — Understanding how routing decisions affect outcomes
- **Local-first applications** — No cloud dependencies, full audit trail
- **Constrained environments** — Consumer hardware, offline operation

### ❌ Not Well-Suited
- **Scale to billions of facts** — Cartridge system targets 10s-100s domains, not petabyte scale
- **Real-time updates** — Facts are immutable once crystallized (learning happens offline)
- **User-facing personalization** — Designed for internal coherence, not individual user models
- **Complex symbolic reasoning** — Lua rules are explicit; no automatic theorem proving

---

## Comparison to Related Work

| System | Focus | Trade-off |
|--------|-------|-----------|
| **RAG systems** | Retrieval quality | No meta-layer (why was X retrieved?) |
| **Knowledge graphs** | Entity relationships | No epistemic distinction (all facts equal) |
| **Symbolic AI (CLIPS, etc.)** | Explicit rules | Complexity explosion, hard to maintain |
| **LLM agents** | Task decomposition | No auditability of routing; hallucination risks |
| **Kitbash** | Auditability + coherence | Slower (offline metabolism), not real-time learning |

Kitbash is a **structural solution** to metacognition, not a performance optimization. It trades speed for observability.

---

## Getting Started

### Installation
```bash
git clone https://github.com/[user]/kitbash.git
cd kitbash
pip install -r requirements.txt
```

### Quick Start
```python
from kitbash import QueryOrchestrator, CartridgeEngine

# Load general knowledge
engine = CartridgeEngine(cartridge_path="cartridges/")
engine.load_faction("_general")

# Process query
orchestrator = QueryOrchestrator(engine)
result = orchestrator.process_query(
    "What is formal logic?",
    project_context=None
)

print(result['response'])
print(f"Grains used: {result['grain_ids']}")
print(f"Trace: {result['decision_trace']}")
```

See `docs/GETTING_STARTED.md` for detailed setup.

---

## Documentation

- **Architecture:** `docs/REDIS_BUS_ARCHITECTURE.md` (how the system thinks)
- **Cartridges:** `docs/CARTRIDGE_SPECIFICATION_COMPLETE.md` (fact organization)
- **Design Space:** `docs/KITBASH_DESIGN_SPACE_ROADMAP.md` (where to go when determinism fails)
- **Epistemic Stack:** `docs/EPISTEMIC_STACK_PHASE5.md` (future layer coupling, Phase 5)
- **NWP (Symbolic Layer):** `docs/NWP_v2_2_SPECIFICATION.md` (Phase 5 symbolic language)

---

## Contributing

Early-stage feedback welcome:
- **Engineers:** Does the architecture make sense? Where's the latency? Is it maintainable?
- **Researchers:** What's novel here? What would you test first? What am I missing?
- **Users:** Does context switching work for your multi-project needs? What breaks?

---

## Known Issues & Next Steps

### Phase 3B → 3C
- [ ] Full Redis bus integration (multi-layer spotlight tests)
- [ ] BitMamba context service integration
- [ ] Latency profiling (target <200ms full cycle)
- [ ] Index semantic filtering (TF-IDF branch testing)

### Phase 3C → 4
- [ ] Metabolism cycle 0 (batch analysis of query logs)
- [ ] Grain reorganization (automatic clustering of facts)
- [ ] Learning signal evaluation (which metrics correlate with response quality?)
- [ ] Dissonance handling (detect contradictions, escalate gracefully)

---

## License

MIT License. See `LICENSE` file for details.

---

## Citation

If you use Kitbash in research, please cite:

```bibtex
@software{kitbash2026,
  title={Kitbash: Externalizing LLM Context for Improved Coherence and Auditability},
  author={[Author]},
  year={2026},
  url={https://github.com/[user]/kitbash}
}
```

---

## Acknowledgments

- **Design philosophy:** Constraint-driven architecture, local-first, "complexity as fallback"
- **Neuromorphic inspiration:** SNNs, ESNs, LNNs (integrated in Phase 4+)
- **Problem statement:** Years of ADHD context-switching, multi-project workflows

---

## Contact

[TBD: email, Discord, GitHub issues]

---

**Last Updated:** February 2026  
**Maturity:** MVP Phase 3C/3D (Multi-Device Coordination)  
**Stability:** Expect changes through Phase 4
