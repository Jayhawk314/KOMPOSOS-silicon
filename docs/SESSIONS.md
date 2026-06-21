# Working Session Log — KOMPOSOS‑V Silicon Co‑Design

> Append a dated entry **every session**. Newest at the top. Keep entries short:
> what we did, what's next, decisions/plan changes. Master plan: `docs/SILICON_PLAN.md`.

---

## 2026-06-21 (later 4) — Roadmap #4: one clean entry point + a 3-minute README ✅

Made the value visible. `domains/silicon/api.py`: the single façade (whitepaper §7.2),
`analyze(def, spef, lef) -> SiliconReport` returning evidence-tiered TRIAGE (risky nets ranked
by the validated structural predictors) + SEAM (Fiedler chiplet split + crossing nets), with a
CLI. On the committed sample it correctly isolates `n_bus` as the one net crossing the seam —
from topology alone. `domains/silicon/README.md`: 3-minute front door (30-second no-download
demo, the measured +0.845 result, the "disproved my own hypotheses" honesty hook); root README
now points at it + VALUE.md/ROADMAP.md. `tests/test_silicon_api.py` (3, runs on the committed
fixture); respects the product-import boundary. ROADMAP #4 → done.

## 2026-06-21 (later 3) — Roadmap #1: light up the `measured` tier on a 2nd real design ✅

Stepped back from the Track-3 frontier to the highest-credibility gap (named in VALUE.md and the
whitepaper): the `measured` evidence tier was only lit on 45_gcd. Extended it to orfs_gcd, the
design we hold in full.
- New `sta_flows/orfs_gcd_netdelay_sta.tcl`: real OpenROAD STA (in-image nangate45 libs +
  our routed 6_final.def/.spef/.sdc), `report_checks -fields {input_pins net ...}` → per-net
  interconnect (wire) delay. Ran it in Docker (`openroad/orfs`): read 646 nets, produced a 7 MB
  report. `net_delay.py` attributes load-pin rows to nets via the DEF pin→net map.
- `tau_scoreboard_measured` on orfs_gcd, attested `tool` (hashed netlist/Liberty/SDC, sha256
  a224877…): **structure predicts the tool's OWN per-net wire delay — wirelength ρ +0.845,
  fanout +0.709, sink_area +0.781, degree +0.740, shuffle control −0.05, 545 nets.** Stronger
  than the SPEF Elmore proxy (+0.768). The `measured` tier is now validated on TWO real designs
  (45_gcd +0.65, orfs_gcd +0.845).
- Wired into `tau_scoreboard.main()` + `tests/test_silicon_tau_scoreboard.py` (skip-guarded on
  the gitignored report). Updated VALUE.md claim #1 (proxy → measured) and its boundary note;
  ROADMAP #1 → done.
- **Context:** this session re-grounded the work on its actual goal (visibility / foot-in-door,
  not a product) and its honest value (VALUE.md / ROADMAP.md). The fancy math is the distinctive
  HOOK; the cheap triage + now measured-validated delay is the PROOF. Next roadmap items: #4 (one
  clean entry point + README), #5 (writeup), #2 (catch a real coherence fault).

## 2026-06-21 (later 2) — Track 3 Step C: trust-gate the coherence verdict (3A + 3B) ✅

