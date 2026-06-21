# KOMPOSOS-Silicon — Handoff (start here)

> Plain-English snapshot to resume this work in a fresh session.
> Repo branch `main` · latest at handoff: `06e27e7` (2026-06-21).
> Deeper docs, in reading order:
> - `docs/SILICON_POSTMOORE_PLAN.md` — the **active plan** (3 tracks + status, receipt-gated)
> - `docs/SILICON_FINDINGS.md` — what's true/false with receipts (reliability era)
> - `docs/SILICON_MATH_INVENTORY.md` — which math is REAL vs scaffold (read from the code)
> - `docs/SILICON_MATH_TOOLBOX.md` — problem→tool map (congestion vs coherence vs Yoneda)
> - `docs/SESSIONS.md` — full chronological log (newest on top)
> - `domains/silicon/sta_flows/` — reproducers + hashes for the real EDA runs

## 1. What this is, in one paragraph

A **verification-backed co-design layer for chips**: point it at a real layout and it finds
where the chip will physically stress, proposes grounded fixes, and **proves** them — with a
checkable receipt on every claim. Two product framings now coexist: (A) the **mature-node
reliability layer** (IR-drop / EM hotspots, proven), and (B) the **post-Moore co-optimization
+ pattern-fidelity/trust** frontier (interconnect delay, 3D thermal, multi-view + multi-
patterning coherence) — aimed at the Huawei-τ / TSMC-multipatterning / Intel-DSA reality.

## 2. The discipline (the moat — do not break it)

- A capability counts only with a **measured/cited receipt** and a **shuffle/held-out control**.
  Proposal ≠ verification (scores/curvature/embeddings only propose; COG + HonestyGate verify).
- **Evidence tiers stay honest:** `measured` (real tool output) > `measured_proxy` (SPEF) >
  `validated_hypothesis` (cited physics + geometry) > `literature_value`. Never promote.
- **Dormant math wires in only when it passes a real measured chip test** — never for show.
- When pointed at code, **read the whole file**, not the docstring (see the math inventory).

## 3. What's proven — the receipts (all on real EDA output)

| Result | Receipt |
|---|---|
| Mature-node IR-drop from cheap structure | +0.5–0.6 Spearman, clean control (ir_scoreboard) |
| Measured EM current from structure | +0.64 (em_scoreboard) |
| **Track 1 — interconnect (τ) delay** | proxy fanout **+0.61**; **measured** net-delay **+0.645** (tau_scoreboard) |
| **Track 2 — 3D thermal cross-die coupling** | **8/8** Open3DBench designs; directional (sink-far die) (thermal3d_scoreboard) |
| **Track 3A — multi-view net coherence** | real orfs_gcd verilog/def/spef → **H0=1, H1=0**; obstruction-localization proven (fidelity_coherence) |
| **Track 3B — double-patterning native conflicts** | real GDS layer-13 shapes → **not 2-colorable, native conflicts localized**, BFS↔spectral agree (dp_conflict + gds) |

**Honest boundaries (don't over-claim):** cheap structure does NOT predict gate-level timing
slack (optimizer flattens it — that's STA's job); the IR/EM win is **mature-node only** (fails
& inverts at 7nm); the within-die "chiplet" proxy was weak (real win needed real 3D data);
NoC routing-load is routing theory, not ours; triple+ patterning is NP-hard coloring, not
cohomological (only double-patterning is a clean Z/2 H¹ fit).

## 4. Where each track stands (see SILICON_POSTMOORE_PLAN.md)

- **Track 1 (τ interconnect delay) — DONE**, both tiers.
- **Track 2 (3D thermal multi-die) — DONE** (Open3DBench). Open: per-die DEFs via their MoL
  flow would add placement geometry + 3D τ.
- **Track 3 (EPE/DSA pattern-fidelity coherence) — engine BUILT + wired:**
  - Step A DONE: H⁰/H¹ coherence engine wired to real silicon (verilog/def/spef).
  - Step B first cut DONE: double-patterning native-conflict localization on **real GDS metal
    shapes** (Z/2 obstruction, two methods agreeing).
  - **Open:** resolve SREF cell-internal metal (currently top-cell routing only); **OpenMPL**
    ground-truth cross-check (build it, run ISCAS/ISPD'19, confirm our localized native
    conflicts match its decomposer); then wire the verdict through the trust gate +
    corroboration/specificity (oracle cluster). Foundry-measured EPE stays gated.

## 5. How to run the key things

```powershell
python -m domains.silicon.tau_scoreboard         # Track 1: structure vs interconnect delay
python -m domains.silicon.thermal3d_scoreboard   # Track 2: 3D cross-die thermal coupling
python -m domains.silicon.fidelity_coherence     # Track 3A: 3-view net coherence (H0/H1)
python -m domains.silicon.dp_conflict            # Track 3B: double-patterning native conflicts (real GDS)
python -m pytest tests/ -q                       # full suite (run it first to confirm green)
```

Real-data tests **skip** when the gitignored artifacts are absent. Key local data (all under
`domains/silicon/data/`, gitignored, regenerable): `sta_45gcd/` (detailed SPEF + net-delay),
`orfs_gcd/results/base/` (self-minted 6_final.v/.def/.spef/.gds — the Track-3 source),
`orfs_aes|ibex/` + `ir_*` (IR/thermal), `open3dbench/` (3D thermal), `rapidchiplet/` (chiplet
graphs). **Docker works** (server 29.5.3; `openroad/orfs` + `openroad/opensta` images cached)
— the old "blocked" notes are stale. STA/IR/thermal reproducers + hashes in `sta_flows/`.

## 6. The math, honestly (so you don't re-hand-wave it)

Read the code, not docstrings. From `docs/SILICON_MATH_INVENTORY.md`:
- **REAL & ready:** the oracle coherence/horns/yoneda cluster (corroboration + specificity +
  contradiction, benchmarked AUROC ~0.98); `topology/persistent_sheaves.py` exact H⁰/H¹ +
  `h1_support`; `domains/silicon/coherence.py` + `verilog.py`; geometry (Ricci/Fiedler) for
  congestion.
- **Scaffold/stub:** `hott/` (homotopy.py/geometric_homotopy.py real; J/transport stubbed) and
  `cubical/` (data model faithful, Kan-fill/transport NOT computed — docstrings overclaim).
- The coherence pattern (object = Yoneda profile; hypothesis = unfilled inner horn; coherence =
  independent views agree, specificity-weighted, contradictions filtered) is the trust layer
  for EPE/DSA. The rest of the ~60k-line math stack is **not** required by the product.

## 7. The strategic question (still open, it's a market call not a coding one)

Is the product the **mature-node reliability layer**, the **post-Moore co-optimization layer**
(interconnect/thermal), or the **pattern-fidelity + trust layer** (gate black-box
computational-litho / DSA-defect / AI-EDA tools behind a localized, corroborated obstruction
receipt)? The tech for all three is built and tested. That choice drives what to harden next.

## 8. One-line status

A tested, honest chip co-design layer: mature-node IR/EM proven; interconnect-delay and 3D
thermal won on real data; the coherence engine wired to real silicon and localizing
double-patterning native conflicts on real GDS — with every boundary documented, not hidden.
Green and committed at `06e27e7`.
