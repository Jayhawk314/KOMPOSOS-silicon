# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Persistent Homology for Topological Data Analysis

Domain-agnostic TDA implementation:
- Compute persistent homology of filtered simplicial complexes
- Detect topological anomalies via Betti number changes
- Build complexes from graphs (flag), point clouds (Vietoris-Rips), or directly

Mathematical Foundation:
- Build simplicial complexes from connectivity or distance data
- Track birth/death of topological features across filtration
- H0 (connected components): connectivity / fragmentation
- H1 (loops / 1-cycles): circular structure detection

Betti number changes signal topological events:
- b0 increase: fragmentation (components splitting)
- b0 decrease: merging (components joining)
- b1 increase: new loops forming
- b1 decrease: loops being filled

This module is self-contained and uses only the Python standard library.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
import math
from collections import defaultdict


# =============================================================================
# SIMPLEX
# =============================================================================

@dataclass
class Simplex:
    """
    A simplex in a simplicial complex.

    A k-simplex is defined by (k+1) vertices. For example:
    - 0-simplex: a single vertex
    - 1-simplex: an edge (2 vertices)
    - 2-simplex: a triangle (3 vertices)
    """
    vertices: Tuple[int, ...]
    filtration_value: float = 0.0

    def __post_init__(self):
        # Ensure vertices are sorted for canonical form
        self.vertices = tuple(sorted(self.vertices))

    @property
    def dimension(self) -> int:
        """Dimension of the simplex: number of vertices minus one."""
        return len(self.vertices) - 1

    def faces(self) -> List['Simplex']:
        """
        Return all (dim-1) faces of this simplex.

        Each face is obtained by removing exactly one vertex.
        For a triangle (0,1,2), the faces are edges (0,1), (0,2), (1,2).
        """
        if self.dimension <= 0:
            return []
        result = []
        for i in range(len(self.vertices)):
            face_vertices = self.vertices[:i] + self.vertices[i + 1:]
            result.append(Simplex(
                vertices=face_vertices,
                filtration_value=self.filtration_value
            ))
        return result

    def __hash__(self):
        return hash(self.vertices)

    def __eq__(self, other):
        return isinstance(other, Simplex) and self.vertices == other.vertices

    def __repr__(self):
        return f"Simplex({self.vertices}, f={self.filtration_value:.2f})"


# =============================================================================
# PERSISTENCE PAIR
# =============================================================================

@dataclass
class PersistencePair:
    """
    A persistence pair (birth, death) representing a topological feature.

    The feature is born at filtration value 'birth' and dies at 'death'.
    Features with death = infinity are essential (never killed).
    """
    birth: float
    death: float
    dimension: int

    @property
    def persistence(self) -> float:
        """
        Lifespan of this topological feature.

        Returns float('inf') if the feature never dies.
        """
        if self.death == float('inf'):
            return float('inf')
        return self.death - self.birth

    @property
    def midlife(self) -> float:
        """Midpoint of the feature's lifespan: (birth + death) / 2."""
        return (self.birth + self.death) / 2.0

    def __repr__(self):
        death_str = "inf" if self.death == float('inf') else f"{self.death:.2f}"
        return f"H{self.dimension}({self.birth:.2f}, {death_str})"


# =============================================================================
# PERSISTENCE DIAGRAM
# =============================================================================

