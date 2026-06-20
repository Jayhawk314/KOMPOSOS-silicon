# Silicon co-design — honest findings (2026-06-20)

> Plain-English reckoning, written after we stopped to reassess. This records what we
> *proved*, what we *disproved*, and what it means — including the negative results,
> because a negative result you can trust is worth more than a hopeful guess you can't.
> Companion docs: `SILICON_PLAN.md` (plan), `SILICON_STATUS.md` (status), `SESSIONS.md`
> (log), `domains/silicon/sta_flows/` (reproducers + hashes).

## The question we set out to answer

A chip layout has a few **timing-critical** signals — the ones on the slowest paths that
limit how fast the chip can run. Finding them normally means running a heavy, accurate
timing tool (STA). Our bet: maybe cheap *structural* clues from the wiring graph alone
(how much a signal fans out, congestion/curvature of the graph, how big the driving gate
is) can **predict** which signals are timing-critical, without running the expensive tool.

If that worked, it would be fast triage: "look here first."

## How we tested it (the method — and why it's trustworthy)

We did **not** use toy data or simulated physics. We:

1. Ran **real industrial tools** — OpenSTA 2.6.2 and OpenROAD 26Q2 (Yosys 0.64 for synth).
2. **Minted real chips ourselves** end-to-end (RTL → synthesis → place → route) for
   `gcd`, `aes`, `ibex` on the Nangate45 cell library, plus a downloaded `45_gcd`.
3. Ran **real timing** on each and compared the cheap structural guesses against it.
4. Kept **receipts**: every timing number is hashed back to the exact netlist, library,
   and constraints it came from (`domains/silicon/sta_flows/`). Fixtures can never be
   passed off as evidence.

Scoring: Spearman rank correlation between each structural guess and the real per-net
timing-criticality, plus `precision@10` (do the top-10 guesses hit the actual top-10
critical nets?), plus a shuffled-control that must collapse to ~0. Pass bar: correlation
≥ +0.30 with a clean control.

## What we found

| Test | design | source | optimized? | nets | best predictor | corr. | top-10 hit | verdict |
|---|---|---|---|---:|---|---:|---:|---|
| 1 | `45_gcd` | downloaded | loosely | 308 | driver_area | **+0.34** | 0.00 | PASS (barely) |
| 2 | `gcd` | self-minted | fully | 621 | sink_area | +0.06 | 0.00 | FAIL |
| 3 | `aes` | self-minted | fully | 14,419 | driver_area | +0.15 | 0.00 | FAIL |
| 4 | `ibex` | self-minted | fully | 15,298 | sink_area | +0.24 | 0.00 | FAIL |
| 5 | `gcd` early (pre-opt) | self-minted | **no** | 572 | driver_area | +0.22 | 0.00 | FAIL |
| 6 | `gcd` early, tighter clk | self-minted | **no** | 572 | driver_area | +0.19 | 0.00 | FAIL |

Three facts stand out:

- **The only pass is the one we didn't build and didn't fully optimize.** It is not
  reproducible on any design we controlled end-to-end.
- **`precision@10` is 0.00 in every single test.** Even when there is a weak positive
  trend, the structural guess **never** correctly identifies the actual worst nets.
- **The curvature math — central to this whole system's "structure" thesis — is the
  *weakest* predictor**, hovering at zero or *negative* for timing in every test. The
  only mildly-positive signals are cell-size ones (`driver_area`/`sink_area`), and even
  those top out around +0.2–0.3 and never pinpoint.

## Why it fails (this is the important part, and it's fundamental)

When a professional flow finishes a chip, its **job** is to make all the critical paths
**equally tight** — it speeds up whatever was slowest until everything is balanced on a
knife's edge. We measured this directly: on the self-minted `gcd`, the violating slacks
clustered to a standard deviation of **0.010 ns** — almost no spread. Once everything is
equally critical, **there is no spike left for a cheap guess to find.** The optimizer
erases the very signal we were trying to detect.

The early-stage experiment (tests 5–6) checked the natural escape hatch: maybe structure
predicts trouble *before* the optimizer flattens it. It does not — even on an
un-optimized placement, the guess fails and never pinpoints. The escape hatch is closed.

## Honest conclusions

1. **As a product, "cheap structural timing predictor" is a dead end.** Not tunable —
   fundamental. The accurate tools already exist and run in minutes on small blocks;
   a fuzzy guess that never pinpoints the worst nets has no buyer.
2. **The project's "structure substitutes for scale" thesis took a real hit** — for
   *this* target (timing). The structural/curvature signals were the weakest of all.
3. **The verification engine works, and that is the real asset.** The whole system is
   built so a guess can never pose as a verified fact — it must produce a real receipt.
   Today that engine **caught our own headline idea over-claiming** and forced the truth
   out in an afternoon. Most "AI for chips" work would have shown only test 1 and called
   it a win.
4. **The test harness is real and fast.** We can mint real chips and check ideas against
   real tools cheaply. That capability is built and reusable.

## Where this leaves the value question

The unmet industry need here is **not** a predictor — it is *trust*. The industry is
racing to put black-box AI into chip design and is rightly scared of a wrong call that
costs millions. The one thing we have that maps to a real, unmet need is the discipline
that just proved itself: **no AI/heuristic suggestion is trusted until it earns a real
tool's receipt.** Whether that is a *product* is a market question (who would pay, in what
workflow) — not a coding question. It will not be answered by writing more code.

**Recommendation:** set the predictor down. Before building further, decide whether the
"trustworthy verification of AI chip decisions" framing has a real user. If we want to
keep the structural work alive, the honest pivot is to aim it at a target where cheap
structure actually wins (we saw in passing that fanout predicts wiring *capacitance*
well) rather than timing — but only after confirming someone needs it.

## Reproduce / audit

Everything is receipted in `domains/silicon/sta_flows/` (flows, constraints, result
tables, sha256 hashes). Real artifacts (DEF/SPEF/reports) are gitignored under
`domains/silicon/data/` but regenerate exactly from the committed flows.
