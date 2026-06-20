# Cell-Fate Net-Balance: an Interpreter, not a Predictor

**Status:** settled. The signed-cascade cell-fate machinery is a *validated mechanism
interpreter and structural-consistency engine*; it is *not* a predictor. Session
2026-06-03. Every artifact below is a standalone diagnostic — **nothing is wired into
any score or `make_strategies`.**

## TL;DR

Across a six-step arc, the *same* toolkit was excellent at **interpretation /
structure** and failed at **prediction / ranking** every single time. That is the
result. Use it to *explain and certify mechanism*, never to *rank unknown outcomes*.

| step | what we did | result |
|---|---|---|
| 1. coverage gate | measure signed structure before building | signaling layer **PASS** (OmniPath 83% signed); pharm disease layer FAIL (19%) |
| 2. control experiment | textbook perturbations vs known biology | **8/8** signed; 1/8 unsigned -- direction is real |
| 3. essentiality AUROC | predict CRISPR essentiality (CEGv2/NEGv1) | **0.36** -- below chance; wrong death mode |
| 4. `explain()` | mechanism interpreter w/ ablation + abstention | **works**; proves mediators, abstains honestly |
| 5. threshold model | minimal non-linearity for synergy | synergy **emerges** (linear = 0) -- mechanism shown |
| 6. SL search | rank synthetic-lethal pairs | **artifacts** -- hub-dominated, implausible, additive |

## The arc in detail

### 1. Coverage gate (the pre-flight that saved months)
`signaling_coverage_gate.py`, `omnipath_gate.py`, `COVERAGE_GATE_TECHNIQUE.md`.
Before building anything signed, we measured whether the structure exists. The pharm
`protein->disease` layer was 19% signed with 12 opposing edges (a signed model would
starve -- and did, AUROC 0.74). The real signed signaling network (OmniPath, 85k
edges) passed: 83% signed, 30% integrator nodes that are *real fate genes* (TP53,
MDM2, BRCA1), 454k signed cascades. Caveat the gate caught: edge balance is
activation-skewed ~9.6:1, but cascades re-balance (signs multiply along paths).

### 2. Control experiment (direction is real)
`cell_fate_netbalance.py`. Signed cascade propagation; `death_drive = Σ pro-death −
Σ pro-survival`. On textbook perturbations it scored **8/8**, including two real drugs
(Nutlin = MDM2i, Venetoclax = BCL2i) correctly pro-apoptotic. The **unsigned** baseline
scored **1/8** -- it cannot tell "activate X" from "inhibit X". Signs carried through
the cascade are necessary and sufficient for *direction*. This is a structural control
experiment (like the Die Hard jug demo vs gcd), NOT a calibrated predictor.

### 3. Essentiality AUROC (the predictor fails)
`depmap_essentiality_auroc.py`. Tested against the CRISPR-essentiality gold standard
(Hart-lab CEGv2 essential / NEGv1 non-essential). **AUROC 0.36** -- below chance, and
the model is *silent* (score 0) on 59% of genes. Reason: core-essential genes are
*housekeeping* (ribosome, proteasome, splicing) -- death by depletion, NOT routed
through the apoptosis cascade the model reads out. **A model can ace a hand-picked
control (8/8) and fail a real labeled benchmark (0.36).** That is exactly why we run
labeled benchmarks, and exactly why control != validation of prediction.

### 4. `explain()` (the interpreter, with discipline)
`explain_fate.py`. Wraps the model as an honest interpreter with three mechanisms:
- **ablation** -- name the load-bearing mediator and PROVE it by deletion (Nutlin ->
  `MDM2 --| TP73 --> PUMA`; delete TP73, 98% of the effect vanishes).
- **dominance** -- flag diffuse explanations as low-confidence (Venetoclax: 23%).
- **abstention** -- refuse on direction mismatch and on genes with no apoptosis route
  (ABCE1 -> "effect below threshold").
Crucially, **the interpreter abstains precisely on the genes that broke the predictor**
(housekeeping essentials). It knows its competence boundary. Interpretation is
validated by faithfulness/coherence/abstention -- not AUROC.

