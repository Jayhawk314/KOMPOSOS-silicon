#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Head-to-head: horn-filling ranking  vs  the composition strategy  (DIAGNOSTIC).

Both score a Drug->Disease pair by the strongest 2-hop mechanistic composite
(Drug --mech--> intermediate --assoc--> Disease, confidence = product). The only
substantive difference:

    composition strategy : intermediate MUST be a curated biological type
                           (REPURPOSING_INTERMEDIATE_TYPES).
    horn-filling (all)   : intermediate may be ANY object -- pure categorical
                           inner-horn filling, no type prior.

So this isolates exactly one question: does the type prior on the intermediate
help, hurt, or not matter for ranking the known treatments above the rest?

Leak control: scoring runs on a category with the direct Drug->Disease labels
removed (remove_direct_labels=True); labels (the 44 'treats' edges) are read from
a separate labelled view. Neither scorer can see the edge it is being graded on.

This is the OFFICIAL benchmark's labels (the 44 FDA-approved oncology 'treats'
pairs) but a single-strategy ranking comparison, NOT the full 5-strategy ensemble
+ LOOCV pipeline. It answers "horn-filling vs composition," nothing more.

Run:  python -m oracle.horns_vs_composition
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from validation.repurposing_benchmark import load_full_typed_view
from oracle.strategies import CompositionStrategy, REPURPOSING_INTERMEDIATE_TYPES
from oracle.horns import inner_horns, best_fillers, _index


# ── Metrics (dependency-free) ─────────────────────────────────────────────────

