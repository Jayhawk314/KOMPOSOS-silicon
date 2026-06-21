# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Track 3 Step B (first cut): double-patterning native-conflict localization via Z/2 H1.

THE HONEST MATH FIT (see docs/SILICON_POSTMOORE_PLAN.md Track 3): a layer is decomposable
into two masks (double patterning, LELE) iff its conflict graph is 2-colorable iff it has NO
ODD CYCLES -- and an odd cycle is exactly a Z/2 H1 obstruction (graph frustration). So the
coherence engine's job here is concrete: LOCALIZE the native (unresolvable) conflicts, the
features that cannot be legally 2-colored.

This is the signed/Z2 coboundary the R-valued engine lacked. For each conflict edge (u,v) the
two masks must DIFFER: x_u + x_v = 1 (mod 2). The whole system is solvable iff bipartite; the
obstruction is the odd cycles, localized to the frustrated edges. We compute it two
independent ways and cross-check:
  1. combinatorial Z/2: BFS 2-coloring; a frustrated edge (endpoints same color) closes an
     odd cycle = a native conflict. Exact 2-colorability answer.
  2. spectral: the SIGNLESS Laplacian Q = D + A has smallest eigenvalue 0 iff the graph is
     bipartite (lambda_min > 0 measures frustration). Independent confirmation.

No-build data: the conflict graph is pure geometry -- same-layer features closer than the
coloring distance. First cut uses REAL cell placements from a DEF as the features (a
placement-proximity stand-in for layer shapes); OpenMPL conflict graphs are the later
ground-truth cross-check. Tier: tool/geometric decomposition-conflict, NOT foundry EPE.

