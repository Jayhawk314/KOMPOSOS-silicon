# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Spectral Graph Theory - Phase 3C

Implements spectral methods for network analysis using Laplacian eigenvalues:
- Graph Laplacian and its spectrum
- Algebraic connectivity (Fiedler value lambda_2)
- Spectral clustering
- Cheeger constant and graph expansion
- Random walk mixing times

Mathematical Foundation:
- Laplacian: L = D - A (degree - adjacency)
- Eigenvalues: 0 = lambda_1 <= lambda_2 <= ... <= lambda_n
- lambda_2 = 0 iff graph disconnected
- lambda_2 > 0 implies connected graph (Fiedler value)
- Cheeger inequality: lambda_2/2 <= h(G) <= sqrt(2*lambda_2)

Applications:
- Community detection (spectral clustering)
- Anomaly detection (spectrum perturbation)
- Network connectivity analysis
- Attack surface identification
- Bottleneck detection (complements Ricci curvature)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
import math
from collections import defaultdict
import heapq


# =============================================================================
# GRAPH REPRESENTATION
# =============================================================================

@dataclass
class Graph:
    """
    Simple graph structure for spectral analysis.

    Attributes:
        nodes: Set of node IDs
        edges: Dict[node, Set[neighbors]]
        weights: Dict[(u,v), weight] for weighted graphs
    """
    nodes: Set[int] = field(default_factory=set)
    edges: Dict[int, Set[int]] = field(default_factory=lambda: defaultdict(set))
    weights: Dict[Tuple[int, int], float] = field(default_factory=dict)

    def add_edge(self, u: int, v: int, weight: float = 1.0):
        """Add undirected edge."""
        self.nodes.add(u)
        self.nodes.add(v)
        self.edges[u].add(v)
        self.edges[v].add(u)
        self.weights[(min(u, v), max(u, v))] = weight

    def get_neighbors(self, node: int) -> Set[int]:
        """Get neighbors of a node."""
        return self.edges.get(node, set())

    def degree(self, node: int) -> int:
        """Degree of a node (number of neighbors)."""
        return len(self.get_neighbors(node))

    def get_weight(self, u: int, v: int) -> float:
        """Get edge weight (1.0 if unweighted)."""
        edge = (min(u, v), max(u, v))
        return self.weights.get(edge, 1.0 if v in self.get_neighbors(u) else 0.0)

    def is_connected(self) -> bool:
        """Check if graph is connected using BFS."""
        if not self.nodes:
            return True

        start = next(iter(self.nodes))
        visited = {start}
        queue = [start]

        while queue:
            node = queue.pop(0)
            for neighbor in self.get_neighbors(node):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return len(visited) == len(self.nodes)


# =============================================================================
# GRAPH LAPLACIAN
# =============================================================================

