# MEMORY — KOMPOSOS‑V decision log & state

Durable, non‑obvious facts and decisions for anyone (human or agent) picking this
up. For *how to work in the repo*, see `CLAUDE.md`; for *what it is*, see `README.md`.

## Architecture decisions

- **Structure substitutes for scale.** The differentiator vs. an LLM is the
  *checkable receipt* on every kept capability (built→executed→verified→grounded→judged).
  Optimize for that, not for raw capability.
- **Proposal vs verification split is the core discipline.** Strategies, candidate
  generators, and embeddings only propose. The symbolic layer (composition, COG,
  ZFC, honesty) verifies. Nothing on the proposal side may persist or gate.
- **Embeddings = soft Yoneda prior, proposal‑side only.** Justified by Yoneda (an
  object *is* its morphism profile; an embedding approximates it). Helps the
  cold‑start/sparse‑graph problem. Never used as a verifier.
- **No hypergraph.** n‑ary relations already have the categorically‑correct tool —
  operads/OPERADUM. A hypergraph layer would be a weaker, redundant duplicate.
- **Honesty must be total.** Grounding (MDL, PRONOIA) gates every persistence point,
  not just route design. A self‑improving loop that can persist ungrounded claims
  reward‑hacks itself into delusion.

## Current state (2026‑06‑17)

- **Six engines** present over one shared `Category`. This is the integration repo /
  substrate; `domains/` is intentionally empty (no vertical yet). `komposos_kg/` is
  currently empty — when built, its write path MUST go through `HonestyGate`.
- **Oracle**: 21 strategies via `oracle.strategies.create_all_strategies`; this is the
  runtime registry COG Tier‑4 iterates. `CategoricalOracle` is the orchestrator.
  Recently promoted: `horn_filling` (generic, from the import‑poisoned `oracle/horns.py`
  diagnostic) and a generalized `conjecture_gap`. Many `oracle/*` files are pharma
  diagnostics or domain‑bound — keep the base registry domain‑pure.
- **ConjectureEngine** (`oracle/conjecture.py`) is the proactive observer; its
  `surface_candidates()` runs oracle‑free (no embeddings). Wired into the loop as
  `observer="conjecture"`.
- **Embeddings** (`data/embeddings.py`): real backend (was a stub). Deterministic
  feature hashing + `fit(category)` soft‑Yoneda structural vectors; optional
  sentence‑transformers via `model=`. Unblocked `CategoricalOracle` and scored
  `conjecture()`.
- **The loop has gates now** (`core/loop.py`):
  - #1 grounding — `ExecutableSynthesizer` builds/runs/verifies the composite (path‑coherence).
  - #2 honesty — `HonestyGate` requires grounding ≥ threshold in committed evidence;
    persistence = `(COG ≠ REJECT) AND honest`. Claim must be in evidence vocabulary.
  - #3 measurement — `core/scoreboard.py` (recall/precision/F1, falsifiable: 1.0/1.0 full,
    0.0 when a supporting edge is removed).
  - #4 scale — `embeddings="auto"` turns on semantic proposals; scoreboard shows
    precision holds (gates absorb the extra proposals).
- **Bug fixed**: `Category.remove_morphism` did not exist → every rollback (incl. COG
  REJECT) was a silent no‑op and rejected edges persisted. Added; rollbacks now remove.
- **Tests**: 140 passing (`python -m pytest tests/ -q`).

## Active project: Silicon co‑design domain (2026‑06‑19)

The chosen real domain is **semiconductor co‑design**. Full plan in
`docs/SILICON_PLAN.md`; running log in `docs/SESSIONS.md`. Key facts:

- **It is mostly integration, not invention.** ~70% already exists across repos:
  - `KOMPOSOS-IV-CHEM/semiconductor_bridge/` — real materials + 5 scorers
    (lattice/band/thermal/process/degradation), heterostructure analyzer, named
    real + `PROBLEMATIC_*` stacks, `integration.py` (Category + curvature). Plus
    `composition_engine/designer.py` = inverse designer ("Crystal Dreamer") and
    `cross_bridge/metal_semiconductor.py`.
  - `KOMPOSOS-GRID/domains/grid/` — the pipeline pattern: `coherence.py` (sheaf
    GLUE/TENSION/CONTRADICT), `flow_geometry.py` (Ricci + Fiedler), `waste_ledger.py`
    (evidence tiers), `agent_tools.py`/`agent_server.py` (local‑agent CLI).
  - `KOMPOSOS-III-LAMBDA-max-3D-fume` — **not relevant** (protein/fragrance); only
    `geometry/ricci.py` + `spectral.py` overlap, already wrapped by GRID.
- **The one new piece = `netlist_bridge`** (layout/netlist → `Category`). Materials
  layer done; topology/layout layer is the new work. Mirror GRID `ingest.py`.
- **Data (free, offline after download):** Materials Project (`mp-api`, CHEM already
  has `download_mp_data.py`); SKY130 open PDK; OpenLane/OpenROAD to mint DEF/SPEF/
  netlists locally; EPFL/ISCAS + ISPD benchmarks. Never needs foundry data. Lives
  outside git (`.gitignore`).
- **Invariant for silicon:** scores/curvature are proposals; verdict = COG≠REJECT +
  HonestyGate grounding. **No physics simulation on the laptop** — ingest tool output
  as evidence. Proxy = `structural_only`, real tool output = `measured`.
- **Roadmap:** Rung 0 (synthetic netlist) → 1 (material bridge + verdicts) →
  2 (netlist_bridge on real OpenLane output) → 3 (waste ledger + agent CLI).
- **Process rule:** every session, read `docs/SILICON_PLAN.md` and append to
  `docs/SESSIONS.md`.

## Known gaps / next steps

- **Next concrete step: build Rung 0** — `domains/silicon/synthetic.py` + a
  sheaf/curvature pass printing a congestion corridor / Fiedler seam on a toy chip.
- Everything is validated on **synthetic graphs**. Highest‑leverage next move: point
  the loop at a **real domain** (now chosen: silicon) so the scoreboard runs on data that matters.
- `komposos_kg` has **no honesty gate yet** (it's empty) — wire `HonestyGate` when built.
- The richer PRONOIA `sincerity()` verdict engine (HIDDEN_STEP/FABRICATION/DISTORTION)
  exists but is only used in OPERADUM demos, not the unified loop.
- Host seam: `core/host.py` is FORGE‑backed (the repo's own "Orion"); real Orion can
  be swapped behind this one interface later.
