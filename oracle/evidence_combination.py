# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Evidence Combination Strategy for KOMPOSOS-IV Oracle

Uses Dempster-Shafer theory of evidence to combine uncertain predictions
from multiple sources. Instead of simple probability multiplication,
Dempster's rule handles conflicting evidence properly by computing
belief and plausibility bounds.

Uses: categorical/dempster_shafer.py (MassFunction, combine, weighted_combine)

This activates previously dead code: dempster_shafer.py

Ruliad connection: When multiple oracle strategies make predictions about
the same edge, this strategy combines their evidence properly, handling
conflicts between strategies that simple averaging would miss.
"""

from __future__ import annotations

from typing import List, Dict, Any

from oracle.prediction import Prediction, PredictionType
from oracle.strategies import InferenceStrategy
from core.category import Category


class EvidenceCombinationStrategy(InferenceStrategy):
    """
    Combine uncertain predictions using Dempster-Shafer theory.

    When multiple strategies predict the same edge with different
    confidences, this strategy combines their evidence using
    Dempster's combination rule, which properly handles conflicts.

    Key advantage over simple averaging:
    - Simple averaging: (0.9 + 0.1) / 2 = 0.5 (hides conflict)
    - Dempster-Shafer: detects the conflict explicitly
    """

    name = "evidence_combination"

    def __init__(self, category: Category, min_confidence: float = 0.3):
        super().__init__(category)
        self.min_confidence = min_confidence

    def predict(self, source: str, target: str) -> List[Prediction]:
        """
        Combine evidence from all other strategies for this edge.

        Strategy:
        1. Run all other strategies on (source, target)
        2. Convert each strategy's prediction to a Dempster-Shafer mass function
        3. Combine mass functions using Dempster's rule
        4. Extract belief and plausibility bounds
        5. Return prediction with combined confidence
        """
        from categorical.dempster_shafer import MassFunction, combine

        # Collect predictions from other strategies
        all_preds = []
        for strategy in self._other_strategies:
            preds = strategy.predict(source, target)
            all_preds.extend(preds)

        if not all_preds:
            return []

        # Group predictions by predicted_relation
        by_relation: Dict[str, List[Prediction]] = {}
        for pred in all_preds:
            by_relation.setdefault(pred.predicted_relation, []).append(pred)

        predictions = []
        for relation, preds in by_relation.items():
            if len(preds) == 1:
                # Single source: no combination needed
                predictions.append(preds[0])
            else:
                # Multiple sources: combine using Dempster's rule
                # Build mass functions for each source
                masses = []
                for pred in preds:
                    # Mass function: m({exists}) = confidence, m({not_exists}) = 1 - confidence
                    mass = MassFunction(
                        masses={
                            frozenset(["exists"]): pred.confidence,
                            frozenset(["exists", "not_exists"]): 1.0 - pred.confidence,
                        },
                    )
                    masses.append(mass)

                # Combine all mass functions
                if masses:
                    combined = masses[0]
                    conflict_total = 0.0
                    for m in masses[1:]:
                        combined, conflict = combine(combined, m)
                        conflict_total += conflict

                    # Extract belief and plausibility
                    belief = combined.belief(frozenset(["exists"]))
                    plausibility = combined.plausibility(frozenset(["exists"]))

                    # Combined confidence is the pignistic probability
                    pignitive = combined.pignistic_probability("exists")

                    if pignitive >= self.min_confidence:
                        predictions.append(Prediction(
                            source=source,
                            target=target,
                            predicted_relation=relation,
                            prediction_type=PredictionType.ENSEMBLE,
                            strategy_name=self.name,
                            confidence=pignitive,
                            reasoning=(
                                f"Dempster-Shafer combination of {len(preds)} strategies. "
                                f"Belief={belief:.2f}, Plausibility={plausibility:.2f}, "
                                f"Conflict={conflict_total:.2f}"
                            ),
                            evidence={
                                "num_sources": len(preds),
                                "strategies": [p.strategy_name for p in preds],
                                "belief": belief,
                                "plausibility": plausibility,
                                "total_conflict": conflict_total,
                                "pignistic": pignitive,
                            },
                        ))

        return sorted(predictions, key=lambda p: -p.confidence)

    def combine_predictions(self, predictions: List[Prediction]) -> Prediction:
        """
        Manually combine a list of predictions using Dempster-Shafer theory.

        This is the main utility method — other strategies can call this
        to combine their outputs.

        Args:
            predictions: List of predictions about the same edge.

        Returns:
            Combined prediction with Dempster-Shafer confidence bounds.
        """
        from categorical.dempster_shafer import MassFunction, combine, weighted_combine

        if len(predictions) == 1:
            return predictions[0]

        # Build mass functions
        masses = []
        for pred in predictions:
            mass = MassFunction(
                masses={
                    frozenset(["exists"]): pred.confidence,
                    frozenset(["exists", "not_exists"]): 1.0 - pred.confidence,
                },
                frame=frozenset(["exists", "not_exists"]),
            )
            masses.append(mass)

        # Combine
        combined = weighted_combine(masses)
        belief = combined.belief(frozenset(["exists"]))
        plausibility = combined.plausibility(frozenset(["exists"]))
        pignitive = combined.pignistic_probability("exists")
        uncertainty = combined.uncertainty

        # Build merged prediction
        merged_evidence = {}
        for pred in predictions:
            merged_evidence.update(pred.evidence)
        merged_evidence["dempster_shafer"] = {
            "belief": belief,
            "plausibility": plausibility,
            "pignitive": pignitive,
            "uncertainty": uncertainty,
        }

        return Prediction(
            source=predictions[0].source,
            target=predictions[0].target,
            predicted_relation=predictions[0].predicted_relation,
            prediction_type=PredictionType.ENSEMBLE,
            strategy_name=self.name,
            confidence=pignitive,
            reasoning=(
                f"Dempster-Shafer combination of {len(predictions)} predictions. "
                f"Belief=[{belief:.2f}, {plausibility:.2f}], "
                f"Conflict={uncertainty:.2f}"
            ),
            evidence=merged_evidence,
        )
