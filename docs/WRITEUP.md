# I built a chip-analysis tool — let me start with what it gets wrong

Most "AI for X" demos lead with a win. I want to lead with two failures, because they're the
reason you should trust the win that comes after.

I've been building a verification-first analysis layer for chip design. The idea is to take the
files a chip-design flow already produces — the netlist, the placement, the parasitics — and run
*cheap* math over them to predict what the slow, expensive sign-off tools would say, so an
engineer knows where to look before paying for a multi-hour run. A triage layer.

The natural way to oversell this would be to wave around category theory and sheaf cohomology
(both of which are in here) and imply they're doing the heavy lifting. They're not, mostly. So
let me be precise about what failed.

## Two things I was wrong about

**Curvature isn't a reliable per-net predictor.** I expected Ollivier-Ricci curvature — a
genuinely beautiful piece of math that measures how "bridge-like" an edge is — to be the hero
that ranks which nets get heavy. It isn't reliable: on one real design it's strong (ρ +0.64 on
gcd), on another it's weak (+0.16 on 45_gcd). It's *design-dependent*, which means I can't trust
it as the triage predictor. What holds up consistently across designs is boring old fan-out. So
I demoted curvature to the job it's actually dependable at — *seam* detection, finding where to
split a chip into chiplets — and stopped pretending it was the per-net ranker.

**Gate-level timing slack isn't structurally predictable.** I wanted to predict timing slack
from cheap structure. It doesn't work, and the reason is interesting: the place-and-route
optimizer *equalizes* slack on purpose, so by the time you have a routed design, the structural
signal has been deliberately flattened out. The optimizer erased exactly the thing I was trying
to read.

Both of these came out of a falsifiable scoreboard with a shuffle-negative control that has to
collapse to ~zero. I could have buried them. I think publishing them is the single strongest
evidence that the *positive* results are real — because they came from the same harness.

## The bet: structure substitutes for scale

The whole system is built on one wager: instead of one large trained model that gives you a
confident answer with no way to check it, compose **small engines where every kept claim is
built, executed, verified, grounded, and judged** — and where *"I can't justify that"* is a
first-class verdict, not a silent guess.

That's the opposite design from the mainstream. A neural placer hands you a layout and cannot
tell you which parts are unjustified. Here, "unjustified" is an output you can act on.

## The result that survived

After throwing out timing and per-net curvature, here's what held up — and I checked it against
the hardest possible target, the real tool's *own* answer, not a proxy:

I ran real OpenROAD/OpenSTA on routed designs, took the tool's own per-net interconnect delay,
and asked whether cheap structure predicts it. It does:

- **orfs_gcd: Spearman ρ +0.845** (wirelength), shuffle control −0.05, 545 nets.
- **45_gcd: ρ +0.65** (fan-out), shuffle control −0.05.

This is at the `measured` evidence tier — the report is attested as real tool output with a
hashed netlist/Liberty/constraints receipt, so a fixture can run the code path but can never
pass it. Cheap structure, computed in seconds, predicts the authoritative number the slow tool
takes minutes to produce. That's a real triage signal.

## What "verification-first" actually buys you

Two more pieces, framed honestly — not as features, but as *checks*:

- **Cross-tool coherence.** Synthesis, layout, and extraction are three independent views of one
  chip. I treat them as sections of a sheaf and compute the exact obstruction to gluing them
  (H⁰/H¹ cohomology), which *localizes the nets where the tools disagree*. On a clean design it
  correctly reports "no obstruction" — which is the honest answer, not a manufactured finding.
- **A trust gate that won't cry wolf.** A flagged problem is only "trusted" if multiple
  independent views corroborate it, weighted by an IDF specificity term so that a global view —
  one that flags *everything* — can't vouch for anything. On real data it splits flagged items
  cleanly into corroborated-and-trusted vs single-view-and-held-back.

These are the parts I think matter beyond chips. The mainstream AI problem right now is
trustworthy inference — getting a confident model to tell you honestly when it's guessing. A
verification layer that grounds, corroborates, and abstains is the same shape as that problem.
The chip work is one concrete, checkable instance of it.

## Honest boundaries

No physics is simulated — these are cheap proposals and proxies; SPICE, RedHawk, and real STA
remain the authorities, and this screens *for* them. The `measured` tier is lit for interconnect
delay but not yet for power/IR. And some of the deeper math in the repo (homotopy transport,
cubical Kan-filling) is scaffold whose computation I haven't built — it is *not* load-bearing for
anything above, and I'd rather say so than imply otherwise.

## Look at it

It runs on a laptop, offline. Thirty seconds, no downloads:

```bash
python -m domains.silicon.api domains/silicon/samples/tiny_core.def \
    --spef domains/silicon/samples/tiny_core.spef
```

It'll point at the one net crossing the natural chiplet seam and rank the nets most likely to be
physically heavy — each tagged with an evidence tier. The value writeup with every claim tied to
a run is in `docs/VALUE.md`; the code is `domains/silicon/`.

If you work on verifiable/neurosymbolic AI, applied category theory, or open EDA, I'd genuinely
like to hear where you think this is wrong. That's the whole point of building it this way.
