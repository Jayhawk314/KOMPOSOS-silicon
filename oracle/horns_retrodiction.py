#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Corroboration-aggregating horn scorer + hold-out retrodiction test.

Builds on oracle/horns.py. Two questions, answered honestly against the
existing repurposing benchmark (leave-one-positive-edge-out):

  1. CORROBORATION AGGREGATION. The diagnostic in horns.py kept only the
     single strongest spine per (Drug, Disease) endpoint pair (`best_fillers`,
     a `max`). But a Drug->Disease edge supported by MANY independent
     mechanistic spines (through distinct intermediates) is stronger than one
     supported by a single spine of the same composite. Here we treat each
     distinct intermediate B as one independent line of evidence and combine
     them with noisy-OR:

         score_noisy_or(A,C) = 1 - prod_over_distinct_B ( 1 - best_composite(A,B,C) )

     where best_composite(A,B,C) = max over parallel A->B->C spines of
     (conf(A->B) * conf(B->C))  -- the multiplicative quantale composite, so
     parallel edges through the SAME protein are not double-counted, but
     additional DISTINCT proteins corroborate.

  2. HOLD-OUT RETRODICTION. For each known `treats` edge we delete it (and its
     label-derived bridges) via load_full_typed_view(skip_pair=...), rebuild
     the nerve, and ask: does horn-filling rank the held-out true edge above
     the unrelated Drug x Disease pairs? This is the chem analog of checking a
     proof's real dependencies: does the method recover truth we removed,
     rather than truth it was shown?

We compare:
    * horn-max      (single best spine -- the original diagnostic behavior)
    * horn-noisy_or (corroboration aggregation -- the new scorer)
    * leakage-free graph baselines (common_neighbor, path_count, shortest_path)

and report AUROC / AUPRC / Hits@K / MRR for each, so improvement (or its
absence) is visible and honest.

Run:
    python -m oracle.horns_retrodiction
    python -m oracle.horns_retrodiction --max-folds 30   # quick smoke run
    python -m oracle.horns_retrodiction --json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from oracle.horns import inner_horns
from validation.repurposing_benchmark import (
    DB_PATH,
    compute_auprc,
    compute_baselines,
    compute_hits_at_k,
    compute_mrr,
    drug_disease_pairs,
    load_full_typed_view,
    pairwise_auroc,
)

Pair = Tuple[str, str]


# ── Corroboration aggregation ──────────────────────────────────────────────────

def _specificity(cat) -> Dict[str, float]:
    """IDF-style specificity weight in [0,1] for each node, from its degree.

    A promiscuous hub (high degree) connects to many things and so generates
    many spurious mechanistic spines; it should corroborate LESS. A specific
    intermediate (low degree) narrows the hypothesis and should corroborate MORE.

        s(B) = clamp_0( log(N / (1 + deg(B))) / log(N) )

    deg(B) = total incident morphisms; N = number of objects. deg small -> s~1,
    deg ~ N (hub) -> s~0.
    """
    deg: Dict[str, int] = defaultdict(int)
    for m in cat.morphisms():
        deg[m.source] += 1
        deg[m.target] += 1
    n = max(2, len(list(cat.objects())))
    denom = math.log(n)
    spec: Dict[str, float] = {}
    for node, d in deg.items():
        s = math.log(n / (1 + d)) / denom
        spec[node] = max(0.0, s)
    return spec


def horn_pair_scores(
    cat,
) -> Tuple[Dict[Pair, float], Dict[Pair, float], Dict[Pair, float], Dict[Pair, int]]:
    """Score every Drug->Disease pair reachable by an inner horn.

    Returns (max_scores, noisy_or_scores, noisy_or_spec_scores, n_intermediates)
    keyed by (drug, disease). Pairs with no mechanistic spine are absent (0.0).

    * max_scores          : strongest single spine composite (old behavior).
    * noisy_or_scores     : corroboration (noisy-OR) across DISTINCT intermediates B.
    * noisy_or_spec_scores: corroboration with each B's evidence DISCOUNTED by its
                            specificity weight s(B) -- kills hub confounding.
    * n_intermediates     : how many distinct B's corroborate (support count).
    """
    spec = _specificity(cat)
    # (a,c) -> { b : best composite of any A->b->C spine }
    by_pair_b: Dict[Pair, Dict[str, float]] = defaultdict(dict)
    for h in inner_horns(cat, a_type="Drug", c_type="Disease"):
        key = (h.a, h.c)
        prev = by_pair_b[key].get(h.b, 0.0)
        if h.composite > prev:
            by_pair_b[key][h.b] = h.composite

    max_scores: Dict[Pair, float] = {}
    nor_scores: Dict[Pair, float] = {}
    nor_spec_scores: Dict[Pair, float] = {}
    support: Dict[Pair, int] = {}
    for key, b_to_comp in by_pair_b.items():
        max_scores[key] = max(b_to_comp.values())
        prod = 1.0
        prod_spec = 1.0
        for b, comp in b_to_comp.items():
            prod *= (1.0 - comp)
            prod_spec *= (1.0 - comp * spec.get(b, 0.0))
        nor_scores[key] = 1.0 - prod
        nor_spec_scores[key] = 1.0 - prod_spec
        support[key] = len(b_to_comp)
    return max_scores, nor_scores, nor_spec_scores, support


# ── Leave-one-positive-edge-out retrodiction ───────────────────────────────────

