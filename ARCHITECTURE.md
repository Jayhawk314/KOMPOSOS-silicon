# KOMPOSOS‑V — Architecture

This document explains *how the system is built and why*. For orientation see
`README.md`; for working rules see `CLAUDE.md`; for decisions/state see `MEMORY.md`.

---

## 1. Design philosophy

Three commitments shape every part of the system.

1. **Structure substitutes for scale.** Reasoning is done by composing small
   categorical engines, not by a large model. The payoff is *verifiability*: a
   composite either type‑checks, runs, and stays coherent, or it doesn't.

2. **Every kept claim carries a checkable receipt.** A capability is only
   retained after it is *built → executed → verified → grounded → judged*. You
   can check the receipt without trusting the system that produced it.

3. **Proposal and verification are strictly separated.** Cheap, fallible
   mechanisms (strategies, candidate generators, embeddings) *propose*. Exact,
   conservative mechanisms (composition, COG, ZFC, honesty/MDL) *verify*. The
   two never mix: a proposer may never persist or act as a verdict.

This separation is what lets the system be aggressive about generating
hypotheses while staying honest about what it commits to memory.

---

## 2. The categorical foundation

Everything sits on one object: the **`Category`** (`core/category.py`), a *fused
runtime* — structure + persistence + enrichment in a single class (mirrors
OPERADUM's `Operad`).

### Objects and morphisms (`core/types.py`)

```python
Object(name, type_name="Object", metadata={}, embedding=None, provenance=...)
Morphism(name, source, target, confidence=1.0, metadata={}, _fn=None, ...)
```

Two design facts drive the whole architecture:

- **`confidence` IS the enriched hom‑value.** The category is enriched over a
  multiplicative quantale: composing `A→B` (conf p) with `B→C` (conf q) yields
  confidence `p·q`. "Strength of a relationship" and "cost to traverse it" are
  the same number, so prediction, costing, and ranking all read from one field.

- **`_fn` makes a morphism executable.** A morphism may carry a callable. This is
  the hook that turns *structural* edges into *runnable* capabilities — the basis
  of executable synthesis (§7). `Morphism.is_callable` / `__call__` expose it.

### The `Category` API contract

| Method | Role |
|---|---|
| `add(name)` / `add_object(obj)` | create objects (auto‑created by edges too) |
| `connect(src, tgt, name, confidence, fn=None, **meta)` | add a (possibly executable) edge |
| `add_morphism(mor)` | lower‑level write; updates adjacency, hom‑values, persists, fires hook |
| `remove_morphism(mor_id)` | reverse a write; drops adjacency/hom‑value when last edge of a pair |
| `morphisms_from/to(name)`, `morphisms()`, `objects()`, `get(name)` | reads |

Internally it maintains `_morphisms` (id→Morphism), `_adjacency` /
`_reverse_adjacency`, `_hom_values` ((s,t)→confidence), a SQLite `_backend`, and a
`_hooks` bus (`morphism_added` / `morphism_removed` / `object_removed`). Writes
and removals keep all of these consistent — important because the loop's rollback
correctness depends on `remove_morphism` truly removing (it was a silent no‑op
before; see `MEMORY.md`).

---

## 3. The six engines and how they compose

| Engine | Module | Verb | Consumes | Produces |
|---|---|---|---|---|
| KOMPOSOS | `core/`, `categorical/` | interpret | the graph | verified relations, factorings |
| ORACLE | `oracle/` | predict | the graph (+embeddings) | ranked `Prediction`s |
| OPERADUM | `operadum/` | construct | a `Spec` | a type/resource‑verified route |
| PRONOIA | `operadum/pronoia/` | predict/honesty | evidence + hypotheses | MDL gain + grounding |
| COG | `cog/` | judge | a `CogClaim` | AGREE/ORPHAN/HOLLOW/REJECT |
| OPTIMUS | `core/optimus.py` | refine | the graph | structural gaps, rewrites |

They compose along a single pipeline (the loop, §6). The unifying data types are
the `Category` (shared substrate), the `Prediction` (prediction currency), and
the `CogClaim` (judgment currency). No engine talks to another except through
these — there are no private cross‑engine seams.

---

## 4. The prediction subsystem (`oracle/`)

### One contract

```python
class InferenceStrategy:
    def predict(self, source: str, target: str) -> List[Prediction]: ...
```

Every strategy — Kan extension, composition, horn‑filling, Yoneda, topos,
operadic, geometric, conjecture‑gap, … — is a drop‑in box keyed on this. That is
why ~50 files cohere: they all speak `Prediction`.

### One currency (`oracle/prediction.py`)

`Prediction(source, target, predicted_relation, prediction_type, strategy_name,
confidence, reasoning, evidence)` with `key = (source,target,relation)` for
dedup and `with_adjusted_confidence(...)` for re‑weighting.

### One registry

`create_all_strategies(category, embeddings)` returns the live ensemble (**21
strategies**). It is the single place COG's Tier 4 imports — adding a guarded
`try/import/append` there auto‑enrolls a strategy everywhere.

### One orchestrator

`CategoricalOracle.predict(source, target)` runs the full pipeline:

```
strategies → merge duplicates (calibrated weighted avg)
           → sheaf‑coherence filter (predictions must agree on overlaps)
           → game‑theoretic selection (Nash)
           → Bayesian confidence adjustment (learner)
```

### Proactive mode (`oracle/conjecture.py`)

`ConjectureEngine` flips prediction from *reactive* (`predict(s,t)`) to
*proactive* (`what pairs are missing?`). Six candidate generators (composition,
structural‑hole, fiber, semantic, temporal, yoneda) surface missing‑edge pairs;
`surface_candidates()` runs them oracle‑free (no embeddings required), while
`conjecture()` additionally scores each pair through `CategoricalOracle`. This is
the loop's richer observer (§6).

---

## 5. The continuous layer (`data/embeddings.py`)

A single shared vector space, justified by **Yoneda**: an object is determined by
its profile of morphisms, and an embedding approximates that profile in a metric
space. `EmbeddingsEngine.fit(category)` computes a *soft‑Yoneda* vector per
object from its in/out morphism signature, so objects with the same graph role
land near each other (verified: two nodes that both `--feeds-->index` score
high even with different names). Default backend is deterministic feature hashing
(numpy + stdlib, offline); `model=` upgrades to sentence‑transformers.

**Architectural constraint:** embeddings are a *proposal‑side prior only*. They
seed candidate edges (semantic similarity); they never gate, verify, or persist.
n‑ary relations are *not* modeled with hypergraphs — that role belongs to operads
(OPERADUM), which carry the composition/coherence laws a hypergraph lacks.

---

## 6. The self‑improvement loop (`core/loop.py`)

One cycle over the shared `Category`. Each stage is a distinct engine; each gate
can roll the candidate back.

```
            ┌─────────────────────────────── shared Category ───────────────────────────────┐
            │                                                                                 │
 observe ───┤  OPTIMUS.find_structural_gaps()  OR  ConjectureEngine.surface_candidates()      │
            │     → gaps: [{source, target, via, path_confidence}]                            │
            │                                                                                 │
 design ────┤  OPERADUM (Wright): synthesize + TYPE/RESOURCE verify route source→target       │
            │     → verdict ∈ {BUILDABLE, OVERBUDGET, ILL_TYPED_GAP, IMPOSSIBLE}              │
            │     (IMPOSSIBLE / ILL_TYPED_GAP → skip: don't synthesize a phantom edge)        │
            │                                                                                 │
 predict ───┤  PRONOIA honest_rank(evidence, routes): MDL compression gain + grounding        │
            │     → pick the best‑grounded route                                              │
            │                                                                                 │
 build ─────┤  HOST (FORGE): generate + hot‑load a plugin; its on_start writes the edge        │
            │                                                                                 │
 ground ────┤  ExecutableSynthesizer: build the COMPOSITE fn, RUN it, check path‑coherence     │
            │     → verify‑fail ⇒ roll back; success ⇒ upgrade edge to the runnable composite  │
            │                                                                                 │
 remember ──┤  HonestyGate: grounding(claim, committed evidence) ≥ min_grounding ?             │
            │                                                                                 │
 judge ─────┤  COG.check_claim: AGREE / ORPHAN / HOLLOW / REJECT                               │
            │                                                                                 │
 keep ──────┤  kept = (COG ≠ REJECT) AND honest ;  else unload + Category.remove_morphism      │
            └─────────────────────────────────────────────────────────────────────────────┘
                 next observe sees the mutated graph → loop to convergence or budget
```

`FillResult` records the full receipt per gap: `operadum_verdict`, `pronoia_gain`,
`pronoia_honest`, `executed`, `runtime_verified`, `grounding`, `cog_verdict`,
`kept`. OPERADUM/PRONOIA load from `operadum/`; if absent the loop degrades to
OPTIMUS + HOST + COG.

---

## 7. The verification spine (the three gates)

The loop's value is the gates. Each is a distinct, independent check.

### Grounding — `core/executable_synthesis.py`

A structural gap `source→target` exists because an *executable spine*
`source→…→target` exists. `ExecutableSynthesizer`:

1. **finds** all callable spines (DFS over morphisms with `_fn`);
2. **composes** them (`reduce` over the spine's functions — the categorical
   composite, with confidence `∏ pᵢ`);
3. **runs** the composite on probe inputs;
4. **verifies path‑coherence**: when multiple spines reach the target, they must
   produce equal outputs (the executable analog of the sheaf/horn coherence
   check). Divergent mechanisms ⇒ ambiguous ⇒ fail.

This is the falsifiable teeth: a single spine only proves "runs without error,"
but multiple spines that *disagree* prove the capability is ill‑defined.

### Honesty — `core/honesty_gate.py`

Reusable commit‑time gate using PRONOIA's `grounding_of` (zlib conditional
description length): `grounding = 1 − fabricated_fraction`, where fabricated bits
are the parts of the claim the committed evidence cannot account for. A claim
persists only if `grounding ≥ min_grounding` (default 0.5).

