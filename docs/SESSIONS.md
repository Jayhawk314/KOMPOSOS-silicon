# Working Session Log — KOMPOSOS‑V Silicon Co‑Design

> Append a dated entry **every session**. Newest at the top. Keep entries short:
> what we did, what's next, decisions/plan changes. Master plan: `docs/SILICON_PLAN.md`.

---

## 2026‑06‑19 — Session 1: research + project foundation

**Did**
- Audited 4 repos by reading code (docs were misleading, per direction):
  `komposos-v` (substrate), `KOMPOSOS-IV-CHEM` (materials), `KOMPOSOS-GRID`
  (pipeline pattern), `KOMPOSOS-III-LAMBDA-max-3D-fume` (mostly irrelevant — protein).
- **Key finding:** ~70% already exists. CHEM has a real `semiconductor_bridge`
  (5 scorers, heterostructure analyzer, named real + broken stacks) + an inverse
  designer (`composition_engine/designer.py`). GRID has the full analysis pipeline
  (coherence/sheaf, flow_geometry/Ricci+Fiedler, waste_ledger, agent_tools).
- **The one new piece identified:** a `netlist_bridge` (layout/netlist → `Category`).
  Materials side is done; topology/layout side is not.
- Web‑checked data sources (OpenLane, Materials Project, EPFL/ISCAS, ISPD).
- Wrote `docs/SILICON_PLAN.md` (master plan), `.gitignore`, this log; updated
  `MEMORY.md`, `CLAUDE.md`, `README.md`; wrote harness memory.

**Decisions**
- Project = port GRID pipeline pattern + CHEM material bridges onto V as `domains/silicon`.
- No silicon physics simulation on the laptop — ingest tool outputs as evidence.
  Proxy = `structural_only`; real tool output = `measured`.
- Roadmap = Rungs 0→3 (see plan §5). Start with Rung 0 (synthetic netlist).

**Then, same session — built Rung 0** ✅
- `domains/silicon/synthetic.py` — synthetic "barbell" chip (two cores + one bus),
  loaded into a `Category`, analyzed with the substrate's own engines:
  - `geometry/ricci.py` (Ollivier-Ricci) → bus wire `n_bus_AB` is the most-negative
    corridor (kappa=-0.125); intra-core wires positive. = congestion bottleneck.
  - `geometry/spectral.py` (Fiedler) → seam cleanly splits core A | core B,
    cut net = `n_bus_AB`. = chiplet boundary.
  - inline coherence (mirrors GRID `coherence.py`) → ghost net `n_ghost_fetch`
    (declared, never routed) = CONTRADICT; bus = TENSION; rest GLUE.
- `tests/test_silicon_synthetic.py` — 4 falsifiable tests (planted structure is
  recovered; routing the ghost net removes the CONTRADICT). All pass.
- Substrate plumbing confirmed: GRID-pattern geometry + V `Category` fit cleanly.
  Note: importing `geometry/*` pulls heavy package init (tensorflow/ESMFold warnings) —
  cosmetic, pre-existing; consider a lighter geometry import path later.

