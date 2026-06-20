# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Topology Bridge: Category → topology.SimplicialComplex converter

Converts a KOMPOSOS-IV Category into a SimplicialComplex for persistent
homology computation.

This unlocks:
  - topology/persistent_homology.py: Betti numbers, persistence diagrams,
    filtration analysis

Activation: persistent_homology.py was previously dead code because it had
no path from Category. This bridge provides that path.

The key insight: Category morphisms filtered by confidence threshold
naturally define a filtration — as the threshold decreases, more edges
appear, and the topology evolves. Persistent homology tracks which
topological features (loops, voids) persist across thresholds.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.category import Category


def category_to_simplicial_complex(category: "Category",
                                   confidence_threshold: float = 0.0,
                                   build_flag_complex: bool = True) -> Any:
    """
    Convert a KOMPOSOS-IV Category to a topology.SimplicialComplex.

    Objects become vertices.
    Morphisms above threshold become edges (1-simplices).
    Triangles (3 mutually connected objects) become 2-simplices.

    The filtration value for each simplex is 1 - confidence, so
    high-confidence morphisms appear early in the filtration.

    Args:
        category: The source Category.
        confidence_threshold: Minimum confidence for morphisms to include.
        build_flag_complex: If True, automatically fill in higher-dimensional
                           simplices from cliques (flag complex construction).

    Returns:
        A SimplicialComplex instance with the Category's structure.
    """
    from topology.persistent_homology import SimplicialComplex

    complex = SimplicialComplex()

    # Add all objects as 0-simplices (vertices)
    for obj in category.objects():
        complex.add_simplex([obj.name], filtration=0.0)

    # Add morphisms as 1-simplices (edges)
    edges: Set[Tuple[str, str]] = set()
    for mor in category.morphisms():
        if mor.confidence < confidence_threshold:
            continue
        if mor.source == mor.target:
            continue  # Skip identity morphisms

        # Filtration value: 1 - confidence (high confidence = early appearance)
        filt = 1.0 - mor.confidence
        complex.add_simplex([mor.source], filtration=min(filt, 0.0))  # Ensure vertex exists
        complex.add_simplex([mor.target], filtration=min(filt, 0.0))
        complex.add_simplex([mor.source, mor.target], filtration=filt)
        edges.add((mor.source, mor.target))

    # Add 2-simplices (triangles) for cliques
    if build_flag_complex:
        _add_triangles_from_cliques(complex, edges, category)

    return complex


def _add_triangles_from_cliques(complex, edges: Set[Tuple[str, str]],
                                 category: "Category") -> None:
    """
    Add 2-simplices for all 3-cliques in the edge set.

    A 3-clique is a set of 3 vertices where all 3 edges exist.
    The filtration value is the max of the 3 edge filtrations.
    """
    # Build adjacency
    neighbors: Dict[str, Set[str]] = {}
    for a, b in edges:
        neighbors.setdefault(a, set()).add(b)
        neighbors.setdefault(b, set()).add(a)

    # Find triangles
    added_triangles = set()
    for a in neighbors:
        for b in neighbors[a]:
            if b <= a:
                continue
            # Common neighbors of a and b form triangles
            common = neighbors[a] & neighbors[b]
            for c in common:
                if c <= b:
                    continue
                # Found triangle (a, b, c)
                triangle = tuple(sorted([a, b, c]))
                if triangle in added_triangles:
                    continue
                added_triangles.add(triangle)

                # Filtration = max of edge filtrations
                max_filt = 0.0
                for e in [(a, b), (b, c), (a, c)]:
                    for mor in category.morphisms():
                        if ((mor.source == e[0] and mor.target == e[1]) or
                            (mor.source == e[1] and mor.target == e[0])):
                            filt = 1.0 - mor.confidence
                            max_filt = max(max_filt, filt)

                complex.add_simplex(list(triangle), filtration=max_filt)


def compute_persistent_homology(category: "Category",
                                confidence_threshold: float = 0.0) -> Dict[str, Any]:
    """
    Compute persistent homology of a Category.

    This is the full pipeline: Category → SimplicialComplex → Persistence Diagram.

    Args:
        category: The source Category.
        confidence_threshold: Minimum confidence for morphisms.

    Returns:
        Dict with betti_numbers, persistence_pairs, and analysis.
    """
    from topology.persistent_homology import PersistentHomologyComputer

    complex = category_to_simplicial_complex(category, confidence_threshold)
    computer = PersistentHomologyComputer()
    diagram = computer.compute(complex)

    # Organize results
    betti_by_dim = {}
    for dim, pairs in diagram.betti_numbers_by_dimension.items():
        betti_by_dim[dim] = [
            {"birth": p.birth, "death": p.death, "persistence": p.death - p.birth if p.death > 0 else 1.0 - p.birth}
            for p in pairs
        ]

    return {
        "betti_numbers": {dim: len(pairs) for dim, pairs in diagram.betti_numbers_by_dimension.items()},
        "persistence_pairs": betti_by_dim,
        "num_simplices": len(complex.simplices),
        "max_dimension": complex.max_dimension,
    }
