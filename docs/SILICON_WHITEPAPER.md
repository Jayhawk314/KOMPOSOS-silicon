# KOMPOSOS‑V Silicon Co‑Design — Methods, Findings, and Directions

> A conceptual + strategic companion to the operational docs. `SILICON_PLAN.md` is the
> roadmap, `SILICON_STATUS.md` the capability ledger, `SESSIONS.md` the chronological log.
> This document explains **what we found, the mathematics we use to find it, and where it
> can go** — including pivots into specific chip‑design needs and how to make the system
> modular for working engineers. Everything here is grounded in the committed code
> (`domains/silicon/`) and the measured results; proxies are labelled as proxies.

---

## 1. What this system is (in one paragraph)

It is a **structural co‑designer and triage layer for chips** that runs on a laptop. It
ingests the same files an EDA flow emits — gate netlists (Verilog), placement and
connectivity (DEF), parasitics (SPEF), the cell library (LEF), and timing (STA) — turns
them into one shared categorical object, and runs *mathematics that is cheap but
structurally honest* over them: curvature, spectral cuts, sheaf coherence, Kan
aggregation, and material physics. It never replaces SPICE, RedHawk, or a router. It
**screens**: in seconds it flags the few nets/regions/interfaces worth an expensive tool's
attention, and every claim it makes carries an evidence tier and a provenance receipt, so
an engineer (or an AI agent) reads computed findings instead of inventing numbers.

The bet, inherited from the substrate: **structure substitutes for scale.** Instead of a
large trained model, small categorical engines compose so that every kept claim is *built,
executed, verified, grounded, and judged.*

---

## 2. The two laws everything obeys

1. **Proposal vs. verification is sacred.** Scores, curvature, embeddings, and material
   rankings only *propose*. The symbolic layer — composition, COG, ZFC, and the
   `HonestyGate` — *verifies*. A proposal never writes to memory or stands in for a verdict.
2. **Evidence is tiered honestly.** Every claim is tagged:
   - `structural_only` — geometry/topology alone (a proposal).
   - `validated_hypothesis` — rests on cited physics (the 5 material scorers + lattice veto).
   - `measured_proxy` — extracted by a tool (SPEF capacitance, current‑demand proxy).
   - `measured` — a real device/EDA measurement (STA slack, PDN/IR). Reserved; not faked.

These two laws are why this is different from a GNN placer: a GNN gives a confident layout
with no way to say which parts are unjustified. Here, "unjustified" is a first‑class verdict.

---

## 3. The mathematics — what each tool *discovers*

The power of the approach is that each piece of mathematics answers a concrete physical
question from public data, cheaply.

### 3.1 The shared `Category` — one object for everything
A chip is loaded as a category: **objects = blocks/instances/materials**, **morphisms =
wires/interfaces/relations**. Because materials and layout live in the *same* category, we
can reason about "this interface is physically unviable" and "this net is congested" as the
same kind of thing — which siloed EDA tools cannot. (`netlist_bridge.py`, `material_bridge.py`)

### 3.2 Ollivier‑Ricci curvature → routing‑congestion corridors
On a graph, the Ollivier‑Ricci curvature of an edge compares the "distance" between the
neighbourhoods of its two endpoints to the edge length (via optimal transport / Wasserstein
distance). **Negative curvature = a tree‑like bridge whose endpoints' neighbourhoods don't
overlap** — exactly the structural bottleneck where routing congestion concentrates and a
single cut partitions the design. We compute it on the routing graph to surface congestion
corridors *from topology alone, with no congestion map*. (`flow_geometry.py`, `geometry/ricci.py`)

### 3.3 Spectral / Fiedler analysis → chiplet seams
The graph Laplacian's second‑smallest eigenvalue (the **Fiedler value / algebraic
connectivity**) measures how hard the design is to cut; the sign pattern of its eigenvector
(the **Fiedler vector**) exhibits the weakest seam. That seam is the natural place to sever
a monolith into chiplets (e.g., a UCIe die‑to‑die boundary). On the synthetic chip it
recovers the two cores and the bus between them with no hint; on real GCD it finds the seam
unprompted. (`flow_geometry.py`, `geometry/spectral.py`)

### 3.4 Sheaf cohomology (H⁰/H¹) → cross‑artifact coherence
RTL, the gate netlist, the placed layout, and the parasitics are four *views of the same
chip*. Treat them as sections of a presheaf over the design's blocks. They **glue** iff they
agree on overlaps. Exact sheaf cohomology gives this teeth: **H⁰ = the globally consistent
data**, **H¹ = the obstruction to gluing** — a localized incoherence (a buffer the netlist
declares but the layout optimized out; an IR‑drop vulnerability where one calibration can't
reconcile all the parasitic models). This is the principled version of "the layout tool and
the synthesis tool disagree." (`coherence.py`, `topology/persistent_sheaves.py`)