### 5. Threshold-buffer model (synergy is possible)
`threshold_buffer.py`. Linear propagation gives `dd(A+B)=dd(A)+dd(B)` exactly -> no
synergy by construction. Added the one biologically-motivated non-linearity -- a
saturating apoptosis gate `committed = max(0, death_signal − buffer_capacity)`. Genuine
super-additive synergy emerges (vs linear's flat 0), robust across a broad threshold
range for the MDM2/BCL2 case, with a clean negative control. **Structural success:** it
shows *how* synergy arises (buffer release), not that it predicts magnitude.

### 6. Synthetic-lethality search (the predictor fails again)
`synthetic_lethality_search.py`. Scanned for clean both-sub-threshold pairs. Produced
790 "hits" that **do not survive scrutiny**: dominated by ~8 hub nodes; top genes are
obscure non-apoptotic (SATB2, HPCA, ACAA2); **no known SL pairs surface**; most "hits"
are two weak *drivers* additively crossing a threshold (not buffering synergy); and
emergence is B0-narrow. Cause: `death_signal` is *reachability strength, not grounded
potency*, so it is dominated by graph topology. A tidy ranked list that looks like
discovery and is actually structure.

## The meta-pattern (the real finding)

| use mode | outcome, every time |
|---|---|
| **interpretation / structure / certification** | held (gate, 8/8 control, explain+ablation+abstention, threshold mechanism) |
| **prediction / ranking** | failed or tied baseline (essentiality 0.36, SL-search artifacts) |

This mirrors the simplicial-horns arc exactly (see `SIMPLICIAL_HORNS_FINDINGS.md`):
horns ≡ composition (no predictive gain) but gave certification; coherence dials lost
as rankers but work as confidence notes. **The categorical/signed machinery is a
language for composition and structure -- built to express and check explanations, not
to out-predict a baseline.**

## What would and would not help

- **Will NOT help:** more aggregators, thresholds, or non-linearities. Four predictive
  variants now fail the honest checks. The math side is exhausted.
- **WILL help:** *grounding and validation*. Replace reachability-strength magnitudes
  with real edge potencies; validate against real combination/dependency data
  (SynLethDB, DepMap combo screens). Then use the interpreter to *annotate validated
  hits* -- "here is the mechanism, here is the load-bearing mediator (ablation-proven),
  here is the confidence" -- which is the interpretive use, where it is strong.

## How to use this toolkit honestly

- **Do:** explain a *known* effect's mechanism; prove mediators by ablation; quantify
  confidence by dominance; abstain outside the validated (apoptosis-direction) regime;
  fact-check mechanistic claims from other systems for coherence; map the competence
  frontier via abstentions.
- **Don't:** rank unknown outcomes; trust a tidy ranked list of obscure genes;
  treat "it can explain X" as evidence that X is true; report magnitudes as potency.

## Files (pharm `oracle/`, all standalone diagnostics)

- `signaling_coverage_gate.py`, `omnipath_gate.py` -- the gate
- `cell_fate_netbalance.py` -- signed cascade + 8/8 control
- `depmap_essentiality_auroc.py` -- essentiality AUROC 0.36
- `explain_fate.py` -- `explain()` with ablation + abstention
- `explain_combination.py` -- additive (exact) + structural (ablation) combination
- `threshold_buffer.py` -- the saturating-gate non-linearity
- `synthetic_lethality_search.py` -- the SL search (artifacts)
- data: `omnipath_signed.tsv`, `CEGv2.txt`, `NEGv1.txt`
- companion: `COVERAGE_GATE_TECHNIQUE.md`, `SIMPLICIAL_HORNS_FINDINGS.md`

## Bottom line

A validated apoptosis-mechanism **interpreter** -- it traces and certifies the cascade
behind a *known* effect (8/8, real drugs), proves its mediators by ablation, and
refuses to speak outside its regime -- and a non-predictor (essentiality 0.36, SL
artifacts). Point it at *"why did this happen / does this mechanism cohere / what
mediates it,"* never at *"rank these unknowns."*
