# Silicon — Post-Moore strategy plan (3 tracks)

> Written 2026-06-20. Companion to `docs/HANDOFF.md` (start-here) and
> `docs/SILICON_FINDINGS.md` (what's true/false, with receipts).
> This plan re-aims the proven product at where the industry is actually going.

## The reframe

Three leading-edge strategies have all stopped chasing the transistor and started
co-optimizing **everything around it**:

- **Huawei τ ("Tau") Scaling Law** — optimize *signal-propagation delay* (τ), not feature
  size, via LogicFolding (shorten critical-path **wiring**) and UnifiedBus (cut
  **system-interconnect** latency). Density-equivalence through architecture + integration,
  not lithography. An **interconnect/delay** play.
- **TSMC multi-patterning** — extend Low-NA EUV with multi-patterning to dodge ~$5–10B of
  High-NA capex; the binding risk lever is **Edge Placement Error (EPE)** — a
  pattern-fidelity / overlay-coherence problem.
- **Intel directed self-assembly (DSA)** — let block-copolymer physics self-assemble the
  fine pitch (e.g. 150nm template → 50nm pitch), guided by a coarse template. Binding risks
  are **stochastic defectivity** and **placement error** — i.e. *materials-statistical*, not
  machine-deterministic. The roadmap explicitly calls for "DTCO for manufacturing."

All three invoke **co-optimization (DTCO/STCO)** by name. That is exactly the slot this
system occupies: *a co-optimization layer with a checkable receipt on every claim.*
"Structure substitutes for scale" is now the industry's playbook, not just ours.

## The discipline (unchanged — it is the moat)

Every track below obeys the project's standing rules:
- A capability counts only with a **measured/cited receipt** and a **shuffle/held-out
  control**. Proposal ≠ verification.
- Evidence tiers stay honest: `measured` > `measured_proxy` (SPEF/extraction) >
  `validated_hypothesis` (cited physics + real geometry) > `literature_value`.
- **Dormant root math is wired in only if it earns its own receipt** — never for show.

## What the industry's move does to our known boundary

We **falsified** cheap structure predicting **gate-level timing slack** (the optimizer
equalizes slack). We **validated** structure predicting **IR-drop (+0.5–0.6)** and
**measured EM current (+0.64)** at mature nodes — quantities optimization does *not* flatten.

The post-Moore constraints (interconnect delay, power delivery, EM, variability/EPE) are
precisely the *un-flattened* family. Timing-slack is not the bottleneck of this regime;
these are — and three of the four are in or adjacent to our proven wheelhouse.

---

## Track 1 — τ interconnect-delay (Huawei). **Executable now.**

**Question (falsifiable):** does cheap *structure* predict real **interconnect RC delay**
the way it predicts IR/EM — and *unlike* gate slack? This is the substrate of Huawei's τ
thesis: τ is wire delay, and wire delay ≈ R·C ≈ resistance·(load·length) — the same
physical family we win on, not the optimizer-flattened slack we lose on.

**Two evidence tiers:**
- **(now, `measured_proxy`)** `tau_scoreboard.py` — extract per-net **Elmore RC** from
  detailed SPEF (R from `*RES`, C from `*D_NET`), score structural predictors
  (fanout, wirelength, degree, curvature, driver/sink area — all SPEF-free) against it,
  with the standard shuffle control. Data in hand (`data/sta_45gcd/` detailed SPEF).
- **(DONE ✅, `measured`)** `net_delay.py` + `tau_scoreboard_measured()` score structure vs
  the tool's *own* per-net interconnect delay (load-input-pin rows attributed to nets via
  the DEF pin→net map). Ran real OpenROAD STA (`sta_flows/tau_netdelay_sta.tcl`):
  **PASS on 45_gcd, fanout +0.645, wirelength +0.516, control −0.053, 274 nets,
  `status: measured`.** Consistent with the proxy (+0.61) and slightly stronger. So the τ
  thesis holds at the tool's authoritative tier: **interconnect delay is structurally
  predictable; gate slack is not.**

**Why it matters:** if structure predicts wire-delay, we have a τ-aligned cheap screen for
the metric Huawei just declared the scaling axis. If it doesn't, that's honest signal that
delay (even wire delay) needs the extractor — also worth knowing.

## Track 2 — System / package interconnect geometry. **Gated on data (gettable).**

