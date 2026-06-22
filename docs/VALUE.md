# What this is, and why it's worth a look

A **verification-first reasoning layer for chip design.** You point it at the files a
chip-design flow already produces, and it tells you where the design will physically stress,
where independent tools disagree with each other, and which of those findings are actually
trustworthy — **and every answer carries a receipt.** Where it can't justify a claim, it says
so. "Unjustified" is a first-class verdict, not a silent guess.

That is the whole bet: **structure substitutes for scale.** Instead of one large trained model
that gives confident answers with no way to check them, this is a set of small composable
engines where every kept claim is *built, executed, verified, grounded, and judged.* It runs on
a laptop, offline, on real public chip data.

Everything below is a result that **runs in this repository today** — the numbers are from runs,
not aspirations. Where something is a proxy, a boundary, or unbuilt, it says so in the same
breath.

---

## What it actually does (each backed by a run)

### 1. A cheap screen that predicts the expensive answer — validated against the *authoritative* number
Sign-off tools (extraction, timing, IR) are slow and run late. This computes cheap structural
signals — fan-out, connectivity, curvature — in seconds and **predicts what the slow tool would
say.** And it's validated not against a proxy, but against the real tool's own output:

> Run real OpenROAD/OpenSTA on a routed design, take the tool's **own per-net interconnect
> delay**, and ask whether cheap structure predicts it. It does, on two independent real
> designs: **orfs_gcd ρ +0.868, 45_gcd fanout ρ +0.65**, with **prec@10 = 0.90 on both** (the
> cheap total-wirelength rank finds 9 of the 10 worst nets), shuffle controls ~0. This is
> the `measured` evidence tier — the report is attested `tool` with a hashed netlist/Liberty/SDC
> receipt, so a fixture can exercise the path but never pass it.
> (`python -m domains.silicon.tau_scoreboard`; reproducer in `sta_flows/`)

Honest part: it *screens for* the expensive tool, it doesn't replace it. The value is doing the
cheap thing first and being right about where to look — now confirmed against the tool's own
authoritative answer, not just an extracted proxy.

### 2. It finds where independent tools disagree about the same chip — and localizes it
Synthesis, place-and-route, and extraction are three independent views of one design. They
*should* describe the same connectivity. This treats them as sections of a sheaf and computes
the exact obstruction to gluing them (H⁰/H¹ cohomology), **pinpointing the nets where the views
diverge.**

