# OPERADUM

**A categorical *design* engine â€” the constructive mirror of KOMPOSOS-IV's interpretive engine.**

> Formerly **TEKTON / SYNTHESIS-I**. The full design rationale lives in
> [`TEKTON_MASTER_SPEC.md`](TEKTON_MASTER_SPEC.md); the complete user manual is
> [`MANUAL.md`](MANUAL.md) (every code example verified against the running system).

KOMPOSOS **interprets**: it stores relations, verifies claims, factors existing
structure. OPERADUM **constructs**: it stores *operations*, generates valid
assemblies, and synthesizes artifacts that satisfy a specification.

| | KOMPOSOS-IV (interpret) | OPERADUM (design) |
|---|---|---|
| Primitive | Morphism `A â†’ B` | Operation `(Aâ‚,â€¦,Aâ‚™) â†’ B` |
| Substrate | Enriched category | Coloured operad, symmetric monoidal |
| Verb | "are these related?" | "what wirings are valid / best-ranked?" |
| Enrichment | Quantale confidence | Resource/figure monoid |
| Truth | Verification (verdict) | Realizability (an executable artifact) |
| Copyability | Cartesian (free copy) | **Substructural** (resources are spent) |

They are duals at the bottom (both symmetric-monoidal) and compose:
an OPERADUM design **compiles into** a KOMPOSOS morphism graph.
**Synthesize, then verify.**

## Shared Delivery Architecture

This repo is now the canonical delivery home for OPERADUM plus PRONOIA, with a
small `domain_core` package between them:

```text
OPERADUM proposes Candidate
KOMPOSOS adapters gather EvidencePacket
PRONOIA returns PredictionReport with ranking, contradiction, and honesty signals
```

KOMPOSOS remains external. Orion is not part of this architecture. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the maintained map.

---

## What's built (this commit)

A working **Phase 0 substrate** + **Phase 1 synthesis MVP**, mirroring
KOMPOSOS-IV's "one fused runtime class, internal persistence, intrinsic
enrichment, structural hooks" discipline.

```
operadum/
â”œâ”€â”€ core/                      # Layer 2: the fused operadic runtime
â”‚   â”œâ”€â”€ types.py               #   Colour, Operation, Composite, Interface, Spec
â”‚   â”œâ”€â”€ enrichment.py          #   ResourceMonoid + 5 algebras (incl. LINEAR_TOKENS)
â”‚   â”œâ”€â”€ persistence.py         #   SQLite backend (internal â€” never use directly)
â”‚   â”œâ”€â”€ hooks.py               #   structural event registry
â”‚   â””â”€â”€ operad.py              #   THE Operad class (structure+store+cost+exec)
â”œâ”€â”€ gate/                      # the Dual Gate
â”‚   â”œâ”€â”€ type_engine.py         #   TYPE: realizability (Curryâ€“Howard inhabitation)
â”‚   â””â”€â”€ res_engine.py          #   RES:  resource soundness + budget feasibility
â”œâ”€â”€ wright/                    # Layer 3: the write path
â”‚   â”œâ”€â”€ schema.py              #   Spec, Construction, Verdict, BuildResult
â”‚   â””â”€â”€ engine.py              #   WRIGHT â€” energy-routed Tiers 0â€“2
â”œâ”€â”€ core/linear.py             # Phase 2: linear logic â€” Tensor/Lolli/OfCourse + checker
â”œâ”€â”€ core/polytope.py           # Phase 3: associahedra, coherence rewrites, normal forms
â”œâ”€â”€ core/prop.py               # Phase 3: PROP lift â€” resource-aware fork/merge & sharing
â”œâ”€â”€ core/formal_coherence.py   # Phase 3: CoherenceProver (Mac Lane, confluence, conservation)
â”œâ”€â”€ daedalus_core.py           # Layer 4: DAEDALUS generative search (branch & bound)
â”œâ”€â”€ gate/pattern_miner.py      # Phase 3: mine & lift reusable patterns (Level-4 operad maps)
â”œâ”€â”€ wright/solver.py           # WRIGHT Tier 3: resource-constrained synthesis
â”œâ”€â”€ forge/                     # Layer 1: plugin host â€” event bus, capability DI, lifecycle
â”‚   â”œâ”€â”€ core.py Â· events.py Â· plugin.py Â· plugins.py
â”œâ”€â”€ agent.py                   # unified entry point: all layers via Forge
â”œâ”€â”€ core/serialization.py      # Phase 5: wiring DSL (parse/emit) + JSON
â”œâ”€â”€ wright/server.py           # Phase 5: MCP-style SynthesisServer
â”œâ”€â”€ core/plugin_generator.py   # Phase 4: package an operad as a fresh DomainPlugin
â”œâ”€â”€ domains/                   # pluggable content (colours + operations + algebra)
â”‚   â”œâ”€â”€ base.py                #   DomainPlugin ABC + GroundTruthCase
â”‚   â”œâ”€â”€ synthesis_design.py    #   domain 1: organic synthesis-route design (additive)
â”‚   â””â”€â”€ compute_pipeline.py    #   domain 2: data pipeline, peak-memory algebra (max)
â”œâ”€â”€ gate/self_observer.py      # Phase 4: redundant/source/sink structural analysis
â”œâ”€â”€ validation/benchmark.py    # synthesis-accuracy harness (optimum/buildable recall)
â”œâ”€â”€ validation/domain_accuracy.py  # real-world accuracy on a domain + round-trip
â”œâ”€â”€ bridges/
â”‚   â”œâ”€â”€ komposos_bridge.py     #   compile a design â†’ KOMPOSOS morphism graph
â”‚   â””â”€â”€ round_trip.py          #   KomposVerifier â€” KOMPOSOS audits the design
â”œâ”€â”€ integrations/
â”‚   â””â”€â”€ komposos_mof.py        #   real KOMPOSOS-MOF generator/verdicts â†’ OPERADUM assembly
â””â”€â”€ tests/                     # laws, search, coherence, domains, round-trip, self-construction
examples/pipeline_demo.py      # Phase 1: design â†’ build â†’ run â†’ compile, end to end
examples/daedalus_demo.py      # Phase 2: cheapest in-budget design, proven sound
examples/coherence_demo.py     # Phase 3: coherence, certification, patterns, accuracy
examples/domain_roundtrip_demo.py  # domain route â†’ real KOMPOSOS verifies [AGREE]
examples/self_construction_demo.py # Phase 4: mine â†’ lift â†’ observe â†’ package
examples/forge_agent_demo.py       # Layer 1 + Phase 5: Forge â†’ Agent â†’ DSL â†’ server
```

