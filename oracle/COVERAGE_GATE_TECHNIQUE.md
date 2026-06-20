# The Coverage Gate — a domain-agnostic pre-flight check

**Principle (one line):** before building a method that *depends* on a structural
property, spend ~10 seconds *measuring whether the domain has that property.* If it
doesn't, the method is starved and will fail no matter how clever the math is.

This is the single most useful methodological habit from the 2026-06-03 simplicial
session. Every failure that session was predictable from a gate we *didn't* run
first; every success was a gate that *passed*.

## Why it exists

Structure-dependent methods only produce signal when the structure is present:

| method | the structure it needs | the gate |
|---|---|---|
| Yoneda / horn similarity | objects share a **bounded anchor vocabulary** | shared-anchor gate |
| horn composition | chains actually **compose** through shared middles | composability gate |
| signed superposition / interference | edges carry a **+/- sign**, balanced, with integration points | **signed-structure gate** (this doc) |
| coherence / corroboration | multiple **independent** paths per endpoint | redundancy gate |

Run the gate *first*. A passing gate doesn't guarantee the method wins (composition
was already near-ceiling in pharm), but a *failing* gate guarantees it loses.

## The signed-structure gate (three levels)

A signed/interference method needs all three, not just edge coverage:

- **[edge]** what fraction of edges carry a +/- sign, and is + vs - **balanced**?
  (A graph that is 99% "+" can't interfere destructively — there's nothing to cancel.)
- **[node]** how many nodes **integrate opposing inputs** (>=1 activating AND >=1
  inhibiting)? Interference is only meaningful where opposing signals actually meet —
  these are the decision / rheostat nodes.
- **[path]** do signs **compose** into cascades? (sign of a 2-path = product of edge
  signs.) Net effects require composable signs.

Thresholds used: PASS if signed >= 50%, balance ratio in [0.3, 3.0], and integrator
nodes exist. Tune per domain.

Implementation: `oracle/signaling_coverage_gate.py`.

## Results this session (the gate earning its keep)

| layer tested | edge signed % | balance (+/-) | integrators | verdict |
|---|---|---|---|---|
| pharm `protein -> disease` | **19%** | — (12 opposing total) | — | **FAIL** — interference starved (confirmed AUROC 0.74) |
| pharm `Mol -> Mol` signaling | **86%** | 0.57 | 12% (receptors) | **PASS edge, weak node** — structure-proof, not a fate model |
| **OmniPath** (real signed causal net, 85k edges) | **83%** | **9.56** | **30% (TP53, MDM2, BRCA1)** | **PASS coverage+integration; CAVEAT on edge balance** |

The contrast is the whole point: the *same* signed-interference math died on the
disease layer and is well-fueled in real signaling — purely because of where the
signs live. That is exactly why you gate before you build.

### What the OmniPath run taught us (a new gate lesson)

Coverage and integration passed strongly, and the integrators are the **right
biology** — TP53, MDM2 (the canonical p53 rheostat), BRCA1, the TRAF family — i.e.
genuine cell-fate / DNA-damage decision nodes, *not* the receptors the drug-centric
graph offered. **That is the real substrate for cell-fate net-balance and
collapse-as-unreachability.**

But the gate flagged a real caveat the edge-only view would have missed: **edge
sign-balance is ~9.6:1 activation-skewed** (OmniPath annotates ~9x more "stimulation"
than "inhibition"). Naive *edge-sum* interference would be activation-dominated.
Two things rescue it, and both are recorded for reuse:
1. **Cascades re-balance.** Net-activating vs net-inhibiting 2-step cascades come out
   0.95 balanced (233k vs 221k), because signs *multiply* along paths — so working at
   the **path/cascade level** restores balance the edge level lacked.
2. **Source choice / weighting.** SIGNOR is more balanced curation; or weight by the
   rarer (inhibition) sign. Prefer one of these before naive edge-sum interference.

**Generalized lesson:** edge coverage is necessary but not sufficient — also gate
**balance** (can it cancel?) and **integration** (do opposing signals meet?), and
remember that **composition can restore a balance the raw edges lack.**

Data: `data/omnipath_signed.tsv` (download in `oracle/omnipath_gate.py` header).

### Honest node-level caveat (recorded so it isn't oversold)

Edge coverage passed (86%), but the top **integrator** nodes in *this* graph are
GPCR/drug-target receptors (HRH1, CHRM3, OPRM1, DRD2, ADRB2 ...) whose +/- inputs are
mostly **drug agonist/antagonist actions**, not intracellular cell-fate cascades. So
this drug-centric graph **proves the technique and the structure exist**, but it is
*not yet* a cell-fate model. Only 12% of nodes integrate opposing signals, and signed
cascades are shallow (94 two-step cascades). For genuine cell-fate / chromosomal-
collapse modeling, load a purpose-built **signed causal signaling network** (SIGNOR,
OmniPath) rich in the apoptosis / cell-cycle / DNA-damage machinery (BAX/BCL2, TP53,
ATM/ATR, CDK complexes), then re-run this gate — it should pass at all three levels.

## Ideas for other systems (apply the gate, then build)

**Cell fate / chromosomal collapse (next target).**
- Gate a SIGNOR/OmniPath signed network. Expect edge PASS; the real question is
  node/path: are there deep signed cascades into apoptosis/mitosis machinery?
- If it passes: `net = Σ(pro-survival) - Σ(pro-death)`; collapse = net flips OR the
  **viability witness becomes unreachable** (reachability after node/edge removal).
- Remember the boundary: the category gives wiring + net balance + reachability; the
  *timing/threshold* of collapse is dynamics (ODE/Boolean/stochastic) it **orchestrates**, not computes.

**Cyber defense (KOMPOSOS-SEC).**
- Sign = attack-advancing (+) vs deployed-control / mitigation (-). Gate question:
  are blocking edges **environment-specific and populated**, or just generic ATT&CK
  mitigations? (The cyber analogue of "19% signed".) Integration nodes = assets where
  attack paths and controls meet. Net = uncovered attack reachability.
- Pairs with the horn certification layer: horns *type* the chain (certified / novel /
  incoherent); signed superposition *prioritizes* it net of controls.

**Chemistry / materials.**
- Sign = stabilizing (+) vs destabilizing (-) interaction. Gate: do interface graphs
  carry balanced signed interactions with integration points? (Likely thin — chem
  leans on intrinsic features, not relational signs; gate would probably FAIL, which
  is itself the useful answer.)

**Generic rule of thumb.** Any time someone proposes "let opposing evidence cancel"
or "let paths reinforce/interfere," run the 3-level gate on the target graph first.
The cost is ~10 seconds; the savings is not building a method the data can't feed.

## The meta-lesson

The gate turns "will this idea work here?" from a months-long build-and-discover into
a measurement you take *before* committing. It is the cheapest honesty mechanism we
have: it makes the data, not optimism, decide whether a structure-dependent method is
worth building in a given domain.
