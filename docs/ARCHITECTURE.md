# Kitbash Architecture

## Executive Summary

Kitbash is a **local-first, three-layer knowledge orchestration system** designed to meet in the middle between explicit knowledge (like Cyc) and neural networks. It processes user queries through a cascade of increasingly expensive reasoning layers, filtering noise and injecting context at each step before queries reach cloud inference.

The system uses:
- **GRAIN layer** — Fast, crystallized facts (0.17ms lookup)
- **CARTRIDGE layer** — Domain-organized knowledge with semantic search
- **LLM layer** — Cloud-based reasoning (optional, explicit opt-in)

This design ensures that **local filtering prevents irrelevant context from reaching paid APIs**, and **knowledge self-organizes through metabolic cycles** rather than requiring constant human curation.

---

## System Overview

### Three-Layer Cascade

```
User Query
    ↓
[TRIAGE] Intent Classification
    ↓ (What type of question? Which cartridges?)
[GRAIN LAYER] Fast Fact Matching
    ├─ GrainRouter searches 261 crystallized patterns
    ├─ Lookup time: 0.17ms (Bloom filter + ternary compression)
    └─ Hit → Return fact + confidence → Success
    ↓ (No grain hit)
[CARTRIDGE LAYER] Semantic Knowledge Search
    ├─ CartridgeEngine searches domain-organized knowledge
    ├─ Hybrid search: keyword (BM25) + semantic (embeddings)
    ├─ Cross-cartridge dependency resolution
    └─ Hit → Return context + confidence → Success
    ↓ (No cartridge hit)
[LLM LAYER] Cloud Reasoning (Optional, Explicit)
    ├─ User must opt-in OR triage explicitly routes here
    ├─ Preprocessed context injected
    ├─ Minimal, relevant facts only
    └─ Return LLM synthesis
    ↓
[VALIDATION] Epistemological Validation
    ├─ Check L0-L4 epistemic levels
    ├─ Detect contradictions
    ├─ Adjust confidence based on source
    └─ Flag dissonance for metabolism
    ↓
[RESPONSE] Return to User
```

### Key Principle: Local-First, Cloud-Optional

- **No auto-ping to paid APIs** — LLM layer requires explicit user request or triage decision
- **Progressive escalation** — Each layer gives you a chance to answer before moving upstream
- **Context reduction** — Only relevant, validated facts reach the LLM (90% token cost reduction vs naive RAG)

---

## Layer Specifications

### Layer 0: Triage (Intent Router)

**Purpose:** Classify query intent and route to appropriate cartridges/layers.

**Input:**
- User query (string)
- Context (optional: session history, domain, user preferences)

**Processing:**
- Classify query type (factual? reasoning? creative?)
- Determine which cartridges are relevant
- Set confidence thresholds for each layer
- Decide if LLM is needed upfront

**Output:**
- Layer sequence (e.g., [GRAIN, CARTRIDGE, LLM])
- Confidence thresholds for each layer
- Recommended cartridges
- Reasoning (why this sequence?)

**Contract:**
- Must return a layer sequence (no passthrough to default routing)
- Confidence thresholds must be in [0.0, 1.0]
- Can recommend cartridges that don't exist (CartridgeEngine handles gracefully)

**Example:**
```
Query: "What is photosynthesis?"
Intent: Factual, biology domain
Sequence: [GRAIN, CARTRIDGE]
Thresholds: {GRAIN: 0.90, CARTRIDGE: 0.75}
Cartridges: [biology_general, chemistry_general]
Reasoning: "Short factual question, likely in knowledge base, no LLM needed"
```

---

### Layer 1: Grain (Fast Fact Matching)

**Purpose:** Ultra-fast lookup of crystallized, high-confidence facts.

**Input:**
- Query (can be original or processed by triage)
- Threshold (e.g., 0.90)

