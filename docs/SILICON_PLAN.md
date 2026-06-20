# KOMPOSOS‑V — Silicon Co‑Design Plan

> **This is the master plan. Read it at the start of every session.**
> It is the source of truth for *what we are building and why*. When reality and
> this doc disagree, fix the doc in the same session (and log it in
> `docs/SESSIONS.md`). Code is the source of truth for *how things work* — this
> doc must never contradict the code.

---

## 0. One sentence

Build a **semiconductor co‑design domain** on the KOMPOSOS‑V substrate that takes
a chip's *materials* and its *layout/netlist*, runs categorical + sheaf + flow‑geometry
analysis over them, and emits an **honest, receipt‑backed waste ledger and action
portfolio** — never a hollow claim, all on a 32 GB Ryzen 9 laptop, offline after
data download.

---

## 1. Why this is mostly an integration job, not an invention job

We audited four repos by **reading the code** (docs were misleading). Findings:

### `KOMPOSOS-IV-CHEM` — the materials side already exists
- `semiconductor_bridge/` is real and working:
  - `material_properties.py` — Si, Ge, GaAs, GaN, InP, SiC, MoS₂/WS₂ (2D), etc., each with bandgap (Eg), lattice constant, mobility, crystal system.
  - `interaction_scoring.py` — the **5 scorers**: `score_lattice_match`, `score_band_alignment`, `score_thermal_compatibility`, `score_process_compatibility`, `score_degradation_penalty`.
  - `interface_validator.py` + `heterostructure_analyzer.py` — validate a stack, find the weakest interface (bottleneck), predict degradation. Named stacks baked in: `GAAS_ALGAAS_HEMT`, `GAN_ALGAN_POWER`, `SIC_GAN_POWER`, `SI_SIGE_BICMOS`, `MOS2_WS2_2D`, plus deliberately broken `PROBLEMATIC_*` cases.
  - `integration.py` — already builds a `Category`, computes curvature + heterostructure coherence.
  - `cross_bridge/metal_semiconductor.py` — the metal↔semiconductor junction (interconnect↔gate).
- `composition_engine/designer.py` — the **inverse designer ("Crystal Dreamer")**: target properties → candidate formulas via 4 strategies; backed by `mp_loader.py` (Materials Project cache) + `formation_energy.py`.

### `KOMPOSOS-GRID` — the analysis pipeline pattern already exists
The whole pipeline shape exists, pointed at power grids:
- `domains/grid/coherence.py` — sheaf/presheaf gluing with **GLUE / TENSION / CONTRADICT** verdicts, written back as `coheres_with` / `disputes` morphisms.
- `domains/grid/flow_geometry.py` — **Ollivier‑Ricci curvature + Fiedler spectral** seam detection (recovers the East/West grid split unprompted).
- `domains/grid/waste_ledger.py` — unified ledger with **evidence tiers** (`measured > measured_proxy > validated_hypothesis > structural_only`).
- `domains/grid/action_portfolio.py`, `agent_tools.py`, `agent_server.py` — the local‑agent CLI (`ba`, `path`, `bottlenecks`, `seam`, `whatif --cut ...`).

### `komposos-v` (here) — the substrate
`Category` runtime, COG judge, ZFC dual‑engine, `topology/persistent_sheaves.py`
(real H⁰/H¹ cohomology), `core/loop.py` + `core/generator.py` (self‑improvement),
`core/evidence_tiers.py`, the simple `Bridge` ABC, `core/scoreboard.py`.

### `KOMPOSOS-III-LAMBDA-max-3D-fume` — mostly NOT relevant
It's protein structure / fragrance (AlphaFold/ESM2, side‑chain packing). Its only
reusable bits are `geometry/ricci.py` + `geometry/spectral.py` (curvature/spectral),
which GRID already wraps. **De‑prioritized.**

### Conclusion
~70% exists. The project = **port GRID's domain pipeline pattern + CHEM's material
bridges onto the V substrate as `domains/silicon`.**

---

## 2. The one genuinely new piece — the `netlist_bridge`

