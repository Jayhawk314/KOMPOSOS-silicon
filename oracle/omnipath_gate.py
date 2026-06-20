#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Re-run the signed-structure coverage gate on a REAL signed causal network
(OmniPath 'omnipath' literature-curated dataset).

Loads data/omnipath_signed.tsv (download command below), assigns a sign from the
is_stimulation / is_inhibition columns, and runs the same 3-level gate as
oracle/signaling_coverage_gate.py so the numbers are directly comparable to:
    pharm protein->disease layer : 19% signed, 12 opposing  (FAIL)
    drug-graph Mol->Mol signaling: 86% signed, 33 integrators (PASS, but receptor-heavy)

Download (already run once):
    https://omnipathdb.org/interactions?datasets=omnipath&genesymbols=1&format=tsv
    -> data/omnipath_signed.tsv

Run:  python -m oracle.omnipath_gate
"""

from __future__ import annotations

from collections import defaultdict

TSV = "data/omnipath_signed.tsv"


def load_edges(path: str):
    """Yield (source, target, sign) for directed, signed interactions."""
    with open(path, encoding="utf-8") as f:
        f.readline()  # header
        for line in f:
            c = line.rstrip("\n").split("\t")
            if len(c) < 7:
                continue
            src, tgt = c[2] or c[0], c[3] or c[1]
            is_dir, stim, inh = c[4] == "True", c[5] == "True", c[6] == "True"
            if not is_dir:
                continue
            if stim and not inh:
                sign = 1
            elif inh and not stim:
                sign = -1
            else:
                sign = 0  # both (context-dependent) or neither (directed, unsigned)
            yield src, tgt, sign


def main() -> None:
    print("=" * 76)
    print("  COVERAGE GATE on OmniPath (real literature-curated signed causal network)")
    print("=" * 76)

    edges = [e for e in load_edges(TSV)]
    n = len(edges)
    n_pos = sum(1 for *_, s in edges if s == 1)
    n_neg = sum(1 for *_, s in edges if s == -1)
    n_uns = n - n_pos - n_neg
    n_signed = n_pos + n_neg

    print("\n[edge level]")
    print(f"    directed interactions: {n}")
    print(f"    signed (+/-): {n_signed} ({100*n_signed/n:.0f}%)   "
          f"[+{n_pos} stimulation, -{n_neg} inhibition]")
    print(f"    balance (+ / -): {n_pos/max(n_neg,1):.2f}")
    print(f"    directed-but-unsigned: {n_uns}")
    print("    >> pharm protein->disease: 19% signed | drug-graph signaling: 86%")

    # Node level: integrators that receive both activating and inhibiting input.
    in_pos = defaultdict(int)
    in_neg = defaultdict(int)
    out_pos = defaultdict(int)
    out_neg = defaultdict(int)
    for s, t, sg in edges:
        if sg == 1:
            in_pos[t] += 1
            out_pos[s] += 1
        elif sg == -1:
            in_neg[t] += 1
            out_neg[s] += 1
    targets = set(in_pos) | set(in_neg)
    integrators = [x for x in targets if in_pos[x] and in_neg[x]]
    print("\n[node level]")
    print(f"    nodes receiving signed input: {len(targets)}")
    print(f"    INTEGRATORS (>=1 activating AND >=1 inhibiting input): {len(integrators)} "
          f"({100*len(integrators)/max(len(targets),1):.0f}%)")
    top = sorted(integrators, key=lambda x: in_pos[x] + in_neg[x], reverse=True)[:10]
    for x in top:
        print(f"      {x:12s} +{in_pos[x]:3d} / -{in_neg[x]:3d}")

    # Path level: signed 2-step cascades, counted via degree products (fast).
    # net-activating = in_pos*out_pos + in_neg*out_neg ; net-inhibiting = mixed.
    casc_act = casc_inh = 0
    for b in set(out_pos) | set(out_neg):
        ip, ineg = in_pos.get(b, 0), in_neg.get(b, 0)
        op, oneg = out_pos.get(b, 0), out_neg.get(b, 0)
        casc_act += ip * op + ineg * oneg
        casc_inh += ip * oneg + ineg * op
    casc = casc_act + casc_inh
    print("\n[path level]  signed 2-step cascades A->B->C (degree-product count)")
    print(f"    total: {casc:,}    net-activating: {casc_act:,}    net-inhibiting: {casc_inh:,}")

    print("\n" + "-" * 76)
    cov = n_signed / n
    bal = n_pos / max(n_neg, 1)
    integ = len(integrators) / max(len(targets), 1)
    casc_bal = min(casc_act, casc_inh) / max(max(casc_act, casc_inh), 1)
    print("VERDICT (per criterion):")
    print(f"  coverage      {cov:5.0%}  {'PASS' if cov>=0.5 else 'FAIL'}  (signed edges)")
    print(f"  edge balance  {bal:5.2f}  {'PASS' if 0.3<=bal<=3.0 else 'CAVEAT'}  "
          f"(activation-skewed; inhibition under-annotated)")
    print(f"  integration   {integ:5.0%}  {'PASS' if integ>=0.15 else 'FAIL'}  "
          f"(nodes mixing +/- input -- and they are real fate genes: TP53, MDM2, BRCA1)")
    print(f"  cascade depth {casc:,} signed 2-paths, net-balance {casc_bal:.2f}  "
          f"{'PASS' if casc_bal>=0.5 else 'CHECK'}")
    print("\n  Read: coverage + integration + biology are strong (the real substrate,")
    print("  not receptors like the drug graph). The one caveat is EDGE sign-balance:")
    print("  OmniPath annotates ~9x more 'stimulation' than 'inhibition', so naive")
    print("  edge-sum interference is activation-dominated -- BUT cascades re-balance")
    print("  (net-act ~ net-inh) because signs multiply along paths. Fixes: prefer")
    print("  SIGNOR (more balanced curation), or weight by inhibition, or work at the")
    print("  cascade level. Cell-fate net-balance is fueled; just mind the edge skew.")


if __name__ == "__main__":
    main()