**Then, same session — built Rung 1** ✅
- Ported CHEM material engine into the V substrate:
  - `domains/silicon/materials_data.py` (verbatim, 28 materials w/ citations) +
    `domains/silicon/scoring.py` (5 scorers, imports rewired to relative).
  - `domains/silicon/material_bridge.py` — clean validator (weighted 5-scorer
    composite + lattice veto, no CHEM `typed_morphism` prior), `analyze_stack`
    (weakest interface = bottleneck), named stacks, `MaterialBridge(Bridge)`, and
    `verdict_for_interface` gating the proposal through **real COG + HonestyGate**.
  - Verdict pipeline: propose (5 scorers) → physics gate (viability/lattice veto →
    REJECT) → COG `check_claim` (≠ REJECT) → HonestyGate grounding. Composite claim
    is grounded in its OWN committed component-score edges (invariant #4 vocabulary),
    so grounding is meaningful + deterministic.
- `tests/test_silicon_material_bridge.py` — 11 tests. **Full suite 155 passed.**
- Falsifiable target HIT: `GAN_ALGAN_POWER`/`GaN+AlGaN` → AGREE (persist);
  `PROBLEMATIC_GAN_GAAS`/`GaN+GaAs` → REJECT (lattice veto). Good stacks viable,
  problematic stacks unviable.
- Bug caught + fixed: honesty verdict was order-dependent (HOLLOW vs AGREE) because
  evidence was empty for a novel interface; fixed by committing component scores as
  evidence. Lookup key gotcha: SiC uses dict key `SiC_4H`, formula `4H-SiC`.

**Then, same session — built Rung 2 (option 2: committed sample, real grammar)** ✅
- `domains/silicon/flow_geometry.py` — shared Category-based geometry (Ricci corridors
  + Fiedler seam). Refactored Rung 0 `synthetic.py` to delegate to it (one impl, not two;
  Rung 0 tests still green).
- `domains/silicon/netlist_bridge.py` — `parse_def` (COMPONENTS+placement, NETS
  connectivity), `parse_spef` (per-net total cap), `NetlistBridge(Bridge)`,
  `analyze_layout`. Star connectivity model; power/clock/high-fanout nets skipped.
- `domains/silicon/samples/tiny_core.def` + `.spef` — committed fixtures in real
  LEF/DEF 5.8 + IEEE-1481 grammar (NOT under the gitignored data/ dir).
- **Robustness built in + tested** (so real OpenLane parses unchanged): routing
  coordinate parens after '+' are NOT misread as connections; USE CLOCK/POWER and
  global net names skipped; missing SPEF degrades gracefully; multi-line net statements.
- `tests/test_silicon_netlist_bridge.py` — 9 tests. **Full suite 164 passing.**
- Result on the sample: `n_bus` is the congestion bottleneck (kappa<0), Fiedler seam
  splits core_a {u_a*} from core_b {u_b*} with cut = `n_bus`, and SPEF flags `n_bus`
  as highest-load (measured_proxy) — kept distinct from the structural proposal.

**Then, same session — built Rung 3** ✅
- `domains/silicon/waste_ledger.py` — `WasteClaim`/`WasteLedger` (clone of GRID), the
  same 4 evidence tiers, `claims_from_layout` (congestion=structural, SPEF cap=
  measured_proxy, seam=structural) + `claims_from_stack` (interface defect=
  validated_hypothesis), and `action_portfolio()` (the Gemini ready_for_scoping /
  validate_proxy / review_required buckets). Exports json/md/csv.
- `domains/silicon/agent_tools.py` — local-agent CLI (manifest, corridors, seam,
  ledger, interface, stack, whatif --isolate). Every command emits JSON with
  `summary` + `provenance` (GRID contract).
- `tests/test_silicon_waste_ledger.py` — 10 tests. **Full suite 174 passing.**
- End-to-end works: sample DEF/SPEF → geometry + material verdicts → tiered ledger →
  agent JSON. `whatif --isolate u_b0` correctly shows the bus block is a cut point
  (Fiedler λ2 0.398 → 0.000).

**Pipeline complete (synthetic/sample stage). Next:**
- **Real download (do regardless):** OpenLane/OpenROAD + SKY130 → real DEF/SPEF →
  point `netlist_bridge`/`agent_tools` at it (plan §4). Parser is ready.
  - **2026-06-19/20 — RESOLVED via a faster path.** First attempted OpenLane via Docker;
    Docker Desktop's WSL2 engine was wedged (HTTP 500, `wsl` CLI hung) — a pending
    Windows reboot, then post-reboot the engine still 500'd on all API versions. Burned
    hours on infra. **Pivot that worked in minutes:** don't *generate* a layout locally —
    *download* a real routed one. Pulled OpenROAD's committed test layouts
    (`gcd.def`/`gcd.spefok`, real placed+routed GCD) from
    raw.githubusercontent.com → `domains/silicon/data/openlane/` (gitignored). No Docker.
  - **REAL SILICON now flows through the pipeline:** `netlist_bridge` parsed gcd.def
    (423 blocks, 785 wires, 405 signal nets; power/clock auto-skipped), real Ricci
    congestion corridors (worst kappa=-0.396), real Fiedler chiplet seam; agent `ledger`
    emits 12 tiered claims (5 measured_proxy from real SPEF). End-to-end on genuine layout.
  - **Robustness fixes from real data:** `parse_spef` now resolves SPEF `*NAME_MAP`
    numeric ids (`*57 _000_`); `claims_from_layout` dedups corridor claims by net.
    Added committed-safe name-map unit test + skip-if-absent real-GCD test. Suite 176 passing.
  - **Lesson:** for validating the bridge, a downloaded real DEF/SPEF == a locally
    generated one. Full local OpenLane generation remains optional/deferred (Docker infra),
    NOT on the critical path.

**Then — built the silicon scoreboard (validation)** ✅
- `domains/silicon/scoreboard.py` — falsifiable test (mirrors `core/scoreboard.py`):
  does the CHEAP structural signal (curvature/degree/fanout/wirelength, computed WITHOUT
  SPEF) predict the EXPENSIVE physical cost (SPEF capacitance)? Spearman + prec@k per
  predictor, plus a SHUFFLE control that must collapse to ~0. numpy+stdlib (own spearman).
- `tests/test_silicon_scoreboard.py` — 6 tests. **Full suite 182 passing.**
- **RESULT — PASS on real silicon, with an honest finding:**
  - real gcd: best predictor **fanout** spearman **+0.563**, prec@10 **0.80**; control +0.08.
  - real 45_gcd: fanout **+0.582**, prec@10 **0.80**; control +0.09. Consistent.
  - **Curvature alone is WEAK on real designs (+0.13–0.16)** — it only looked strong on the
    planted toy. Takeaway: Ricci/Fiedler geometry is for SEAM/partition detection, not
    per-net congestion ranking; fanout/degree dominate congestion. LEF/real-placement
    wirelength would likely lift the geometric signals.
  - The near-zero shuffle control proves the signal is real. **Triage is screening-grade:
    top-10 structural picks catch 80% of the physically heaviest nets, in seconds.**
- Deferred: RTL↔layout *coherence* on real data needs a verilog gate-netlist parser.
- Optional: HTML dashboard for the ledger; promote claims to `measured` once STA/SPICE
  evidence is attached (the tier slots exist).
</content>
