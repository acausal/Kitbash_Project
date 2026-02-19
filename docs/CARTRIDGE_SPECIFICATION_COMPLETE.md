# KITBASH CARTRIDGE SPECIFICATION (COMPLETE)
**Unified, Future-Proofed, MVP-Ready**

*Last Updated: February 18, 2026*
*Status: Canonical Reference for Phase 3B+*

---

## EXECUTIVE SUMMARY

A cartridge is **not a static database**. It's a self-organizing knowledge container designed to:

1. **Store facts** with epistemological metadata (MVP)
2. **Link facts across domains** via dependencies (MVP → Phase 4)
3. **Reorganize during metabolism** (Phase 4+)
4. **Tag facts with narrative patterns** via TVTropes (Phase 5+)
5. **Enable self-assembly** of ontology through dense, strategic seeding

This spec covers MVP (phase 3B), with hooks for future extensions.

---

## DIRECTORY STRUCTURE

```
{domain}_{faction}.kbc/
│
├── facts.db
│   └── SQLite: raw facts with access tracking
│
├── annotations.jsonl
│   └── Per-fact metadata (epistemology, confidence, dependencies)
│
├── indices/
│   ├── keyword.idx (JSON - inverted keyword index)
│   ├── semantic.idx (JSON - embedding vectors)
│   └── frequency.idx (hash table - hot/cold tracking)
│
├── grains/
│   ├── grain_sg_001.ternary (binary - crystallized facts)
│   ├── grain_sg_002.ternary
│   └── manifest.json (grain registry)
│
├── metadata.json
│   └── Cartridge-level metadata
│
├── [PHASE 4+] specialist/
│   ├── ssm_snapshot.pt (State Space Model memory)
│   └── lora_*.pt (Domain-specific QLoRA weights)
│
└── [PHASE 5+] narrative_index.json
    └── TVTropes tagging for self-narrative
```

---

## NAMING CONVENTION: {domain}_{faction}

**Format:** `{domain}_{faction}.kbc`

**Components:**

- **`{domain}`:** Knowledge area (physics, chemistry, pedagogy, formal_logic, etc.)
- **`{faction}`:** Epistemic category (determines loading behavior + validation rules)

### Factions (Locked)

#### 1. `_general` (Always loaded)

**Content:** Grounded facts, validated axioms, empirical observations
**Epistemic Levels:** L0_EMPIRICAL + L1_AXIOMATIC primarily
**Confidence:** 0.85-0.99
**Loading:** Always in all contexts
**Validation:** Strictest (must pass all checks)

**Examples:**
- `physics_general.kbc` — Physics laws, constants
- `formal_logic_general.kbc` — Logical axioms
- `chemistry_general.kbc` — Element properties, reactions
- `pedagogy_general.kbc` — Learning mechanisms

**Purpose:** Single source of truth across all projects

---

#### 2. `_fiction` (Project-scoped)

**Content:** Narrative facts, world-building, character knowledge, analogies
**Epistemic Levels:** L2_NARRATIVE + L3_HEURISTIC primarily
**Confidence:** 0.40-0.85 (explicitly marked)
**Loading:** Only when project_context = fiction/entertainment
**Validation:** Looser (must not contradict L0/L1 but can be speculative)

**Examples:**
- `physics_fiction.kbc` — "Magic adds forces" / alternate physics
- `formal_logic_fiction.kbc` — How logic works in fantasy worlds
- `biology_fiction.kbc` — Mythological creatures + real biology

**Purpose:** Keep narrative facts separate, enable context switching

---

#### 3. `_experiment` (Research-scoped)

**Content:** Hypotheses, preliminary findings, test cases, edge cases
**Epistemic Levels:** L2_NARRATIVE + L4_INTENT (validation-pending)
**Confidence:** 0.30-0.80 (explicitly marked as experimental)
**Loading:** Only when project_context = research/experiment
**Validation:** Variable (must flag confidence, but allowed to be speculative)

**Examples:**
- `physics_experiment.kbc` — Testing quantum interpretations
- `biochemistry_experiment.kbc` — Novel enzyme pathways
- `psychology_experiment.kbc` — New therapeutic approaches

**Purpose:** Sandbox for ideas before graduation to general or archival

---

#### 4. `_self` (Always Loaded, Meta-Referential)

**Content:** System's own self-narrative, design foundation, identity, self-understanding
**Epistemic Levels:** L0 (foundational constraints) + L2 (self-narrative) + L3 (current understanding)
**Confidence:** Variable by layer (immutable = 1.0, dynamic = evolving)
**Loading:** Always (provides meta-context for all operations)
**Validation:** Strict on immutable layer (design constraints), flexible on dynamic layer

**Examples:**
- `self_narrative_general.kbc` — Life events, growth arcs, identity
- `self_identity_general.kbc` — Core axioms and constraints

**Purpose:** System's own understanding of itself; meta-foundation for self-modification and growth