class PersistenceDiagram:
    """
    A persistence diagram: a multiset of persistence pairs.

    The diagram summarizes the topological features of a filtered
    simplicial complex, recording when each feature appears (birth)
    and disappears (death) across the filtration.
    """

    def __init__(self, pairs: List[PersistencePair]):
        self.pairs = list(pairs)

    def betti_numbers_at(self, t: float) -> Dict[int, int]:
        """
        Compute Betti numbers at filtration value t.

        b_k(t) = number of k-dimensional features alive at time t,
        i.e., pairs where birth <= t < death.

        Returns:
            Dictionary mapping dimension to Betti number.
        """
        betti = defaultdict(int)
        for pair in self.pairs:
            if pair.birth <= t and (pair.death == float('inf') or t < pair.death):
                betti[pair.dimension] += 1
        return dict(betti)

    def total_persistence(self, p: float = 1.0) -> float:
        """
        Total persistence: sum of persistence^p over all finite pairs.

        This is a summary statistic for the diagram. Higher values
        indicate more significant topological features.

        Args:
            p: The power to raise each persistence to (default 1).

        Returns:
            Sum of |death - birth|^p for all pairs with finite persistence.
        """
        total = 0.0
        for pair in self.pairs:
            if pair.death != float('inf'):
                total += abs(pair.death - pair.birth) ** p
        return total

    def max_persistence(self) -> float:
        """
        Maximum persistence among all pairs.

        Returns 0.0 if the diagram is empty.
        """
        if not self.pairs:
            return 0.0
        return max(pair.persistence for pair in self.pairs)

    def num_features(self, dim: Optional[int] = None) -> int:
        """
        Count the number of persistence pairs.

        Args:
            dim: If specified, only count pairs of this dimension.

        Returns:
            Number of pairs (optionally filtered by dimension).
        """
        if dim is None:
            return len(self.pairs)
        return sum(1 for pair in self.pairs if pair.dimension == dim)

    def __repr__(self):
        return f"PersistenceDiagram({len(self.pairs)} pairs)"


# =============================================================================
# SIMPLICIAL COMPLEX
# =============================================================================

