# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Flow geometry over any chip `Category` — shared by Rung 0 (synthetic) and Rung 2
(real netlists). Lifts the pattern from KOMPOSOS-GRID/domains/grid/flow_geometry.py
(Ricci congestion + Fiedler seam) onto the V substrate's geometry engines.

- Ollivier-Ricci curvature (geometry/ricci.py): negative-curvature wires are
  tree-like passages whose endpoints' neighborhoods don't overlap — the routing
  bottlenecks where congestion concentrates.
- Spectral / Fiedler (geometry/spectral.py): the algebraic connectivity is how hard
  the chip is to cut; the Fiedler vector's sign pattern is the weakest seam — the
  natural chiplet boundary.

Generic on a `Category`: nodes = blocks/instances, morphisms = wires. Domain modules
wrap these to add net names, cut sets, etc.
"""

from __future__ import annotations

from typing import List, Tuple

from core.category import Category
from geometry.ricci import OllivierRicciCurvature
from geometry.spectral import Graph, GraphLaplacian

# Above this edge count, exact optimal-transport Ricci is too slow; fall back to the
# Effective-Resistance approximation, which preserves the negative-curvature ranking
# (the bottleneck) ~4x faster. (LowerRicci is linear but loses the bottleneck, so it is
# NOT used for corridor detection.) For very large designs, partition first (partition.py).
AUTO_EXACT_MAX_EDGES = 1500


def _curvature(category: Category, method: str):
    n = len(category.morphisms())
    if method == "auto":
        method = "exact" if n < AUTO_EXACT_MAX_EDGES else "effres"
    if method == "exact":
        return OllivierRicciCurvature(category, alpha=0.5).compute_all_curvatures()
    if method == "effres":
        from geometry.fast_ricci import EffectiveResistanceCurvature
        return EffectiveResistanceCurvature(category, alpha=0.5).compute_all_curvatures()
    if method == "lower":
        from geometry.fast_ricci import LowerRicciCurvature
        return LowerRicciCurvature(category, alpha=0.5).compute_all_curvatures()
    raise ValueError(f"unknown curvature method: {method!r}")


def edge_curvatures(category: Category,
                    method: str = "auto") -> List[Tuple[str, str, float]]:
    """Undirected edge curvatures, most negative (worst bottleneck) first.

    method: "auto" (exact below AUTO_EXACT_MAX_EDGES, else effres), "exact", "effres",
    or "lower". gcd/sample stay on exact under "auto"; large designs scale automatically.
    """
    if not category.morphisms():
        return []
    result = _curvature(category, method)
    out: List[Tuple[str, str, float]] = []
    seen = set()
    for (s, t), kappa in result.edge_curvatures.items():
        key = frozenset((s, t))
        if key in seen:
            continue
        seen.add(key)
        out.append((s, t, kappa))
    out.sort(key=lambda e: e[2])
    return out


def fiedler_seam(category: Category) -> Tuple[float, List[str], List[str]]:
    """(algebraic connectivity, partition_a, partition_b) by Fiedler-vector sign."""
    names = sorted({n for m in category.morphisms() for n in (m.source, m.target)})
    if len(names) < 2:
        return 0.0, names, []
    idx = {name: i for i, name in enumerate(names)}

    g = Graph()
    for m in category.morphisms():
        g.add_edge(idx[m.source], idx[m.target], weight=1.0)

    lap = GraphLaplacian(graph=g)
    fiedler_value = lap.algebraic_connectivity()
    vec = lap.fiedler_vector()

    part_a, part_b = [], []
    for name in names:
        component = vec[idx[name]] if idx[name] < len(vec) else 0.0
        (part_a if component >= 0 else part_b).append(name)
    return fiedler_value, part_a, part_b
