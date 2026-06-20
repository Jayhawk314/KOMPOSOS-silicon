# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Process-pool worker for per-region curvature — deliberately dependency-light.

`partition.analyze_partitioned` runs regions in parallel. A pool worker must import the
module holding its target function, so this lives apart from `flow_geometry` (which pulls
the heavy geometry/TensorFlow chain, ~8s per process and would erase any parallel gain).
This module imports only numpy, so workers start in ~0.2s.

Default curvature is the Effective-Resistance approximation (same formula as
geometry.fast_ricci.EffectiveResistanceCurvature: kappa = 1 - R * avg_degree * (1-alpha)),
which preserves the negative-curvature bottleneck and is deterministic across processes
(node indices come from the given order; no hash-seed-dependent set iteration). For
method="exact" the worker lazily imports the heavy path (opt-in; slower under a pool).
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np

ALPHA = 0.5


def _effres_curvature(nodes: List[str], edges: List[Tuple[str, str, str]]):
    idx = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)
    if n == 0:
        return []
    uniq = {}                                    # (i,j) -> net, undirected, deduped
    L = np.zeros((n, n))
    for s, t, net in edges:
        i, j = idx[s], idx[t]
        if i == j:
            continue
        key = (i, j) if i < j else (j, i)
        if key in uniq:
            continue
        uniq[key] = net
        L[i, i] += 1.0; L[j, j] += 1.0
        L[i, j] -= 1.0; L[j, i] -= 1.0
    if not uniq:
        return []
    avg_degree = float(np.mean(np.diag(L))) or 1.0
    L_pinv = np.linalg.pinv(L)
    out = []
    for (i, j), net in uniq.items():
        R = L_pinv[i, i] + L_pinv[j, j] - 2 * L_pinv[i, j]
        kappa = 1.0 - R * avg_degree * (1.0 - ALPHA)
        out.append((nodes[i], nodes[j], net, float(kappa)))
    out.sort(key=lambda c: c[3])
    return out


def region_curvature_task(payload):
    """Top-level, picklable. payload = (nodes, edges[(src,tgt,net)], method)."""
    nodes, edges, method = payload
    if method == "exact":
        # opt-in heavy path: only pay the geometry/TensorFlow import when explicitly asked
        from core.category import Category
        from .flow_geometry import edge_curvatures
        cat = Category(name="region", db_path=":memory:")
        for nm in nodes:
            cat.add(nm, type_name="block")
        for s, t, net in edges:
            cat.connect(s, t, name="wire", confidence=1.0, net=net)
        net_of = {frozenset((s, t)): net for s, t, net in edges}
        return [(s, t, net_of.get(frozenset((s, t)), "?"), k)
                for s, t, k in edge_curvatures(cat, method="exact")]
    return _effres_curvature(nodes, edges)
