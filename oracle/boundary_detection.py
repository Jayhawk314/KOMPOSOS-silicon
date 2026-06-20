# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Boundary Detection Strategy for KOMPOSOS-IV Oracle

Uses profunctors between activity systems to detect boundary objects -
concepts that are meaningful in multiple domains but aren't fully
integrated into either.

Uses: categorical/boundary_profunctor.py (BoundaryProfunctor, BoundaryObjectDetector)

This activates previously dead code: boundary_profunctor.py (which also
activates activity_system.py)

Ruliad connection: When the system spans multiple domains (e.g., chemistry
and finance), boundary objects are the concepts that bridge them. Detecting
and strengthening these bridges enables cross-domain reasoning.
"""

from __future__ import annotations

from typing import List, Dict, Any

from oracle.prediction import Prediction, PredictionType
from oracle.strategies import InferenceStrategy
from core.category import Category


class BoundaryDetectionStrategy(InferenceStrategy):
    """
    Detect boundary objects between activity systems.

    Boundary objects are concepts that are meaningful in multiple domains
    but aren't fully integrated into either. They represent potential
    bridges for cross-domain reasoning.

    Usage:
        strategy = BoundaryDetectionStrategy(category)
        predictions = strategy.predict("chemistry_concept", "finance_concept")
    """

    name = "boundary_detection"

    def __init__(self, category: Category, min_strength: float = 0.3):
        super().__init__(category)
        self.min_strength = min_strength
        self._detector = None

    def _get_detector(self):
        """Lazy import and initialize BoundaryObjectDetector."""
        if self._detector is None:
            from categorical.boundary_profunctor import (
                BoundaryObjectDetector, BoundaryProfunctor
            )
            self._detector = BoundaryObjectDetector()
            self._BoundaryProfunctor = BoundaryProfunctor
        return self._detector

    def predict(self, source: str, target: str) -> List[Prediction]:
        """
        Predict cross-domain bridges via boundary objects.

        Strategy:
        1. Identify objects that participate in multiple type domains
        2. Check if they form boundary objects (same concept, different roles)
        3. Predict bridges between domains through these boundary objects
        """
        predictions = []
        existing = self._existing_morphism_pairs()

        if (source, target) in existing:
            return predictions

        # Check if source and target are in different domains
        source_obj = self.category.get(source)
        target_obj = self.category.get(target)

        if not source_obj or not target_obj:
            return predictions

        # Different type domains = potential boundary
        if source_obj.type_name != target_obj.type_name:
            # Check if there's a shared structure (boundary object)
            source_neighbors = set()
            target_neighbors = set()

            for mor in self._get_morphisms():
                if mor.source == source:
                    source_neighbors.add(mor.target)
                if mor.target == source:
                    source_neighbors.add(mor.source)
                if mor.source == target:
                    target_neighbors.add(mor.target)
                if mor.target == target:
                    target_neighbors.add(mor.source)

            # Shared neighbors = potential boundary objects
            shared = source_neighbors & target_neighbors
            if shared:
                strength = len(shared) / max(len(source_neighbors | target_neighbors), 1)
                if strength >= self.min_strength:
                    predictions.append(Prediction(
                        source=source,
                        target=target,
                        predicted_relation="boundary_bridge",
                        prediction_type=PredictionType.CURVATURE_BRIDGE,
                        strategy_name=self.name,
                        confidence=strength,
                        reasoning=(
                            f"Boundary object detection: {source} ({source_obj.type_name}) "
                            f"and {target} ({target_obj.type_name}) share {len(shared)} "
                            f"neighbors: {', '.join(list(shared)[:5])}. "
                            f"This suggests a cross-domain bridge."
                        ),
                        evidence={
                            "source_domain": source_obj.type_name,
                            "target_domain": target_obj.type_name,
                            "shared_neighbors": list(shared),
                            "strength": strength,
                        },
                    ))

        return sorted(predictions, key=lambda p: -p.confidence)

    def detect_boundary_objects(self) -> List[Dict[str, Any]]:
        """
        Find all boundary objects in the capability graph.

        Returns:
            List of boundary object descriptions.
        """
        detector = self._get_detector()

        # Group objects by domain
        domains: Dict[str, List[str]] = {}
        for obj in self._get_objects():
            domains.setdefault(obj.type_name, []).append(obj.name)

        # Detect boundary objects between each pair of domains
        boundary_objects = []
        domain_list = list(domains.keys())

        for i, domain_a in enumerate(domain_list):
            for domain_b in domain_list[i + 1:]:
                detected = detector.detect_across_many(
                    system_a_objects=domains[domain_a],
                    system_b_objects=domains[domain_b],
                    category=self.category,
                )
                boundary_objects.extend(detected)

        return boundary_objects
