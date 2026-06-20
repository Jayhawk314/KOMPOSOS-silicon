# Silicon co-design — what cheap structure can and can't predict (2026-06-20)

> Honest, plain-English findings on real silicon, with receipts. The headline is not
> "it failed" — it's **we found the line**: cheap structural analysis predicts the
> physical quantities that optimization does *not* flatten (current / IR-drop / load),
> and fails on the ones it *does* (timing). That line is the product.
> Companion docs: `SILICON_PLAN.md`, `SILICON_STATUS.md`, `SESSIONS.md`,
> reproducers + hashes in `domains/silicon/sta_flows/` and `ir_scoreboard.py`.

## The question

A chip has physical trouble spots — slow timing paths, places that draw too much current
and brown out (IR-drop), wires that will wear out (electromigration). Finding them
normally needs heavy, accurate tools. Our bet: cheap **structural** clues from the wiring
graph (fanout, congestion/curvature, cell density, load) can predict *where* the trouble
is — fast, early, and at scale — as long as every claim still earns a real receipt.

The real question turned out to be sharper: **which** trouble does structure predict, and
which does it not — and why.

## Method (and why it's trustworthy)

Real tools only: OpenSTA 2.6.2, OpenROAD 26Q2, Yosys 0.64. We **minted real chips**
ourselves end-to-end (`gcd`, `aes`, `ibex` on Nangate45) and tested cheap structural
guesses against **real measured tool output**, every number hashed back to the exact
design files it came from. Scoring: Spearman rank correlation + a shuffled control that
must collapse to ~0. Pass bar: ≥ +0.30 with a clean control.

## Result 1 — Timing criticality: structure FAILS

Can structure guess which nets are on the critical timing paths? **No.**

| design | source | optimized? | best structural ρ vs timing | verdict |
|---|---|---|---:|---|
| `45_gcd` | downloaded | loosely | +0.34 | pass (barely) |
| `gcd` | self-minted | fully | +0.06 | FAIL |
| `aes` | self-minted | fully | +0.15 | FAIL |
| `ibex` | self-minted | fully | +0.24 | FAIL |
| `gcd` early (pre-optimization) | self-minted | no | +0.19–0.22 | FAIL |

Only the un-optimized downloaded design passed; everything we built and optimized failed,
and the guess never pinpointed the worst nets. **Why:** a timing-driven flow's *job* is to
make all critical paths equally tight — it balances slack until nothing stands out
(measured: violating-slack spread of 0.010 ns on self-minted `gcd`). Optimization erases
the very signal. Rewinding to before optimization didn't rescue it either.

## Result 2 — IR-drop (where the chip browns out): structure SUCCEEDS ✅

Can structure predict where the chip actually has the worst supply voltage drop? **Yes —
decisively.** Ground truth: OpenROAD's real power-grid analysis (`analyze_power_grid`),
per-instance voltage, binned into a 20×20 tile map. (`domains/silicon/ir_scoreboard.py`.)

| structural signal | aes (8.3% worst drop) | ibex (0.65% worst drop) | needs extraction? |
|---|---:|---:|---|
| **fanout** | **+0.597** | +0.443 | no — free |
| load (SPEF cap) | +0.586 | **+0.478** | yes |
| cell density | +0.558 | +0.385 | no — free |
| cell area | −0.416 | −0.168 | no |
| shuffled control | ~0 | ~0 | — |

Both chips **pass** (bar +0.30, controls clean). The *free* signals — fanout and cell
density, no parasitic extraction at all — predict real IR-drop hotspots at +0.4 to +0.6.
(Nuance: the overall ranking is strong, but exact top-10 tile pinpointing is still
imperfect — it reliably ranks risk across the die, it doesn't always nail the single
worst tile.)

## The line we found (the actual insight)

Structure predicts the physical quantities optimization **does not flatten**, and fails on
the ones it **does**:

- **Current / IR-drop / load** → structure *wins* (+0.4–0.6). A busy, high-fanout, dense
  region genuinely draws more current; the optimizer balances *timing*, not *current*, so
  the spatial signal survives. (Earlier we also saw fanout predict SPEF capacitance at
  +0.57, and tile-level load at ~0.99 — same family.)
- **Timing slack** → structure *loses*. The optimizer's whole purpose is to equalize it.

This is a clean, defensible, falsifiable boundary — and it points straight at a product:
**structure is a fast, cheap detector for physical-stress / reliability hotspots
(power, current, electromigration), not a timing tool.**

## What this means for direction

1. **There is a real, working capability here** — cheap, extraction-free prediction of
   IR-drop/current hotspots, validated on real designs against real tool output. This is
   the "find the problems" half of reliability co-design.
2. **It plays to our unique strengths.** The next step is the part nobody else does:
   connect a structural current/EM hotspot to a *grounded materials fix* (metal/barrier
   choice), and prove the fix with a real receipt — the materials × layout co-design loop.
3. **The verification engine works and earned its keep.** It killed the timing idea
   honestly *and* certified the IR-drop win against measured ground truth. Same discipline,
   both outcomes — that's the trust layer the AI-EDA wave needs.

## Where the value is

Not a better timing tool (incumbents own that). The wedge is the **reliability co-design
layer**: find where silicon will physically degrade (IR-drop/EM/thermal) with cheap
structure, fix it with grounded materials science, and prove every fix — on an engine that
never lets a guess pose as a verified fact. Result 2 is the first proven brick of it.

## Reproduce / audit

- Timing: `domains/silicon/sta_flows/` (flows, SDCs, hashes; OpenSTA + OpenROAD).
- IR-drop: `domains/silicon/ir_scoreboard.py` + `analyze_power_grid` flow; real artifacts
  gitignored under `domains/silicon/data/ir_*/` but regenerate from the committed flows.
- Tests: `tests/test_silicon_ir_scoreboard.py` (asserts structure beats the control on
  real `aes` when artifacts are present).
