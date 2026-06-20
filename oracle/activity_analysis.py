# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Activity Analysis Strategy for KOMPOSOS-IV Oracle

Uses Engeström's Activity Theory (modeled categorically) to analyze
the human factors in capability use. Detects contradictions between
what the system is designed to do and what users actually need.

Uses: categorical/activity_system.py (ActivitySystem, ContradictionDetector)

This activates previously dead code: activity_system.py

Ruliad connection: Telemetry data shows not just what capabilities fire
together, but how humans interact with them. Activity theory detects
tensions between the system's design and actual use patterns.
"""

from __future__ import annotations

from typing import List, Dict, Any

from oracle.prediction import Prediction, PredictionType
from oracle.strategies import InferenceStrategy
from core.category import Category


class ActivityAnalysisStrategy(InferenceStrategy):
    """
    Analyze capability use via Engeström's Activity Theory.

    Detects contradictions between:
    - What the system is designed to do (Subject → Object via Tools)
    - What users actually need (detected from telemetry)
    - Organizational rules and community norms

    Contradictions reveal where capabilities are mispositioned in the
    architecture or where user needs aren't being met.
    """

    name = "activity_analysis"

    def __init__(self, category: Category, telemetry_category: Category = None):
        super().__init__(category)
        self.telemetry = telemetry_category
        self._activity_system = None

    def _get_activity_system(self):
        """Lazy import and build activity system from telemetry."""
        if self._activity_system is None:
            from categorical.activity_system import (
                ActivitySystem, ActivitySystemBuilder, ContradictionDetector
            )

            builder = ActivitySystemBuilder()
            if self.telemetry:
                objects = self.telemetry.objects()
                morphisms = self.telemetry.morphisms()
                self._activity_system = builder.build(objects, morphisms)
            else:
                # Build from category directly
                objects = self.category.objects()
                morphisms = self.category.morphisms()
                self._activity_system = builder.build(objects, morphisms)

        return self._activity_system

    def predict(self, source: str, target: str) -> List[Prediction]:
        """
        Predict capability gaps using activity theory analysis.

        Strategy:
        1. Build activity system from telemetry/category
        2. Detect contradictions (tensions between design and use)
        3. For each contradiction, predict the missing capability
           that would resolve it
        """
        predictions = []
        activity_system = self._get_activity_system()

        from categorical.activity_system import ContradictionDetector

        detector = ContradictionDetector()
        contradictions = detector.detect_all(activity_system)

        for contradiction in contradictions:
            # Check if this contradiction involves source or target
            components = contradiction.components_involved
            if source in components or target in components:
                predictions.append(Prediction(
                    source=source,
                    target=target,
                    predicted_relation=f"resolves_{contradiction.level}_contradiction",
                    prediction_type=PredictionType.STRUCTURAL_HOLE,
                    strategy_name=self.name,
                    confidence=0.6,
                    reasoning=(
                        f"Activity theory detects a {contradiction.level}-level contradiction: "
                        f"{contradiction.description}. "
                        f"Components involved: {', '.join(components)}. "
                        f"A new capability may resolve this tension."
                    ),
                    evidence={
                        "contradiction_level": contradiction.level,
                        "description": contradiction.description,
                        "components": list(components),
                    },
                ))

        return sorted(predictions, key=lambda p: -p.confidence)

    def detect_activity_contradictions(self) -> List[Dict[str, Any]]:
        """
        Detect all activity theory contradictions in the capability graph.

        Returns:
            List of contradiction descriptions with recommended fixes.
        """
        activity_system = self._get_activity_system()
        from categorical.activity_system import ContradictionDetector

        detector = ContradictionDetector()
        contradictions = detector.detect_all(activity_system)

        return [
            {
                "level": c.level,
                "description": c.description,
                "components": list(c.components_involved),
                "recommendation": f"Consider restructuring the relationship between {', '.join(c.components_involved)}",
            }
            for c in contradictions
        ]
