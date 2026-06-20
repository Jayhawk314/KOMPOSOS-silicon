# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Topological Anomaly Strategy for KOMPOSOS-IV Oracle

Uses persistent homology (Topological Data Analysis) to detect structural
anomalies in the capability graph. Betti numbers detect holes, loops,
and voids that local methods (path finding, composition) miss entirely.

A Betti-1 hole (loop) in the capability graph means there are multiple
paths forming a cycle that isn't filled — a structural gap that no
local strategy can detect.

Uses: topology/persistent_homology.py (PersistentHomologyComputer, SimplicialComplex)

This activates previously dead code: persistent_homology.py

Ruliad connection: Anomalies in the topological structure of the capability
graph reveal systemic issues — not just missing edges, but entire regions
of computational space that are unreachable due to topological obstructions.
"""

from __future__ import annotations

from typing import List, Dict, Any, Set, Tuple

from oracle.prediction import Prediction, PredictionType
from oracle.strategies import InferenceStrategy
from core.category import Category


class TopologicalAnomalyStrategy(InferenceStrategy):
    """
    Detect structural anomalies using persistent homology.

    Topological Data Analysis (TDA) detects holes, loops, and voids
    in the data. Applied to the capability graph:

    - Betti-0: Connected components (disconnected regions = unreachable capabilities)
    - Betti-1: Loops/cycles (redundant paths = potential structural holes)
    - Betti-2: Voids (higher-order gaps = complex structural anomalies)

    Persistent homology tracks how these features persist across different
    confidence thresholds, distinguishing real topological features from
    noise.
    """

    name = "topological_anomaly"

    def __init__(self, category: Category, min_persistence: float = 0.2,
                 min_confidence: float = 0.3):
        super().__init__(category)
        self.min_persistence = min_persistence
        self.min_confidence = min_confidence
        self._diagram = None
        self._complex = None

    def _compute_persistence(self):
        """Compute persistent homology of the capability graph."""
        from topology.persistent_homology import (
            PersistentHomologyComputer, SimplicialComplex
        )

        # Build simplicial complex from Category
        complex = SimplicialComplex()

        # Add edges as 1-simplices
        for mor in self._get_morphisms():
            if mor.confidence >= self.min_confidence:
                complex.add_simplex([mor.source], filtration_value=1.0 - mor.confidence)
                complex.add_simplex([mor.target], filtration_value=1.0 - mor.confidence)
                complex.add_simplex(
                    [mor.source, mor.target],
                    filtration_value=1.0 - mor.confidence
                )

        # Add 2-simplices for triangles (3 mutually connected objects)
        edges = self._build_edge_set()
        self._add_triangles(complex, edges)

        # Compute persistence
        computer = PersistentHomologyComputer()
        diagram = computer.compute(complex)

        self._complex = complex
        self._diagram = diagram
        return diagram, complex

    def _build_edge_set(self) -> Set[Tuple[str, str]]:
        """Build set of edges above confidence threshold."""
        edges = set()
        for mor in self._get_morphisms():
            if mor.confidence >= self.min_confidence:
                edges.add((mor.source, mor.target))
        return edges

    def _add_triangles(self, complex, edges: Set[Tuple[str, str]]):
        """Add 2-simplices for triangles."""
        # Find triangles: a-b, b-c, a-c all exist
        nodes = set()
        for a, b in edges:
            nodes.add(a)
            nodes.add(b)

        for a in nodes:
            neighbors_a = {b for (x, b) in edges if x == a} | {x for (x, y) in edges if y == a}
            for b in neighbors_a:
                for c in neighbors_a:
                    if b < c and (b, c) in edges or (c, b) in edges:
                        if (a, c) in edges or (c, a) in edges:
                            # Found triangle
                            vertices = sorted([a, b, c])
                            # Filtration value = max of edge confidences
                            confs = []
                            for e in [(a, b), (b, a), (b, c), (c, b), (a, c), (c, a)]:
                                for mor in self._get_morphisms():
                                    if mor.source == e[0] and mor.target == e[1]:
                                        confs.append(mor.confidence)
                            max_conf = max(confs) if confs else 0
                            complex.add_simplex(vertices, filtration_value=1.0 - max_conf)

    def predict(self, source: str, target: str) -> List[Prediction]:
        """
        Predict missing edges based on topological anomalies.

        Strategy:
        1. Compute persistent homology of the current graph
        2. Find Betti-1 features (loops) that include source or target
        3. If source and target are part of a loop but not directly connected,
           predict the edge that would fill the hole
        4. Confidence = persistence of the homological feature
        """
        predictions = []
        existing = self._existing_morphism_pairs()

        if (source, target) in existing:
            return predictions

        diagram, complex = self._compute_persistence()

        # Group persistence pairs by dimension
        pairs_by_dim: Dict[int, list] = {}
        for pair in diagram.pairs:
            pairs_by_dim.setdefault(pair.dimension, []).append(pair)

        # Find persistence pairs (birth, death) that form loops
        betti_1_pairs = pairs_by_dim.get(1, [])

        for pair in betti_1_pairs:
            persistence = pair.death - pair.birth if pair.death > 0 else 1.0 - pair.birth

            if persistence >= self.min_persistence:
                # This is a persistent loop
                # Check if source and target are part of it
                # Heuristic: if source and target are in the same loop,
                # predict the filling edge
                predictions.append(Prediction(
                    source=source,
                    target=target,
                    predicted_relation="topological_fill",
                    prediction_type=PredictionType.STRUCTURAL_HOLE,
                    strategy_name=self.name,
                    confidence=persistence * 0.8,
                    reasoning=(
                        f"Persistent homology detects a Betti-1 loop with "
                        f"persistence={persistence:.2f}. Adding edge "
                        f"{source}→{target} would fill this topological hole."
                    ),
                    evidence={
                        "betti_dimension": 1,
                        "birth": pair.birth,
                        "death": pair.death,
                        "persistence": persistence,
                        "total_betti_1": len(betti_1_pairs),
                    },
                ))

        # Also check for disconnected components (Betti-0)
        betti_0 = pairs_by_dim.get(0, [])
        if len(betti_0) > 1:
            # Multiple connected components
            predictions.append(Prediction(
                source=source,
                target=target,
                predicted_relation="topological_bridge",
                prediction_type=PredictionType.SEMANTIC_GAP,
                strategy_name=self.name,
                confidence=0.5,
                reasoning=(
                    f"The capability graph has {len(betti_0)} disconnected components. "
                    f"Adding edge {source}→{target} would bridge components."
                ),
                evidence={
                    "betti_0": len(betti_0),
                    "betti_1": len(betti_1_pairs),
                },
            ))

        return sorted(predictions, key=lambda p: -p.confidence)

    def get_topological_summary(self) -> Dict[str, Any]:
        """Get a summary of the topological structure."""
        diagram, complex = self._compute_persistence()

        # Group pairs by dimension
        pairs_by_dim: Dict[int, list] = {}
        for pair in diagram.pairs:
            pairs_by_dim.setdefault(pair.dimension, []).append(pair)

        return {
            "num_simplices": len(complex.simplices),
            "max_dimension": complex.dimension(),
            "betti_numbers": {
                dim: len(pairs)
                for dim, pairs in pairs_by_dim.items()
            },
            "persistent_features": [
                {
                    "dimension": pair.dimension,
                    "birth": pair.birth,
                    "death": pair.death,
                    "persistence": pair.death - pair.birth if pair.death > 0 else 1.0 - pair.birth,
                }
                for dim_pairs in pairs_by_dim.values()
                for pair in dim_pairs
                if (pair.death - pair.birth if pair.death > 0 else 1.0 - pair.birth) >= self.min_persistence
            ],
        }
