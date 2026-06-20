# Working Session Log — KOMPOSOS‑V Silicon Co‑Design

> Append a dated entry **every session**. Newest at the top. Keep entries short:
> what we did, what's next, decisions/plan changes. Master plan: `docs/SILICON_PLAN.md`.

---

## 2026-06-20 — #3 measured tier: OpenSTA toolchain BLOCKED (host), ingestion proven

Attempted the OpenSTA toolchain bring-up to light up the `measured` tier on a real design.
- **Blocked by a host-level WSL fault.** Docker engine still 500s on all API versions
  (post-reboot); the `wsl` CLI itself HANGS (`wsl -l -v`, `wsl --status` time out) even
  though the services run (`vmcompute`/`WSLService`/`hns` = Running). A reboot did not clear
  it. Reviving needs user/admin/BIOS actions that also hang from here (`wsl --update`,
  enable Virtual Machine Platform, firmware virtualization, or a WSL reinstall). Cannot
  generate a real STA report locally on this machine right now.
- **Ingestion path PROVEN ready instead.** Verified `sta.py` `parse_sta` on a GENUINE
  OpenSTA golden (`mcmm3.ok`, multi-corner `report_checks`): 7 paths parsed, slacks correct,
  worst 201.62 (all MET). Added a committed regression test of the real OpenSTA output
  format (`<num>   slack (MET)`, multi-corner) so #3's ingestion is locked against real tool
  output, not just our fixture. The VIOLATED->measured path is already covered by the fixture
  tests. So: parser + measured-tier code is ready; only LOCAL GENERATION is blocked.
- **Handoff:** once WSL is revived, run OpenSTA on gcd (examples/liberty/sdc + our gcd.spef)
  -> real report -> `sta.py` -> `measured` claims in the ledger + scoreboard vs timing.

---

## 2026-06-20 — Push to 100k+: large01 / netcard (276k nodes) ✅

Pulled OpenROAD's `large01.defok` (gpl golden, "netcard": 274,700 components / 290,354 nets
-> **276,249-node / 538,359-edge** graph; placed, 47MB). The scale path holds at the 100k+
tier: parse 3.9s, load 25s, spatial partition -> 512 bounded regions; per-region effres
**158.9s sequential -> 73.1s parallel (x2.2)**, identical top-10 corridors. Whole-graph is
absurd here (276k x 276k dense pinv ~600GB). Added a skip-if-absent parser-scale test
(parse_def handles >100k components fast; full load ~25s is too slow for the suite).
Validates the partition+parallel approach across three real designs at 17k / 30k / 276k nodes.

---

## 2026-06-20 — Push to a bigger design: ibex (~30k nodes) ✅

Pulled OpenROAD's `ibex.defok` (real RISC-V `ibex_core`, 34,184 components / 33,171 nets ->
**29,522-node / 67,990-edge** graph — bigger than AES, which was mostly fill). Placed,
Nangate45 (LEF we have). The scale path handles it: spatial partition -> 64 bounded regions;
per-region effres **12.6s sequential -> 5.1s parallel (x2.5)**, identical results. Whole-graph
is hopeless (30k x 30k dense pinv ~7GB; exact = many hours). `partition` benchmark now takes a
DEF path arg / auto-picks the largest local design. Added a skip-if-absent ibex scale test
(partition-only, disjoint cover at 30k, bounded regions). Confirms the partition+parallel
approach generalizes past AES on a second, larger real core.

---

## 2026-06-20 — Parallelize per-region analysis ✅