The `Operad` class is simultaneously four things, exactly as KOMPOSOS's
`Category` is: an operadic structure, a SQLite store, a resource-enriched
structure, and an executable structure.

## Quick start

```python
from operadum import Operad, Spec, Wright

op = Operad("text-pipeline")                       # additive-cost monoid by default
op.add_op("tokenize", ["RawText"], "Tokens",    cost={"ms": 2}, fn=str.split)
op.add_op("embed",    ["Tokens"],  "Embedding", cost={"ms": 8}, fn=len)

# Hand WRIGHT a target interface + budget; get a buildable construction back.
result = Wright(op).synthesize(Spec(inputs=("RawText",), output="Embedding",
                                    budget={"ms": 20}))
print(result)                       # [BUILDABLE] (RawText) -> Embedding  tier=1 ...
result.construction.artifact("the quick brown fox")   # runs embed(tokenize(...)) â†’ 4
```

### Figures, not just cost

`cost={...}` is the compatibility name for a design's **figure vector**. It can
hold money, time, safety risk, confidence, evidence strength, emissions, memory,
labor, compliance debt, rework, or domain-specific quantities. The operad's
resource algebra decides how each figure combines and how WRIGHT ranks designs.

```python
from operadum import Operad, Spec, Wright, SAFETY_FIRST, FASTEST_RECOVERY

def release_operad(monoid):
    op = Operad("release", monoid=monoid)
    op.add_op("quick_close", [], "Released",
              cost={"schedule_delay": 1, "safety_risk": 0.70,
                    "compliance_debt": 1, "confidence": 0.70})
    op.add_op("document_torque_inspect", [], "Released",
              cost={"schedule_delay": 8, "safety_risk": 0.01,
                    "compliance_debt": 0, "confidence": 0.96})
    return op

Wright(release_operad(SAFETY_FIRST)).optimize(Spec((), "Released"))
# -> document_torque_inspect

Wright(release_operad(FASTEST_RECOVERY)).optimize(Spec((), "Released"))
# -> quick_close
```

Use `budget={...}` for upper bounds (`safety_risk <= 0.05`) and
`requirements={...}` for lower bounds (`confidence >= 0.9`). Built-in profiles:
`GENERAL_FIGURES`, `SAFETY_FIRST`, `COMPLIANCE_FIRST`, `FASTEST_RECOVERY`,
`LEAST_DISRUPTIVE`, `EVIDENCE_FIRST`, and `SUSTAINABILITY_FIRST`.

### Lightweight world models

A world model in OPERADUM is not an LLM. It is a small transition shell:

```text
WorldState + action -> predicted next WorldState + figures + evidence
```