**Vocabulary rule:** the claim must be serialized in the *same* form as the
evidence (`"src name tgt conf"` lines) or grounding reads ~0. `loop._supporting_claim()`
builds the claim from the actual supporting path, and excludes the candidate edge
itself so a claim cannot ground itself. Degrades *open* (honest=None) if PRONOIA
is absent, consistent with the loop's optional‑engine policy.

### Judgment — COG (`cog/engine.py`)

An **energy‑routed, progressively‑refining** gate. `check_claim(CogClaim)` starts
cheap and escalates only as needed:

| Tier | Check | Cost |
|---|---|---|
| 0 | direct graph lookup | ~1 ms |
| 1 | composition / path finding | ~10 ms |
| 2 | sheaf coherence + Kan extension | ~100 ms |
| 3 | ZFC dual engine (logic/proof) | — |
| 4 | topology (Ricci + persistent homology + interchange) **+ the oracle ensemble** (`create_all_strategies`) | budgeted (≤30 s) |

Verdicts: **AGREE** (supported), **ORPHAN** (plausible but unconnected),
**HOLLOW** (asserted without substance), **REJECT** (contradicted). The loop keeps
on anything but REJECT — *and* honesty must pass.

Persistence decision: `kept = (cog_verdict != "REJECT") and honesty.honest`.
Structure (COG) says *well‑formed*; honesty says *not fabricated*; both required.

