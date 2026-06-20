#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Signed path-superposition  (DIAGNOSTIC, quantum-walk-inspired, fully classical).

Idea: instead of combining a Drug->Disease pair's multiple mechanistic chains by
max (composition) or noisy-OR (which only ADDS evidence and so inflated promiscuous
drugs), give each chain a SIGNED amplitude and SUM them, so contradictory
mechanisms destructively interfere.

Therapeutic sign of a chain  Drug --d--> Protein --p--> Disease:
    d : drug's effect on protein activity   inhibit=-1, activate=+1, (bind/target)=0
    p : does more protein => more disease    driver_of/Oncogene=+1, TumorSuppressor=-1,
                                             (associated_with, untyped)=0
    s = -(d*p)   -> +1 therapeutic, -1 harmful, 0 undeclared
    amplitude a = s * magnitude              magnitude = product of edge confidences

Aggregators tested against base = max(magnitude) (= composition, AUROC 0.9807):
    net_strict : sum of a over chains whose sign is declared (interference only)
    net_opt    : undeclared chains count as +1 (control: closer to noisy-OR)

The bet: promiscuous false positives (Sunitinib -> many cancers) carry mixed-sign
chains that cancel; clean single-driver treatments (inhibit the disease's driver)
carry all-therapeutic chains that reinforce. Classical signs (+-1) are enough for
the interference; "quantum" is only the inspiration.

Nothing here is wired into scoring. Run:  python -m oracle.path_superposition
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from validation.repurposing_benchmark import load_full_typed_view
from oracle.horns import inner_horns, _index
from oracle.horns_vs_composition import auroc
from oracle.coherence_dial import avg_rank_of_positives

INHIBIT = {"inhibits", "indirect_inhibitor"}
ACTIVATE = {"activates", "activator"}


def d_sign(rel: str) -> int:
    if rel in INHIBIT:
        return -1
    if rel in ACTIVATE:
        return 1
    return 0


def p_sign(rel: str, ptype: str) -> int:
    if rel == "driver_of":
        return 1
    if ptype == "Oncogene":
        return 1
    if ptype == "TumorSuppressor":
        return -1
    return 0


def therapeutic(d: int, p: int) -> int:
    return -(d * p)  # {-1, 0, +1}


# A chain record: (magnitude, sign, declared, protein, drug_rel, dis_rel)
Chain = Tuple[float, int, bool, str, str, str]


def build_chains(score_cat, type_by) -> Dict[Tuple[str, str], List[Chain]]:
    chains: Dict[Tuple[str, str], List[Chain]] = defaultdict(list)
    for h in inner_horns(score_cat, a_type="Drug", c_type="Disease"):
        d = d_sign(h.f_name)
        p = p_sign(h.g_name, type_by.get(h.b, ""))
        s = therapeutic(d, p)
        declared = (d != 0 and p != 0)
        chains[(h.a, h.c)].append((h.composite, s, declared, h.b, h.f_name, h.g_name))
    return chains


def main() -> None:
    print("=" * 78)
    print("  SIGNED PATH-SUPERPOSITION  --  do interfering amplitudes beat max (0.9807)?")
    print("=" * 78)

    label_cat, _ = load_full_typed_view()
    _, _, treats = _index(label_cat)
    drugs = sorted(o.name for o in label_cat.objects() if o.type_name == "Drug")
    diseases = sorted(o.name for o in label_cat.objects() if o.type_name == "Disease")

    score_cat, _ = load_full_typed_view(remove_direct_labels=True)
    type_by = {o.name: o.type_name for o in score_cat.objects()}
    chains = build_chains(score_cat, type_by)

    # ── [0] COVERAGE GATE ──────────────────────────────────────────────────
    all_ch = [c for cs in chains.values() for c in cs]
    n = len(all_ch)
    n_d = sum(1 for c in all_ch if d_sign(c[4]) != 0)
    n_p = sum(1 for c in all_ch if p_sign(c[5], type_by.get(c[3], "")) != 0)
    n_decl = sum(1 for c in all_ch if c[2])
    n_ther = sum(1 for c in all_ch if c[1] == 1)
    n_harm = sum(1 for c in all_ch if c[1] == -1)
    print("\n[0] COVERAGE GATE  (can interference even act?)")
    print(f"    total Drug->Protein->Disease chains: {n}")
    print(f"    drug->protein sign declared:  {n_d} ({100*n_d/n:.0f}%)")
    print(f"    protein->disease sign declared:{n_p} ({100*n_p/n:.0f}%)")
    print(f"    BOTH declared (chain can interfere): {n_decl} ({100*n_decl/n:.0f}%)")
    print(f"    of declared: therapeutic(+) {n_ther}, harmful(-) {n_harm}")
    if n_decl < 0.25 * n:
        print("    >> WARNING: <25% of chains are signed -- interference is starved.")
    else:
        print("    >> Enough signed structure to test interference.")

    # ── Aggregators ────────────────────────────────────────────────────────
    def base(cs):
        return max(m for m, *_ in cs)

    def net_strict(cs):
        return sum(s * m for m, s, decl, *_ in cs if decl)

    def net_opt(cs):
        return sum((s if decl else 1) * m for m, s, decl, *_ in cs)

    base_d = {k: base(v) for k, v in chains.items()}
    strict_d = {k: net_strict(v) for k, v in chains.items()}
    opt_d = {k: net_opt(v) for k, v in chains.items()}

    pairs = [(d, dis) for d in drugs for dis in diseases]
    labels = [1 if p in treats else 0 for p in pairs]
    pos_set = {p for p in pairs if p in treats and p in chains}

    def vec(dd):
        return [dd.get(p, 0.0) for p in pairs]

    print("\n[1] AUROC + avg rank of the 44 positives (lower rank = better)")
    for name, dd in [("base = max (composition)", base_d),
                     ("net_strict (interference)", strict_d),
                     ("net_opt (undeclared=+1)", opt_d)]:
        print(f"    {name:28s} AUROC {auroc(vec(dd), labels):.4f}   "
              f"avg_rank_pos {avg_rank_of_positives(dd, pairs, pos_set):.1f}")

    # ── [2] Did interference tame the promiscuous offender? ────────────────
    print("\n[2] Sunitinib: base vs net_strict across its diseases")
    suni = sorted(dis for (d, dis) in chains if d == "Sunitinib")
    for dis in suni:
        k = ("Sunitinib", dis)
        cs = chains[k]
        t = sum(1 for _, s, decl, *_ in cs if decl and s == 1)
        h = sum(1 for _, s, decl, *_ in cs if decl and s == -1)
        tag = " <- KNOWN TREAT" if k in treats else ""
        print(f"      {dis:22s} base={base_d[k]:.3f}  net_strict={strict_d[k]:+.3f}  "
              f"(+{t}/-{h} signed){tag}")

    # ── [3] Single-driver safety check ─────────────────────────────────────
    print("\n[3] Clean single-driver positives (should stay strongly positive)")
    for k in [("Imatinib", "CML"), ("Ruxolitinib", "Myelofibrosis"),
              ("Adagrasib", "Pancreatic_Cancer")]:
        if k in chains:
            cs = chains[k]
            print(f"      {k[0]}->{k[1]}: base={base_d[k]:.3f}  net_strict={strict_d[k]:+.3f}  "
                  f"chains={[(round(m,2), s) for m, s, decl, *_ in cs]}")

    print("\n" + "-" * 78)
    print("Read: if net_strict AUROC >= base AND Sunitinib's wrong diseases go")
    print("negative/small while its true ones stay positive, interference worked.")
    print("If coverage was low or signs don't separate, it's a negative result.")


if __name__ == "__main__":
    main()
