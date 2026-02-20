# Redis Bus Architecture: Active Cognition Substrate
**Status:** MVP Design, Phase 3C Implementation  
**Related Docs:** `EPISTEMIC_STACK_PHASE5.md`, `CARTRIDGE_SPECIFICATION_COMPLETE.md`  
**Future Docs:** `TRIAGE_AGENT_ORCHESTRATION.md` (separate)

---

## Executive Summary

Redis is not a caching layer. It is the **active cognition substrate** of Kitbash—the real-time working memory where the system thinks.

The Redis bus:
- **Manages multi-layer attention spotlights** (one per epistemic level: L0–L5)
- **Executes coupling geometry deterministically** via Lua scripts
- **Coordinates between components** (grain/cart search, synthesis, context service, LLM interface)
- **Makes decision traces observable and replayable** for Phase 4 learning

Everything else—persistent knowledge (cartridges on disk), temporal context (BitMamba snapshots), learning signals (structured file logs)—supports this central bus. Redis is where the actual computation happens.

---

## The Problem: Token Window Externalization

Traditional LLM applications waste tokens on:
- **Attention mechanism overhead** (deciding what matters)
- **Context management** (tracking conversational state)
- **Metacognitive burden** (remembering constraints, rules, identity)

Kitbash externalizes all of this *outside the LLM's token window*:

1. **Grain/cartridge search** returns candidate facts (some noise acceptable)
2. **Redis bus** becomes the working memory where those facts are triaged, validated, and filtered
3. **Deterministic logic** (Lua scripts, Triage Agent routing) handles structural decisions
4. **BitNet synthesis** condenses the curated spotlight state into NWP assertions
5. **LLM receives clean, attention-filtered context** with no metacognitive overhead

The bus is where steps 2–4 happen atomically, observably, and replayably.

---

## Core Architecture: Multi-Layer Spotlights

### Epistemic Stack Recap (See `EPISTEMIC_STACK_PHASE5.md` for full details)

The system maintains six concurrent attention spotlights on Redis, one per epistemic layer:

```
L0_EMPIRICAL  — Raw observations, verified facts (confidence 0.90–0.99)
L1_AXIOMATIC  — Foundational axioms, rules (confidence 0.95–0.99)
L2_NARRATIVE  — Story events, character history (confidence 0.60–0.90)
L3_HEURISTIC  — Folk wisdom, analogies (confidence 0.50–0.80)
L4_INTENT     — Character intent, empathy state (confidence 0.40–0.75)
L5_MASK       — Public persona, interaction style (confidence 0.30–0.70)
```

At any moment in a query lifecycle, each layer has an **active spotlight**: a small set of facts currently relevant to the query. Lower layers constrain higher layers via **coupling geometry** (see below).

### What Lives Where

```
┌─────────────────────────────────────────────────────────┐
│ REDIS BUS (Hot, Active, Queryable)                      │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  L0_spotlight = [fact_1, fact_2, ...]                   │
│  L1_spotlight = [axiom_1, axiom_2, ...]                 │
│  L2_spotlight = [narrative_event_1, ...]                │
│  L3_spotlight = [heuristic_1, ...]                       │
│  L4_spotlight = [intent_signal_1, ...]                   │
│  L5_spotlight = [mask_token_1, ...]                      │
│                                                           │
│  coupling_state = {L0→L1, L1→L2, L2↔L4, ...}           │
│  query_lifecycle = [grain_search, synthesis, ...]       │
│  structural_deltas = [delta_1, delta_2, ...]            │
│                                                           │
└─────────────────────────────────────────────────────────┘
         ↕ (query in/out)
┌─────────────────────────────────────────────────────────┐
│ DISK STORAGE (Cold, Persistent, Archive)                │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Cartridges: {domain}_{faction}.kbc/                    │
│    ├── facts.db (SQLite)                                │
│    ├── annotations.jsonl                                │
│    ├── indices/ (keyword, semantic, frequency)          │
│    └── grains/ (crystallized facts)                      │
│                                                           │
└─────────────────────────────────────────────────────────┘
         ↕ (search / grain updates)
┌─────────────────────────────────────────────────────────┐
│ STRUCTURED FILE LOGS (Cold, Archived, Analyzed)         │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  {date}/query_traces.jsonl                              │
│  {date}/routing_decisions.jsonl                         │
│  {date}/coupling_violations.jsonl                       │
│  {date}/synthesis_outputs.jsonl                         │
│                                                           │
│  (Phase 4 metabolism analyzes these for learning)       │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

**Key principle:** Redis holds only what's *active right now*. Everything else is either on disk (persistent knowledge) or in files (historical decision traces).

---

## Query Lifecycle on the Bus

A typical query flows through Redis as follows:

```
1. Query Arrives
   └─> Query posted to Redis: {query_id, query_text, timestamp}

