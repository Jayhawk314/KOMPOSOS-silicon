#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Topology toolkit over core.category  --  INTERPRETIVE structural analysis.

Runs on ANY KOMPOSOS category (objects + morphisms over core.category). Pure Python,
no dependencies, so it drops into chem / pharm / sec / proof / any repo unchanged.

It answers STRUCTURAL questions -- which nodes are hubs, bottlenecks, control levers,
single points of failure, or sit in feedback loops -- NOT outcome predictions. Per the
session's findings: this machinery is a structure/interpretation engine. Other tools
validate; this one explains structure (and topology is fun).

Measures and what each one MEANS:
  degree        high-traffic node (many interactions)
  pagerank      globally influential / important
  betweenness   bottleneck -- flow funnels through it (Brandes, sampled for big graphs)
  articulation  single point of failure -- deleting it disconnects the graph
  scc (>1)      feedback loop -- a cyclic regulatory motif
  driver_nodes  minimal set you must perturb to STEER the system (the design lever;
                structural controllability, Liu-Slotine-Barabasi)
  k-core        depth of embedding -- high = inside a robust dense core

Run:  python -m oracle.topology_toolkit          # demo on the pharm category
"""

from __future__ import annotations

import sys
import random
from collections import defaultdict, deque
from typing import Dict, List, Tuple


class Topology:
    def __init__(self, nodes, out_edges):
        self.nodes = list(dict.fromkeys(nodes))
        self.out: Dict[str, List[Tuple[str, float]]] = {n: [] for n in self.nodes}
        self.in_: Dict[str, List[Tuple[str, float]]] = {n: [] for n in self.nodes}
        for u, vs in out_edges.items():
            for v, w in vs:
                if u not in self.out:
                    self.out[u] = []; self.in_[u] = []; self.nodes.append(u)
                if v not in self.out:
                    self.out[v] = []; self.in_[v] = []; self.nodes.append(v)
                self.out[u].append((v, w))
                self.in_[v].append((u, w))

    @classmethod
    def from_category(cls, cat):
        nodes = [getattr(o, "name", str(o)) for o in cat.objects()]
        out = defaultdict(list)
        for m in cat.morphisms():
            out[str(m.source)].append((str(m.target), float(getattr(m, "confidence", 1.0))))
        return cls(nodes, out)

    # ── centrality ────────────────────────────────────────────────────────────

    def degree(self) -> Dict[str, int]:
        return {n: len(self.in_[n]) + len(self.out[n]) for n in self.nodes}

    def pagerank(self, damping=0.85, iters=60) -> Dict[str, float]:
        N = len(self.nodes)
        pr = {n: 1.0 / N for n in self.nodes}
        outw = {u: sum(w for _, w in self.out[u]) for u in self.nodes}
        for _ in range(iters):
            nxt = {n: (1 - damping) / N for n in self.nodes}
            dangling = damping * sum(pr[u] for u in self.nodes if outw[u] == 0) / N
            for u in self.nodes:
                if outw[u] == 0:
                    continue
                share = damping * pr[u] / outw[u]
                for v, w in self.out[u]:
                    nxt[v] += share * w
            for n in self.nodes:
                nxt[n] += dangling
            pr = nxt
        return pr

    def betweenness(self, samples=250) -> Dict[str, float]:
        nodes = self.nodes
        adj = {u: [v for v, _ in self.out[u]] for u in nodes}
        srcs = nodes if samples >= len(nodes) else random.sample(nodes, samples)
        bc = {n: 0.0 for n in nodes}
        for s in srcs:
            S, P = [], defaultdict(list)
            sigma = defaultdict(float); sigma[s] = 1.0
            d = {n: -1 for n in nodes}; d[s] = 0
            Q = deque([s])
            while Q:
                v = Q.popleft(); S.append(v)
                for w in adj[v]:
                    if d[w] < 0:
                        d[w] = d[v] + 1; Q.append(w)
                    if d[w] == d[v] + 1:
                        sigma[w] += sigma[v]; P[w].append(v)
            delta = defaultdict(float)
            while S:
                w = S.pop()
                for v in P[w]:
                    delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w])
                if w != s:
                    bc[w] += delta[w]
        if samples < len(nodes):
            scale = len(nodes) / samples
            bc = {n: v * scale for n, v in bc.items()}
        return bc

    # ── connectivity / motifs ──────────────────────────────────────────────────

    def articulation_points(self):
        adj = defaultdict(set)
        for u in self.nodes:
            for v, _ in self.out[u]:
                if u != v:
                    adj[u].add(v); adj[v].add(u)
        sys.setrecursionlimit(max(100000, len(self.nodes) * 5))
        visited, disc, low, ap, t = set(), {}, {}, set(), [0]

        def dfs(u, parent):
            visited.add(u); disc[u] = low[u] = t[0]; t[0] += 1; children = 0
            for w in adj[u]:
                if w not in visited:
                    children += 1; dfs(w, u); low[u] = min(low[u], low[w])
                    if parent is not None and low[w] >= disc[u]:
                        ap.add(u)
                elif w != parent:
                    low[u] = min(low[u], disc[w])
            if parent is None and children > 1:
                ap.add(u)

        try:
            for n in self.nodes:
                if n not in visited:
                    dfs(n, None)
        except RecursionError:
            return None  # graph too deep for recursive AP
        return ap

    def sccs(self) -> List[List[str]]:
        adj = {u: [v for v, _ in self.out[u]] for u in self.nodes}
        radj = defaultdict(list)
        for u in self.nodes:
            for v in adj[u]:
                radj[v].append(u)
        visited, order = set(), []
        for s in self.nodes:
            if s in visited:
                continue
            stack = [(s, iter(adj[s]))]; visited.add(s)
            while stack:
                node, it = stack[-1]
                for w in it:
                    if w not in visited:
                        visited.add(w); stack.append((w, iter(adj[w]))); break
                else:
                    order.append(node); stack.pop()
        comp, seen = {}, set()
        groups = []
        for s in reversed(order):
            if s in seen:
                continue
            stack, members = [s], []
            seen.add(s)
            while stack:
                node = stack.pop(); members.append(node)
                for w in radj[node]:
                    if w not in seen:
                        seen.add(w); stack.append(w)
            groups.append(members)
        return groups

    def driver_nodes(self):
        """Structural controllability: minimum nodes to perturb to steer the system."""
        graph = {u: [v for v, _ in self.out[u]] for u in self.nodes}
        matchR = {v: None for v in self.nodes}
        matchL = {u: None for u in self.nodes}
        INF = float("inf")

        def bfs():
            dist = {}; Q = deque()
            for u in self.nodes:
                if matchL[u] is None:
                    dist[u] = 0; Q.append(u)
                else:
                    dist[u] = INF
            reachable = False
            while Q:
                u = Q.popleft()
                for v in graph[u]:
                    w = matchR[v]
                    if w is None:
                        reachable = True
                    elif dist.get(w, INF) == INF:
                        dist[w] = dist[u] + 1; Q.append(w)
            return reachable, dist

        def dfs(u, dist):
            for v in graph[u]:
                w = matchR[v]
                if w is None or (dist.get(w, INF) == dist[u] + 1 and dfs(w, dist)):
                    matchL[u] = v; matchR[v] = u; return True
            dist[u] = INF; return False

        sys.setrecursionlimit(max(100000, len(self.nodes) * 5))
        m = 0
        while True:
            ok, dist = bfs()
            if not ok:
                break
            for u in self.nodes:
                if matchL[u] is None and dfs(u, dist):
                    m += 1
        drivers = [v for v in self.nodes if matchR[v] is None]
        return drivers, m

    def short_cycles(self, max_len=3, mid_degree_cap=80) -> set:
        """Nodes in a *tight* feedback loop (2- or 3-cycle) -- not the giant SCC.

        A 2-cycle is mutual regulation (A->B and B->A, e.g. MDM2<->TP53); a 3-cycle
        is A->B->C->A. These are genuine local feedback motifs, unlike "is somewhere
        in the big recurrent core" which fires for almost everything on a dense graph.
        """
        out_set = {u: set(v for v, _ in self.out[u]) for u in self.nodes}
        in_cycle = set()
        for u in self.nodes:
            for v in out_set[u]:
                if v != u and u in out_set.get(v, ()):
                    in_cycle.add(u); in_cycle.add(v)
        if max_len >= 3:
            for u in self.nodes:
                ou = out_set[u]
                for v in ou:
                    if v == u:
                        continue
                    ov = out_set.get(v, ())
                    if len(ov) > mid_degree_cap:
                        continue  # bound cost through hub intermediates
                    for w in ov:
                        if w == u or w == v:
                            continue
                        if u in out_set.get(w, ()):
                            in_cycle.update((u, v, w))
        return in_cycle

    def cut_vertices(self, min_chunk=5) -> Dict[str, int]:
        """Articulation points whose removal ORPHANS a chunk of >= min_chunk nodes.

        Filters out leaf-bridges (removing them isolates 1-2 nodes). Returns
        {node: size of the largest chunk it disconnects}.
        """
        adj = defaultdict(set)
        for u in self.nodes:
            for v, _ in self.out[u]:
                if u != v:
                    adj[u].add(v); adj[v].add(u)
        sys.setrecursionlimit(max(100000, len(self.nodes) * 5))
        visited, disc, low, t, size = set(), {}, {}, [0], {}
        ap_chunk: Dict[str, int] = {}

        def dfs(u, parent):
            visited.add(u); disc[u] = low[u] = t[0]; t[0] += 1; size[u] = 1
            child_sizes = []
            for w in adj[u]:
                if w not in visited:
                    dfs(w, u); size[u] += size[w]; child_sizes.append(size[w])
                    low[u] = min(low[u], low[w])
                    if parent is not None and low[w] >= disc[u]:
                        ap_chunk[u] = max(ap_chunk.get(u, 0), size[w])
                elif w != parent:
                    low[u] = min(low[u], disc[w])
            if parent is None and len(child_sizes) > 1:
                child_sizes.sort(reverse=True)
                ap_chunk[u] = max(ap_chunk.get(u, 0), child_sizes[1])

        try:
            for n in self.nodes:
                if n not in visited:
                    dfs(n, None)
        except RecursionError:
            return {}
        return {a: c for a, c in ap_chunk.items() if c >= min_chunk}

    def kcore(self) -> Dict[str, int]:
        import heapq
        adj = defaultdict(set)
        for u in self.nodes:
            for v, _ in self.out[u]:
                if u != v:
                    adj[u].add(v); adj[v].add(u)
        d = {n: len(adj[n]) for n in self.nodes}
        core, remaining = {}, set(self.nodes)
        heap = [(d[n], n) for n in self.nodes]; heapq.heapify(heap)
        k = 0
        while heap:
            dv, v = heapq.heappop(heap)
            if v not in remaining:
                continue
            k = max(k, dv); core[v] = k; remaining.discard(v)
            for w in adj[v]:
                if w in remaining:
                    d[w] -= 1; heapq.heappush(heap, (d[w], w))
        return core


def _top(d, n=10):
    return sorted(d.items(), key=lambda x: x[1], reverse=True)[:n]


def report(topo: Topology, label="category"):
    print("=" * 76)
    print(f"  TOPOLOGY REPORT  --  {label}  ({len(topo.nodes)} nodes)")
    print("=" * 76)

    print("\n[hubs]  high-traffic nodes (most interactions)")
    for n, v in _top(topo.degree()):
        print(f"    {n:18s} degree {v}")

    print("\n[influence]  PageRank -- globally important")
    for n, v in _top(topo.pagerank()):
        print(f"    {n:18s} {v:.4f}")

    print("\n[bottlenecks]  betweenness -- flow funnels through them")
    for n, v in _top(topo.betweenness()):
        print(f"    {n:18s} {v:.1f}")

    ap = topo.articulation_points()
    print("\n[single points of failure]  articulation points (deletion disconnects)")
    if ap is None:
        print("    (skipped: graph too deep for recursive pass)")
    else:
        deg = topo.degree()
        for n in sorted(ap, key=lambda x: deg[x], reverse=True)[:10]:
            print(f"    {n:18s} (degree {deg[n]})")
        print(f"    total articulation points: {len(ap)}")

    sccs = [g for g in topo.sccs() if len(g) > 1]
    print("\n[feedback loops]  strongly-connected components of size > 1")
    print(f"    cyclic motifs: {len(sccs)}")
    for g in sorted(sccs, key=len, reverse=True)[:3]:
        print(f"    loop of {len(g)}: {', '.join(g[:8])}{' ...' if len(g) > 8 else ''}")

    drivers, matching = topo.driver_nodes()
    nd = len(drivers); N = len(topo.nodes)
    print("\n[control levers]  driver nodes -- minimal set to STEER the system (design)")
    print(f"    driver nodes: {nd}/{N}  (controllability nD/N = {nd/N:.2f})")
    deg = topo.degree()
    for n in sorted(drivers, key=lambda x: deg[x], reverse=True)[:8]:
        print(f"    {n:18s} (degree {deg[n]})")

    print("\n[robust cores]  k-core depth -- high = inside a dense robust core")
    for n, v in _top(topo.kcore()):
        print(f"    {n:18s} core {v}")

    print("\n" + "-" * 76)
    print("All structural / INTERPRETIVE: which nodes are hubs, bottlenecks, control")
    print("levers, failure points, loops. Not outcome prediction -- validate elsewhere.")


def main():
    from validation.repurposing_benchmark import load_full_typed_view
    cat, _ = load_full_typed_view()
    report(Topology.from_category(cat), "pharm drug-repurposing category")


if __name__ == "__main__":
    main()