> On a clean design, three tool-views → **H⁰=1, H¹=0 (globally coherent)**, 621/621 common nets
> agree exactly (all three pairwise views match 1.000) — the honest "all clear." And on a *real*
> divergence — the **synthesis netlist vs the final routed netlist** (two real tool outputs the
> flow's own equivalence check certifies as logically equivalent, but structurally different) — it
> localizes precisely what changed:
> **509/592 nets preserved with identical connectivity (86%); the 137 divergent nets pinpoint the
> cells the flow inserted — `CLKBUF_X3` clock-tree buffers and `BUF_X1/X2/X4` hold/fanout
> buffers.** (`python -m domains.silicon.fidelity_coherence`)

This is the principled version of "the layout tool and the synthesis tool disagree" — with the
disagreement *located* and attributed, not just suspected. (Honest scope: this localizes real
*structural change* between equivalent stages; it is a what-changed check, not a bug-finder.)

### 3. It won't cry wolf — a finding is "trusted" only if independent views corroborate it
A flagged problem is just a *proposal* until it's verified. The trust gate accepts a finding
only when **multiple independent views agree on it**, weighted so that a non-specific/global
view (one that flags everything) can't vouch for anything — then it grounds the rationale in
committed evidence.

> On real net divergences: of 100 flagged nets, **50 are TRUSTED** (corroborated by two
> independent tool-pair comparisons) and **50 are held back as UNCORROBORATED** (flagged by a
> single view — likely one tool's naming quirk, not a real fault). Two views that each flag
> *everything* still can't push a finding through. (`python -m domains.silicon.coherence_trust`)

This is the part most "AI for X" tools don't have: a built-in reason to *distrust* its own
output, and the discipline to act on it.

### 4. It localizes real manufacturability conflicts, by the same rule a real tool uses
On the densest metal of a real layout, it finds the spots that can't be cleanly split into two
masks (the unavoidable double-patterning conflicts) — verified **two independent ways that must
agree** (combinatorial 2-coloring and a spectral check).

> Real flattened M1: **not 2-colorable, 7143 native conflicts localized**, both methods agree.
> The conflict rule was checked against a real open-source decomposer (OpenMPL) and is
> identical. (`python -m domains.silicon.dp_conflict`)

### 5. Materials verdicts that behave like physics, gated for honesty
Heterostructure interfaces are scored on five cited physics axes with a hard lattice veto, and a
recommendation is kept only if it passes a contradiction check *and* its rationale grounds in
the committed property facts.

> GaN/AlGaN (0.6% mismatch) → **AGREE, persisted**. GaN-on-GaAs (56% mismatch) → **REJECT** via
> the lattice veto. A recommendation that cited a net name instead of real property facts came
> back **HOLLOW** until re-grounded. (`python -m domains.silicon.material_bridge`)

---

## Why this is different from the mainstream

A GNN or an LLM hands you a confident answer and **cannot tell you which parts are unjustified.**
This is the opposite design:

- **Proposal vs. verification is sacred.** Scores, geometry, and embeddings only *propose*. A
  symbolic layer (composition check + a grounding gate) *verifies*. A proposal never becomes a
  kept claim on its own.
- **Every claim is tiered honestly:** `structural_only` (geometry alone) < `validated_hypothesis`
  (cited physics) < `measured_proxy` (tool-extracted) < `measured` (authoritative tool output).
  A proxy is never dressed up as a measurement.
- **It reports its own failures.** The scoreboard *disproved* two of its own hypotheses with
  controls — curvature is a weak per-net congestion predictor, and gate-level timing slack is
  *not* structurally predictable (the optimizer flattens it). Those negative results are kept,
  not hidden. That is the strongest evidence that the positive results are real.

The same engines (coherence, corroboration, composition) are domain-agnostic — they were lifted
from a prior knowledge-inference system and re-pointed at silicon. The chip vertical is one
application of a general "verified inference with a receipt" substrate.

---

## Honest boundaries (so the claims are trustworthy)

- **No physics is simulated.** Curvature, fan-out, and current-demand are proposals/proxies;
  SPICE, RedHawk, and real STA remain the authorities. This screens *for* them.
- **The `measured` evidence tier is now lit for interconnect delay** (real OpenROAD STA, two
  designs, attested + hashed) — but **IR-drop / power and gate-level timing are still proxy/
  structural** until their real reports are ingested too. One quantity is measured-validated; the
  rest of the ladder is honestly still below it.
- **The cross-tool coherence engine now localizes a real divergence (synthesis vs final), not
  just "all clear."** It attributes the change to the flow's inserted buffers — a genuine
  what-changed check on real tool output. Honest scope: that is structural-change localization
  between *logically equivalent* stages, not bug-finding; catching a true cross-tool *fault*
  still awaits a design that actually contains one.
- **Some of the deeper math is scaffold** (homotopy transport, cubical Kan-filling are data
  models with computation stubbed) and is honestly not load-bearing for the results above.

---

## How to see it in 60 seconds

```powershell
python -m domains.silicon.scoreboard          # cheap structure predicts real extraction (PASS + control)
python -m domains.silicon.fidelity_coherence  # three tool-views of a chip: do they glue? where don't they?
python -m domains.silicon.coherence_trust      # which findings are independently corroborated vs single-view
python -m domains.silicon.material_bridge      # materials verdicts: AGREE / REJECT / HOLLOW, gated
python -m pytest tests/ -q                      # the whole thing, green
```

The one-line version: **a chip-analysis layer that screens for the expensive tools, checks
whether your tools agree with each other, refuses to trust a finding it can't corroborate, and
hands you a receipt for every claim — running on a laptop, with its own failures on the record.**