def retrodict(
    db_path: str = DB_PATH,
    max_folds: Optional[int] = None,
) -> dict:
    """Hold out each `treats` edge, score the held pair vs all negatives with
    horn-max and horn-noisy_or, and report ranking metrics for both, plus
    leakage-free graph baselines for reference."""
    base_cat, _ = load_full_typed_view(db_path)
    drugs, diseases, positives = drug_disease_pairs(base_cat)
    positives = sorted(positives)
    if max_folds is not None:
        positives = positives[:max_folds]
    negatives = [(d, dis) for d in drugs for dis in diseases if (d, dis) not in set(positives)]

    n_folds = len(positives)
    held_max: List[float] = []
    held_nor: List[float] = []
    held_nor_spec: List[float] = []
    neg_sum_max: Dict[Pair, float] = {neg: 0.0 for neg in negatives}
    neg_sum_nor: Dict[Pair, float] = {neg: 0.0 for neg in negatives}
    neg_sum_nor_spec: Dict[Pair, float] = {neg: 0.0 for neg in negatives}
    support_hist: List[int] = []

    for i, held in enumerate(positives, 1):
        fold_cat, _ = load_full_typed_view(db_path, skip_pair=held)
        s_max, s_nor, s_nor_spec, support = horn_pair_scores(fold_cat)
        held_max.append(s_max.get(held, 0.0))
        held_nor.append(s_nor.get(held, 0.0))
        held_nor_spec.append(s_nor_spec.get(held, 0.0))
        support_hist.append(support.get(held, 0))
        for neg in negatives:
            neg_sum_max[neg] += s_max.get(neg, 0.0)
            neg_sum_nor[neg] += s_nor.get(neg, 0.0)
            neg_sum_nor_spec[neg] += s_nor_spec.get(neg, 0.0)
        if i % 20 == 0:
            print(f"  ... fold {i}/{n_folds}", file=sys.stderr)

    def metrics(held_scores: List[float], neg_sums: Dict[Pair, float]) -> dict:
        scores = list(held_scores) + [v / n_folds for v in neg_sums.values()]
        labels = [1] * len(held_scores) + [0] * len(neg_sums)
        auroc, conc, disc, tied = pairwise_auroc(scores, labels)
        return {
            "auroc": round(auroc, 6),
            "auprc": round(compute_auprc(scores, labels), 6),
            "hits_at_5": round(compute_hits_at_k(scores, labels, 5), 4),
            "hits_at_10": round(compute_hits_at_k(scores, labels, 10), 4),
            "hits_at_20": round(compute_hits_at_k(scores, labels, 20), 4),
            "mrr": round(compute_mrr(scores, labels), 6),
            "held_scored": sum(1 for s in held_scores if s > 0),
        }

    # Leakage-free graph baselines (direct Drug->Disease labels removed).
    base_no_labels, _ = load_full_typed_view(db_path, remove_direct_labels=True)
    base_labels = [1 if (d, dis) in set(positives) else 0 for d in drugs for dis in diseases]
    baselines = compute_baselines(base_no_labels, drugs, diseases, base_labels)

    avg_support = round(sum(support_hist) / len(support_hist), 2) if support_hist else 0.0
    return {
        "protocol": "leave_one_positive_edge_out",
        "n_drugs": len(drugs),
        "n_diseases": len(diseases),
        "n_positives": n_folds,
        "n_negatives": len(negatives),
        "avg_intermediates_per_held_positive": avg_support,
        "horn_max": metrics(held_max, neg_sum_max),
        "horn_noisy_or": metrics(held_nor, neg_sum_nor),
        "horn_noisy_or_spec": metrics(held_nor_spec, neg_sum_nor_spec),
        "baselines": baselines,
    }


# ── Report ─────────────────────────────────────────────────────────────────────

def _print(result: dict) -> None:
    print("=" * 74)
    print("  HORN RETRODICTION  (leave-one-treats-edge-out)")
    print("=" * 74)
    print(f"Task: {result['n_drugs']} drugs x {result['n_diseases']} diseases")
    print(f"Held-out positives (folds): {result['n_positives']}")
    print(f"Avg distinct mechanistic intermediates per held positive: "
          f"{result['avg_intermediates_per_held_positive']}")

    def row(name: str, m: dict) -> str:
        return (f"  {name:18s} AUROC {m['auroc']:.4f}  AUPRC {m['auprc']:.4f}  "
                f"Hits@10 {m['hits_at_10']:.3f}  MRR {m['mrr']:.4f}  "
                f"(held scored {m['held_scored']}/{result['n_positives']})")

    print("\nHorn scorers:")
    print(row("horn-max", result["horn_max"]))
    print(row("horn-noisy_or", result["horn_noisy_or"]))
    print(row("horn-noisy_or-spec", result["horn_noisy_or_spec"]))

    base = result["horn_max"]["auroc"]
    d_nor = result["horn_noisy_or"]["auroc"] - base
    d_spec = result["horn_noisy_or_spec"]["auroc"] - base
    print(f"\n  corroboration delta vs max:  noisy_or {'+' if d_nor >= 0 else ''}{d_nor:.4f}"
          f"   noisy_or-spec {'+' if d_spec >= 0 else ''}{d_spec:.4f}")

    print("\nLeakage-free graph baselines (AUROC):")
    for n, a in sorted(result["baselines"].items(), key=lambda x: -x[1]):
        print(f"  {n:18s} {a:.4f}")
    print("\nHonest reading: noisy_or should beat max iff true edges are corroborated")
    print("by MORE independent mechanistic chains than random pairs are. If it does")
    print("not, the graph's spines are not yet independent/specific enough (hub")
    print("confounding) -- that is itself a finding, not a failure to hide.")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--max-folds", type=int, default=None,
                    help="cap number of held-out positives (for a quick smoke run)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    result = retrodict(args.db, max_folds=args.max_folds)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
