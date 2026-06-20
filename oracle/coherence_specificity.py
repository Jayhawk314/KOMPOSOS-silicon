#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Specificity-normalized coherence dial  (DIAGNOSTIC).

Raw corroboration (noisy-OR) HURT ranking because promiscuous drugs (Sunitinib:
many kinase targets -> chains to many diseases) get boosted toward everything.
This version fixes the confound two ways and re-tests on the same 44 labels:

  1. Protein-specificity weight (IDF):
        spec(P) = log(N_dis / breadth(P)) / log(N_dis)
     where breadth(P) = # distinct diseases P connects to. A hub protein
     (TP53, associated with every cancer) -> spec ~ 0; a clean driver
     (BCR_ABL -> CML only) -> spec ~ 1. Each chain's evidence is scaled by it.

  2. Drug-promiscuity penalty:
        promisc(d) = 1 / (1 + 0.5*log(#diseases d reaches))
     so a drug that points at everything is down-weighted.

We compare against base = max composite (= composition, AUROC 0.9807, the number
to beat). Honest test: report AUROC + avg rank of the 44 positives, and check
whether a known promiscuous drug's WRONG diseases get pushed down while its right
one (if labelled) stays up.

Nothing here is wired into scoring.

Run:  python -m oracle.coherence_specificity
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, List, Tuple

from validation.repurposing_benchmark import load_full_typed_view
from oracle.horns import inner_horns, _index
from oracle.horns_vs_composition import auroc
from oracle.coherence_dial import avg_rank_of_positives

Chain = Tuple[float, str]  # (composite, intermediate protein)


def main() -> None:
    print("=" * 78)
    print("  SPECIFICITY-NORMALIZED COHERENCE  --  can it beat plain max (0.9807)?")
    print("=" * 78)

    label_cat, _ = load_full_typed_view()
    _, _, treats = _index(label_cat)
    drugs = sorted(o.name for o in label_cat.objects() if o.type_name == "Drug")
    diseases = sorted(o.name for o in label_cat.objects() if o.type_name == "Disease")
    n_dis = len(diseases)

    score_cat, _ = load_full_typed_view(remove_direct_labels=True)
    type_by = {o.name: o.type_name for o in score_cat.objects()}

    # Protein -> set of diseases it connects to (for IDF specificity).
    prot_breadth: Dict[str, set] = defaultdict(set)
    for m in score_cat.morphisms():
        if type_by.get(m.target) == "Disease":
            prot_breadth[m.source].add(m.target)

    def spec(p: str) -> float:
        b = len(prot_breadth.get(p, ())) or 1
        return math.log(n_dis / b) / math.log(n_dis) if n_dis > 1 else 1.0

    # Chains per (drug, disease), carrying the intermediate.
    chains: Dict[Tuple[str, str], List[Chain]] = defaultdict(list)
    for h in inner_horns(score_cat, a_type="Drug", c_type="Disease"):
        chains[(h.a, h.c)].append((h.composite, h.b))

    # Drug promiscuity = how many diseases it reaches.
    drug_reach: Dict[str, set] = defaultdict(set)
    for (d, dis) in chains:
        drug_reach[d].add(dis)

    def promisc(d: str) -> float:
        b = len(drug_reach.get(d, ())) or 1
        return 1.0 / (1.0 + 0.5 * math.log(b))

    # Aggregators over a pair's chains.
    def a_base(cs):
        return max(c for c, _ in cs)

    def a_spec_max(cs):
        return max(c * spec(p) for c, p in cs)

    def a_spec_nor(cs):
        pr = 1.0
        for c, p in cs:
            pr *= (1.0 - c * spec(p))
        return 1.0 - pr

    base = {k: a_base(v) for k, v in chains.items()}
    spec_max = {k: a_spec_max(v) for k, v in chains.items()}
    spec_nor = {k: a_spec_nor(v) for k, v in chains.items()}
    spec_nor_pr = {k: a_spec_nor(v) * promisc(k[0]) for k, v in chains.items()}
    base_pr = {k: a_base(v) * promisc(k[0]) for k, v in chains.items()}

    pairs = [(d, dis) for d in drugs for dis in diseases]
    labels = [1 if p in treats else 0 for p in pairs]
    pos_set = {p for p in pairs if p in treats and p in chains}

    def vec(dd):
        return [dd.get(p, 0.0) for p in pairs]

    print("\n[1] AUROC + avg rank of the 44 positives (lower rank = better)")
    rows = [
        ("base = max (composition)", base),
        ("specificity-weighted max", spec_max),
        ("specificity noisy-OR", spec_nor),
        ("base x promiscuity penalty", base_pr),
        ("spec noisy-OR x promiscuity", spec_nor_pr),
    ]
    for name, dd in rows:
        print(f"    {name:30s} AUROC {auroc(vec(dd), labels):.4f}   "
              f"avg_rank_pos {avg_rank_of_positives(dd, pairs, pos_set):.1f}")

    # [2] Sunitinib: did specificity tame the promiscuous false boosts?
    print("\n[2] Sunitinib across its diseases  (the promiscuity offender)")
    suni = sorted([dis for (d, dis) in chains if d == "Sunitinib"])
    print(f"    reaches {len(suni)} diseases; promiscuity factor {promisc('Sunitinib'):.3f}")
    for dis in suni:
        k = ("Sunitinib", dis)
        tag = " <- KNOWN TREAT" if k in treats else ""
        print(f"      {dis:24s} base={base[k]:.3f}  spec_max={spec_max[k]:.3f}  "
              f"spec_nor_pr={spec_nor_pr[k]:.3f}{tag}")

    # [3] A clean single-driver positive should be UNHARMED.
    print("\n[3] Clean single-driver checks (should stay high under specificity)")
    for k in [("Imatinib", "CML"), ("Ruxolitinib", "Myelofibrosis")]:
        if k in chains:
            ps = chains[k]
            sp = max(spec(p) for _, p in ps)
            print(f"      {k[0]}->{k[1]}: base={base[k]:.3f}  spec_max={spec_max[k]:.3f}  "
                  f"(best protein spec {sp:.2f})")

    print("\n" + "-" * 78)
    print("If specificity recovers >= base AUROC, disease-specific corroboration is")
    print("real signal and the promiscuity confound was the whole problem. If it")
    print("still trails base, the single strongest specific chain already captures")
    print("it -- keep coherence as a CONFIDENCE annotation, not a ranking term.")


if __name__ == "__main__":
    main()