**Thesis:** at the package/chiplet/system level (UnifiedBus, advanced packaging) the wires
are **fat again** — back in the mature-node regime where our IR/EM prediction *holds* — and
the money/bets are concentrating there. Our Ricci-corridor / Fiedler-seam geometry
(`flow_geometry.py`, `partition.py`) was *built* to find congestion bottlenecks and chiplet
boundaries.

**Plan:** point the existing geometry at a real package/chiplet-level netlist (multi-die,
interposer, or NoC). The code path already exists; this is a **data-acquisition** task
(public chiplet/NoC layouts) plus a validation target (package-level IR/thermal/latency).

**Proxy experiment run (2026-06-20) — honest, weak result.** `system_scoreboard.py`
partitions a real die into chiplet-analogue blocks, marks boundary-crossing nets as the
system interconnect, and tests vs REAL measured IR-drop. On aes + ibex the signal is **weak
and design-dependent**: inter-block nets sit in only ~5–12% higher IR regions (aes 1.06×
FAIL, ibex 1.12× PASS); block `system_load` predicts block IR cleanly on ibex (+0.47,
control −0.00) but is null on aes. Shuffle controls collapse to ~1.0, so the mechanism is
sound — the *signal* is just weak. **Verdict:** a within-die proxy does NOT substitute for
real package data; the system-interconnect-stress thesis needs an actual multi-die/chiplet
layout to test. The partition→classify→validate path is built and ready to point at one.
`tests/test_silicon_system_scoreboard.py` locks the honesty mechanism (control collapses),
not a design-dependent pass.

**Real multi-die data acquired + a measured WIN (2026-06-20).** Scouted public datasets
(see below) and pulled **Open3DBench** (`github.com/lamda-bbo/Open3DBench`): 8 real
face-to-face 3D-IC designs (ariane133/136, black_parrot, bp_*, swerv_wrapper), each two
stacked dies tiled 10x10, with committed HotSpot per-tile **power** and steady-state
**temperature** — a genuine multi-die boundary with measured-analogue thermal ground truth,
no multi-hour run. `thermal3d_scoreboard.py` asks the genuinely-3D question a within-die view
cannot: *does a tile's temperature depend on the power of the tile STACKED across it on the
OTHER die?*
- **RESULT — yes, strongly, on 8/8 designs.** Cross-die (stacked) power predicts tile
  temperature far better than the tile's OWN power; own-die power is often *negatively*
  correlated. Adding the cross-die term beats the 2D baseline on **8/8 designs, mean coupling
  gain +0.54** (e.g. bp_fe own −0.558 → stacked +0.564; bp_multi own −0.194 → stacked +0.631),
  shuffle controls collapse (~0).