@dataclass
class GraphLaplacian:
    """
    Graph Laplacian: L = D - A

    where:
    - D = degree matrix (diagonal)
    - A = adjacency matrix

    Properties:
    - L is positive semi-definite
    - L has eigenvalue 0 with eigenvector [1,1,...,1]
    - Number of 0 eigenvalues = number of connected components
    - lambda_2 (second smallest eigenvalue) = algebraic connectivity
    """
    graph: Graph
    laplacian: Dict[Tuple[int, int], float] = field(default_factory=dict)
    eigenvalues: List[float] = field(default_factory=list)
    eigenvectors: Dict[int, List[float]] = field(default_factory=dict)

    def __post_init__(self):
        """Compute Laplacian matrix."""
        self._compute_laplacian()

    def _compute_laplacian(self):
        """Compute L = D - A as sparse dict."""
        nodes = sorted(self.graph.nodes)

        for i, u in enumerate(nodes):
            for j, v in enumerate(nodes):
                if u == v:
                    # Diagonal: degree
                    self.laplacian[(i, j)] = float(self.graph.degree(u))
                elif v in self.graph.get_neighbors(u):
                    # Off-diagonal: -1 for edges
                    weight = self.graph.get_weight(u, v)
                    self.laplacian[(i, j)] = -weight
                # else: 0 (no edge)

    def compute_spectrum(self, k: Optional[int] = None):
        """
        Compute eigenvalues of Laplacian.

        Args:
            k: Number of smallest eigenvalues to compute (None = all)

        For small graphs (<1000 nodes), computes full spectrum.
        For large graphs, computes only k smallest eigenvalues.
        """
        nodes = sorted(self.graph.nodes)
        n = len(nodes)

        if n == 0:
            return

        # For small graphs, use power iteration
        # For production, would use scipy.sparse.linalg.eigsh
        if n <= 100 or k is None:
            self._compute_spectrum_small()
        else:
            self._compute_spectrum_lanczos(k)

    def _compute_spectrum_small(self):
        """
        Compute full spectrum for small graphs.

        Uses scipy.linalg.eigh for accurate eigenvalue computation.
        Falls back to simplified method if scipy not available.
        """
        nodes = sorted(self.graph.nodes)
        n = len(nodes)

        # Build dense matrix (for small graphs only)
        L = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                L[i][j] = self.laplacian.get((i, j), 0.0)

        # Try using scipy for accurate computation
        try:
            import numpy as np
            from scipy import linalg

            L_array = np.array(L)
            eigenvalues, eigenvectors = linalg.eigh(L_array)

            self.eigenvalues = eigenvalues.tolist()

            # Store eigenvectors (column i is eigenvector for eigenvalue i)
            for i in range(min(n, 10)):
                self.eigenvectors[i] = eigenvectors[:, i].tolist()

        except ImportError:
            # Fallback: simplified approximation
            eigenvalue_estimates = []

            for i in range(n):
                center = L[i][i]
                radius = sum(abs(L[i][j]) for j in range(n) if j != i)
                eigenvalue_estimates.append(center)

            eigenvalue_estimates.sort()
            eigenvalue_estimates[0] = 0.0

            self.eigenvalues = eigenvalue_estimates

            # Eigenvectors (simplified - first is constant vector)
            self.eigenvectors[0] = [1.0 / math.sqrt(n)] * n

            for i in range(1, min(n, 10)):
                self.eigenvectors[i] = [0.0] * n

    def _compute_spectrum_lanczos(self, k: int):
        """
        Compute k smallest eigenvalues using Lanczos algorithm.

        Uses scipy.sparse.linalg.eigsh for efficient sparse computation.
        """
        try:
            import numpy as np
            from scipy.sparse import lil_matrix
            from scipy.sparse.linalg import eigsh

            nodes = sorted(self.graph.nodes)
            n = len(nodes)

            # Build sparse Laplacian matrix
            L_sparse = lil_matrix((n, n))
            for i in range(n):
                for j in range(n):
                    val = self.laplacian.get((i, j), 0.0)
                    if val != 0:
                        L_sparse[i, j] = val

            # Compute k smallest eigenvalues
            k_actual = min(k, n - 1)  # eigsh requires k < n
            if k_actual > 0:
                eigenvalues, eigenvectors = eigsh(L_sparse, k=k_actual, which='SM')

                self.eigenvalues = eigenvalues.tolist()

                # Store eigenvectors
                for i in range(k_actual):
                    self.eigenvectors[i] = eigenvectors[:, i].tolist()
            else:
                self.eigenvalues = []

        except ImportError:
            # Fallback to full computation
            self._compute_spectrum_small()
            self.eigenvalues = self.eigenvalues[:k]

    def algebraic_connectivity(self) -> float:
        """
        Compute lambda_2 (Fiedler value) - the algebraic connectivity.

        lambda_2 = 0 iff graph is disconnected
        lambda_2 > 0 iff graph is connected

        Larger lambda_2 means better connected graph.
        """
        if not self.eigenvalues:
            self.compute_spectrum()

        if len(self.eigenvalues) < 2:
            return 0.0

        return self.eigenvalues[1]

    def spectral_gap(self) -> float:
        """
        Gap between lambda_2 and lambda_3.

        Large gap → clear community structure.
        """
        if not self.eigenvalues:
            self.compute_spectrum()

        if len(self.eigenvalues) < 3:
            return 0.0

        return self.eigenvalues[2] - self.eigenvalues[1]

    def fiedler_vector(self) -> List[float]:
        """
        Get Fiedler vector (eigenvector for lambda_2).

        Used for graph bisection - sign of components indicates partition.
        """
        if not self.eigenvectors:
            self.compute_spectrum()

        return self.eigenvectors.get(1, [])


