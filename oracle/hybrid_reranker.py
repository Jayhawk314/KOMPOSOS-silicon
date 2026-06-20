#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Hybrid re-ranker  (DIAGNOSTIC).

base = max(magnitude) (= composition, AUROC 0.9807) gives the coarse GLOBAL order.
signed path-superposition (net_strict) is reliable only where mechanism signs exist,
but where it exists it correctly surfaced a promiscuous drug's TRUE indications
(Sunitinib -> GIST, RCC) over its false ones.

Hybrid:  score = base + w * net_strict
         net_strict adds a signed, therapeutic-corroboration nudge; it is 0 for
         unsigned pairs (so they fall back to pure base), positive for clean
         therapeutic mechanisms, negative for harmful ones.

Two evaluations:
  (A) GLOBAL AUROC over all 1560 pairs  -- must NOT drop below base 0.9807.
  (B) WITHIN-DRUG ranking (the real triage use case): for each drug with a known
      treatment, rank its 20 diseases; how high is the true indication? Reported as
      MRR, mean rank, hit@1, hit@3. This is where the signed nudge should help.

Nothing here is wired into scoring. Run:  python -m oracle.hybrid_reranker
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from validation.repurposing_benchmark import load_full_typed_view
from oracle.horns import _index
from oracle.horns_vs_composition import auroc
from oracle.path_superposition import build_chains


def avg_rank_within(scores: Dict[Tuple[str, str], float],
                    drug: str, diseases: List[str], true_dis: set) -> List[float]:
    """Competition-average rank (1=best) of each true disease among the drug's 20."""
    scored = [(dis, scores.get((drug, dis), 0.0)) for dis in diseases]
    ranks = []
    for td in true_dis:
        s_td = scores.get((drug, td), 0.0)
        greater = sum(1 for _, s in scored if s > s_td)
        tied = sum(1 for _, s in scored if s == s_td)
        ranks.append(greater + (tied + 1) / 2.0)  # average rank within the tie block
    return ranks


def within_drug_metrics(scores, drugs_with_pos, diseases, pos_by_drug):
    all_ranks: List[float] = []
    for d in drugs_with_pos:
        all_ranks.extend(avg_rank_within(scores, d, diseases, pos_by_drug[d]))
    n = len(all_ranks)
    mrr = sum(1.0 / r for r in all_ranks) / n
    mean_rank = sum(all_ranks) / n
    hit1 = sum(1 for r in all_ranks if r <= 1.5) / n   # rank 1 (avg-rank <=1.5 ~ clear top)
    hit3 = sum(1 for r in all_ranks if r <= 3.0) / n
    return mrr, mean_rank, hit1, hit3, n


def main() -> None:
    print("=" * 78)
    print("  HYBRID RE-RANKER  --  base (global) + signed nudge (within-drug)")
    print("=" * 78)

    label_cat, _ = load_full_typed_view()
    _, _, treats = _index(label_cat)
    drugs = sorted(o.name for o in label_cat.objects() if o.type_name == "Drug")
    diseases = sorted(o.name for o in label_cat.objects() if o.type_name == "Disease")

    score_cat, _ = load_full_typed_view(remove_direct_labels=True)
    type_by = {o.name: o.type_name for o in score_cat.objects()}
    chains = build_chains(score_cat, type_by)

    base = {k: max(m for m, *_ in v) for k, v in chains.items()}
    strict = {k: sum(s * m for m, s, decl, *_ in v if decl) for k, v in chains.items()}

    pairs = [(d, dis) for d in drugs for dis in diseases]
    labels = [1 if p in treats else 0 for p in pairs]

    pos_by_drug: Dict[str, set] = defaultdict(set)
    for (d, dis) in treats:
        pos_by_drug[d].add(dis)
    drugs_with_pos = sorted(pos_by_drug)

    def hybrid(w):
        return {k: base.get(k, 0.0) + w * strict.get(k, 0.0) for k in base}

    def vec(dd):
        return [dd.get(p, 0.0) for p in pairs]

    print(f"\nDrugs with >=1 known treatment: {len(drugs_with_pos)}   "
          f"(total positive indications: {sum(len(v) for v in pos_by_drug.values())})")

    # (A) global AUROC must hold; (B) within-drug triage should improve.
    print("\n[A] GLOBAL AUROC      [B] WITHIN-DRUG triage (true indication among the drug's 20)")
    print(f"    {'variant':22s} {'AUROC':>7s}   {'MRR':>5s} {'meanRank':>8s} {'hit@1':>6s} {'hit@3':>6s}")
    configs = [("base (composition)", base)]
    for w in (0.2, 0.3, 0.5, 1.0):
        configs.append((f"hybrid w={w}", hybrid(w)))
    for name, dd in configs:
        a = auroc(vec(dd), labels)
        mrr, mr, h1, h3, _ = within_drug_metrics(dd, drugs_with_pos, diseases, pos_by_drug)
        print(f"    {name:22s} {a:7.4f}   {mrr:5.3f} {mr:8.2f} {h1:6.0%} {h3:6.0%}")

    # Showcase: Sunitinib's disease ranking, base vs hybrid.
    print("\n[2] Sunitinib disease ranking (true indications GIST, RCC)")
    w = 0.3
    hyb = hybrid(w)
    for label, dd in [("base", base), (f"hybrid w={w}", hyb)]:
        ordered = sorted(diseases, key=lambda dis: dd.get(("Sunitinib", dis), 0.0), reverse=True)
        marked = []
        for i, dis in enumerate(ordered[:6], 1):
            star = "*" if ("Sunitinib", dis) in treats else " "
            marked.append(f"{i}.{star}{dis}({dd.get(('Sunitinib',dis),0.0):.2f})")
        print(f"    {label:12s}: " + "  ".join(marked))
    print("    (* = known true indication; we want GIST and RCC at the top)")

    print("\n" + "-" * 78)
    print("If hybrid holds AUROC ~0.98 AND improves MRR / hit@1 vs base, the signed")
    print("nudge fixes within-drug triage (the real use case) without breaking the")
    print("global order. If MRR is flat, base already ranks indications top -- the")
    print("nudge had nothing to fix on average even if it helped Sunitinib.")


if __name__ == "__main__":
    main()
