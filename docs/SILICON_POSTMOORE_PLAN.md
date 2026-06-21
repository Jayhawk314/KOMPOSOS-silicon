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

## Track 3 — EPE / DSA pattern-fidelity coherence (TSMC + Intel). **Gated research probe.**

**Unification:** TSMC's **Edge Placement Error** and DSA's **placement error** are the same
shape — "did the realized pattern register to design intent, and where does it deviate?"
Our dormant **sheaf H⁰/H¹ cohomology** (`topology/persistent_sheaves.py`) already localizes
where multiple views of one artifact fail to cohere. One dormant-math home, two strategies
served: a **pattern-fidelity coherence layer** (multi-patterning masks *or* DSA
template→assembly) that localizes the obstruction.

**Materials angle (our distinctive asset):** DSA's constraints are materials-statistical, so
`materials_grounding.py` extends naturally from metals to block-copolymer parameters
(χ, natural pitch L₀, defect energetics) — grounded, cited, receipted. And the trust gate is
purpose-built for trusting stochastic defect/computational-litho models under uncertainty.

**Honest blocker:** real EPE/defect/placement-error data lives on foundry/research 300mm
pilot lines — far harder to get than ORFS output. This is a **research probe gated on data**,
not a near-term product claim. Per the rule: no coherence claim without a measured test.

---

## Sequence (by actionability, not by appeal)

1. **Track 1 now** — prove (or falsify) structure→interconnect-RC on real `45_gcd`. Data in
   hand. *(This session.)*
2. **Track 1 measured upgrade** — STA `-fields {net}` net-delay re-run when Docker is up.
3. **Track 2** — acquire a package/chiplet layout; re-aim existing geometry; validate.
4. **Track 3** — pursue EPE/DSA coherence + BCP grounding *iff* real placement-error data
   becomes available; until then it stays a designed, unbuilt probe.

The honest order: earn the τ receipt we *can* get, and use it to earn the right to chase the
materials/variability frontier where DSA's deepest fit — but hardest data — lives.

## Sources

- Huawei Tau Scaling Law (IEEE ISCAS 2026): huawei.com/en/news/2026/5/ieee-iscas-tau-scaling
- Tom's Hardware — Huawei 1.4nm-class by 2031 / LogicFolding; TSMC no High-NA for 1.4nm-class
- TrendForce — TSMC A12/A13 2029 roadmap without High-NA EUV
- SemiEngineering — "DSA Re-Enters Litho Picture"; "EUV + DSA strategy progress"
