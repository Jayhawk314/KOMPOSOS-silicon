# OPERADUM — guidance for Claude

OPERADUM is a categorical **design** engine: the constructive mirror of
KOMPOSOS-IV (`../KOMPOSOS-IV-CHEM`), which is an interpretive engine.
Renamed from **TEKTON**; the full spec is `TEKTON_MASTER_SPEC.md`.

## The one idea

- KOMPOSOS primitive = **morphism** `A → B` (relate two existing things).
- OPERADUM primitive = **operation** `(A₁,…,Aₙ) → B` (a rule for *building* a B).
- Designs are **composites**: well-typed wiring trees in the free operad.
- Costs live in a **ResourceMonoid** and are **non-cartesian** by default
  (the `LINEAR_TOKENS` algebra forbids reusing a spent resource — the single
  most important difference from cartesian KOMPOSOS).

## Architectural invariants (do not break these)

1. **`Operad` is the fused runtime** — it IS structure + persistence + cost +
   execution, mirroring KOMPOSOS's `Category`. One class, zero translation seams.
2. **`Operad` owns persistence.** Never touch `SQLiteBackend` directly.
3. **Cost is intrinsic.** `op.cost` IS the monoidal weight, not metadata.
4. **`compose()` enforces TYPE safety; the RES gate enforces resource soundness.**
   `compose` raises `TypeError` on a colour mismatch at build time. A resource
   violation (e.g. linear reuse) is *not* refused by `compose` — it is reported
   by `ResEngine`. Keep that separation.
5. **WRIGHT is the operad's write path**, tightly coupled — not a peer plugin.
6. **The KOMPOSOS bridge stays dependency-free.** `compile_to_komposos` emits a
   plain graph dict; the live-`Category` adapter imports KOMPOSOS lazily.

## Layout

| Path | Role |
|---|---|
| `operadum/core/operad.py` | THE fused operadic runtime |
| `operadum/core/types.py` | Colour, Operation, Composite, Interface, Spec |
| `operadum/core/enrichment.py` | ResourceMonoid + 5 algebras |
| `operadum/core/persistence.py` | SQLite (internal) |
| `operadum/core/linear.py` | linear logic: Tensor/Lolli/OfCourse + LinearChecker |
| `operadum/core/polytope.py` | associahedra, coherence rewrites, unique normal form |
| `operadum/core/prop.py` | PROP lift: resource-aware fork/merge & sharing |
| `operadum/core/formal_coherence.py` | CoherenceProver: Mac Lane + confluence + conservation |
| `operadum/daedalus_core.py` | DAEDALUS generative search (branch & bound) |
| `operadum/gate/` | Dual Gate: TYPE + RES + PatternMiner (System-3 analog) |
| `operadum/wright/` | WRIGHT synthesizer: Tiers 0–3, `optimize()`, `certify()` |
| `operadum/validation/benchmark.py` | synthesis-accuracy harness (optimum recall) |
| `operadum/bridges/komposos_bridge.py` | design → KOMPOSOS morphism graph |
| `operadum/tests/` | operad laws, four verdicts, search, coherence, patterns |

## How to extend

- **Add a synthesis tier** → a `_tierN` method on `Wright` that returns
  candidate `Composite`s; energy routing already tries them cheapest-first.
- **Add a resource algebra** → a `ResourceMonoid` in `enrichment.py` + registry
  entry. `combine` must be associative with `unit` as identity.
- **Add a domain** → colours + operations + a resource algebra. The substrate
  does the synthesis; domains bring only content (master spec §18).

## Conventions

- Match KOMPOSOS-IV's file idiom: SPDX header, module docstring that states the
  KOMPOSOS dual, dataclasses for data, fused runtime classes for behaviour.
- Python ≥ 3.10, standard library only (no third-party runtime deps yet).
- Tests mirror KOMPOSOS's discipline: prove the laws, not just the happy path.

## Commands

```powershell
python -m pytest operadum/tests -q     # full suite (currently 24 passing)
python -m examples.pipeline_demo       # design → build → run → compile loop
```
