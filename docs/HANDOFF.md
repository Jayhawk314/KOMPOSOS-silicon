# KOMPOSOS-Silicon — Handoff (start here)

> Plain-English snapshot to resume this work in a fresh session.
> Repo branch `main` · latest at handoff: `741b4ec` (2026-06-21).
> Deeper docs, in reading order:
> - `docs/VALUE.md` — **what this is worth and why** (the goal: a useful, receipt-backed tool)
> - `docs/ROADMAP.md` — from "claimed" to "delivered + seen" (the value-and-visibility plan)
> - `docs/SILICON_POSTMOORE_PLAN.md` — the **active plan** (3 tracks + status, receipt-gated)
> - `docs/SILICON_FINDINGS.md` — what's true/false with receipts (reliability era)
> - `docs/SILICON_MATH_INVENTORY.md` — which math is REAL vs scaffold (read from the code)
> - `docs/SILICON_MATH_TOOLBOX.md` — problem→tool map (congestion vs coherence vs Yoneda)
> - `docs/SESSIONS.md` — full chronological log (newest on top)
> - `domains/silicon/sta_flows/` — reproducers + hashes for the real EDA runs

## 1. What this is, in one paragraph

A **verification-backed co-design layer for chips**: point it at a real layout and it finds
where the chip will physically stress, proposes grounded fixes, and **proves** them — with a
checkable receipt on every claim. The aim is a genuinely useful, receipt-backed tool that saves
a real engineer real effort on a real design — free, a favor, or a service, **not a company**
(see `docs/VALUE.md`). Two proven capability areas coexist: (A) the **mature-node reliability
layer** (IR-drop / EM hotspots, proven), and (B) the **post-Moore co-optimization +
pattern-fidelity/trust** frontier (interconnect delay, 3D thermal, multi-view + multi-patterning
coherence) — aimed at the Huawei-τ / TSMC-multipatterning / Intel-DSA reality.

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
| **Track 3B — double-patterning native conflicts** | real GDS shapes, SREF-flattened → real dense **M1 not 2-colorable, 7143 native conflicts localized**; conflict rule verified == OpenMPL's; BFS↔spectral agree (dp_conflict + gds) |
| **Track 3C — trust-gate the coherence verdict** | obstructions TRUSTED only on independent specificity-weighted corroboration + grounding; real orfs_gcd 3A 50/50 trusted/uncorroborated, 3B M1 1 trusted region; tier `structural_only` (coherence_trust) |

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
  - Step B SREF-flatten DONE: GDS reader resolves the SREF/AREF hierarchy, so cell-internal
    metal is included — real dense **M1: 7143 native conflicts localized**. Also fixed a latent
    honesty bug (spectral silently skipped huge components → false 0); now scalable + honest.
  - Step B OpenMPL cross-check, DEFINITION level DONE: read OpenMPL's conflict construction and
    confirmed our rule is identical (euclidean gap < coloring_distance); aligned comparator to
    its strict `<`. (Open: the NUMERIC binary run on identical inputs is build-gated:
    C++/Boost/Limbo, Docker only; OpenMPL ships no in-repo benchmarks, its cmdtest is the
    color_num=3 triple-patterning regime we don't subsume.)
  - Step C DONE: `coherence_trust.py` routes BOTH coherence verdicts (3A + 3B) through
    proposal→verification — TRUSTED only on independent, specificity-weighted corroboration +
    HonestyGate grounding; tier stays `structural_only`. Trust unit is the net (3A) vs the
    frustrated component (3B), per the genuine independent-localizer granularity. Foundry-
    measured EPE still gated. **Open:** the OpenMPL numeric run (build-gated, above).

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

## 7. The open question (which capability to sharpen next — a value call, not a market one)

The tech for three capabilities is built and tested: the **mature-node reliability layer**, the
**post-Moore co-optimization layer** (interconnect/thermal), and the **pattern-fidelity + trust
layer** (localized, corroborated obstruction receipts over black-box computational-litho /
DSA-defect / AI-EDA tools). The open question is *not* which to sell. It's which one most clearly
**saves a real engineer real effort on a real design** — and is therefore worth hardening and
putting in front of the right eyes. That's the test (`docs/VALUE.md`, `docs/ROADMAP.md`): value
is measured by effort saved, not by sellability. The current ROADMAP picks visibility (#6: aim it
at the applied-category-theory / verifiable-AI / open-EDA audiences) as the next move.

## 8. One-line status

A tested, honest chip co-design layer: mature-node IR/EM proven; interconnect-delay and 3D
thermal won on real data; the coherence engine wired to real silicon — localizing
double-patterning native conflicts on real GDS, and a **real cross-stage divergence** (synthesis
vs final netlist, attributing the flow's inserted clock/hold buffers) — with every boundary
documented, not hidden. Green (331 tests) and committed at `741b4ec`.