def auroc(scores: List[float], labels: List[int]) -> float:
    """Tie-corrected AUROC via average ranks (Mann-Whitney U)."""
    n = len(scores)
    pos = sum(labels)
    neg = n - pos
    if pos == 0 or neg == 0:
        return float("nan")
    order = sorted(range(n), key=lambda i: scores[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n and scores[order[j]] == scores[order[i]]:
            j += 1
        avg = (i + 1 + j) / 2.0  # 1-based average rank across the tie block
        for k in range(i, j):
            ranks[order[k]] = avg
        i = j
    sum_pos = sum(ranks[i] for i in range(n) if labels[i] == 1)
    return (sum_pos - pos * (pos + 1) / 2.0) / (pos * neg)


def spearman(x: List[float], y: List[float]) -> float:
    """Spearman rank correlation (average-rank tie handling)."""
    def rank(v: List[float]) -> List[float]:
        n = len(v)
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n and v[order[j]] == v[order[i]]:
                j += 1
            avg = (i + 1 + j) / 2.0
            for k in range(i, j):
                r[order[k]] = avg
            i = j
        return r
    rx, ry = rank(x), rank(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den = (sum((rx[i] - mx) ** 2 for i in range(n)) *
           sum((ry[i] - my) ** 2 for i in range(n))) ** 0.5
    return num / den if den else float("nan")


# ── Scorers ───────────────────────────────────────────────────────────────────

def horn_scores(score_cat, type_by, restrict_types: Set[str] | None) -> Dict[Tuple[str, str], float]:
    """Best inner-horn composite per (Drug, Disease), optionally type-restricting B."""
    horns = inner_horns(score_cat, a_type="Drug", c_type="Disease")
    if restrict_types is not None:
        horns = [h for h in horns if type_by.get(h.b) in restrict_types]
    return {k: h.composite for k, h in best_fillers(horns).items()}


def composition_scores(score_cat, drugs, diseases) -> Dict[Tuple[str, str], float]:
    """Max composition-strategy confidence per (Drug, Disease)."""
    strat = CompositionStrategy(score_cat)
    out: Dict[Tuple[str, str], float] = {}
    for d in drugs:
        for dis in diseases:
            preds = strat.predict(d, dis)
            if preds:
                out[(d, dis)] = max(float(p.confidence) for p in preds)
    return out


# ── Driver ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 76)
    print("  HORN-FILLING vs COMPOSITION  on the 44-treatment benchmark labels")
    print("=" * 76)

    label_cat, _ = load_full_typed_view()
    type_by_lbl = {o.name: o.type_name for o in label_cat.objects()}
    _, _, treats = _index(label_cat)            # the 44 positive Drug->Disease pairs
    drugs = sorted(o.name for o in label_cat.objects() if o.type_name == "Drug")
    diseases = sorted(o.name for o in label_cat.objects() if o.type_name == "Disease")

    # Leak-free scoring graph (direct labels removed).
    score_cat, _ = load_full_typed_view(remove_direct_labels=True)
    type_by = {o.name: o.type_name for o in score_cat.objects()}

    horn_all = horn_scores(score_cat, type_by, restrict_types=None)
    horn_typed = horn_scores(score_cat, type_by, restrict_types=REPURPOSING_INTERMEDIATE_TYPES)
    comp = composition_scores(score_cat, drugs, diseases)

    # Build aligned vectors over ALL candidate Drug x Disease pairs.
    pairs = [(d, dis) for d in drugs for dis in diseases]
    labels = [1 if (d, dis) in treats else 0 for (d, dis) in pairs]
    v_all = [horn_all.get(p, 0.0) for p in pairs]
    v_typed = [horn_typed.get(p, 0.0) for p in pairs]
    v_comp = [comp.get(p, 0.0) for p in pairs]

    n_pos = sum(labels)
    print(f"\nCandidate pairs: {len(pairs)}  (drugs {len(drugs)} x diseases {len(diseases)})")
    print(f"Positives (known 'treats'): {n_pos}")
    print(f"Scored > 0:   composition {sum(s>0 for s in v_comp)}   "
          f"horn-typed {sum(s>0 for s in v_typed)}   horn-all {sum(s>0 for s in v_all)}")

    print("\n--- AUROC (rank known treatments above the rest) ---")
    print(f"  composition strategy           : {auroc(v_comp, labels):.4f}")
    print(f"  horn-filling (typed B = same)  : {auroc(v_typed, labels):.4f}")
    print(f"  horn-filling (ANY intermediate): {auroc(v_all, labels):.4f}")

    print("\n--- Agreement ---")
    print(f"  Spearman(composition, horn-typed): {spearman(v_comp, v_typed):.4f}")
    print(f"  Spearman(composition, horn-all)  : {spearman(v_comp, v_all):.4f}")

    # Top-K overlap on the *non-positive* pairs (the actual hypotheses surfaced).
    def topk_neg(vec, k=25):
        ranked = sorted(
            (p for i, p in enumerate(pairs) if labels[i] == 0),
            key=lambda p: {pp: s for pp, s in zip(pairs, vec)}[p], reverse=True)
        return ranked[:k]
    tk_comp = set(topk_neg(v_comp))
    tk_all = set(topk_neg(v_all))
    print(f"\n--- Top-25 candidate (non-label) overlap ---")
    print(f"  |composition ∩ horn-all| = {len(tk_comp & tk_all)} / 25")

    # Where horn-ALL surfaces a pair composition cannot (non-curated intermediate).
    only_horn = [(p, horn_all[p]) for p in horn_all
                 if p not in comp and labels[pairs.index(p)] == 0]
    only_horn.sort(key=lambda x: x[1], reverse=True)
    print(f"\n--- Pairs horn-ALL finds that composition DROPS (intermediate not a "
          f"curated type) ---  [{len(only_horn)} total]")
    for (d, dis), sc in only_horn[:8]:
        # show which intermediate carried it
        hs = [h for h in inner_horns(score_cat, a_type="Drug", c_type="Disease")
              if h.a == d and h.c == dis]
        h = max(hs, key=lambda h: h.composite)
        print(f"    {d} -> {dis}  conf {sc:.3f}  via {h.b} (type {type_by.get(h.b)})")

    print("\n" + "-" * 76)
    print("Read-out: with the same type prior, horn-filling and composition are the")
    print("same construction (Spearman ~ 1, equal AUROC). Dropping the prior changes")
    print("coverage; compare the AUROC delta to decide whether the biological type")
    print("filter is doing real work or just trimming the candidate list.")


if __name__ == "__main__":
    main()