### 3.5 Left Kan extension → gates‑to‑tiles aggregation
To go from per‑gate data to per‑region telemetry you need a *functorial* aggregation, not an
ad‑hoc bucketing. The **left Kan extension** of the gate‑metrics functor along the
gate→tile map is exactly "sum each gate's contribution into its physical tile," and it is
**mass‑conserving** by construction (we test that gate count and fan‑out are conserved
across tiles). This gives honest tile‑level switching‑capacitance / area / fan‑out maps. On
real GCD, tile fan‑out and wirelength predict tile SPEF capacitance at ρ≈0.99. (`tiles.py`,
`categorical/kan_extensions.py`)

### 3.6 Coloured operads → n‑ary nets
A real net connects many pins, not two. Category theory's correct tool for n‑ary relations
is the **coloured operad**, not a hypergraph: one operadic operation per signal net, with
laws (DEF‑order and LEF‑order invariance) that the binary graph projection must respect.
This keeps the netlist model categorically honest while still letting curvature/Fiedler run
on a recorded binary projection. (`net_operad.py`)

### 3.7 The five material scorers + lattice veto → interface viability
A heterostructure interface is scored on five physics axes — lattice match, band alignment,
thermal compatibility, process compatibility, degradation penalty — combined into a weighted
viability composite, with a hard **lattice veto** (>3% mismatch ⇒ dislocations ⇒ no coherent
epitaxy). This is screening‑grade materials triage from cited property tables, not a DFT
run. (`scoring.py`, `materials_data.py`, `material_bridge.py`)

### 3.8 COG + HonestyGate → the verdict
A proposal becomes a kept claim only if **COG ≠ REJECT** (no contradiction in the committed
graph) **and** the `HonestyGate` finds its rationale *grounded* in committed evidence
(grounding = 1 − fabricated fraction, via compression distance, in the same `"src rel tgt
conf"` vocabulary as the evidence). A confident score on missing data is `HOLLOW`; an
unsound one is `REJECT`. (`material_bridge.verdict_for_interface`, `core/honesty_gate.py`,
`cog/`)

### 3.9 Effective‑resistance curvature + partitioning → scale
Exact Ollivier‑Ricci is optimal‑transport per edge; even the effective‑resistance
approximation is O(n²) (a Laplacian pseudoinverse). Neither runs whole on a 100k‑cell block.
But congestion is *local*, so we **partition first** — recursive spatial (placement) median
bisection, O(n log n) — into bounded regions, then run curvature per region (independent,
parallelizable). Inter‑region edges are seams, found by the cheap global spectral pass. The
worst‑inter‑region bottleneck is the seam; intra‑region corridors are the congestion. This
is "design triage over detail" made literal. (`partition.py`, `_region_worker.py`,
`geometry/fast_ricci.py`)

### 3.10 The GenerativeLoop → self‑learning remediation
Fixes are typed transforms on a discrete risk level (swap interconnect, widen wire, reroute
to upper metal, insert buffer). The substrate's `GenerativeLoop` — the same engine that grows
NAND→XOR — composes them under OPERADUM, gates the composite with COG, and **a verified
remediation becomes a primitive for the next pass**, converging when nothing new can be
added. A fix is grounded on real data (before/after the risk proxy drops, gated), not
asserted. (`fix_loop.py`, `core/generator.py`)

---

## 4. The findings — what we actually discovered and validated

These are measured, falsifiable results (see `tests/` and `domains/silicon/scoreboard.py`),
not aspirations.

### 4.1 The triage signal is real, and we know *which* signal
The scoreboard asks: do cheap predictors computed **without** SPEF rank nets the same way
the physically‑extracted SPEF capacitance does? With a shuffle control that must collapse
to ~0.

| Design | best predictor | Spearman ρ | prec@10 | shuffle control |
|---|---|---:|---:|---:|
| real gcd | **fanout** | +0.563 | 0.80 | +0.08 |
| real 45_gcd (no LEF) | fanout | +0.582 | 0.80 | +0.09 |
| real 45_gcd (with LEF) | fanout | +0.584 | 0.80 | −0.03 |

- **It passes** on real silicon: the top‑10 structural picks catch **80%** of the
  physically heaviest nets, in seconds, and the control proves it isn't an artifact.
