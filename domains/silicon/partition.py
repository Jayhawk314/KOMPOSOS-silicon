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
# NOTE: geometry.spectral / flow_geometry pull the heavy geometry+TensorFlow chain (~8s).
# They are imported LAZILY inside the functions that need them so this module stays cheap
# to import — critical for ProcessPool workers on Windows (spawn re-imports the entry
# module per worker; a heavy import here would erase the parallel speedup).


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
    from geometry.spectral import Graph, GraphLaplacian   # lazy: heavy import
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


# Spectral bisection does a dense eigensolve, so it is only viable for modest graphs.
# Above this many nodes, fall back to spatial (placement) bisection, which is O(n log n)
# and physically meaningful (cells near each other share a region). Coordinates come
# from the DEF placement carried on each object's metadata.
SPECTRAL_MAX_NODES = 2000


def _coords(category: Category, nodes: List[str]):
    """Placement coords {node: (x, y)} from object metadata, where available."""
    out = {}
    for n in nodes:
        obj = category.get(n)
        if obj is not None:
            x, y = obj.metadata.get("x"), obj.metadata.get("y")
            if x is not None and y is not None:
                out[n] = (float(x), float(y))
    return out


def _spatial_bisect(nodes: List[str], coords) -> Tuple[List[str], List[str]]:
    """Median split along the longer placement axis (k-d-tree style). O(n log n)."""
    placed = [n for n in nodes if n in coords]
    unplaced = [n for n in nodes if n not in coords]
    if len(placed) < 2:
        mid = len(nodes) // 2
        return nodes[:mid], nodes[mid:]
    xs = [coords[n][0] for n in placed]; ys = [coords[n][1] for n in placed]
    axis = 0 if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else 1
    placed.sort(key=lambda n: coords[n][axis])
    mid = len(placed) // 2
    a, b = placed[:mid], placed[mid:]
    for i, n in enumerate(unplaced):        # spread unplaced nodes evenly
        (a if i % 2 == 0 else b).append(n)
    return a, b


def partition_nodes(category: Category, max_size: int = 1500,
                    method: str = "auto") -> List[List[str]]:
    """Recursively bisect into node groups each <= max_size.

    method: "spectral" (Fiedler; quality, small graphs), "spatial" (placement median
    split; scales to millions), or "auto" (spatial above SPECTRAL_MAX_NODES or when the
    graph is fully placed, else spectral). Spatial is used automatically for big designs.
    """
    adj = _adjacency(category)
    all_nodes = sorted(adj)
    coords = _coords(category, all_nodes)
    if method == "auto":
        method = ("spatial" if len(all_nodes) > SPECTRAL_MAX_NODES and coords
                  else "spectral")
    if method == "spatial" and not coords:
        method = "spectral"          # no placement -> can't split spatially

    work = (_components(all_nodes, adj) if method == "spectral"
            else [all_nodes])        # spatial ignores connectivity (regions are spatial)
    out: List[List[str]] = []
    while work:
        group = work.pop()
        if len(group) <= max_size:
            out.append(group)
            continue
        if method == "spectral":
            a, b = _fiedler_bisect(group, adj)
            work.extend(_components(a, adj))
            work.extend(_components(b, adj))
        else:
            a, b = _spatial_bisect(group, coords)
            work.extend([a, b])
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


def partition_category(category: Category, max_size: int = 1500,
                       method: str = "auto") -> List[Partition]:
    groups = partition_nodes(category, max_size, method=method)
    return [Partition(i, sorted(g), induced_subcategory(category, g, f"part_{i}"))
            for i, g in enumerate(groups)]


@dataclass
class PartitionedAnalysis:
    n_partitions: int
    max_partition_size: int
    corridors: List[Tuple[str, str, str, float]]   # (src,tgt,net,kappa) across regions
    inter_region_nets: List[str]                    # cut wires = seam candidates


def _resolve_workers(workers, n_parts: int) -> int:
    if workers in (None, 1):
        return 1
    import os
    cap = os.cpu_count() or 1
    n = cap if workers in ("auto", -1) else int(workers)
    return max(1, min(n, cap, n_parts))


def analyze_partitioned(bridge, max_size: int = 1500,
                        method: str = "effres",
                        partition_method: str = "auto",
                        workers=1) -> PartitionedAnalysis:
    """Bounded-cost congestion analysis: curvature per region + inter-region seam nets.

    `method` is the per-region curvature: "effres" (default; fast, dependency-light,
    preserves the bottleneck — the scale path) or "exact" (heavier, opt-in). `partition_method`
    is how regions are formed (auto/spatial/spectral). `workers` runs the independent regions
    in parallel (int, "auto", or 1 = sequential); results are identical to sequential because
    the partition is disjoint and the effres worker is deterministic across processes."""
    from ._region_worker import region_curvature_task

    cat = bridge.category
    parts = partition_category(cat, max_size, method=partition_method)
    part_of: Dict[str, int] = {n: p.index for p in parts for n in p.nodes}

    payloads = [(p.nodes,
                 [(m.source, m.target, m.metadata.get("net", "?"))
                  for m in p.category.morphisms()],
                 method)
                for p in parts]

    n_workers = _resolve_workers(workers, len(parts))
    if n_workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=n_workers) as ex:
            results = list(ex.map(region_curvature_task, payloads))
    else:
        results = [region_curvature_task(p) for p in payloads]

    corridors = [c for region in results for c in region]
    corridors.sort(key=lambda c: c[3])

    inter = sorted({m.metadata.get("net", "?") for m in cat.morphisms()
                    if part_of.get(m.source) != part_of.get(m.target)})
    return PartitionedAnalysis(len(parts), max((p.size for p in parts), default=0),
                               corridors, inter)


def main() -> None:
    """Benchmark sequential vs parallel per-region analysis (guarded for spawn)."""
    import os
    import time
    from .netlist_bridge import NetlistBridge, SAMPLE_DEF, SAMPLE_SPEF

    data = os.path.join(os.path.dirname(SAMPLE_DEF), "..", "data", "openlane")
    aes = os.path.join(data, "aes.def")
    if os.path.exists(aes):
        lef = os.path.join(data, "Nangate45.lef")
        b = NetlistBridge(aes, lef_path=lef if os.path.exists(lef) else None)
        max_size = 800
    else:
        b = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF); max_size = 3
    b.load()
    n = len({x for m in b.category.morphisms() for x in (m.source, m.target)})
    print(f"design graph: {n} nodes, {len(b.category.morphisms())} edges, "
          f"max_size={max_size}, cpus={os.cpu_count()}")

    t = time.time(); seq = analyze_partitioned(b, max_size=max_size, workers=1)
    t_seq = time.time() - t
    t = time.time(); par = analyze_partitioned(b, max_size=max_size, workers="auto")
    t_par = time.time() - t

    print(f"  sequential: {t_seq:6.1f}s  ({seq.n_partitions} regions)")
    print(f"  parallel:   {t_par:6.1f}s  speedup x{t_seq / t_par:.1f}")
    same = seq.corridors[:10] == par.corridors[:10]
    print(f"  identical top-10 corridors: {same}  worst={par.corridors[0][2] if par.corridors else None}")


if __name__ == "__main__":
    main()