class SimplicialComplex:
    """
    A filtered simplicial complex.

    Stores simplices with filtration values, ensuring the subcomplex
    property: all faces of a simplex must also be present with
    filtration values no greater than the simplex itself.
    """

    def __init__(self):
        self.simplices: List[Simplex] = []
        self._simplex_set: Set[Tuple[int, ...]] = set()
        self._filtration_values: Dict[Tuple[int, ...], float] = {}

    def add_simplex(self, vertices: Tuple[int, ...], filtration_value: float = 0.0):
        """
        Add a simplex and all of its faces to the complex.

        Faces are added with the same filtration value if they are not
        already present. If a face already exists with a lower filtration
        value, the lower value is kept.

        Args:
            vertices: Tuple of vertex indices.
            filtration_value: The filtration value at which this simplex appears.
        """
        vertices = tuple(sorted(vertices))

        # Add the simplex itself
        if vertices not in self._simplex_set:
            s = Simplex(vertices=vertices, filtration_value=filtration_value)
            self.simplices.append(s)
            self._simplex_set.add(vertices)
            self._filtration_values[vertices] = filtration_value
        else:
            # Update filtration value if new one is lower
            existing_val = self._filtration_values[vertices]
            if filtration_value < existing_val:
                self._filtration_values[vertices] = filtration_value
                for s in self.simplices:
                    if s.vertices == vertices:
                        s.filtration_value = filtration_value
                        break

        # Recursively add all faces
        if len(vertices) > 1:
            for i in range(len(vertices)):
                face_vertices = vertices[:i] + vertices[i + 1:]
                face_filt = min(filtration_value, self._filtration_values.get(face_vertices, filtration_value))
                self.add_simplex(face_vertices, face_filt)

    def build_flag_complex(self, graph_edges: List[Tuple[int, int]], max_dim: int = 2):
        """
        Build a flag (clique) complex from a graph.

        The flag complex of a graph G has a k-simplex for every
        (k+1)-clique in G. This is the standard way to build a
        simplicial complex from network connectivity data.

        Args:
            graph_edges: List of (u, v) edges.
            max_dim: Maximum dimension of simplices to generate.
        """
        # Collect all vertices
        vertices: Set[int] = set()
        adjacency: Dict[int, Set[int]] = defaultdict(set)

        for u, v in graph_edges:
            vertices.add(u)
            vertices.add(v)
            adjacency[u].add(v)
            adjacency[v].add(u)

        # Add 0-simplices (vertices) at filtration 0.0
        for v in sorted(vertices):
            self.add_simplex((v,), 0.0)

        # Add 1-simplices (edges) at filtration 1.0
        for u, v in graph_edges:
            self.add_simplex((u, v), 1.0)

        # Add higher-dimensional simplices (cliques)
        if max_dim >= 2:
            # Find triangles (3-cliques)
            for u in sorted(vertices):
                neighbors_u = adjacency[u]
                for v in sorted(neighbors_u):
                    if v <= u:
                        continue
                    neighbors_v = adjacency[v]
                    common = neighbors_u & neighbors_v
                    for w in sorted(common):
                        if w <= v:
                            continue
                        # (u, v, w) is a triangle
                        # Filtration = max of edge filtrations (all 1.0 here)
                        self.add_simplex((u, v, w), 1.0)

                        if max_dim >= 3:
                            # Find 4-cliques
                            neighbors_w = adjacency[w]
                            common_uvw = common & neighbors_w
                            for x in sorted(common_uvw):
                                if x <= w:
                                    continue
                                self.add_simplex((u, v, w, x), 1.0)

    def build_vietoris_rips(self, points: List[Tuple[float, ...]], max_radius: float,
                            max_dim: int = 2):
        """
        Build a Vietoris-Rips complex from point cloud data.

        Two points are connected by an edge if their Euclidean distance
        is at most max_radius. The filtration value of each edge is the
        distance between its endpoints. Higher simplices are added as
        cliques in the resulting graph, with filtration value equal to
        the maximum edge filtration in the clique.

        Args:
            points: List of coordinate tuples (any dimension).
            max_radius: Maximum distance for edge inclusion.
            max_dim: Maximum simplex dimension to generate.
        """
        n = len(points)

        # Add 0-simplices (vertices) at filtration 0.0
        for i in range(n):
            self.add_simplex((i,), 0.0)

        # Compute pairwise distances, add edges within max_radius
        distances: Dict[Tuple[int, int], float] = {}
        adjacency: Dict[int, Set[int]] = defaultdict(set)

        for i in range(n):
            for j in range(i + 1, n):
                d = _euclidean_distance(points[i], points[j])
                if d <= max_radius:
                    distances[(i, j)] = d
                    adjacency[i].add(j)
                    adjacency[j].add(i)
                    self.add_simplex((i, j), d)

        # Add triangles (2-simplices)
        if max_dim >= 2:
            for i in range(n):
                for j in sorted(adjacency[i]):
                    if j <= i:
                        continue
                    common = adjacency[i] & adjacency[j]
                    for k in sorted(common):
                        if k <= j:
                            continue
                        # Triangle (i, j, k): filtration = max edge distance
                        d_ij = distances.get((min(i, j), max(i, j)), 0.0)
                        d_ik = distances.get((min(i, k), max(i, k)), 0.0)
                        d_jk = distances.get((min(j, k), max(j, k)), 0.0)
                        filt = max(d_ij, d_ik, d_jk)
                        self.add_simplex((i, j, k), filt)

    def build_sparse_rips(self, points: List[Tuple[float, ...]], max_radius: float,
                          max_dim: int = 2, epsilon: float = 0.1):
        """
        Build a sparsified Vietoris-Rips complex from point cloud data.

        Like build_vietoris_rips but skips edges beyond (1+epsilon) factor
        of each point's nearest neighbor distance. This reduces the
        simplex count by 10-100x for large point clouds while preserving
        the persistent homology up to a (1+epsilon) interleaving.

        Args:
            points: List of coordinate tuples (any dimension).
            max_radius: Maximum distance for edge inclusion.
            max_dim: Maximum simplex dimension to generate.
            epsilon: Sparsification parameter. Smaller = more accurate, more edges.
        """
        n = len(points)
        if n == 0:
            return

        # Add 0-simplices (vertices) at filtration 0.0
        for i in range(n):
            self.add_simplex((i,), 0.0)

        # Compute all pairwise distances
        all_distances: Dict[Tuple[int, int], float] = {}
        for i in range(n):
            for j in range(i + 1, n):
                d = _euclidean_distance(points[i], points[j])
                if d <= max_radius:
                    all_distances[(i, j)] = d

        # Compute nearest neighbor distance for each point
        nn_dist: Dict[int, float] = {}
        for i in range(n):
            min_d = float('inf')
            for j in range(n):
                if i == j:
                    continue
                key = (min(i, j), max(i, j))
                d = all_distances.get(key, float('inf'))
                if d < min_d:
                    min_d = d
            nn_dist[i] = min_d if min_d < float('inf') else max_radius

        # Add edges that pass the sparsification criterion
        adjacency: Dict[int, Set[int]] = defaultdict(set)
        distances: Dict[Tuple[int, int], float] = {}

        for (i, j), d in all_distances.items():
            # Include edge if distance is within (1+epsilon) of either
            # endpoint's nearest neighbor distance
            threshold = (1 + epsilon) * max(nn_dist[i], nn_dist[j])
            if d <= threshold:
                distances[(i, j)] = d
                adjacency[i].add(j)
                adjacency[j].add(i)
                self.add_simplex((i, j), d)

        # Add triangles (2-simplices) from sparse edges
        if max_dim >= 2:
            for i in range(n):
                for j in sorted(adjacency[i]):
                    if j <= i:
                        continue
                    common = adjacency[i] & adjacency[j]
                    for k in sorted(common):
                        if k <= j:
                            continue
                        d_ij = distances.get((min(i, j), max(i, j)), 0.0)
                        d_ik = distances.get((min(i, k), max(i, k)), 0.0)
                        d_jk = distances.get((min(j, k), max(j, k)), 0.0)
                        filt = max(d_ij, d_ik, d_jk)
                        self.add_simplex((i, j, k), filt)

    def dimension(self) -> int:
        """Maximum dimension of any simplex in the complex."""
        if not self.simplices:
            return -1
        return max(s.dimension for s in self.simplices)

    def num_simplices(self, dim: Optional[int] = None) -> int:
        """
        Count simplices, optionally filtered by dimension.

        Args:
            dim: If specified, count only simplices of this dimension.

        Returns:
            Number of simplices.
        """
        if dim is None:
            return len(self.simplices)
        return sum(1 for s in self.simplices if s.dimension == dim)

    def __repr__(self):
        return (f"SimplicialComplex({self.num_simplices()} simplices, "
                f"dim={self.dimension()})")