- **An honest, non‑obvious finding:** pure‑topology *curvature* is a **weak per‑net**
  congestion predictor on real designs (ρ≈0.13–0.16) — it only looked strong on the planted
  toy. So Ricci/Fiedler belong to **seam and partition** analysis; **fan‑out/degree dominate
  per‑net congestion.** A scoreboard earning its keep by overturning an assumption.
- **LEF matters, and we measured how:** adding the real cell library (so the net's driver is
  its actual OUTPUT pin, not a guess) roughly **doubled** the geometric correlations on
  45_gcd (curvature +0.13→+0.28, wirelength +0.24→+0.44). The value of LEF is *fixing graph
  direction*, not the cell‑area features (which were weak).

### 4.2 Material verdicts behave like physics
`GAN_ALGAN_POWER` (GaN/AlGaN, ~0.6% mismatch) → **AGREE** (persisted, gated). `PROBLEMATIC_
GAN_GAAS` (wurtzite‑on‑zincblende, ~56% mismatch) → **REJECT** via the lattice veto. The
gate is real: a recommendation that referenced a net name instead of committed property
facts came back `HOLLOW` until re‑grounded in the property vocabulary.

### 4.3 The layout↔materials loop closes
An electromigration‑risk net (high current‑demand proxy = cap × fan‑out) is handed to the
interconnect bridge, which ranks metals on the genuine **EM‑resistance vs. resistivity**
trade‑off: cool nets keep **Cu** (conductivity wins); hot nets get **W/Ru/Co** (higher EM
activation energy) — the real advanced‑node trend. On the sample, the bus net (severity 1.0)
→ W, verified before/after to cut EM risk ~50%, gated AGREE.

### 4.4 It scales to real 100k+ designs
Three independent real designs, whole‑graph curvature infeasible at the top:

| Design | nodes / edges | per‑region analysis | whole‑graph |
|---|---|---|---|
| AES | 16,853 / 43,718 | 33s exact → 8.3s effres → **3.1s parallel** | infeasible |
| ibex_core | 29,522 / 67,990 | 12.6s → **5.1s parallel** | ~7 GB pinv |
| large01 / netcard | **276,249 / 538,359** | 158.9s → **73.1s parallel** (512 regions) | ~600 GB pinv |

Parallel output is **identical** to sequential (deterministic worker). At 276k nodes
partitioning is not an optimization — it is the only thing that makes the analysis exist.

### 4.5 The method that scales is the one that keeps the signal
Benchmarked on gcd: exact 981 ms (worst κ −0.396); **EffectiveResistance 263 ms, worst κ
−0.86 — preserves the bottleneck**; LowerRicci 10 ms but worst κ +0.02 — *loses* the
bottleneck. We chose effres for scale, not the fastest method. Picking the cheap method that
keeps the signal, not just the cheap one, is the whole discipline in miniature.

**Status:** 250 tests passing; the `measured` evidence tier is the one tier still empty on
real data (it needs a real STA/PDN report, which needs the toolchain).

---

## 5. How we move forward (the four follow‑ups, made concrete)

### 5.1 Light‑entry parallel launcher (so the agent CLI gets the speedup on Windows)
**Why:** ProcessPool uses *spawn* on Windows; each worker re‑imports the entry module. The
benchmark (`python -m domains.silicon.partition`) is light, so parallel works (×2.2–2.6). The
full agent CLI's `__main__` imports the heavy geometry/TensorFlow chain (~8s), which each
worker would re‑pay — erasing the gain.
**How:** add a minimal launcher module whose top level imports *only* `argparse`/`json` and
defers all heavy imports into the command body, and route the parallel `partition`/analysis
commands through it (or set the pool's `initializer`/`mp_context` so workers import only
`_region_worker`). Net effect: `--workers auto` becomes useful from the engineer‑facing CLI,
not just the benchmark. (Small, isolated; no algorithm change.)

### 5.2 Light up the `measured` tier (real STA / PDN ingestion)
**Why:** every claim today is at best `measured_proxy`. The top tier is reserved and empty
on real data — by design, but it's the credibility ceiling.
**How:** the parsers already exist (`sta.py` `report_checks` grammar with provenance hashing;
`ir_drop.py` ready for a PDN/IR report). The missing piece is *producing* a real report,
which needs the toolchain (OpenSTA + a liberty `.lib`; OpenROAD `analyze_power_grid` /
Voltus). Two paths: (a) bring up the toolchain (Docker/WSL — the earlier blocker was a
pending Windows reboot, now resolved) and run OpenSTA on one of our downloaded designs; or
(b) ingest a committed real STA report if one can be sourced. Once a real, design‑matched
report is attested, `claims_from_sta` / a PDN equivalent populate the `measured` tier and the
scoreboard can correlate structural triage against *timing* ground truth — the strongest
validation available.

