#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Coherence dial: turn "how many mechanistic chains agree" into a confidence signal.

The inner-horn RANKING is provably identical to the composition strategy (it takes
the single strongest 2-hop chain). This module asks the DIFFERENT, independent
question the horn structure exposes:

    For one Drug->Disease pair, how do the *multiple* chains
    (Drug -> P1 -> Disease, Drug -> P2 -> Disease, ...) agree?

That agreement is not in the max-composite at all, so it is genuinely new signal.
We test three aggregators against the plain max (= composition):

    base      : max composite                       (the existing point estimate)
    noisy_or  : 1 - prod(1 - c_i)                    (treat chains as independent
                                                      corroborating evidence)
    corr      : base + kappa * tanh(strong-1)*(1-base)
                                                      (small tie-breaking bonus for
                                                      having several STRONG chains)

Then we measure whether the dial moves the 44 known treatments UP and the shaky
ones DOWN (AUROC + average rank of the positives). Honest test: if oncology
targeted therapies are mostly SINGLE-driver (Imatinib->BCR_ABL->CML), corroboration
may NOT help -- and that is itself a finding worth knowing.

NOTHING here is wired into scoring. Diagnostic only.

Run:  python -m oracle.coherence_dial
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, List, Tuple

from validation.repurposing_benchmark import load_full_typed_view
from oracle.horns import inner_horns, _index
from oracle.horns_vs_composition import auroc


def chain_table(score_cat) -> Dict[Tuple[str, str], List[float]]:
    """All 2-hop composite confidences per (Drug, Disease) pair."""
    chains: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    for h in inner_horns(score_cat, a_type="Drug", c_type="Disease"):
        chains[(h.a, h.c)].append(h.composite)
    return chains


# ── Aggregators ───────────────────────────────────────────────────────────────

def agg_base(cs: List[float]) -> float:
    return max(cs)


def agg_noisy_or(cs: List[float]) -> float:
    prod = 1.0
    for c in cs:
        prod *= (1.0 - c)
    return 1.0 - prod


def agg_corr(cs: List[float], kappa: float = 0.3, tau: float = 0.5) -> float:
    base = max(cs)
    strong = sum(1 for c in cs if c >= tau)
    return base + kappa * math.tanh(strong - 1) * (1.0 - base)


# ── Reporting helpers ─────────────────────────────────────────────────────────

def avg_rank_of_positives(scores: Dict[Tuple[str, str], float],
                          pairs: List[Tuple[str, str]],
                          positives: set) -> float:
    """Average rank (1 = best) of the positive pairs under a score dict.

    Lower is better. Pairs with no score sit at the bottom (rank = n).
    """
    ranked = sorted(pairs, key=lambda p: scores.get(p, 0.0), reverse=True)
    rank_of = {p: i + 1 for i, p in enumerate(ranked)}
    pos_in = [rank_of[p] for p in positives if p in rank_of]
    return sum(pos_in) / len(pos_in) if pos_in else float("nan")


def main() -> None:
    print("=" * 76)
    print("  COHERENCE DIAL  --  do multiple agreeing chains beat the single best?")
    print("=" * 76)

    label_cat, _ = load_full_typed_view()
    _, _, treats = _index(label_cat)
    drugs = sorted(o.name for o in label_cat.objects() if o.type_name == "Drug")
    diseases = sorted(o.name for o in label_cat.objects() if o.type_name == "Disease")

    score_cat, _ = load_full_typed_view(remove_direct_labels=True)
    chains = chain_table(score_cat)

    pairs = [(d, dis) for d in drugs for dis in diseases]
    labels = [1 if p in treats else 0 for p in pairs]

    base = {p: agg_base(chains[p]) for p in chains}
    nor = {p: agg_noisy_or(chains[p]) for p in chains}
    corr3 = {p: agg_corr(chains[p], kappa=0.3) for p in chains}
    corr6 = {p: agg_corr(chains[p], kappa=0.6) for p in chains}

    def vec(d):
        return [d.get(p, 0.0) for p in pairs]

    # 1. How corroborated are positives vs negatives?
    pos_pairs = [p for p in pairs if p in treats and p in chains]
    neg_pairs = [p for p in pairs if p not in treats and p in chains]

    def stat(ps, fn):
        vals = [fn(chains[p]) for p in ps]
        return sum(vals) / len(vals) if vals else float("nan")

    print("\n[1] Corroboration profile (mean over pairs that have >=1 chain)")
    print(f"    positives (n={len(pos_pairs)}): "
          f"chains={stat(pos_pairs, len):.2f}  "
          f"strong>=0.5={stat(pos_pairs, lambda cs: sum(c>=0.5 for c in cs)):.2f}  "
          f"max={stat(pos_pairs, max):.3f}")
    print(f"    negatives (n={len(neg_pairs)}): "
          f"chains={stat(neg_pairs, len):.2f}  "
          f"strong>=0.5={stat(neg_pairs, lambda cs: sum(c>=0.5 for c in cs)):.2f}  "
          f"max={stat(neg_pairs, max):.3f}")

    # 2. Does the dial improve ranking?
    print("\n[2] AUROC and average rank of the 44 positives (lower rank = better)")
    for name, d in [("base = max (composition)", base),
                    ("noisy_or (corroboration)", nor),
                    ("corr  (kappa=0.3)", corr3),
                    ("corr  (kappa=0.6)", corr6)]:
        print(f"    {name:28s} AUROC {auroc(vec(d), labels):.4f}   "
              f"avg_rank_pos {avg_rank_of_positives(d, pairs, set(pos_pairs)):.1f}")

    # 3. Where did the dial move things, and was it right?
    print("\n[3] Biggest movers: base -> noisy_or  (did corroboration help or hurt?)")
    moved = []
    for p in chains:
        moved.append((p, nor[p] - base[p], p in treats, len(chains[p])))
    moved.sort(key=lambda x: x[1], reverse=True)
    print("    largest UP-nudges (most corroborated):")
    for (d, dis), delta, is_pos, n in moved[:6]:
        tag = "KNOWN-TREAT" if is_pos else "candidate"
        print(f"      {d}->{dis}: +{delta:.3f}  ({n} chains)  [{tag}]")

    # 4. Single-driver positives -- the honest counter-test.
    single_pos = [p for p in pos_pairs if len(chains[p]) == 1]
    multi_pos = [p for p in pos_pairs if len(chains[p]) > 1]
    print(f"\n[4] Of the {len(pos_pairs)} positives with chains: "
          f"{len(single_pos)} are SINGLE-driver, {len(multi_pos)} are multi-chain.")
    print("    (If most true treatments are single-driver, rewarding corroboration")
    print("     cannot help -- the single clean mechanism IS the right answer.)")

    print("\n" + "-" * 76)
    print("Verdict printed above. The dial is a CONFIDENCE signal (corroboration),")
    print("orthogonal to the max-composite RANKING. Use it to widen/narrow the")
    print("uncertainty band, not to replace the point estimate. It pairs with the")
    print("strategy-level gray-coherence guard, which arbitrates ACROSS strategies.")


if __name__ == "__main__":
    main()