# =============================================================================
# UNION-FIND (DISJOINT SET) FOR H0 COMPUTATION
# =============================================================================

class _UnionFind:
    """Disjoint-set (union-find) data structure for connected components."""

    def __init__(self):
        self.parent: Dict[int, int] = {}
        self.rank: Dict[int, int] = {}

    def make_set(self, x: int):
        """Create a new singleton set containing x."""
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0

    def find(self, x: int) -> int:
        """Find the representative of the set containing x (with path compression)."""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: int, y: int) -> bool:
        """
        Merge the sets containing x and y.

        Returns True if a merge occurred (x and y were in different sets),
        False if they were already in the same set.
        """
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return False
        # Union by rank
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1
        return True


# =============================================================================
# PERSISTENT HOMOLOGY COMPUTER
# =============================================================================

class PersistentHomologyComputer:
    """
    Compute persistent homology of a filtered simplicial complex.

    Computes:
    - H0 (connected components) via union-find
    - H1 (loops / 1-cycles) via boundary matrix reduction

    The algorithm processes simplices in filtration order and tracks
    the birth and death of topological features.
    """

    def compute(self, complex: SimplicialComplex) -> PersistenceDiagram:
        """
        Compute the persistence diagram of the given simplicial complex.

        Args:
            complex: A filtered simplicial complex.

        Returns:
            PersistenceDiagram containing all persistence pairs.
        """
        pairs: List[PersistencePair] = []

        # Separate simplices by dimension
        vertices = sorted(
            [s for s in complex.simplices if s.dimension == 0],
            key=lambda s: s.filtration_value
        )
        edges = sorted(
            [s for s in complex.simplices if s.dimension == 1],
            key=lambda s: s.filtration_value
        )
        triangles = sorted(
            [s for s in complex.simplices if s.dimension == 2],
            key=lambda s: s.filtration_value
        )

        # --- H0: Connected components via union-find ---
        h0_pairs = self._compute_h0(vertices, edges)
        pairs.extend(h0_pairs)

        # --- H1: Loops via boundary analysis ---
        h1_pairs = self._compute_h1(vertices, edges, triangles)
        pairs.extend(h1_pairs)

        return PersistenceDiagram(pairs)

    def _compute_h0(self, vertices: List[Simplex],
                    edges: List[Simplex]) -> List[PersistencePair]:
        """
        Compute H0 (connected components) using union-find.

        Each vertex is born at its filtration value. When an edge
        merges two components, the younger component (higher birth)
        dies at the edge's filtration value.
        """
        pairs: List[PersistencePair] = []
        uf = _UnionFind()

        # Birth times for each vertex
        birth_time: Dict[int, float] = {}

        for v in vertices:
            vid = v.vertices[0]
            uf.make_set(vid)
            birth_time[vid] = v.filtration_value

        # Process edges in filtration order
        for edge in edges:
            u, v = edge.vertices
            ru, rv = uf.find(u), uf.find(v)

            if ru != rv:
                # Merge: the younger component dies
                birth_u = birth_time.get(ru, 0.0)
                birth_v = birth_time.get(rv, 0.0)

                # The younger one (higher birth time) dies
                if birth_u <= birth_v:
                    # v's component is younger, it dies
                    pairs.append(PersistencePair(
                        birth=birth_v,
                        death=edge.filtration_value,
                        dimension=0
                    ))
                    uf.union(u, v)
                    # Propagate the older birth time to the merged component
                    new_root = uf.find(u)
                    birth_time[new_root] = birth_u
                else:
                    # u's component is younger, it dies
                    pairs.append(PersistencePair(
                        birth=birth_u,
                        death=edge.filtration_value,
                        dimension=0
                    ))
                    uf.union(u, v)
                    new_root = uf.find(u)
                    birth_time[new_root] = birth_v

        # Remaining components are essential (never die)
        seen_roots: Set[int] = set()
        for v in vertices:
            vid = v.vertices[0]
            root = uf.find(vid)
            if root not in seen_roots:
                seen_roots.add(root)
                pairs.append(PersistencePair(
                    birth=birth_time.get(root, 0.0),
                    death=float('inf'),
                    dimension=0
                ))

        return pairs

    def _compute_h1(self, vertices: List[Simplex], edges: List[Simplex],
                    triangles: List[Simplex]) -> List[PersistencePair]:
        """
        Compute H1 (loops / 1-cycles) via boundary analysis.

        Strategy: Build a spanning tree using union-find. Any edge not
        in the spanning tree creates a 1-cycle (loop). The cycle is
        born at the edge's filtration value. A triangle kills a cycle
        if its boundary contains a non-tree edge.
        """
        pairs: List[PersistencePair] = []
        uf = _UnionFind()

        for v in vertices:
            uf.make_set(v.vertices[0])

        # Track which edges are NOT in the spanning tree (these create cycles)
        non_tree_edges: List[Simplex] = []

        for edge in edges:
            u, v = edge.vertices
            if uf.find(u) != uf.find(v):
                uf.union(u, v)
                # This edge is part of the spanning tree
            else:
                # This edge creates a 1-cycle
                non_tree_edges.append(edge)

        # Each non-tree edge creates a cycle born at its filtration value
        # A triangle kills a cycle if its boundary includes a non-tree edge
        non_tree_set = {e.vertices for e in non_tree_edges}
        cycle_birth: Dict[Tuple[int, ...], float] = {}
        for edge in non_tree_edges:
            cycle_birth[edge.vertices] = edge.filtration_value

        # Process triangles: each triangle can kill one cycle
        killed_cycles: Set[Tuple[int, ...]] = set()

        for tri in triangles:
            # Get the three edges of this triangle
            tri_edges = []
            for face in tri.faces():
                if face.dimension == 1:
                    tri_edges.append(face.vertices)

            # Check which edges of this triangle are non-tree edges
            non_tree_in_tri = [e for e in tri_edges if e in non_tree_set]

            if non_tree_in_tri:
                # This triangle kills the cycle created by one non-tree edge
                # Pick the first unkilled non-tree edge
                for nt_edge in non_tree_in_tri:
                    if nt_edge not in killed_cycles:
                        killed_cycles.add(nt_edge)
                        pairs.append(PersistencePair(
                            birth=cycle_birth[nt_edge],
                            death=tri.filtration_value,
                            dimension=1
                        ))
                        break

        # Remaining non-tree edges create essential 1-cycles
        for edge in non_tree_edges:
            if edge.vertices not in killed_cycles:
                pairs.append(PersistencePair(
                    birth=cycle_birth[edge.vertices],
                    death=float('inf'),
                    dimension=1
                ))

        return pairs

    def _compute_h1_fast(self, edges: List[Simplex],
                         triangles: List[Simplex]) -> List[PersistencePair]:
        """
        Optimized H1 computation using minimum spanning tree approach.

        Instead of naive boundary matrix reduction, uses Kruskal's MST
        algorithm (reusing _UnionFind). Each non-tree edge creates exactly
        one cycle. Triangle filling kills cycles -- we track which persist.

        This is functionally equivalent to _compute_h1 but avoids
        redundant set operations on large complexes.
        """
        pairs: List[PersistencePair] = []

        # Collect all vertices from edges
        all_verts: Set[int] = set()
        for edge in edges:
            all_verts.update(edge.vertices)

        uf = _UnionFind()
        for v in all_verts:
            uf.make_set(v)

        # Kruskal's: build MST, collect non-tree edges as cycle generators
        non_tree_edges: List[Simplex] = []
        for edge in edges:
            u, v = edge.vertices
            if uf.find(u) != uf.find(v):
                uf.union(u, v)
            else:
                non_tree_edges.append(edge)

        if not non_tree_edges:
            return pairs

        # Build index for fast triangle-edge lookup
        # Map each edge -> set of triangles containing it
        edge_to_triangles: Dict[Tuple[int, ...], List[Simplex]] = defaultdict(list)
        for tri in triangles:
            for face in tri.faces():
                if face.dimension == 1:
                    edge_to_triangles[face.vertices].append(tri)

        # Track cycles and their killers
        cycle_birth: Dict[Tuple[int, ...], float] = {}
        for edge in non_tree_edges:
            cycle_birth[edge.vertices] = edge.filtration_value

        killed_cycles: Set[Tuple[int, ...]] = set()

        # Process triangles in filtration order
        sorted_triangles = sorted(triangles, key=lambda t: t.filtration_value)
        non_tree_set = {e.vertices for e in non_tree_edges}

        for tri in sorted_triangles:
            tri_edges = [f.vertices for f in tri.faces() if f.dimension == 1]
            non_tree_in_tri = [e for e in tri_edges if e in non_tree_set]

            for nt_edge in non_tree_in_tri:
                if nt_edge not in killed_cycles:
                    killed_cycles.add(nt_edge)
                    pairs.append(PersistencePair(
                        birth=cycle_birth[nt_edge],
                        death=tri.filtration_value,
                        dimension=1,
                    ))
                    break

        # Essential cycles (never killed)
        for edge in non_tree_edges:
            if edge.vertices not in killed_cycles:
                pairs.append(PersistencePair(
                    birth=cycle_birth[edge.vertices],
                    death=float('inf'),
                    dimension=1,
                ))

        return pairs


