#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Does signed cascade net-balance PREDICT essentiality?  (the honest validation)

The cell-fate prototype reproduced textbook *direction* (8/8 control). This goes
further: it measures AUROC against a real labeled outcome -- the CRISPR-essentiality
gold standard (Hart-lab CEGv2 core-essential = 1, NEGv1 non-essential = 0), the same
reference sets DepMap screens are benchmarked on.

Hypothesis: knocking out a gene = inhibiting it (sigma=-1). If the gene is essential,
its loss should push the cell toward death, so `death_drive(inhibit X)` should be
HIGH for essential genes and LOW for non-essential ones. AUROC tests that.

Honest expectation up front: core-essential genes are mostly *housekeeping*
(ribosome, proteasome, splicing) -- death by depletion, NOT routed through the
apoptosis signaling cascade this model reads out. So a modest AUROC would itself be
the finding: "this captures apoptosis-routed death, not viability in general."

Needs data/omnipath_signed.tsv, data/CEGv2.txt, data/NEGv1.txt.
Run:  python -m oracle.depmap_essentiality_auroc
"""

from __future__ import annotations

from oracle.cell_fate_netbalance import (
    load_signed_graph, propagate, death_drive, PRO_DEATH, PRO_SURVIVAL,
)
from oracle.horns_vs_composition import auroc


def load_geneset(path: str) -> set:
    genes = set()
    with open(path, encoding="utf-8") as f:
        f.readline()  # header: GENE  HGNC_ID  ENTREZ_ID
        for line in f:
            g = line.split("\t")[0].strip()
            if g:
                genes.add(g)
    return genes


def main() -> None:
    print("=" * 78)
    print("  ESSENTIALITY AUROC  --  signed cascade net-balance vs CRISPR gold sets")
    print("=" * 78)

    out_edges, nodes = load_signed_graph("data/omnipath_signed.tsv")
    pd_ = sorted(PRO_DEATH & nodes)
    ps_ = sorted(PRO_SURVIVAL & nodes)

    ceg = load_geneset("data/CEGv2.txt")    # essential = 1
    neg = load_geneset("data/NEGv1.txt")    # non-essential = 0

    ceg_n = sorted(ceg & nodes)
    neg_n = sorted(neg & nodes)
    print(f"\nnetwork nodes: {len(nodes)}")
    print(f"CEG (essential) in network:     {len(ceg_n)}/{len(ceg)}")
    print(f"NEG (non-essential) in network: {len(neg_n)}/{len(neg)}")

    # Exclude the readout-panel genes themselves (they would self-score trivially).
    panel = PRO_DEATH | PRO_SURVIVAL
    genes = [(g, 1) for g in ceg_n if g not in panel] + \
            [(g, 0) for g in neg_n if g not in panel]

    def score(g, signed=True):
        return death_drive(propagate(out_edges, g, -1, signed=signed), pd_, ps_)

    signed_scores = [score(g, True) for g, _ in genes]
    unsigned_scores = [score(g, False) for g, _ in genes]
    labels = [lab for _, lab in genes]

    n_nonzero = sum(1 for s in signed_scores if abs(s) > 1e-12)
    print(f"genes scored (excl. panel): {len(genes)}  "
          f"({sum(labels)} essential / {len(labels)-sum(labels)} non-essential)")
    print(f"genes with a nonzero cascade score: {n_nonzero} "
          f"({100*n_nonzero/len(genes):.0f}%)")

    # Mean separation (sanity).
    e = [s for s, l in zip(signed_scores, labels) if l == 1]
    ne = [s for s, l in zip(signed_scores, labels) if l == 0]
    print(f"\nmean death_drive(inhibit):  essential {sum(e)/len(e):+.4f}   "
          f"non-essential {sum(ne)/len(ne):+.4f}")

    print("\n[AUROC] death_drive(inhibit gene) predicting essential=1")
    print(f"    signed cascade   : {auroc(signed_scores, labels):.4f}")
    print(f"    unsigned baseline: {auroc(unsigned_scores, labels):.4f}")
    print(f"    (0.5 = no signal; >0.5 = essential genes get higher death_drive)")

    print("\n" + "-" * 78)
    print("Interpretation guide:")
    print("  >=0.65  : signed cascade net-balance carries real essentiality signal.")
    print("  ~0.5    : core essentiality is housekeeping/depletion, NOT apoptosis-")
    print("            routed -- the model captures one death mode, not viability.")
    print("  Either way it is an honest measurement, not a hand-picked control.")


if __name__ == "__main__":
    main()