`RuleWorldModel` registers cheap Python transition rules, cached scores, or
KOMPOSOS queries, then converts the available one-step actions into OPERADUM
operations. WRIGHT picks the next action under the active figure profile.

```python
from operadum import EVIDENCE_FIRST
from operadum.integrations.komposos_drug_world import (
    build_drug_world_model, initial_drug_state,
)

state = initial_drug_state(drug="Erlotinib", disease="TB", target="EGFR")
choice = build_drug_world_model().choose(
    state,
    monoid=EVIDENCE_FIRST,
    requirements={"evidence_strength": 0.8},
)
print(choice.prediction.action)
```

The drug adapter can read `KOMPOSOS-IV-CHEM-TB` when available, but it also has
deterministic fallbacks for local demos and tests.

### The four verdicts (dual of COG's AGREE/HOLLOW/ORPHAN/REJECT)

| Verdict | Type-realizable | In budget | Meaning |
|---|---|---|---|
| `BUILDABLE` | âœ“ | âœ“ | A sound, in-budget construction exists. Ship it. |
| `OVERBUDGET` | âœ“ | âœ— | A wiring exists but exceeds the resource budget. |
| `ILL_TYPED_GAP` | âœ— | âœ“ | Resources suffice but no type-correct wiring (missing component). |
| `IMPOSSIBLE` | âœ— | âœ— | No realizer under current components. |

### The load-bearing difference: non-cartesian resources

KOMPOSOS is cartesian â€” knowledge copies freely. A resource does not. The
`LINEAR_TOKENS` algebra forbids the diagonal: spend a one-shot permit twice and
the build is rejected.

```python
from operadum import Operad, LINEAR_TOKENS
op = Operad("build", monoid=LINEAR_TOKENS)
# ...a design that consumes the same permit on two branches raises ResourceError.
```

## Run it

```powershell
python -m pytest operadum/tests -q     # 135 passing, 2 skipped
python -m examples.figure_profiles_demo # safest vs fastest figure profiles
python -m examples.drug_world_model_demo # cheap world-model action choice
python -m examples.real_drug_world_model_demo # real KOMPOSOS-CHEM-TB smoke test
python -m examples.pipeline_demo       # the full designâ†’verify loop
```

## Roadmap (from the master spec)

- **Phase 0 â€” Foundations** âœ… operad runtime, persistence, enrichment, `realize()`.
- **Phase 1 â€” Synthesis MVP** âœ… WRIGHT Tiers 0â€“2, Dual Gate, four verdicts.
- **Phase 2 â€” Resources & optimal search** âœ… linear-logic typing (`âŠ—`/`âŠ¸`/`!`),
  DAEDALUS branch-and-bound generative search (Level 1) with memoisation +
  tropical optimality, WRIGHT Tier 3 + `optimize()`, resource-soundness proofs.
- **Phase 3 â€” Higher structure** âœ… Polytope (associahedra, coherence rewrites,
  unique normal forms), PROP lift (resource-aware fork/merge), WRIGHT Tier 4
  certification, formal CoherenceProver (Mac Lane + confluence + *proven*
  conservation), PatternMiner (mine & lift reusable components), plus a
  synthesis-accuracy benchmark (optimum recall = 1.0).
- **Phase 4 â€” Self-construction** âœ… outcome learning (realizability rates),
  autonomous `auto_lift` of mined patterns, `SelfObserver` (redundant/source/
  sink detection), `PluginGenerator` (package the self-extended operad as a
  fresh DomainPlugin: mine â†’ lift â†’ package â†’ reload).
- **Phase 5 â€” Integration & scale** âœ… wiring DSL (`parse_wiring`/`to_wiring_dsl`),
  JSON serialization, MCP-style `SynthesisServer`. (KOMPOSOS round-trip already
  runs against the real engine; sharded operads remain future work.)
- **Layer 1 â€” Forge** âœ… the hot-loadable plugin host: event bus, capability DI
  (a plugin requiring `component_store` starts only once one provides it),
  lifecycle. All layers wired through it via the unified `Agent`.

### One object: the Agent

```python
from operadum import Agent, Spec, SynthesisDesignDomain
agent = Agent.for_domain(SynthesisDesignDomain())     # boots Forge + all layers
agent.optimize(Spec(("Benzene",), "Paracetamol"))     # cheapest route
agent.certify(spec)                                   # Tier-4 certificate
agent.verify(design.composite)                        # KOMPOSOS round-trip
agent.self_extend()                                   # mine history â†’ new components
```

`Agent` registers the component store, synthesizer (WRIGHT), search (DAEDALUS),
and coherence (Polytope) as Forge capabilities and starts them in dependency
order. The MCP-style `SynthesisServer` wraps it: `handle({"method": "optimize",
"params": {...}})` â†’ JSON in, JSON out.

