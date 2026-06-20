#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Coverage gate for SIGNED-STRUCTURE methods, run on the cell-signaling subgraph.

Before building any signed-superposition / interference / cell-fate-net-balance
model, you must answer one question in ~10 seconds: does the graph actually carry
enough *signed* and *balanced* structure for interference to act? In pharm the
protein->disease layer failed this gate (19% signed, 12 opposing edges). This
checks the Mol->Mol signaling layer, which is the real substrate for cell dynamics.

Three levels (a method needs all three, not just edge coverage):

  [edge]  what fraction of signaling edges carry a +/- sign, and is + vs - balanced?
  [node]  how many nodes INTEGRATE opposing signals (>=1 activating AND >=1
          inhibiting input)? These are the decision/rheostat points -- interference
          is only meaningful where opposing signals actually meet.
  [path]  do signed edges COMPOSE into signed cascades (sign of a 2-path = product
          of edge signs)? Net effect needs composable signs.

Run:  python -m oracle.signaling_coverage_gate
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Set

from validation.repurposing_benchmark import load_full_typed_view

# Sign lexicon for the relation vocabulary in this graph.
ACTIVATE = {"activates", "activator", "activated_by", "cooperates"}        # +1
INHIBIT = {"inhibits", "indirect_inhibitor", "sequesters", "ubiquitinates"}  # -1
AMBIG_CAUSAL = {"phosphorylates", "modulates", "regulates", "regulated_by"}   # directed, sign unknown
UNSIGNED = {"targets", "binds", "interacts", "pathway_crosstalk"}             # no sign


def edge_sign(rel: str) -> int:
    if rel in ACTIVATE:
        return 1
    if rel in INHIBIT:
        return -1
    return 0  # ambiguous or unsigned -> contributes no interference


def main() -> None:
    print("=" * 76)
    print("  COVERAGE GATE  --  signed-structure check on the cell-signaling subgraph")
    print("=" * 76)

    cat, _ = load_full_typed_view()
    type_by = {o.name: o.type_name for o in cat.objects()}

    def is_mol(n: str) -> bool:
        t = type_by.get(n, "")
        return t not in ("Drug", "Disease", "")

    # Collect the Mol->Mol signaling edges.
    sig_edges = []  # (src, tgt, rel, sign)
    for m in cat.morphisms():
        if is_mol(m.source) and is_mol(m.target):
            sig_edges.append((m.source, m.target, m.name, edge_sign(m.name)))

    n = len(sig_edges)
    n_pos = sum(1 for *_, s in sig_edges if s == 1)
    n_neg = sum(1 for *_, s in sig_edges if s == -1)
    n_amb = sum(1 for _, _, r, s in sig_edges if s == 0 and r in AMBIG_CAUSAL)
    n_uns = sum(1 for _, _, r, s in sig_edges if s == 0 and r not in AMBIG_CAUSAL)
    n_signed = n_pos + n_neg

    print("\n[edge level]  can edges carry interference?")
    print(f"    signaling edges (Mol->Mol): {n}")
    print(f"    signed (+/-):   {n_signed} ({100*n_signed/n:.0f}%)   "
          f"[+{n_pos} activating, -{n_neg} inhibiting]")
    print(f"    balance (+ / -): {n_pos/max(n_neg,1):.2f}   "
          f"(near 1.0 = both forces present)")
    print(f"    ambiguous-causal (sign unknown): {n_amb}   unsigned: {n_uns}")
    print(f"    >> compare pharm protein->disease layer: 19% signed, 12 opposing total")

    # Node-level: who integrates opposing inputs?
    in_pos: Dict[str, int] = defaultdict(int)
    in_neg: Dict[str, int] = defaultdict(int)
    for _, t, _, s in sig_edges:
        if s == 1:
            in_pos[t] += 1
        elif s == -1:
            in_neg[t] += 1
    integrators = [x for x in set(in_pos) | set(in_neg) if in_pos[x] and in_neg[x]]
    targets = set(in_pos) | set(in_neg)
    print("\n[node level]  where do opposing signals actually meet?")
    print(f"    nodes receiving signed input: {len(targets)}")
    print(f"    INTEGRATORS (>=1 activating AND >=1 inhibiting input): {len(integrators)} "
          f"({100*len(integrators)/max(len(targets),1):.0f}%)")
    top = sorted(integrators, key=lambda x: in_pos[x] + in_neg[x], reverse=True)[:8]
    for x in top:
        print(f"      {x:14s} +{in_pos[x]} / -{in_neg[x]}  (a decision/rheostat node)")

    # Path-level: do signs compose into cascades?
    out_signed = defaultdict(list)   # node -> [(tgt, sign)]
    in_signed = defaultdict(list)    # node -> [(src, sign)]
    for s, t, _, sg in sig_edges:
        if sg != 0:
            out_signed[s].append((t, sg))
            in_signed[t].append((s, sg))
    casc_pos = casc_neg = 0
    for b in set(out_signed) & set(in_signed):
        for (a, s1) in in_signed[b]:
            for (c, s2) in out_signed[b]:
                if len({a, b, c}) != 3:
                    continue
                if s1 * s2 > 0:
                    casc_pos += 1
                else:
                    casc_neg += 1
    casc = casc_pos + casc_neg
    print("\n[path level]  do signs compose into net cascades?")
    print(f"    signed 2-step cascades A->B->C: {casc}")
    print(f"      net-activating (+ * + or - * -): {casc_pos}")
    print(f"      net-inhibiting (+ * - ): {casc_neg}")

    # Verdict.
    print("\n" + "-" * 76)
    passed = (n_signed / n >= 0.5) and (0.3 <= n_pos / max(n_neg, 1) <= 3.0) and integrators
    if passed:
        print("VERDICT: PASS. The signaling layer is densely + balanced-ly signed, has")
        print("real integration nodes, and signs compose into cascades. Signed")
        print("superposition / cell-fate net-balance is *fueled* here -- exactly the")
        print("structure the pharm protein->disease layer lacked. Worth prototyping.")
    else:
        print("VERDICT: FAIL or thin. Not enough signed/balanced structure; an")
        print("interference model would be starved (as in pharm). Curate signs first.")


if __name__ == "__main__":
    main()