The **materials** layer is done (`semiconductor_bridge` = *what it's made of*).
The **layout/netlist** layer does not exist yet (*how it's wired & placed*).

> **New work = a `netlist_bridge` / `layout_bridge`**: ingest a chip's connectivity
> (netlist) + physical placement (DEF/floorplan) + parasitics (SPEF) and turn it
> into a `Category` (nets → wires as morphisms) so curvature / Fiedler / sheaf run
> on real silicon topology.

In GRID this is `ingest.py` + `sources/eia930.py`. We build the silicon equivalent.

---

## 3. The architecture invariant we must never break

Same as the substrate's core discipline:

- **Material scores and curvature are PROPOSALS** (Yoneda‑style priors, like embeddings).
- **The VERDICT is COG ≠ REJECT + grounding in committed evidence** (HonestyGate).
- On this laptop we **never simulate silicon physics**. We ingest OpenLane / Materials
  Project outputs as *evidence* and run *structure* on them. Proxy scores enter the
  ledger as `structural_only`; only real tool output (STA/SPEF/SPICE/DFT) is `measured`.

This is the differentiator vs. GNN placers: they pattern‑match; we carry a receipt.

---

## 4. Data we need (free, open, offline‑after‑download)

GRID never hits live APIs — it bulk‑downloads CSVs once (`EIA930_*.csv`) and
processes offline. Same playbook for silicon:

| Layer | Source | What you get | Notes |
|---|---|---|---|
| **Material properties** | **Materials Project** (`mp-api`) | bandgap, lattice, formation energy | CHEM already has `download_mp_data.py` + gzipped cache; needs a free API key, download once |
| **Open PDK** (cells, tech, layer stack) | **SkyWater SKY130** (also IHP SG13G2, GF180) | LEF (cell geometry), tech rules | the standard‑cell + metal‑stack reference |
| **RTL to synthesize** | **OpenCores**, RISC‑V cores (Ibex, PicoRV32); EPFL + ISCAS85 benchmark netlists | real logic | small designs run fine on the laptop |
| **Generate your own layouts** ⭐ | **OpenLane / OpenROAD** (open RTL→GDSII) | **DEF** (placement), **SPEF** (parasitics), **gate netlists**, STA reports | this *is* our "EIA‑930 download," self‑minted — the core input |
| **Pre‑made placement benchmarks** | **ISPD 2005/2006/2011** (bookshelf format) | industrial‑derived netlists + floorplans | for testing geometry without running OpenLane |

**Key unlock:** no foundry data required. OpenLane on a small open core + SKY130
mints real DEF/SPEF/netlists locally. Materials Project covers chemistry. All free,
all offline after first download.

**Data lives outside git** — see `.gitignore` (`data/cache/`, `*.def`, `*.spef`,
`*.gds*`, large CSVs). Each loader degrades gracefully when its cache is absent
(mirror `mp_loader.py`'s "no cache → fall back to baseline").

### Sources (verified June 2026)
- OpenLane / OpenROAD: https://openlane.readthedocs.io/ · https://github.com/The-OpenROAD-Project/OpenLane
- Materials Project API: https://docs.materialsproject.org/downloading-data/using-the-api · https://next-gen.materialsproject.org/api
- EPFL / ISCAS85 verilog netlists: https://github.com/jpsety/verilog_benchmark_circuits
- ISPD benchmark background: https://vlsicad.ucsd.edu/Publications/Conferences/313/c313.pdf

---

## 5. The roadmap — rungs, each runnable before the next

Build a thing that runs Friday. Don't build the cathedral.

### Rung 0 — Prove the substrate carries silicon  *(no real data)* ✅ DONE (2026‑06‑19)
- `domains/silicon/synthetic.py` — toy "barbell" chip (two cores + one bus) → `Category`.
- Runs `geometry/ricci.py` (congestion corridors) + `geometry/spectral.py` (Fiedler seam)
  + inline GLUE/TENSION/CONTRADICT coherence (mirrors GRID `coherence.py`).
- `tests/test_silicon_synthetic.py` — 4 falsifiable tests, all pass.
- **Result:** bus wire is the most‑negative corridor; Fiedler splits the two cores
  (cut = the bus); the unrouted "ghost" net fires CONTRADICT. Plumbing confirmed.
- **Note:** used inline coherence, not `topology/persistent_sheaves` — the full sheaf
  filtration is overkill for a toy; Rung 2 upgrades to it on real layout data.

### Rung 1 — Real materials, real verdicts  *(lift from CHEM)* ✅ DONE (2026‑06‑19)
- Ported CHEM material engine: `materials_data.py` (28 materials, cited) + `scoring.py`
  (5 scorers) + `material_bridge.py` (validator, `analyze_stack`, `MaterialBridge(Bridge)`,
  `verdict_for_interface`).
- Verdict pipeline: propose (5 scorers) → physics gate (viability/lattice veto) →
  **COG `check_claim`** → **HonestyGate** grounding (claim grounded in its own committed
  component‑score edges, invariant #4). AGREE persists; HOLLOW/REJECT do not.
- `tests/test_silicon_material_bridge.py` — 11 tests; full suite 155 passing.
- **Result:** `GAN_ALGAN_POWER` → AGREE; `PROBLEMATIC_GAN_GAAS` → REJECT (lattice veto). ✓
- **Note:** omitted CHEM's `oracle.typed_morphism` learned prior (proposal‑side extra,
  not needed). SiC lookup key is `SiC_4H` (formula `4H-SiC`).

### Rung 2 — Real layout  *(the new `netlist_bridge`)* ✅ DONE (2026‑06‑19, sample stage)
- `domains/silicon/netlist_bridge.py` — `parse_def` + `parse_spef` (real LEF/DEF 5.8 +
  IEEE‑1481 grammar), `NetlistBridge(Bridge)`, `analyze_layout`. Star connectivity;
  power/clock/high‑fanout nets skipped.
- `domains/silicon/flow_geometry.py` — shared Ricci+Fiedler geometry; Rung 0 now
  delegates to it.
- Committed fixtures `samples/tiny_core.def` + `.spef` (option 2: no toolchain needed).
- Robustness tested for real OpenLane output: routing‑coordinate parens ignored,
  USE CLOCK/POWER skipped, missing SPEF degrades, multi‑line nets.
- `tests/test_silicon_netlist_bridge.py` — 9 tests; full suite 164 passing.
- **Result:** on the sample, `n_bus` = congestion bottleneck, Fiedler seam splits the
  two cores (cut = `n_bus`), SPEF flags `n_bus` highest‑load (measured_proxy, distinct
  from the structural proposal).
- **Validated on REAL silicon (2026-06-20):** instead of the heavy local OpenLane flow
  (Docker/WSL was wedged for hours), downloaded OpenROAD's committed routed test layout
  `gcd.def`/`gcd.spefok` (real GCD) → `data/openlane/` (gitignored). `netlist_bridge`
  parsed it (423 blocks, 785 wires), produced real Ricci corridors + Fiedler seam, and
  the agent `ledger` produced 12 tiered claims. Added SPEF `*NAME_MAP` resolution.
  **A downloaded real DEF/SPEF == a locally generated one for validation.** Full local
  OpenLane generation is now optional/deferred, not on the critical path.
- RTL↔layout *coherence* on real data still needs a verilog netlist parser (deferred).

### Rung 3 — Silicon waste ledger + agent CLI  *(clone GRID shape)* ✅ DONE (2026‑06‑19)
- `domains/silicon/waste_ledger.py` — `WasteClaim`/`WasteLedger`, 4 evidence tiers,
  `claims_from_layout` + `claims_from_stack`, `action_portfolio()` (ready_for_scoping /
  validate_proxy / review_required), json/md/csv exports.
- `domains/silicon/agent_tools.py` — CLI: manifest, corridors, seam, ledger, interface,
  stack, `whatif --isolate <block>`. Every command emits JSON with `summary` + `provenance`.
- `tests/test_silicon_waste_ledger.py` — 10 tests; full suite 174 passing.
- **Result:** every claim carries an evidence tier + provenance; SPEF cap=measured_proxy,
  geometry=structural_only, material defect=validated_hypothesis — no invented numbers.
  End-to-end pipeline runs on the sample.

### Futures (after Rung 3)
- **Self‑learning:** verified material substitutions / routing fixes become primitives
  for the next `GenerativeLoop` pass (exactly like circuits grows NAND→XOR).
- **Automated lab simulation, iterated:** swap proxy scorers for real SPICE/DFT calls
  as *evidence*, upgrading ledger claims `structural_only → measured` in place.

---

## 6. Target layout for `domains/silicon/`

| File | Lifts from | Role |
|---|---|---|
| `synthetic.py` | GRID `synthetic.py` | toy netlist generator (Rung 0) |
| `netlist_bridge.py` | GRID `ingest.py` + V `Bridge` | DEF/SPEF/netlist → `Category` (Rung 2) |
| `material_bridge.py` | CHEM `semiconductor_bridge` | materials + 5 scorers → `Category` (Rung 1) |
| `coherence.py` | GRID `coherence.py` | RTL↔netlist↔layout sheaf gluing |
| `flow_geometry.py` | GRID `flow_geometry.py` | Ricci curvature + Fiedler seams |
| `waste_ledger.py` | GRID `waste_ledger.py` | tiered, provenance‑backed claims (Rung 3) |
| `agent_tools.py` | GRID `agent_tools.py` | local‑agent CLI (Rung 3) |
| `sources/` | GRID `sources/` + CHEM loaders | data loaders w/ graceful degradation |

---

## 7. Constraints (hard)

- **Hardware:** HP OmniBook, 32 GB RAM, AMD Ryzen 9, **CPU only**.
- **Dependencies:** core stays numpy + stdlib (mirror substrate). Heavy/optional
  tools (OpenLane, mp‑api) are *data producers*, run out‑of‑band, never imported by core.
- **Offline:** everything runs offline after the one‑time data download.
- **Honesty:** no hollow claims — ever. Proxy ≠ measured. Rollback must actually remove.

---

## 8. Working agreement (process)

- **Every session:** read this plan, then append a dated entry to `docs/SESSIONS.md`
  (what we did, what's next, any plan changes).
- **Plan drift:** if we change direction, edit this doc in the same session.
- **Memory:** durable cross‑session facts also go in the harness memory + `MEMORY.md`.
</content>
</invoke>