Run:  python -m domains.silicon.dp_conflict
"""

from __future__ import annotations

import os
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np

Feature = Tuple[str, float, float]


def parse_def_placements(def_path: str, exclude_fillers: bool = True) -> List[Feature]:
    """Real placed cells as features: (name, x, y) in DEF units."""
    with open(def_path, encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    feats: List[Feature] = []
    for m in re.finditer(
            r"-\s+(\S+)\s+(\S+).*?\+\s+(?:PLACED|FIXED)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)",
            text, re.S):
        name, cell = m.group(1), m.group(2)
        if exclude_fillers and (name.startswith("FILLER") or "FILL" in cell.upper()):
            continue
        feats.append((name, float(m.group(3)), float(m.group(4))))
    return feats


def build_conflict_graph(feats: List[Feature], distance: float
                         ) -> Tuple[List[str], Dict[str, set]]:
    """Conflict edge between same-layer features within `distance` (grid-bucketed)."""
    names = [f[0] for f in feats]
    cell = max(distance, 1.0)
    buckets: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for i, (_, x, y) in enumerate(feats):
        buckets[(int(x // cell), int(y // cell))].append(i)
    adj: Dict[str, set] = {n: set() for n in names}
    d2 = distance * distance
    for (bx, by), idxs in buckets.items():
        neigh = [idx for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                 for idx in buckets.get((bx + dx, by + dy), ())]
        for i in idxs:
            _, xi, yi = feats[i]
            for j in neigh:
                if j <= i:
                    continue
                _, xj, yj = feats[j]
                if (xi - xj) ** 2 + (yi - yj) ** 2 <= d2:
                    adj[names[i]].add(names[j])
                    adj[names[j]].add(names[i])
    return names, adj


def _bbox_gap(a, b) -> float:
    """Euclidean gap between two bounding boxes (0 if they touch/overlap)."""
    dx = max(0.0, a[0] - b[2], b[0] - a[2])
    dy = max(0.0, a[1] - b[3], b[1] - a[3])
    return (dx * dx + dy * dy) ** 0.5


def build_conflict_graph_bbox(feats, distance: float) -> Tuple[List[str], Dict[str, set]]:
    """Conflict edge between real shapes whose bounding-box GAP < distance (grid-indexed).

    feats: [(id, cx, cy, bbox)]. Correct for spacing (edge-to-edge), and handles long wires
    by indexing each shape into every grid cell its distance-inflated bbox covers.
    """
    cell = max(distance, 1.0)
    grid: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for idx, (_, _, _, bb) in enumerate(feats):
        for gx in range(int((bb[0] - distance) // cell), int((bb[2] + distance) // cell) + 1):
            for gy in range(int((bb[1] - distance) // cell), int((bb[3] + distance) // cell) + 1):
                grid[(gx, gy)].append(idx)
    adj: Dict[str, set] = {f[0]: set() for f in feats}
    checked: set = set()
    for idxs in grid.values():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                key = (i, j) if i < j else (j, i)
                if key in checked:
                    continue
                checked.add(key)
                if _bbox_gap(feats[i][3], feats[j][3]) <= distance:
                    adj[feats[i][0]].add(feats[j][0])
                    adj[feats[j][0]].add(feats[i][0])
    return [f[0] for f in feats], adj


def two_color_conflicts(names: List[str], adj: Dict[str, set]
                        ) -> Tuple[bool, Dict[str, int], List[Tuple[str, str]]]:
    """BFS 2-coloring (the combinatorial Z/2 computation). Frustrated edges = native conflicts."""
    color: Dict[str, int] = {}
    frustrated: List[Tuple[str, str]] = []
    for start in names:
        if start in color:
            continue
        color[start] = 0
        q = deque([start])
        while q:
            u = q.popleft()
            for v in adj[u]:
                if v not in color:
                    color[v] = color[u] ^ 1
                    q.append(v)
                elif color[v] == color[u]:
                    e = tuple(sorted((u, v)))
                    frustrated.append(e)
    # dedup
    frustrated = sorted(set(frustrated))
    return (len(frustrated) == 0), color, frustrated


def spectral_frustration(names: List[str], adj: Dict[str, set],
                         max_comp: int = 2500) -> float:
    """Spectral cross-check: MAX over components of lambda_min(D + A).

    For a connected graph lambda_min(D+A)=0 iff bipartite, else >0. The signless Laplacian
    of the WHOLE graph is misleading (isolated/bipartite components always give 0), so we
    take the worst component: max-of-mins == 0 iff every component is bipartite iff the
    layer is 2-colorable -- agreeing with the combinatorial BFS test.
    """
    seen: set = set()
    worst = 0.0
    for s in names:
        if s in seen:
            continue
        comp: List[str] = []
        q = deque([s]); seen.add(s)
        while q:
            u = q.popleft(); comp.append(u)
            for v in adj[u]:
                if v not in seen:
                    seen.add(v); q.append(v)
        if len(comp) < 3 or len(comp) > max_comp:
            continue                              # <3 nodes always bipartite; skip huge comps
        ci = {n: i for i, n in enumerate(comp)}
        mat = np.zeros((len(comp), len(comp)))
        for u in comp:
            mat[ci[u], ci[u]] = len(adj[u])
            for v in adj[u]:
                if v in ci:
                    mat[ci[u], ci[v]] = 1.0
        worst = max(worst, float(np.linalg.eigvalsh(mat)[0]))
    return worst


@dataclass
class DPReport:
    design: str
    distance: float
    n_features: int
    n_conflict_edges: int
    colorable: bool
    n_native_conflicts: int
    frustration: float
    native_examples: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def coherent(self) -> bool:
        return self.colorable

    def render(self) -> str:
        head = ("DECOMPOSABLE (2-colorable, H1=0)" if self.colorable
                else f"NATIVE CONFLICTS (not 2-colorable, H1 != 0)")
        lines = [
            f"[{head}] double-patterning -- {self.design}",
            f"   features={self.n_features}  conflict edges={self.n_conflict_edges}  "
            f"(distance={self.distance:.0f} dbu)",
            f"   native conflicts (frustrated/odd-cycle edges): {self.n_native_conflicts}",
            f"   spectral check  max_comp lambda_min(D+A) = {self.frustration:.4f}  "
            f"({'~0 => bipartite' if self.frustration < 1e-6 else '>0 => frustrated'})",
        ]
        if self.native_examples:
            lines.append(f"   localized native conflicts (sample): {self.native_examples[:5]}")
        return "\n".join(lines)


def _report(names, adj, distance, design) -> DPReport:
    n_edges = sum(len(v) for v in adj.values()) // 2
    colorable, _, frustrated = two_color_conflicts(names, adj)
    frust = spectral_frustration(names, adj)
    return DPReport(
        design=design, distance=distance, n_features=len(names),
        n_conflict_edges=n_edges, colorable=colorable,
        n_native_conflicts=len(frustrated), frustration=frust,
        native_examples=frustrated[:5])


def analyze(def_path: str, distance: float, design: str = "design") -> DPReport:
    """Placement-proximity conflict graph (a stand-in; see analyze_gds for real shapes)."""
    names, adj = build_conflict_graph(parse_def_placements(def_path), distance)
    return _report(names, adj, distance, design)


def analyze_gds(gds_path: str, layer: int, distance: float,
                design: str = "design", cell: str | None = None) -> DPReport:
    """REAL metal shapes: conflict graph from GDS top-cell shapes on `layer` (bbox gap)."""
    from .gds import gds_features
    names, adj = build_conflict_graph_bbox(gds_features(gds_path, layer, cell), distance)
    return _report(names, adj, distance, f"{design} L{layer}")


def main() -> None:
    print("KOMPOSOS-V | silicon double-patterning native-conflict localization (Track 3 Step B)")
    print("=" * 74)
    print("Q: is this layer 2-mask decomposable, and WHERE are the native (odd-cycle) conflicts?")
    print("   (2-colorable <=> no odd cycles <=> Z/2 H1 = 0; engine localizes the obstruction)\n")
    base = "domains/silicon/data/orfs_gcd/results/base"
    gds = f"{base}/6_final.gds"
    if not os.path.exists(gds):
        print(f"[skip] {gds} absent")
        return
    # REAL metal shapes on the densest routing layer (13), distance sweep in GDS db units.
    print("--- REAL GDS metal shapes (top cell 'gcd', layer 13) ---")
    for dist in (700.0, 1400.0, 2800.0):
        print(analyze_gds(gds, 13, dist, design="orfs_gcd").render()); print()


if __name__ == "__main__":
    main()