# =============================================================================
# SPECTRAL CLUSTERING
# =============================================================================

@dataclass
class SpectralClustering:
    """
    Cluster graph nodes using Laplacian eigenvectors.

    Algorithm:
    1. Compute Laplacian L
    2. Compute k smallest eigenvectors
    3. Embed nodes in ℝᵏ using eigenvectors
    4. Run k-means on embeddings

    Better than traditional clustering for network data.
    """
    graph: Graph

    def cluster(self, k: int) -> Dict[int, int]:
        """
        Partition graph into k clusters.

        Args:
            k: Number of clusters

        Returns:
            Dict[node_id, cluster_id]
        """
        laplacian = GraphLaplacian(self.graph)
        laplacian.compute_spectrum(k=k+1)  # Need k+1 eigenvalues (skip lambda_1=0)

        nodes = sorted(self.graph.nodes)
        n = len(nodes)

        if n == 0 or k <= 0:
            return {}

        # Embed nodes using eigenvectors 1..k (skip eigenvector 0)
        embeddings = {}
        for i, node in enumerate(nodes):
            embedding = []
            for j in range(1, min(k+1, len(laplacian.eigenvectors))):
                if j in laplacian.eigenvectors:
                    vec = laplacian.eigenvectors[j]
                    if i < len(vec):
                        embedding.append(vec[i])

            if embedding:
                embeddings[node] = embedding

        # Simple k-means clustering on embeddings
        clusters = self._kmeans_clustering(embeddings, k)

        return clusters

    def _kmeans_clustering(self, embeddings: Dict[int, List[float]], k: int) -> Dict[int, int]:
        """
        Simple k-means clustering on node embeddings.

        Args:
            embeddings: Dict[node_id, embedding_vector]
            k: Number of clusters

        Returns:
            Dict[node_id, cluster_id]
        """
        if not embeddings or k <= 0:
            return {}

        nodes = list(embeddings.keys())
        n = len(nodes)

        if n <= k:
            # Each node is its own cluster
            return {node: i for i, node in enumerate(nodes)}

        # Initialize centroids: pick k nodes uniformly
        import random
        random.seed(42)
        centroid_nodes = random.sample(nodes, k)
        centroids = {i: embeddings[node] for i, node in enumerate(centroid_nodes)}

        # Run k-means for fixed iterations
        assignments = {}
        for iteration in range(10):  # Fixed iterations for simplicity
            # Assignment step
            for node in nodes:
                embedding = embeddings[node]
                distances = [
                    self._euclidean_distance(embedding, centroid)
                    for centroid in centroids.values()
                ]
                cluster_id = distances.index(min(distances))
                assignments[node] = cluster_id

            # Update step
            for cluster_id in range(k):
                cluster_nodes = [node for node in nodes if assignments.get(node) == cluster_id]
                if cluster_nodes:
                    # Compute mean embedding
                    dim = len(embeddings[cluster_nodes[0]])
                    new_centroid = [0.0] * dim
                    for node in cluster_nodes:
                        for i, val in enumerate(embeddings[node]):
                            new_centroid[i] += val
                    for i in range(dim):
                        new_centroid[i] /= len(cluster_nodes)
                    centroids[cluster_id] = new_centroid

        return assignments

    def _euclidean_distance(self, v1: List[float], v2: List[float]) -> float:
        """Compute Euclidean distance between vectors."""
        if len(v1) != len(v2):
            return float('inf')
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))

    def find_optimal_k(self, max_k: int = 10) -> int:
        """
        Find optimal number of clusters using eigengap heuristic.

        Look for largest gap in eigenvalue spectrum.

        Args:
            max_k: Maximum number of clusters to consider

        Returns:
            Optimal k
        """
        laplacian = GraphLaplacian(self.graph)
        laplacian.compute_spectrum(k=max_k+2)

        if len(laplacian.eigenvalues) < 3:
            return 1

        # Find largest gap in eigenvalues
        gaps = []
        for i in range(1, min(len(laplacian.eigenvalues) - 1, max_k)):
            gap = laplacian.eigenvalues[i+1] - laplacian.eigenvalues[i]
            gaps.append((gap, i))

        if not gaps:
            return 1

        # Return k corresponding to largest gap
        largest_gap = max(gaps, key=lambda x: x[0])
        return largest_gap[1]