**Processing:**
1. Hash query to pattern
2. Look up in Bloom filter (false positive rate controlled)
3. If hit, retrieve grain from ternary store
4. Decode ternary → fact + metadata
5. Check confidence against threshold

**Output:**
- Hit: `{fact, confidence, source_grain_id, latency_ms}`
- Miss: `{confidence, best_match_score, gap_to_threshold}`

**Performance:**
- Latency: 0.17ms average (median across 261 grains)
- Storage: Ternary compressed (~8 bits per fact vs 64+ for text)
- Accuracy: Bloom filter ensures zero false negatives (only false positives possible, caught by verification)

**Contract:**
- Must return within 1ms (SLA)
- Confidence is always between 0.0 and 1.0
- If confidence < threshold, escalate to next layer (don't guess)
- Grain IDs are immutable once assigned

**When to Escalate:**
- Grain not found
- Grain found but confidence < threshold
- Grain found but doesn't match semantic intent (wrong sense of word)

**Example:**
```
Query: "What freezes water?"
Pattern hash: hash("freezes water")
Lookup result: 
  - Grain grain_ice_001 found
  - Fact: "Temperature below 0°C freezes water"
  - Confidence: 0.98
  - Latency: 0.14ms
  - Threshold met (0.98 > 0.90) → RETURN
```

---

### Layer 2: Cartridge (Semantic Knowledge Search)

**Purpose:** Domain-organized knowledge search with semantic understanding.

**Input:**
- Query (original or expanded by triage)
- Threshold (e.g., 0.75)
- Cartridge list (from triage, or all if not specified)

**Processing:**
1. Load specified cartridges into memory
2. Run dual retrieval:
   - Semantic search: Embed query → cosine similarity on fact embeddings
   - Keyword search: BM25 on fact text
3. Merge results using Reciprocal Rank Fusion (RRF)
4. Optional: Cross-cartridge dependency resolution (if fact A references fact B, load B)
5. Filter by confidence threshold

**Output:**
- Hit: `{facts: [{text, confidence, source_cartridge, dependencies}, ...], merged_score, context_window_size}`
- Miss: `{candidates: [{text, score, gap_to_threshold}, ...], search_latency_ms}`

**Performance:**
- Latency: 65-200ms (depends on cartridge size and complexity)
- Cartridge size: Typically 100-1000 facts per cartridge
- Search strategy: Hybrid (keyword + semantic) to catch both exact matches and semantic relationships

**Contract:**
- Facts must have `confidence` metadata
- Cartridges can be missing/unavailable — gracefully skip and continue
- Embedding model is fixed (all-MiniLM-L6-v2 or equivalent)
- Dependency resolution is optional (if a fact has dependencies, include them but don't fail if missing)

**Cartridge Factions & Loading:**
- `_general` — Always loaded (trusted, L0-L1 facts)
- `_fiction` — Loaded if project_context = fiction/creative
- `_experiment` — Loaded if project_context = research/experiment
- `_self` — Always loaded (provides meta-context)

**When to Escalate:**
- No cartridges loaded (all unavailable)
- All results score below threshold
- Search timeout (>500ms)

**Example:**
```
Query: "How do plants make food?"
Cartridges loaded: [biology_general, chemistry_general, self_identity]
Semantic search results: [fact_567 (0.85), fact_234 (0.78), fact_891 (0.72)]
Keyword search results: [fact_567 (0.92), fact_445 (0.68)]
Merged (RRF): [fact_567 (0.88), fact_234 (0.78), fact_445 (0.68), fact_891 (0.72)]
Filtered (threshold 0.75): [fact_567, fact_234, fact_445, fact_891]
Dependencies: fact_567 references fact_123 (glucose) → load fact_123 too
Output: Multiple facts with context, ready for synthesis
```

---

### Layer 3: LLM (Cloud Reasoning)

**Purpose:** Complex reasoning on top of validated context.

**Input:**
- Query (original)
- Context (facts from Grain/Cartridge layers, with confidence scores)
- Reasoning prompt (system prompt + few-shot examples)

**Processing:**
1. Check user opt-in (explicit request to use LLM)
   - OR check if triage explicitly routed here
   - OR check if both Grain and Cartridge failed
2. Prepare context:
   - Inject validated facts only (filtered by epistemological level)
   - Redact low-confidence facts (≤ L3)
   - Include source attribution
3. Stream response from kobold.cpp or cloud API
4. Apply token limits (don't exceed budget)

**Output:**
- Synthesis: `{answer, sources: [{fact, cartridge, confidence}], reasoning_trace}`

**Contract:**
- LLM is OPTIONAL — never required for correct operation
- Context window is limited (depends on backend, typically 2k-4k tokens for context)
- API calls are logged and counted (for cost awareness)
- Fallback: If LLM fails, return "I need to think about this" rather than hallucinating

**When to Use LLM:**
- User explicitly asks ("I want your reasoning on this")
- Triage classifies query as requiring reasoning (not just facts)
- Both Grain and Cartridge exhausted without good answer
- Query is creative/generative (not factual lookup)

**Cost Model:**
- Grain: Free (local)
- Cartridge: Free (local)
- LLM: Paid — only if user or system explicitly chooses

**Example:**
```
Query: "Based on photosynthesis and climate change, how will plants adapt?"
Grain result: Miss (reasoning question, not fact lookup)
Cartridge result: Retrieved 5 facts about photosynthesis, 3 about climate change
User opt-in: "Use your reasoning"
LLM prepared context:
  - Fact: "Plants photosynthesize using sunlight, water, CO2"
  - Fact: "Global temperature rising 1.5°C per decade"
  - Fact: "Some plants have short-term adaptations (stomatal control)"
  - Sources: biology_general (0.95), climate_general (0.92), self_knowledge (0.88)
LLM synthesis: "Plants may evolve deeper root systems, altered blooming times..."
Cost: ~50 tokens (3 input + 47 output)
```

---

### Layer 4: Validation (Epistemological Gating)

**Purpose:** Ensure facts meet epistemic standards before use.

**Input:**
- Facts from Grain/Cartridge/LLM layers
- Epistemological criteria (L0-L4)

**Processing:**
1. Check each fact's epistemological level
2. Detect contradictions (fact A vs fact B)
3. Apply validation rules:
   - L0 (Empirical): Must be grounded in observation, confidence ≥ 0.95
   - L1 (Axiomatic): Must be consistent with L0, confidence ≥ 0.90
   - L2 (Narrative): Can be speculative, confidence ≥ 0.70, must flag source
   - L3 (Heuristic): Working hypothesis, confidence ≥ 0.50, explicit uncertainty
   - L4 (Intent): System goals/values, confidence varies, immutable during query
4. Adjust confidence based on validation outcome
5. Flag dissonance for downstream metabolism

**Output:**
- Validated facts: `{fact, epistemological_level, adjusted_confidence, sources}`
- Dissonance signals: `{type, severity, facts_involved}`

**Contract:**
- Validation is NON-BLOCKING (invalid facts are downgraded, not rejected)
- Contradictions are detected but not auto-resolved (flagged for learning)
- Confidence never increases, only decreases or stays same

**When Validation Blocks:**
- L0 fact with confidence < 0.95 (downgrade to L1)
- L1 fact contradicts L0 axiomatic (flag for review, use with caution)
- LLM synthesis contradicts validated L0 facts (note conflict in output)

**Example:**
```
Facts retrieved:
  - "Photosynthesis produces glucose" (biology_general, 0.98, L0)
  - "Plants create energy from sunlight" (chemistry_general, 0.92, L1)
Validation:
  - First fact: L0, confidence 0.98 ≥ 0.95 → PASS
  - Second fact: L1, confidence 0.92 ≥ 0.90 → PASS
  - Coherence: No contradiction (both true, different levels of abstraction)
  - Output: Both facts validated, confidence unchanged
```

---

## Data Flow & Latency Model

### Query Timeline

```
T+0ms:     User submits query
T+2ms:     Triage completes (intent classification)
T+2-20ms:  Grain search (0.17ms median, 20ms worst case with Bloom filter rebuild)
T+20ms:    Grain hit/miss decision
T+20-200ms: Cartridge search (65-200ms depending on cartridges loaded)
T+200ms:   Cartridge hit/miss decision
T+200-3000ms: LLM request (if needed) — mostly network latency
T+3000ms:  Validation pass
T+3000ms:  Return to user
```

**Total Latency:**
- Grain hit (best case): 20ms
- Cartridge hit: 200ms
- LLM required: 3000ms+ (network-bound)

**Concurrency:**
- Grain and Cartridge searches can run in parallel
- LLM requests are async (don't block next query)
- Validation is synchronous (final pass before returning)

---

## Error Handling & Fallback

### Grain Layer Fails
- Scenario: Grain lookup timeout, Bloom filter corruption, etc.
- Fallback: Escalate to Cartridge layer
- User Impact: Slower response, but no loss of correctness

### Cartridge Layer Fails
- Scenario: Cartridge unavailable, search timeout, embedding model offline
- Fallback: Escalate to LLM layer (if user opted in) OR return "I don't know"
- User Impact: May require cloud inference, or no answer

### LLM Layer Fails
- Scenario: API key invalid, network error, token limit exceeded
- Fallback: Return best answer from Cartridge + "I wasn't able to reason further"
- User Impact: Partial answer, user can refine query

### Validation Detects Contradiction
- Scenario: Grain fact contradicts Cartridge fact
- Action: Flag both, return with confidence-adjusted metadata
- User Impact: Output includes note that sources conflict (transparency)

### Recovery & Metabolism
- Failed queries are logged with reason
- Metabolism cycles analyze failures to improve routing
- High failure rates in a domain trigger cartridge review

---

## Extensibility Points (Phase 4+)

### New Layers
- **BitNetEngine** (Phase 4): Fast ranking/scoring before LLM
- **SpecialistEngine** (Phase 4): Domain-specific reasoning agents

### New Cartridge Types
- **Dynamic cartridges** (Phase 4): Generated on-the-fly from web searches
- **Temporal cartridges** (Phase 4): Time-aware facts with validity windows

### Metabolism Integration
- **Consolidation cycles** (Phase 4): Learn new patterns from queries
- **Dissonance resolution** (Phase 4): Auto-upgrade fact levels based on agreement
- **Grain evolution** (Phase 4): Grains update as understanding improves

### Self-Modification
- **Self-narrative updates** (Phase 5): System learns about itself
- **Routing adaptation** (Phase 5): Triage learns from past decisions
- **Cartridge organization** (Phase 5): Facts reorganize into new domains

---

## See Also

- `EPISTEMOLOGICAL_STACK.md` — L0-L4 definitions and decision rules
- `QUERY_CASCADE.md` — Detailed pseudocode for cascade flow
- `GRAIN_SPECIFICATION.md` — Grain format and crystallization
- `CARTRIDGE_CONTRACT.md` — Cartridge metadata and structure
- `PHASE_4_ROADMAP/METABOLISM_SKELETON.md` — Learning layer design
- `LOGGING_EVENTS.md` — What's logged at each layer

---

## Open Questions

1. **Parallelization:** Should Grain and Cartridge search run in parallel, or sequentially? (Current: Sequential to save resources)
2. **Cartridge hot-loading:** Can users mount/unmount cartridges mid-query? (Current: No, static for MVP)
3. **Context injection:** How much context is too much for the LLM? (Current: As much as fits, but need explicit tuning)
4. **Contradiction resolution:** If Grain and Cartridge disagree, which wins? (Current: Both returned, user decides)
5. **Metabolism frequency:** How often should consolidation cycles run? (Current: Open for Phase 4 design)
