"""
KOMPOSOS-IV Categorical Oracle
================================

The Oracle system generates predictions using structural inference strategies:
1. KanExtensionStrategy - Categorical Kan extensions (colimit computation)
2. SemanticSimilarityStrategy - Embedding-based similarity
3. TemporalReasoningStrategy - Temporal metadata analysis
4. YonedaPatternStrategy - Morphism pattern matching
5. CompositionStrategy - Path composition (transitive closure)
6. FibrationLiftStrategy - Cartesian lift predictions
7. StructuralHoleStrategy - Triangle closure
8. YonedaDistanceStrategy - Drug-repurposing structural similarity when
   Drug/Disease objects are present

Predictions are validated by:
- SheafCoherenceChecker - Ensures predictions agree on overlaps
- PredictionOptimizer - Game-theoretic selection
- OracleLearner - Bayesian confidence adjustment

Usage:
    from oracle import CategoricalOracle

    oracle = CategoricalOracle(category, embeddings)
    predictions = oracle.predict(source, target)
"""

import sys
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from oracle.prediction import Prediction, PredictionBatch, PredictionType
from oracle.strategies import (
    InferenceStrategy,
    KanExtensionStrategy,
    SemanticSimilarityStrategy,
    TemporalReasoningStrategy,
    YonedaPatternStrategy,
    CompositionStrategy,
    FibrationLiftStrategy,
    StructuralHoleStrategy,
)
from oracle.coherence import SheafCoherenceChecker, CoherenceResult
from oracle.optimizer import PredictionOptimizer, OptimizationResult
from oracle.learner import OracleLearner

from core.category import Category
from data.embeddings import EmbeddingsEngine


@dataclass
class OracleResult:
    """Complete result from Oracle prediction."""
    predictions: List[Prediction]
    coherence_result: CoherenceResult
    optimization_result: OptimizationResult
    strategy_contributions: Dict[str, int]
    total_candidates: int
    computation_time_ms: float


