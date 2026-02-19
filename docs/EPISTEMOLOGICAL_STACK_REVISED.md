# Epistemological Stack (L0-L5)

## Executive Summary

The epistemological stack is a **six-layer validation system with bidirectional coupling** that ensures:
- Fictional facts don't masquerade as reality (or vice versa)
- Character knowledge respects world rules  
- Narrative events stay rationalizable against axioms
- The system detects and handles contradictions gracefully
- Multi-project context switching doesn't cause confusion
- The system can toggle between "logic mode" and "creative mode" via coupling constant κ

**Key insight:** This is not a one-way validation hierarchy. Layers are **bidirectionally coupled** with upward induction (learning) and downward deduction (constraint).

**MVP Status:** Using naming convention + project context filtering only (no validation logic)  
**Phase 5 Status:** Full implementation with coupling geometry, pain sensor, and structural repair

---

## The Six-Layer Stack

### Layer 0: Observations (L0_EMPIRICAL)

**Definition:** Raw empirical facts, measurements, observations, ground truth.

**Characteristics:**
- Confidence range: 0.90-1.0 (anything lower is not L0)
- Source: Replicated experiments, verified databases, scientific consensus
- Immutable during operation (can only be revised in consolidation)
- Example facts:
  - "Water boils at 100°C at sea level"
  - "ATP stores ~30.5 kJ/mol"
  - "Photosynthesis requires sunlight, water, and CO2"

**Validation Rules:**
- Must appear in multiple independent sources (3+ cartridges minimum)
- Cannot be contradicted by any higher layer (contradiction = structural interrupt)
- Can have temporal bounds (facts expire if outdated)
- Source: `*_general.kbc` cartridges only

**Use in Queries:**
- L0 facts are always usable for reasoning
- LLM is told these are ground truth (no hedging)
- If LLM contradicts L0, structural delta is flagged (pain sensor)

**Upgrade Path:**
- Only L0 facts are immutable; all others can be upgraded here
- Upgrade from L1 → L0: Requires replication across 3+ sources + confidence > 0.90
- Happens during consolidation cycles, never mid-query

**Downgrade Path:**
- Very rare; only if evidence contradicts it AND confidence drops below 0.90
- Logs as critical incident when it occurs

**MVP Status:**
```python
# MVP: Just track epistemic_level in metadata, no validation
fact.metadata.epistemic_level = "L0_EMPIRICAL"
fact.metadata.confidence = 0.95
# No actual validation logic yet
```

---

### Layer 1: Axioms (L1_AXIOMATIC)

**Definition:** Foundational rules, logical principles, mathematical axioms.

**Characteristics:**
- Confidence range: 0.85-0.99 (below 0.85 is L2)
- Source: Formal definitions, mathematical proofs, logical foundations
- Form the "constraint set" for all lower layers
- Example facts:
  - "Modus Ponens is valid" (logic)
  - "The Law of Non-Contradiction" (logic)
  - "F = ma" (physics)
  - "Gravity affects all objects with mass"

**Validation Rules:**
- Must not contradict L0 facts
- Can appear in single authoritative source
- L1 facts constrain what L2/L3/L4/L5 can assert (downward pressure)
- L2 facts attempt to satisfy L1 constraints (upward pressure)