---

## 8. Measurement (`core/scoreboard.py`)

Self‑improvement is meaningless without a falsifiable metric. The scoreboard is a
link‑prediction harness: build a ground‑truth category (executable spine +
derivable transitive shortcuts + an isolated trap pair), **hold out** the
shortcuts and trap, run the loop, and score:

```
recall       = recovered_derivable / held_out_derivable
precision    = recovered_derivable / all_edges_added
hallucinated = added edges matching the no‑path trap   (must be 0)
spurious     = added edges that are not ground truth at all
```

Full structure → 1.0 / 1.0 (PASS) under both observers — including conjecture,
which proposes the trap but has it rejected by the gates, so precision stays 1.0.
Remove a supporting spine edge → recall 0.0 (FAIL). The number tracks reality.

---

## 9. The math engine room

The strategies and COG tiers are thin; the depth lives here.

| Area | Module | Used for |
|---|---|---|
| Kan extensions (Lan/Ran) | `categorical/kan_extensions.py` | predict‑forward / synthesize‑back; COG Tier 2 |
| Operads / multicategories | `categorical/operads.py`, OPERADUM | n‑ary construction, the design engine |
| Topos / intuitionistic logic | `categorical/`, `oracle/topos_strategy.py` | partial‑evidence reasoning |
| Gray categories | `categorical/` | interchange / coherence (COG Tier 4) |
| Persistent homology / sheaves | `topology/` | H¹ = inconsistency; coherence checks |
| HoTT / cubical | `hott/`, `cubical/` | identity / path / constructive equality |
| ZFC dual engine | `zfc/` | the logic narrator (COG Tier 3) |
| Geometry | `geometry/` | Ricci curvature (COG Tier 4), protein heritage |
| Games | `game/` | Nash selection in the oracle optimizer |

---

## 10. Persistence

`Category` persists through a SQLite `_backend` (`core/persistence.py`):
`insert_morphism` / `delete_morphism` / `delete_object`, and object embeddings are
stored as blobs. `db_path=":memory:"` gives an ephemeral graph (used by the loop
demo and scoreboard); a file path makes the memory durable. The hooks bus lets
observers react to writes, but hooks fire *after* the write — gating therefore
happens at the call site (the loop), not in a hook.

---

## 11. Extension points & invariants

**Extend:**
- *new strategy* → subclass `InferenceStrategy`, register in `create_all_strategies`.
- *new observer* → emit `{source,target,via,path_confidence}` and dispatch in `_observe`.
- *new persistence path* (e.g. `komposos_kg`) → route writes through `HonestyGate`.
- *new construction tier* → add a `_tierN` to OPERADUM's Wright (see `operadum/CLAUDE.md`).

**Never break (enforced by convention + the scoreboard):**
1. proposers don't persist or verify;
2. embeddings are proposal‑side only; no hypergraphs (use operads);
3. honesty + COG gate every persistence point;
4. a filled gap is a runnable, path‑coherent composite;
5. rollback truly removes (`Category.remove_morphism`).

---

## 12. Current boundaries

The full pipeline (observe→design→predict→ground→remember→judge→measure) is real
and tested (140 tests). It is validated on **synthetic graphs**. The substrate is
complete; what's missing is *content* — `domains/` is empty by design, and
`komposos_kg` is not yet built (when it is, its write path must pass through the
honesty gate). The highest‑leverage next step is pointing the loop at a real
domain so the scoreboard runs on data that matters.