class CategoricalOracle:
    """
    The KOMPOSOS-IV Categorical Oracle.

    Uses structural inference strategies backed by:
    - Category theory (Kan extensions)
    - Semantic analysis (embeddings)
    - Game theory (Nash equilibrium)
    - Bayesian learning (confidence adjustment)

    Requires embeddings to be initialized for semantic similarity strategy.
    """

    def __init__(self,
                 category: Category,
                 embeddings: EmbeddingsEngine,
                 min_confidence: float = 0.4,
                 max_predictions: int = 20):
        """
        Initialize the Categorical Oracle.

        Args:
            category: KOMPOSOS-IV Category runtime
            embeddings: Embeddings engine (REQUIRED)
            min_confidence: Minimum confidence threshold for predictions
            max_predictions: Maximum predictions to return

        Raises:
            ValueError: If embeddings is None or not available
        """
        if embeddings is None or not embeddings.is_available:
            raise ValueError(
                "CategoricalOracle requires initialized embeddings. "
                "Run 'python cli.py embed' first to compute embeddings."
            )

        self.category = category
        self.embeddings = embeddings
        self.min_confidence = min_confidence
        self.max_predictions = max_predictions

        # Initialize default structural strategies.  The legacy type heuristic is
        # intentionally not part of this runtime profile.
        self.strategies: List[InferenceStrategy] = [
            KanExtensionStrategy(category),
            SemanticSimilarityStrategy(category, embeddings),
            TemporalReasoningStrategy(category),
            YonedaPatternStrategy(category),
            CompositionStrategy(category),
            FibrationLiftStrategy(category),
            StructuralHoleStrategy(category),
        ]
        if self._has_visible_drug_disease_labels(category):
            try:
                from oracle.yoneda_strategy import YonedaDistanceStrategy
                self.strategies.append(YonedaDistanceStrategy(category))
            except Exception as exc:
                print(f"Warning: Yoneda distance strategy unavailable: {exc}")

        # Initialize validation and optimization components
        self.coherence_checker = SheafCoherenceChecker(embeddings)
        self.optimizer = PredictionOptimizer(
            min_confidence=min_confidence,
            max_predictions=max_predictions,
        )
        self.learner = OracleLearner()

    def predict(self, source: str, target: str) -> OracleResult:
        """
        Generate predictions for source -> target relationship.

        Process:
        1. Run all 8 inference strategies
        2. Merge duplicate predictions
        3. Apply sheaf coherence validation
        4. Optimize selection via game theory
        5. Adjust confidences via learning

        Args:
            source: Source object name
            target: Target object name

        Returns:
            OracleResult with predictions and metadata
        """
        start_time = time.time()

        # Verify objects exist
        source_obj = self.category.get(source)
        target_obj = self.category.get(target)

        if not source_obj:
            return self._empty_result(f"Source object '{source}' not found")
        if not target_obj:
            return self._empty_result(f"Target object '{target}' not found")

        # Step 1: Collect predictions from all strategies
        all_predictions: List[Prediction] = []
        strategy_contributions: Dict[str, int] = {}

        for strategy in self.strategies:
            try:
                preds = strategy.predict(source, target)
                strategy_contributions[strategy.name] = len(preds)
                all_predictions.extend(preds)
            except Exception as e:
                # Log error but continue with other strategies
                print(f"Warning: Strategy {strategy.name} failed: {e}")
                strategy_contributions[strategy.name] = 0

        total_candidates = len(all_predictions)

        if not all_predictions:
            return self._empty_result("No predictions generated", start_time)

        # Step 2: Merge duplicate predictions
        merged = self._merge_predictions(all_predictions)

        # Step 3: Apply sheaf coherence validation
        coherence_result = self.coherence_checker.check_coherence(merged)
        coherent_predictions = coherence_result.filtered_predictions

        # Step 4: Adjust confidences based on coherence
        adjusted = self.coherence_checker.adjust_confidences(coherent_predictions)

        # Step 5: Apply learning-based confidence adjustment
        learned = [
            p.with_adjusted_confidence(self.learner.adjust_confidence(p))
            for p in adjusted
        ]

        # Step 6: Game-theoretic optimization
        optimization_result = self.optimizer.optimize(learned)

        computation_time = (time.time() - start_time) * 1000

        return OracleResult(
            predictions=optimization_result.selected_predictions,
            coherence_result=coherence_result,
            optimization_result=optimization_result,
            strategy_contributions=strategy_contributions,
            total_candidates=total_candidates,
            computation_time_ms=computation_time,
        )

    def predict_simple(self, source: str, target: str) -> List[Prediction]:
        """
        Simplified prediction interface - just returns predictions.

        Args:
            source: Source object name
            target: Target object name

        Returns:
            List of predictions sorted by confidence
        """
        result = self.predict(source, target)
        return result.predictions

    def predict_batch(self, pairs: List[tuple]) -> Dict[tuple, List[Prediction]]:
        """
        Predict for multiple source-target pairs.

        Args:
            pairs: List of (source, target) tuples

        Returns:
            Dict mapping each pair to its predictions
        """
        results = {}
        for source, target in pairs:
            results[(source, target)] = self.predict_simple(source, target)
        return results

    def record_outcome(self, prediction: Prediction, was_correct: bool):
        """
        Record prediction outcome for learning.

        Call this when a prediction has been validated or rejected.

        Args:
            prediction: The prediction that was evaluated
            was_correct: True if prediction was confirmed
        """
        self.learner.record_outcome(prediction, was_correct)

    def get_learning_stats(self) -> Dict[str, Any]:
        """Get learning statistics summary."""
        return self.learner.get_summary()

    def _merge_predictions(self, predictions: List[Prediction]) -> List[Prediction]:
        """
        Merge predictions with the same key.

        Uses calibrated weighted average instead of sequential merging.
        """
        from oracle.calibration import weighted_average, StrategyCalibrator
        from pathlib import Path

        by_key: Dict[tuple, List[Prediction]] = {}

        for pred in predictions:
            if pred.key not in by_key:
                by_key[pred.key] = []
            by_key[pred.key].append(pred)

        # Load calibrator if available
        calibrator = None
        if Path("data/strategy_weights.json").exists():
            calibrator = StrategyCalibrator("data/strategy_weights.json")

        merged = []
        for key, preds in by_key.items():
            if len(preds) == 1:
                merged.append(preds[0])
            else:
                # Merge using calibrated weighted average (all at once, not sequential)
                votes = [(p.strategy_name, p.confidence) for p in preds]
                combined_conf = weighted_average(votes, calibrator)

                # Create merged prediction
                strategy_names = "+".join(sorted(set(p.strategy_name for p in preds)))
                merged_evidence = {}
                for p in preds:
                    merged_evidence.update(p.evidence)
                merged_evidence["merged_from"] = [p.strategy_name for p in preds]

                merged_pred = Prediction(
                    source=preds[0].source,
                    target=preds[0].target,
                    predicted_relation=preds[0].predicted_relation,
                    prediction_type=PredictionType.ENSEMBLE,
                    strategy_name=strategy_names,
                    confidence=combined_conf,
                    reasoning=f"Combined from {len(preds)} strategies",
                    evidence=merged_evidence,
                )
                merged.append(merged_pred)

        return merged

    def _empty_result(self, reason: str, start_time: float = None) -> OracleResult:
        """Create empty result for error cases."""
        computation_time = 0.0
        if start_time:
            computation_time = (time.time() - start_time) * 1000

        return OracleResult(
            predictions=[],
            coherence_result=CoherenceResult(
                is_coherent=True,
                coherence_score=0.0,
                min_similarity=0.0,
                contradictions=[],
                filtered_predictions=[],
            ),
            optimization_result=OptimizationResult(
                selected_predictions=[],
                total_utility=0.0,
                strategy_profile={},
                iterations=0,
            ),
            strategy_contributions={},
            total_candidates=0,
            computation_time_ms=computation_time,
        )

    @staticmethod
    def _has_visible_drug_disease_labels(category: Category) -> bool:
        """Return True when Yoneda distance has treatment comparators."""
        try:
            morphisms = category.morphisms()
        except Exception:
            return False
        for morphism in morphisms:
            source = category.get(morphism.source)
            target = category.get(morphism.target)
            if (
                source and target
                and source.type_name == "Drug"
                and target.type_name == "Disease"
            ):
                return True
        return False


# Export main classes
__all__ = [
    'CategoricalOracle',
    'OracleResult',
    'Prediction',
    'PredictionType',
    'PredictionBatch',
]
