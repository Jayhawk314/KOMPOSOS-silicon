"""
Oracle Learner for KOMPOSOS-III.

Implements feedback-based learning to improve prediction confidence over time:
- Tracks prediction outcomes (correct/incorrect)
- Uses Bayesian updating for confidence adjustment
- Persists learning to disk for cross-session improvement

Formula: adjusted_confidence = 0.5 * original + 0.25 * type_confidence + 0.25 * strategy_confidence
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from oracle.prediction import Prediction, PredictionType


@dataclass
class OutcomeRecord:
    """Record of a prediction outcome."""
    prediction_type: str
    strategy_name: str
    relation_type: str
    original_confidence: float
    was_correct: bool
    timestamp: str


@dataclass
class LearningStats:
    """Statistics for a particular prediction category."""
    total: int = 0
    correct: int = 0

    @property
    def success_rate(self) -> float:
        """Bayesian estimate with Laplace smoothing."""
        return (self.correct + 1) / (self.total + 2)


class OracleLearner:
    """
    Learn from prediction outcomes to improve confidence estimates.

    Uses Bayesian updating:
    P(correct | category) = (correct + 1) / (total + 2)

    Persists learning to .komposos/oracle_learning.json
    """

    def __init__(self, persistence_path: Optional[Path] = None):
        """
        Initialize learner.

        Args:
            persistence_path: Path to persistence file. If None, uses default.
        """
        if persistence_path is None:
            persistence_path = Path.home() / ".komposos" / "oracle_learning.json"

        self.persistence_path = persistence_path
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)

        # Statistics by category
        self.by_prediction_type: Dict[str, LearningStats] = {}
        self.by_strategy: Dict[str, LearningStats] = {}
        self.by_relation: Dict[str, LearningStats] = {}

        # Detailed outcome history
        self.outcomes: List[OutcomeRecord] = []

        # Load persisted data
        self._load()

    def record_outcome(self, prediction: Prediction, was_correct: bool):
        """
        Record whether a prediction was validated.

        Args:
            prediction: The prediction that was evaluated
            was_correct: True if prediction was confirmed, False otherwise
        """
        # Update statistics
        pred_type = prediction.prediction_type.value
        strategy = prediction.strategy_name.split("+")[0]
        relation = prediction.predicted_relation

        # By prediction type
        if pred_type not in self.by_prediction_type:
            self.by_prediction_type[pred_type] = LearningStats()
        self.by_prediction_type[pred_type].total += 1
        if was_correct:
            self.by_prediction_type[pred_type].correct += 1

        # By strategy
        if strategy not in self.by_strategy:
            self.by_strategy[strategy] = LearningStats()
        self.by_strategy[strategy].total += 1
        if was_correct:
            self.by_strategy[strategy].correct += 1

        # By relation type
        if relation not in self.by_relation:
            self.by_relation[relation] = LearningStats()
        self.by_relation[relation].total += 1
        if was_correct:
            self.by_relation[relation].correct += 1

        # Record outcome
        self.outcomes.append(OutcomeRecord(
            prediction_type=pred_type,
            strategy_name=strategy,
            relation_type=relation,
            original_confidence=prediction.confidence,
            was_correct=was_correct,
            timestamp=datetime.now().isoformat(),
        ))

        # Persist
        self._save()

    def adjust_confidence(self, prediction: Prediction) -> float:
        """
        Adjust prediction confidence based on learned statistics.

        Formula:
        adjusted = 0.5 * original + 0.25 * type_confidence + 0.25 * strategy_confidence

        Returns adjusted confidence.
        """
        original = prediction.confidence
        pred_type = prediction.prediction_type.value
        strategy = prediction.strategy_name.split("+")[0]

        # Get learned success rates
        type_rate = self.by_prediction_type.get(
            pred_type, LearningStats()
        ).success_rate

        strategy_rate = self.by_strategy.get(
            strategy, LearningStats()
        ).success_rate

        # Weighted combination
        adjusted = (
            0.5 * original +
            0.25 * type_rate +
            0.25 * strategy_rate
        )

        return min(0.98, max(0.1, adjusted))

    def get_strategy_rankings(self) -> List[tuple]:
        """Get strategies ranked by success rate."""
        rankings = []
        for strategy, stats in self.by_strategy.items():
            rankings.append((strategy, stats.success_rate, stats.total))

        return sorted(rankings, key=lambda x: -x[1])

    def get_relation_rankings(self) -> List[tuple]:
        """Get relation types ranked by success rate."""
        rankings = []
        for relation, stats in self.by_relation.items():
            rankings.append((relation, stats.success_rate, stats.total))

        return sorted(rankings, key=lambda x: -x[1])

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of learning statistics."""
        total_outcomes = len(self.outcomes)
        correct_outcomes = sum(1 for o in self.outcomes if o.was_correct)

        return {
            "total_outcomes": total_outcomes,
            "correct_outcomes": correct_outcomes,
            "overall_accuracy": correct_outcomes / total_outcomes if total_outcomes > 0 else 0,
            "strategies_tracked": len(self.by_strategy),
            "prediction_types_tracked": len(self.by_prediction_type),
            "relations_tracked": len(self.by_relation),
            "best_strategy": self.get_strategy_rankings()[0] if self.by_strategy else None,
            "best_relation": self.get_relation_rankings()[0] if self.by_relation else None,
        }

    def _save(self):
        """Persist learning data to disk."""
        data = {
            "by_prediction_type": {
                k: asdict(v) for k, v in self.by_prediction_type.items()
            },
            "by_strategy": {
                k: asdict(v) for k, v in self.by_strategy.items()
            },
            "by_relation": {
                k: asdict(v) for k, v in self.by_relation.items()
            },
            "outcomes": [asdict(o) for o in self.outcomes[-1000:]],  # Keep last 1000
            "last_updated": datetime.now().isoformat(),
        }

        with open(self.persistence_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _load(self):
        """Load persisted learning data."""
        if not self.persistence_path.exists():
            return

        try:
            with open(self.persistence_path, 'r') as f:
                data = json.load(f)

            # Restore statistics
            for k, v in data.get("by_prediction_type", {}).items():
                self.by_prediction_type[k] = LearningStats(**v)

            for k, v in data.get("by_strategy", {}).items():
                self.by_strategy[k] = LearningStats(**v)

            for k, v in data.get("by_relation", {}).items():
                self.by_relation[k] = LearningStats(**v)

            # Restore outcomes
            for o in data.get("outcomes", []):
                self.outcomes.append(OutcomeRecord(**o))

        except (json.JSONDecodeError, TypeError, KeyError) as e:
            # Corrupted file - start fresh
            print(f"Warning: Could not load oracle learning data: {e}")

    def reset(self):
        """Reset all learning data."""
        self.by_prediction_type = {}
        self.by_strategy = {}
        self.by_relation = {}
        self.outcomes = []

        if self.persistence_path.exists():
            self.persistence_path.unlink()
