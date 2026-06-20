# KOMPOSOS-V Silicon Co-Design Status

> Current as of 2026-06-19 (America/Los_Angeles). This is the concise status and
> handoff document. `docs/SILICON_PLAN.md` remains the architectural plan and
> `docs/SESSIONS.md` remains the chronological log.

## Executive status

The baseline silicon vertical is working end to end. It can ingest material
stacks and DEF/SPEF layouts, construct a shared `Category`, run structural flow
geometry, and emit a provenance-bearing waste ledger through a local CLI. The
structural triage was tested against SPEF capacitance on two real OpenROAD GCD
layouts and passed its predeclared scoreboard threshold.

Multi-pin signal nets now have canonical colored-operad operations. Ricci/Fiedler
consume an explicit binary projection whose assumption is recorded on every edge.

The current working tree adds LEF-aware net direction plus a provenance-bearing STA
pipeline. LEF produced a meaningful real-data improvement. STA parsing, timing-path
mapping, ledger insertion, CLI commands, and timing scoring are complete in code, but
real STA output and its design context have not been ingested.

## Capability ledger

| Capability | State | Evidence | Boundary |
|---|---|---|---|
| Synthetic chip + coherence demo | Complete | Planted bus/seam/ghost-net tests | Demonstrates plumbing, not silicon realism |
| Material bridge | Complete | 28 materials, five scorers, good/bad stack tests, COG + HonestyGate | Scores are validated hypotheses, not device measurements |
| DEF/SPEF netlist bridge | Complete | Committed fixture plus real `gcd` and `45_gcd` OpenROAD files | Parser covers the exercised grammar, not every corner of the standards |
| Colored n-ary net semantics | Complete working tree | One operation per signal net; DEF-order and LEF-order invariance laws | Binary geometry still uses an explicit star projection |
| Gate-Verilog identity crosswalk | Complete working tree | Structural parser, endpoint-set renaming laws, mismatch + CLI tests | Establishes identities consumed by the artifact nerve |
| Exact H0/H1 cohomology | Complete working tree | Coboundary ranks/nullspaces, quotient basis, localized hollow-cycle laws | H1 requires an independently calibrated cycle; ordinary coverage gaps are not H1 |
| Gates-to-tiles Kan extension | Complete working tree | Fixed an Object-kwarg bug that blocked execution; mass-conservation + grid + skip + scoring tests; `tiles` CLI; on real gcd, tile fanout/wirelength predict tile SPEF cap (rho ~0.99) | Aggregates extracted cap/area, not yet IR-drop/power telemetry |
| IR-drop / current-density proxy | Complete working tree | `ir_drop.py`: per-tile switching-demand hotspots + per-net EM current-demand proxy; `irdrop`/`emrisk` CLI; measured_proxy claims; 8 tests | Demand proxy from SPEF, NOT a simulated PDN/IR voltage drop |
| Interconnect material proposal | Complete working tree | `interconnect.py`: Cu/Al/W/Co/Ru/TaN table; severity-weighted EM-vs-resistance ranking; HonestyGate-gated recommendation; layout EM-risk -> metal swap | Bulk literature properties; screening triage, not foundry qualification |
| Self-learning fix loop (GenerativeLoop) | Complete working tree | `fix_loop.py`: real `core.generator.GenerativeLoop` over typed fix primitives; OPERADUM composes+COG-gates `mitigate_em`/`relieve_congestion`, which become reusable primitives; `verify_em_fix` grounds a swap on a real net (risk 1.0->0.5, gated AGREE); `fixloop` CLI; 6 tests | Fix magnitudes are proxies, not a sim; converges on a fixed primitive set |
| Scale: fast Ricci + partitioning | Complete working tree | `flow_geometry` method selector (auto/exact/effres/lower; auto keeps gcd/sample exact); `partition.py` spectral (small) + spatial-placement (large, O(n log n)) bisection into bounded regions, disjoint cover proven; per-region curvature + inter-region seam nets; `partition` CLI; 10 tests. **Stressed on real AES (16,853 nodes / 43,718 edges): 32 disjoint regions in ~1s; per-region analysis 33s exact -> 8.3s effres -> 3.1s parallel (x2.6, identical results)** where whole-graph is infeasible | EffectiveResistance ~4x faster and preserves the bottleneck; LowerRicci linear but loses it (excluded). Spectral bisection is dense, so large designs use spatial. Parallel via numpy-only worker; on Windows the entry module must be light (spawn re-import). Inter-region edges need the global seam pass |
| Ricci corridors + Fiedler seam | Complete | Synthetic recovery and real-layout execution | Useful for structure/partitioning; curvature alone is a weak real per-net cost ranker |
| Waste ledger + agent CLI | Complete working tree | Evidence tiers, provenance, portfolio, exports, LEF/STA/score commands | Real STA artifacts are still absent |
| SPEF scoreboard | Complete and committed | Real layouts beat a shuffled control | Validates screening against extracted capacitance only |
| LEF ingestion | Working tree | Nangate45 parsing, real output-pin direction tests, scoreboard delta | Area features are weak; direction correction is the main gain |
| STA ingestion | Code complete, validation pending | Real grammar variants, source/context hashes, critical-net mapping, ledger + scoreboard tests | Fixture is non-evidence; no real OpenSTA/OpenROAD report yet |
| Full test suite | Passing | `244 passed` on 2026-06-20 (214 baseline + 8 tiles + 8 IR-drop/EM + 6 fix-loop + 8 scale) | Real-data tests skip when local gitignored files are absent |

