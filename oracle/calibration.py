"""
Per-strategy calibration for score combination.

Measures each strategy's predictive power and learns optimal weights.
"""
from typing import Dict, List, Tuple
import json
from pathlib import Path
from dataclasses import dataclass, asdict
import numpy as np


@dataclass
class StrategyCalibration:
    """Calibration data for a single strategy."""
    name: str
    weight: float = 1.0          # Learned weight (1.0 = neutral)
    precision: float = 0.0        # TP / (TP + FP)
    recall: float = 0.0           # TP / (TP + FN)
    auroc: float = 0.0            # Strategy-specific AUROC
    n_predictions: int = 0        # How many predictions made
    n_correct: int = 0            # How many were correct

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


class StrategyCalibrator:
    """
    Learns optimal weights for each strategy based on historical performance.

    Usage:
        calibrator = StrategyCalibrator()

        # During validation:
        for true_edge in ground_truth:
            predictions = oracle.predict(src, tgt)
            calibrator.record_predictions(predictions, is_true_edge=True)

        # Learn weights
        calibrator.calibrate()
        calibrator.save("strategy_weights.json")
    """

    def __init__(self, calibration_file: str = None):
        self.calibrations: Dict[str, StrategyCalibration] = {}
        self.history: List[dict] = []  # Raw prediction history

        if calibration_file and Path(calibration_file).exists():
            self.load(calibration_file)

    def record_prediction(self, strategy_name: str, confidence: float,
                         is_correct: bool, pair_key: tuple):
        """Record a single prediction from a strategy."""
        if strategy_name not in self.calibrations:
            self.calibrations[strategy_name] = StrategyCalibration(name=strategy_name)

        self.history.append({
            'strategy': strategy_name,
            'confidence': confidence,
            'is_correct': is_correct,
            'pair': pair_key
        })

        cal = self.calibrations[strategy_name]
        cal.n_predictions += 1
        if is_correct:
            cal.n_correct += 1

    def calibrate(self):
        """
        Compute optimal weights for each strategy.

        Uses precision as the primary signal:
        - High precision strategies get higher weight
        - Strategies with low precision get downweighted
        """
        if not self.history:
            print("Warning: No prediction history to calibrate from")
            return

        # Group by strategy
        by_strategy = {}
        for record in self.history:
            strat = record['strategy']
            if strat not in by_strategy:
                by_strategy[strat] = {'correct': [], 'incorrect': []}

            if record['is_correct']:
                by_strategy[strat]['correct'].append(record['confidence'])
            else:
                by_strategy[strat]['incorrect'].append(record['confidence'])

        # Compute precision and weight for each strategy
        for strategy_name, cal in self.calibrations.items():
            if cal.n_predictions == 0:
                cal.weight = 0.0
                continue

            # Precision = how often this strategy is right
            cal.precision = cal.n_correct / cal.n_predictions if cal.n_predictions > 0 else 0.0

            # Weight based on precision
            # Map precision [0, 1] to weight [0, 2]
            # precision=0.5 (random) → weight=1.0 (neutral)
            # precision=0.75 → weight=1.5
            # precision=1.0 → weight=2.0
            # precision=0.0 → weight=0.0
            if cal.precision > 0.5:
                # Better than random: boost
                cal.weight = 1.0 + 2 * (cal.precision - 0.5)
            else:
                # Worse than random: penalize
                cal.weight = 2 * cal.precision

            # Compute per-strategy AUROC if we have enough data
            if strategy_name in by_strategy:
                correct_scores = by_strategy[strategy_name]['correct']
                incorrect_scores = by_strategy[strategy_name]['incorrect']

                if correct_scores and incorrect_scores:
                    cal.auroc = self._compute_auroc(correct_scores, incorrect_scores)

        print(f"\n[Calibration] Learned weights for {len(self.calibrations)} strategies:")
        for name, cal in sorted(self.calibrations.items(), key=lambda x: x[1].weight, reverse=True):
            print(f"  {name:40s} weight={cal.weight:.3f} precision={cal.precision:.3f} ({cal.n_correct}/{cal.n_predictions})")

    def _compute_auroc(self, positive_scores: List[float], negative_scores: List[float]) -> float:
        """Compute AUROC for a single strategy."""
        if not positive_scores or not negative_scores:
            return 0.5

        # Count how often positive > negative
        better = 0
        total = 0
        for pos in positive_scores:
            for neg in negative_scores:
                if pos > neg:
                    better += 1
                elif pos == neg:
                    better += 0.5
                total += 1

        return better / total if total > 0 else 0.5

    def get_weight(self, strategy_name: str) -> float:
        """Get learned weight for a strategy (1.0 if unknown)."""
        if strategy_name in self.calibrations:
            return self.calibrations[strategy_name].weight
        return 1.0

    def save(self, filepath: str):
        """Save calibration to JSON."""
        data = {
            'calibrations': {name: cal.to_dict() for name, cal in self.calibrations.items()},
            'n_history': len(self.history)
        }
        Path(filepath).write_text(json.dumps(data, indent=2))
        print(f"[Calibration] Saved to {filepath}")

    def load(self, filepath: str):
        """Load calibration from JSON."""
        data = json.loads(Path(filepath).read_text())
        self.calibrations = {
            name: StrategyCalibration.from_dict(cal_data)
            for name, cal_data in data['calibrations'].items()
        }
        print(f"[Calibration] Loaded {len(self.calibrations)} strategy weights from {filepath}")


def weighted_average(scores: List[Tuple[str, float]], calibrator: StrategyCalibrator = None) -> float:
    """
    Compute weighted average of strategy scores.

    Args:
        scores: List of (strategy_name, confidence) tuples
        calibrator: Optional calibrator with learned weights

    Returns:
        Weighted average confidence
    """
    if not scores:
        return 0.0

    if calibrator is None:
        # Fallback to simple average
        return sum(conf for _, conf in scores) / len(scores)

    # Weighted average using learned weights
    total_weight = 0.0
    weighted_sum = 0.0

    for strategy_name, confidence in scores:
        weight = calibrator.get_weight(strategy_name)
        weighted_sum += weight * confidence
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return weighted_sum / total_weight