- **Why this matters:** this is exactly the system/multi-die effect the within-die proxy was
  blind to — it explains the weak proxy result. In a 3D stack the dominant thermal driver is
  the *opposing die*, and cheap structure (a tile's cross-die power) captures it. Track 2 now
  has a real, measured, multi-die receipt.
- **Per-die-split refinement (done) — the finding is real AND directional.** Splitting by die
  to remove the heat-sink confound: the coupling **survives strongly for the UPPER (sink-far)
  die — 7/8 designs, mean gain +0.45** (swerv +1.08, bp_fe +0.76, bp_be +0.56) — but is **~0
  for the BOTTOM (sink-adjacent) die (5/8, mean +0.02)**. Physically sensible: the die far
  from the heat sink must dump its heat *through* the other die, so the sink-near die's power
  governs the sink-far die's temperature, not the reverse. So the pooled 8/8 was partly
  inflated by die position; the true effect is **directional cross-die coupling onto the
  sink-far die**, which a within-die view cannot capture and cheap structure predicts.
- **Honest residual:** power→temperature is partly trivial; the informative parts are the
  *sign flip* (own-die power negative) and the *direction* (sink-far die only). `tests/
  test_silicon_thermal3d.py` checks planted-coupling recovery, the per-die split, and real
  bp_fe (upper-die coupling > 0.1).
- **Next:** pull Open3DBench per-die DEFs (their MoL flow) to run the placement geometry +
  extend the τ measured net-delay test to 3D.

## Track 3 — multi-view pattern-fidelity coherence (TSMC EPE + Intel DSA). **Engine BUILT; data-gated.**

**Unification:** TSMC's **Edge Placement Error** and DSA's **placement error** are the same
shape — "did the realized pattern register to design intent, and where does it deviate?"

**The engine already exists and is tested** (audited 2026-06-20, files read in full —
`docs/SILICON_MATH_INVENTORY.md`):
- `topology/persistent_sheaves.py` → `CellularCochainComplex`: exact H⁰/H¹ via SVD, verifies
  δ¹∘δ⁰=0, and **localizes `h1_support`** (which edges carry the obstruction).
- `domains/silicon/coherence.py` → `analyze_calibration_nerve` already wires it to silicon,
  and honestly refuses to invent unjustified calibrations.
- `domains/silicon/verilog.py` → the independent *logical* view (terminal-set crosswalk).
- Trust-weighting: the oracle **corroboration + specificity** cluster (`horns_retrodiction`,
  `coherence_specificity`) — a deviation is real only if multiple independent views
  corroborate it, down-weighted so a non-specific/global view can't over-vouch.

So Track 3 is **not a math build** — it needs (a) a genuine *third independent view* (the
current verilog↔def↔spef is a 2-view chain → H¹=0 by construction), and (b) real data + a
measured test. **Multi-patterning supplies (a) for free:** N masks of one layer are N
independent views of the same target → mask disagreement = a real H¹ obstruction, and
`h1_support` localizes the EPE-risk features.

### The buildout (receipt-gated, chip-first)
- **Step A — DONE ✅ (`fidelity_coherence.py`).** Three independent tool views of net
  connectivity on self-minted `orfs_gcd` — verilog (synth), def (route), spef `*CONN`
  (extraction), each net→terminal-set, cross-view identity by terminal set. **Real result:
  H0=1, H1=0 (coherent, no cyclic obstruction); 482/627 nets agree exactly across all three;
  def~spef 0.915 after escaping normalization.** Divergences are representational (name
  escaping + verilog flop-pin scope), localized per net — not logical faults. H¹
  obstruction-localization demonstrated on the cyclic (EPE-shaped) case (unfilled triangle →
  H1=1, localized); injected faults localize. `tests/test_silicon_fidelity_coherence.py` (4).
  The engine is wired to real silicon with a receipt; the "is it even wired" risk is gone.
- **Step B — multi-patterning decomposition coherence (scouted 2026-06-20).**
  **The honest math fit (not cargo-cult):** double-patterning (LELE, K=2) is feasible iff the
  conflict graph is 2-colorable iff it has **no odd cycles** — and an odd cycle is exactly a
  **Z/2 H¹ obstruction** (graph frustration / signed-balance). So our exact-cohomology engine
  can *localize the native double-patterning conflicts* (the unresolvable regions). Honest
  boundary: triple+ patterning (K≥3) is NP-hard graph coloring (OpenMPL's domain, **not**
  cohomological) — we do NOT subsume it; the clean fit is **double-patterning native-conflict
  localization**.
  **Data:** `OpenMPL` (github.com/limbo018/OpenMPL, open source, GDS→mask assignment + conflict
  graph; ships ISCAS + ISPD'19 benchmarks) is the ground truth for native conflicts. **No-build
  first cut:** the conflict graph is pure geometry — same-layer features within the coloring
  distance = a conflict edge — so we can build it directly from a real DEF/GDS layer (data in
  hand) and test whether our H¹ localizes the odd-cycle native conflicts, using OpenMPL only as
  a cross-check later (it needs a C++/Boost/Limbo build).
  **Small extension needed:** the current cochain complex is over ℝ (SVD); odd-cycle 2-coloring
  is a **Z/2 / signed** obstruction, so add a signed (frustration) coboundary. Tier: tool/
  geometric decomposition-conflict (not foundry-measured EPE — that stays gated).
  Gate the verdict with the oracle corroboration+specificity pattern + the trust gate.
  - **First cut DONE ✅ (`dp_conflict.py`).** Conflict graph from REAL cell placements
    (orfs_gcd DEF) + the signed/Z2 obstruction two ways (combinatorial BFS 2-coloring +
    spectral max-component `lambda_min(D+A)`), which AGREE. Distance sweep on 681 cells:
    1500 dbu → 2-colorable, 0 native conflicts; 2500 → 81 native conflicts (frustration 1.0);
    4000 → 949 (1.63) — a clean colorable→native transition, native conflicts **localized to
    feature pairs**. `tests/test_silicon_dp_conflict.py` (4). The engine now localizes native
    double-patterning conflicts on a real layer. *Upgrades:* real GDS metal shapes (vs
    placement proxy) + OpenMPL conflict-graph ground-truth cross-check.
  - **Real GDS metal shapes DONE ✅ (`gds.py` stdlib GDSII reader + `analyze_gds`).** Conflict
    graph now from actual routing shapes (top-cell `gcd`, layer 13 = 1890 shapes), bbox-gap
    proximity. At min-width spacing (700 db units) the layer is **not 2-colorable: 87 native
    conflicts localized**, rising to 1130 at 2800 — realistic (dense real routing needs
    multi-patterning), with BFS↔spectral still agreeing.
  - **SREF cell-internal metal DONE ✅ (`flatten_gds_shapes` + `analyze_gds(flatten=True)`).**
    The "top-cell routing only" boundary is retired: the GDSII reader now resolves the SREF/AREF
    hierarchy (4514 instances in `gcd`), placing standard-cell internal metal into the top frame
    with the full GDS transform (reflect→mag→rotate→translate, recursive; verified spanning the
    DEF die area exactly). The real dense layer appears: **M1 (layer 11) 25 → 6076 shapes, NOT
    2-colorable, 7303 native conflicts localized, λ_min(D+A)=0.62** — M1 being the canonical
    double-patterning layer is exactly the point. This exposed + fixed a latent honesty bug:
    `spectral_frustration` silently skipped components >2500 nodes (false 0); now exact dense
    `eigvalsh` ≤2000 + numpy-only sparse power iteration above, so no component is skipped.
    Honest limit: the sparse estimate confirms by magnitude (convergence floor); BFS Z/2 stays
    the exact verdict. 14 dp_conflict tests. **Open: OpenMPL conflict-graph cross-check** (needs
    a C++/Boost/Limbo build — no native toolchain here, Docker only).
- **Step C — wire the verdict through the trust gate + COG/honesty** (proposal→verification),
  same discipline as the rest of the product.

**Materials angle (distinctive):** DSA constraints are materials-statistical, so
`materials_grounding.py` extends from metals to block-copolymer parameters (χ, pitch L₀,
defect energetics) — cited, receipted.

**Honest blocker (unchanged for Steps B/C):** real EPE/defect/placement-error data lives on
foundry/research 300mm pilot lines. Step A removes the "is the engine even wired" risk now;
Steps B/C stay gated on data + a measured test. No coherence claim ships without one.

**Why this is chip work, not math:** this is the *pattern-fidelity + trust* half of the
product (the TSMC-EPE / Intel-DSA wedge from §reframe) — gate black-box computational-litho /
DSA-defect models behind a localized, corroborated obstruction receipt.

---

## Sequence (by actionability, not by appeal)

1. **Track 1 — DONE** (both tiers): structure predicts interconnect RC (proxy +0.61) and the
   tool's own net delay (measured +0.645). ✅
2. **Track 2 — DONE** (real multi-die): 3D cross-die thermal coupling on Open3DBench, 8/8
   designs, directional (sink-far die), measured. ✅
3. **Track 3 Step A — DONE ✅:** `fidelity_coherence.py` wires the exact H⁰/H¹ engine to real
   `orfs_gcd` (verilog/def/spef three-view) → H0=1/H1=0 coherent receipt; cyclic case → H1=1
   localized. The "is the engine wired to chips" risk is gone.
4. **Track 3 Steps B/C — data-gated:** multi-patterning mask-nerve coherence vs real EPE data,
   gated by oracle corroboration+specificity, wired through the trust gate. Needs foundry/
   research placement-error data + a measured test.

The honest order: Tracks 1–2 banked with measured receipts; Track 3's *engine is built and
audited* (exact H⁰/H¹ + silicon adapter), so Step A is a wiring proof on data in hand, and the
frontier (EPE/DSA) is the data-gated part — not a math build.

## Sources

- Huawei Tau Scaling Law (IEEE ISCAS 2026): huawei.com/en/news/2026/5/ieee-iscas-tau-scaling
- Tom's Hardware — Huawei 1.4nm-class by 2031 / LogicFolding; TSMC no High-NA for 1.4nm-class
- TrendForce — TSMC A12/A13 2029 roadmap without High-NA EUV
- SemiEngineering — "DSA Re-Enters Litho Picture"; "EUV + DSA strategy progress"
