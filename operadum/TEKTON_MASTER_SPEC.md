# TEKTON / SYNTHESIS-I: The Master Spec

**A categorical *design* engine — the constructive mirror of KOMPOSOS-IV's interpretive engine.**

> KOMPOSOS interprets: it stores relations, verifies claims, factors existing structure.
> TEKTON constructs: it stores *operations*, generates valid assemblies, and synthesizes artifacts that satisfy a specification.
>
> Where KOMPOSOS's primitive is the **morphism** (relate two existing things),
> TEKTON's primitive is the **operation** (an n-input → m-output wiring rule) carried on an **operad/PROP**, enriched by **resources** (linear/monoidal), and emitting **constructions** (Curry–Howard artifacts).
>
> The two are duals at the bottom (both symmetric-monoidal-categorical) and compose: a TEKTON design **compiles into** a KOMPOSOS morphism graph.

---

## Table of Contents

1. [What This System Is](#1-what-this-system-is)
2. [The Primitive Inversion](#2-the-primitive-inversion)
3. [The Unified Architecture](#3-the-unified-architecture)
4. [Layer 1: Forge — The Plugin Framework](#4-layer-1-forge--the-plugin-framework)
5. [Layer 2: TEKTON — The Operadic Runtime](#5-layer-2-tekton--the-operadic-runtime)
6. [Layer 2.5: Polytope — Higher Operadic / Resource Reasoning](#6-layer-25-polytope)
7. [Layer 3: WRIGHT — The Synthesis Co-Processor](#7-layer-3-wright)
8. [Layer 4: DAEDALUS — Generative Search](#8-layer-4-daedalus)
9. [The Synthesis Strategies](#9-the-synthesis-strategies)
10. [The Dual Gate: Realizability + Resource Soundness](#10-the-dual-gate)
11. [Higher-Order DAEDALUS](#11-higher-order-daedalus)
12. [Formal Coherence Guarantee](#12-formal-coherence-guarantee)
13. [The Bridge to KOMPOSOS](#13-the-bridge-to-komposos)
14. [Mathematical Foundation — File Map](#14-mathematical-foundation--file-map)
15. [Data Flow Through the System](#15-data-flow)
16. [Mathematical Guarantees](#16-mathematical-guarantees)
17. [Directory Structure](#17-directory-structure)
18. [How to Add a Domain — One Line](#18-how-to-add-a-domain)
19. [Honest Limitations](#19-honest-limitations)
20. [Roadmap](#20-roadmap)

---

## 1. What This System Is

TEKTON/SYNTHESIS-I is a **design engine built on operad theory** — not inspired by it, built on it. Every reusable component is an **operation**. Every design is a **wiring of operations** (an operad composite). Every cost/budget is a **resource in a symmetric monoidal category**. Every "does this design satisfy the spec?" is a **realizability check**. Every "find me a better design" is **generative search over the space of valid composites**.

It is a **self-constructing computational organism** hosted by a hot-loadable plugin framework, that:

- **Stores components operadically** — typed operations with arities, composition laws, equivariance, and units.
- **Generates valid assemblies** — enumerates/searches well-typed wirings that satisfy a target interface.
- **Tracks resources linearly** — budgets, materials, capacities are *consumed*, not freely copied.
- **Synthesizes artifacts** — a successful design is an executable construction (Curry–Howard), not just a description.
- **Improves its own designs** — searches for cheaper/stronger composites achieving the same interface.
- **Compiles to KOMPOSOS** — emits a morphism graph that KOMPOSOS can then interpret and verify.

It is **not** a workflow-DAG builder. It is **not** a constraint solver with extra steps. It is **not** a code generator template engine. The operadic substrate is load-bearing: the composition laws are what make partial designs safe to assemble and search.

### The Inversion in One Table

| Concern | KOMPOSOS-IV (interpret) | TEKTON / SYNTHESIS-I (design) |
|---|---|---|
| Primitive | Morphism `A → B` | Operation `(A₁,…,Aₙ) → B` |
| Substrate | Enriched category | Coloured operad / PROP, symmetric monoidal |
| Verb | "are these related?" | "what wirings are valid / cheapest?" |
| Enrichment | Quantale confidence on hom-sets | Resource monoid on operations (cost/material/capacity) |
| Self-improvement | Factor `A→C` into `A→B→C` | Search composites achieving target interface |
| Truth notion | Verification (5-tier) | Realizability (does a construction exist?) |
| Output | A verdict | An executable artifact |
| Copyability | Cartesian (free copy/discard) | Substructural (resources are spent) |

---

## 2. The Primitive Inversion

KOMPOSOS can only reason about objects *by their existing relations* (this is literally Yoneda: `y(A) = Hom(-,A)`). That makes it interpretive by construction — there is no native verb for "bring a new object into being from a spec."

TEKTON's primitive operation `o : (A₁,…,Aₙ) → B` is generative: it is a *rule for building a `B` out of parts*. Operadic composition `o ∘ᵢ p` plugs the output of `p` into the i-th input of `o`, and the operad axioms (associativity, unitality, equivariance under input permutation) guarantee that any well-typed tree of plug-ins is itself a valid operation. **The space of valid designs is therefore the free operad on your component set, quotiented by your equations** — and search/synthesis is exploration of that space.

Three mathematical pillars, each replacing a KOMPOSOS pillar:

1. **Coloured operads / PROPs** replace enriched categories as the substrate. Colours = interface types. A PROP additionally gives you many-out (m outputs), which you want for designs that fork/share.
2. **Symmetric monoidal + substructural enrichment** replaces the quantale. The tensor `⊗` models "having two things at once"; making it *non-cartesian* (no diagonal `A → A⊗A`) is what models resource consumption — the single most important difference from KOMPOSOS, which is cartesian and so treats knowledge as infinitely copyable.
3. **Constructive type theory (Curry–Howard)** replaces verification with realizability. A design that type-checks *is* a program; "the spec is satisfiable" is witnessed by an actual construction rather than a proof-about-a-graph.

---

## 3. The Unified Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  FORGE (src/forge_core/)                                             │
│  The Plugin Framework — outer shell (event bus, hooks, registry, DI) │
│  Mirrors Orion. Knows nothing about operads.                         │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  TEKTON / SYNTHESIS-I (tekton/)                                  │ │
│  │                                                                  │ │
│  │  ┌────────────────────────────────────────────────────────────┐│ │
│  │  │ Layer 2: Operad Runtime (tekton/core/)                     ││ │
│  │  │   One class — Operad — does four jobs:                     ││ │
│  │  │     1. Operadic structure (colours, operations, ∘ᵢ, units) ││ │
│  │  │     2. Persistence (SQLite, owned by Operad)               ││ │
│  │  │     3. Resource enrichment (symmetric-monoidal cost algebra)││ │
│  │  │     4. Execution (operations carry callables; composites run)││ │
│  │  └───────────────────────────┬────────────────────────────────┘│ │
│  │  ┌───────────────────────────▼────────────────────────────────┐│ │
│  │  │ Layer 2.5: Polytope (tekton/core/polytope.py)              ││ │
│  │  │   Higher structure over the operad:                        ││ │
│  │  │     - Associahedra / coherence cells (rewrites between      ││ │
│  │  │       equivalent wirings)                                   ││ │
│  │  │     - PROP lifting (many-in/many-out, sharing & forking)    ││ │
│  │  │     - Distributive laws (compose two operads safely)        ││ │
│  │  │     - Linear-logic typing (⊗, ⊸, !) for resource discipline ││ │
│  │  └───────────────────────────┬────────────────────────────────┘│ │
│  │  ┌───────────────────────────▼────────────────────────────────┐│ │
│  │  │ Layer 3: WRIGHT (tekton/wright/) — the WRITE path          ││ │
│  │  │   5 escalating synthesis tiers:                            ││ │
│  │  │     Tier 0 (~1ms):  Direct operation match (interface hit) ││ │
│  │  │     Tier 1 (~10ms): Single composition (one plug-in)       ││ │
│  │  │     Tier 2 (~100ms):Bounded tree search (typed enumeration)││ │
│  │  │     Tier 3 (~1s):   Resource-constrained synthesis (ILP/SMT)││ │
│  │  │     Tier 4 (~5-10s):Full coherence + linear-logic proof    ││ │
│  │  │   Energy routing: cheapest synthesis tier first.           ││ │
│  │  └───────────────────────────┬────────────────────────────────┘│ │
│  │  ┌───────────────────────────▼────────────────────────────────┐│ │
│  │  │ Layer 4: DAEDALUS (tekton/daedalus_core.py)                ││ │
│  │  │   Generative search (the dual of OPTIMUS):                 ││ │
│  │  │     Classical:  minimize loss over parameters              ││ │
│  │  │     OPTIMUS:    factor a morphism into a better path       ││ │
│  │  │     DAEDALUS:   d_{t+1} = argmin_{c ∈ composites(spec)} cost(c)││ │
│  │  │   Discovers *assemblies*, not parameters; not paths but     ││ │
│  │  │   whole constructions that meet the interface.             ││ │
│  │  │   Guarantees: monotone cost improvement, no re-expansion    ││ │
│  │  │   (memoised), provable termination on bounded depth.        ││ │
│  │  └────────────────────────────────────────────────────────────┘│ │
│  │                                                                  │ │
│  │  BRIDGES (tekton/bridges/) — wire to Forge event bus            │ │
│  │  MATH (tekton/operadic|monoidal|linear|typetheory|polytope|prop)│ │
│  │  STRATEGIES (tekton/strategies/) — synthesis lenses             │ │
│  │  AGENT (tekton/forge_tekton_wright/) — unified entry point      │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  KOMPOSOS BRIDGE: tekton/bridges/komposos_bridge.py                  │
│    compile(design) -> KOMPOSOS Category morphism graph               │
└──────────────────────────────────────────────────────────────────────┘
```

### Why Five Layers (mirrors KOMPOSOS, inverted)

| Layer | Location | Problem | Solution |
|---|---|---|---|
| **Forge** | `src/forge_core/` | "How do I add capabilities?" | Hot-loadable plugins, event bus, DI |
| **TEKTON** | `tekton/core/operad.py` | "How do I keep assemblies valid?" | Operad composition laws |
| **Polytope** | `tekton/core/polytope.py` | "How do I reason about equivalent / resourceful designs?" | Coherence cells, PROPs, linear logic |
| **WRIGHT** | `tekton/wright/` | "How do I synthesize efficiently?" | Tiered, energy-routed synthesis |
| **DAEDALUS** | `tekton/daedalus_core.py` | "How do I find a *better* design?" | Generative search over composites |

### Architectural Invariants

1. **Forge is the outer shell.** Owns process, bus, lifecycle. Knows nothing of operads.
2. **Operad owns persistence.** Never touch the SQLite backend directly.
3. **Resource enrichment is intrinsic.** `op.cost` IS the monoidal weight, not metadata. The tensor is **non-cartesian** by default — no implicit copy.
4. **WRIGHT is the write path for Operad.** Tightly coupled; it is the synthesis interface, not a peer plugin.
5. **DAEDALUS operates on snapshots.** Snapshots the operad, searches, syncs discovered composites back.
6. **Strategies are functions on the Operad.** Math, not plugins.
7. **Bridges are glue.** Translate between Forge's event world and TEKTON's operadic world.
8. **Domain plugins are content.** They bring colours (types), operations, and resource algebras. The substrate does the synthesis.

---

## 4. Layer 1: Forge — The Plugin Framework

**Location:** `src/forge_core/` · **License:** MIT · **Philosophy:** framework, not product.

Four kernel primitives, identical in spirit to Orion:

- **Event Bus** (`events/`) — pub/sub, non-blocking. `await core.emit("design.synthesized", {...})`.
- **Hook System** (`hooks/`) — priority-ordered extension points, e.g. `@hook("before.synthesize")`.
- **Plugin Registry** (`registry/`) — `provide` / `require` dependency declarations.
- **Capability System** (`core/`) — a plugin requiring `component_store` only starts if one provides it.
- **Plugin Base** (`plugin/`) — DX layer, lifecycle (`on_start`, `on_stop`).

> Forge can be *the same code as Orion* if you want one host for both engines. Keeping the name distinct lets you ship TEKTON standalone.

---

## 5. Layer 2: TEKTON — The Operadic Runtime

**Location:** `tekton/core/operad.py` (the heart). The `Operad` class is simultaneously four things.

### An Operad (mathematical structure)

```python
op = Operad(db_path="my_components.db")

# Colours = interface types
op.add_colour("RawText"); op.add_colour("Tokens"); op.add_colour("Embedding")

# Operations: (inputs...) -> output, with a resource cost
op.add_op("tokenize", inputs=["RawText"], output="Tokens",  cost={"ms": 2})
op.add_op("embed",    inputs=["Tokens"],  output="Embedding", cost={"ms": 8})
op.add_op("merge",    inputs=["Embedding","Embedding"], output="Embedding", cost={"ms": 1})

# Operadic composition: plug `tokenize` into input 0 of `embed`
pipeline = op.compose("embed", 0, "tokenize")   # RawText -> Embedding, cost ms=10
```

**Laws enforced on every composition:**

- **Associativity of ∘ᵢ:** plugging order doesn't matter where inputs are disjoint.
- **Equivariance:** permuting inputs permutes the composite consistently (symmetric operad).
- **Unitality:** identity operation `1_C : (C) -> C` is a two-sided unit.
- **Type safety:** `op.compose` rejects colour mismatches at build time, not run time.
- **Resource soundness:** composite cost = monoidal product of part costs; never under-counts.

### A Persistent Store
Every `add_op` / `compose` writes to SQLite. Operad owns the DB. Deleting a colour cascades to its operations.

### A Resource-Enriched Structure
Every operation carries a **resource value** in a chosen monoid. Pluggable algebras (the dual of KOMPOSOS's 5 quantales):

| Resource Algebra | Combine `a ⊗ b` | Use case |
|---|---|---|
| Additive cost | `a + b` | Time/money accumulates along a build |
| Max capacity | `max(a,b)` | Peak memory / bottleneck |
| Multiset materials | `a ⊎ b` | Bill of materials, parts consumed |
| Linear tokens | spend-once | Permits, one-shot resources (non-copyable) |
| Tropical (min,+) | `min`/`+` | Cheapest-path-style optimisation |

> The **linear tokens** algebra is the load-bearing difference from KOMPOSOS: it forbids the diagonal, so a design literally cannot reuse a spent resource.

### An Executable Structure
Operations carry callables; composing operations composes the callables into a runnable artifact — synthesis output is executable, not descriptive.

```python
artifact = op.realize(pipeline)     # returns a callable
artifact("some raw text")           # runs embed(tokenize(...))
```

### Core Runtime Files (`tekton/core/`)

| File | Purpose |
|---|---|
| `types.py` | Colour, Operation, Composite, Wiring, ResourceValue, Interface, Spec |
| `enrichment.py` | ResourceMonoid + the 5 resource algebras |
| `persistence.py` | SQLiteBackend (internal — never use directly) |
| `hooks.py` | HookRegistry, internal events |
| `operad.py` | **THE** fused operadic runtime |
| `prop.py` | PROP lift: many-in/many-out, copy/discard *only where declared* |
| `polytope.py` | Higher coherence: associahedra, rewrites, distributive laws (Layer 2.5) |
| `linear.py` | Linear-logic typing: `⊗`, `⊸`, `!` exponential for the one place copy is allowed |
| `functor.py` | OperadMap (operad morphism), algebra over an operad |
| `theory.py` | Theory, Equation, validate (equational presentation of an operad) |
| `wright_bridge.py` | Bridges Operad ↔ WRIGHT synthesis |
| `daedalus.py` | Bridges Operad ↔ DAEDALUS search |
| `formal_coherence.py` | CoherenceProver (Mac Lane coherence / confluence of rewrites) |
| `serialization.py` | to_json / to_graphml / to_wiring_dsl |
| `komposos_compile.py` | Operadic composite → KOMPOSOS morphism graph |

---

## 6. Layer 2.5: Polytope — Higher Operadic / Resource Reasoning

**Location:** `tekton/core/polytope.py` · **Based on:** Mac Lane coherence, Leinster (*Higher Operads, Higher Categories*), Baez–Stay (Rosetta Stone), Melliès on linear logic.

Wraps an Operad and builds higher structure. The dual of KOMPOSOS's ∞-Cosmos.

- **Coherence cells (associahedra).** Two wirings that should be equal (re-bracketed composites) get a rewrite cell witnessing it. Lets the system treat equivalent designs as one.
- **PROP lifting.** Promotes the operad to a PROP so designs may fork outputs and merge inputs — but only via *declared* copy/merge operations, preserving resource discipline.
- **Distributive laws.** Safely compose two operads (e.g. a "control-flow" operad over a "data" operad) when a distributive law exists; refuse when it doesn't.
- **Linear-logic typing.** Assigns `⊗`/`⊸`/`!` types so the synthesizer can prove a design never duplicates a non-`!` resource.

### What This Activates
Higher-tier WRIGHT synthesis and DAEDALUS Levels 3–4 (below). Equivalent to how ∞-Cosmos activates KOMPOSOS Tier 2+.

---

## 7. Layer 3: WRIGHT — The Synthesis Co-Processor

**Location:** `tekton/wright/` · **Role:** the **write path** for the Operad (mirror of COG, which is KOMPOSOS's read path).

Given a **Spec** (target interface + resource budget + optional constraints), WRIGHT produces a **Construction** (a typed composite + its executable artifact) or a principled "no realizer."

### The 5 Tiers

| Tier | Cost | Method | What it produces |
|---|---|---|---|
| **0** | ~1ms | Direct match | A single existing operation already has the target interface |
| **1** | ~10ms | Single composition | One plug-in `o ∘ᵢ p` meets the interface |
| **2** | ~100ms | Bounded typed tree search | A small well-typed assembly (depth ≤ k) |
| **3** | ~1s | Resource-constrained synthesis | Cheapest assembly under budget (ILP / SMT over costs) |
| **4** | ~5–10s | Coherence + linear-logic proof | A construction *proven* resource-sound and unique up to coherence |

### Energy-Based Routing
Cheapest synthesis tier fires first; stop as soon as a construction meets the spec within budget. Cost-aware, exactly like COG's energy routing.

### The Verdicts (dual of COG's AGREE/ORPHAN/HOLLOW/REJECT)

| Verdict | Type-realizable | Resource-feasible | Meaning |
|---|---|---|---|
| **BUILDABLE** | Yes | Yes | A sound, in-budget construction exists. Ship it. |
| **OVERBUDGET** | Yes | No | Wiring exists but exceeds the resource budget. |
| **ILL-TYPED-GAP** | No | Yes | Resources suffice but no type-correct wiring (missing a component). |
| **IMPOSSIBLE** | No | No | No realizer under current components. |

### WRIGHT Files (`tekton/wright/`)
`engine.py` (5-tier synth), `session.py` (per-design state), `energy.py` (tier routing), `schema.py` (Spec, Construction, BuildResult), `router.py`, `solver.py` (ILP/SMT bridge for Tier 3), `server.py` (MCP), `serializers.py`.

---

## 8. Layer 4: DAEDALUS — Generative Search

**Location:** `tekton/daedalus_core.py` (kernel) + `tekton/core/daedalus.py` (bridge).

The dual of OPTIMUS. OPTIMUS *factors a morphism* into a better path; DAEDALUS *searches the space of composites* for a better whole design.

```
OPTIMUS:   m_{t+1} = argmax_{f ∈ factorizations(m_t)} weight(f)      # improve a relation
DAEDALUS:  d_{t+1} = argmin_{c ∈ composites(spec)}     cost(c)        # improve a design
           subject to: c realizes spec  ∧  c is resource-sound
```

Instead of discovering intermediate *objects*, DAEDALUS discovers intermediate *assemblies* — and prunes by type (only well-typed plug-ins expand) and by resource (branch-and-bound on cost).

### Three Guarantees
1. **Monotone improvement:** every accepted design has cost ≤ incumbent.
2. **No re-expansion:** composites are memoised by interface+resource signature (the dual of "no cycles").
3. **Provable termination:** bounded depth + finite component set ⇒ finite search; with the tropical algebra, Dijkstra-style optimality.

### Higher-Order DAEDALUS — 4 generation levels (mirrors Higher-Order OPTIMUS)
- **Level 1: operations** — assemble existing operations (standard).
- **Level 2: rewrites** — use Polytope coherence cells to swap an assembly for an equivalent cheaper one.
- **Level 3: PROP composites** — introduce declared fork/merge for sharing (resource-aware).
- **Level 4: operad maps** — synthesize a whole new operad-to-operad map (a *reusable design pattern*), not just one design.

---

## 9. The Synthesis Strategies

**Location:** `tekton/strategies/`. Each is a lens that proposes candidate assemblies — the generative dual of KOMPOSOS's 22 oracle strategies. Start with a focused core set; grow to parity.

| # | Strategy | Math | File |
|---|---|---|---|
| 1 | Interface match | colour/arity unification | `strategies.py` |
| 2 | Greedy composition | cheapest next plug-in | `strategies.py` |
| 3 | Type-directed search | inhabitation (proof search) | `inhabitation.py` |
| 4 | Resource ILP | integer program over costs | `resource_ilp.py` |
| 5 | SMT realizability | constraints → construction | `smt_synth.py` |
| 6 | Coherence rewrite | associahedra simplification | `coherence_rewrite.py` |
| 7 | PROP sharing | introduce declared copy/merge | `prop_sharing.py` |
| 8 | Distributive compose | combine two operads | `distributive.py` |
| 9 | Pattern lift | reuse a Level-4 operad map | `pattern_lift.py` |
| 10 | Linear discharge | spend-once resource planning | `linear_planner.py` |
| 11 | Tropical shortest build | (min,+) optimal assembly | `tropical.py` |
| 12 | Sketch completion | fill holes in a partial design | `sketch.py` |

---

## 10. The Dual Gate: Realizability + Resource Soundness

Every proposed design runs through a two-engine gate (mirror of KOMPOSOS's ZFC+CAT Dual Engine):

- **TYPE engine** — does a type-correct realizer exist? (Curry–Howard inhabitation.)
- **RES engine** — is it resource-sound and in-budget? (Linear-logic + cost monoid.)

**System 3 analog (PatternMiner):** records every BUILDABLE/IMPOSSIBLE outcome as an episode, learns which sketch shapes tend to be realizable, and proposes Level-4 operad maps (reusable patterns) when a shape consistently succeeds — the constructive mirror of MetaKan mining emergent axioms.

---

## 11. Higher-Order DAEDALUS

See §8. Levels 1–2 ship first (operations + coherence rewrites); 3–4 (PROP composites + operad maps) follow once Polytope is complete — matching KOMPOSOS shipping OPTIMUS Levels 1–2 and stubbing 3–4.

---

## 12. Formal Coherence Guarantee

`tekton/core/formal_coherence.py` provides a `CoherenceProver`:

- **Mac Lane coherence:** all formally-equal re-bracketings of a composite are genuinely equal — so "the design" is well-defined independent of assembly order.
- **Confluence of rewrites:** the coherence-cell rewrite system is confluent (Newman's lemma on a terminating system) ⇒ a unique normal-form design.
- **Resource conservation:** the composite's resource value equals the monoidal product of parts (no creation/loss), proven not merely tested.

This is the dual of KOMPOSOS's Formal Yoneda Proof — and notably the spec aims to *prove* conservation rather than only test it, addressing the analogue of KOMPOSOS limitation #8.

---

## 13. The Bridge to KOMPOSOS

**Location:** `tekton/bridges/komposos_bridge.py`

```python
design = wright.synthesize(spec)            # TEKTON builds it
graph  = compile_to_komposos(design)        # operations -> morphisms, wiring -> composition
verdict = komposos_cog.verify(graph, claim) # KOMPOSOS interprets/verifies it
```

The compile is structure-preserving: each unary operation becomes a morphism; each n-ary operation becomes a span/cospan (or a morphism out of a monoidal product object); resource costs map to quantale confidences via a chosen homomorphism (e.g. tropical-cost → multiplicative-confidence). This is the payoff of keeping both engines symmetric-monoidal at the bottom: **TEKTON designs, KOMPOSOS audits, and the loop closes.**

---

## 14. Mathematical Foundation — File Map

```
tekton/
├── operadic/      # coloured operads, free operad, algebras, equivariance
├── prop/          # PROPs, string-diagram normal forms
├── monoidal/      # symmetric monoidal cats, tensor, coherence
├── linear/        # linear logic, ⊗/⊸/!, resource discipline
├── typetheory/    # Curry–Howard, inhabitation / proof search
├── polytope/      # associahedra, higher coherence, distributive laws
└── tropical/      # (min,+) semiring optimisation
```

---

## 15. Data Flow

```
Spec (interface + budget + constraints)
   │
   ▼  WRIGHT.synthesize
[Tier 0→4 energy routing] ──uses──► Operad (components) + Polytope (coherence/linear)
   │
   ├─ proposes candidates via Strategies (§9)
   ├─ each candidate ► Dual Gate (TYPE + RES)  (§10)
   ▼
DAEDALUS.search  (improve cost over BUILDABLE candidates, branch-and-bound)
   │
   ▼
Construction (typed composite + executable artifact)
   │
   ├─ realize() ► runnable artifact
   └─ compile_to_komposos() ► morphism graph ► KOMPOSOS verifies
```

---

## 16. Mathematical Guarantees

1. **Validity by construction.** Any design WRIGHT returns is type-correct — the operad laws make ill-typed assemblies unrepresentable.
2. **Resource soundness.** No design reuses a non-`!` resource; conservation is proven (§12).
3. **Optimality (bounded).** Under the tropical algebra, DAEDALUS returns a cost-minimal design within the depth bound.
4. **Termination.** Finite components + bounded depth + memoisation ⇒ finite, terminating search.
5. **Round-trip soundness.** `compile_to_komposos` preserves composition, so KOMPOSOS verifies the *same* structure TEKTON built.

---

## 17. Directory Structure

```
tekton-synthesis/
├── src/
│   └── forge_core/                     # Layer 1: plugin framework (mirror of orion_core)
│       ├── events/                     #   event bus
│       ├── hooks/                      #   hook system
│       ├── registry/                   #   plugin registry
│       ├── core/                       #   capability DI
│       └── plugin/                     #   plugin base / DX
│
├── tekton/
│   ├── core/                           # Layer 2 + 2.5 runtime
│   │   ├── types.py
│   │   ├── enrichment.py               #   resource monoid + 5 algebras
│   │   ├── persistence.py              #   SQLite backend (internal)
│   │   ├── hooks.py
│   │   ├── operad.py                   #   THE operadic runtime
│   │   ├── prop.py
│   │   ├── polytope.py                 #   Layer 2.5 higher coherence
│   │   ├── linear.py
│   │   ├── functor.py                  #   operad maps / algebras
│   │   ├── theory.py
│   │   ├── wright_bridge.py
│   │   ├── daedalus.py
│   │   ├── formal_coherence.py
│   │   ├── serialization.py
│   │   └── komposos_compile.py
│   │
│   ├── wright/                         # Layer 3: synthesis (write path)
│   │   ├── engine.py
│   │   ├── session.py
│   │   ├── energy.py
│   │   ├── schema.py
│   │   ├── router.py
│   │   ├── solver.py                   #   ILP/SMT bridge (Tier 3)
│   │   ├── server.py                   #   MCP server
│   │   └── serializers.py
│   │
│   ├── daedalus_core.py                # Layer 4: generative search kernel
│   │
│   ├── strategies/                     # synthesis lenses (§9)
│   │   ├── strategies.py
│   │   ├── inhabitation.py
│   │   ├── resource_ilp.py
│   │   ├── smt_synth.py
│   │   ├── coherence_rewrite.py
│   │   ├── prop_sharing.py
│   │   ├── distributive.py
│   │   ├── pattern_lift.py
│   │   ├── linear_planner.py
│   │   ├── tropical.py
│   │   └── sketch.py
│   │
│   ├── operadic/                       # pure math: coloured operads
│   ├── prop/                           # pure math: PROPs / string diagrams
│   ├── monoidal/                       # pure math: symmetric monoidal cats
│   ├── linear/                         # pure math: linear logic
│   ├── typetheory/                     # pure math: Curry–Howard / inhabitation
│   ├── polytope/                       # pure math: associahedra, coherence
│   ├── tropical/                       # pure math: (min,+) semiring
│   │
│   ├── gate/                           # Dual Gate: TYPE + RES + PatternMiner (§10)
│   │   ├── type_engine.py
│   │   ├── res_engine.py
│   │   └── pattern_miner.py            #   System-3 analog
│   │
│   ├── bridges/                        # Forge bridge plugins
│   │   ├── component_store_plugin.py   #   Operad as a Forge capability
│   │   ├── wright_plugin.py
│   │   ├── daedalus_plugin.py
│   │   ├── polytope_plugin.py
│   │   ├── session_plugin.py
│   │   ├── telemetry_plugin.py
│   │   └── komposos_bridge.py          #   compile design -> KOMPOSOS graph
│   │
│   ├── forge_tekton_wright/            # unified Agent
│   │   ├── agent.py                    #   wires all layers
│   │   └── config.py
│   │
│   └── tests/                          # mirror KOMPOSOS's test discipline
│
├── tests/                              # Forge tests
├── docs/
├── CLAUDE.md
├── TEKTON_MASTER_SPEC.md               # this file
└── pyproject.toml
```

---

## 18. How to Add a Domain — One Line

```python
await agent.add_plugin(CircuitDesignPlugin(agent.forge))
```

A domain plugin brings **content** — colours (interface types), operations (components), and a resource algebra. It does **not** bring infrastructure. The layers handle the rest:

- **Forge** manages plugin lifecycle.
- **Operad** stores the domain's components with composition laws.
- **Polytope** builds coherence/resource structure over them.
- **WRIGHT** synthesizes designs meeting a spec.
- **DAEDALUS** searches for cheaper/stronger designs.

The adapter implements:

```python
colours() -> list[str]                 # interface types in this domain
operations() -> list[Operation]        # components with inputs/output/cost
resource_algebra() -> ResourceMonoid   # how this domain's costs combine
```

Every strategy then works on every domain. The same resource-ILP that lays out a circuit lays out a data pipeline. The math doesn't know which domain it's in.

---

## 19. Honest Limitations

1. **Synthesis is search; search is exponential.** Operad laws prune hard, but Tier 2+ can blow up on rich component sets. Depth bounds and memoisation contain it; they don't abolish it.
2. **Resource modelling is only as good as the algebra you declare.** Wrong algebra → confidently-wrong budgets.
3. **Linear discipline adds friction.** Non-cartesian typing is the whole point but makes "just reuse it" require an explicit `!`/copy operation. Intentional, occasionally annoying.
4. **Tier 3 leans on external ILP/SMT.** Inherits their scaling limits; large designs untested.
5. **Coherence proof is hard past low dimension.** Mac Lane coherence is clean for monoidal/symmetric; higher coherence (Levels 3–4) is where formality gets expensive.
6. **No domain plugins yet.** Infrastructure first, content later — same posture as KOMPOSOS.
7. **The KOMPOSOS compile is structure-preserving but lossy on resources.** The cost→confidence homomorphism is a modelling choice, not a theorem.

---

## 20. Roadmap

### Phase 0 — Foundations (substrate that must be right)
- `tekton/operadic/`: coloured operad, free operad, `∘ᵢ`, equivariance, units.
- `tekton/core/types.py` + `enrichment.py`: Colour/Operation/Composite + 3 resource algebras (additive, max, tropical).
- `tekton/core/operad.py`: fused runtime (structure + persistence + enrichment + execution) with law checks on compose.
- `tekton/core/persistence.py`: SQLite, cascade deletes.
- Tests: associativity, equivariance, unit laws, type-rejection, resource conservation.
- **Exit criterion:** can build, persist, and `realize()` a multi-step pipeline with correct cost.

### Phase 1 — Synthesis MVP (the write path)
- `tekton/wright/`: Tiers 0–2 (direct, single compose, bounded typed tree search) + energy routing + verdicts.
- `tekton/strategies/`: interface match, greedy composition, type-directed inhabitation, sketch completion.
- `tekton/gate/type_engine.py`: realizability check.
- **Exit criterion:** give a Spec (target interface), get back a BUILDABLE construction or a principled gap.

### Phase 2 — Resources & optimal search
- `tekton/linear/` + `tekton/core/linear.py`: `⊗`/`⊸`/`!`, spend-once tokens, multiset materials algebra.
- `tekton/gate/res_engine.py`: resource soundness + budget feasibility.
- `tekton/wright/solver.py` + Tier 3: resource-constrained synthesis (ILP/SMT).
- `tekton/daedalus_core.py`: branch-and-bound generative search, memoisation, tropical optimality. Levels 1–2.
- **Exit criterion:** synthesize the *cheapest* in-budget design and prove it resource-sound.

### Phase 3 — Higher structure & coherence
- `tekton/polytope/` + `tekton/core/polytope.py`: associahedra, coherence-cell rewrites, distributive laws.
- `tekton/prop/` + `tekton/core/prop.py`: PROP lift, declared fork/merge.
- `tekton/core/formal_coherence.py`: Mac Lane coherence + confluence + conservation proofs.
- WRIGHT Tier 4; DAEDALUS Levels 3–4 (PROP composites, operad maps).
- **Exit criterion:** unique normal-form designs; reusable Level-4 patterns mined and reapplied.

### Phase 4 — Self-construction & learning
- `tekton/gate/pattern_miner.py`: System-3 analog — mine BUILDABLE/IMPOSSIBLE episodes, propose operad maps.
- Self-extension: auto-generate Forge plugins from operation signatures (dual of KOMPOSOS PluginGenerator).
- Self-observation: telemetry as components; find missing colours / redundant operations.
- **Exit criterion:** system proposes new reusable components/patterns from its own build history.

### Phase 5 — Integration & scale
- `tekton/bridges/komposos_bridge.py`: `compile_to_komposos`, round-trip tests (TEKTON builds → KOMPOSOS verifies).
- MCP server (`wright/server.py`), serialization, wiring DSL.
- Scale benchmarking; consider sharding operads connected by operad maps.
- **Exit criterion:** closed loop — design in TEKTON, audit in KOMPOSOS, both agreeing on the same structure.

---

## The Bottom Line

TEKTON is KOMPOSOS turned inside-out. KOMPOSOS asks *"is this true, given what relates to what?"* and answers with a verdict. TEKTON asks *"what can I build, given what composes with what, and what it costs?"* and answers with a thing you can run.

Same monoidal-categorical bedrock; opposite primitive (operation vs morphism), opposite direction (generate vs interpret), opposite resource stance (linear vs cartesian). Keep them sharing a substrate and they compose into one loop: **synthesize, then verify.**

---

**Status:** specification / roadmap. No code written yet — Phase 0 is the first build.
**Authors:** (you) & Claude · **Date:** 2026-06-04
