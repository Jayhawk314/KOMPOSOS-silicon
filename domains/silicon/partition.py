# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Partitioning for scale — bound the cost of flow geometry on large designs.

Exact Ollivier-Ricci is optimal-transport per edge; even Effective-Resistance is O(n^2).
Neither scales to a million-cell block run whole. But congestion is local, so we
**partition first**: recursively Fiedler-bisect the routing graph into regions of bounded
size, then run flow geometry per region. Cost becomes ~linear in the number of regions,
each region is small enough for exact curvature, and the regions are independent (trivially
parallelizable). This is the "design triage over detail" philosophy made concrete.

Honest boundary: bisection CUTS inter-region wires, so the worst *inter-region* edge (a
chiplet seam) is not seen inside any region — that is exactly what the cheap global
`fiedler_seam` is for. So: seams come from the global spectral pass; intra-region
congestion corridors come from the bounded per-region curvature.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from core.category import Category
from core.types import Object, Morphism
from geometry.spectral import Graph, GraphLaplacian
from .flow_geometry import edge_curvatures


@dataclass
class Partition:
    index: int
    nodes: List[str]
    category: Category

    @property
    def size(self) -> int:
        return len(self.nodes)


def _adjacency(category: Category) -> Dict[str, Set[str]]:
    adj: Dict[str, Set[str]] = {}
    for m in category.morphisms():
        adj.setdefault(m.source, set()).add(m.target)
        adj.setdefault(m.target, set()).add(m.source)
    return adj


def _components(nodes: List[str], adj: Dict[str, Set[str]]) -> List[List[str]]:
    seen: Set[str] = set()
    out: List[List[str]] = []
    nodeset = set(nodes)
    for start in nodes:
        if start in seen:
            continue
        stack, comp = [start], []
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n); comp.append(n)
            stack.extend(x for x in adj.get(n, ()) if x in nodeset and x not in seen)
        out.append(comp)
    return out


def _fiedler_bisect(nodes: List[str], adj: Dict[str, Set[str]]) -> Tuple[List[str], List[str]]:
    """Split a connected node set by Fiedler-vector sign (balanced fallback if degenerate)."""
    idx = {n: i for i, n in enumerate(nodes)}
    g = Graph()
    for n in nodes:
        for m in adj.get(n, ()):
            if m in idx and idx[m] > idx[n]:
                g.add_edge(idx[n], idx[m], weight=1.0)
    lap = GraphLaplacian(graph=g)
    vec = lap.fiedler_vector()
    a, b = [], []
    for n in nodes:
        comp = vec[idx[n]] if idx[n] < len(vec) else 0.0
        (a if comp >= 0 else b).append(n)
    if not a or not b:                       # degenerate -> even split, keep recursion finite
        mid = len(nodes) // 2
        a, b = nodes[:mid], nodes[mid:]
    return a, b


def partition_nodes(category: Category, max_size: int = 1500) -> List[List[str]]:
    """Recursively Fiedler-bisect into node groups each <= max_size."""
    adj = _adjacency(category)
    all_nodes = sorted(adj)
    work = _components(all_nodes, adj)
    out: List[List[str]] = []
    while work:
        group = work.pop()
        if len(group) <= max_size:
            out.append(group)
            continue
        a, b = _fiedler_bisect(group, adj)
        work.extend(_components(a, adj))
        work.extend(_components(b, adj))
    return out


def induced_subcategory(category: Category, nodes: List[str], name: str) -> Category:
    nodeset = set(nodes)
    sub = Category(name=name, db_path=":memory:")
    for n in nodes:
        obj = category.get(n)
        sub.add_object(Object(name=n, type_name=obj.type_name if obj else "block",
                              metadata=dict(obj.metadata) if obj else {}))
    for m in category.morphisms():
        if m.source in nodeset and m.target in nodeset:
            sub.add_morphism(Morphism(name=m.name, source=m.source, target=m.target,
                                      confidence=m.confidence, metadata=dict(m.metadata)))
    return sub


def partition_category(category: Category, max_size: int = 1500) -> List[Partition]:
    groups = partition_nodes(category, max_size)
    return [Partition(i, sorted(g), induced_subcategory(category, g, f"part_{i}"))
            for i, g in enumerate(groups)]


@dataclass
class PartitionedAnalysis:
    n_partitions: int
    max_partition_size: int
    corridors: List[Tuple[str, str, str, float]]   # (src,tgt,net,kappa) across regions
    inter_region_nets: List[str]                    # cut wires = seam candidates


def analyze_partitioned(bridge, max_size: int = 1500,
                        method: str = "auto") -> PartitionedAnalysis:
    """Bounded-cost congestion analysis: curvature per region + inter-region seam nets."""
    cat = bridge.category
    parts = partition_category(cat, max_size)
    part_of: Dict[str, int] = {n: p.index for p in parts for n in p.nodes}

    corridors: List[Tuple[str, str, str, float]] = []
    for p in parts:
        net_of = {frozenset((m.source, m.target)): m.metadata.get("net", "?")
                  for m in p.category.morphisms()}
        for s, t, k in edge_curvatures(p.category, method=method):
            corridors.append((s, t, net_of.get(frozenset((s, t)), "?"), k))
    corridors.sort(key=lambda c: c[3])

    inter = sorted({m.metadata.get("net", "?") for m in cat.morphisms()
                    if part_of.get(m.source) != part_of.get(m.target)})
    return PartitionedAnalysis(len(parts), max((p.size for p in parts), default=0),
                               corridors, inter)
