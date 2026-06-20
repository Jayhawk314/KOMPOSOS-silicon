"""
Game-Theoretic Prediction Optimizer for KOMPOSOS-III Oracle.

Models prediction selection as a 2-player game:
- Player 1 (Predictor): Chooses which predictions to output
- Player 2 (Validator): Accepts or rejects predictions

Nash equilibrium identifies predictions that are:
- Likely to be accepted (high quality)
- Mutually consistent
- Optimal under uncertainty
"""

import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import math

sys.path.insert(0, str(Path(__file__).parent.parent))

from oracle.prediction import Prediction, PredictionBatch


@dataclass
class OptimizationResult:
    """Result of game-theoretic optimization."""
    selected_predictions: List[Prediction]
    total_utility: float
    strategy_profile: Dict[str, float]  # Strategy -> weight
    iterations: int


class PredictionOptimizer:
    """
    Use game theory to select optimal predictions.

    The prediction game:
    - Predictor's utility: sum of confidences for accepted predictions
    - Validator's utility: precision (accepted predictions that are correct)

    Nash equilibrium: Output predictions where both players are satisfied.
    """

    def __init__(self,
                 min_confidence: float = 0.4,
                 max_predictions: int = 20,
                 diversity_weight: float = 0.3):
        """
        Initialize optimizer.

        Args:
            min_confidence: Minimum confidence to consider
            max_predictions: Maximum predictions to return
            diversity_weight: Weight for strategy diversity in utility
        """
        self.min_confidence = min_confidence
        self.max_predictions = max_predictions
        self.diversity_weight = diversity_weight

    def optimize(self, predictions: List[Prediction]) -> OptimizationResult:
        """
        Select optimal predictions using game-theoretic reasoning.

        Algorithm:
        1. Filter by minimum confidence
        2. Compute utility for each prediction
        3. Use iterated best response to find equilibrium
        4. Select predictions in equilibrium
        """
        if not predictions:
            return OptimizationResult(
                selected_predictions=[],
                total_utility=0.0,
                strategy_profile={},
                iterations=0,
            )

        # Filter by minimum confidence
        candidates = [p for p in predictions if p.confidence >= self.min_confidence]

        if not candidates:
            return OptimizationResult(
                selected_predictions=[],
                total_utility=0.0,
                strategy_profile={},
                iterations=0,
            )

        # Compute utility for each prediction
        utilities = self._compute_utilities(candidates)

        # Iterated best response
        selected, iterations = self._iterated_best_response(candidates, utilities)

        # Compute strategy profile (which strategies contributed)
        strategy_profile = {}
        for pred in selected:
            strategy = pred.strategy_name.split("+")[0]  # Handle merged strategies
            strategy_profile[strategy] = strategy_profile.get(strategy, 0) + 1

        total = sum(strategy_profile.values())
        strategy_profile = {k: v/total for k, v in strategy_profile.items()}

        total_utility = sum(utilities.get(id(p), 0) for p in selected)

        return OptimizationResult(
            selected_predictions=selected,
            total_utility=total_utility,
            strategy_profile=strategy_profile,
            iterations=iterations,
        )

    def _compute_utilities(self, predictions: List[Prediction]) -> Dict[int, float]:
        """
        Compute utility for each prediction.

        Utility factors:
        1. Confidence (primary)
        2. Strategy diversity (bonus for unique strategies)
        3. Relation type diversity (bonus for varied predictions)
        4. Evidence quality (bonus for more evidence)
        """
        utilities = {}

        # Count strategy occurrences for diversity bonus
        strategy_counts = {}
        for p in predictions:
            s = p.strategy_name.split("+")[0]
            strategy_counts[s] = strategy_counts.get(s, 0) + 1

        # Count relation type occurrences
        relation_counts = {}
        for p in predictions:
            relation_counts[p.predicted_relation] = relation_counts.get(p.predicted_relation, 0) + 1

        total_predictions = len(predictions)

        for pred in predictions:
            # Base utility is confidence
            utility = pred.confidence

            # Strategy diversity bonus (rare strategies get bonus)
            strategy = pred.strategy_name.split("+")[0]
            strategy_rarity = 1 - (strategy_counts[strategy] / total_predictions)
            utility += self.diversity_weight * strategy_rarity * 0.2

            # Relation diversity bonus
            relation_rarity = 1 - (relation_counts[pred.predicted_relation] / total_predictions)
            utility += self.diversity_weight * relation_rarity * 0.1

            # Evidence quality bonus
            evidence_score = min(0.1, len(pred.evidence) * 0.02)
            utility += evidence_score

            # Ensemble bonus (multiple strategies agreed)
            if "+" in pred.strategy_name:
                num_strategies = pred.strategy_name.count("+") + 1
                utility += 0.05 * num_strategies

            utilities[id(pred)] = utility

        return utilities

    def _iterated_best_response(self, predictions: List[Prediction],
                                 utilities: Dict[int, float],
                                 max_iterations: int = 10) -> Tuple[List[Prediction], int]:
        """
        Iterated best response algorithm for equilibrium finding.

        Each iteration:
        1. Predictor selects highest utility predictions
        2. Validator "rejects" low confidence ones
        3. Update selection based on mutual best response

        Converges when selection stabilizes.
        """
        # Initial selection: top k by utility
        sorted_preds = sorted(predictions, key=lambda p: utilities.get(id(p), 0), reverse=True)
        selected = set(id(p) for p in sorted_preds[:self.max_predictions])

        for iteration in range(max_iterations):
            prev_selected = selected.copy()

            # Validator's response: reject low confidence
            validator_threshold = self._compute_validator_threshold(predictions, selected, utilities)
            accepted = {
                pid for pid in selected
                if any(p.confidence >= validator_threshold for p in predictions if id(p) == pid)
            }

            # Predictor's response: maximize utility given validator's acceptance
            # Add back predictions that would be accepted
            candidate_utilities = []
            for p in predictions:
                pid = id(p)
                if p.confidence >= validator_threshold:
                    candidate_utilities.append((pid, utilities.get(pid, 0)))

            candidate_utilities.sort(key=lambda x: -x[1])
            selected = set(pid for pid, _ in candidate_utilities[:self.max_predictions])

            # Check convergence
            if selected == prev_selected:
                return [p for p in predictions if id(p) in selected], iteration + 1

        # Return final selection
        return [p for p in predictions if id(p) in selected], max_iterations

    def _compute_validator_threshold(self, predictions: List[Prediction],
                                      selected: set,
                                      utilities: Dict[int, float]) -> float:
        """
        Compute validator's acceptance threshold.

        Validator wants high precision, so sets threshold based on
        confidence distribution of selected predictions.
        """
        selected_confidences = [
            p.confidence for p in predictions if id(p) in selected
        ]

        if not selected_confidences:
            return self.min_confidence

        # Threshold is median confidence (validator accepts top half)
        sorted_conf = sorted(selected_confidences)
        median_idx = len(sorted_conf) // 2
        threshold = sorted_conf[median_idx]

        # But not lower than minimum
        return max(self.min_confidence, threshold * 0.9)


class UtilityFunction:
    """
    Utility function for prediction evaluation.

    Combines multiple factors into a single utility score.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {
            "confidence": 0.5,
            "strategy_diversity": 0.15,
            "relation_diversity": 0.1,
            "evidence_quality": 0.1,
            "coherence": 0.15,
        }

    def compute(self, prediction: Prediction,
                strategy_rarity: float = 0.5,
                relation_rarity: float = 0.5,
                coherence_score: float = 1.0) -> float:
        """Compute utility for a single prediction."""
        utility = (
            self.weights["confidence"] * prediction.confidence +
            self.weights["strategy_diversity"] * strategy_rarity +
            self.weights["relation_diversity"] * relation_rarity +
            self.weights["evidence_quality"] * min(1.0, len(prediction.evidence) * 0.2) +
            self.weights["coherence"] * coherence_score
        )
        return utility