### 5.3 HTML ledger dashboard (engineer‑facing view)
**Why:** engineers want to *see* the ledger and action portfolio, not read JSON.
**How:** GRID already has a self‑contained HTML/CSS dashboard generator
(`KOMPOSOS-GRID/domains/grid/waste_ledger.py` → `to_html`). Port `to_html`/`export_html` onto
the silicon `WasteLedger`: evidence‑tier chips, the ready/validate/review action‑portfolio
columns, sortable claim table, and small inline SVGs for the congestion corridors / Fiedler
seam / tile heatmap. Static file, no server, opens in a browser — fits the "runs on a
laptop, offline" constraint. (Mechanical port; mostly templating.)

### 5.4 Performance follow‑ups the large01 run exposed
- **Faster `Category` load** (25s for 276k objects via sqlite `bulk_add`): a batched/bulk
  insert path is the single biggest fixed‑cost win.
- **Coarser/chunked parallel tasks**: 512 tiny regions pay per‑task pickle/dispatch; grouping
  regions per worker would push past the current ×2.2.
- **large02 / multi‑million**: the next real wall; would test whether a second parallel level
  or streaming load is needed.

---

## 6. Pivots — methods and designs where this wins *now*

The triage philosophy fits several high‑value, current chip‑design problems. Each is a
plug‑in on the existing substrate, not a rewrite.

### 6.1 Chiplet / 3D‑IC partitioning (UCIe era) — strongest near‑term fit
The Fiedler‑seam machinery already proposes where to cut a monolith into chiplets. The
industry is moving hard to chiplets + UCIe; a fast, tool‑agnostic "where are the natural die
boundaries and what crosses them" screen is directly useful. **Pivot:** formalize the seam as
a `boundary_profunctor` between two sub‑categories, score the cut by inter‑region wire count
+ SPEF load (we already compute both), and emit UCIe‑interface candidates. Add a Z‑axis
(3D‑IC) by partitioning on a layer/coordinate dimension.

### 6.2 Advanced‑node electromigration & the Cu→Co/Ru transition
The `interconnect.py` EM‑vs‑resistance trade‑off is exactly the live materials decision at
3nm/2nm. **Pivot:** feed real per‑net current density (from a power report) instead of the
cap×fan‑out proxy to move EM claims from `measured_proxy` to `measured`, and use the CHEM
inverse designer ("Crystal Dreamer") to *propose novel barrier alloys* (Ru/Co doping
variants) for the hottest nets — the layout defect drives a materials search.

### 6.3 "AI proposes, KOMPOSOS disposes" — a guardrail for GNN/RL placers
GNN/RL placers (AlphaChip‑style) produce compact but sometimes physically unsound layouts.
**Pivot:** wrap a placer so each candidate placement is piped through our sheaf‑coherence +
curvature + material gates *before* the expensive EDA evaluation; a `HOLLOW`/`REJECT` verdict
with an interpretable reason becomes an immediate training/backtrack signal. This is the
highest‑leverage integration: we don't compete with the placer, we make it honest.

### 6.4 PFAS / process‑material compliance (regulatory pressure)
Fabs face fluoropolymer restrictions. The CHEM `pfas_bridge` + inverse designer can search
for non‑PFAS dielectrics/photoresists matching a target property window. **Pivot:** wire the
material‑proposal pattern (already built for interconnect EM) to dielectric `k`‑value / etch‑
resistance targets, gated by COG/ZFC so substitutions are traceable to published data before
anything reaches a mask set.

### 6.5 Thermal hotspot triage
The tile aggregation already yields per‑region switching‑capacitance demand. **Pivot:** add a
leakage/area term and a simple thermal‑diffusion smoothing over the tile grid to flag thermal
hotspot candidates (`measured_proxy` until a real thermal map is ingested), feeding the same
ledger.

### 6.6 Which designs to target right now
- **AI accelerators / HBM‑adjacent logic**: dense bus matrices and memory‑to‑core interfaces
  are exactly the negative‑curvature corridors we recover well.
- **Power devices (GaN/SiC)**: the material bridge already has the stacks; thermal/EM triage
  is the differentiator.
- **Chiplet platforms**: seam detection → UCIe boundaries.

---

## 7. Modularity — making it easy for engineers

The system is already plug‑in shaped; the goal is to make that explicit and ergonomic.