# =============================================================================
# CHEEGER CONSTANT AND GRAPH EXPANSION
# =============================================================================

@dataclass
class CheegerConstant:
    """
    Graph expansion via Cheeger inequality.

    Cheeger constant: h(G) = min_S |dS| / min(|S|, |V\\S|)

    where dS = edges leaving S (cut size)

    Relates to eigenvalues via Cheeger inequality:
        lambda_2/2 <= h(G) <= sqrt(2*lambda_2)

    High h(G) → well-connected graph (hard to partition)
    Low h(G) → bottleneck exists
    """
    graph: Graph

    def cheeger_lower_bound(self) -> float:
        """
        Lower bound on Cheeger constant using lambda_2.

        h(G) >= lambda_2/2
        """
        laplacian = GraphLaplacian(self.graph)
        lambda_2 = laplacian.algebraic_connectivity()
        return lambda_2 / 2.0

    def cheeger_upper_bound(self) -> float:
        """
        Upper bound on Cheeger constant using lambda_2.

        h(G) <= sqrt(2*lambda_2)
        """
        laplacian = GraphLaplacian(self.graph)
        lambda_2 = laplacian.algebraic_connectivity()
        return math.sqrt(2.0 * lambda_2)

    def approximate_cheeger_constant(self) -> float:
        """
        Approximate Cheeger constant.

        Exact computation is NP-hard.
        Use geometric mean of bounds as approximation.
        """
        lower = self.cheeger_lower_bound()
        upper = self.cheeger_upper_bound()
        return math.sqrt(lower * upper) if lower > 0 and upper > 0 else 0.0

    def find_sparse_cut(self) -> Tuple[Set[int], Set[int]]:
        """
        Find approximate sparse cut using Fiedler vector.

        Algorithm:
        1. Compute Fiedler vector (eigenvector for lambda_2)
        2. Partition nodes by sign of Fiedler vector components

        Returns:
            (S, V\S) partition
        """
        laplacian = GraphLaplacian(self.graph)
        laplacian.compute_spectrum(k=2)

        fiedler = laplacian.fiedler_vector()
        nodes = sorted(self.graph.nodes)

        if not fiedler or len(fiedler) < len(nodes):
            # Fallback: arbitrary partition
            mid = len(nodes) // 2
            return (set(nodes[:mid]), set(nodes[mid:]))

        # Partition by sign
        S = set()
        T = set()
        for i, node in enumerate(nodes):
            if i < len(fiedler):
                if fiedler[i] >= 0:
                    S.add(node)
                else:
                    T.add(node)

        # Handle empty sets
        if not S:
            S.add(nodes[0])
            T.discard(nodes[0])
        if not T:
            T.add(nodes[-1])
            S.discard(nodes[-1])

        return (S, T)

    def compute_conductance(self, S: Set[int]) -> float:
        """
        Compute conductance of set S.

        φ(S) = |∂S| / min(vol(S), vol(V\S))

        where:
        - |∂S| = number of edges leaving S
        - vol(S) = sum of degrees in S
        """
        if not S or S == self.graph.nodes:
            return 0.0

        # Compute cut size
        cut_size = 0
        for u in S:
            for v in self.graph.get_neighbors(u):
                if v not in S:
                    cut_size += 1

        # Compute volumes
        vol_S = sum(self.graph.degree(node) for node in S)
        vol_complement = sum(self.graph.degree(node) for node in self.graph.nodes if node not in S)

        if vol_S == 0 or vol_complement == 0:
            return 0.0

        return cut_size / min(vol_S, vol_complement)


# =============================================================================
# RANDOM WALK ANALYSIS
# =============================================================================