Committed work currently ends at the SPEF scoreboard commit (`4e736ec`). LEF/STA,
operadic nets, Verilog crosswalking, their tests, and bridge/ledger changes are uncommitted.

## Measured results

The scoreboard asks whether cheap predictors computed without SPEF rank nets in
the same order as extracted SPEF total capacitance. The pass threshold is
Spearman rho >= 0.30 with an absolute shuffled-control rho < 0.20.

| Design | Nets | Curvature rho | Fanout rho | Wirelength rho | Best top-10 overlap | Control |
|---|---:|---:|---:|---:|---:|---:|
| real `gcd` | 371 | +0.159 | +0.563 | +0.309 | 0.80 | +0.143 |
| real `45_gcd`, no LEF | 272 | +0.131 | +0.582 | +0.243 | 0.80 | +0.088 |
| real `45_gcd`, with LEF | 274 | +0.287 | +0.584 | +0.438 | 0.80 | -0.025 |

The honest conclusion is narrower than "geometry predicts congestion." Fanout
is the strongest baseline. LEF nearly doubled the curvature and wirelength
correlations because the actual output pin corrected the directed star center;
cell-area predictors themselves were weak. Ricci/Fiedler remain better motivated
for corridor and partition analysis than as standalone per-net rankings.
Scoreboard rows are now canonicalized by net name, making the seeded shuffled
controls deterministic across processes. The real-design conclusions did not change.

## Evidence boundary

- `structural_only`: curvature, Fiedler partitions, fanout, degree, placement
  wirelength, and counterfactual graph changes.
- `measured_proxy`: extracted SPEF capacitance. It is tool-derived physical data,
  but still a model output rather than observed chip behavior.
- `validated_hypothesis`: material compatibility scores that survived the physics,
  COG, and honesty gates.
- `measured` in the current EDA vocabulary: an explicitly attested STA report plus
  hashed gate-netlist, Liberty, and SDC receipts. This means tool ground truth for
  the workflow, not a lab measurement of fabricated silicon.

The STA fixture must never be presented as evidence about `tiny_core`.
It proves parser and ledger behavior only. The fixture marker cannot be overridden.
Unmarked reports default to `unverified`; `--sta-source tool` plus hashed netlist,
Liberty, and constraints are required before making timing claims about a design.

## What is not built yet

- Gate-level structural Verilog, DEF identity matching, and exact artifact-nerve
  cohomology are built. RTL behavioral semantics and independent third-view
  calibrations needed for real H1 evidence are not.
