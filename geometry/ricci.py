"""
Ollivier-Ricci Curvature for Knowledge Graphs

Implements discrete Ricci curvature computation using optimal transport.

The Ollivier-Ricci curvature of an edge (u,v) measures how much the
neighborhoods of u and v overlap:
- Positive curvature: neighborhoods overlap (cluster-like)
- Negative curvature: neighborhoods diverge (tree-like)
- Zero curvature: flat (chain-like)

This is the discrete analog of Ricci curvature from differential geometry,
and connects to Thurston's geometrization through the Ricci flow.

References:
- Ollivier (2009): Ricci curvature of Markov chains on metric spaces
- Lin, Lu, Yau (2011): Ricci curvature of graphs
- Ni et al. (2015): Community detection via Ricci flow
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional, Any
from enum import Enum
import numpy as np
from collections import defaultdict

# Try to import scipy for optimal transport
try:
    from scipy.optimize import linprog
    from scipy.spatial.distance import cdist
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


class GeometryType(Enum):
    """Classification of local geometry based on curvature."""
    SPHERICAL = "spherical"      # Positive curvature, cluster-like
    HYPERBOLIC = "hyperbolic"    # Negative curvature, tree-like
    EUCLIDEAN = "euclidean"      # Near-zero curvature, flat
    UNKNOWN = "unknown"


@dataclass
class CurvatureResult:
    """Result of curvature computation for the entire graph."""
    edge_curvatures: Dict[Tuple[str, str], float]
    node_curvatures: Dict[str, float]  # Average of incident edges
    geometry_classification: Dict[Tuple[str, str], GeometryType]
    statistics: Dict[str, float]
    analysis: str

    @property
    def num_spherical(self) -> int:
        return sum(1 for g in self.geometry_classification.values() if g == GeometryType.SPHERICAL)

    @property
    def num_hyperbolic(self) -> int:
        return sum(1 for g in self.geometry_classification.values() if g == GeometryType.HYPERBOLIC)

    @property
    def num_euclidean(self) -> int:
        return sum(1 for g in self.geometry_classification.values() if g == GeometryType.EUCLIDEAN)


class OllivierRicciCurvature:
    """
    Compute Ollivier-Ricci curvature for knowledge graphs.

    The curvature of edge (u,v) is:
        kappa(u,v) = 1 - W_1(mu_u, mu_v) / d(u,v)

    Where:
    - W_1 is the Wasserstein-1 (earth mover's) distance
    - mu_u is the probability distribution on neighbors of u
    - d(u,v) is the edge distance (we use 1 for unweighted)

    For knowledge graphs, this reveals:
    - Clusters of related concepts (spherical, kappa > 0)
    - Hierarchical structures (hyperbolic, kappa < 0)
    - Linear chains of influence (euclidean, kappa ~ 0)
    """

    def __init__(self, category, alpha: float = 0.5):
        """
        Initialize curvature computer.

        Args:
            category: Category with objects and morphisms
            alpha: Laziness parameter for random walk (0 = pure neighbors, 1 = stay at node)
                   Default 0.5 gives weight to both the node and its neighbors
        """
        self.category = category
        self.alpha = alpha
        self._graph = None
        self._neighbors = None
        self._weights = None
        self._build_graph()

    def _build_graph(self):
        """Build internal graph representation from store."""
        self._neighbors = defaultdict(set)
        self._weights = {}

        # Get all morphisms
        morphisms = self.category.morphisms()

        for mor in morphisms:
            source, target = mor.source, mor.target

            # Add both directions for undirected curvature analysis
            self._neighbors[source].add(target)
            self._neighbors[target].add(source)

            # Store edge weight (use confidence if available)
            weight = mor.confidence if mor.confidence else 1.0
            self._weights[(source, target)] = weight
            self._weights[(target, source)] = weight

        # Get all nodes
        self._nodes = set(self._neighbors.keys())

    def _get_neighbor_distribution(self, node: str) -> Dict[str, float]:
        """
        Get probability distribution over neighbors of a node.

        Uses lazy random walk: with probability alpha stay at node,
        with probability (1-alpha) move uniformly to a neighbor.
        """
        neighbors = self._neighbors.get(node, set())
        if not neighbors:
            return {node: 1.0}

        distribution = {}

        # Lazy part: probability alpha to stay
        distribution[node] = self.alpha

        # Uniform distribution over neighbors
        neighbor_prob = (1 - self.alpha) / len(neighbors)
        for neighbor in neighbors:
            distribution[neighbor] = neighbor_prob

        return distribution

    def _wasserstein_distance(self, mu: Dict[str, float], nu: Dict[str, float]) -> float:
        """
        Compute Wasserstein-1 distance between two distributions.

        Uses linear programming when scipy is available,
        otherwise falls back to a simpler approximation.
        """
        if not SCIPY_AVAILABLE:
            return self._wasserstein_approximate(mu, nu)

        # Get all nodes in either distribution
        all_nodes = list(set(mu.keys()) | set(nu.keys()))
        n = len(all_nodes)

        if n == 0:
            return 0.0

        # Build node index mapping
        node_to_idx = {node: i for i, node in enumerate(all_nodes)}

        # Build cost matrix (graph distances)
        cost_matrix = np.zeros((n, n))
        for i, node_i in enumerate(all_nodes):
            for j, node_j in enumerate(all_nodes):
                if i != j:
                    # Use shortest path distance (simplified: 1 if neighbors, 2 otherwise)
                    if node_j in self._neighbors.get(node_i, set()):
                        cost_matrix[i, j] = 1.0
                    else:
                        cost_matrix[i, j] = 2.0  # Not direct neighbors

        # Build supply and demand vectors
        supply = np.array([mu.get(node, 0.0) for node in all_nodes])
        demand = np.array([nu.get(node, 0.0) for node in all_nodes])

        # Normalize
        supply = supply / supply.sum() if supply.sum() > 0 else supply
        demand = demand / demand.sum() if demand.sum() > 0 else demand

        # Solve optimal transport via linear programming
        # Variables: flow[i,j] for each pair
        # Minimize: sum cost[i,j] * flow[i,j]
        # Subject to: sum_j flow[i,j] = supply[i], sum_i flow[i,j] = demand[j]

        c = cost_matrix.flatten()

        # Equality constraints for supply
        A_eq_supply = np.zeros((n, n * n))
        for i in range(n):
            A_eq_supply[i, i * n:(i + 1) * n] = 1

        # Equality constraints for demand
        A_eq_demand = np.zeros((n, n * n))
        for j in range(n):
            for i in range(n):
                A_eq_demand[j, i * n + j] = 1

        A_eq = np.vstack([A_eq_supply, A_eq_demand])
        b_eq = np.concatenate([supply, demand])

        # Bounds: flow >= 0
        bounds = [(0, None) for _ in range(n * n)]

        try:
            result = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
            if result.success:
                return result.fun
            else:
                return self._wasserstein_approximate(mu, nu)
        except Exception:
            return self._wasserstein_approximate(mu, nu)

    def _wasserstein_approximate(self, mu: Dict[str, float], nu: Dict[str, float]) -> float:
        """
        Approximate Wasserstein distance when scipy unavailable.

        Uses total variation distance as upper bound.
        """
        all_nodes = set(mu.keys()) | set(nu.keys())
        tv_distance = 0.5 * sum(abs(mu.get(n, 0) - nu.get(n, 0)) for n in all_nodes)
        return tv_distance

    def compute_edge_curvature(self, source: str, target: str) -> float:
        """
        Compute Ollivier-Ricci curvature for a single edge.

        kappa(u,v) = 1 - W_1(mu_u, mu_v) / d(u,v)

        Args:
            source: Source node name
            target: Target node name

        Returns:
            Curvature value (positive = spherical, negative = hyperbolic)
        """
        # Get neighbor distributions
        mu_source = self._get_neighbor_distribution(source)
        mu_target = self._get_neighbor_distribution(target)

        # Compute Wasserstein distance
        W1 = self._wasserstein_distance(mu_source, mu_target)

        # Edge distance (default 1 for unweighted)
        d = self._weights.get((source, target), 1.0)

        # Curvature
        kappa = 1 - W1 / d

        return kappa

    def compute_all_curvatures(self) -> CurvatureResult:
        """
        Compute curvature for all edges in the graph.

        Returns:
            CurvatureResult with edge curvatures, classifications, and analysis
        """
        edge_curvatures = {}
        geometry_classification = {}

        # Compute curvature for each edge
        computed_edges = set()
        for source, neighbors in self._neighbors.items():
            for target in neighbors:
                # Avoid computing twice for undirected edges
                edge_key = tuple(sorted([source, target]))
                if edge_key in computed_edges:
                    continue
                computed_edges.add(edge_key)

                kappa = self.compute_edge_curvature(source, target)
                edge_curvatures[(source, target)] = kappa

                # Classify geometry
                geometry_classification[(source, target)] = self._classify_curvature(kappa)

        # Compute node curvatures (average of incident edges)
        node_curvatures = {}
        for node in self._nodes:
            incident_curvatures = []
            for (s, t), kappa in edge_curvatures.items():
                if s == node or t == node:
                    incident_curvatures.append(kappa)
            if incident_curvatures:
                node_curvatures[node] = np.mean(incident_curvatures)
            else:
                node_curvatures[node] = 0.0

        # Compute statistics
        curvature_values = list(edge_curvatures.values())
        statistics = {
            "mean": np.mean(curvature_values) if curvature_values else 0.0,
            "std": np.std(curvature_values) if curvature_values else 0.0,
            "min": np.min(curvature_values) if curvature_values else 0.0,
            "max": np.max(curvature_values) if curvature_values else 0.0,
            "median": np.median(curvature_values) if curvature_values else 0.0,
            "num_edges": len(curvature_values),
            "num_nodes": len(self._nodes),
        }

        # Generate analysis
        analysis = self._generate_analysis(edge_curvatures, node_curvatures, statistics)

        return CurvatureResult(
            edge_curvatures=edge_curvatures,
            node_curvatures=node_curvatures,
            geometry_classification=geometry_classification,
            statistics=statistics,
            analysis=analysis
        )

    def _classify_curvature(self, kappa: float) -> GeometryType:
        """Classify geometry type based on curvature value."""
        if kappa > 0.2:
            return GeometryType.SPHERICAL
        elif kappa < -0.2:
            return GeometryType.HYPERBOLIC
        else:
            return GeometryType.EUCLIDEAN

    def _generate_analysis(
        self,
        edge_curvatures: Dict[Tuple[str, str], float],
        node_curvatures: Dict[str, float],
        statistics: Dict[str, float]
    ) -> str:
        """Generate human-readable analysis of curvature results."""
        lines = []

        lines.append("# Ollivier-Ricci Curvature Analysis")
        lines.append("")
        lines.append("## Overview")
        lines.append(f"- Analyzed {statistics['num_nodes']} nodes and {statistics['num_edges']} edges")
        lines.append(f"- Mean curvature: {statistics['mean']:.4f}")
        lines.append(f"- Curvature range: [{statistics['min']:.4f}, {statistics['max']:.4f}]")
        lines.append("")

        # Count geometry types
        num_spherical = sum(1 for k in edge_curvatures.values() if k > 0.2)
        num_hyperbolic = sum(1 for k in edge_curvatures.values() if k < -0.2)
        num_euclidean = len(edge_curvatures) - num_spherical - num_hyperbolic

        lines.append("## Geometry Distribution")
        lines.append(f"- **Spherical** (clusters, kappa > 0.2): {num_spherical} edges ({100*num_spherical/max(1,len(edge_curvatures)):.1f}%)")
        lines.append(f"- **Hyperbolic** (hierarchies, kappa < -0.2): {num_hyperbolic} edges ({100*num_hyperbolic/max(1,len(edge_curvatures)):.1f}%)")
        lines.append(f"- **Euclidean** (chains, -0.2 <= kappa <= 0.2): {num_euclidean} edges ({100*num_euclidean/max(1,len(edge_curvatures)):.1f}%)")
        lines.append("")

        # Identify hub nodes (highest average curvature)
        sorted_nodes = sorted(node_curvatures.items(), key=lambda x: x[1], reverse=True)
        lines.append("## Hub Nodes (Highest Curvature)")
        lines.append("These nodes are at the center of dense clusters:")
        for node, kappa in sorted_nodes[:5]:
            lines.append(f"- **{node}**: kappa = {kappa:.4f}")
        lines.append("")

        # Identify bridge nodes (lowest curvature)
        lines.append("## Bridge Nodes (Lowest Curvature)")
        lines.append("These nodes connect different regions:")
        for node, kappa in sorted_nodes[-5:]:
            lines.append(f"- **{node}**: kappa = {kappa:.4f}")
        lines.append("")

        # Most positive edges (dense clusters)
        sorted_edges = sorted(edge_curvatures.items(), key=lambda x: x[1], reverse=True)
        lines.append("## Strongest Cluster Edges (Most Positive)")
        for (s, t), kappa in sorted_edges[:5]:
            lines.append(f"- {s} <-> {t}: kappa = {kappa:.4f}")
        lines.append("")

        # Most negative edges (bottlenecks)
        lines.append("## Bridge Edges (Most Negative)")
        lines.append("These edges connect different geometric regions:")
        for (s, t), kappa in sorted_edges[-5:]:
            lines.append(f"- {s} <-> {t}: kappa = {kappa:.4f}")
        lines.append("")

        # Interpretation
        lines.append("## Interpretation")
        if statistics['mean'] > 0.1:
            lines.append("The graph is predominantly **spherical** (cluster-dominated).")
            lines.append("This suggests a knowledge domain with densely interconnected concepts.")
        elif statistics['mean'] < -0.1:
            lines.append("The graph is predominantly **hyperbolic** (hierarchy-dominated).")
            lines.append("This suggests a knowledge domain with tree-like structures.")
        else:
            lines.append("The graph has **mixed geometry** (euclidean average).")
            lines.append("This suggests a knowledge domain with both clusters and hierarchies.")

        return "\n".join(lines)

    def get_geometric_regions(self, threshold: float = 0.0) -> Dict[str, str]:
        """
        Classify each node into a geometric region based on its average curvature.

        Args:
            threshold: Curvature threshold for classification

        Returns:
            Dict mapping node name to geometry type string
        """
        result = self.compute_all_curvatures()
        regions = {}

        for node, kappa in result.node_curvatures.items():
            if kappa > threshold + 0.2:
                regions[node] = "spherical"
            elif kappa < threshold - 0.2:
                regions[node] = "hyperbolic"
            else:
                regions[node] = "euclidean"

        return regions


def compute_graph_curvature(category, alpha: float = 0.5) -> CurvatureResult:
    """
    Convenience function to compute curvature for a category.

    Args:
        category: Category with objects and morphisms
        alpha: Laziness parameter for random walk

    Returns:
        CurvatureResult with full analysis
    """
    computer = OllivierRicciCurvature(category, alpha=alpha)
    return computer.compute_all_curvatures()


# Example usage and testing
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from evaluation.physics_dataset import create_physics_dataset

    print("=" * 70)
    print("Ollivier-Ricci Curvature Analysis: Physics Dataset")
    print("=" * 70)
    print()

    # Create physics dataset
    store = create_physics_dataset()

    # Compute curvature
    result = compute_graph_curvature(store)

    # Print analysis
    print(result.analysis)

    print()
    print("=" * 70)
    print("Statistics Summary")
    print("=" * 70)
    for key, value in result.statistics.items():
        print(f"  {key}: {value}")
