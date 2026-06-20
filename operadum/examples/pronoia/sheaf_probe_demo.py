"""
Demo: sheaf contradiction probe on a small mechanistic evidence graph.

A consistent signed graph (drug inhibits KRAS, KRAS activates MAPK, MAPK drives
the tumor, drug reduces the tumor) glues to a global section with ~zero
disagreement. Inject a source that claims the drug *increases* the tumor and the
H^1 obstruction lights up and localizes onto the conflicting edges.

    python -m examples.sheaf_probe_demo
"""

from __future__ import annotations

from pronoia.sheaf_probe import Sheaf


def consistent_graph() -> Sheaf:
    s = Sheaf()
    s.add_edge("Drug", "KRAS", sign=-1, weight=0.9)   # drug inhibits KRAS
    s.add_edge("KRAS", "MAPK", sign=+1, weight=0.8)   # KRAS activates MAPK
    s.add_edge("MAPK", "Tumor", sign=+1, weight=0.8)  # MAPK drives the tumor
    s.add_edge("Drug", "Tumor", sign=-1, weight=0.7)  # => drug reduces the tumor
    return s


def _report(title, s: Sheaf) -> None:
    r = s.probe()
    print(f"\n{title}")
    print(f"  inconsistency (H^1 proxy): {r.inconsistency:.4f}  "
          f"-> {'CONSISTENT' if r.consistent else 'CONTRADICTION'}")
    print("  worst edges (residual):")
    for edge, resid in r.edge_residuals[:3]:
        rel = "agrees" if edge.sign > 0 else "opposes"
        print(f"    {edge.u:>5} --{rel}--> {edge.v:<6} (w={edge.weight})  residual={resid:.4f}")


def main() -> None:
    print("Sheaf contradiction probe — H^1 obstruction = the disagreement that")
    print("cannot be glued away.")

    s = consistent_graph()
    _report("Consistent evidence:", s)

    s2 = consistent_graph()
    # A new source claims the OPPOSITE: the drug increases the tumor.
    s2.add_edge("Drug", "Tumor", sign=+1, weight=0.7)
    _report("After injecting a contradictory source (Drug --agrees--> Tumor):", s2)


if __name__ == "__main__":
    main()