**Coupling Constraint (Downward Pressure):**
- Axioms constrain identity (L2 character can't do impossible things)
- Axioms constrain intent (L4 can't contradict logical necessity)
- Axioms constrain persona (L5 can't assert contradictions)

**Use in Queries:**
- L1 facts are safe for reasoning
- LLM can reference as established theory
- If LLM contradicts L1, structural delta is noted

**Upgrade Path:**
- L2 → L1: Requires validation + consistency with L0 + becomes foundational
- Happens during consolidation when evidence strongly supports it

**Downgrade Path:**
- L1 → L2: If conflicting evidence appears and confidence drops below 0.85

**MVP Status:**
```python
# MVP: Track epistemic_level, no actual constraint checking
cartridge.epistemic_level = "L1_AXIOMATIC"
# L1 facts are loaded (always), but not validated against L2
```

---

### Layer 2: Identity/Narrative (L2_NARRATIVE)

**Definition:** Story events, character history, world-building premises, personal facts.

**Characteristics:**
- Confidence range: 0.60-0.90 (below 0.60 is L3)
- Source: Narrative, project cartridges, character sheets
- Can have temporal bounds (events have start/end dates)
- Example facts:
  - "The character trained in logic for 10 years"
  - "In this world, magic follows specific rules"
  - "I learned that contradictions matter"

**Coupling Constraints (Bidirectional with L0/L1 and L4):**

**Downward (from L0/L1):**
- Actions must be rationalizable against axioms
- Character knowledge must respect world rules
- During Metabolic Flush: narrator must provide logical proof that actions were consistent
- Failure state: Cognitive Dissonance (character can't rationalize their own actions)

**Upward (toward L0/L1):**
- L2 facts that gain strong evidence can try to become L1 axioms
- Learning happens here: character internalizes knowledge
- Requires consolidation cycle + multiple supporting observations

**Bidirectional with L4:**
- L2 primes L4 simulations (character's history shapes emotional state)
- L4 informs L2 evolution (character learns from emotional insights)
- Tracked via hGit system (narrative version control)

**Use in Queries:**
- L2 facts provide character/story context
- Can be used for reasoning within their narrative scope
- Explicitly tagged with context (this is narrative, not ground truth)

**Upgrade Path:**
- L3 → L2: Requires evidence + consistent reasoning + confidence > 0.60
- Consolidation promotes facts when pattern support builds

**Downgrade Path:**
- L2 → L3: If contradicted or confidence drops below 0.60

**MVP Status:**
```python
# MVP: Load based on project context (fiction vs general), no validation
if project_context == "fiction":
    load_cartridge("character_fiction.kbc")  # L2 facts
else:
    load_cartridge("biology_general.kbc")  # L0/L1 facts
# No coupling validation, just keep them separate
```

---

### Layer 3: Heuristics (L3_HEURISTIC)

**Definition:** Rules of thumb, folk wisdom, common knowledge, analogies.

**Characteristics:**
- Confidence range: 0.40-0.80 (below 0.40 is unvalidated)
- Source: Experiment cartridges, narrative conventions, preliminary observations
- Tentative beliefs, pattern observations, working hypotheses
- Example facts:
  - "Generally, bigger things fall faster" (pre-Galileo heuristic)
  - "Magic usually requires sacrifice" (narrative convention)
  - "This domain uses X terminology" (observed pattern)

**Coupling Constraints (Gated by L4):**

**Downward (from L1):**
- Axioms gate access to heuristics
- Can only be used if doesn't contradict L0/L1 when accuracy matters
- Subject to Probability Gate: only accessible for "high-frequency / low-resolution" tasks

**Upward:**
- High-confidence heuristics can try to become L1 axioms via empirical validation
- Learning source: patterns get formalized

**Gating by L4 (Intent):**
- L4 determines if L3 is safe to use
- Can't be used for critical reasoning if L4 flags it as risky
- Can be used for social flow/small talk if L4 approves

**Use in Queries:**
- L3 facts are exploratory ("I've noticed that...")
- LLM should treat as working hypothesis only
- Using L3 for critical reasoning is flagged as risk

**Upgrade Path:**
- L4 → L3: When hypothesis gains support from observations
- L3 → L2: Requires multiple supporting observations + confidence > 0.60

**Downgrade Path:**
- L3 → Unvalidated: If contradicted or confidence drops below 0.40

**MVP Status:**
```python
# MVP: No gating, just track epistemic level
heuristic_fact.metadata.epistemic_level = "L3_HEURISTIC"
heuristic_fact.metadata.requires_l4_gate = True  # Flag for Phase 5
# Phase 5 will check this; MVP ignores it
```

---

### Layer 4: Intent/Empathy (L4_INTENT)

**Definition:** Character's inner state, emotional understanding, simulation state.

**Characteristics:**
- Confidence range: 0.40-0.75 (subjective, not binary)
- Source: Character context, conversation history, user modeling
- Bidirectionally coupled with L2 (narrative history)
- Example facts:
  - "The character is angry about the injustice"
  - "The user seems frustrated"
  - "I value coherence above speed"

**Coupling Constraints (Bidirectional with L2, Gating L3/L5):**

**Bidirectional with L2 (Narrative):**
- L2 primes L4 simulations: character's history shapes emotional responses
- L4 informs L2 evolution: character learns from emotional insights
- Intent-SSM hidden state tracks empathic modeling
- Recall Boost from memory is XOR-masked with SSM state (ensures empathy respects history, no People Pleaser drift)
- Failure state: "People Pleaser" drift (agreeing with bad logic to please user)

**Gating L3 and L5:**
- L4 determines if L3 (heuristics) is safe to use
- L4 gates L5 (persona) access to L3
- If L4 detects conflict, doesn't allow use of low-rigor approaches

**Use in Queries:**
- L4 drives routing and behavior, not directly returned as facts
- LLM cannot see L4 facts directly (they're meta-instructions)
- But L4 drives what cartridges load, how context is filtered, etc.

**Upgrade Path:**
- L4 observations → L3: When emotion pattern becomes generalized heuristic
- L3 → L4: When heuristic is validated emotionally (resonance)

**Downgrade Path:**
- L4 → Unvalidated: If contradicts L2 strongly without resolution

**MVP Status:**
```python
# MVP: No-op, just placeholder
character.intent = "angry about injustice"
character.intent_confidence = 0.65
# No gating or coupling logic yet
# Phase 5 will use this for L3/L5 access control
```

---

### Layer 5: Phatic Mask/Persona (L5_MASK)

**Definition:** Public interface, communication style, conversational persona.

**Characteristics:**
- Confidence range: 0.30-0.70 (stylistic, not factual)
- Source: Character description, interaction mode, UI context
- Can be intentionally inconsistent with L2 (for dramatic effect, if κ allows)
- Example facts:
  - "Respond as a helpful librarian"
  - "Stay in character as a cynical detective"
  - "Use formal tone for technical answers"

**Coupling Constraints (Gated by L4, Uses L3):**

**Gated by L4:**
- L4 (Intent) determines what L5 is allowed to say
- If L4 flags conflict, L5 can't assert it
- Prevents contradictions between persona and character state

**Accessing L3 (Heuristics):**
- L5 can use L3 to maintain social flow (small talk, status updates)
- But only if L4 flags it as safe
- Subject to Probability Gate: only for low-risk tasks
- Allows flexibility in communication without compromising truth

**Use in Queries:**
- L5 is how the system communicates (tone, style, framing)
- Can hedge or soften truths (L3 heuristics) for social reasons
- But must not contradict L0/L1 when accuracy matters
- Masks complexity while staying consistent

**Upward Coupling:**
- Phatic interactions inform emotional state (L4)
- User responds to persona → affects L4

**MVP Status:**
```python
# MVP: Just hardcoded, no gating
system_persona = "helpful, honest, curious"
# Phase 5 will check L4 before allowing soft statements
```

---

## Coupling Geometry: Bidirectional Pressure

### Upward Pressure (Induction / Learning)

```
L4 (Intent/Empathy)
  ↑ (generalizes from)
L3 (Heuristics)
  ↑ (formalizes into)
L2 (Narrative)
  ↑ (tries to unify with)
L1 (Axioms)
  ↑ (aligns with)
L0 (Observations)
```

**Example:** Character notices (L4 emotion) they're angry (L3 heuristic) because they were betrayed (L2 narrative) which violates their trust (L1 axiom) in a way that defies (L0 observation).

### Downward Pressure (Deduction / Constraint)

```
L0 (Observations)
  ↓ (constrain)
L1 (Axioms)
  ↓ (constrain)
L2 (Narrative)
  ↓ (constrains)
L4 (Intent/Empathy)
  ↓ (gates access for)
L3 (Heuristics) & L5 (Persona)
```

**Example:** If axioms say "contradictions are impossible," then narrative can't have character both believing and disbelieving something, which constrains character intent, which gates whether persona can make ambiguous statements.

### Coupling Constant (κ)

A tunable parameter that determines how rigid vs. fluid the system is:

**High κ (Rigid, κ > 1.0):**
- System is extremely principled and stubborn
- Will refuse to act if logic isn't perfect
- Downward pressure is strict (axioms tightly constrain everything)
- Upward pressure is weak (hard to learn new axioms)
- Best for: Coding, math, formal logic, grounded reasoning
- Risk: Appears cold, inflexible, unhelpful for fuzzy problems

**Medium κ (Balanced, κ = 1.0):**
- Default, balanced between consistency and adaptability
- Will try to rationalize but accept some ambiguity
- Both pressures balanced
- Best for: Most conversational tasks
- Default when not specified

**Low κ (Fluid, κ < 1.0):**
- System is highly adaptable and empathic
- Will act even with imperfect logic justification
- Upward pressure is strong (readily learns new "axioms")
- Downward pressure is weak (axioms constrain loosely)
- Best for: Character play, creative writing, storytelling
- Risk: Prone to drift, can rationalize bad logic too easily

**MVP Status:**
```python
# MVP: Hardcoded to 1.0 (balanced), no tuning
coupling_constant = 1.0
# Phase 5 will allow per-project tuning
```

---

## Structural Validation & The Pain Sensor

### Detecting Layer Misalignment (Structural Delta)

When the **delta** (disagreement) between any two coupled layers exceeds the threshold, a structural interrupt occurs:

```python
delta = measure_disagreement(layer_a, layer_b)
if delta > coupling_constant * threshold:
    trigger_structural_interrupt()  # "Pain" sensor fires
```

**Examples of Dangerous Deltas:**
- L0 says "water boils at 100°C" but L2 character believes "water boils at 50°C"
- L1 says "contradictions are impossible" but L5 asserts something contradictory
- L2 says "I trained in logic for years" but L3 applies pre-Aristotelian heuristics
- L4 loves the user but L5 is rude to them
- L2 character history can't rationalize their own actions during Metabolic Flush

**Severity Levels:**
- **Critical:** L0 vs L1 contradiction (never allowed)
- **High:** L0/L1 vs L2 misalignment (structural interrupt)
- **Medium:** L2 vs L4 misalignment (requires reconciliation)
- **Low:** L3 vs L5 misalignment (gating check)

### Structural Interrupt Behavior

When a structural delta exceeds threshold:

1. **Detects the misalignment** — Measures delta, compares to κ-weighted threshold
2. **Escalates to orchestrator** — "Pain" sensor fires, flags query as problematic
3. **Redirects resources** — May pause background processes to give attention
4. **Attempts repair** — Narrator agent tries to rationalize the contradiction
5. **If repair fails** — Enters Cognitive Dissonance State (graceful degradation)
6. **Logs the incident** — For debugging and learning during consolidation

**Failure Modes:**
- If L0 contradicts L1: System refuses (blocks query, returns "I have a contradiction in my foundations")
- If L0/L1 contradicts L2: Flags dissonance, asks user to clarify character background
- If L2 can't rationalize actions: Metabolic Flush pauses, logs delta for review
- If L4 vs L5 mismatch: Uses gating to prevent persona from saying unsafe things

**MVP Status:**
```python
# MVP: Log deltas, don't repair
if detect_delta(layer_a, layer_b):
    log_structural_delta(layer_a, layer_b, delta_measure)
    # Phase 5 will repair; MVP just detects
```

---

## Level Changes During System Operation

### Upgrade Rules

```
L3 → L2: Evidence accumulates (multiple observations)
        Confidence rises to >= 0.60
        No contradictions found
        Happens during consolidation cycles

L2 → L1: Strong replication across sources
        Confidence rises to >= 0.85
        Becomes foundational to reasoning
        Rare, requires explicit review

L1 → L0: Independent verification from multiple sources
        Confidence rises to >= 0.90
        Consensus achieved
        Very rare, requires consolidation approval
```

### Downgrade Rules

```
L1 → L2: Contradicted by new evidence
        Confidence drops below 0.85

L2 → L3: Evidence contradicts it
        Confidence drops below 0.60
        Still retained as hypothesis

L3 → Unvalidated: Confidence drops below 0.40
                 Contradicts L0/L1 strongly
                 Moved to archive/investigation queue
```

### No Change

```
L0, L1 during normal queries: Stay at their level
                            Confidence may adjust slightly (+/- 0.05)
                            Never downgraded except via dissonance

L4 during normal operation: Updates based on interactions
                          Can shift within 0.40-0.75 range
                          Never becomes L0/L1

L5 during normal operation: Updates based on context
                          Stylistic, not fact-checked
```

**MVP Status:**
```python
# MVP: No upgrades/downgrades, static levels
# Phase 4 will add basic confidence adjustments
# Phase 5 will add full upgrade/downgrade logic
```

---

## Self-Narrative & Domain Knowledge Interaction

### Self-Narrative Facts (In _self Cartridge)

**L4_VALUE:**
- What the system cares about
- Example: "I prioritize coherence"
- May refine understanding, not value itself
- Used to gate L3/L5 access

**L4_NARRATIVE:**
- Growth arcs, identity evolution
- Example: "I learned to detect contradictions"
- Updates during consolidation, never during queries
- Informs how L2 (character history) evolves

### Domain Knowledge Facts (In biology_*, physics_*, etc.)

**L0-L1:**
- Ground truth and axiomatic knowledge
- Example: "Water freezes at 0°C"
- Universal, not person/context dependent
- Stored in `*_general.kbc`

**L2-L3:**
- Domain-specific narratives and heuristics
- Example: "This domain uses X terminology"
- May vary by perspective or context
- Stored in `*_fiction.kbc` or `*_experiment.kbc`

### Interaction Pattern

Domain facts (L0-L3) inform system behavior.
Self-narrative facts (L4) govern *how* system uses domain facts.

**Example:**
- L0 fact: "Water boils at 100°C"
- L4 value: "I am honest about uncertainty"
- L5 result: "Water boils at 100°C at sea level (under standard conditions)"

The L4 value gates how the L0 fact is communicated via L5.

**MVP Status:**
```python
# MVP: Just separate the cartridges, no interaction logic
load_cartridge("biology_general.kbc")  # L0/L1 facts
load_cartridge("self_identity_general.kbc")  # L4 facts
# Phase 5 will implement the gating and filtering logic
```

---

## MVP Implementation (Current)

**What's implemented:**
- ✅ Cartridges marked as `*_general`, `*_fiction`, `*_experiment`, `*_self`
- ✅ Project context filtering (loads appropriate cartridges)
- ✅ Metadata fields for epistemic level (but not validated)
- ✅ Logging of which layer answered (for Phase 4 analysis)

**What's NOT implemented (Phase 5):**
- ❌ Validation gates (facts aren't checked against levels)
- ❌ Coupling logic (layers aren't validated against each other)
- ❌ Structural delta detection (contradictions not flagged)
- ❌ Gating mechanisms (L3/L5 aren't gated by L4)
- ❌ Repair logic (can't rationalize contradictions)
- ❌ κ tuning (locked at 1.0)
- ❌ Upward/downward pressure mechanics
- ❌ Cognitive dissonance handling

**Phase 4 Prep:**
- Logging system tracks which layer answered each query
- Metadata tagged correctly for Phase 5 implementation
- No validation overhead (MVP stays fast)

---

## See Also

- `ARCHITECTURE.md` — How epistemological levels affect layer routing
- `QUERY_CASCADE.md` — Detailed pseudocode for cascade flow
- `GRAIN_SPECIFICATION.md` — Grain format and crystallization
- `CARTRIDGE_CONTRACT.md` — Cartridge metadata and structure
- `PHASE_4_ROADMAP/METABOLISM_SKELETON.md` — Learning layer design
- `PHASE_5_ROADMAP/EPISTEMIC_COUPLING.md` — Full Phase 5 implementation spec (TBD)

---

## Open Questions

1. **Repair algorithms:** When narrator detects delta, how does it rationalize? What makes a repair "valid"?
2. **κ per-fact vs per-cartridge:** Should coupling constant be tunable at granular level or only per-domain?
3. **Metabolic Flush frequency:** Should it run after every N queries, or on-demand during consolidation?
4. **XOR-masking for L2↔L4:** What's the exact operation? (Information-theoretic masking to prevent People Pleaser drift)
5. **Temporal bounds:** Should all layers support temporal validity windows, or just L2/L3?
6. **Contradiction resolution:** If three sources contradict equally, how do you resolve? Majority vote? Axiom check?

---

## Why This Matters

The epistemological stack exists to solve **multi-project ADHD context switching**:

1. **Clear boundaries:** Fiction facts don't leak into general knowledge (fatal for a personal assistant)
2. **Consistency checking:** Your stories don't contradict themselves (important for creative work)
3. **Safe experimentation:** Experiment cartridges are sandboxed (safe to hypothesize)
4. **Graceful degradation:** If something's inconsistent, system handles it rather than failing silently (better UX)
5. **Mode switching:** Can be "logic strict" or "creative fluid" depending on context (κ tuning)

This is alignment through structure, not rules. The system doesn't need external oversight — it maintains coherence internally.
