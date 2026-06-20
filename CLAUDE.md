# KOMPOSOS‑V — guidance for Claude

This is the **integration repo**: six categorical engines over one shared
`Category`. It is the substrate. The sub‑package `operadum/` has its own
`CLAUDE.md` — read it before touching OPERADUM/PRONOIA.

## ⚑ Active project: Silicon co‑design domain

The substrate now has a chosen vertical: **semiconductor co‑design**
(`domains/silicon/`, being built). **Before doing project work, read
`docs/SILICON_PLAN.md` (the master plan), and at the end of every session append
a dated entry to `docs/SESSIONS.md`.** Durable cross‑session facts go in
`MEMORY.md` + harness memory.

The project is **mostly integration, not invention** — ~70% exists:
- `KOMPOSOS-IV-CHEM/semiconductor_bridge/` = materials + 5 scorers + heterostructure
  analyzer + Category integration; `composition_engine/designer.py` = inverse designer.
- `KOMPOSOS-GRID/domains/grid/` = the pipeline pattern (sheaf coherence → flow
  geometry → waste ledger → agent CLI).
- The one new piece is a **`netlist_bridge`** (layout/netlist → `Category`).

See the plan for the data sources, the rung roadmap (0→3), and `domains/silicon/`
target layout. **Hardware reality: 32 GB Ryzen 9 laptop, CPU only, offline after
data download. Never simulate silicon physics — ingest tool output as evidence.**

## The one idea

**Structure substitutes for scale.** The system's value is that every kept
capability comes with a checkable receipt: it was *built, executed, verified,
grounded, and judged*. Your job when extending it is to **preserve that receipt**,
never to bypass it for convenience.

## Architectural invariants (do not break these)

1. **Proposal vs verification is sacred.** Generators/strategies/embeddings — and,
   for silicon, **material scores and curvature** — only *propose*. The symbolic
   layer (composition, COG, ZFC, honesty) *verifies*. Never let a proposal mechanism
   write to memory directly or stand in for a verdict.
2. **Embeddings are a proposal‑side Yoneda prior — nothing more.** `data/embeddings.py`
   may seed candidate edges (similarity); it must never gate, verify, or persist.
3. **n‑ary relations use operads, not hypergraphs.** Category theory already has
   the right tool (`categorical/operads.py`, OPERADUM). Do not add a hypergraph layer.
4. **Honesty + grounding are mandatory at every persistence point.** A claim enters
   memory only if COG ≠ REJECT *and* `HonestyGate` finds it grounded in committed
   evidence. The honesty claim MUST be serialized in the same vocabulary as the
   evidence (`"src name tgt conf"` lines) or grounding reads ~0 — see
   `loop._supporting_claim()`.
5. **A filled gap is a runnable, verified composite, not an assertion.**
   `ExecutableSynthesizer` builds the composite, runs it, and checks path‑coherence
   (multiple spines must agree). Verify‑fail rolls back.
6. **Rollback must actually remove.** Persistence is real; use `Category.remove_morphism`.
7. **The loop is embedding‑free by default.** `embeddings=None` (structural only),
   `"auto"` to fit a real engine on the live graph, or pass an engine.
8. **Evidence tiers are honest.** Proxy/structural results are `structural_only`;
   only real tool output (STA/SPEF/SPICE/DFT, measured data) is `measured`. Never
   promote a proxy to measured. (`core/evidence_tiers.py`, GRID `waste_ledger.py`.)

## The loop (`core/loop.py`)

```
observe (OPTIMUS | ConjectureEngine) → design (OPERADUM) → predict (PRONOIA, honest_rank)
→ ground (ExecutableSynthesizer) → remember‑gate (HonestyGate) → judge (COG) → keep/rollback
```

OPERADUM/PRONOIA are optional (loaded from `operadum/`); the loop degrades to
OPTIMUS+HOST+COG if absent.

## Layout

| Path | Role |
|---|---|
| `core/loop.py` | the self‑improvement spine + `_observe`/`_fill_gap`/`_supporting_claim` |
| `core/generator.py` | `GenerativeLoop` — compositional self‑improvement (NAND→XOR demo) |
| `core/executable_synthesis.py` | build+run+verify the composite for a gap (#1 grounding) |
| `core/honesty_gate.py` | commit‑time grounding gate (#4), reusable for any KG write path |
| `core/scoreboard.py` | falsifiable recall/precision benchmark |
| `core/category.py` | the fused `Category` runtime (structure + persistence + enrichment) |
| `core/bridge.py` | `Bridge` ABC — load domain data into a `Category` (objects/morphisms/score) |
| `core/evidence_tiers.py` | MEASURED → … → SPECULATIVE evidence annotations |
| `oracle/strategies.py` | `create_all_strategies` registry + `InferenceStrategy` base |
| `oracle/conjecture.py` | `ConjectureEngine` — proactive observe |
| `topology/persistent_sheaves.py` | real H⁰/H¹ sheaf cohomology (gluing obstructions) |
| `categorical/boundary_profunctor.py` | boundary/seam structure |
| `data/embeddings.py` | soft‑Yoneda embeddings backend (proposal‑side only) |
| `domains/` | verticals. `circuits.py`, `numeric.py` exist; **`silicon/` is the active build** |
| `cog/`, `zfc/`, `categorical/`, `operadum/` | judge, logic, math engine room, construct+predict |
| `docs/SILICON_PLAN.md`, `docs/SESSIONS.md` | **master plan + session log — read/update these** |

## How to extend

- **Build the silicon domain** → follow `docs/SILICON_PLAN.md` §6 target layout;
  lift from GRID (`domains/grid/`) and CHEM (`semiconductor_bridge/`). Route every
  write through the honesty/COG gate; tag evidence honestly.
- **Add an oracle strategy** → subclass `InferenceStrategy` (`predict(source,target)
  -> List[Prediction]`), then add a guarded `try/import/append` in
  `create_all_strategies`. COG Tier‑4 picks it up automatically.
- **Add a loop observer** → return `{source,target,via,path_confidence}` dicts from
  a `_observe_*` method and dispatch in `_observe`.
- **Add a persistence path** → route every write through `HonestyGate.check_claim`;
  do not write unconditionally.
- **Touch OPERADUM/PRONOIA** → read `operadum/CLAUDE.md` first; preserve the
  proposal/verification and type/resource‑gate separations.

## Conventions

- Python ≥ 3.10. Core loop/oracle/scoreboard/domain cores are **numpy + stdlib**;
  keep them so. Heavy tools (OpenLane, mp‑api) are *data producers*, run out‑of‑band,
  never imported by core.
- SPDX header + a module docstring that states the engine/dual it belongs to.
- Dataclasses for data, fused runtime classes for behaviour (mirror `Category`).
- Tests prove the laws and the gates, not just the happy path.
- **Process:** read `docs/SILICON_PLAN.md` at session start; append `docs/SESSIONS.md`
  at session end; fix the plan in‑session if direction changes.

## Commands

```powershell
python -m core.loop                 # run the loop
python -m core.generator            # compositional self-improvement (circuits demo)
python -m core.scoreboard           # measure it (PASS/FAIL)
python -m pytest tests/ -q          # test suite
```
</content>
