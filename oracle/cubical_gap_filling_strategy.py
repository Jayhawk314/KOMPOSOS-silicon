# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Cubical Gap Filling Strategy - Transitive Inference via Kan Operations
========================================================================

Uses Cubical Type Theory Kan operations to infer missing relationships.

Mathematical Foundation:
------------------------
In Cubical Type Theory, Kan operations (hcomp, hfill) allow us to complete
partial cubes. For knowledge graphs, this means:

1. **hcomp** (composition): A -> B, B -> C  |-  A -> C
   - Confidence decreases with path length
   - Relation type is "composed" of intermediate types

2. **hfill** (filling): Complete gaps in partial pathways
   - If most steps in a pathway exist, fill the missing step

Confidence formula:
- 2-hop: confidence = c1 * c2 * 0.9  (90% penalty for indirect)
- 3-hop: confidence = c1 * c2 * c3 * 0.7  (70% penalty)
- 4-hop: confidence = c1 * c2 * c3 * c4 * 0.5  (50% penalty)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from oracle.prediction import Prediction, PredictionType
from oracle.strategies import InferenceStrategy


@dataclass
class InferredInteraction:
    """An interaction inferred via Cubical operations."""
    source: str
    target: str
    path: List[str]
    relations: List[str]
    confidence: float
    operation: str  # "hcomp" or "hfill"


class CubicalGapFillingStrategy(InferenceStrategy):
    """
    Infer missing relationships using Cubical Type Theory Kan operations.

    Strategy:
    1. Find all paths of length 2-4 from source to target
    2. For each path, use hcomp (composition) to infer direct interaction
    3. Compute confidence based on path length and intermediate confidences
    4. Generate predictions for high-confidence inferences
    """

    name = "cubical_gap_filling"

    def __init__(self, category, max_path_length: int = 3, min_confidence: float = 0.4):
        super().__init__(category)
        self.max_path_length = max_path_length
        self.min_confidence = min_confidence

    def _find_indirect_paths(self, source: str, target: str) -> List[List[Tuple[str, str, float]]]:
        """
        Find all indirect paths from source to target (length 2-4).

        Returns:
            List of paths, where each path is a list of (node, relation, confidence) tuples
        """
        outgoing, incoming = self._build_morphism_index()

        paths = []
        queue = [(source, [(source, None, 1.0)], {source})]

        while queue and len(paths) < 100:
            current, path, visited = queue.pop(0)

            if len(path) > self.max_path_length + 1:
                continue

            morphisms = outgoing.get(current, [])

            for morphism in morphisms:
                next_node = morphism.target

                if next_node in visited:
                    continue

                new_path = path + [(next_node, morphism.name, morphism.confidence)]
                new_visited = visited | {next_node}

                if next_node == target and len(new_path) >= 3:
                    paths.append(new_path)
                    if len(paths) >= 100:
                        break
                else:
                    queue.append((next_node, new_path, new_visited))

        return paths

    def _compose_path(self, path: List[Tuple[str, str, float]]) -> InferredInteraction:
        """
        Use hcomp to compose a path into an inferred interaction.
        """
        source = path[0][0]
        target = path[-1][0]

        nodes = [p[0] for p in path]
        relations = [p[1] for p in path[1:]]
        confidences = [p[2] for p in path[1:]]

        base_confidence = 1.0
        for c in confidences:
            base_confidence *= c

        path_length = len(nodes) - 1
        if path_length == 2:
            length_penalty = 0.9
        elif path_length == 3:
            length_penalty = 0.7
        elif path_length == 4:
            length_penalty = 0.5
        else:
            length_penalty = 0.3

        confidence = base_confidence * length_penalty

        if len(set(relations)) == 1:
            composed_relation = relations[0]
        else:
            composed_relation = f"composed_{'_'.join(set(r for r in relations if r))}"

        return InferredInteraction(
            source=source,
            target=target,
            path=nodes,
            relations=relations,
            confidence=confidence,
            operation="hcomp"
        )

    def predict(self, source: str, target: str) -> List[Prediction]:
        """
        Generate predictions using Cubical gap filling.
        """
        outgoing, incoming = self._build_morphism_index()
        morphisms = outgoing.get(source, [])

        direct_exists = any(m.target == target for m in morphisms)
        if direct_exists:
            return []

        paths = self._find_indirect_paths(source, target)

        if not paths:
            return []

        inferred = []
        for path in paths:
            composed = self._compose_path(path)
            if composed.confidence >= self.min_confidence:
                inferred.append(composed)

        if not inferred:
            return []

        by_relation = {}
        for inf in inferred:
            relation = inf.relations[0] if len(inf.relations) > 0 else "related_to"
            if relation not in by_relation or inf.confidence > by_relation[relation].confidence:
                by_relation[relation] = inf

        predictions = []
        for relation, inf in by_relation.items():
            path_str = " -> ".join(inf.path)
            reasoning = (
                f"Cubical inference (hcomp) via {len(inf.path)-1}-hop path: {path_str}. "
                f"Confidence: {inf.confidence:.3f}. "
                f"This inferred relationship fills a gap in the known graph."
            )

            prediction = Prediction(
                source=source,
                target=target,
                predicted_relation=relation,
                prediction_type=PredictionType.TRANSITIVE_CLOSURE,
                confidence=inf.confidence,
                reasoning=reasoning,
                strategy_name=self.name,
                evidence={
                    'operation': 'hcomp',
                    'path': inf.path,
                    'path_length': len(inf.path) - 1,
                    'intermediate_relations': inf.relations,
                    'num_alternative_paths': len([i for i in inferred if i.relations[0] == relation]),
                }
            )
            predictions.append(prediction)

        return predictions