2. Grain/Cartridge Search (Disk → Redis)
   └─> Candidate facts returned, scattered across layer spotlights
       based on their epistemic level (L0 facts → L0_spotlight, etc.)

3. Triage Agent Reads Bus State
   └─> Reads all six spotlights + coupling constraints
       Decides which facts stay, which are filtered, which are escalated

4. Coupling Geometry Executes (Lua)
   └─> Constraints applied atomically:
       - L0 facts validate L1 consistency
       - L1 axioms gate L2 narrative access
       - L2 history XOR-masks L4 intent
       - L4 intent gates L3 heuristics → L5 mask
       
5. BitMamba State Query (Optional)
   └─> Triage queries BitMamba for temporal context snapshot
       (How salient is each spotlight historically?)

6. BitNet Synthesis
   └─> Reads curated spotlight state
       Outputs condensed NWP assertions

7. Context Injection
   └─> Synthesis + BitMamba context → LLM input block

8. LLM Generation
   └─> Response generated

9. Response Logged (Redis → Files)
   └─> Response + metadata posted to Redis temporarily
       Then dumped to structured file logs for Phase 4 analysis

10. Spotlight Cleared or Decayed
    └─> Query-specific spotlight state expires
        System ready for next query
```

---

## Coupling Geometry on Redis

The six epistemic layers don't exist in isolation. **Coupling constraints** enforce relationships:

### Vertical Pressure

**Downward (Deduction):** L0 observations constrain what L1 axioms can be, which constrain L2 narrative, which constrain L4 intent, which constrain L5 mask.

**Upward (Induction):** L5 observations try to generalize into L4 patterns, which try to solidify into L2 narrative, which try to unify with L1 axioms, which anchor in L0.

### Coupling as Lua

Rather than checking constraints in application code, they execute as **atomic Lua operations on Redis**:

```lua
-- Example: L4 intent gates L3 heuristic access

function gate_heuristic_access(query_id, heuristic_id)
  local l4_intent = redis.call('GET', query_id .. ':L4_spotlight')
  local intent_flags = cjson.decode(l4_intent)
  
  if intent_flags.allows_folk_wisdom then
    redis.call('LPUSH', query_id .. ':L3_approved', heuristic_id)
    return 'approved'
  else
    redis.call('LPUSH', query_id .. ':L3_blocked', heuristic_id)
    return 'blocked'
  end
end
```

Lua scripts on Redis guarantee **atomicity**: either the constraint applies fully or not at all. No race conditions, no partial states.

### Structural Deltas

When two layers contradict, a **delta** is recorded on the bus:

```
{
  delta_id: "delta_001",
  timestamp: 1708397400,
  layer_a: "L0_EMPIRICAL",
  layer_b: "L2_NARRATIVE",
  conflict: "L0 says water boils at 100C, L2 says character believes 50C",
  severity: "high",
  resolution: "unresolved"
}
```

Deltas are queryable. The **structural validator** (formerly "pain sensor") runs as a Lua script:

```lua
function check_structural_health(query_id)
  local deltas = redis.call('LRANGE', query_id .. ':deltas', 0, -1)
  local high_severity_count = 0
  
  for _, delta in ipairs(deltas) do
    if delta.severity == 'critical' then
      high_severity_count = high_severity_count + 1
    end
  end
  
  if high_severity_count > threshold then
    return 'trigger_dissonance_response'
  end
  return 'coherent'