- The n-ary net source is built, but graph-only algorithms still use its driver-star
  projection. Without LEF that projection is explicitly `def_order_fallback` and can
  affect degree and curvature.
- No gates-to-tiles left Kan extension or comparison with tile telemetry.
- No IR-drop, current-density, electromigration, SPICE, or DFT evidence loader.
- No silicon use of `GenerativeLoop`; proposed fixes do not become verified
  primitives for later passes.
- No local CHEM metal/semiconductor cross-bridge or Crystal Dreamer integration.
- No power/timing/area open-game objective and no GNN proposal prior.

The substrate has generic Kan extensions, `GenerativeLoop`, and open games that the
silicon vertical still does not call. `topology/persistent_sheaves.py` now has exact
finite cochain ranks/nullspaces and localized H1 bases alongside its older scalar
heuristic. The silicon adapter refuses to infer missing calibration edges, so current
two-view chains do not manufacture obstructions.

## Remaining milestone: real STA validation

The ingestion and scoring path is complete. The remaining work requires external
artifacts, not more parser scaffolding:

1. Generate or obtain `report_checks`, gate netlist, Liberty, and SDC files for the
   same `45_gcd` layout and record the actual OpenSTA/OpenROAD version.
2. Run `sta`, `ledger`, and `score` with `--sta-source tool`, `--sta-netlist`,
   `--sta-liberty`, and `--sta-sdc` so all context receipts are hashed.
3. Record the timing scoreboard result whether it passes or fails. The local fixture
   currently gives negative/zero structural correlations and is explicitly non-evidence.

Exit condition: the CLI shows which structural signals predict real critical nets,
and every timing claim traces to the exact report, netlist, library, and constraints.

## Advanced roadmap after STA

### 1. Finish cross-layer coherence

- **Completed:** each multi-pin net is a colored n-ary operation; graph projection is
  explicit, and tests cover DEF ordering plus LEF direction invariance.
- **Completed:** parse gate-level Verilog and establish endpoint-based identities
  between logical nets and DEF, independent of synthesis net renaming.
- **Completed:** exact coboundary matrices, rank/nullspace H0/H1, quotient bases, and
  obstruction-edge localization for explicitly justified artifact nerves.

### 2. Build the gates-to-tiles crosswalk

- Use the existing left Kan extension substrate to aggregate gate/net properties
  onto physical tiles.
- Compare tile predictions with available routing density, IR-drop, thermal, or
  power telemetry. Keep the Kan output proposal-side until that comparison passes.

### 3. Close the physical/material loop

- Add report loaders for IR drop and current density, then derive EM candidates on
  high-current nets.
- Port the CHEM metal/semiconductor bridge and Crystal Dreamer only after the layout
  defect has a real evidence path. Candidate barrier alloys remain proposals until
  DFT/literature/process evidence verifies them.

### 4. Add verified self-improvement

- Define a routing/material action as a primitive only when it has before/after
  artifacts, passes COG/HonestyGate, and improves a held-out scoreboard metric.
- Feed those verified actions to `GenerativeLoop`; do not promote a recommendation
  merely because it was generated or because a proxy score improved.

### 5. Add optimization and learned proposals last

- Model power, timing, and area policies with open games once each utility has a
  grounded measurement and rollback semantics.
- Train a small GNN only when enough labeled designs exist. Use it to rank proposals,
  compare it against fanout/wirelength baselines, and forbid it from persistence or
  verdict decisions. The current fanout baseline is already strong, so the GNN must
  demonstrate incremental held-out value.

## Supporting cleanup

- Add a reproducible downloader/manifest with source URLs and hashes for the local
  OpenROAD files; currently the real data is gitignored and tests silently skip.
- Reduce heavy import side effects that emit TensorFlow/ESMFold and missing-module
  warnings during the lightweight silicon scoreboard.
- Update module status docstrings and CLI manifests as capabilities graduate.