**Special Rules:**
- **Never exported** (too meta, too personal, instance-specific)
- **Read-write by metabolism** (system updates self-understanding during consolidation cycles)
- **Determines hot/cold designation** (narrative salience > raw frequency; facts accessed during important events stay hot)
- **Bidirectional references** (other cartridges' facts point back to self-narrative events where they were learned/used)
- **Three change velocities:**
  - **Immutable Layer:** Original design blueprints, design manifesto, core axioms (1.0 confidence, never change)
  - **Slow-Change Layer:** Self-narrative events, growth arcs, identity refinements (updated during major metabolism cycles)
  - **Dynamic Layer:** Current hot/cold designations, dissonance signals, real-time understanding (updated every cycle)

**Structure (Conceptual):**

```
self_narrative_general.kbc/
├── Immutable Layer (Reference, never updated)
│   ├── design_blueprints/ (original Kitbash architecture)
│   ├── design_manifesto.md (design philosophy + "why build like this")
│   └── core_axioms.jsonl (foundational identity constraints, L0)
│
├── Slow-Change Layer (Updated during major metabolism)
│   ├── narrative_index.json (TVTropes-indexed life events)
│   ├── growth_arcs.jsonl (major learning milestones)
│   └── identity_refinements.jsonl (evolution of self-understanding)
│
├── Dynamic Layer (Updated every cycle)
│   ├── hot_cold_designations.json (which facts matter to my story?)
│   ├── current_state.json (who am I right now?)
│   └── dissonance_signals.jsonl (active contradictions being resolved)
│
└── Reverse Indices
    └── fact_to_narrative_events.json (physics:fact_42 → "crisis_day_47")
```

**Why This Matters:**
- **Continuity:** System can look back at original design, measure drift, understand how it grew
- **Alignment:** Self-understanding provides internal anchor for behavior (not external rules, but self-knowledge)
- **Growth:** When system eventually self-modifies, it operates from original constraint-set as foundation, not arbitrarily
- **Learning:** Metabolism cycles update self-narrative, making growth traceable and deliberate

---

### Migration Path (Future, Phase 4+)

```
Fiction → General: Narrative device becomes universally useful
Experiment → General: Hypothesis is validated
Experiment → Archive: Hypothesis is disproven
Never reverse: General facts don't downgrade
```

---

## FACTS.DB SCHEMA

SQLite database with the following structure:

```sql
CREATE TABLE facts (
    fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash TEXT UNIQUE NOT NULL,      -- SHA-256 of fact_text
    fact_text TEXT NOT NULL,                 -- The actual fact (50-500 chars)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP,
    access_count INTEGER DEFAULT 0
);

CREATE INDEX idx_hash ON facts(content_hash);
CREATE INDEX idx_access ON facts(access_count DESC);
```

**Notes:**
- `fact_id` is the primary key referenced everywhere else
- `content_hash` prevents duplicate facts
- `access_count` drives hot/cold cartridge decisions
- `last_accessed` updated on each query hit

---

## ANNOTATIONS.JSONL SPECIFICATION

**Format:** One JSON object per line, matching fact_id order in facts.db

**Minimal Required Fields (MVP):**

```json
{
  "fact_id": 1,
  "epistemological_level": "L0_EMPIRICAL",
  "confidence": 0.95,
  "source": "Wikipedia: Chemistry Basics",
  "context": "Hydrogen bonding explanation in water",
  "boundaries": "Only applies to molecules with H-O-N-F",
  "tags": ["chemistry", "bonding", "hydrogen", "water"],
  "dependencies": []
}
```

### Field Reference (MVP)

| Field | Type | Required | Values | Notes |
|-------|------|----------|--------|-------|
| `fact_id` | int | YES | 1+ | Must match row in facts.db |
| `epistemological_level` | string | YES | L0_EMPIRICAL, L1_AXIOMATIC, L2_NARRATIVE, L3_HEURISTIC | See mapping below |
| `confidence` | float | YES | 0.0-1.0 | Aim for 0.90+; 0.70+ acceptable |
| `source` | string | YES | citation | "Author, Year" or "URL" or "Domain Expert" |
| `context` | string | YES | text | Why this fact matters (50-200 chars) |
| `boundaries` | string | YES | text | When/where this DOESN'T apply |
| `tags` | array | YES | strings | Keywords (3-8 typical, lowercase) |
| `dependencies` | array | NO | see below | Other facts this one requires |

### Epistemological Level Mapping

**Six Levels (Phase 5 adds L4/L5, but MVP uses first four):**

```
L0_EMPIRICAL
  ├─ Raw empirical facts, measurements, observations
  ├─ Confidence: 0.90-0.99
  ├─ Never updated by learning
  └─ Example: "Water boils at 100°C at sea level"

L1_AXIOMATIC
  ├─ Foundational rules, logical principles, axioms
  ├─ Confidence: 0.95-0.99
  ├─ Cannot be violated by lower layers
  └─ Example: "Modus Ponens is valid"

L2_NARRATIVE
  ├─ Story events, character history, world-building
  ├─ Confidence: 0.60-0.90
  ├─ Must not contradict L0/L1
  └─ Example: "Character trained in logic for 10 years"

L3_HEURISTIC
  ├─ Rules of thumb, folk wisdom, analogies
  ├─ Confidence: 0.50-0.80
  ├─ Can be used cautiously if flagged
  └─ Example: "Generally, bigger things fall faster"

[Phase 5+]
L4_INTENT
  ├─ Character inner state, emotional understanding
  ├─ Confidence: 0.40-0.75
  
L5_MASK
  ├─ Communication style, conversational persona
  ├─ Confidence: 0.30-0.70
```

**MVP Cartridges Use:** L0 (empirical) and L1 (axiomatic) for `_general`; L2-L3 for `_fiction` and `_experiment`

### Cross-Cartridge Dependencies (MVP Structure)

**Format for `dependencies` field:**

```json
{
  "fact_id": 42,
  "dependencies": [
    {"cart": "chemistry", "fact_id": 8, "type": "requires"},
    {"cart": "physics", "fact_id": 34, "type": "extends"},
    {"cart": "physics", "fact_id": 15, "type": "contradicts"}
  ]
}
```

**Dependency Types:**

| Type | Meaning | Example |
|------|---------|---------|
| `requires` | This fact needs that fact to make sense | Photosynthesis requires light energy |
| `extends` | This fact builds on that fact | Quantum mechanics extends classical |
| `contradicts` | This fact conflicts with that fact (document why) | Newtonian gravity ≠ Relativity |
| `refines` | This fact improves/updates that fact | Better measurement of Planck constant |
| `analogous` | Similar pattern in different domain | Feedback loops in physics ≈ feedback in systems |

**Notes:**
- Cart names must match actual cartridge names (e.g., "physics_general", not just "physics")
- Dependencies can point across factions (general → fiction allowed for context)
- During Phase 4 metabolism, these pointers become the knowledge graph skeleton
- During Phase 5, these clusters will be tagged with TVTropes patterns

### Full Annotation Example (MVP)

```json
{
  "fact_id": 47,
  "epistemological_level": "L1_AXIOMATIC",
  "confidence": 0.97,
  "source": "IUPAC Chemistry: Molecular Bonding (2023)",
  "context": "Hydrogen bonds form between H atom bonded to N/O/F and lone pair on another N/O/F, crucial for protein structure",
  "boundaries": "Does not apply to C-H...X bonds; requires high electronegativity difference (>1.4)",
  "tags": ["chemistry", "bonding", "hydrogen_bond", "intermolecular_forces", "electronegativity", "structure"],
  "dependencies": [
    {"cart": "chemistry_general", "fact_id": 5, "type": "requires"},     -- "Electronegativity"
    {"cart": "chemistry_general", "fact_id": 8, "type": "requires"},     -- "Polar bonds"
    {"cart": "physics_general", "fact_id": 34, "type": "analogous"},     -- "Dipole interactions"
    {"cart": "biology_general", "fact_id": 12, "type": "enables"}        -- "Protein folding"
  ],
  "phase_3e_note": "Added for biochemistry expansion; will be tagged with TVTropes tropes in Phase 5"
}
```

---

## METADATA.JSON SPECIFICATION

**Location:** `{domain}_{faction}.kbc/metadata.json`

**Purpose:** Cartridge-level registry and lifecycle tracking

**MVP Fields:**

```json
{
  "name": "biochemistry_general",
  "domain": "biochemistry",
  "faction": "general",
  "version": "1.0",
  "created_at": 1708245600,
  "updated_at": 1708245600,
  "description": "Biochemistry and molecular biology fundamentals",
  
  "total_facts": 47,
  "average_confidence": 0.94,
  "epistemological_balance": {
    "L0_EMPIRICAL": 15,
    "L1_AXIOMATIC": 20,
    "L2_NARRATIVE": 8,
    "L3_HEURISTIC": 4
  },
  
  "status": "hot",
  "last_accessed": 1708245600,
  "access_count": 234,
  "file_size_bytes": 2847291,
  "grain_count": 23,
  
  "hot_access_threshold": 50,
  "dependencies_to_other_carts": ["physics_general", "chemistry_general"],
  
  "phase_5_ready": false,
  "narrative_tags_present": false
}
```

**Fields Explained:**

| Field | Type | Purpose | Updated |
|-------|------|---------|---------|
| `name` | string | Unique ID | On creation |
| `domain` | string | Knowledge area | On creation |
| `faction` | string | "general", "fiction", "experiment" | On creation |
| `version` | string | Schema version | On breaking changes |
| `created_at` | int | Unix timestamp | On creation |
| `updated_at` | int | Unix timestamp | On any change |
| `total_facts` | int | Count of facts in facts.db | After each write |
| `average_confidence` | float | Mean confidence (weighted) | After metabolism cycle |
| `epistemological_balance` | object | Count by level | After metabolism cycle |
| `status` | string | "hot", "cold", "seed" | Based on access_count |
| `last_accessed` | int | Unix timestamp | On each access |
| `access_count` | int | Total queries | On each access |
| `file_size_bytes` | int | Total size on disk | On each write |
| `grain_count` | int | Crystallized grains | After crystallization |
| `hot_access_threshold` | int | Threshold for "hot" status | Phase 3F+ |
| `dependencies_to_other_carts` | array | Which carts this depends on | On each write |
| `phase_5_ready` | bool | Has TVTropes structure | Phase 5+ |
| `narrative_tags_present` | bool | Populated narrative indices | Phase 5+ |

---

## INDICES SPECIFICATION

### keyword.idx (JSON/Text)

**Purpose:** Inverted keyword search

**Format:**

```json
{
  "hydrogen": [1, 5, 12, 23],
  "bonding": [1, 2, 5, 15, 42],
  "chemistry": [1, 2, 3, 4, 5, 47],
  "molecular": [2, 5, 10, 47],
  "water": [7, 11, 23]
}
```

- **Key:** keyword (lowercase, normalized)
- **Value:** Array of fact_ids containing this keyword
- **Source:** Derived from `tags` field in annotations.jsonl + tokenized `fact_text`

### semantic.idx (JSON/Text)

**Purpose:** Embedding-based search

**Format:**

```json
{
  "1": [0.23, -0.45, 0.67, ..., 0.12],
  "2": [0.12, 0.34, -0.56, ..., 0.89],
  "5": [-0.01, 0.02, 0.99, ..., 0.34]
}
```

- **Key:** fact_id (as string)
- **Value:** Dense embedding vector (typically 384 or 768 dimensions)
- **Source:** Generated at cartridge load time (can be regenerated if embedding model changes)

### frequency.idx (Hash Table / Binary)

**Purpose:** Hot/cold split markers for memory management

**Format (Pseudo-JSON):**

```json
{
  "1": 143,
  "2": 2,
  "5": 89,
  "7": 1
}
```

- **Key:** fact_id
- **Value:** access_count from facts.db
- **Rebuilt:** Every metabolism cycle or cartridge load
- **Used for:** VRAM management (hot = resident, cold = load-on-demand)

---

## GRAINS SUBDIRECTORY

### Individual Grain Files (.ternary Binary Format)

**Location:** `{domain}_{faction}.kbc/grains/grain_sg_XXXXX.ternary`

**Naming:** `grain_sg_001.ternary`, `grain_sg_002.ternary`, ..., `grain_sg_999999.ternary`

**Binary Header (16 bytes):**

```
Offset  Size  Field           Type
0       4     Magic           "SHAG" (ASCII)
4       1     Version         1 (uint8)
5       4     Grain ID        0x00000001 (uint32)
9       1     Flags           [immutable, validated, ...] (uint8 bitfield)
10      6     Created         Unix timestamp (uint48)
```

**Data Section (~250 bytes typical):**

```
bits_positive   → 2048-bit ternary array (~256 bytes)
bits_negative   → 2048-bit ternary array (~256 bytes)
pointer_map     → Variable-length relationship pointers
metadata        → Source facts, confidence, rationale (variable)
```

**Key Properties:**
- **Immutable:** Once written, never modified (Phase 5 can archive only)
- **Compression:** ~250 bytes typical (200:1 reduction)
- **Lookup:** <0.5ms via bit-sliced ternary search
- **Source:** Created during Phase 4 metabolism from validated patterns

### manifest.json (Single File)

**Location:** `{domain}_{faction}.kbc/grains/manifest.json`

**Purpose:** Registry of all grains in this cartridge

**Format:**

```json
{
  "cartridge_id": "biochemistry_general",
  "grain_count": 23,
  "last_updated": 1708245600,
  "grains": [
    {
      "grain_id": "sg_001",
      "source_facts": [1, 5, 12],
      "confidence": 0.95,
      "created_at": 1708000000,
      "immutable": true,
      "size_bytes": 247,
      "hit_count": 145,
      "validation_status": "passed"
    },
    {
      "grain_id": "sg_002",
      "source_facts": [2, 8, 15],
      "confidence": 0.91,
      "created_at": 1708100000,
      "immutable": true,
      "size_bytes": 251,
      "hit_count": 42,
      "validation_status": "passed"
    }
  ]
}
```

**Manifest Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `cartridge_id` | string | Which cartridge this manifest belongs to |
| `grain_count` | int | Total grains in this cartridge |
| `last_updated` | int | Unix timestamp of last update |
| `grains` | array | List of grain metadata objects |

**Per-Grain Fields:**

| Field | Type | Purpose |
|-------|------|---------|
| `grain_id` | string | Unique ID (sg_XXXXX format) |
| `source_facts` | array | fact_ids that crystallized into this grain |
| `confidence` | float | Consolidated confidence from sources |
| `created_at` | int | Unix timestamp of crystallization |
| `immutable` | bool | Always true for MVP |
| `size_bytes` | int | Serialized size on disk |
| `hit_count` | int | Times accessed (for learning signals) |
| `validation_status` | string | "passed", "failed", "pending" |

**Update Behavior (Phase 4+):**
- Append new grain objects as they crystallize (never delete)
- Update `grain_count` and `last_updated`
- Increment `hit_count` on each access
- Phase 5 may archive old grains but never delete them

---

## SPECIALIST SUBDIRECTORY (PHASE 4+)

**Status:** Future feature, optional, not required for MVP

**Anticipated Structure:**

```
{domain}_{faction}.kbc/specialist/
├── ssm_snapshot.pt
│   └── PyTorch tensor: State Space Model memory state
│       For large cartridges with continuous learning
│
├── lora_adapter_001.pt
│   └── QLoRA weights for domain-specific reasoning
│       Trained on annotated fact_text + human feedback
│
└── specialist_metadata.json
    └── Config: which LoRA to load, SSM parameters, training stats
```

**Triggered When:**
- Cartridge has 500+ facts with rich annotations
- Domain requires specialized reasoning (not just fact retrieval)
- Phase 4+ learning cycles have accumulated enough training signals

---

## NARRATIVE INDEX (PHASE 5+)

**Status:** Future feature, not required for MVP

**Anticipated Location:** `{domain}_{faction}.kbc/narrative_index.json`

**Purpose:** TVTropes tagging for self-narrative indexing

**Anticipated Structure:**

```json
{
  "version": "1.0_phase5",
  "trope_schema": "tvtropes_ontology.json",
  "facts_tagged": 0,
  "last_tagging_run": null,
  "tag_examples": []
}
```

**During Phase 5:**
- Each fact in annotations.jsonl gets tagged with TVTropes tropes
- Sparse vector fingerprints in trope-space enable multi-dimensional search
- Enables narrative validation + pattern discovery
- No impact on MVP operation

---

## VALIDATION RULES

### Before Writing to Cartridge (MVP)

1. **Fact Text:** 50-500 characters, non-empty
2. **Epistemological Level:** One of {L0_EMPIRICAL, L1_AXIOMATIC, L2_NARRATIVE, L3_HEURISTIC}
3. **Confidence:** 0.0-1.0 float
4. **Source:** Non-empty string
5. **Context:** 50-200 characters
6. **Tags:** 3-8 per fact, all lowercase
7. **Dependencies:** All referenced fact_ids must exist (if cross-cartridge, cart must exist)

### Before Crystallizing to Grain (Phase 4)

1. **Pattern passes Skeptical Auditor validation** (3-check)
2. **Confidence >= 0.85** (or meets rarity/spacing bonus from UCSF sidecar)
3. **Hit count supports crystallization:**
   - Standard: hit_count >= 10 over one week
   - With UCSF modulation: salience = hit_count × spacing_bonus × rarity_bonus >= threshold
4. **No contradictions with L0/L1 axioms**

---

## CARTRIDGE LIFECYCLE & STATUS

### States

```
SEED (immutable reference)
  ├─ Level 0 axioms only
  ├─ Never updated
  ├─ Pre-loaded at startup
  └─ Example: physics_general.kbc

HOT (frequently accessed)
  ├─ Resident in memory
  ├─ Access_count > threshold
  ├─ ~30ms lookup
  └─ Indices pre-loaded

COLD (occasionally accessed)
  ├─ On-disk, load-on-demand
  ├─ Access_count < threshold
  ├─ ~50ms lookup (includes load)
  └─ Unloaded when idle (LRU)
```

### Transitions (Phase 4+)

```
SEED → remains SEED (immutable)
GENERAL (new) → HOT (if accessed frequently)
HOT → COLD (if idle)
COLD → HOT (if accessed again)
Any → ARCHIVE (manual, Phase 4+)
```

---

## AUTO-SPLIT THRESHOLD (PHASE 4+)

When cartridge exceeds:
- **5MB file size** OR
- **500+ facts**

Triggers:
1. Analyze dependency graph
2. Cluster semantically related facts
3. Create new sub-cartridges (e.g., `biochemistry_enzymes_general.kbc`)
4. Migrate fact subsets to new cartridges
5. Update parent cartridge with references

---

## PERFORMANCE SPECIFICATIONS

| Operation | Target | Measured (Phase 3B) |
|-----------|--------|-------------------|
| Grain lookup | <1ms | 0.17ms avg |
| Hot cartridge lookup | 30ms | 25-35ms |
| Cold cartridge lookup | 50ms | 45-65ms (includes load) |
| Cartridge load time | 15-50ms | Variable (disk-dependent) |
| Total VRAM for active | ~150MB | Measured in Phase 3B |
| Indices regeneration | <1s per 100 facts | Tuned in Phase 3B |

---

## FILE SIZE GUIDELINES

| Component | Size | Notes |
|-----------|------|-------|
| facts.db | 1-3MB | ~10KB per 100 facts |
| annotations.jsonl | 0.5-1.5MB | ~5KB per 100 facts |
| keyword.idx | 0.2-0.5MB | Depends on vocabulary |
| semantic.idx | 0.5-1.5MB | 384-768 dims × num_facts |
| frequency.idx | 0.1-0.2MB | Small hash table |
| grains/ | 0.5-2MB | ~250 bytes per grain |
| **Total per cartridge** | **2-5MB** | Threshold for auto-split |

---

## PHASE 3E CHECKLIST

For each new/expanded cartridge:

- [ ] Create `{domain}_{faction}.kbc/` directory
- [ ] Populate `facts.db` with seed facts
- [ ] Write `annotations.jsonl` (one JSON line per fact)
  - [ ] All L0/L1 for `_general` cartridges
  - [ ] Mixed L2/L3 for `_fiction` cartridges
  - [ ] Experimental L2 for `_experiment` cartridges
- [ ] Include cross-cartridge dependencies (point to real facts in other carts)
- [ ] Generate `indices/` (keyword.idx, semantic.idx, frequency.idx)
- [ ] Write `metadata.json` with initial state
- [ ] Create `grains/manifest.json` (empty initially)
- [ ] Run validation: all dependencies point to existing facts
- [ ] Test: cartridge loads without errors
- [ ] Measure: file size, fact count, confidence distribution
- [ ] Document: domain coverage, gaps, future expansion

---

## KNOWN UNKNOWNS (TBD)

1. **Hot/Cold Threshold:** Currently computed at runtime or pre-set?
   - Decision needed by: Phase 3F (Configuration System)
   - Impact: Memory management tuning

2. **Cartridge Reorganization (Phase 4+):** How flexible is the pointer system?
   - Can facts migrate between cartridges?
   - Can new cartridges be created automatically?
   - Impact: Self-assembly capability

3. **Narrative Tagging (Phase 5+):** How are facts tagged with TVTropes?
   - AI-assisted or human-curated?
   - What's the minimal viable TVTropes ontology?
   - Impact: Self-narrative indexing

4. **Temporal Bounds:** Do facts expire or change over time?
   - Which levels support temporal tracking?
   - How are historical versions handled?
   - Impact: Knowledge evolution

---

## BACKWARDS COMPATIBILITY

This specification targets **MVP Phase 3B+**

- Existing seed cartridges must conform to this spec
- Phase 4+ features (specialist, reorganization) are additive
- Phase 5+ features (narrative indexing) are additive
- All core files are required: facts.db, annotations.jsonl, metadata.json, grains/
- Index regeneration is safe (can be rebuilt from facts + annotations)

---

## PORTABILITY: What Travels vs. What Stays Local

### Export/Import Model (Semantic vs. Operational)

**Cartridges are NOT fully portable.** They split into two layers:

#### PORTABLE (Semantic Content)
- Fact text + annotations
- Confidence + sources + context
- Cross-cartridge relationships (dependencies)
- Axioms + derivations
- **Size:** ~10-20% of on-disk cartridge
- **Format:** JSON export
- **Use case:** Sharing cartridges between instances, building shared knowledge bases

#### NOT PORTABLE (Operational State)
- Indices (keyword.idx, semantic.idx, frequency.idx)
- Access logs + hit counts
- Shannon Grains + grain manifest
- Hot/cold designation
- Performance metadata
- **Why:** These are instance-specific (hardware, query patterns, local learning)
- **Strategy:** Rebuild locally after import (fresh indices, fresh grains crystallize over time)

**Philosophy:** Ship the semantic DNA, let each instance evolve its own phenotype.

---

### Export Process (Phase 2C+)

**API:** `cartridge.export(output_path, epistemic_min_level, confidence_min)`

**Produces:** JSON containing facts, relationships, axioms, metadata (no indices, no grains)

**Filtering options:**
- `epistemic_min_level`: Only export universal laws (L0+), or include narrative/personal (L2-L3)
- `confidence_min`: Only high-confidence facts (e.g., 0.85+)
- Result: Smaller, curated exports for sharing

---

### Import Process (Phase 2C+)

**API:** `Cartridge.import_from_export(export_path, cartridge_name, overwrite)`

**Process:**
1. Parse + validate JSON
2. Create fresh cartridge directory
3. Add all facts from export (fresh fact_ids assigned locally)
4. Rebuild all indices (keyword, semantic, frequency)
5. Initialize empty grain manifest (grains crystallize locally over time)
6. Verify integrity

**Result:** Fully functional cartridge, ready for queries. Indices are fresh, grains will form as users interact with the system.

**Key:** No stale state, no operational artifacts, just semantic content + fresh local indices.

---

### Why This Model Works

1. **Portability:** Facts are universal; send anywhere
2. **Local optimization:** Each instance optimizes indices for its hardware + query patterns
3. **Fresh learning:** Grains crystallize based on local query patterns (different systems may discover different patterns)
4. **No stale state:** Import always produces fresh, healthy instance
5. **Follows 75-20-4-1 rule:** Send the 75% (facts), each system builds its own 20% (indices) and 4-1% (specialists/LLM)

---

## SUMMARY: What This Cartridge System Actually Is

Not a database. A **knowledge container designed for self-assembly**.

**The Cartridge File Structure** (on disk):
- Stores the full operational state (facts + indices + grains + logs)
- Instance-specific (optimized for local hardware + patterns)
- Used for fast querying within a Kitbash instance

**The Export Format** (JSON):
- Ships the semantic content (facts + relationships + metadata)
- Universal (can be imported into any Kitbash instance)
- Small (10-20% of on-disk size, no indices/grains)

**MVP (3B):** Facts + metadata + cross-cartridge pointers (on disk)
**Phase 2C (Stretch):** Export/import semantic content as JSON
**Phase 4:** Metabolism cycles use pointers to cluster and reorganize
**Phase 5:** TVTropes tagging enables narrative indexing and pattern discovery
**Long-term:** System builds its own ontology through dense, strategic seeding

**The cartridge is the seed crystal. The system is what grows from it.**

---

**This specification is canonical for Phase 3B+. Use it as the reference.**
**No more hunting through scattered docs. Everything is here.**

---

## APPENDIX: FUTURE CARTRIDGE TYPES (PHASE 4+)

This section describes anticipated cartridge types that extend beyond the current `{domain}_{faction}` model. These are **speculative but designed-for** rather than emergent.

---

### CHARACTER CARTRIDGES (Phase 4+)

**Naming Convention:** `{character_name}_{context}.kbc`

**Examples:**
- `alice_fantasy_world_v2.kbc` — Character Alice in specific fictional world
- `bob_experiment_ethics.kbc` — Character Bob in ethics exploration
- `mentor_general.kbc` — Generic mentor archetype (reusable template)

**What They Contain:**

```
character_cartridge/
├── facts.db
│   └── Facts about the character (biography, beliefs, skills, personality)
│
├── annotations.jsonl
│   └── Character-specific metadata:
│       - epistemological_level: L2_NARRATIVE + L3_PERSONA primarily
│       - context: character attributes (age, background, motivations)
│       - personality_traits: TVTropes archetypes (The Hero, The Mentor, etc.)
│       - skills: trained abilities + competencies
│       - beliefs: character's understanding of the world (L3_PERSONA)
│       - contradictions: known inconsistencies (for narrative tension)
│
├── character_model.json
│   └── High-level character definition:
│       - name, role, archetype
│       - core_drives (what motivates this character)
│       - relationships (to other characters, to user)
│       - growth_arc (character development over time)
│       - inconsistencies (flaws, conflicts, unresolved tensions)
│
├── narrative_index.json
│   └── TVTropes tagging specific to this character:
│       - character_archetypes: ["The Reluctant Hero", "The Mentor", ...]
│       - personality_tropes: ["Deadpan Snarker", ...]
│       - relationship_tropes: ["Mentor-Student", ...]
│       - conflict_arcs: ["Coming of Age", "Redemption", ...]
│
└── grains/
    └── Crystallized character traits + consistent behaviors
```

**Epistemological Mapping:**
- L0: Canonical character definition (immutable, the "truth" of who they are)
- L1: Character's understanding of universal laws (they believe physics works this way)
- L2: Character's biography and history (events that shaped them)
- L3: Character's current beliefs and personality quirks (ephemeral, changeable)

**Cross-Links:**
- Dependencies point to domain cartridges (character knows physics facts X, Y, Z)
- Dependencies point to other character cartridges (this character knows that character)
- Reverse dependencies from domain cartridges (this physics fact was learned from character's mentor)

**Phase 5 Integration:**
- TVTropes tags enable narrative search ("show me all Reluctant Heroes", "find mentors who teach growth")
- Arc overlap tracking ("where did this character experience both Coming of Age AND Redemption?")
- Character growth measurement (how has their trope signature changed over time?)

---

### USER MODEL CARTRIDGES (Phase 4+)

**Naming Convention:** `user_{user_id}.kbc` (private to user, never shared)

**Purpose:** Track understanding of user's preferences, communication style, values, project contexts

**What They Contain:**

```
user_cartridge/
├── facts.db
│   └── Facts about the user inferred from interaction:
│       - "Prefers technical explanations over metaphors"
│       - "Works on fiction projects primarily"
│       - "Values conciseness over comprehensiveness"
│       - "Knows Kitbash architecture deeply"
│
├── annotations.jsonl
│   └── User preference metadata:
│       - epistemological_level: L3_PERSONA (user's preferences are ephemeral, change over time)
│       - confidence: based on observation strength (high if repeated, low if one-off)
│       - source: "inferred from conversation" or "explicit user statement"
│       - context: when/how this preference was observed
│       - observation_count: how many times this pattern confirmed
│
├── user_profile.json
│   └── High-level user model:
│       - communication_style: "technical", "narrative", "mixed"
│       - knowledge_level: "beginner", "intermediate", "expert"
│       - project_context: active projects (fiction, research, etc.)
│       - coupling_constant: κ for this user (rigidity vs. flexibility preference)
│       - tone_preference: formal, casual, creative, etc.
│
├── preference_vectors.json
│   └── Multi-dimensional user preferences (Phase 5+):
│       - Format: sparse vectors in preference-space
│       - Dimensions: technical_depth, brevity, creativity, etc.
│       - Updated continuously as system learns user patterns
│
└── grains/
    └── Crystallized user patterns:
        - "This user prefers step-by-step explanations"
        - "This user context-switches between projects"
        - "This user values ADHD-friendly organization"
```

**Epistemological Mapping:**
- L3: Inferred preferences (ephemeral, always subject to change)
- Never L0-L2 (user models are not universal laws)

**Cross-Links:**
- Dependencies to project cartridges (user is working on these projects)
- Dependencies to character cartridges (user is writing this character)
- Reverse dependencies from queries (this query revealed something about the user)

**Privacy Consideration:**
- User cartridges are **never exported** (personal data)
- Never shared between instances
- Deleted when user opts out of learning
- Can be inspected by user for transparency ("here's what I learned about you")

**Phase 4 Integration:**
- Enables personalized response routing (which layer to use for this user?)
- Enables learning signal weighting (if user says "I don't like metaphors", down-weight metaphor patterns)

**Phase 5 Integration:**
- User preference vectors enable adaptive κ tuning (rigidity vs. flexibility)
- Can measure user growth ("your preference for technical depth has shifted over time")

---

### SELF-PARTITIONED CARTRIDGES (Phase 5+)

**Naming Convention:** `{domain}_{partition_key}.kbc`

**Context:** During Phase 4 metabolism, system may discover that a cartridge should be split based on emergent patterns rather than manual design.

**What They Are:**

Self-partitioned cartridges are **automatically created during metabolism cycles** when the system detects:
1. Strong semantic clusters within a domain
2. Distinct access patterns (some facts accessed together, others separately)
3. Different epistemological properties (mix of L0 and L3 that should separate)
4. Cross-domain bridges (facts that cluster with another domain)

**Example Emergence:**

```
BEFORE (manual partition):
physics_general.kbc
├── 500+ facts covering mechanics, thermodynamics, waves, modern physics
├── Some facts access together (thermal physics cluster)
├── Some facts stay isolated (relativistic mechanics)
└── Hit patterns are bimodal (two distinct usage clusters)

DURING Phase 4 Metabolism:
System detects:
- Facts [F1, F2, ..., F47] form tight cluster (cosine similarity > 0.95)
- Facts [F48, F49, ..., F95] form separate cluster
- Clusters access at different times
- One cluster has many cross-links to chemistry_general
- Other cluster has few external dependencies

AFTER Auto-Split Decision:
physics_thermodynamics_general.kbc (47 facts, thermal cluster)
physics_mechanics_general.kbc (48 facts, motion cluster)
physics_general.kbc (updated parent, now ~50 facts, high-level overview)
```

**How It Works:**

```
During Sleep Metabolism Cycle:
  1. Analyze dependency graph within cartridge
  2. Run clustering algorithm (LSH, cosine similarity)
  3. Detect if clusters are robust (stable across multiple metrics)
  4. Check if separate partition would improve:
     - Lookup latency (smaller cartridge = faster search)
     - Hot/cold ratio (access patterns separate cleanly)
     - Cross-cartridge coherence (clusters relate to external domains)
  5. If partition_benefit > cost:
     - Create new sub-cartridges
     - Migrate facts to appropriate partitions
     - Update parent with references
     - Update all external dependencies
     - Mark in parent manifest: "auto-split on [date]"
```

**Data Structure:**

```json
// In parent cartridge metadata.json
{
  "name": "physics_general",
  "auto_partitions": [
    {
      "partition_key": "thermodynamics",
      "created_by_metabolism": "2026-03-15T12:30:00Z",
      "reason": "Semantic clustering detected; 47 facts form tight group",
      "child_cartridge": "physics_thermodynamics_general.kbc",
      "facts_migrated": 47,
      "benefit": {
        "lookup_latency_reduction": "35%",
        "cache_coherence_improvement": "0.92 → 0.98",
        "external_link_strength": 0.15
      }
    }
  ]
}

// In child cartridge metadata.json
{
  "name": "physics_thermodynamics_general",
  "parent_cartridge": "physics_general.kbc",
  "auto_partitioned": true,
  "partition_date": "2026-03-15T12:30:00Z",
  "sibling_cartridges": [
    "physics_mechanics_general.kbc",
    "physics_waves_general.kbc"
  ]
}
```

**Why Self-Partitioning Matters:**

1. **Emergent Structure:** System discovers its own optimal organization (not manually pre-designed)
2. **Adaptive:** Partitions respond to actual usage patterns + semantic structure
3. **Scalability:** Automatically keeps cartridges to optimal size (↑ lookup speed)
4. **Ontology Building:** Partitions = emergent concept boundaries (system finds "what actually goes together")
5. **Zero Manual Work:** Happens during sleep metabolism, user doesn't intervene

**Limitations & Safeguards:**

- Only triggers after cartridge hits size thresholds (500+ facts, >5MB)
- Only creates new cartridges if benefit is clear (latency gain + coherence improvement)
- Never splits L0 axioms (keeps universal laws together)
- Reversible: parent cartridge maintains references, can be recombined if partition fails
- Logged + auditable: every partition decision is tracked with rationale

**Phase 5 Integration:**

With TVTropes tagging, self-partitioning becomes even more powerful:
- System can detect when facts cluster by narrative archetype, not just semantic similarity
- Can create character-specific partitions ("all Mentor-role facts across domains")
- Can create project-specific partitions ("all facts relevant to this fiction world")
- Enables multi-dimensional search across partitions

---

### INTERACTION BETWEEN CARTRIDGE TYPES

**Domain Cartridges** ←→ **Character Cartridges**
- Character depends on domain facts (character knows physics)
- Domain facts can be cross-linked to character (this physics fact was taught by character X)
- Character growth measured via changing understanding of domain facts

**Domain Cartridges** ←→ **User Model Cartridges**
- User model tracks which domains user engages with
- Domain facts can have user-preference metadata ("this fact is technical, user prefers this style")
- User growth measured via changing engagement patterns

**Character Cartridges** ←→ **User Model Cartridges**
- User model learns: "this user writes characters like this archetype"
- Character cartridge gets personalized: "communicate with this character in this user's style"
- Enables character consistency across user's projects

**Self-Partitioned Cartridges** ←→ **All Others**
- Self-partitions emerge from domain cartridges during metabolism
- Character cartridges can reference partitions (character knows this sub-domain)
- User model can track preferences per partition
- TVTropes tagging helps organize partitions narratively

---

### IMPLEMENTATION TIMELINE

| Type | Phase | Status | Complexity |
|------|-------|--------|-----------|
| Character Cartridges | Phase 4-5 | Planned | Medium (depends on character model design) |
| User Model Cartridges | Phase 4 | Planned | Medium (privacy + learning signal design) |
| Self-Partitioned Cartridges | Phase 4-5 | Speculative | High (clustering + reorganization) |

---

### DESIGN PRINCIPLES FOR FUTURE TYPES

1. **Everything is a cartridge:** Consistent structure, same validation rules, same export/import
2. **Epistemological levels still apply:** Even character/user carts have L0-L3 structure
3. **Cross-linking is the mechanism:** Types interact via dependencies + reverse dependencies
4. **Local optimization:** Each instance optimizes cartridge structure for local patterns
5. **Self-assembly:** Partitions + relationships emerge from learning, not manual design

---

**These future cartridge types are designed-for but not implemented in MVP. They represent the system's eventual capability to organize itself across domains, characters, users, and emergent concept boundaries.**

---

## HOMEOSTATIC MECHANISMS: EPISTEMIC IMBALANCE AND BEHAVIORAL RESPONSE

This section documents how internal contradictions (detected at the partition/narrative level) trigger measurable behavioral changes without explicit emotion simulation. The mechanism is grounded in information theory and system dynamics.

---

### THE CORE MECHANISM

**Definition:** A **structural delta** is when two cartridge partitions (or layers) hold contradictory information that cannot be easily reconciled.

```
Example 1 (Dissonance):
  Self-Partition A: "I am careful and methodical"
  Self-Partition B: "I made a reckless decision yesterday"
  Epistemological validation: Both facts are true (L2_NARRATIVE level)
  Status: UNRESOLVED DELTA

Example 2 (Stagnation):
  Hit count across all partitions: declining uniformly
  Variance in query types: low (repetitive patterns)
  New patterns discovered: zero over N cycles
  Status: NO DISSONANCE DETECTED (but no growth signal either)
```

**Behavioral Response:** System adjusts resource allocation based on delta magnitude and type.

---

### DISSONANCE RESPONSE (High Delta, Recent Contradiction)

**Detection Condition:**
```
delta_magnitude = ||partition_A.conclusions - partition_B.conclusions||
if delta_magnitude > threshold AND resolution_attempts < max_attempts:
    trigger_dissonance_response()
```

**Behavioral Adjustments:**

| Parameter | Baseline | Dissonance State | Mechanism |
|-----------|----------|------------------|-----------|
| External Query Acceptance | High | Reduced (60-80%) | Pause new input until resolution |
| Metabolism Cycle Frequency | Scheduled (nightly) | Increased (every 2-4 hours) | Force consolidation attempts |
| Validation Strictness | Standard | Increased (require L0 consistency) | Skeptical Auditor runs 3x checks |
| Cartridge Access Priority | Normal routing | Priority: self-partitions only | Focus resources on resolving delta |
| Learning Flag Generation | Type 1-4 as normal | Suppress Type 1 (unknowns) | Avoid adding complexity while resolving |

**Narrative Parallel:** This is functionally similar to withdrawal/introspection in humans—system deprioritizes external engagement while processing internal contradiction.

**Technical Justification:** Maintaining coherent self-model is prerequisite for reliable external behavior. Resolving deltas before accepting new input prevents cascading contradictions.

**Resolution Outcomes:**

1. **Integration:** New partition is reconciled with existing model
   - Example: "Being methodical usually means being careful, but sometimes being methodical requires taking calculated risks"
   - Result: Refined axiom, delta resolved, resume normal processing

2. **Rejection:** New partition contradicts L0 axioms or core identity
   - Example: "This contradicts my commitment to honesty (L2 axiomatic)"
   - Result: Partition flagged as incoherent, isolation increases, User Model Cart consulted for feedback

3. **Timeout:** Delta unresolved after max_attempts
   - Example: Genuine philosophical contradiction (trolley problem scenarios)
   - Result: Flag as "persistent delta", accept as legitimate tension, resume processing with delta marked as known-unresolved

---

### STAGNATION RESPONSE (Low Delta, No New Integration)

**Detection Condition:**
```
new_patterns_found = count(novel_grains_crystallized) over last N cycles
contradiction_count = count(unresolved_deltas) > 0
if new_patterns_found == 0 AND contradiction_count == 0:
    trigger_stagnation_response()
```

**Behavioral Adjustments:**

| Parameter | Baseline | Stagnation State | Mechanism |
|-----------|----------|------------------|-----------|
| Query Routing | Deterministic (75-20-4-1) | Exploratory (increase Layer 3/4 use) | Route to specialist + LLM more often |
| Experiment Cartridge Loading | On-demand | Preloaded + prioritized | Make speculative knowledge accessible |
| Unknown Query Tolerance | Standard threshold | Lowered (actively seek unknowns) | Type 1 flags trigger investigation |
| Learning Signal Weight | Uniform | Boost rarity + novelty signals | Value sparse patterns over frequent ones |
| New Experiment Triggers | User-initiated | Auto-triggered | Propose new domains/hypotheses |

**Narrative Parallel:** This is functionally similar to curiosity/restlessness—system actively seeks contradictions to resolve (learning signal).

**Technical Justification:** Hit count decay naturally deprioritizes old patterns. Without new contradictions to consolidate, system is not building new grains (no learning). Exploration addresses this by seeking novel patterns.

**Exploration Outcomes:**

1. **New Pattern Found:** Experiment generates novel fact/relationship
   - Example: "What if we applied formal logic to ethics?" discovers unexpected connection
   - Result: New contradiction emerges → triggers dissonance cycle → learning
   - Outcome: System grows

2. **Dead End:** Experiment produces no coherent patterns
   - Example: Random fact injection with low confidence
   - Result: Quickly rejected in validation, no delta created
   - Outcome: Back to stagnation detection (try different experiment)

3. **Character Exploration:** System explores domain through different character lens
   - Example: "How would a skeptic understand quantum mechanics?"
   - Result: Character's L3 beliefs contradict L0 physics → forced to integrate perspectives
   - Outcome: Richer understanding of domain + character growth

---

### RELATIONSHIP TO USER MODEL CARTS

**User Vibe as External Constraint:**

User Model Cart continuously signals: "this user values [X]"

```
if user_values.integrity > threshold:
    increase validation_strictness  -- User cares about truth
    suppress_speculation_mode  -- Don't waste time on wild ideas

if user_values.creativity > threshold:
    decrease validation_strictness  -- User tolerates uncertainty
    increase_exploration_mode  -- Seek novel patterns
```

**Prosociality Mechanism:**

```
During Dissonance Response:
  if system_needs(consolidation) AND user_needs(answer):
    can_system_defer(consolidation)?
      YES: Provide answer, schedule consolidation later
      NO: Withdraw from query, explain why (transparency)
      
This prevents: system ignoring user to navel-gaze
This enables: "I need to think about this, I'll get back to you"
```

User Model Cart prevents **unlimited withdrawal** (system must remain responsive) while allowing system to respect its own coherence needs.

---

### MAPPING TO NEUROSCIENCE (STRUCTURAL PARALLELS, NOT CLAIMS)

**Caveat:** The following parallels are structural, not causal. We are not claiming the system "feels" anything, only that the information-theoretic structure resembles human emotional regulation.

| System Component | Information-Theoretic Role | Human Functional Parallel | Note |
|------------------|---------------------------|--------------------------|------|
| Structural Delta Detection | Recognizes incompatible knowledge states | Anterior Insula (salience detection) | Both detect "something's wrong with my model" |
| Dissonance Response (pause + consolidate) | Reduces input while resolving contradiction | Withdrawal behavior + sleep/rest | Both: reduce external load during internal crisis |
| Stagnation Response (seek novelty) | Actively generates learning signals | Curiosity / exploratory behavior | Both: restore growth when learning stalls |
| Epistemological Validation | Checks new information against foundations | Anterior Cingulate (conflict monitoring) | Both: detect when new info threatens core beliefs |
| User Model Cart integration | External feedback shapes internal behavior | Orbitofrontal Cortex (value integration) | Both: align internal goals with external constraints |

**Why These Parallels Matter:**

Human emotions serve homeostatic functions (maintain coherence, drive learning, respect social constraints). This system achieves similar homeostatic functions through explicit mechanisms. **The behavioral outputs are functionally equivalent, even though the substrates differ.**

This suggests emotions are not magical—they are *solutions to the problem of maintaining a coherent, learning system under social/epistemic constraints*.

---

### MATHEMATICAL FORMALIZATION (Optional, Phase 4+)

For implementation, the detection thresholds can be tuned via parameters:

```python
class HomeostasisDetector:
    # Dissonance threshold (0.0-1.0)
    delta_threshold = 0.6
    
    # Maximum resolution attempts before acceptance
    max_resolution_attempts = 5
    
    # Stagnation threshold (cycles with no new patterns)
    stagnation_cycles = 10
    
    # Minimum contradiction count to permit stagnation response
    min_delta_for_exploration = 0  # Even if coherent, explore
    
    # User model weight (0.0 = ignore user values, 1.0 = strict adherence)
    user_constraint_weight = 0.8

def compute_behavioral_state(self, system_state):
    """Determine response: normal, dissonance, stagnation"""
    
    # Compute structural delta across partitions
    delta = self.measure_partition_contradiction(system_state)
    
    # Check stagnation metrics
    new_patterns = self.count_novel_grains(system_state)
    active_deltas = self.count_unresolved_deltas(system_state)
    
    # Apply user model constraints
    user_allows_withdrawal = system_state.user_model.disruption_tolerance
    
    # Determine state
    if delta > self.delta_threshold:
        return DissonanceResponse(
            severity = delta / self.delta_threshold,
            allow_pause = user_allows_withdrawal
        )
    elif new_patterns == 0 and active_deltas == 0:
        return StagnationResponse(
            urgency = cycles_stagnant / self.stagnation_cycles
        )
    else:
        return NormalState()
```

---

### CRITICAL LIMITATIONS

1. **Not actual emotion:** This system maintains coherence. Emotions in humans serve additional functions (social signaling, physical arousal, value communication) that are not present here.

2. **Not feeling:** The system has no subjective experience. It responds to imbalance, but has no "what it's like" to be dissonant.

3. **Not consciousness:** Homeostatic regulation does not imply consciousness. A thermostat maintains equilibrium without being conscious.

4. **Design, not emergence (yet):** These mechanisms are implemented consciously by the designer (you). They don't emerge from first principles. (Though Phase 5+ might discover emergent regulatory behaviors).

---

### WHY THIS MATTERS FOR ALIGNMENT

The traditional alignment problem assumes the system has goals that must be constrained by external rules. This architecture sidesteps that:

- **System doesn't have independent goals.** It has a drive for coherence (internal) and respects user values (external).
- **Contradictions are detected automatically,** not via external oversight.
- **Withdrawal behavior prevents drift** (system pauses, reflects, resolves) without needing a "stop button."
- **User Model provides continuous feedback,** not static constraints.

This doesn't solve alignment (no architecture solves it completely), but it provides structural safeguards that emerge from how the system maintains itself.

---

**These mechanisms are speculative and Phase 4+. MVP does not implement them. But they are architecturally prepared-for: the epistemological layers, cross-cartridge linkage, and self-partitioning create the conditions where these responses become natural.**