end
```

---

## Triage Agent Partnership

**Triage Agent** (BitNet-based, separate doc forthcoming) is the **active orchestrator** of the bus.

Triage reads:
1. **Multi-layer spotlight state** (what's active in each L0–L5)
2. **Coupling constraints** (what gates what)
3. **Structural deltas** (what contradicts)

Triage decides:
- Which candidate facts from grain/cart search stay in which spotlight
- Whether L3 heuristics can be accessed (gated by L4)
- Whether a contradiction is critical (escalate) or acceptable (log and continue)
- When to defer to BitMamba for temporal context

Triage's decisions are **logged as events on the bus** for Phase 4 to learn from:

```
{
  decision_id: "route_001",
  timestamp: 1708397400,
  type: "grain_filter",
  rationale: "L4_intent_check_failed",
  input: [grain_1, grain_2, grain_3],
  output: [grain_1, grain_3],  # grain_2 blocked by intent gate
  confidence: 0.92
}
```

---

## BitMamba Integration: Temporal Context Service

**BitMamba** (SSM, separate from Redis) maintains **temporal state snapshots**.

Triage queries BitMamba to answer: "Historically, which epistemic layers have been most salient to this query type?"

BitMamba returns a **context snapshot**:

```
{
  snapshot_id: "snap_001",
  query_type: "creative_worldbuilding",
  layer_salience: {
    L0: 0.6,  -- Background grounding
    L1: 0.7,  -- Axioms still constrain
    L2: 0.95, -- Narrative is hot
    L3: 0.8,  -- Heuristics useful
    L4: 0.85, -- Intent matters
    L5: 0.75  -- Persona matters
  },
  recency_decay: exponential(days_since_similar_query)
}
```

Triage uses this to **modulate** spotlight attention:
- High L2 salience → expand narrative spotlight, gate L3 more carefully
- Low L0 salience → don't waste synthesis tokens on empirical validation

---

## Minimal MVP Schema

### Core Redis Keys (YAML notation for clarity)

```yaml
# Per-query namespace: {query_id}:*

query:{query_id}:
  metadata:
    query_text: string
    timestamp: unix_timestamp
    user_id: string
  
  L0_spotlight:
    - fact_id: string
      source_cartridge: string
      confidence: float
      
  L1_spotlight:
    - axiom_id: string
      source_cartridge: string
      
  L2_spotlight:
    - narrative_event_id: string
      source_cartridge: string
      narrative_timestamp: iso_date
      
  L3_spotlight:
    - heuristic_id: string
      blocked: boolean  # L4 intent gating
      
  L4_spotlight:
    - intent_signal: string
      allows_folk_wisdom: boolean
      allows_speculation: boolean
      
  L5_spotlight:
    - mask_token: string
      character_context: string
  
  coupling_checks:
    - layer_a: "L1"
      layer_b: "L2"
      passed: boolean
      delta_id: string (if failed)
  
  deltas:
    - delta_id: string
      layer_a: string
      layer_b: string
      severity: "low" | "medium" | "high" | "critical"
      resolved: boolean
  
  synthesis_output:
    nwp_assertions: [string, ...]  # NWP format (see NWP docs)
    timestamp: unix_timestamp
  
  lifecycle_stage: "search" | "triage" | "synthesis" | "injection" | "generation" | "logged"
