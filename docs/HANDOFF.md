# KOMPOSOS-Silicon — Handoff (start here)

> Plain-English snapshot to resume this work (or hand it to someone else).
> Repo: https://github.com/Jayhawk314/KOMPOSOS-silicon · branch `main` · latest at handoff: `696d394`.
> Deeper docs: `SILICON_FINDINGS.md` (what's true/false, with receipts), `SILICON_PLAN.md`
> (the plan), `SESSIONS.md` (full chronological log), `domains/silicon/sta_flows/` (reproducers + hashes).

## 1. What this is, in one paragraph

A **reliability co-design layer for chips**: point it at a real layout and it finds where the
chip will physically stress (power/IR-drop, electromigration), proposes a materials/geometry
fix grounded in *cited* data, and **proves** the fix (gain vs cost) — with a checkable receipt
on every claim, and a trust gate that lets you use black-box AI tools without trusting them
blindly. Built on real industrial tools (OpenSTA, OpenROAD/Yosys) and tested against real
measured output, not simulations.

## 2. The honest bottom line (read this first)

- **What works (measured):** cheap structural analysis predicts where a chip browns out
  (real IR-drop, **+0.5–0.6**) and where the real electromigration current flows (**+0.64**),
  validated on two real 45nm designs with clean controls.
- **The hard boundary:** this holds at **mature nodes only** (~28–130nm). At **7nm it fails
  and even inverts** — there IR-drop is dominated by the resistive power grid, not local
  current. That's most chips by volume (automotive/IoT/analog/power/MCU), stated honestly
  rather than over-claimed.
- **What does NOT work:** predicting **timing** from cheap structure (falsified — the
  optimizer flattens slack). We don't compete on timing; that's what STA is for.
- **Learning helps modestly:** a learned model beats the cheap baseline on held-out data
  (+0.57 vs +0.48, +0.66 vs +0.60), and the trust gate blocks models that don't generalize.
- **The differentiator:** incumbents *compute* IR/EM; none connect that stress to a grounded,
  *proven* materials fix with a receipt per step — and none gate black-box AI behind it.

## 3. What's built (the pipeline)

| Module (`domains/silicon/`) | Role |
|---|---|
| `ir_scoreboard.py` | the core measured win: does structure predict real IR-drop? (validation) |
| `em_scoreboard.py` | same, vs real measured EM current (+0.64) |
| `hotspot.py` | the detector: rank stress tiles + at-risk nets from layout alone, no power sim |
| `interconnect.py` | propose a metal swap (Cu→W/Ru/Co) on the EM-vs-resistance tradeoff |
| `materials_grounding.py` | cross-validate metal properties vs CITED data; Jmax + melting-point grounding |
| `codesign_loop.py` | find→fix→**prove**: EM gain (Black's eq) vs resistance cost; keep only if it nets out |
| `reliability.py` | the product: one report (WHERE + WHAT + WHY/evidence-ladder) |
| `trust_layer.py` | gate any external proposer: keep if grounded, BLOCK if fabricated |
| `ml_hotspot.py` | a real learned predictor, trust-gated on held-out data (beats the cheap baseline) |

Materials data was lifted/grounded from the sibling repo
`C:\Users\JAMES\github\KOMPOSOS-IV-CHEM` (`metal_bridge/material_properties.py`, cited ASM/Smithells).

## 4. How to run it

```bash
# the product — one report on a real layout:
python -m domains.silicon.agent_tools \
    --def <design>.def --spef <design>.spef --lef Nangate45.lef reliability

# the core validations (need the gitignored real artifacts; regenerate via sta_flows):
python -m domains.silicon.ir_scoreboard      # structure vs real IR-drop
python -m domains.silicon.em_scoreboard      # structure vs real EM current
python -m domains.silicon.ml_hotspot         # learned model vs baseline, trust-gated
python -m domains.silicon.codesign_loop      # find->fix->prove portfolio
python -m domains.silicon.trust_layer        # black-box proposer gating demo

python -m pytest tests/ -q                   # full suite (green at handoff)
```

To regenerate real data (Docker + OpenROAD, see `sta_flows/README.md`):
mint a layout with ORFS (`make DESIGN_CONFIG=designs/nangate45/<d>/config.mk`), then run
`analyze_power_grid` for the IR/EM `.rpt`. Real artifacts live under `domains/silicon/data/`
(gitignored; reproducible from the committed flows).

## 5. Important context for whoever resumes

- **The system is much bigger than the product uses.** The reliability product imports local
  silicon modules plus the lightweight core bridge/category/types/honesty gate path; the
  boundary is guarded by `tests/test_silicon_product_boundary.py`. ~50k lines of math
  (oracle/geometry/zfc/categorical/operadum/PRONOIA/cog/...) are **dormant** relative to it.
  The proven value is the *discipline*
  (receipts/grounding) + the *materials↔layout bridge*, NOT the exotic math. Do not bolt the
  dormant engines in for show — only wire one in if it passes a real measured test like
  everything else. That's the project's own honesty rule.
- **Evidence tiers are sacred:** `measured` (real tool output) > `measured_proxy` (SPEF) >
  `validated_hypothesis` (cited physics + geometry) > `literature_value` (cited bulk props).
  Never promote a tier dishonestly.
- **"Meaningful" = built on a validated step AND checkable against real data.** Don't stack an
  unvalidated step on a broken one (why the 7nm swap test was moot — the detector fails there).

## 6. What's open (honest)

- **Edge #1 (not done, low value):** a sub-7nm design would exercise the metal-swap branch —
  but the detector fails at 7nm, so it isn't grounded there. Skip unless you want completeness.
- **Firm up the 7nm boundary:** the node-failure was one design on the default ASAP7 power
  grid; a few more designs/PDN configs would separate "the node" from "this grid."
- **Strategic question (the real one):** is the product the *mature-node reliability layer*,
  or the *trust layer* (gate AI in EDA), or both? That's a market/customer question now, not a
  coding one — the tech for both is built and tested.

## 7. One-line status

A tested, honest, **mature-node** reliability co-design layer — proven detection (IR +0.5–0.6,
EM +0.64), grounded fixes, a closed find→fix→prove loop, and a working trust gate over learned
models — with its real boundary (fails at 7nm) documented rather than hidden. Green and pushed.