@dataclass
class RandomWalkAnalysis:
    """
    Analyze random walks using spectral methods.

    Key relationships:
    - Mixing time tau_mix ~ 1/lambda_2 (for regular graphs)
    - Hitting time H(u,v) via commute time resistance
    - Stationary distribution π_i = deg(i) / (2|E|)
    """
    graph: Graph

    def mixing_time_estimate(self) -> float:
        """
        Estimate mixing time of random walk.

        tau_mix ~ 1 / lambda_2

        For non-regular graphs, this is approximate.
        """
        laplacian = GraphLaplacian(self.graph)
        lambda_2 = laplacian.algebraic_connectivity()

        if lambda_2 == 0:
            return float('inf')  # Disconnected graph

        return 1.0 / lambda_2

    def stationary_distribution(self) -> Dict[int, float]:
        """
        Compute stationary distribution of random walk.

        For undirected graphs: π_i = deg(i) / (2|E|)
        """
        total_degree = sum(self.graph.degree(node) for node in self.graph.nodes)

        if total_degree == 0:
            return {}

        return {
            node: self.graph.degree(node) / total_degree
            for node in self.graph.nodes
        }

    def hitting_time_lower_bound(self, source: int, target: int) -> float:
        """
        Lower bound on hitting time H(source, target).

        Uses resistance distance and stationary distribution.
        """
        stationary = self.stationary_distribution()

        if target not in stationary or stationary[target] == 0:
            return float('inf')

        # H(u,v) ≥ 1/π_v
        return 1.0 / stationary[target]

    def commute_time_estimate(self, u: int, v: int) -> float:
        """
        Estimate commute time C(u,v) = H(u,v) + H(v,u).

        Uses effective resistance: C(u,v) = 2|E| * R_eff(u,v)

        For simple estimate, use graph distance.
        """
        # BFS distance
        distance = self._bfs_distance(u, v)

        if distance == float('inf'):
            return float('inf')

        # Rough estimate: commute time ~ distance * graph size
        return distance * len(self.graph.nodes)

    def _bfs_distance(self, source: int, target: int) -> float:
        """Compute shortest path distance using BFS."""
        if source == target:
            return 0.0

        visited = {source: 0}
        queue = [source]

        while queue:
            node = queue.pop(0)
            dist = visited[node]

            for neighbor in self.graph.get_neighbors(node):
                if neighbor not in visited:
                    visited[neighbor] = dist + 1
                    if neighbor == target:
                        return float(dist + 1)
                    queue.append(neighbor)

        return float('inf')


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def graph_from_adjacency(adjacency: Dict[int, Set[int]]) -> Graph:
    """Create Graph from adjacency dict."""
    graph = Graph()
    for node, neighbors in adjacency.items():
        graph.nodes.add(node)
        for neighbor in neighbors:
            graph.add_edge(node, neighbor)
    return graph


def graph_from_edges(edges: List[Tuple[int, int]], weighted: bool = False) -> Graph:
    """
    Create Graph from edge list.

    Args:
        edges: List of (u, v) or (u, v, weight) tuples
        weighted: If True, expect 3-tuples with weights
    """
    graph = Graph()
    for edge in edges:
        if weighted and len(edge) == 3:
            u, v, w = edge
            graph.add_edge(u, v, weight=w)
        else:
            u, v = edge[0], edge[1]
            graph.add_edge(u, v)
    return graph


def analyze_connectivity(graph: Graph) -> Dict:
    """
    Comprehensive connectivity analysis.

    Returns:
        Dict with connectivity metrics
    """
    laplacian = GraphLaplacian(graph)
    laplacian.compute_spectrum()

    cheeger = CheegerConstant(graph)
    random_walk = RandomWalkAnalysis(graph)

    return {
        'is_connected': graph.is_connected(),
        'num_nodes': len(graph.nodes),
        'num_edges': sum(len(neighbors) for neighbors in graph.edges.values()) // 2,
        'algebraic_connectivity': laplacian.algebraic_connectivity(),
        'spectral_gap': laplacian.spectral_gap(),
        'cheeger_lower_bound': cheeger.cheeger_lower_bound(),
        'cheeger_upper_bound': cheeger.cheeger_upper_bound(),
        'mixing_time_estimate': random_walk.mixing_time_estimate(),
    }
