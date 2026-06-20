# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
Fast Ricci Curvature Approximations

Provides two fast alternatives to exact Ollivier-Ricci curvature:

1. EffectiveResistanceCurvature: O(n^2) via Laplacian pseudoinverse.
   Effective resistance between nodes approximates Wasserstein distance.

2. LowerRicciCurvature: O(m) via neighbor overlap bounds.
   Linear-time lower bound on Ollivier-Ricci curvature using degree-based
   estimates from Lin-Lu-Yau (2011).

Both return the same CurvatureResult type as OllivierRicciCurvature,
so they are drop-in replacements.

References:
- Lin, Lu, Yau (2011): Ricci curvature of graphs
- Chandra et al. (1996): Effective resistance and random walks
"""

from collections import defaultdict
from typing import Dict, List, Set, Tuple

import numpy as np

from geometry.ricci import CurvatureResult, GeometryType, OllivierRicciCurvature


class EffectiveResistanceCurvature:
    """
    O(n^2) curvature approximation via Laplacian pseudoinverse.

    Uses effective resistance as a proxy for Wasserstein distance:
      R(u,v) = L_pinv[u,u] + L_pinv[v,v] - 2*L_pinv[u,v]
      kappa(u,v) = 1 - R(u,v) * degree_factor

    Good for graphs with 5,000-50,000 nodes.
    """

    def __init__(self, category, alpha: float = 0.5):
        self.category = category
        self.alpha = alpha
        self._neighbors: Dict[str, Set[str]] = defaultdict(set)
        self._weights: Dict[Tuple[str, str], float] = {}
        self._build_graph()

    def _build_graph(self):
        """Build internal graph representation from category."""
        morphisms = self.category.morphisms()
        for mor in morphisms:
            source, target = mor.source, mor.target
            self._neighbors[source].add(target)
            self._neighbors[target].add(source)
            weight = mor.confidence if mor.confidence else 1.0
            self._weights[(source, target)] = weight
            self._weights[(target, source)] = weight
        self._nodes = sorted(self._neighbors.keys())
        self._node_idx = {n: i for i, n in enumerate(self._nodes)}

    def _build_laplacian(self) -> np.ndarray:
        """Build graph Laplacian matrix L = D - A."""
        n = len(self._nodes)
        L = np.zeros((n, n))
        for node in self._nodes:
            i = self._node_idx[node]
            neighbors = self._neighbors[node]
            L[i, i] = len(neighbors)
            for nb in neighbors:
                j = self._node_idx[nb]
                L[i, j] = -1.0
        return L

    def compute_all_curvatures(self) -> CurvatureResult:
        """Compute curvature for all edges using effective resistance."""
        n = len(self._nodes)
        if n == 0:
            return CurvatureResult(
                edge_curvatures={},
                node_curvatures={},
                geometry_classification={},
                statistics={"mean": 0.0, "std": 0.0, "min": 0.0,
                            "max": 0.0, "median": 0.0, "num_edges": 0,
                            "num_nodes": 0},
                analysis="No nodes in graph."
            )

        L = self._build_laplacian()
        L_pinv = np.linalg.pinv(L)

        # Average degree for normalization
        degrees = [len(self._neighbors[n]) for n in self._nodes]
        avg_degree = np.mean(degrees) if degrees else 1.0

        edge_curvatures = {}
        geometry_classification = {}
        computed_edges = set()

        for source, neighbors in self._neighbors.items():
            for target in neighbors:
                edge_key = tuple(sorted([source, target]))
                if edge_key in computed_edges:
                    continue
                computed_edges.add(edge_key)

                i = self._node_idx[source]
                j = self._node_idx[target]

                # Effective resistance
                R = L_pinv[i, i] + L_pinv[j, j] - 2 * L_pinv[i, j]

                # Convert resistance to curvature-like measure
                # Scale by average degree to normalize
                kappa = 1.0 - R * avg_degree * (1.0 - self.alpha)

                edge_curvatures[(source, target)] = kappa
                geometry_classification[(source, target)] = _classify(kappa)

        return _build_result(
            edge_curvatures, geometry_classification,
            self._nodes, "Effective Resistance"
        )


class LowerRicciCurvature:
    """
    O(m) curvature lower bound via degree-based estimates.

    Uses the Lin-Lu-Yau lower bound:
      kappa_lower(u,v) = 1/d_max - 1 + overlap(N(u), N(v)) / max(d_u, d_v)

    Linear time -- pure neighbor counting, no LP solver or matrix inversion.
    Good for graphs with >50,000 edges.
    """

    def __init__(self, category, alpha: float = 0.5):
        self.category = category
        self.alpha = alpha
        self._neighbors: Dict[str, Set[str]] = defaultdict(set)
        self._weights: Dict[Tuple[str, str], float] = {}
        self._build_graph()

    def _build_graph(self):
        """Build internal graph representation from category."""
        morphisms = self.category.morphisms()
        for mor in morphisms:
            source, target = mor.source, mor.target
            self._neighbors[source].add(target)
            self._neighbors[target].add(source)
            weight = mor.confidence if mor.confidence else 1.0
            self._weights[(source, target)] = weight
            self._weights[(target, source)] = weight
        self._nodes = set(self._neighbors.keys())

    def compute_all_curvatures(self) -> CurvatureResult:
        """Compute curvature lower bounds for all edges."""
        if not self._nodes:
            return CurvatureResult(
                edge_curvatures={},
                node_curvatures={},
                geometry_classification={},
                statistics={"mean": 0.0, "std": 0.0, "min": 0.0,
                            "max": 0.0, "median": 0.0, "num_edges": 0,
                            "num_nodes": 0},
                analysis="No nodes in graph."
            )

        # Max degree across graph
        d_max = max(len(self._neighbors[n]) for n in self._nodes)
        if d_max == 0:
            d_max = 1

        edge_curvatures = {}
        geometry_classification = {}
        computed_edges = set()

        for source, neighbors in self._neighbors.items():
            for target in neighbors:
                edge_key = tuple(sorted([source, target]))
                if edge_key in computed_edges:
                    continue
                computed_edges.add(edge_key)

                d_u = len(self._neighbors[source])
                d_v = len(self._neighbors[target])

                # Neighbor overlap (common neighbors)
                overlap = len(self._neighbors[source] & self._neighbors[target])

                # Lin-Lu-Yau lower bound
                max_deg = max(d_u, d_v)
                if max_deg == 0:
                    max_deg = 1

                kappa = (1.0 / d_max) - 1.0 + (overlap / max_deg)

                # Apply alpha correction: lazier walks see more overlap
                kappa = kappa + self.alpha * (1.0 - kappa)

                edge_curvatures[(source, target)] = kappa
                geometry_classification[(source, target)] = _classify(kappa)

        return _build_result(
            edge_curvatures, geometry_classification,
            self._nodes, "Lower Ricci (Lin-Lu-Yau)"
        )


def auto_curvature(category, alpha: float = 0.5) -> CurvatureResult:
    """
    Auto-select curvature method based on graph size.

    - <5,000 edges: exact Ollivier-Ricci (optimal transport LP)
    - >=5,000 edges: LowerRicciCurvature (linear time)

    Args:
        category: Category with objects and morphisms
        alpha: Laziness parameter for random walk

    Returns:
        CurvatureResult with full analysis
    """
    edge_count = len(category.morphisms())
    if edge_count < 5000:
        return OllivierRicciCurvature(category, alpha).compute_all_curvatures()
    else:
        return LowerRicciCurvature(category, alpha).compute_all_curvatures()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _classify(kappa: float) -> GeometryType:
    """Classify geometry type based on curvature value."""
    if kappa > 0.2:
        return GeometryType.SPHERICAL
    elif kappa < -0.2:
        return GeometryType.HYPERBOLIC
    else:
        return GeometryType.EUCLIDEAN


def _build_result(
    edge_curvatures: Dict[Tuple[str, str], float],
    geometry_classification: Dict[Tuple[str, str], GeometryType],
    nodes,
    method_name: str,
) -> CurvatureResult:
    """Build a CurvatureResult from computed edge curvatures."""
    # Node curvatures (average of incident edges)
    node_curvatures: Dict[str, float] = {}
    for node in nodes:
        incident = [k for (s, t), k in edge_curvatures.items()
                     if s == node or t == node]
        node_curvatures[node] = float(np.mean(incident)) if incident else 0.0

    curvature_values = list(edge_curvatures.values())
    if curvature_values:
        statistics = {
            "mean": float(np.mean(curvature_values)),
            "std": float(np.std(curvature_values)),
            "min": float(np.min(curvature_values)),
            "max": float(np.max(curvature_values)),
            "median": float(np.median(curvature_values)),
            "num_edges": len(curvature_values),
            "num_nodes": len(set(nodes)),
        }
    else:
        statistics = {
            "mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0,
            "median": 0.0, "num_edges": 0, "num_nodes": len(set(nodes)),
        }

    # Generate analysis
    num_spherical = sum(1 for k in curvature_values if k > 0.2)
    num_hyperbolic = sum(1 for k in curvature_values if k < -0.2)
    num_euclidean = len(curvature_values) - num_spherical - num_hyperbolic
    total = max(1, len(curvature_values))

    analysis_lines = [
        f"# {method_name} Curvature Analysis",
        "",
        "## Overview",
        f"- Analyzed {statistics['num_nodes']} nodes and {statistics['num_edges']} edges",
        f"- Mean curvature: {statistics['mean']:.4f}",
        f"- Curvature range: [{statistics['min']:.4f}, {statistics['max']:.4f}]",
        "",
        "## Geometry Distribution",
        f"- **Spherical** (clusters): {num_spherical} edges ({100*num_spherical/total:.1f}%)",
        f"- **Hyperbolic** (hierarchies): {num_hyperbolic} edges ({100*num_hyperbolic/total:.1f}%)",
        f"- **Euclidean** (chains): {num_euclidean} edges ({100*num_euclidean/total:.1f}%)",
    ]

    return CurvatureResult(
        edge_curvatures=edge_curvatures,
        node_curvatures=node_curvatures,
        geometry_classification=geometry_classification,
        statistics=statistics,
        analysis="\n".join(analysis_lines),
    )
