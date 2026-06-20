# PRONOIA (prototype)

Interpretable, non-LLM prediction stack. Working codename. Full vision:
`PRONOIA_PREDICTION_STACK.md` (currently in the operadum repo — copy it here if
you want everything together).

All six layers of the stack are built and runnable:

| Layer | Module | Idea |
|---|---|---|
| **L5 Certify** | `pronoia/honesty_mdl.py` | Honesty as compression fidelity — an honest explanation losslessly regenerates its reasoning trace; a lie shows up as excess bits (pure stdlib `zlib`). |
| **L4 Learn rules** | `pronoia/tsetlin.py` | Tsetlin Machine — learns predictions as human-readable AND-clauses, no gradients (numpy). Solves XOR; recovers conjunctive rules. |
| **L3 Generalize** | `pronoia/scm.py` | Structural Causal Model — predict under intervention `do(x)`; observation lies under confounding, do() + back-door adjustment recover the truth (numpy). |
| **L2 Predict** | `pronoia/mdl_ranker.py` | Prediction by compression — rank hypotheses by how much each compresses the evidence (`gain = L(D) − L(D∣H)`). The actual predictor (pure stdlib `zlib`). |
| **L1 Fuse** | `pronoia/sheaf_probe.py` | Cellular sheaf over a signed evidence graph — H¹ obstruction is a measurable "these sources can't all be right" alarm that localizes the contradiction (numpy). |
| **L0 Represent** | `pronoia/vsa.py` | Vector Symbolic Architecture — concepts as hypervectors; bind/bundle algebra gives holographic associative memory, one-shot learning, analogy (numpy). |

## Run

```powershell
python -m examples.honesty_mdl_demo   # honest vs hidden/fabricated/distorted
python -m examples.mdl_ranker_demo    # rank drug hypotheses by evidence compression
python -m examples.tsetlin_demo       # learn XOR + a drug rule as readable clauses
python -m examples.scm_demo           # observation lies, do(...) tells the truth
python -m examples.vsa_demo           # associative memory + one-shot classification
python -m examples.sheaf_probe_demo   # consistent graph vs injected contradiction
python examples\sheaf_on_pharm_graph.py   # run the probe on the REAL PHARM graph
python -m pytest tests -q             # 24 tests
```

## What they show

- **honesty_mdl:** the honest explanation scores `excess = 0 bits`; a hidden step
  dumps its bits into the `hidden` channel, a fabrication into the `fabricated`
  channel, a distortion into both — and `most_sincere` ABSTAINS when no honest
  explanation is on offer.
- **mdl_ranker:** ranks candidate drug→disease hypotheses by conditional
  compression benefit; the well-supported candidates (Erlotinib/Osimertinib,
  ~19% of the evidence explained) outrank the weakly-supported (Sotorasib 8.5%)
  and the unsupported (Aspirin 4.4%) — no training, no neural net.
- **tsetlin:** learns XOR (100%) with readable clauses (x0 AND NOT x1), and
  recovers a conjunctive drug-advancement rule (strong_path AND low_tox).
- **sheaf on the real PHARM graph:** 1,069 signed edges; no direct
  contradictions, mild global frustration (H¹≈0.02) that localizes onto
  tumor-suppressor genes (PTEN/TP53/RB1) carrying "+driver" signs — exactly the
  edges a domain expert would re-check.
- **vsa:** stores 4 drug→target associations in ONE 10,000-d vector and recovers
  all 4; classifies new drugs from a single labelled example per class.
- **scm:** under confounding the observed effect looks like +0.04 (drug seems
  useless), but do(...) shows the true +0.40 and back-door adjustment recovers it
  from observational data — why causal models survive distribution shift.
- **sheaf_probe:** a balanced (consistent) signed graph has inconsistency ~0; a
  single contradictory edge raises the H¹ obstruction and the top per-edge
  residual lands on the planted contradiction.

## Maturity / honesty

- These are the **computable, MEASURED-mode** versions. honesty_mdl *bounds*
  insincerity given a faithful trace; it does not prove honesty. The sheaf is the
  **scalar (rank-1)** case (signed-graph balance) — enough to prove the alarm
  fires; vector stalks with learned restriction maps are the next step.
- Dependencies: `numpy` (sheaf only); honesty_mdl is pure standard library.

Next layers per the vision doc: L2 MDL hypothesis ranker, L4 Tsetlin rules,
L3 causal upgrade, then fuse L0 (VSA) stalks into L1.