### 7.1 The three extension seams (today)
1. **`Bridge`** (`core/bridge.py`): implement `get_objects` / `get_morphisms` / `score_pair`
   to load *any* domain data into the shared `Category`. `NetlistBridge` and `MaterialBridge`
   are the worked examples. A new data source = one bridge subclass.
2. **Analysis module**: a function on a `Category` returning structured findings
   (`flow_geometry`, `tiles`, `ir_drop`, `coherence`). Add one; it composes with the rest.
3. **Agent‑CLI command**: a `cmd_*` that emits JSON with a `summary` + `provenance`
   (`agent_tools.py`). 17 commands exist; adding one is ~15 lines.

### 7.2 What "modular for engineer ease" should add next
- **A single stable façade** (`domains/silicon/api.py`): `analyze(def, spef=…, lef=…,
  sta=…) -> Report` returning a typed result with corridors, seam, tiles, ledger, verdicts —
  so an engineer never has to wire the bridges by hand.
- **A capability registry**: each analysis/bridge/material set self‑registers (name,
  inputs, evidence tier, CLI verb), so the CLI/dashboard/registry stay in sync and new
  plug‑ins appear automatically (mirrors `oracle.create_all_strategies`).
- **Config‑driven runs**: a small TOML/JSON describing inputs + which analyses + thresholds,
  so a run is reproducible and shareable without code.
- **The agent contract as the API**: the JSON‑with‑provenance CLI *is* the integration
  surface for an engineer's own coding agent; documenting it as a stable contract (like
  GRID's `AGENTS.md`) makes the system usable without reading the internals.

### 7.3 Packaging
Keep core analyses **numpy + stdlib** (they are). Heavy/optional producers — OpenLane,
OpenSTA, `mp‑api`, sentence‑transformers — stay out‑of‑band data producers, never imported by
the core. Ship `domains/silicon` as an installable package with the committed sample +
`samples/` fixtures so it runs end‑to‑end with zero downloads, and the real designs/LEF/SPEF
slot in via `data/` (gitignored).

---

## 8. Honest limitations (the boundary of the claims)

- **No physics is simulated.** Curvature, fan‑out, current‑demand, and material scores are
  proposals/proxies. SPICE/RedHawk/DFT/real STA remain the authorities; we screen for them.
- **`measured` is empty on real data** until a real STA/PDN report is ingested.
- **Curvature is a weak per‑net congestion ranker** on real designs (good for seams; use
  fan‑out for per‑net). We say so and rank accordingly.
- **Inter‑region bottlenecks** aren't seen inside partitions; they're recovered by the cheap
  global spectral pass — documented, not hidden.
- **Material data is bulk/literature‑grade**, suitable for screening, not foundry sign‑off.
- **Windows ProcessPool** speedup needs a light entry module (§5.1).

The discipline that makes these *features*, not embarrassments: each is stated, tiered, and
testable, so a downstream decision knows exactly how much to trust each number.

---

## 9. Appendix — module map and commands

| Module | Math / role |
|---|---|
| `netlist_bridge.py`, `lef.py`, `sta.py`, `verilog.py` | ingest DEF/SPEF/LEF/STA/Verilog → `Category` |
| `flow_geometry.py`, `geometry/ricci.py`, `fast_ricci.py`, `spectral.py` | Ricci corridors + Fiedler seams (exact/effres/auto) |
| `partition.py`, `_region_worker.py` | spatial/spectral bisection + parallel per‑region curvature |
| `tiles.py`, `categorical/kan_extensions.py` | left‑Kan gates→tiles aggregation |
| `coherence.py`, `topology/persistent_sheaves.py` | exact H⁰/H¹ cross‑artifact coherence |
| `net_operad.py` | coloured‑operad n‑ary nets |
| `material_bridge.py`, `materials_data.py`, `scoring.py` | 5 scorers + lattice veto + COG/HonestyGate verdict |
| `ir_drop.py`, `interconnect.py` | current‑demand proxy + EM→metal proposal (layout↔materials) |
| `waste_ledger.py`, `agent_tools.py` | tiered ledger + action portfolio + local‑agent CLI |
| `fix_loop.py`, `core/generator.py` | self‑learning: verified fixes become primitives |
| `scoreboard.py` | falsifiable validation vs SPEF (+ shuffle control) |

```powershell
python -m domains.silicon.scoreboard                 # validate triage vs SPEF
python -m domains.silicon.partition <design.def>     # scale benchmark (seq vs parallel)
python -m domains.silicon.fix_loop                   # self-learning remediation demo
python -m domains.silicon.agent_tools manifest       # the engineer/agent CLI surface
python -m pytest tests/ -q                           # 250 passing
```
</content>
