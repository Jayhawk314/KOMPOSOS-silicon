"""
Run the PRONOIA sheaf contradiction probe on the REAL KOMPOSOS-IV-PHARM graph.

The signed mechanistic edges (inhibits/activates/driver_of/treats/...) define a
cellular sheaf: a repurposing's sign-logic should compose consistently
(Drug --inhibits--> Protein --driver_of--> Disease  ==  Drug --treats--> Disease,
both net "down"). Frustration = a sign-inconsistency in the evidence — a genuine
"these sources can't all be right" signal (context-dependence or extraction error).

We report (1) direct contradictions (same pair, opposite signs) and (2) the H^1
obstruction on the largest connected component with its most-frustrated edges.

    python examples/sheaf_on_pharm_graph.py
    # or set PHARM_PATH to point elsewhere
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

from pronoia.sheaf_probe import Sheaf

PHARM = os.environ.get("PHARM_PATH", r"C:\Users\JAMES\github\KOMPOSOS-IV-PHARM")

# Relation polarity. Skipped relations carry no up/down sign (association,
# binding, targeting) and are excluded from the signed sheaf.
SIGN = {
    "inhibits": -1, "indirect_inhibitor": -1, "treats": -1,
    "sequesters": -1, "ubiquitinates": -1,
    "activates": +1, "activator": +1, "activated_by": +1, "driver_of": +1,
    "phosphorylates": +1, "enhances": +1, "synergizes_with": +1, "cooperates": +1,
}


def load_signed_edges():
    sys.path.insert(0, PHARM)
    from validation.repurposing_benchmark import load_full_typed_view
    db = os.path.join(PHARM, "data", "drugs", "tier1.db")
    category, _ = load_full_typed_view(db_path=db)

    edges, skipped = [], 0
    for m in category.morphisms():
        sign = SIGN.get(m.name)
        if sign is None:
            skipped += 1
            continue
        w = float(getattr(m, "confidence", 1.0) or 1.0)
        edges.append((m.source, m.target, sign, max(0.05, w)))
    return edges, skipped


def largest_component(edges):
    adj = defaultdict(set)
    for u, v, _, _ in edges:
        adj[u].add(v)
        adj[v].add(u)
    seen, best = set(), set()
    for start in adj:
        if start in seen:
            continue
        stack, comp = [start], set()
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            stack.extend(adj[n] - comp)
        seen |= comp
        if len(comp) > len(best):
            best = comp
    return best


def main() -> None:
    if not os.path.isdir(PHARM):
        print(f"PHARM repo not found at {PHARM}; set PHARM_PATH.")
        return

    edges, skipped = load_signed_edges()
    print(f"Signed mechanistic edges: {len(edges)}  (skipped {skipped} unsigned)")

    # (1) Direct contradictions: same unordered pair asserted with both signs.
    by_pair = defaultdict(set)
    pair_examples = defaultdict(list)
    for u, v, s, w in edges:
        key = frozenset((u, v))
        by_pair[key].add(s)
        pair_examples[key].append((u, v, s, w))
    direct = [k for k, signs in by_pair.items() if len(signs) > 1]
    print(f"\nDirect sign contradictions (same pair, both + and -): {len(direct)}")
    for key in direct[:8]:
        a, b = tuple(key) if len(key) == 2 else (next(iter(key)), next(iter(key)))
        rels = ", ".join(f"{u}->{v}:{'+' if s>0 else '-'}(w={w:.2f})"
                         for u, v, s, w in pair_examples[key])
        print(f"   {a} <-> {b}:  {rels}")

    # (2) Global H^1 frustration on the largest connected component.
    comp = largest_component(edges)
    sub = [(u, v, s, w) for u, v, s, w in edges if u in comp and v in comp]
    sheaf = Sheaf()
    for u, v, s, w in sub:
        sheaf.add_edge(u, v, s, w)
    report = sheaf.probe()
    print(f"\nLargest connected component: {len(comp)} nodes, {len(sub)} signed edges")
    print(f"  H^1 inconsistency (min normalised disagreement): {report.inconsistency:.4f}"
          f"  -> {'CONSISTENT' if report.consistent else 'FRUSTRATED'}")
    print("  most-frustrated edges (global sign-logic violations):")
    for edge, resid in report.edge_residuals[:10]:
        if resid <= 1e-9:
            break
        rel = "+" if edge.sign > 0 else "-"
        print(f"    {edge.u:>16} --{rel}--> {edge.v:<16} (w={edge.weight:.2f})  residual={resid:.4f}")


if __name__ == "__main__":
    main()