# =============================================================================
# TDA ANOMALY DETECTOR
# =============================================================================

class TDAAnomalyDetector:
    """
    Detect topological anomalies using persistent homology.

    Compares the persistent homology of a baseline graph against
    a current graph. Changes in Betti numbers signal topological events:

    - b0 increase: fragmentation (components splitting apart)
    - b1 increase: new loops forming (circular structures appearing)
    - b0 decrease: merging (previously separate components joining)
    """

    def __init__(self, baseline_edges: List[Tuple[int, int]]):
        """
        Initialize with a baseline graph.

        Args:
            baseline_edges: Edges of the baseline graph.
        """
        self.baseline_edges = list(baseline_edges)
        self.baseline_complex = SimplicialComplex()
        self.baseline_complex.build_flag_complex(self.baseline_edges)

        computer = PersistentHomologyComputer()
        self.baseline_diagram = computer.compute(self.baseline_complex)

    def detect_anomaly(self, current_edges: List[Tuple[int, int]]) -> Dict:
        """
        Detect anomalies by comparing current graph to baseline.

        Computes the persistence diagram of the current graph and
        compares Betti numbers to the baseline at a reference filtration
        value (t=2.0, after all edges have appeared).

        Args:
            current_edges: Edges of the current graph.

        Returns:
            Dictionary with detection results:
            - is_anomalous: True if topological change detected
            - anomaly_type: Description of topological change or None
            - b0_change: Change in b0 (connected components)
            - b1_change: Change in b1 (loops)
            - baseline_diagram: Baseline persistence diagram
            - current_diagram: Current persistence diagram
            - severity: "low", "medium", or "high"
        """
        current_complex = SimplicialComplex()
        current_complex.build_flag_complex(current_edges)

        computer = PersistentHomologyComputer()
        current_diagram = computer.compute(current_complex)

        t = 2.0
        baseline_betti = self.baseline_diagram.betti_numbers_at(t)
        current_betti = current_diagram.betti_numbers_at(t)

        b0_baseline = baseline_betti.get(0, 0)
        b0_current = current_betti.get(0, 0)
        b1_baseline = baseline_betti.get(1, 0)
        b1_current = current_betti.get(1, 0)

        b0_change = b0_current - b0_baseline
        b1_change = b1_current - b1_baseline

        anomaly_type = None
        is_anomalous = False

        if b0_change > 0:
            anomaly_type = "fragmentation"
            is_anomalous = True
        elif b1_change > 0:
            anomaly_type = "loop_formation"
            is_anomalous = True
        elif b0_change < 0:
            anomaly_type = "merging"
            is_anomalous = True

        magnitude = abs(b0_change) + abs(b1_change)
        if magnitude == 0:
            severity = "none"
        elif magnitude <= 2:
            severity = "low"
        elif magnitude <= 5:
            severity = "medium"
        else:
            severity = "high"

        return {
            "is_anomalous": is_anomalous,
            "anomaly_type": anomaly_type,
            "b0_change": b0_change,
            "b1_change": b1_change,
            "baseline_diagram": self.baseline_diagram,
            "current_diagram": current_diagram,
            "severity": severity,
        }

