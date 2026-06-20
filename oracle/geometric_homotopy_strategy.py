# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Geometric Homotopy Strategy - Pathway Redundancy Analysis
==========================================================

Finds alternative pathways that are geometrically homotopic.

Two pathways A->B->C and A->D->C are homotopic if they:
1. Share the same endpoints (A and C)
2. Traverse the same geometric regions (spherical, hyperbolic, euclidean)
3. Have similar curvature profiles

Applications:
- Redundancy analysis: If pathway 1 is blocked, can the system use pathway 2?
- Robustness: Identify pathway redundancy in knowledge graphs
- Bottleneck detection: Unique pathways (no homotopic alternatives) are critical
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import List, Set, Tuple, Dict
from dataclasses import dataclass
from oracle.prediction import Prediction, PredictionType
from oracle.strategies import InferenceStrategy

try:
    from hott.geometric_homotopy import GeometricHomotopyChecker, GeometricHomotopyType
    from geometry.ricci import OllivierRicciCurvature
    HOMOTOPY_AVAILABLE = True
except ImportError:
    HOMOTOPY_AVAILABLE = False


class GeometricHomotopyStrategy(InferenceStrategy):
    """
    Find alternative pathways using geometric homotopy.

    Strategy:
    1. Find all paths from source to target (up to length 4)
    2. Compute geometric signatures (sequence of geometry types)
    3. Group paths by homotopy class
    4. Generate predictions for alternative pathways

    Confidence scoring:
    - Higher confidence for pathways with fewer alternatives (harder to bypass)
    - Lower confidence for pathways with many alternatives (easy to route around)
    """

    name = "geometric_homotopy"

    def __init__(self, category, max_path_length: int = 4, max_paths: int = 50):
        super().__init__(category)
        self.max_path_length = max_path_length
        self.max_paths = max_paths
        self.checker = None
        self.ricci = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazily initialize geometric components."""
        if self._initialized:
            return

        if not HOMOTOPY_AVAILABLE:
            self._initialized = True
            return

        try:
            self.ricci = OllivierRicciCurvature(self.category, alpha=0.5)
            self.checker = GeometricHomotopyChecker(ricci_curvature=self.ricci, store=self.category)
            self._initialized = True
        except Exception as e:
            print(f"Warning: Could not initialize GeometricHomotopyStrategy: {e}")
            self._initialized = True

    def _find_paths_bfs(self, source: str, target: str, max_length: int) -> List[List[str]]:
        """Find all paths from source to target using BFS."""
        if source == target:
            return [[source]]

        outgoing, incoming = self._build_morphism_index()

        paths = []
        queue = [([source], {source})]

        while queue and len(paths) < self.max_paths:
            current_path, visited = queue.pop(0)
            current_node = current_path[-1]

            if len(current_path) >= max_length:
                continue

            morphisms = outgoing.get(current_node, [])

            for morphism in morphisms:
                next_node = morphism.target

                if next_node in visited:
                    continue

                new_path = current_path + [next_node]
                new_visited = visited | {next_node}

                if next_node == target:
                    paths.append(new_path)
                    if len(paths) >= self.max_paths:
                        break
                else:
                    queue.append((new_path, new_visited))

        return paths

    def predict(self, source: str, target: str) -> List[Prediction]:
        """Generate predictions for alternative pathways."""
        self._ensure_initialized()

        if not HOMOTOPY_AVAILABLE or self.checker is None:
            return []

        paths = self._find_paths_bfs(source, target, self.max_path_length)

        if len(paths) <= 1:
            return []

        try:
            result = self.checker.check_paths(paths, strict=True)

            predictions = []

            for class_idx, homotopy_class in enumerate(result.homotopy_classes):
                class_size = len(homotopy_class)

                representative_idx = list(homotopy_class)[0]
                representative_path = paths[representative_idx]
                signature = result.signatures[representative_idx]

                num_alternatives = class_size - 1
                base_confidence = 1.0 / (1.0 + num_alternatives)

                geometric_diversity_bonus = 0.0
                if signature.num_transitions > 0:
                    geometric_diversity_bonus = min(0.2, signature.num_transitions * 0.05)

                confidence = min(0.95, base_confidence + geometric_diversity_bonus)

                if class_size == 1:
                    relation = "unique_pathway"
                elif class_size <= 3:
                    relation = "limited_alternatives"
                else:
                    relation = "high_redundancy"

                path_str = " -> ".join(representative_path)
                geometry_str = " -> ".join(signature.simplified) if signature.simplified else "unknown"

                reasoning = (
                    f"Homotopy class {class_idx + 1}: {class_size} pathway(s) with "
                    f"geometric signature [{geometry_str}]. "
                    f"Representative: {path_str}. "
                )

                if class_size == 1:
                    reasoning += "UNIQUE pathway - critical bottleneck!"
                elif num_alternatives <= 2:
                    reasoning += f"Only {num_alternatives} alternative(s)."
                else:
                    reasoning += f"{num_alternatives} alternatives exist - high redundancy."

                prediction = Prediction(
                    source=source,
                    target=target,
                    predicted_relation=relation,
                    prediction_type=PredictionType.GEOMETRIC,
                    confidence=confidence,
                    reasoning=reasoning,
                    strategy_name=self.name,
                    evidence={
                        'homotopy_class': class_idx,
                        'num_pathways_in_class': class_size,
                        'num_alternatives': num_alternatives,
                        'representative_path': representative_path,
                        'geometric_signature': list(signature.simplified),
                        'num_transitions': signature.num_transitions,
                        'dominant_geometry': signature.dominant_geometry,
                        'total_paths_found': len(paths),
                        'total_homotopy_classes': len(result.homotopy_classes)
                    }
                )

                predictions.append(prediction)

            return predictions

        except Exception as e:
            print(f"Warning: Homotopy analysis failed for {source} -> {target}: {e}")
            return []
