# Silicon — the math toolbox, mapped to problems (which tool, when)

> Written 2026-06-20 to stop conflating two different jobs. Grounded in the actual
> repo files, not theory. Companion to `docs/SILICON_POSTMOORE_PLAN.md`.

## The one distinction that matters

There are **two different problem classes**, and they need different math. Conflating them
is what made the RapidChiplet torus look like a "geometry failure."

| Class | Question | Tool family |
|---|---|---|
| **Congestion / flow** | *Where does flow concentrate? Where's the bottleneck?* | **Geometry** (Ricci/Fiedler) |
| **Coherence** | *Do multiple representations AGREE, and can the gap be resolved/composed?* | **Sheaf → coherence engine → horns → HoTT → cubical** |
| *(Routing / queueing)* | *Which links does the routing POLICY load?* | *Not ours* — combinatorial/queueing theory |

## 1. Congestion (geometry) — VALIDATED for silicon

Metric/quantitative; assumes flow follows geodesics. Works when there is geometric
heterogeneity. Receipts:
- Rung-0 barbell: the bus is the most-negative-curvature link (bottleneck found).
- IR-drop / EM tile detection (Phase 1–2); 3D thermal cross-die coupling (Track 2).
- τ interconnect delay: curvature +0.30–0.35 (`tau_scoreboard.py`).

**Boundary (the RapidChiplet lesson):** Ricci curvature is a **bridge/cut detector** — it
flags low-redundancy links *between clusters*, not central high-throughput links. On a
**symmetric** topology (4×4 torus) every link is identical (curvature ≡ 0.25), so geometry
carries *zero* information and the apparent correlation is a ranking artifact. There, link
load is set by the **routing policy's tie-breaking** — a routing/queueing phenomenon, not a
geometric one. Curvature applies to chiplets only in its real regime: **clustered /
hierarchical interconnect** (a few die-to-die links bridging clusters — the UnifiedBus case).
The uniform-NoC-load angle is parked: forcing a tool there would break the discipline, like
forcing structure onto optimizer-flattened timing.

## 2. Coherence — the ladder (validated on CHEM, dormant for silicon)

Logical/structural consistency, *not* metric. This stack is **not untested theory** — it is a
benchmarked engine (drug-repurposing, AUROC ~0.98) carrying the project's honesty discipline
(leak control, hold-out). It is **dormant for silicon only because Track 3 has no real data
yet**, not because it doesn't work.

| Rung | File(s) | What it answers |
|---|---|---|
| Sheaf gate | `oracle/coherence.py`, `topology/persistent_sheaves.py`, `domains/silicon/coherence.py` | Do local views agree on overlaps? Detect contradictions; localize the obstruction (H¹). |
| Corroboration | `oracle/coherence_dial.py` | Is a claim trustworthy because *several independent* witnesses agree? (noisy-OR) |
| Specificity | `oracle/coherence_specificity.py` | …without a non-specific/hub witness vouching for everything? (IDF weighting) |
| Composition | `oracle/horns.py` (+`_retrodiction`,`_vs_composition`) | Can local fragments **compose** into a coherent whole? Unfilled inner horn = conflict / missing piece. |
| Equivalence | `hott/homotopy.py`, `hott/geometric_homotopy.py` | Is the realized thing *the same up to coherent deformation* as the intended thing? (`homotopy`/`geometric_homotopy` are real algorithms; `identity.py` is symbolic bookkeeping.) |
| Computation | `cubical/kan_ops.py`, `cubical/paths.py` | *Intended* to make path-equivalences computable (transport / Kan-fill) — but **the code is a scaffold**: faithful data model, computation **stubbed** (endpoints / linear interp / symbolic wrappers). Docstrings overclaim. See `docs/SILICON_MATH_INVENTORY.md`. |

> **Maturity correction (after reading the code, not docstrings):** the *ready* coherence
> engine is the **oracle cluster** (`horns*`, `coherence*`, `yoneda_strategy` — real,
> benchmarked, leak-controlled). The HoTT/cubical layer is a scaffold whose transport/Kan
> computation is not built. So for Track 3, reach for the oracle corroboration+specificity
> pattern first; HoTT/cubical only if real *transport along an equivalence* is needed (and
> then it must be implemented). Full per-file verdicts: `docs/SILICON_MATH_INVENTORY.md`.

Two unifications worth holding in mind:
- **Horn-filling = Kan-filling.** `oracle/horns.py` (simplicial/proposal) and
  `cubical/kan_ops.py` (computational) are two layers of one idea.
- **`hott/geometric_homotopy.py` bridges the two classes** (curvature-aware path equivalence),
  if a problem ever needs both metric and coherence structure.

**Discipline:** `oracle/coherence.py` is proposal-side (uses embeddings, invariant #2). The
whole coherence stack *proposes/filters*; the symbolic layer (COG + HonestyGate) still
*verifies*. Never let coherence stand in for a verdict.

## 3. Mapping the silicon coherence problems (Track 3) to the ladder

When real EPE/DSA placement-error / multi-mask data arrives, the tools are pre-assigned:

| Silicon problem | Tool |
|---|---|
| Multi-mask / multi-view *agree on overlaps?* (EPE) | sheaf gate + contradiction detection (`oracle/coherence.py`) |
| Feature trustworthy because *several independent* constraints agree? | corroboration (`coherence_dial.py`) |
| …without a global constraint vouching for everything? | specificity weighting (`coherence_specificity.py`) |
| Do the local pattern fragments **recompose** to the target layer? | horns / Kan-fill (`horns.py` / `cubical/kan_ops.py`) |
| Is the realized pattern ≃ the intended design? | path equivalence (`hott/homotopy.py`) |

## 4. The gate (unchanged)

Nothing in §2–§3 wires into silicon scoring until it passes a **real measured silicon test**,
exactly like geometry did for congestion. Track 3 is data-gated (foundry/research
placement-error data). This doc is the *map* so the right tool is obvious when the data lands —
not a license to bolt dormant engines in for show.