```

### Logging/Archival

After generation, the full query state is **dumped to structured files**:

```
logs/
├── 2026-02-20/
│   ├── query_traces.jsonl
│   ├── routing_decisions.jsonl
│   ├── coupling_checks.jsonl
│   ├── structural_deltas.jsonl
│   └── synthesis_outputs.jsonl
```

Each file is **append-only JSONL**, one event per line, with full query context. No optimization yet; capture everything.

---

## NWP Connection (Brief Forward Reference)

Coupling constraints can be expressed as **NWP assertions** (see `NWP_v2_2_Specification.md`):

- L0 fact in spotlight: `⊢ [MAT:fact_1] ∈ [SYS:L0_EMPIRICAL]`
- Coupling check: `□ [SYS:L1_AXIOM] ⊃ ◊ [SYS:L2_NARRATIVE]` (L1 necessity implies L2 possibility)
- Delta detected: `⊢ [TSK:STRUCTURAL_DELTA] ∩ [SYS:COUPLING] ⇒ ⊥` (contradiction flagged)

Phase 5 will formalize NWP as the symbolic language of the bus. MVP treats it as a forward-design note; the actual bus mechanics are deterministic Lua + logical gating.

---

## What MVP Implements, What It Doesn't

### ✅ MVP Scope
- Multi-layer spotlights on Redis
- Lua coupling enforcement (deterministic gating rules)
- Query lifecycle logging
- Structural delta detection
- Integration with Triage Agent (BitNet routing orchestrator)
- Dump-to-file logging for Phase 4 analysis

### ⏳ Phase 4+ (Metabolism & Learning)
- Learning from routing decision logs
- Grain/cartridge surface salience weights
- Adaptive routing based on historical outcomes
- Dissonance response handling (stagnation detection, exploration triggers)

### ⏳ Phase 5+ (Epistemic Coupling & NWP)
- Formal NWP assertions on the bus
- XOR-masking for L2↔L4 coupling
- Full epistemic validation pipeline
- Narrative consistency checking (Metabolic Flush)

---

## Why This Works

### For MVP
- **Deterministic logic** on Redis is reliable and testable
- **Observable decision traces** enable Phase 4 learning without requiring neural machinery yet
- **Lua atomicity** prevents race conditions and partial states
- **Clear separation** (Redis = active, disk = archive) keeps latency low

### For Phase 4
- **Rich logs** provide training signal for learning what routing decisions work well
- **Queryable bus state** lets metabolism understand *why* a decision was made, not just *what* happened
- **Structured events** enable statistical analysis of coupling violations, spotlight evolution, etc.

### For Phase 5+
- **NWP ready** (symbolic layer designed to execute on this substrate)
- **Epistemic stack prepared** (six layers built into architecture)
- **Scaling ready** (Lua scripts can be sharded across Redis cluster if needed)

---

## Implementation Notes

### Latency Targets
- Grain/cart search → Redis post: <10ms
- Triage orchestration (Lua coupling checks): <5ms per layer
- Full query lifecycle: <50ms before synthesis (disk I/O dominates)

### Memory Assumptions
- Per-query spotlight state: ~1KB (rough)
- 1000 concurrent queries: ~1MB active memory (negligible)
- File logs grow ~100MB/day at heavy usage; rotate to cold storage

### Testing Strategy
- Unit test Lua scripts for coupling atomicity
- Integration test full query lifecycle against mock grain/cart data
- Replay logs with different routing weights to validate determinism

---

## Questions for Implementation

1. Should spotlight state expire automatically (TTL) or only on query completion?
2. Does Triage Agent need sub-ms feedback from Redis, or is <10ms acceptable?
3. Should deltas be auto-escalated (Lua) or only flagged for Triage to review?
4. Do we snapshot the entire spotlight state per query, or just deltas?
5. Should coupling constraints be configurable per-project (like epistemic κ from EPISTEMIC_STACK)?

---

## Related Documentation

- `EPISTEMIC_STACK_PHASE5.md` — Full epistemic layer detail and coupling geometry
- `CARTRIDGE_SPECIFICATION_COMPLETE.md` — How grains/carts interface with the bus
- `NWP_v2_2_Specification.md` — Symbolic language for Phase 5 (currently forward reference)
- `TRIAGE_AGENT_ORCHESTRATION.md` — (Forthcoming) Detailed routing orchestration logic
- `REDIS_QUERIES_REFERENCE.md` — (Forthcoming) All Lua scripts and query patterns
