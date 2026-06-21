# Silicon — a verification-first triage layer for chip design

Point it at a routed design and it tells you, in seconds, **where the chip will be physically
heavy and where it naturally splits into chiplets — with a checkable receipt on every claim.**
It does not replace the slow sign-off tools (extraction, timing, IR); it **screens for them**,
cheaply. And where it can't justify a finding, it says so — *"unjustified" is a first-class
verdict, not a silent guess.*

The bet: **structure substitutes for scale.** Small composable engines, every kept claim
*built, executed, verified, grounded, and judged* — running on a laptop, offline.

## See it in 30 seconds (no downloads)

```bash
python -m domains.silicon.api domains/silicon/samples/tiny_core.def \
    --spef domains/silicon/samples/tiny_core.spef --top 4
```
```
KOMPOSOS-V silicon report -- tiny_core.def
  7 cells, 8 signal nets  (SPEF=yes, LEF=no)

TRIAGE -- nets most likely to be physically heavy (structural_only proposals; SPEF cap is measured_proxy)
  net                     fanout   wirelen   -curv  cap(pF)
  n_a0                         3       2.2  -0.417  0.0042
  ...
SEAM -- natural chiplet split (structural_only)
  algebraic connectivity = 0.3983  (partition 3 | 4 cells)
  1 nets cross the seam: ['n_bus']
```
It correctly isolates `n_bus` as the single net crossing the chiplet boundary — from topology
alone, with no hint. Point `api` at a real routed DEF/SPEF/LEF and it does the same at scale.

## The result that matters (validated against the *authoritative* number)

The triage isn't checked against a proxy — it's checked against a real tool's **own output**.
Run OpenROAD/OpenSTA on a routed design, take its per-net interconnect delay, and ask whether
cheap structure predicts it:

| design | best predictor | Spearman ρ | shuffle control | tier |
|---|---|---:|---:|---|
| 45_gcd | fan-out | **+0.65** | −0.05 | `measured` (attested tool, hashed) |
| orfs_gcd | wirelength | **+0.845** | −0.05 | `measured` (attested tool, hashed) |

Cheap structure predicts the slow tool's authoritative answer on two independent real designs.
(`python -m domains.silicon.tau_scoreboard`; reproducer in `sta_flows/`.)

**And it reports its own failures.** With shuffle controls, this project *disproved two of its
own hypotheses*: curvature is a weak per-net congestion predictor (it's a seam detector), and
gate-level timing slack is **not** structurally predictable (the optimizer flattens it). Those
negative results are kept on the record — which is the strongest reason to trust the positive
ones.

## What else it does (each is a real run)

```bash
python -m domains.silicon.scoreboard          # cheap structure vs real extracted parasitics (PASS + control)
python -m domains.silicon.fidelity_coherence  # 3 tool-views of a chip: do they glue? where don't they? (H0/H1)
python -m domains.silicon.coherence_trust      # which findings are independently corroborated vs single-view
python -m domains.silicon.dp_conflict          # localize double-patterning conflicts (2 methods that must agree)
python -m domains.silicon.material_bridge      # heterostructure verdicts: AGREE / REJECT / HOLLOW, gated
```

- **Cross-tool coherence** — treats synthesis/layout/extraction as three views of one chip and
  computes the exact obstruction to gluing them (H⁰/H¹), localizing the nets where they diverge.
- **A trust gate** — a finding is only TRUSTED if multiple independent views corroborate it,
  weighted so a global/non-specific view can't over-vouch. It won't cry wolf.
- **Manufacturability** — localizes the spots a metal layer can't be cleanly two-mask split,
  verified two independent ways, by the same rule a real decomposer (OpenMPL) uses.
- **Materials** — heterostructure interfaces scored on cited physics with a hard lattice veto,
  kept only if a contradiction check and an evidence-grounding gate pass.

## Honest boundaries

- No physics is simulated — these are proposals/proxies; SPICE/RedHawk/real STA stay the
  authorities. This screens *for* them.
- `measured` is lit for interconnect delay (above); IR/power and gate timing are still proxy.
- Some of the deeper math (homotopy transport, cubical Kan-fill) is scaffold, and is honestly
  not load-bearing for the results above.

## Read next

- **`docs/VALUE.md`** — the full value writeup, every claim tied to a run.
- **`docs/ROADMAP.md`** — the honest path from "claimed" to "delivered + seen."
- `docs/SILICON_FINDINGS.md` — the receipts ledger. `docs/SILICON_POSTMOORE_PLAN.md` — the frontier.

```bash
python -m pytest tests/ -q     # the whole thing, green
```
