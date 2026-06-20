# OPERADUM — The Manual

**A categorical *design* engine: the constructive mirror of KOMPOSOS.**

Version 0.3.0 · Python ≥ 3.10 · standard library only (no third-party runtime deps)

---

## Table of Contents

1. [What OPERADUM is](#1-what-operadum-is)
2. [Install & quickstart](#2-install--quickstart)
3. [The mental model](#3-the-mental-model)
4. [Tutorial: your first design](#4-tutorial-your-first-design)
5. [The Operad runtime](#5-the-operad-runtime)
6. [Resource algebras](#6-resource-algebras)
7. [Synthesis with WRIGHT](#7-synthesis-with-wright)
8. [The Dual Gate](#8-the-dual-gate)
9. [Generative search with DAEDALUS](#9-generative-search-with-daedalus)
10. [Linear logic & non-cartesian resources](#10-linear-logic--non-cartesian-resources)
11. [Coherence & higher structure (Polytope, PROP)](#11-coherence--higher-structure)
12. [Self-construction & learning](#12-self-construction--learning)
13. [Domains](#13-domains)
14. [The KOMPOSOS round-trip](#14-the-komposos-round-trip)
15. [Forge & the Agent](#15-forge--the-agent)
16. [The synthesis server & wiring DSL](#16-the-synthesis-server--wiring-dsl)
17. [Accuracy & validation](#17-accuracy--validation)
18. [Cookbook](#18-cookbook)
19. [API quick reference](#19-api-quick-reference)
20. [Architecture map](#20-architecture-map)
21. [Glossary](#21-glossary)
22. [Limitations & roadmap](#22-limitations--roadmap)

---

## 1. What OPERADUM is

OPERADUM is a **design engine built on operad theory**. Where KOMPOSOS *interprets*
(stores relations, verifies claims, factors existing structure), OPERADUM
*constructs* (stores operations, generates valid assemblies, synthesizes artifacts
that satisfy a specification).

The two are duals at the bottom — both symmetric-monoidal-categorical — and they
compose: an OPERADUM design **compiles into** a KOMPOSOS morphism graph. *Synthesize,
then verify.*

| Concern | KOMPOSOS (interpret) | OPERADUM (design) |
|---|---|---|
| Primitive | Morphism `A → B` | Operation `(A₁,…,Aₙ) → B` |
| Substrate | Enriched category | Coloured operad, symmetric monoidal |
| Question | "are these related?" | "what wiring is valid / best-ranked?" |
| Enrichment | Quantale confidence | Resource/figure monoid |
| Truth | Verification (a verdict) | Realizability (an executable artifact) |
| Copyability | Cartesian (copy facts freely) | **Substructural** (resources are spent) |

OPERADUM was formerly named **TEKTON / SYNTHESIS-I**; that name still appears inside
`TEKTON_MASTER_SPEC.md`, the design rationale.

---

## 2. Install & quickstart

OPERADUM is a pure-Python package. From the repo root:

```powershell
python -m pytest operadum/tests -q      # 135 passing, 2 skipped
python -m examples.pipeline_demo        # the end-to-end loop
```

To use it as a library, ensure the repo root is on `sys.path` (or `pip install -e .`
with the provided `pyproject.toml`), then:

```python
from operadum import Operad, Spec, Wright

op = Operad("text-pipeline")
op.add_op("tokenize", ["RawText"], "Tokens",    cost={"ms": 2}, fn=str.split)
op.add_op("embed",    ["Tokens"],  "Embedding", cost={"ms": 8}, fn=len)

result = Wright(op).synthesize(Spec(inputs=("RawText",), output="Embedding"))
print(result)                                   # [BUILDABLE] (RawText) -> Embedding ...
print(result.construction.artifact("a b c"))    # runs embed(tokenize("a b c")) -> 3
```

The highest-level entry point is the **Agent** (§15):

```python
from operadum import Agent, Spec, SynthesisDesignDomain
agent = Agent.for_domain(SynthesisDesignDomain())
agent.optimize(Spec(("Benzene",), "Paracetamol"))
```

---

## 3. The mental model

Five ideas. Internalize these and the whole API follows.

1. **Colour** = an interface type (a "port"). `RawText`, `Embedding`, `Aniline`.
2. **Operation** = a typed build rule `(A₁,…,Aₙ) → B` carrying a **cost** and an
   optional **callable**. This is the primitive — a *rule for building a B out of parts*.
3. **Composite** = a wiring tree of operations — a point in the *free operad*. Its
   still-open input ports (left-to-right) are its inputs; the head's output is its
   output. Any well-typed tree is itself a valid operation (that's the operad axioms).
4. **Resource monoid** = how costs combine along a build (additive, max, …). It is
   **non-cartesian** by default — a resource is *spent*, not copied.
5. **Spec** = a target interface (`inputs → output`) plus an optional budget. You hand
   a Spec to WRIGHT; you get back a **Construction** (a typed composite + a runnable
   artifact) or a principled "no realizer."

> KOMPOSOS's primitive relates two existing things. OPERADUM's primitive builds a new
> thing. The space of valid designs is the free operad on your components; synthesis is
> search over that space, and the composition laws make partial designs safe to assemble.

---

## 4. Tutorial: your first design

We will design a route through a tiny "pipeline" domain, run it, optimize it, and
audit it.

```python
from operadum import Operad, Spec, Wright, ADDITIVE_COST

# 1. Declare the domain: colours (types) and operations (components).
op = Operad("pipeline", monoid=ADDITIVE_COST)
op.add_op("tokenize", ["RawText"], "Tokens",    cost={"ms": 2}, fn=lambda s: s.split())
op.add_op("embed",    ["Tokens"],  "Embedding", cost={"ms": 8}, fn=len)
op.add_op("merge",    ["Embedding", "Embedding"], "Embedding", cost={"ms": 1},
          fn=lambda a, b: a + b)

# 2. Build by hand with operadic composition: plug `tokenize` into input 0 of `embed`.
pipeline = op.compose("embed", 0, "tokenize")      # (RawText) -> Embedding
print(pipeline.to_wiring())                        # embed(tokenize(RawText))
print(pipeline.cost(op.monoid))                    # {'ms': 10}

# 3. Realize it into a runnable artifact.
run = op.realize(pipeline)
print(run("the quick brown fox"))                  # 4

# 4. Or let WRIGHT find it for you, cheapest-first, within a budget.
result = Wright(op).synthesize(Spec(("RawText",), "Embedding", budget={"ms": 20}))
print(result)                                      # [BUILDABLE] ... tier=1 cost={'ms': 10.0}
```

`compose(outer, i, inner)` plugs `inner` into the **i-th open input** of `outer`. After
you fill one slot, the open-input list changes — so the index refers to *currently open*
ports, not original ones. (This is operadic composition `∘ᵢ`.)

---

## 5. The Operad runtime

`operadum.core.operad.Operad` is the fused runtime — it *is* the operadic structure, a
SQLite store, a resource-enriched structure, an executable structure, and a hook-enabled
runtime, all in one class. Mirror of KOMPOSOS's `Category`.

### Construction

```python
Operad(name="default", db_path=":memory:", monoid=ADDITIVE_COST)
```

Pass `db_path="components.db"` for on-disk persistence; colours, operations, and
composites persist automatically. Pass any `ResourceMonoid` as `monoid` (§6).

### Colours

```python
op.add_colour("RawText", **metadata)     # -> Colour
op.get_colour("RawText")                 # -> Colour | None
op.colours()                             # -> list[Colour]
op.remove_colour("Tokens")               # cascades to every operation that mentions it
```

### Operations

```python
op.add_op(name, inputs, output, cost=None, fn=None, **metadata)   # -> Operation
op.get_op(ref)                       # ref = id, name, or live Operation
op.operations()                      # -> list[Operation]
op.operations_producing("Embedding") # the search primitive: ops whose output is X
op.identity("Tokens")                # the unit 1_C : (C) -> C
```

An `Operation` has `.inputs`, `.output`, `.cost`, `.arity`, `.interface`, `.id`,
`.as_composite()`. Its `id` is the deterministic signature `name:in1,in2->out`.

### Composition

```python
op.compose(outer, i, inner) -> Composite   # plug inner into the i-th OPEN input of outer
```

`compose` enforces **type safety at build time** — a colour mismatch raises `TypeError`,
an out-of-range index raises `IndexError`. (Resource *soundness* is the RES gate's job,
not `compose`'s — see §8.)

A `Composite` exposes: `.open_inputs()`, `.output`, `.arity`, `.interface`, `.depth`,
`.operations()`, `.cost(monoid)`, `.to_wiring()`.

### Execution

```python
artifact = op.realize(composite)     # -> callable; raises if any op lacks a fn
artifact(*open_inputs)               # runs the wired callables, left-to-right
```

The returned callable takes one positional argument per open input and returns the
output value. Synthesis output is **executable**, not descriptive.

### Hooks

```python
op.hooks.on("operation_added", lambda operation: ...)
op.hooks.on("composed", lambda **kw: ...)
# events: colour_added, colour_removed, operation_added, operation_removed,
#         composed, realized, bulk_loaded
```

---

## 6. Resource algebras

A `ResourceMonoid` says how two figure vectors combine along a build. The field is
still named `cost` for compatibility, but it can hold any labelled quantity:
`{"ms": 8}`, `{"safety_risk": 0.05}`, `{"confidence": 0.92}`, etc.
The classic algebras are:

| Constant | `combine(a,b)` | `linear` | Use for |
|---|---|---|---|
| `ADDITIVE_COST` | per-key sum | no | time, money, energy, steps |
| `MAX_CAPACITY` | per-key max | no | peak memory, bottleneck, thermal |
| `MULTISET_MATERIALS` | per-key sum | no | bill of materials, parts consumed |
| `TROPICAL` | per-key sum (min-ordered) | no | shortest-path / cheapest assembly |
| `LINEAR_TOKENS` | disjoint union, **raises on overlap** | **yes** | permits, licences, one-shot, qubits |
| `GENERAL_FIGURES` | per-figure policy | no | mixed time/risk/confidence/evidence/etc. |
| `SAFETY_FIRST` | per-figure policy | no | rank by safety/compliance first |
| `COMPLIANCE_FIRST` | per-figure policy | no | rank by AS9100/regulatory trace first |
| `FASTEST_RECOVERY` | per-figure policy | no | rank by schedule recovery first |
| `LEAST_DISRUPTIVE` | per-figure policy | no | rank by rework/disruption first |
| `EVIDENCE_FIRST` | per-figure policy | no | rank by evidence/confidence first |
| `SUSTAINABILITY_FIRST` | per-figure policy | no | rank by emissions/energy first |

```python
from operadum import get_resource_algebra
get_resource_algebra("additive")    # additive|max|multiset|tropical|linear
get_resource_algebra("safety")      # safety|compliance|fastest|least_disruptive|evidence|sustainability
```

Use `budget={...}` for upper bounds and `requirements={...}` for lower bounds:

```python
Spec((), "Released",
     budget={"safety_risk": 0.05, "compliance_debt": 0},
     requirements={"confidence": 0.9})
```

`GENERAL_FIGURES` combines common figures by their natural rule: schedule,
labor, energy, emissions, and compliance debt sum; memory and toxicity take max;
safety/defect risk use probabilistic union; confidence multiplies; evidence,
trace completeness, trust, throughput, and safety margin use weakest-link min.

`LINEAR_TOKENS` is the load-bearing one: combining a token with itself raises
`ResourceError` — it forbids the diagonal, so a design cannot spend a one-shot resource
twice. Write your own with `ResourceMonoid(combine, unit, compare, name=name, linear=False)`;
`combine` must be associative with `unit` as identity, and `compare(cost, budget)` must
return whether `cost` is within `budget`.

---

## 7. Synthesis with WRIGHT

`operadum.wright.Wright` is the **write path** — the operad's synthesizer. Hand it a
`Spec`, get a `BuildResult`.

```python
from operadum import Wright, Spec, Verdict
w = Wright(operad, max_depth=4)

spec = Spec(inputs=("RawText",), output="Embedding", budget={"ms": 20})
result = w.synthesize(spec)         # energy-routed: first in-budget construction
result = w.optimize(spec)           # best-ranked in-budget construction (DAEDALUS)
cert   = w.certify(spec)            # Tier-4: normal form + proofs (§11)
```

### Energy-routed tiers

`synthesize` tries the cheapest synthesis tier first and stops at the first sound,
in-budget construction:

| Tier | Method | Finds |
|---|---|---|
| 0 (~1ms) | direct match | an existing op already has the interface |
| 1 (~10ms) | single composition | one plug-in `o ∘ᵢ p` meets it |
| 2 (~100ms) | bounded tree search | a small typed assembly (depth ≤ `max_depth`) |
| 3 (~1s) | resource-constrained search | the globally best-ranked in-budget design (DAEDALUS) |

`optimize` skips routing and always returns the global best-ranked design within
the depth bound. With `ADDITIVE_COST`, best-ranked still means cheapest.

### Verdicts

`BuildResult` carries a `Verdict` (dual of KOMPOSOS's COG verdicts):

| Verdict | Type-realizable | In budget | Meaning |
|---|---|---|---|
| `BUILDABLE` | ✓ | ✓ | a sound, in-budget construction exists — ship it |
| `OVERBUDGET` | ✓ | ✗ | a wiring exists but exceeds the budget |
| `ILL_TYPED_GAP` | ✗ | ✓ | resources suffice but no type-correct wiring (missing component) |
| `IMPOSSIBLE` | ✗ | ✗ | no realizer under current components |

```python
result.verdict            # Verdict.BUILDABLE
result.buildable          # bool
result.tier               # which tier produced it
result.construction       # Construction | None
result.construction.wiring        # "embed(tokenize(RawText))"
result.construction.cost          # {'ms': 10.0}
result.construction.artifact      # runnable callable
result.construction.composite     # the Composite
```

---

## 8. The Dual Gate

Every candidate passes a two-engine gate (mirror of KOMPOSOS's ZFC+CAT dual engine).

- **TYPE engine** (`operadum.gate.TypeEngine`) — realizability via Curry–Howard
  inhabitation. *Does a type-correct realizer exist?*
  ```python
  TypeEngine(op).is_realizable(spec)         # reachable in the colour graph?
  TypeEngine(op).realizes(composite, spec)   # does THIS composite realize the spec?
  TypeEngine(op).inhabited_colours({"RawText"})
  ```
- **RES engine** (`operadum.gate.ResEngine`) — resource soundness + budget feasibility.
  ```python
  res = ResEngine(op)
  res.feasible(composite, spec)   # (sound_and_in_budget, cost, reason)
  res.prove_sound(composite)      # -> LinearJudgement (the conservation proof, §10)
  ```

`prove_sound` reads linearity off the monoid: `LINEAR_TOKENS` judges every token
strictly; additive/max/tropical treat every resource as freely reusable, so their
designs are linear-sound by construction.

---

## 9. Generative search with DAEDALUS

`operadum.daedalus_core.Daedalus` is the dual of OPTIMUS. OPTIMUS factors a morphism
into a better path; DAEDALUS searches the space of composites for a better whole design:

```
DAEDALUS:  d* = argmin_{c ∈ composites(spec)} rank(cost(c))   s.t.  c realizes spec  ∧  sound
```

```python
from operadum import Daedalus, Spec
result = Daedalus(operad, max_depth=6).search(Spec(("Benzene",), "Paracetamol"))

result.found_in_budget     # bool
result.best                # best-ranked in-budget sound Composite
result.best_cost           # its cost
result.best_any            # best-ranked sound design ignoring budget (for OVERBUDGET)
result.stats               # SearchStats(expansions, memo_hits, frontier_size, pruned_unsound)
```

It builds a Pareto frontier of designs keyed by open-input signature, memoised on
`(target, depth, allowed-inputs)`. Three guarantees:

1. **Monotone improvement** — returns the best-ranked design among all depth-bounded
   sound designs.
2. **No re-expansion** — sub-designs memoised (the dual of "no cycles").
3. **Provable termination** — bounded depth + finite components ⇒ finite search; under
   `TROPICAL` this is Dijkstra-style optimality.

Resource-unsound branches (e.g. linear reuse) are pruned automatically because the
monoid's `combine` raises.

---

## 10. Linear logic & non-cartesian resources

This is the single most important difference from cartesian KOMPOSOS. A *fact* copies
freely; a *resource* does not.

```python
from operadum import Operad, LINEAR_TOKENS, Daedalus, Spec
op = Operad("site", monoid=LINEAR_TOKENS)
op.add_op("use", ["Site"], "Part", cost={"permit_42": 1}, fn=lambda x: x)
op.add_op("join", ["Part", "Part"], "Build", cost={}, fn=lambda a, b: (a, b))

# join(use, use) would spend permit_42 twice -> pruned as unsound.
r = Daedalus(op).search(Spec(("Site", "Site"), "Build"))
r.found_any                 # False
r.stats.pruned_unsound      # > 0
```

The **typed** view lives in `operadum.core.linear`:

```python
from operadum import LinearChecker, operation_signature, composite_signature
operation_signature(op.get_op("join"))     # (Part ⊗ Part) -o Build   (a Lolli)
judgement = LinearChecker().judge(composite)
judgement.ok                                # False if a non-! token is spent twice
judgement.duplicated                        # the contracted tokens
judgement.sequent                           # the design's linear type, as witness
```

Types: `Atom`, `Tensor` (⊗, "both at once"), `Lolli` (⊸, "consume to produce"),
`OfCourse` (!, the one place copying is allowed). A token in the checker's `bang` set is
exempt — `!` restores the right to copy. An operation `(A₁,…,Aₙ) → B` is the sequent
`A₁ ⊗ … ⊗ Aₙ ⊸ B`.

---

## 11. Coherence & higher structure

### Polytope — associahedra & normal forms

`operadum.core.Polytope` builds higher structure over an operad: it recognizes when two
differently-bracketed wirings are *the same design* and reduces every design to a unique
normal form.

```python
from operadum import Polytope
poly = Polytope(op).declare_associative("merge").declare_unit("V")

poly.normalize(design)        # right-associate + drop identity units -> canonical form
poly.equivalent(a, b)         # do a and b share a normal form?
poly.one_step_rewrites(comp)  # the coherence-cell edges (associahedron edges)
poly.bracketings(op, operands)# all K_n bracketings (associahedron vertices)
```

### CoherenceProver — Mac Lane, confluence, conservation

`operadum.core.CoherenceProver` *proves* three things (dual of KOMPOSOS's Formal Yoneda
Proof), each returning a `Proof(claim, holds, witness, data)`:

```python
from operadum import CoherenceProver, catalan
prover = CoherenceProver(op, poly)
prover.prove_coherence(merge_op, operands)  # Mac Lane: all Catalan(n-1) bracketings -> 1 NF
prover.prove_confluence(composite)          # Newman: terminating + locally confluent
prover.prove_conservation(composite)        # cost(comp) == cost(normalize(comp)), PROVEN
```

Conservation is proven *structurally* — the non-identity operation multiset is invariant
under the rewrites and identities cost the monoid unit — not merely tested.

### WRIGHT Tier 4 certification

```python
cert = Wright(op).certify(spec, polytope=poly)   # -> Certificate | None
cert.certified        # unique & conservation.holds & linear.ok & coherence.holds
cert.normal_form      # the canonical design
cert.conservation     # a Proof
cert.linear           # a LinearJudgement
```

### PROP — declared fork/merge & sharing

`operadum.core.PROP` adds many-output structure: a design may *fork* a result, but only
through a **declared** copy, and copying a linear (non-banged) colour is refused.

```python
from operadum import PROP, CopyError
prop = PROP(op, bang={"Config"})
prop.can_copy("Mid")            # True for accumulative resources; linear needs a bang
prop.declare_copy("Mid")        # raises CopyError if unsound
report = prop.analyze_sharing(design)     # closed sub-designs worth sharing + cost saved
run, counts = prop.realize_shared(design) # memoised DAG execution; counts ops actually run
```

---

## 12. Self-construction & learning

The engine improves its own component set from its build history (master spec Phase 4).

### PatternMiner — mine & lift reusable components

```python
from operadum import PatternMiner
miner = PatternMiner(op, min_support=2, min_size=2)

for r in build_results:
    miner.record_result(r)               # logs BUILDABLE/IMPOSSIBLE by interface shape

miner.realizability_rate("Embedding")    # learned: how often that shape succeeds
miner.mine()                             # recurring sub-designs (Patterns)
miner.propose()                          # not-yet-lifted patterns, best first
lifted = miner.auto_lift()               # promote them to reusable compound operations
```

A lifted pattern becomes a first-class operation, so a former multi-step target becomes
a **Tier-0** one-step build.

### SelfObserver — structural self-analysis

```python
from operadum import SelfObserver
report = SelfObserver(op).observe()
report.source_colours    # colours no operation produces (raw inputs)
report.sink_colours      # colours no operation consumes (terminal products)
report.redundant_ops     # (dominated, by, reason) — same interface, cost-dominated
report.proposals         # human-readable suggested corrections
```

### PluginGenerator — package the operad as a fresh plugin

```python
from operadum import PluginGenerator
gen = PluginGenerator()
plugin = gen.materialize(op, name="learned-domain")   # live DomainPlugin (callables kept)
source = gen.generate_source(op, class_name="LearnedDomain")  # importable Python source
```

The loop: **mine → lift → package → reload.**

---

## 13. Domains

A domain brings *content* — colours, operations, a resource algebra — and nothing else.
The substrate does the synthesis. Subclass `operadum.domains.DomainPlugin`:

```python
from operadum import DomainPlugin, ADDITIVE_COST
from operadum.core.types import Operation, Spec
from operadum.domains.base import GroundTruthCase

class MyDomain(DomainPlugin):
    name = "my-domain"

    def colours(self):
        return ["A", "B", "C"]

    def operations(self):
        return [
            Operation("f", ["A"], "B", cost={"u": 1}, _fn=lambda x: x),
            Operation("g", ["B"], "C", cost={"u": 2}, _fn=lambda x: x),
        ]

    def resource_algebra(self):
        return ADDITIVE_COST

    def ground_truth(self):                       # optional, for the accuracy harness
        return [GroundTruthCase("A->C", Spec(("A",), "C"), buildable=True, min_cost=3.0)]

op = MyDomain().build_operad()                    # loads colours + operations in one call
```

`GroundTruthCase` fields: `name, spec, buildable, min_cost, note, expected_roundtrip`
(`"AGREE"` for additive-style algebras, `"HOLLOW"` for peak/bottleneck — see §14).

### Built-in domains

| Domain | Algebra | Shape | Verified by |
|---|---|---|---|
| `SynthesisDesignDomain` | additive (USD) | tree | cost optimum / round-trip |
| `ComputePipelineDomain` | max (peak memory) | tree | cost optimum / round-trip |
| `ManufacturingDomain` | multiset (bill of materials) | tree | cost optimum / round-trip |
| `ProgramSynthesisDomain` | additive (op count) | tree | **input/output examples** |
| `QuantumCircuitDomain` | additive (gate count) | tree | **2×2 unitary matrices** |
| `LogicCircuitDomain` | additive (gate count) | **network** | **truth table** |
| `TopologicalNetworkDomain` | additive (modules) | **network** | **graph invariants** |
| `MaterialsDomain` | additive (molecular weight) | tree + net | **real linker descriptors + KOMPOSOS** |

`operadum.domains.DOMAINS` is a `{name: class}` registry of all eight.

### Designing by behaviour — the SemanticGate

The Dual Gate decides *type-correct* and *resource-sound*. Many designs pass both yet
only some are *the right one*. `operadum.gate.SemanticGate` (the "third gate") enumerates
type-correct designs cheapest-first and returns the cheapest whose **behaviour** passes a
validator:

```python
from operadum import SemanticGate, Spec
gate = SemanticGate(ProgramSynthesisDomain().build_operad(), max_depth=5)

# Program-by-example: give input/output pairs, get a correct program.
d = gate.by_examples(Spec(("String",), "Int"),
                     examples=[("a b c", 3), ("x y", 2)])
d.wiring                  # "word_count(split_words(String))"
d.artifact("hello world") # 2

# Or any custom validator (a simulator, a solver, a test suite, KOMPOSOS):
gate.synthesize(spec, validator=lambda artifact, composite: ...)
```

This is OPERADUM's deepest test of *design potential*: given only a target behaviour and
a component library, it designs an artifact a validator then confirms independently. The
quantum domain does the same with a unitary-matrix validator (`phase_equal`). The
validator is exactly where a specialized toolkit plugs in — and the numerics it needs
live in the *domain*, never in the stdlib core.

### Network designs (the Diagram layer)

A `Composite` is a *tree*; some designs are *graphs* (fan-out, distinguished inputs,
feedback). `operadum.core.Diagram` is the DAG / string-diagram form: named boundary
inputs (so two `Bool` ports differ), shared node outputs (true fan-out), and sharing for
free (each node costed and run once). `operadum.gate.synthesize_diagram` searches small
DAGs against a validator.

```python
from operadum import Diagram, synthesize_diagram, truth_table_validator, LogicCircuitDomain

op = LogicCircuitDomain().build_operad()
# Synthesize XOR from NAND alone — needs fan-out a tree cannot express.
r = synthesize_diagram(op, inputs=[("a","Bit"),("b","Bit")], output_colour="Bit",
                       validator=truth_table_validator([({"a":a,"b":b}, a != b)
                                  for a in (False,True) for b in (False,True)]),
                       gate_ops=["nand"], max_nodes=4)
r.diagram.realize()(a=True, b=False)            # True
r.diagram.graph_metrics()                       # {nodes, edges, cycle_rank, ...}
```

`Diagram.graph_metrics()` exposes topological invariants (cycle rank = first Betti
number, edge count, connectivity), so a network can be designed *to a topological
specification* — see `TopologicalNetworkDomain`.

### Materials / MOF design (real data + KOMPOSOS)

`MaterialsDomain` designs a metal-organic framework from a **real** linker library (the
Kulik 22-atom set: SMILES, MW, donor counts, viability), optimizes the lightest viable
linker, designs by property via the SemanticGate, exposes the framework as a topological
net (`mof_net`), and round-trips to KOMPOSOS. The property "model" is a transparent
surrogate over real descriptors — the seam where a true DFT/stability predictor attaches.

> **What kinds of domains fit?** Anything you can frame as "assemble a target from typed
> parts via composable steps, with a cost that combines monoidally, where you want to
> *design* (not merely interpret)." Good fits: synthesis routes, ETL/ML pipelines,
> program & proof synthesis (the Curry–Howard-native case), circuit/hardware layout,
> bill-of-materials manufacturing, planning, quantum circuits (linear / no-cloning).
> Poor fits: pure classification, continuous-parameter tuning, problems where the whole
> isn't a function of its parts.

---

## 14. The KOMPOSOS round-trip

OPERADUM designs; KOMPOSOS audits; the loop closes. Both engines share a
symmetric-monoidal bottom, so the compile is structure-preserving.

```python
from operadum import compile_to_komposos, KomposVerifier

graph = compile_to_komposos(design.composite, op)   # operations -> morphisms
graph.objects                                        # the colours
graph.morphisms                                      # [{name, source, target, confidence, ...}]
graph.root                                           # the output colour

result = KomposVerifier().verify(design.composite, op)
result.verdict           # "AGREE" / "HOLLOW" / "REJECT"
result.sound             # is the resource->confidence map exact here?
result.engine            # "mini" or "komposos"
```

### The soundness theorem

`product(confidences) == cost_to_confidence(total_cost)`. Because each operation's
confidence is `exp(-λ·cost)` and additive costs sum, this is an **exact monoid
homomorphism** (additive cost → multiplicative confidence) — the theorem behind "both
engines agree on the same structure." Verdict `AGREE`.

Under non-additive algebras (max/tropical) the map is **lossy** → verdict `HOLLOW`
(structure preserved, homomorphism inexact). The engine reports this honestly; it is
the master spec's limitation #7, not a bug.

### Verifying with the real KOMPOSOS

Point the verifier at a KOMPOSOS-IV checkout and the actual `core.category.Category`
ingests the graph:

```python
KomposVerifier(komposos_path=r"C:\Users\JAMES\github\KOMPOSOS-IV-CHEM") \
    .verify(design.composite, op)
# [AGREE] engine=komposos composed=0.2725 expected=0.2725 (sound)
```

### Hybridizing with specialized tools

OPERADUM's guarantees are **structural** (type-correct, resource-sound, coherent,
cost-optimal-within-bound), not **semantic**. Domain accuracy lives in three places you
control, and each is a hook for a specialized, validated toolkit:

1. **Operation callables (`_fn`)** — let `_fn` call a real engine (a reaction predictor,
   a SPICE sim, a quantum simulator) instead of a placeholder.
2. **Cost models** — derive costs from a learned/empirical predictor (yield, latency, FEM).
3. **A validator gate** — after TYPE + RES pass, hand the candidate to a specialized
   checker (SAT/SMT, a physics sim, a test suite, or KOMPOSOS) before calling it BUILDABLE.

The division of labor: OPERADUM is the categorical scaffold that *cannot propose
nonsense*; the specialized tool supplies the *domain truth*.

---

## 15. Forge & the Agent

### Forge — the plugin host (Layer 1)

`operadum.forge.Forge` is the outer shell: an event bus, a capability registry, and
plugin lifecycle with dependency-injection. It knows nothing about operads.

```python
from operadum import Forge, ComponentStorePlugin, WrightPlugin, DaedalusPlugin
forge = (Forge("host")
         .register(WrightPlugin())            # requires "component_store"
         .register(ComponentStorePlugin())    # provides "component_store"
         .start())                            # starts in dependency order
forge.capability("synthesizer")               # the Wright instance
forge.capabilities_available                  # ['component_store', 'synthesizer', ...]
```

A plugin declares `provides` / `requires`; Forge starts each only once its requirements
are satisfied, and raises `CapabilityError` if they never can be. Built-in plugins:
`ComponentStorePlugin → component_store` (the Operad), `WrightPlugin → synthesizer`,
`DaedalusPlugin → search`, `PolytopePlugin → coherence`.

Write your own by subclassing `operadum.forge.Plugin` (`name`, `provides`, `requires`,
`on_start`, `capabilities`).

### Agent — the unified entry point

`operadum.Agent` boots a Forge with every layer wired in and exposes one friendly
surface.

```python
from operadum import Agent, Spec, SynthesisDesignDomain

agent = Agent.for_domain(SynthesisDesignDomain())   # monoid taken from the domain
agent.optimize(Spec(("Benzene",), "Paracetamol"))   # cheapest route
agent.certify(spec)                                  # Tier-4 certificate
agent.verify(design.composite)                       # KOMPOSOS round-trip
agent.observe()                                      # SelfReport
agent.self_extend()                                  # mine history -> new components

agent.operad        # the component store
agent.wright        # the synthesizer
agent.daedalus      # the search engine
agent.polytope      # the coherence engine
```

`Agent.for_domain` threads the domain's resource algebra through so DAEDALUS uses the
right monoid. `agent.add_domain(other)` loads more content. Design calls emit
`design.synthesized` / `design.optimized` events on the Forge bus.

---

## 16. The synthesis server & wiring DSL

### Wiring DSL

A design serializes to a compact S-expression and round-trips back:

```python
from operadum import to_wiring_dsl, parse_wiring, design_to_json

dsl = to_wiring_dsl(design.composite)        # "embed(tokenize(RawText))"
rebuilt = parse_wiring(dsl, op)              # -> Composite (runnable)
record = design_to_json(design.composite, op)# {wiring, inputs, output, cost, depth, operations}
```

In the DSL grammar, a name that resolves to an operation is an application
`op(arg, …)`; any other bare name is an open-input colour leaf.

### MCP-style server

`operadum.wright.server.SynthesisServer` exposes the design surface as MCP-style tools.
It is transport-agnostic: `handle(request)` takes a JSON-shaped dict and returns one.

```python
from operadum.wright.server import SynthesisServer
from operadum import Agent, SynthesisDesignDomain

server = SynthesisServer(Agent.for_domain(SynthesisDesignDomain()))
server.tools()                               # discovery: tool names + params
server.handle({"method": "optimize",
               "params": {"inputs": ["Benzene"], "output": "Paracetamol"}})
# {'ok': True, 'result': {'verdict': 'BUILDABLE', 'design': {...}}}
```

Methods: `list_colours`, `list_operations`, `synthesize`, `optimize`, `certify`,
`verify`, `compile`. Errors come back as `{"ok": False, "error": "..."}` — the server
never crashes on bad input.

---

## 17. Accuracy & validation

There are three notions of accuracy, available at different stages.

### 1. Engine correctness (now) — `operadum.validation.benchmark`

Over random operads with a brute-forced known optimum, does `optimize()` recover the
true minimum cost?

```python
from operadum.validation.benchmark import run_benchmark
run_benchmark(n_trials=50, seed=0)
# BenchmarkResult(trials=50, optimum_recall=1.000, buildable_recall=1.000)
```

### 2 & 3. Synthesis quality + real-world accuracy — `operadum.validation.domain_accuracy`

Run a domain's ground truth through synthesis and the round-trip:

```python
from operadum.validation.domain_accuracy import measure_domain_accuracy
from operadum import SynthesisDesignDomain
measure_domain_accuracy(SynthesisDesignDomain())
# DomainScore(synthesis-design: buildable_accuracy=1.000, optimum_recall=1.000,
#             roundtrip_accuracy=1.000)
```

- `buildable_accuracy` — did WRIGHT call each spec buildable/not correctly?
- `optimum_recall` — for buildable specs, did `optimize()` find the known cheapest?
- `roundtrip_accuracy` — did the round-trip match the domain's expectation (AGREE for
  additive, HOLLOW for peak)?
- `roundtrip_agree` — the stricter "fraction verified AGREE".

> Real-world accuracy in a domain ultimately comes from grounding operation
> callables, cost models, and the validator gate in specialized tools (§14). The harness
> measures whatever truth you wire in.

### Measuring *accuracy levels* (where the system can be wrong)

The harnesses above score 1.0 because they test correctness-by-construction or
exhaustive optimum recall — neither can fail. To measure genuine accuracy (a number
that varies below 1.0), test **generalization**: synthesize from partial information,
then evaluate on held-out data.

```python
from operadum.validation.generalization import measure_generalization
measure_generalization()      # program-by-example: accuracy vs. #training examples
#   n_train=1: holdout_accuracy=0.872   (the cheapest consistent program can overfit)
#   n_train=2: holdout_accuracy=1.000

from operadum.validation.concept_learning import measure_concept_learning
measure_concept_learning(realizable=True)   # PAC learning curve: chance -> exact
measure_concept_learning(realizable=False)  # structureless target: stays at chance
```

Two findings worth internalizing:
- **Inductive bias is real.** OPERADUM returns the *cheapest* consistent design (Occam),
  so under-determined specs can yield a simpler-but-wrong artifact. More examples raise
  accuracy — the curve is the measurement.
- **No free lunch.** For a *structureless* target (a random Boolean function), held-out
  accuracy stays at chance until the entire truth table is seen. No learner — OPERADUM
  included — can generalize a concept with no structure for its hypothesis class to
  exploit. Accuracy levels are bounded by how well the *component library* matches the
  domain's true structure.

### Real-data accuracy: materials design (`validation/materials_accuracy.py`)

The domain-grounded study. On the real Kulik 22-atom MOF linker set, a stdlib logistic
regression predicts donor-richness (≥5 oxygen donors → water-stable carboxylate
coordination) from *cheap* descriptors (MW, N, S — never the oxygen count), trained on a
split and evaluated held out. OPERADUM then designs a framework on the held-out linkers
using the predictor as its validator.

```
predictor_accuracy = 0.867   (majority baseline 0.472)
design_hit_rate    = 0.533   (oracle 1.000, random 0.467)
```

Two lessons, both important and only visible on real data:
- The predictor extracts **genuine structure–property signal** (0.87 ≫ 0.47) — heavier
  linkers carry more carboxylate oxygens (corr ≈ +0.75), nitrogen competes with oxygen
  under the fixed atom budget (corr ≈ −0.49).
- **Predictor accuracy ≠ design accuracy.** An 87%-accurate model yields only ~53% design
  accuracy — barely above random. Because the cost being minimized (molecular weight)
  *correlates* with the property, the cost-optimizer preferentially selects the lightest
  linkers, which is exactly where the predictor's false positives live. **Optimizing cost
  against a correlated predicted property amplifies prediction error.** This is the real
  caution for design-under-prediction, and the seam where a better (DFT/ML) predictor —
  or a cost decorrelated from the property — earns its keep.

---

## 18. Cookbook

**Build a design by hand and run it**
```python
pipe = op.compose("embed", 0, "tokenize")
op.realize(pipe)("hello world")
```

**Synthesize the cheapest design under a budget**
```python
Wright(op).optimize(Spec(("RawText",), "Embedding", budget={"ms": 20}))
```

**Prove a design is resource-sound**
```python
ResEngine(op).prove_sound(design.composite)        # -> LinearJudgement
```

**Forbid a resource being spent twice**
```python
op = Operad("x", monoid=LINEAR_TOKENS)             # any reuse now raises / is pruned
```

**Find equivalent designs / a canonical form**
```python
poly = Polytope(op).declare_associative("merge")
poly.equivalent(a, b); poly.normalize(a)
```

**Certify a design (proofs attached)**
```python
Wright(op).certify(spec, polytope=poly)            # -> Certificate
```

**Let the system learn a reusable component from history**
```python
miner = PatternMiner(op); [miner.record_result(r) for r in results]; miner.auto_lift()
```

**Add a whole domain in one line**
```python
agent = Agent.for_domain(MyDomain())
```

**Audit a design through KOMPOSOS**
```python
KomposVerifier(komposos_path=PATH).verify(design.composite, op)
```

**Serve synthesis over a JSON interface**
```python
SynthesisServer(agent).handle({"method": "optimize", "params": {...}})
```

---

## 19. API quick reference

| Symbol | Module | Role |
|---|---|---|
| `Operad` | `core.operad` | the fused operadic runtime |
| `Colour`, `Operation`, `Composite`, `Interface`, `Spec` | `core.types` | the data |
| `ResourceMonoid`, `ADDITIVE_COST`, `MAX_CAPACITY`, `MULTISET_MATERIALS`, `TROPICAL`, `LINEAR_TOKENS` | `core.enrichment` | resource algebras |
| `LinearChecker`, `Atom`/`Tensor`/`Lolli`/`OfCourse`, `operation_signature` | `core.linear` | linear-logic typing |
| `Polytope`, `CoherenceProver`, `Proof`, `catalan` | `core.polytope`, `core.formal_coherence` | coherence |
| `PROP`, `CopyError` | `core.prop` | fork/merge & sharing |
| `PluginGenerator` | `core.plugin_generator` | package operad as plugin |
| `to_wiring_dsl`, `parse_wiring`, `design_to_json` | `core.serialization` | the wiring DSL |
| `Wright`, `BuildResult`, `Construction`, `Certificate`, `Verdict` | `wright` | synthesis |
| `SynthesisServer` | `wright.server` | MCP-style server |
| `TypeEngine`, `ResEngine` | `gate` | the Dual Gate |
| `PatternMiner`, `Pattern`, `SelfObserver`, `SelfReport` | `gate` | self-construction |
| `Daedalus`, `SearchResult`, `Solver` | `daedalus_core`, `wright.solver` | generative search |
| `DomainPlugin`, `GroundTruthCase`, `SynthesisDesignDomain`, `ComputePipelineDomain` | `domains` | content |
| `compile_to_komposos`, `MorphismGraph`, `KomposVerifier`, `RoundTripResult` | `bridges` | KOMPOSOS round-trip |
| `Forge`, `Plugin`, `CapabilityError`, `*Plugin` | `forge` | the plugin host |
| `Agent` | `agent` | the unified entry point |

---

## 20. Architecture map

```
operadum/
├── core/                  # Layer 2 + 2.5 — the runtime
│   ├── operad.py          #   THE fused operadic runtime
│   ├── types.py           #   Colour, Operation, Composite, Interface, Spec
│   ├── enrichment.py      #   ResourceMonoid + 5 algebras
│   ├── persistence.py     #   SQLite backend (internal)
│   ├── hooks.py           #   structural events
│   ├── linear.py          #   linear logic (⊗/⊸/!)
│   ├── polytope.py        #   associahedra, coherence rewrites, normal forms
│   ├── prop.py            #   PROP lift, sharing
│   ├── formal_coherence.py#   Mac Lane + confluence + conservation proofs
│   ├── plugin_generator.py#   package operad as a DomainPlugin
│   └── serialization.py   #   wiring DSL + JSON
├── gate/                  # the Dual Gate + learning
│   ├── type_engine.py · res_engine.py
│   ├── pattern_miner.py · self_observer.py
├── wright/                # Layer 3 — the write path
│   ├── engine.py · schema.py · solver.py · server.py
├── daedalus_core.py       # Layer 4 — generative search
├── domains/               # pluggable content
│   ├── base.py · synthesis_design.py · compute_pipeline.py
├── bridges/               # KOMPOSOS glue
│   ├── komposos_bridge.py · round_trip.py
├── forge/                 # Layer 1 — the plugin host
│   ├── core.py · events.py · plugin.py · plugins.py
├── agent.py               # the unified entry point
├── validation/            # accuracy harnesses
│   ├── benchmark.py · domain_accuracy.py
└── tests/                 # 137 tests including integration

examples/   pipeline_demo · daedalus_demo · coherence_demo
            domain_roundtrip_demo · self_construction_demo · forge_agent_demo
```

**Architectural invariants (do not break):** the `Operad` is the fused runtime and owns
persistence (never touch `SQLiteBackend`); cost is intrinsic, not metadata; `compose`
enforces TYPE safety while the RES gate enforces resource soundness; WRIGHT is the
operad's write path (not a peer plugin); the KOMPOSOS bridge stays dependency-free.

---

## 21. Glossary

- **Colour** — an interface type; the "port" operations plug into.
- **Operation** — an `(A₁,…,Aₙ) → B` build rule with a cost and an optional callable.
- **Composite** — a wiring tree of operations; a point in the free operad.
- **Free operad** — the space of all well-typed wirings of your components; the design space.
- **Operadic composition `∘ᵢ`** — plug one operation's output into the i-th input of another.
- **Resource monoid** — how costs combine along a build; non-cartesian by default.
- **Cartesian vs substructural** — facts copy freely (cartesian); resources are spent (linear).
- **Realizability** — "does a construction exist?"; OPERADUM's notion of truth (Curry–Howard).
- **Spec** — target interface + budget handed to WRIGHT.
- **Construction** — a typed composite + its runnable artifact; a successful design.
- **Verdict** — BUILDABLE / OVERBUDGET / ILL_TYPED_GAP / IMPOSSIBLE.
- **Dual Gate** — the TYPE (realizability) + RES (resource) engines a candidate must pass.
- **Coherence normal form** — the canonical representative of a class of equivalent designs.
- **Associahedron `Kₙ`** — the polytope of bracketings of an n-ary associative composite.
- **Round-trip soundness** — `product(confidences) == cost_to_confidence(total cost)`.

---

## 22. Limitations & roadmap

### Honest limitations

1. **Synthesis is search; search is exponential.** Operad laws prune hard, but Tier 2+
   can blow up on rich component sets. Depth bounds + memoisation contain it, not abolish it.
2. **Only as good as the algebra you declare.** Wrong resource algebra → confidently
   wrong budgets.
3. **Linear discipline adds friction.** Non-cartesian typing is the point, but "just
   reuse it" needs an explicit `!`/copy. Intentional, occasionally annoying.
4. **Structural, not semantic.** OPERADUM guarantees type-correct, resource-sound,
   coherent, cost-optimal-within-bound designs. It does **not** guarantee the *domain*
   is right unless the costs / `_fn`s / validators encode real domain knowledge (§14).
5. **The KOMPOSOS compile is lossy on non-additive resources.** Exact homomorphism for
   additive; `HOLLOW` (honestly reported) for peak/bottleneck algebras.

### Roadmap

- **Done:** Phases 0–4 (runtime, synthesis, resources/search, coherence,
  self-construction), Layer 1 Forge, Phase 5 (DSL + server), two domains, real KOMPOSOS
  round-trip.
- **Next:** more domains (each one `DomainPlugin`); a validator-gate for grounding in
  specialized tools; sharded operads connected by operad maps (scale); an async Forge
  bus; a real stdio/HTTP transport for the server.

---

*OPERADUM is the constructive mirror of KOMPOSOS. KOMPOSOS asks "is this true, given
what relates to what?" and answers with a verdict. OPERADUM asks "what can I build,
given what composes with what, and what it costs?" and answers with a thing you can run.
Keep them sharing a substrate and they compose into one loop: **synthesize, then
verify.***

© 2026 James Hawkins · `LicenseRef-Proprietary-Commercial`