Wired the obstruction verdicts of BOTH coherence tracks through the proposal→verification
discipline (CLAUDE.md #1). New `domains/silicon/coherence_trust.py`: a localized obstruction
is TRUSTED only if INDEPENDENT, specificity-weighted views corroborate it — then the rationale
grounds via the shared `HonestyGate`, and the tier stays `structural_only` (foundry-EPE never
promoted, #8).
- **Reused the oracle coherence cluster's MATH, not its module** (respects the product-import
  boundary — only `core.category` + `core.honesty_gate` + the silicon producers are imported):
  IDF specificity `spec(w)=log(N/breadth(w))/log(N)` + specificity-weighted noisy-OR
  `1−∏(1−conf·spec)` from `oracle/coherence_specificity.py`. A witness that flags a large
  FRACTION of items (a global rename in 3A; the per-component spectral signal in 3B) gets
  spec≈0 and cannot over-vouch; a localized witness carries the verdict.
- **3A adapter (net-fidelity):** witnesses = the three view-PAIRS flagging a net. On real
  orfs_gcd: of 100 divergent nets, **50 TRUSTED** (flagged by 2 independent pairs, corrob 0.60,
  grounded) vs **50 UNCORROBORATED** (1 pair only — e.g. `clk`, corrob 0.37 — a likely
  single-tool representational artifact, honestly held back). Exactly the plan's intent.
- **3B adapter (double-patterning):** an EDGE has only ONE edge-level localizer (BFS), so
  edge-level "independent corroboration" would be dishonest. The two methods genuinely agree at
  COMPONENT granularity (combinatorial BFS odd-cycle ⟂ linear-algebraic spectral λ_min>0), so
  the trusted unit is the frustrated COMPONENT (the native-conflict region); its BFS edges are
  the localized `support`. Real flattened M1: **1 TRUSTED region (6076 features), corrob 1.00,
  3 views agree, grounded — localizing all 7143 native conflicts**, tier `structural_only`.
- `tests/test_silicon_coherence_trust.py` (12): IDF specificity, noisy-OR, two-specific→TRUSTED,
  single-view→UNCORROBORATED, **two global views cannot over-vouch** (corrob 0.02), tier never
  promoted; 3B trusts frustrated-not-bipartite components + localizes edges; 3A multi-pair
  trusted / single-pair not / global-pair down-weighted; real-data discrimination on both.
- **Decision:** the trust unit differs by track (net for 3A, component for 3B) because the
  independent-localizer granularity genuinely differs — encoded honestly rather than forced.

## 2026-06-21 (later) — Track 3 Step B: SREF-flatten real cell-internal metal + scalable spectral check ✅

Retired the documented honest boundary "top-cell routing only" on the GDS double-patterning
analysis, and fixed a latent honesty bug it exposed.
- **SREF/AREF flattening (`gds.py`):** `parse_gds_structures` now reads every structure's own
  shapes AND its SREF/AREF placements; `flatten_gds_shapes` resolves the hierarchy into the
  top frame with the full GDS transform (reflect→mag→rotate→translate, recursive). Added the
  GDS 8-byte real decoder (`_gds_real`) and `_xform_bbox`. `gds_features(..., flatten=True)`
  and `analyze_gds(..., flatten=True)` expose it. Verified geometrically: the orfs_gcd top
  cell `gcd` has **4514 SREF instances**; flattened metal spans exactly 0–367250 db units =
  0–36.725 µm, corner-to-corner with the DEF DIEAREA. Units are 10000/µm (700 db = 70 nm).
- **Real result — cell-internal metal is the dense layer.** M1 (layer 11) goes 25 → 6076
  shapes once flattened; at 70 nm spacing it is NOT 2-colorable: **7143 native conflicts
  localized**, spectral λ_min(D+A)=0.616. Layer 13 goes 1890 → 5076 (513 conflicts); layer 10
  flattens to 9483 shapes and is bipartite (0). M1 being the canonical double-patterning layer
  and only now visible is exactly the point.
- **Bug found + fixed (honesty):** the dense data exposed that `spectral_frustration` silently
  SKIPPED components >2500 nodes and returned a false 0 ("bipartite"), disagreeing with the
  exact BFS on flattened M1. Replaced with: exact dense `eigvalsh` for components ≤2000, and a
  numpy-only **shifted sparse power iteration** (`_lambda_min_signless_sparse`) for larger ones
  — no component is ever skipped. Honest limit documented: the sparse estimate confirms
  bipartite-vs-frustrated by ORDER OF MAGNITUDE (convergence floor ~1e-5..1e-3; cannot certify
  a lone huge near-1D cycle). The EXACT verdict + localization always come from BFS Z/2.
- **OpenMPL cross-check — definition level DONE (no build needed).** Read OpenMPL's actual
  conflict-graph construction (`SimpleMPL.cpp` `update_conflict_relation`): bloat each shape by
  `coloring_distance`, then connect adjacent shapes with `euclidean_distance < coloring_distance`.
  That is identical to our `_bbox_gap` rule. Aligned our comparator from `<=` to OpenMPL's
  strict `<` (also the correct physical convention — a gap EQUAL to min-spacing is legal, not a
  violation). Effect: at min-width spacing the count drops to the genuinely sub-spacing
  conflicts (top-cell L13 87 → 19; M1-flat 7303 → 7143; L13-flat 600 → 513) — more honest. For
  Manhattan metal (bbox == rectangle) our rule matches OpenMPL exactly; for non-rect polygons
  OpenMPL takes min-over-child-rects while we use the bbox (conservative, documented). The
  remaining gap is purely the NUMERIC binary run on identical inputs — still build-gated
  (C++/Boost/Limbo; OpenMPL ships no in-repo benchmarks, and its `cmdtest` uses color_num=3,
  the triple-patterning NP-hard regime we explicitly do NOT subsume).
- `tests/test_silicon_dp_conflict.py` now 15 (was 6): GDS-real round-trip, bbox rotate/reflect,
  SREF placement + transform + nested recursion, OpenMPL strict-distance boundary rule,
  sparse-spectral scales to large dense components (bipartite <1e-2, heavily-frustrated >0.1,
  agrees with BFS), real flattened M1 denser + native-conflict localization. All green.
- **Still open:** OpenMPL NUMERIC binary cross-check (build-gated, Docker only). Then wire the
  verdict through the trust gate + corroboration/specificity.

## 2026-06-21 — Track 3 Step B first cut: double-patterning native-conflict localization (Z/2 H1) ✅

Scouted MPLD data (OpenMPL, ISCAS/ISPD'19) and found the honest math fit: double patterning
(LELE) is feasible iff the conflict graph is 2-colorable iff no odd cycles iff Z/2 H1 = 0 —
so the engine's job is to LOCALIZE native (unresolvable) conflicts. Triple+ patterning is
NP-hard coloring (OpenMPL's domain), NOT cohomological — stated as the boundary.
- Built the no-build first cut `domains/silicon/dp_conflict.py`: conflict graph from REAL cell
  placements (orfs_gcd DEF, fillers excluded) — same-layer features within the coloring
  distance — then the signed/Z2 obstruction two independent ways: (1) combinatorial BFS
  2-coloring (frustrated edge = native conflict), (2) spectral max-over-components
  lambda_min(D+A) (>0 iff a non-bipartite component). They AGREE.
- **Real result on orfs_gcd (681 cells), distance sweep:** 1500 dbu → 2-colorable, 0 native
  conflicts, frustration 0 (decomposable); 2500 dbu → NOT colorable, **81 native conflicts**,
  frustration 1.0; 4000 dbu → 949 native conflicts, frustration 1.63. Clean colorable→native
  transition; native conflicts **localized to specific feature pairs** (e.g. `_507_`,`clkload1`).
- The signed/Z2 coboundary is the extension the plan called for (R-engine couldn't see odd
  cycles). `tests/test_silicon_dp_conflict.py` (4: path/even-cycle colorable, triangle native
  conflict localized, real-layer transition + BFS↔spectral agreement). 8 green w/ Step A.
- **Honest scope:** features are a placement-proximity stand-in for layer shapes; tier is
  tool/geometric decomposition-conflict, NOT foundry-measured EPE. Upgrades: real metal
  shapes (GDS) + OpenMPL conflict-graph cross-check. But the engine now LOCALIZES native
  double-patterning conflicts on a real layer, two methods agreeing — Step B has a receipt.

## 2026-06-20 (later) — Track 3 Step A DONE: H1 coherence engine wired to real chip artifacts ✅

After auditing the chip-coherence stack in full (persistent_sheaves exact H0/H1 + h1_support;
domains/silicon/coherence.py adapter; verilog.py logical view — all REAL), executed Track 3
Step A: wire the obstruction engine to real silicon on data in hand (self-minted orfs_gcd:
6_final.v + .def + .spef, a matched three-tool set).
- `domains/silicon/fidelity_coherence.py`: three INDEPENDENT tool views of net connectivity —
  verilog (synthesis), def (route), spef *CONN (extraction) — each as net→terminal-set;
  cross-view identity by terminal set (rename-proof); per-net localization + artifact
  calibration nerve → exact H0/H1 via the existing engine.
- **REAL RESULT on orfs_gcd: H0=1, H1=0 — coherent, no cyclic obstruction.** 482/627 nets
  agree exactly across all three tools. After stripping inconsistent name-escaping (def vs
  spef), def~spef agreement 0.776→**0.915**; verilog lags (0.78–0.86) because the gate-netlist
  parser doesn't capture sequential-cell driver pins (flop QN) the way def/spef do. So the
  ~145 divergences are REPRESENTATIONAL (escaping + flop-pin scope), localized per net — not
  logical faults. A genuine measured-tier coherence receipt on real silicon.
- **H1 obstruction-localization demonstrated** on the cyclic (EPE-shaped) case: three views
  pairwise-agree ≥0.75 but not jointly → unfilled triangle → H1=1, localized. Injected faults
  localize to the offending net. `tests/test_silicon_fidelity_coherence.py` (4: clean-coherent,
  cyclic-H1, fault-localized, real-orfs_gcd). All pass.
- **Honest scope:** def+spef are both post-route (independent tools, not independent physics);
  artifact-level H1 is the coarse global-cyclic bit. A genuinely cyclic, feature-level H1 needs
  the N-masks-of-one-layer structure of multi-patterning — Track 3 Step B, still data-gated.
  But Step A removes the "is the engine even wired to chips" risk: it is, with a receipt.

## 2026-06-20 (later) — Track 2 REAL multi-die win: 3D thermal cross-die coupling (Open3DBench) ✅

Scouted public chiplet/3D datasets, pulled **Open3DBench** (`lamda-bbo/Open3DBench`, under
`data/open3dbench`, gitignored). It ships 8 real face-to-face 3D-IC designs (ariane133/136,
black_parrot, bp_*, swerv_wrapper), each two stacked dies tiled 10x10, with **committed
HotSpot per-tile power (.ptrace) + steady-state temperature (.steady)** — real multi-die
boundary + measured-analogue thermal ground truth, NO multi-hour run needed.
- `domains/silicon/thermal3d_scoreboard.py` asks the genuinely-3D question: does a tile's
  temperature depend on the power of the tile STACKED across it on the OTHER die?
- **RESULT — yes, 8/8 designs.** Cross-die (stacked) power predicts tile temperature far
  better than own power; own-die power is often NEGATIVE (bp_fe own −0.558 vs stacked +0.564;
  bp_multi −0.194 vs +0.631; ariane133 own −0.312 vs stacked-added +0.49). Coupling gain
  positive on **8/8, mean +0.54**; shuffle controls collapse (~0).
- This is the system/multi-die effect the within-die partition proxy was blind to — it
  EXPLAINS the weak proxy: in a 3D stack the dominant thermal driver is the opposing die, and
  cheap structure (cross-die power) captures it. **Track 2 now has a real measured receipt.**
- **Per-die-split refinement (done):** removing the heat-sink confound, coupling SURVIVES for
  the UPPER (sink-far) die — 7/8, mean +0.45 (swerv +1.08, bp_fe +0.76) — but is ~0 for the
  BOTTOM (sink-near) die (5/8, +0.02). Physically sensible: the sink-far die dumps heat
  THROUGH the other die, so the sink-near die's power governs the sink-far die's temp, not the
  reverse. So the effect is real and DIRECTIONAL (onto the sink-far die); pooled 8/8 was partly
  die-position inflation. Honest residual: power→temp partly trivial; informative parts are the
  sign flip + the direction. `tests/test_silicon_thermal3d.py` (3) now checks the per-die split.
- Next: pull Open3DBench per-die DEFs (MoL flow) to run placement geometry + extend τ
  measured net-delay to 3D.

## 2026-06-20 (later) — Track 2 proxy experiment: weak/mixed (needs real package data) — honest

Built `system_scoreboard.py` (Track 2): partition a real die into chiplet-analogue blocks
(spatial Fiedler bisection), mark boundary-crossing nets as the **system interconnect**, and
test vs REAL measured IR-drop — H1 (are system nets in higher-IR regions?) + H2 (does a
block's system-connectivity predict its IR stress?), both with shuffle controls.
- **Real result (aes + ibex) — weak, design-dependent.** H1 separation: aes 1.057x (FAIL),
  ibex 1.124x (PASS); shuffle controls clean (~0.997x). H2: ibex `system_load` +0.473
  (control −0.001) and `system_links` +0.553 (control +0.223); aes `system_load` ≈ 0.
- **Honest verdict:** the within-die "chiplet analogue" does NOT strongly validate the
  package-interconnect-stress thesis — the effect is small (5–12%) and doesn't generalize
  across designs. The mechanism is sound (controls collapse); the *signal* is weak. This
  CONFIRMS Track 2 genuinely needs real multi-die/chiplet data, not a within-die proxy. The
  partition→classify→validate code path is built and ready to point at real package data.
- `tests/test_silicon_system_scoreboard.py` locks the honesty mechanism (control ~1.0), not
  a design-dependent pass. This is proposal-vs-verification again: proposed a proxy, measured
  it honestly, it under-delivered, reported that rather than overselling.
- **Tracks status:** 1 = DONE (measured). 2 = proxy run, weak; real package data is the gate.
  3 = still a gated research probe (EPE/DSA placement-error data).

## 2026-06-20 (later) — Track 1 CLOSED at measured tier + Docker confirmed working ✅

Picked up Track 2; user rightly questioned the "can't run Docker" assumption. **Checked:
Docker works** (server 29.5.3, `docker ps` clean; `openroad/orfs` + `openroad/opensta`
images cached locally). The old "blocked" note was stale. So ran the staged Track 1 measured
upgrade for real:
- First run exposed a real format mismatch: `report_checks -fields {...}` rows have VARIABLE
  leading columns (`Fanout Cap Slew Delay Time`), Delay is the **second-to-last** number, and
  default `-digits 2` floors 45nm wire delays to 0.00. My staged parser (assumed
  `<delay> <time>`) would have mis-parsed — exactly why running it mattered. Fixed `_ROW` to
  take the second-to-last number, added `-digits 5`, realigned the test fixture to the real
  layout. (`tests/test_silicon_net_delay.py` now mirrors actual OpenROAD output.)
- A `-path_delay max` run covered only 37 nets and the single-seed shuffle control didn't
  collapse (+0.30) — a small-sample artifact. `min_max` + more paths/endpoint → **full
  274-net coverage**.
- **MEASURED RESULT — PASS on real 45_gcd:** structure vs the tool's OWN per-net interconnect
  delay: fanout **+0.645** (prec@10 0.80), wirelength +0.516, degree +0.429, curvature
  +0.350; shuffle control **−0.053**; `status: measured` (netlist/liberty/sdc hashed; report
  sha256 `c5ec4cc1…3038ea`). Consistent with the Elmore proxy (+0.61), slightly stronger.
- **Track 1 is complete across both tiers.** The τ thesis holds at the authoritative
  measured tier: interconnect delay is structurally predictable; gate slack is not.
  `tests/test_silicon_tau_scoreboard.py` +1 measured real-data test (9 tau+net_delay green).

## 2026-06-20 (later) — resumed Codex's orphaned work + NEW τ WIN: interconnect delay IS structural ✅

Resumed after a Codex session ran out of tokens mid-cleanup (`codexsesh.txt`). Two things:

**1. Committed Codex's verified-but-orphaned cleanup** (`a38dce6`): the product-boundary
audit (`docs/SILICON_PRODUCT_BOUNDARY.md`) + guard test, a lean-import refactor (lazy
`flow_geometry`/`net_operad`; dropped redundant `bridge.load()` where only parsed
nets/components are read — kept where `.category` is used), and docs sync. Full suite was
green (282) at that boundary; focused product+boundary re-ran green (30).

**2. Strategy → executed Track 1 of a new 3-track plan** (`docs/SILICON_POSTMOORE_PLAN.md`).
Brainstormed the Huawei τ / TSMC multi-patterning / Intel DSA landscape: all three abandon
transistor-shrink for **co-optimization** (DTCO/STCO) — exactly our slot. Key insight: we
falsified structure→**gate slack** (optimizer flattens it), but Huawei's τ is about
**interconnect delay** (R·C), the *un-flattened* family our IR/EM wins live in. So we built
the falsifiable test:
- `domains/silicon/tau_scoreboard.py` — extract per-net **Elmore RC** from detailed SPEF
  (R from `*RES`, C from `*D_NET`; `measured_proxy`), score SPEF-free structural predictors
  vs it with a shuffle control. `tests/test_silicon_tau_scoreboard.py` (4: RC-parse,
  product ordering, reduced-SPEF R=0, real-45_gcd skip-if-absent). All pass.
- **RESULT — PASS on real 45_gcd (274 nets):** fanout **+0.610** (prec@10 0.80), wirelength
  +0.443, degree +0.373, curvature +0.299; driver_area −0.191 (correctly weak); shuffle
  control **−0.018**. **Interconnect delay is structurally visible — unlike gate slack.**
  This is the τ thesis landing on terms we win on, with a receipt.
- **Honest scope:** target is a *lumped* Elmore R·C proxy (measured_proxy), not STA net
  delay.
- **Then STAGED the `measured` upgrade** (code + tests ready, only a Docker run left):
  `net_delay.py` parses load-input-pin rows from `report_checks -fields {input_pins ...}`
  and attributes each row's wire delay to its net via the DEF pin→net map (driver pins
  excluded; worst-case per net). `tau_scoreboard_measured()` scores structure vs that,
  with `measured` eligibility + receipt hash from `load_sta` (netlist=DEF, liberty, sdc).
  Flow `sta_flows/tau_netdelay_sta.tcl` + README section emit
  `45_gcd.netdelay.report_checks.txt`; the CLI auto-detects it. The parse contract is
  pinned by `tests/test_silicon_net_delay.py` (4) so it's testable before the Docker run.
  The synthetic fixture is the format spec; adjust `_ROW` + fixture together if a tool
  version differs. (8 tau+net_delay tests green.)
- **Tracks 2 (system/package geometry) and 3 (EPE/DSA pattern-fidelity coherence + BCP
  grounding via the dormant sheaf math)** are designed in the plan but **gated on data we
  don't have locally** — honest probes, not built.

**Next:** the STA net-delay `measured` upgrade for Track 1; acquire a package/chiplet layout
for Track 2; Track 3 stays a gated research probe pending real placement-error data.

## 2026-06-20 (later) — #3 measured tier UNBLOCKED: real OpenSTA report ingested ✅

The host WSL/Docker fault from the earlier entry is **resolved** — user updated Docker;
WSL CLI now responds, Ubuntu boots, `docker ps` clean (server 29.5.3). The prior
"blocked" state was the `docker-desktop` WSL distro being stopped under a dead `wsl` CLI.

**Ran real OpenSTA and lit up the `measured` tier on a real design:**
- Pulled `openroad/opensta:latest` (OpenSTA **2.6.2**). It bundles a complete, self-
  consistent `gcd_sky130hd` design under `/OpenSTA/examples` (gate `.v` + `.sdc` +
  sky130 Liberty + SPEF). `sta` binary is at `/OpenSTA/app/sta` (image entrypoint), not
  on PATH; `MSYS_NO_PATHCONV=1` needed so Git Bash doesn't mangle the `/work` mount.
- Ran `report_checks` two ways on the SAME real design:
  - relaxed clock (5 ns): **meets timing**, worst slack **+0.0648 ns**, 0/53 violations.
  - tight clock (1 ns, 5×): **52/53 real violations**, worst **−3.9352 ns**.
- Both parse to 53 paths via `sta.py` and qualify `is_evidence=True`. CLI
  `agent_tools … --sta-source tool --sta-netlist/-liberty/-sdc sta` → **`status:
  "measured"`** with hashed receipts for report + netlist + Liberty + SDC. First real
  measured-tier timing claim in the project.
- Committed reproducer + provenance/hashes: `domains/silicon/sta_flows/` (flows +
  README). Report `.txt` + staged design files live under `domains/silicon/data/sta_gcd/`
  (gitignored, regenerable).

**Then — closed the cross-mapping loop (structural triage vs REAL timing) ✅**
The remaining piece was a design where we hold BOTH a DEF and a matched report. Got it
the light way: **run OpenROAD STA directly on our held `45_gcd.def`** (placed Nangate45
gcd) so report instances == DEF instances by construction — no synthesis, no name
guessing.
- Pulled `openroad/orfs:latest` (**OpenROAD 26Q2**). Binary at
  `/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad`. Gotcha: **do NOT source
  ORFS `env.sh`** — it `exit`s the shell; call the binary directly as the entrypoint.
- Inputs we already had: `45_gcd.def` + `45_gcd.spefok` + `Nangate45.lef` (merged
  tech+cell, 22 layers/135 macros) + nangate45 Liberty copied from the opensta image.
  Constraints `45_gcd.sdc` @ 0.3 ns clock (tight, to force violations).
- `read_lef`+`read_liberty`+`read_def`+`read_spef`+`source sdc`+`report_checks` →
  53 paths, **48 violating**, worst **−0.7169 ns**. CLI `sta` → `status: measured`,
  **106 critical nets mapped onto DEF nets** (e.g. `dpath.a_lt_b$in1[1]`).
- **Scoreboard vs real `sta_negative_slack` (308 nets): PASS.** Best **driver_area
  ρ=+0.343**, shuffle control +0.020. neg_curvature +0.16, degree +0.11, **fanout −0.04**,
  wirelength −0.00, sink_area +0.25. `prec@10≈0` for all.
- **Honest findings:** (1) signal real but modest — monotone trend, no sharp top-k
  pinpointing; (2) `driver_area` is partly circular (synthesis upsizes drivers on
  critical paths — it's partly an *output* of timing opt), so the purest structural
  signal is `neg_curvature` +0.16; (3) **fanout predicts SPEF capacitance (+0.57) but
  NOT timing criticality (≈0)** — load and timing are different targets, and the
  predictor ranking flips between them. Good falsifiable science.
- Reproducer committed: `domains/silicon/sta_flows/` (`45_gcd_openroad_sta.tcl`,
  `45_gcd.sdc`, README with commands + result tables + hashes). Reports/staged inputs
  under `data/sta_45gcd/` (gitignored). Docs updated: `SILICON_STATUS.md` (STA row,
  milestone, measured-results table) + memory.

**Next ideas:** more designs/clock points for stability; placement-aware timing
predictors that aren't synthesis outputs; or run the full ORFS gcd flow to also get a
self-minted DEF (the long-deferred "mint our own layout" capability — now unblocked
since OpenROAD works).

**Then — self-minted our own layout (full ORFS flow) + a falsifying contrast ✅**
Ran the **full ORFS RTL→GDSII flow** (Yosys 0.64 synth → floorplan → place → CTS →
route → finish; OpenROAD 26Q2) on `gcd_nangate45` — the long-deferred "mint our own
layout" capability, now unblocked. Gotcha: source `env.sh` under **`bash -l`** (not
`sh`); the openroad/yosys binaries are exposed by env.sh, not on the default PATH.
Outputs in `data/orfs_gcd/results/base/`: `6_final.def/.v/.spef/.sdc/.gds` + odb + the
full report set (incl. IR-drop/congestion webp). 1065 placed+routed cells; flow met
timing at the edge (worst slack +0.01 ns @ 0.46 ns, fmax 2254 MHz).
- STA on the self-minted routed design (tightened 0.46→0.40 ns): 53 paths, **42
  violations**, **177 critical nets mapped**, `status: measured`.
- **Scoreboard FAILS** on the self-minted design: every predictor |ρ|<0.15 (best
  sink_area +0.061, shuffle −0.019). NOT a bug — the violating slacks cluster tightly
  (worst −0.0396, all in [−0.040,−0.009], **stdev 0.010 ns**). **The timing-driven flow
  equalizes slack, erasing the structural signal.** The `45_gcd` PASS (+0.34) held only
  because that downloaded layout was less slack-balanced.
- **Important honest verdict:** structural triage predicts timing criticality on
  *un-converged* layouts but is **falsified on a cleanly optimized one**. This is the
  proposal-vs-verification discipline paying off live: the structural proposal would
  have over-claimed; the measured STA receipt caught it. Strengthens "carry a receipt."
- Reproducer committed: `domains/silicon/sta_flows/orfs_gcd.sdc` + `orfs_gcd_sta.tcl` +
  README section (commands, result table, hashes). Self-minted artifacts under
  `data/orfs_gcd/` (gitignored). Docs + memory updated.

**Honest boundary:** all real EDA-workflow ground truth (tool output + hashed design
context), not fabricated-silicon lab data.

## 2026-06-20 (later) — minted aes+ibex, ran early-stage test, REASSESSED & STOPPED

Pushed the timing-prediction question to a verdict, then stopped to reassess honestly
(user's call). Wrote `docs/SILICON_FINDINGS.md` — the plain-English reckoning.

- **Minted `aes` + `ibex`** with the full ORFS flow (each ~32k cells; resumable via
  host-mounted ORFS output dirs; ~7 min each). Scored structural triage vs real STA:
  **both FAIL** — aes best driver_area +0.15, ibex best sink_area +0.24 (curvature on
  32k nodes via effres ~8.5 min each). `prec@10 = 0` on both.
- **Early-stage experiment** (the one escape hatch): does structure predict timing
  *before* the optimizer flattens it? Took self-minted `gcd` at `3_2_place_iop`
  (placed, pre-timing-opt), estimated parasitics, ran STA at 0.40 and 0.30 ns. **Both
  FAIL** (driver_area +0.22 / +0.19, `prec@10 = 0`). Escape hatch closed.
- **Complete verdict (6 tests):** only the downloaded, loosely-optimized `45_gcd`
  passed (+0.34); every design we minted+optimized ourselves failed; the early/un-opt
  stage failed too; `prec@10 = 0` in ALL six — the guess never pinpoints the worst nets;
  the curvature math (the system's core "structure" signal) is the *weakest* (≤0 for
  timing everywhere). **Root cause is fundamental: timing-driven optimization equalizes
  slack (self-mint gcd violating-slack stdev 0.010 ns), erasing the signal.**
- **Conclusion:** cheap structural timing-prediction is a dead end as a product. What
  *works* and is the real asset: the verification/receipt engine (it caught our own idea
  over-claiming) + the real-silicon test harness. The unmet industry need is *trust* in
  AI chip decisions, not a predictor — but whether that's a product is a market question,
  not a coding one. **Set the predictor down; next decision is about users, not code.**
- Reproducer: `domains/silicon/sta_flows/selfmint_sta.tcl` + `early_stage_sta.tcl`
  (+ aes/ibex via the documented ORFS commands). Findings: `docs/SILICON_FINDINGS.md`.

## 2026-06-20 (later) — PIVOT + FIRST REAL WIN: structure predicts real IR-drop ✅

Reframed (user pushed back, rightly): the project isn't a timing predictor — it's a
verification-backed system to attack chip problems. Timing was one falsifiable test that
failed. Opened the aperture, set a competitive wedge (reliability co-design: find physical
stress with cheap structure → fix with grounded materials → prove with receipts), and made
a 5-phase plan (task list #1–#5). **Phase 1 done, and it's a measured WIN.**

- Ran OpenROAD `analyze_power_grid` (real PDNSim IR-drop) on self-minted aes + ibex →
  per-instance supply voltage. aes worst drop 90.9 mV (8.3%), ibex 7.2 mV (0.65%).
- New module `domains/silicon/ir_scoreboard.py`: bins the die into 20×20 tiles, tests
  whether cheap structural proxies predict the REAL per-tile IR drop. Spearman + prec@k +
  shuffled control. `tests/test_silicon_ir_scoreboard.py` (4 tests, real-data assertion
  skips if artifacts absent).
- **RESULT — PASS on both designs.** fanout +0.597/+0.443, load(cap) +0.586/+0.478,
  density +0.558/+0.385 (aes/ibex); controls ~0. The FREE signals (fanout, density — no
  extraction) predict where the chip browns out at +0.4–0.6. (Nuance: strong ranking,
  prec@10 still weak — ranks risk well, doesn't always nail the single worst tile.)
- **The insight = the boundary:** structure predicts what optimization does NOT flatten
  (current / IR-drop / load: WINS) and fails on what it DOES (timing slack: equalized,
  LOSES). That line is the product: a cheap reliability/power hotspot detector, not a
  timing tool. Rewrote `docs/SILICON_FINDINGS.md` from obituary → "what structure can and
  can't predict," with the IR-drop win as the centerpiece.
- **Next (Phase 2):** fold load + power into one structural hotspot detector; then Phase 3
  ground the materials engine; Phase 4 close the find→fix→prove co-design loop.

## 2026-06-20 (later) — Phase 2 DONE: unified hotspot detector (validated)

- **Combine experiment (honest):** a rank-sum "stress" of cap+fanout+density does NOT beat
  the best single signal (aes +0.598 vs fanout +0.597; ibex +0.456 vs cap +0.478). The
  signals are redundant (all measure "how busy is this tile"). So the detector uses a
  simple validated metric, not a fancy blend — and the FREE signals (fanout/density) are
  enough.
- **New module `domains/silicon/hotspot.py`:** `predict_hotspots(def, spef, lef)` ranks the
  worst physical-stress tiles from the LAYOUT ALONE (no power sim) by current-demand
  (cap x fanout), names the dominant EM-risk nets per tile, and carries the Phase-1
  measured receipt (tier=measured_proxy). This is the "find the problems" front-end.
- **Validated the detector's exact metric:** added `demand`=cap×fanout to `ir_scoreboard`;
  it predicts real IR-drop at +0.581 (aes) / +0.473 (ibex), clean controls — so the
  ranking isn't a hollow guess, it's a measured-correlated predictor.
- `tests/test_silicon_hotspot.py` (+ ir_scoreboard demand) — 6 tests pass.
- **Next (Phase 3):** ground the materials engine (real Cu/W/Ru/Co properties) so the
  "fix" half of co-design carries real receipts; then Phase 4 closes find→fix→prove.

## 2026-06-20 (later) — Phase 3 DONE: materials engine grounded against cited data

User pointed to the sibling repo `KOMPOSOS-IV-CHEM` (the materials bridges). Its
`metal_bridge/material_properties.py` has real, CITED per-metal data (resistivity +
melting point + sources: ASM Handbook Vol.2, Smithells) for Cu/Al/W/Mo/Ag/Au.

- New `domains/silicon/materials_grounding.py`: cross-validates `interconnect.py`'s
  hardcoded metal table against an independently CITED reference (Cu/Al/W/Mo/Ag/Au lifted
  from CHEM metal_bridge; Co/Ru from Gall J.Appl.Phys. 2016; TaN from CRC/ITRS). Each
  metal gets a grounding receipt + evidence tier `literature_value`.
- **It earned its keep — caught real discrepancies:** Cu/Al/Co/TaN grounded (0% error),
  but W flagged (table 5.60 vs cited 5.28 bulk; thin-film/CVD note) and Ru flagged (7.10
  vs 7.60; literature spread). Grounding surfaces, doesn't hide.
- **Grounded the EM-robustness claim in an independent property:** Spearman(melting point,
  EM activation) = +1.00 — perfectly concordant (Al < Cu < Co < Ru < W on both). The
  EM ordering is now backed by real Tm data, not asserted.
- Wired into `recommend_interconnect`: a metal swap now carries cited receipts + tier
  (e.g. hot net -> Cu→W, "Cu [grounded; ASM/Smithells]", "W [flagged; bulk value]").
- `tests/test_silicon_materials_grounding.py` (6 tests) + suite green (19 related pass).
- **Next (Phase 4):** close the loop — hotspot net (Phase 1-2) → grounded material fix
  (Phase 3) → re-verify it improves the real metric → keep only if proven.

## 2026-06-20 (later) — Phase 4 DONE: reliability co-design loop closed (find→fix→PROVE)

New `domains/silicon/codesign_loop.py` ties the whole bridge together and — crucially —
proves BOTH sides of the fix, not one:
- FIND: worst current-demand nets from the validated hotspot signal (Phase 1-2).
- FIX: grounded interconnect swap (Phase 3, cited).
- PROVE: EM lifetime gain via **Black's equation** (MTTF ~ exp(Ea/kT); grounded Ea) AND
  the **resistance cost** (cited ρ_new/ρ_old). A Cu→W swap gives ~10^11x EM lifetime but
  3.3x resistance — only worth it on a SHORT local net (bounded absolute R). The net's
  REAL wirelength (layout) decides: local→swap, global→widen_wire instead.
- KEEP/REJECT: gated by the same HonestyGate that grounds the recommendation; HOLLOW→reject.
- **Honest real result:** on aes/ibex the worst-current nets are all long global lines, so
  the loop correctly refuses the swap (would triple R) and redirects to widening — exactly
  the right call, and a genuine co-design *decision*, not a rubber stamp. (Fixed a
  `_wirelen` None-guard.) tier=`validated_hypothesis` (cited physics + real geometry).
- `tests/test_silicon_codesign_loop.py` (5 tests: swap-for-local, widen-for-global,
  reject, real-aes). **Full suite: 268 passed.**
- **Next (Phase 5):** productize — one CLI/portfolio that runs find→fix→prove on a layout
  and emits the receipt-backed reliability action portfolio.

## 2026-06-20 (later) — Phase 5 DONE: productized. ALL FIVE PHASES COMPLETE ✅

New `domains/silicon/reliability.py` + agent CLI `reliability` command = the product:
one command on a real layout emits WHERE (validated hotspots) + WHAT (proven co-design
actions) + WHY (the evidence ladder, every claim tiered). `assess_reliability()` composes
Phase 2 hotspots + Phase 4 actions; `to_dict()` exposes the evidence_ladder
(measured → measured_proxy → validated_hypothesis → literature_value).
- CLI: `python -m domains.silicon.agent_tools --def .. --spef .. --lef .. reliability`
  → JSON report (hotspots + fixes + tiers + provenance). (Fixed a missing `import os`.)
- `tests/test_silicon_reliability.py` (2 tests); phase 1-5 sweep 19 pass.
- Updated `docs/SILICON_FINDINGS.md` with "The product, built" section.

**The reliability co-design wedge is real, end-to-end, tested, and honest.** The whole
arc this session: timing-prediction falsified (the right way) → pivot → structure PREDICTS
real IR-drop (measured win) → hotspot detector → materials grounded in cited data →
find→fix→prove loop → one productized report. The differentiator is the evidence ladder:
incumbents compute EM/IR; none connect stress to a grounded, PROVEN materials fix with a
checkable receipt for every step.

## 2026-06-20 (later) — Phase 6: Jmax grounding + the trust-layer demo

Pushed on the open edges.
- **Jmax grounding (6a):** added cited EM current-density capacity (Jmax, IRDS/Hu) to the
  metal reference. Second independent EM check — Spearman(Jmax, EM activation) = +1.00
  (Al<Cu<Co<Ru<W), concordant with the melting-point check. The co-design swap reason now
  cites the current-capacity gain (Cu→W = x10 current before EM failure), not just Black's
  eq. NOTE the "swaps never fire" edge was NOT a bug: on aes/ibex the high-current nets are
  genuinely long/global, so widen is correct; the swap branch is right to stay quiet and is
  unit-tested for local nets.
- **Trust layer (6b):** `domains/silicon/trust_layer.py` — gate ANY external/black-box
  proposer behind the receipt. A proposal is kept only if its asserted values MATCH the
  cited facts AND grounds via HonestyGate. Demo: grounded ranker → KEEP; an LLM asserting
  fabricated values (0.99 vs cited 0.80) → BLOCK ("fabricated rationale"); unknown metal →
  BLOCK. (First pass accepted the fabrication because HonestyGate grounds *vocabulary* not
  *values*; added an explicit value-vs-cited-fact check to catch it.) This is the meet-the-
  market story: use black-box AI EDA tools without trusting them blindly.
- `tests/test_silicon_trust_layer.py` (5) + grounding Jmax test; suite green.
- **The five-phase product + trust layer are complete.** Honest remaining: a sub-7nm
  design would exercise the metal-swap branch; real per-segment EM current-density (vs
  Jmax, using LEF cross-sections) would lift the EM check from validated_hypothesis toward
  measured; wrap a *real* third-party ML tool (not a demo stand-in) through the trust gate.

## 2026-06-20 (later) — Phase 7: the IR-drop win is NODE-DEPENDENT (honest narrowing)

Minted **7nm (ASAP7)** gcd + aes via ORFS to test whether the core IR-drop finding
generalizes across technology nodes. **It does NOT.**
- 7nm aes (23k cells, real 19% worst IR drop): scoreboard **FAILS** — structural signals
  collapse and density *inverts* (−0.30, stable across grids); best demand +0.10. The
  45nm aes regression check still passes (+0.598), so it's real, not a code bug.
- **Physics:** at mature nodes (fat, low-R wires) IR drop tracks local current demand
  (structure sees it). At 7nm (thin, resistive wires) IR drop is dominated by the
  resistive PDN delivery path, not local demand — the bottleneck moves from current-draw
  to delivery, so the cheap signal fails (denser/better-gridded regions even drop less).
  Caveat: one 7nm design + ORFS default PDN; node-vs-PDN not fully disentangled, but the
  direction is stable.
- **Product scope narrowed honestly:** the cheap IR-drop detector is validated for MATURE
  nodes (~28-130nm — automotive/IoT/analog/power/MCU, most chips by volume); advanced
  nodes need the real PDN tool. 7nm gcd was too small to test (768 cells, noise). Updated
  `docs/SILICON_FINDINGS.md` with Result 3.
- This is the system working as intended: it falsified an over-broad claim with real
  measured data and a clean control, and narrowed the product to where it actually holds.

## 2026-06-20 (later) — measured-EM lift (edge #2 done) + honest system audit

**System audit (user asked):** the reliability PRODUCT (Phases 1-7) imports only
`core.category` + `core.honesty_gate`. PRONOIA is touched by one older file
(`material_bridge.py`), NOT the product. ~50k+ lines of math (oracle/geometry/zfc/
categorical/operadum/cog/hott/cubical/game) are DORMANT relative to the product. Honest
read: the proven value is the DISCIPLINE (receipts/grounding) + the materials↔layout
bridge, not the exotic math. Forcing dormant engines in = cargo-culting. Rule: only wire a
dormant engine in if it passes a real measured test like everything else. "Meaningful" =
built on a validated step AND checkable against real data (why the 7nm swap test was moot —
the find step failed there).

**Edge #2 — measured EM (done):** turning measured EM current into current-DENSITY needs
per-segment wire widths the report lacks (high-current segments are wide PDN straps; min-
width grossly overestimates). So instead validated EM *detection* directly: new
`em_scoreboard.py` tests whether structure predicts the REAL measured EM current (OpenROAD
`analyze_power_grid -enable_em` per-segment current, binned to tiles). **PASS on 45nm aes:
density +0.638, demand/fanout +0.593, clean control.** The EM hotspot detection is now
MEASURED-validated, not just Black's-eq estimated — lifts the EM find-side toward measured.
Same 45nm-node caveat as IR (PDN-delivery-structured). `tests/test_silicon_em_scoreboard.py`
(2). Updated hotspot VALIDATION receipt (now cites IR +0.5 AND EM +0.64).
**Edges #1 (sub-7nm swaps) and #3 (real ML tool thru trust gate) remain not done.**

## 2026-06-20 (later) — edge #3 done properly: a learned model, trust-gated, beats baseline

Built a REAL proposer (not a stand-in): `ml_hotspot.py` — a ridge-regression IR-drop
predictor over per-tile layout features (cap, fanout, density, area, demand, distance-from-
center), trained on one design and evaluated on a DIFFERENT one (cross-design held-out).
- **Learning beats the cheap baseline, both directions:** train aes→test ibex ML +0.572 vs
  baseline +0.478; train ibex→test aes ML +0.657 vs +0.597. The multi-feature + spatial
  combination captures PDN-delivery structure the single demand signal misses (modest but
  consistent ~+0.06-0.09 gain). Generalizes across designs.
- **The trust gate has TEETH:** it accepts the model only if it beats a shuffled control on
  HELD-OUT data. A model trained on signal but tested on noise is BLOCKED (in-sample looks
  fine, held-out fails) — exactly the black-box failure the gate exists to catch. This is
  the project roadmap's rule made real: a learned model must show held-out value and may
  never gate a verdict (proposal-side only, numpy+stdlib).
- `tests/test_silicon_ml_hotspot.py` (3: trusted-generalizes, blocked-on-noise, real-data).
  Suite green. This makes #3 genuinely done with a real model, not a demo stand-in.
- **Edge #1 (sub-7nm swap branch) still open** — and lower value, since the IR/EM detector
  itself fails at 7nm (node finding), so a swap test there isn't grounded.

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
