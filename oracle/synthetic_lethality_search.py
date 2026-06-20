#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Clean synthetic-lethality search over the thresholded-buffer model  (DIAGNOSTIC).

A pair (A, B) is a CLEAN synthetic-lethal candidate when each inhibition alone is
buffered (commits no death) but together they cross the apoptosis gate:

    comm(A) = 0   AND   comm(B) = 0   AND   comm(A+B) > 0

Pipeline:
  1. reverse-BFS from the effector/buffer panels -> the set of nodes that can
     mechanistically reach the gate within K hops (keeps the scan principled+cheap).
  2. compute each node's solo (death_signal, buffer_delta).
  3. keep nodes that are SUB-THRESHOLD alone (excludes e.g. BCL2, which commits solo).
  4. scan pairs; flag and rank those that emerge together.
  5. classify roles: DRIVER (raises death_signal) + SENSITIZER (lowers buffer).
  6. robustness: confirm top hits hold across a range of the threshold B0.

HONESTY: these are pairs the *model* proposes, directional not calibrated. They are
hypotheses to test against real combination data (DepMap combo screens / SynLethDB),
NOT validated synthetic-lethal interactions. B0 and the candidate set are choices;
robustness across B0 is reported so it isn't a single-parameter artifact.

Needs data/omnipath_signed.tsv. Run:  python -m oracle.synthetic_lethality_search
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from oracle.cell_fate_netbalance import load_signed_graph
from oracle.threshold_buffer import signals, committed, EFFECTORS, BUFFERS

B0 = 0.30
FLOOR = 1e-4


def reverse_relevant(out_edges, panel, K=4):
    in_adj = defaultdict(set)
    for u, es in out_edges.items():
        for v, _ in es:
            in_adj[v].add(u)
    relevant, frontier = set(panel), set(panel)
    for _ in range(K):
        nf = set()
        for v in frontier:
            nf |= in_adj.get(v, set())
        nf -= relevant
        relevant |= nf
        frontier = nf
        if not frontier:
            break
    return relevant


def main() -> None:
    print("=" * 82)
    print("  CLEAN SYNTHETIC-LETHALITY SEARCH  (both sub-threshold alone, lethal together)")
    print("=" * 82)
    out_edges, nodes = load_signed_graph("data/omnipath_signed.tsv")
    panel = (EFFECTORS | BUFFERS) & nodes

    candidates = sorted(reverse_relevant(out_edges, panel) & set(out_edges))
    print(f"\ncandidate sources able to reach the apoptosis gate (<=4 hops): {len(candidates)}")

    single: Dict[str, Tuple[float, float]] = {}
    for n in candidates:
        single[n] = signals(out_edges, nodes, [(n, -1)])

    eligible = [n for n, (ds, bd) in single.items()
                if committed(ds, bd, B0) <= 1e-9 and (abs(ds) > FLOOR or abs(bd) > FLOOR)]
    print(f"of these, SUB-THRESHOLD alone (comm=0) and gate-relevant: {len(eligible)}")
    print(f"(threshold B0={B0}; supra-threshold solos like BCL2 correctly excluded)")

    hits = []
    for i, a in enumerate(eligible):
        dsa, bda = single[a]
        for b in eligible[i + 1:]:
            dsb, bdb = single[b]
            c = committed(dsa + dsb, bda + bdb, B0)
            if c > FLOOR:
                hits.append((c, a, b, dsa, bda, dsb, bdb))
    hits.sort(reverse=True)
    print(f"\nclean synthetic-lethal PAIRS found: {len(hits)}")

    print("\n[top candidates]  (driver raises death_signal; sensitizer lowers buffer)")
    print(f"    {'A':>10s} {'B':>10s} {'comm(A+B)':>10s}   roles")
    for c, a, b, dsa, bda, dsb, bdb in hits[:18]:
        # role by which side contributes death_signal vs buffer-lowering
        a_role = "driver" if dsa >= dsb else "sensitizer"
        b_role = "sensitizer" if a_role == "driver" else "driver"
        note = f"{a}({'ds' if dsa>=dsb else 'buf'} {dsa:+.2f}/{bda:+.2f}) + " \
               f"{b}({'ds' if dsb>dsa else 'buf'} {dsb:+.2f}/{bdb:+.2f})"
        print(f"    {a:>10s} {b:>10s} {c:10.4f}   {note}")

    # Which sensitizers recur (a dominant buffer-removal hub would be a red flag/insight)?
    from collections import Counter
    part = Counter()
    for _, a, b, *_ in hits:
        part[a] += 1; part[b] += 1
    print("\n[most frequent partners across hits]")
    for g, n in part.most_common(8):
        ds, bd = single[g]
        kind = "buffer-remover" if bd < -FLOOR else "death-driver"
        print(f"    {g:10s} in {n:4d} pairs   (solo ds={ds:+.3f} buf_delta={bd:+.3f} -> {kind})")

    # Robustness of the top 5 across the threshold.
    print("\n[robustness] do the top pairs emerge across a range of B0?")
    for c, a, b, dsa, bda, dsb, bdb in hits[:5]:
        row = []
        for tb in (0.1, 0.2, 0.3, 0.5, 0.8):
            ok = (committed(dsa, bda, tb) <= 1e-9 and committed(dsb, bdb, tb) <= 1e-9
                  and committed(dsa + dsb, bda + bdb, tb) > 1e-9)
            row.append("Y" if ok else "-")
        print(f"    {a:>10s}+{b:<10s} B0[0.1,0.2,0.3,0.5,0.8] = {' '.join(row)}")

    print("\n" + "-" * 82)
    print("These are MODEL-PROPOSED synthetic-lethal hypotheses (driver + buffer-")
    print("remover crossing the apoptosis gate together). Directional, not potency;")
    print("the honest next step is validation against real combination screens.")


if __name__ == "__main__":
    main()