### Eight domains, one substrate

| Domain | Algebra | Shape | Designed / verified by |
|---|---|---|---|
| `synthesis-design` | additive (USD) | tree | cheapest route |
| `compute-pipeline` | max (peak MB) | tree | lowest bottleneck |
| `manufacturing` | multiset (BOM) | tree | lightest bill of materials |
| `program-synthesis` | additive (ops) | tree | **input/output examples** |
| `quantum-circuit` | additive (gates) | tree | **2Ã—2 unitary matrices** |
| `logic-circuit` | additive (gates) | **network** | **truth table** (XOR from NAND) |
| `topological-network` | additive (modules) | **network** | **graph invariants** (cycle rank) |
| `materials` | additive (MW) | tree + net | **real MOF linker data + KOMPOSOS** |

The same WRIGHT/DAEDALUS lays out a synthesis route, a quantum circuit, a logic
network, and a MOF â€” *the math doesn't know which domain it's in* (spec Â§18). Run
`python -m examples.full_showcase` to see all eight.

OPERADUM also designs **networks**, not just trees: `operadum.core.Diagram` is the
DAG / string-diagram layer (distinguished inputs, fan-out, sharing), and
`synthesize_diagram` searches DAGs against a validator â€” e.g. **XOR from NAND
alone**, which no tree can express.

## Testing accuracy

Three notions of "accuracy", available at different stages:

1. **Engine correctness** (now) â€” type-safety, resource-soundness, cost
   conservation, optimality, normal-form uniqueness â€” proven and tested.
   `python -m operadum.validation.benchmark` reports **optimum recall**: over
   random operads with a brute-forced known optimum, does `optimize()` recover
   the true minimum? (Currently 1.0.)
2. **Synthesis quality** (now, growing) â€” the benchmark harness measures
   optimum/buildable recall; richer benchmark domains land in Phase 4.
3. **Real-world design accuracy** (now, via the first domain plugin) â€” does a
   synthesized design work in a real domain? The `synthesis-design` domain
   (organic synthesis-route planning) ships with ground truth; the harness
   measures **buildable accuracy**, **optimum recall**, and **roundtrip agree**
   (all 1.0). Each design is audited by the **real KOMPOSOS-IV engine**:
   `python -m examples.domain_roundtrip_demo` â†’ `[AGREE] engine=komposos`.

### The KOMPOSOS round-trip

```python
from operadum import SynthesisDesignDomain, Spec, Wright, KomposVerifier
op = SynthesisDesignDomain().build_operad()
design = Wright(op, max_depth=8).optimize(Spec(("Benzene",), "Paracetamol")).construction
KomposVerifier(komposos_path=r"...\KOMPOSOS-IV-CHEM").verify(design.composite, op)
# [AGREE] engine=komposos composed=0.2725 expected=0.2725 (sound)
```

OPERADUM designs the cheapest route, compiles it to a morphism graph, and the
real KOMPOSOS `Category` ingests and verifies it. **Round-trip soundness** is a
theorem here: `product(confidences) == cost_to_confidence(total cost)` â€” the
additive-cost â†’ multiplicative-confidence map is an exact monoid homomorphism,
so both engines agree on the same structure. (Under non-additive monoids the map
is lossy â†’ verdict `HOLLOW`, matching honest limitation #7.)

### Chemistry is tandem, not head-to-head

For MOF chemistry, KOMPOSOS remains the chemistry engine: it generates linker
SMILES from the real linker cache, validates with RDKit, and scores CAT/ZFC
verdicts. OPERADUM consumes those screened linkers as typed operations and adds
assembly constraints, resource accounting, search, and the KOMPOSOS round-trip.

```python
from operadum.integrations.komposos_mof import (
    KompososMOFSpec,
    design_mof_with_komposos,
)

result = design_mof_with_komposos(
    KompososMOFSpec(
        exact_atoms=22,
        num_candidates=50,
        require_all_agree=True,
        required_groups=["carboxyl"],
    )
)
print(result.selected_linker["smiles"])
print(result.round_trip)  # [AGREE] when the assembled design audits cleanly
```

### Adding a domain â€” one call

```python
class MyDomain(DomainPlugin):
    name = "my-domain"
    def colours(self):    return ["A", "B", "C"]
    def operations(self): return [...]                # typed, costed, executable
    def resource_algebra(self): return ADDITIVE_COST
op = MyDomain().build_operad()                        # substrate does the rest
```

## License

Proprietary / commercial â€” `LicenseRef-Proprietary-Commercial`.
Â© 2026 James Hawkins.