The partition regions are independent, so run their curvature in parallel.
- Made `analyze_partitioned` default to **effres** per region (it's the scale path) — that
  alone took AES from 33s (exact) to **8.3s** sequential.
- Added a `workers` param (int/"auto"/1) using `ProcessPoolExecutor`. Key Windows-spawn
  fixes: (1) the worker lives in a **numpy-only** `_region_worker.py` (no geometry/TensorFlow
  import — 0.2s vs 8s startup); (2) made `partition.py`'s own geometry imports LAZY so the
  entry module re-imported per spawned worker stays cheap. The effres worker is deterministic
  (node-order indices, no hash-seed set iteration), so **parallel results == sequential**.
- Result on AES (20 cpus): 8.3s -> **3.1s (x2.6)**, identical top-10 corridors.
- `partition --workers` CLI flag (default 1; parallel best via the light `python -m
  domains.silicon.partition` entry — a heavy `__main__` like the full agent CLI pays the
  re-import per worker on Windows). `tests/test_silicon_partition.py` +2 (worker determinism
  + effres default); real pool not tested in-suite (would pay 8s heavy import per worker).

---

## 2026-06-20 — Scale: fast Ricci + partitioning ✅

Made flow geometry tractable beyond a single small block.
- Benchmarked on real gcd: exact Ricci 981ms (worst kappa -0.396); LowerRicci 10ms but
  worst +0.02 (LOSES the bottleneck — unusable for corridors); EffectiveResistance 263ms
  and worst -0.86 (PRESERVES the bottleneck). Conclusion: effres for scale, not lower.
- `flow_geometry.edge_curvatures(method=...)`: auto/exact/effres/lower. `auto` = exact
  below AUTO_EXACT_MAX_EDGES (1500) else effres — gcd/sample stay exact, so all prior
  tests/results are unchanged; large designs switch automatically.
- `domains/silicon/partition.py`: recursive Fiedler bisection into bounded regions
  (connected-components + spectral split), induced sub-categories, `analyze_partitioned`
  (per-region bounded curvature + inter-region seam nets). On gcd: 423 nodes -> 5 disjoint
  regions (<=104), cover proven. Bounds per-region cost so exact stays feasible at scale;
  inter-region edges are seams (use the cheap global `seam`).
- `partition` CLI; `tests/test_silicon_partition.py` (8): disjoint-cover, bounded size,
  bus-is-cut, effres preserves bottleneck, auto-threshold, CLI.

**Stress test on a larger real design (same day).** Pulled OpenROAD's `aes_nangate45_preroute.def`
(real AES core: 156k components, 17,386 nets -> 16,853-node / 43,718-edge graph after
fill/clock filtering; Nangate45 LEF we already had). Found a real limit: my Fiedler
bisection calls the spectral module's DENSE eigensolve, which won't scale to 16k. Added a
**spatial (placement) partitioner** (`_spatial_bisect`, median k-d split, O(n log n)); auto
uses spatial above SPECTRAL_MAX_NODES (2000) or whenever fully placed. Result: AES partitions
into **32 disjoint balanced regions (~527 each) in ~1s**, full per-region exact analysis in
~33s — where whole-graph curvature is infeasible (effres needs a 16k x 16k dense pinv).
Added 2 tests (committed synthetic spatial + skip-if-absent AES scale). gcd/sample stay on
spectral (< 2000 nodes), so prior tests unchanged.

---

## 2026-06-20 — Self-learning fix loop (GenerativeLoop) ✅ — final plan item

The capstone: verified silicon fixes become primitives, via the REAL
`core.generator.GenerativeLoop` (same engine that grows NAND->XOR).
- `domains/silicon/fix_loop.py` — fix primitives as typed transforms on a discrete
  risk level (swap_interconnect/widen_wire for EM; reroute_upper_metal/insert_buffer for
  congestion). Goals "drive any risk level to clean"; OPERADUM composes + COG gates
  `mitigate_em` and `relieve_congestion`, which are hot-loaded AND appended as primitives.
  Loop converges when nothing new can be added.
- `verify_em_fix` grounds it on REAL data: applies the recommended metal swap to the worst
  EM-risk net (n_bus), verifies the risk proxy drops 1.0->0.5 (Ea 0.8->1.6 eV), gated AGREE.
- Fixed a grounding bug (recommendation claim referenced the net name, not committed
  facts -> HOLLOW); re-grounded in the metal-property vocabulary (invariant #4) -> AGREE.
- `fixloop` CLI; `tests/test_silicon_fix_loop.py` (6 tests): composition, vocab growth,
  convergence, real before/after improvement, CLI.
- **All five handoff plan items are now complete.** Scope boundary held throughout:
  fix magnitudes and current/EM are proxies, never a simulation.

---

## 2026-06-20 — IR-drop / current-density + interconnect material bridge ✅

Started the next plan item (allowed now that tile Kan conservation laws pass).
- `domains/silicon/ir_drop.py` — honest current-DEMAND proxies (no PDN sim):
  per-tile switching-cap hotspots (from the gates->tiles aggregation) and per-net EM
  current-demand (cap x fanout). High-EM nets are handed to the material bridge.
  Claims are `measured_proxy` (SPEF-extracted), never `measured`.
- `domains/silicon/interconnect.py` — the layout<->materials loop: Cu/Al/W/Co/Ru/TaN
  table (resistivity + EM activation energy), a severity-weighted EM-vs-resistance
  ranking (`propose_interconnect`), and a HonestyGate-gated `recommend_interconnect`.
  Cool nets keep Cu (conductivity); hot/high-current nets get W/Ru/Co (EM Ea).
- Wired into `build_waste_ledger(power_crosswalk=...)` and added `irdrop`/`emrisk` CLI.
- `tests/test_silicon_ir_drop.py` — 8 tests (tradeoff, gated recommendation, proxy-tier
  honesty, CLI). Real-data sanity: worst EM net on sample is `n_bus` (severity 1.0)->W.
- **Scope boundary held:** SPEF is routing telemetry, so this is current *demand*, not a
  simulated voltage drop; a real OpenROAD/Voltus PDN report is the `measured` upgrade
  (deferred). Remaining plan item: GenerativeLoop integration of verified before/after fixes.

---

## 2026-06-20 — Gates-to-tiles Kan extension RESOLVED ✅ (resumed from handoff)

Picked up the partial handoff below; double-checked the baseline (214 passing) and finished it.
- **Found + fixed the bug that left tiles untested:** `build_tile_crosswalk` called
  `Category.add(tile, x_index=..., y_index=...)`, but `Object` only takes those inside
  `metadata` → `TypeError`. Moved them into `metadata`; the module now runs.
- **Added `tests/test_silicon_tiles.py` (8 tests):** left-Kan additive **mass conservation**
  (gate count + fanout conserved across tiles), grid-bound indices, unplaced-gate skipping,
  invalid-grid guard, deterministic shuffle control, CLI JSON, and a real-gcd telemetry test.
- **Wired the `tiles` CLI command** (`--nx/--ny`) into `agent_tools.py` + MANIFEST.
- **Result:** on real gcd, the gates→tiles left-Kan aggregation yields tile telemetry where
  tile **fanout/wirelength predict tile SPEF cap at rho ~0.99** (control −0.19). Mass is
  conserved (7 sample gates → 7 across tiles).
- **Full regression: 222 passed** (214 baseline + 8 tiles). No regressions.
- Scope boundary held: SPEF is routing telemetry, NOT power/IR-drop — tile score is not
  described as power validation. IR-drop/material/GenerativeLoop items still not started.

---

## 2026-06-19 — Gates-to-tiles Kan extension HANDOFF (partial)

**Completed before cutoff**
- Audited `categorical/kan_extensions.py` and found it incompatible with the fused
  `core.Category` API (`objects.items()`, `hom()` returning morphisms, obsolete
  `morphism.data`).
- Repaired `LeftKanExtension` to enumerate fused objects/morphisms, read `metadata`,
  and accept an explicit colimit reducer.
- Added `domains/silicon/tiles.py` with a first implementation of:
  - deterministic DEF placement grid (`nx` by `ny`),
  - gate→tile embedding functor,
  - additive left-Kan colimit for gate count, LEF area, fanout, wirelength, and SPEF cap,
  - per-tile SPEF scoreboard with Spearman, precision@k, and shuffled control.

**Verification state**
- `py_compile categorical/kan_extensions.py domains/silicon/tiles.py` passes.
- `git diff --check` passes.
- **No tile unit tests or full regression were run after these two edits.** The last
  fully verified baseline before the Kan work is **214 passed**.

**Resume exactly here**
1. Add `tests/test_silicon_tiles.py`: conservation of gate count/area/cap, deterministic
   assignment, empty/unplaced behavior, and proof that `LeftKanExtension` contributes.
2. Run the tile tests; fix compatibility or aggregation errors before CLI wiring.
3. Add `--tiles-x/--tiles-y` and `tiles` to `agent_tools.py`, returning aggregates and
   telemetry score as JSON.
4. Run `python -m pytest tests -q`; only then mark Rung 9 complete in
   `SILICON_PLAN.md`, `SILICON_STATUS.md`, `MEMORY.md`, and `domains/silicon/__init__.py`.
5. Do not begin IR-drop/current-density until the Kan conservation laws pass.

**Important scope boundary**
- SPEF capacitance is the currently available routing telemetry proxy. No power/IR-drop
  data is present, so the tile score must not be described as power validation.
- The physical/material and `GenerativeLoop` items have not been started.

## 2026-06-19 — Exact cross-layer H0/H1 cohomology

**Did**
- Added finite-dimensional `C0 -> C1 -> C2` cochain complexes to
  `topology/persistent_sheaves.py`, with shape/complex validation, SVD rank/nullspace,
  quotient-basis H1, and edge-support localization.
- Added `domains/silicon/coherence.py` for artifact calibration nerves and an agent
  `cohomology` command.
- Kept coverage mismatches separate from cohomology. Verilog↔DEF↔SPEF is currently a
  chain, so it cannot honestly produce H1 without an independent third calibration.

**Laws**
- Filled triangle: H0=1, H1=0.
- Unfilled pairwise triangle: H0=1, H1=1, localized to all three calibration edges.
- Disconnected artifact: H0=2, H1=0 (not mislabeled as obstruction).
- Current two-step crosswalk: H0=1, H1=0; CLI agrees.

**Verified**
- Focused cross-layer suite: **12 passed**.
- Full suite: **214 passed**.

## 2026-06-19 — Gate-netlist identity crosswalk

**Contract chosen**
- Parse the exercised structural Verilog subset: module ports, scalar/bus net
  declarations, and named-port standard-cell instances.
- Identify nets by canonical `(instance, pin)` terminal sets, not by net names, so
  synthesis renaming does not create false incoherence.
- Report cell mismatches and unmatched logical/physical nets separately. Do not call
  these H1 obstructions until the real sheaf linear algebra exists.

**Did**
- Added `domains/silicon/verilog.py` for structural gate Verilog: ANSI/non-ANSI ports,
  scalar/bus declarations, named standard-cell connections, constants, and comments.
- Added endpoint-signature crosswalking. Exact terminal sets match even when synthesis
  renames a net; missing/extra instances, cell mismatches, and logical/physical-only
  nets remain explicit.
- Added the agent `crosswalk` command via `--verilog PATH`.
- Added parser, renamed-net, mismatch, and CLI laws.

**Verified**
- Full suite: **209 passed**.

**Next**
- Build the cross-layer sheaf adapter over these identities. Implement actual H0/H1
  matrices and obstruction localization before using cohomological language in claims.

## 2026-06-19 — Operadic multi-pin net semantics

**Did**
- Added `domains/silicon/net_operad.py`: one `ColoredOperad` operation per accepted
  signal net, with canonical terminals, arity, direction source, and SPEF metadata.
- Changed `NetlistBridge` so binary morphisms are projections of those operations,
  not the primary net representation. Each edge records `operad_operation` and
  `projection_assumption`.
- LEF OUTPUT direction produces an order-invariant driver-star projection. Without
  LEF, the n-ary terminals remain canonical while the graph projection is honestly
  labeled `def_order_fallback`.
- Added the agent `operad` command with color, arity, operation, and fallback summaries.
- Added laws proving semantic invariance under shuffled DEF connections and projection
  invariance when LEF is present. The no-LEF law deliberately proves that only the
  fallback projection can change.

**Verified**
- Focused operad/netlist/scoreboard/CLI suite: **38 passed**.
- Full suite: **205 passed**.

**Next**
- External track: obtain real STA + gate netlist + Liberty + SDC and run timing scoring.
- Code track: parse gate-level Verilog and build canonical identities needed for true
  RTL/netlist/layout sheaf coherence.

## 2026-06-19 — STA-backed triage (code complete; real data pending)

**Audit completed**
- Chosen milestone: finish LEF/STA CLI integration and timing-criticality scoring
  before starting the operad/sheaf layers.
- Found no local OpenSTA/OpenROAD executable or real STA report. Docker is installed,
  but the available real artifacts are DEF/SPEF plus Nangate45 LEF only.
- Found two honesty/compatibility gaps in the interrupted code: the parser accepts
  only the fixture's `<value> slack` form, not common `slack (VIOLATED) <value>`
  output, and bare fixture paths can currently create `measured` ledger claims.

**Completed slice 1 — provenance + CLI**
- Added provenance-bearing `TimingReport` loading with SHA-256 and automatic fixture
  detection. The fixture can be parsed and inspected but cannot create measured claims.
- STA parsing now accepts both `<value> slack (VIOLATED)` and common
  `slack (VIOLATED) <value>` layouts plus hierarchical instance names.
- Added global `--lef`/`--sta`, a `sta` command, and STA-aware `ledger` output. Every
  timing result includes path, source kind, hash, tool label, and evidence eligibility.
- Added unit and CLI integration laws, including hashed tool-report promotion and
  fixture non-promotion. Focused result: **24 passed**.

**Completed slice 2 — timing scoreboard**
- Added STA negative slack as a second independent scoreboard target, reusing the
  structural predictors, Spearman, precision@k, and deterministic shuffled control.
- Timing targets are restricted to analyzed signal nets; global `clk` no longer enters
  critical-net results.
- Added a JSON `score` agent command. Fixture timing renders `NON-EVIDENCE` and cannot
  pass regardless of correlation; only a hashed non-fixture report is eligible.
- Honest fixture result: structural predictors do not predict its planted critical path
  (correlations are negative or zero). No success claim is made from the fixture.
- Focused result after this slice: **33 passed**.

**Completed slice 3 — evidence hardening + regression**
- Unmarked STA files now default to `unverified`; `--sta-source tool` is explicit.
  The known fixture marker always wins and cannot be overridden.
- Measured promotion additionally requires hashed gate-netlist, Liberty, and SDC
  receipts. Tool attestation without all three remains `incomplete_provenance` and
  creates no measured ledger claim.
- Canonicalized scoreboard rows by net name after finding that category iteration
  order made a seeded shuffle nondeterministic across processes. The real conclusions
  remain: `45_gcd` fanout rho +0.584, wirelength +0.438, deterministic control -0.025;
  real `gcd` fanout +0.563, control +0.143. Both still pass.
- Canonical DEF/SPEF and STA fixtures now render `NON-EVIDENCE` even when a metric
  clears its numerical threshold.
- Final verification: **201 passed**; `py_compile` and `git diff --check` clean.

**Remaining external dependency**
- No real STA report, gate netlist, Liberty, or SDC is present locally and no OpenSTA/
  OpenROAD executable is installed. The next evidence milestone is to obtain those
  four design-matched artifacts and record the timing scoreboard result without
  changing thresholds after seeing it.

## 2026-06-19 — Status recovery after LEF/STA session cutoff

**Observed and documented**
- Added `docs/SILICON_STATUS.md` as the concise source for current progress,
  evidence boundaries, unfinished work, and the advanced roadmap.
- Verified the full current suite: **190 passed**.
- Reproduced the LEF delta on real `45_gcd`: curvature rho +0.131→+0.286 and
  wirelength +0.243→+0.438. The gain comes primarily from correct output-pin
  direction; cell-area predictors are weak.
- Confirmed STA parsing, critical-net mapping, and ledger insertion on the fixture.
  Real STA is not yet present, and `agent_tools.py` stopped after importing STA helpers:
  it has no `--sta`, `--lef`, STA command, or ledger integration yet.
- Corrected an advanced-plan overstatement: `persistent_sheaves.py` does not yet
  compute/localize an H1 obstruction. It provides coboundaries, persistence, and an
  H0 heuristic; true H1 requires matrix rank/nullspace and support localization.

**Next**
- Finish CLI wiring and obtain a real design-matched STA report.
- Score structural predictors against timing criticality with a shuffled control.
- Then replace the star net model with operadic n-ary nets and build real cross-layer
  RTL/netlist/layout coherence.

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