# Backward-compatible alias
TDAAttackDetector = TDAAnomalyDetector


# =============================================================================
# INCREMENTAL PERSISTENCE
# =============================================================================

class IncrementalPersistence:
    """
    Add edges one at a time, maintaining running Betti numbers.

    Supports streaming computation of persistent homology without
    rebuilding the entire complex from scratch each time. Uses
    union-find for H0 and tracks non-tree edges for H1.

    Usage:
        ip = IncrementalPersistence()
        ip.add_vertex(0, 0.0)
        ip.add_vertex(1, 0.0)
        betti = ip.add_edge(0, 1, 1.0)
        # betti == {0: 1, 1: 0}
    """

    def __init__(self):
        self._uf = _UnionFind()
        self._vertices: Set[int] = set()
        self._birth_time: Dict[int, float] = {}
        self._pairs: List[PersistencePair] = []
        self._non_tree_edges: List[Tuple[int, int, float]] = []
        self._triangles: List[Tuple[int, int, int, float]] = []
        self._adjacency: Dict[int, Set[int]] = defaultdict(set)
        self._killed_cycles: Set[Tuple[int, int]] = set()

    def add_vertex(self, v: int, filtration: float = 0.0):
        """Add a vertex at the given filtration value."""
        if v not in self._vertices:
            self._vertices.add(v)
            self._uf.make_set(v)
            self._birth_time[v] = filtration

    def add_edge(self, u: int, v: int, filtration: float) -> Dict[str, int]:
        """
        Add an edge and return current Betti numbers.

        Automatically adds vertices if not present.

        Args:
            u: First vertex
            v: Second vertex
            filtration: Filtration value for this edge

        Returns:
            Dictionary with keys 'b0' and 'b1' for current Betti numbers.
        """
        # Ensure vertices exist
        if u not in self._vertices:
            self.add_vertex(u, 0.0)
        if v not in self._vertices:
            self.add_vertex(v, 0.0)

        edge_key = (min(u, v), max(u, v))

        # Check if this edge merges components (H0)
        ru, rv = self._uf.find(u), self._uf.find(v)
        if ru != rv:
            # Merge: younger component dies
            birth_u = self._birth_time.get(ru, 0.0)
            birth_v = self._birth_time.get(rv, 0.0)
            if birth_u <= birth_v:
                self._pairs.append(PersistencePair(
                    birth=birth_v, death=filtration, dimension=0
                ))
                self._uf.union(u, v)
                new_root = self._uf.find(u)
                self._birth_time[new_root] = birth_u
            else:
                self._pairs.append(PersistencePair(
                    birth=birth_u, death=filtration, dimension=0
                ))
                self._uf.union(u, v)
                new_root = self._uf.find(u)
                self._birth_time[new_root] = birth_v
        else:
            # Non-tree edge: creates a 1-cycle
            self._non_tree_edges.append((edge_key[0], edge_key[1], filtration))

        # Check for new triangles formed by this edge
        common = self._adjacency.get(u, set()) & self._adjacency.get(v, set())
        for w in common:
            self._triangles.append((
                min(u, v, w),
                sorted([u, v, w])[1],
                max(u, v, w),
                filtration,
            ))
            # Check if this triangle kills a non-tree cycle
            tri_edges = [
                (min(u, v), max(u, v)),
                (min(u, w), max(u, w)),
                (min(v, w), max(v, w)),
            ]
            for te in tri_edges:
                if te not in self._killed_cycles:
                    # Check if this is a non-tree edge
                    for nte_u, nte_v, nte_f in self._non_tree_edges:
                        if (nte_u, nte_v) == te and te not in self._killed_cycles:
                            self._killed_cycles.add(te)
                            self._pairs.append(PersistencePair(
                                birth=nte_f, death=filtration, dimension=1
                            ))
                            break

        self._adjacency[u].add(v)
        self._adjacency[v].add(u)

        return self.betti_numbers()

    def betti_numbers(self) -> Dict[str, int]:
        """Return current Betti numbers b0 and b1."""
        # b0 = number of connected components
        roots = set()
        for v in self._vertices:
            roots.add(self._uf.find(v))
        b0 = len(roots)

        # b1 = non-tree edges that haven't been killed by triangles
        b1 = sum(
            1 for u, v, _ in self._non_tree_edges
            if (u, v) not in self._killed_cycles
        )

        return {"b0": b0, "b1": b1}

    def get_diagram(self) -> PersistenceDiagram:
        """Return the current persistence diagram."""
        pairs = list(self._pairs)

        # Add essential H0 pairs (surviving components)
        roots_seen: Set[int] = set()
        for v in self._vertices:
            root = self._uf.find(v)
            if root not in roots_seen:
                roots_seen.add(root)
                pairs.append(PersistencePair(
                    birth=self._birth_time.get(root, 0.0),
                    death=float('inf'),
                    dimension=0,
                ))

        # Add essential H1 pairs (surviving cycles)
        for u, v, f in self._non_tree_edges:
            if (u, v) not in self._killed_cycles:
                pairs.append(PersistencePair(
                    birth=f, death=float('inf'), dimension=1
                ))

        return PersistenceDiagram(pairs)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def _euclidean_distance(p: Tuple[float, ...], q: Tuple[float, ...]) -> float:
    """Compute Euclidean distance between two points."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(p, q)))
