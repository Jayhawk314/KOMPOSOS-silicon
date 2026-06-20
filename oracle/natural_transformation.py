# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Natural Transformation Strategy for KOMPOSOS-IV Oracle

Detects when two functors (pattern sequences) are related by a natural
transformation — meaning they share the same abstract shape but differ in
concrete elements.

Uses: categorical/natural_transformations.py (PatternFunctor, NaturalTransformationDetector)

This activates previously dead code: natural_transformations.py

Riehl-Verity connection: 2-morphisms in the homotopy 2-category ARE natural
transformations. This strategy detects them in the knowledge graph.
"""

from __future__ import annotations

from typing import List, Dict, Any

from oracle.prediction import Prediction, PredictionType
from oracle.strategies import InferenceStrategy
from core.category import Category


class NaturalTransformationStrategy(InferenceStrategy):
    """
    Detect pattern variants via natural transformations.

    If two sequences of morphisms have the same abstract structure
    (same pattern of relationships) but different concrete objects,
    they are related by a natural transformation. This predicts that
    missing edges in one pattern should mirror the other.

    Usage:
        strategy = NaturalTransformationStrategy(category)
        predictions = strategy.predict("A", "B")
    """

    name = "natural_transformation"

    def __init__(self, category: Category, threshold: float = 0.6):
        super().__init__(category)
        self.threshold = threshold
        self._detector = None

    def _get_detector(self):
        """Lazy import and initialize NaturalTransformationDetector."""
        if self._detector is None:
            from categorical.natural_transformations import (
                NaturalTransformationDetector, PatternFunctor
            )
            self._detector = NaturalTransformationDetector()
            self._PatternFunctor = PatternFunctor
        return self._detector

    def predict(self, source: str, target: str) -> List[Prediction]:
        """
        Predict missing edges by detecting natural transformations between patterns.

        Strategy:
        1. Find all paths from source to any intermediate X
        2. Find all paths from X to target
        3. Check if these form naturality squares with other known patterns
        4. If naturality holds, predict the missing diagonal
        """
        predictions = []
        existing = self._existing_morphism_pairs()

        if (source, target) in existing:
            return predictions

        # Find patterns: source -> X -> Y and source -> X' -> Y where X ~ X'
        objects = self._get_objects()
        intermediates = []

        for obj in objects:
            if obj.name == source or obj.name == target:
                continue

            # Check if source -> obj exists
            source_to_obj = [
                m for m in self._get_morphisms()
                if m.source == source and m.target == obj.name
            ]
            if not source_to_obj:
                continue

            # Check if obj -> target exists
            obj_to_target = [
                m for m in self._get_morphisms()
                if m.source == obj.name and m.target == target
            ]
            if not obj_to_target:
                continue

            intermediates.append({
                "intermediate": obj.name,
                "forward": source_to_obj,
                "backward": obj_to_target,
            })

        # Check for naturality between different intermediate paths
        for i, path_a in enumerate(intermediates):
            for path_b in intermediates[i + 1:]:
                # Check if the patterns are "similar" (same shape, different intermediate)
                if len(path_a["forward"]) > 0 and len(path_b["forward"]) > 0:
                    # Both have source -> intermediate -> target
                    # This is a naturality square candidate
                    conf_a = max(m.confidence for m in path_a["forward"] + path_a["backward"])
                    conf_b = max(m.confidence for m in path_b["forward"] + path_b["backward"])

                    # Natural transformation score: how similar are the patterns?
                    nat_score = 1.0 - abs(conf_a - conf_b)

                    if nat_score >= self.threshold:
                        predictions.append(Prediction(
                            source=source,
                            target=target,
                            predicted_relation="natural_transform",
                            prediction_type=PredictionType.STRUCTURAL_SIMILARITY,
                            strategy_name=self.name,
                            confidence=nat_score * 0.85,
                            reasoning=(
                                f"Natural transformation detected between patterns "
                                f"via {path_a['intermediate']} (conf={conf_a:.2f}) "
                                f"and {path_b['intermediate']} (conf={conf_b:.2f}). "
                                f"Both share the same abstract shape."
                            ),
                            evidence={
                                "pattern_a": path_a["intermediate"],
                                "pattern_b": path_b["intermediate"],
                                "confidence_a": conf_a,
                                "confidence_b": conf_b,
                                "naturality_score": nat_score,
                            },
                        ))

        return sorted(predictions, key=lambda p: -p.confidence)

    def detect_variants(self, observed_sequence: List[str],
                        threshold: float = None) -> List[Prediction]:
        """
        Detect variant patterns similar to an observed sequence.

        Args:
            observed_sequence: List of object names forming a pattern.
            threshold: Override the instance threshold.

        Returns:
            List of predictions for similar patterns.
        """
        threshold = threshold or self.threshold
        predictions = []
        detector = self._get_detector()

        # Build pattern functor from observed sequence
        if len(observed_sequence) < 2:
            return predictions

        pattern = self._PatternFunctor(
            name="observed",
            shape=list(range(len(observed_sequence))),
            instance=observed_sequence,
        )

        # Register and detect variants
        detector.register_pattern(pattern)

        # Find similar patterns in the category
        all_objects = [obj.name for obj in self._get_objects()]
        for obj in all_objects:
            if obj in observed_sequence:
                continue

            # Check if obj participates in a similar pattern
            obj_morphisms = [
                m for m in self._get_morphisms()
                if m.source == obj or m.target == obj
            ]

            if obj_morphisms:
                obj_pattern = self._PatternFunctor(
                    name=f"variant_{obj}",
                    shape=list(range(len(obj_morphisms))),
                    instance=[obj] + [m.target if m.source == obj else m.source
                                     for m in obj_morphisms[:len(observed_sequence) - 1]],
                )

                if detector.check_naturality(pattern, obj_pattern) > threshold:
                    predictions.append(Prediction(
                        source=observed_sequence[0],
                        target=obj,
                        predicted_relation="pattern_variant",
                        prediction_type=PredictionType.YONEDA_ANALOGY,
                        strategy_name=self.name,
                        confidence=threshold,
                        reasoning=f"Object {obj} participates in a pattern variant of the observed sequence",
                        evidence={"observed": observed_sequence, "variant": obj_pattern.instance},
                    ))

        return sorted(predictions, key=lambda p: -p.confidence)
