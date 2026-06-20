#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Uncertainty quantification for drug repurposing predictions.

Provides confidence intervals and calibrated probabilities for predictions.

Methods:
1. Bootstrap confidence intervals (95% CI via resampling)
2. Wilson score intervals (for proportions)
3. Ensemble disagreement (strategy variance as uncertainty proxy)
4. Evidence-based uncertainty (tier-weighted confidence)
"""

import numpy as np
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from scipy import stats


@dataclass
class UncertaintyEstimate:
    """Uncertainty estimate for a prediction."""
    point_estimate: float
    lower_bound: float
    upper_bound: float
    std_error: float
    method: str
    evidence_strength: str  # "strong", "moderate", "weak"

    @property
    def interval_width(self) -> float:
        """Width of the confidence interval."""
        return self.upper_bound - self.lower_bound

    @property
    def relative_uncertainty(self) -> float:
        """Relative uncertainty (interval width / point estimate)."""
        if self.point_estimate > 0:
            return self.interval_width / self.point_estimate
        return float('inf')


class UncertaintyQuantifier:
    """
    Quantify uncertainty in drug repurposing predictions.

    Combines multiple uncertainty estimation methods:
    - Bootstrap for confidence intervals
    - Wilson intervals for binary outcomes
    - Evidence tier-based confidence adjustment
    - Ensemble variance for multi-strategy predictions
    """

    def __init__(self, confidence_level: float = 0.95):
        """
        Initialize uncertainty quantifier.

        Args:
            confidence_level: Confidence level for intervals (default 0.95)
        """
        self.confidence_level = confidence_level
        self.alpha = 1.0 - confidence_level

    def bootstrap_confidence_interval(
        self,
        predictions: List[float],
        n_bootstrap: int = 1000,
        method: str = "percentile"
    ) -> Tuple[float, float, float]:
        """
        Compute bootstrap confidence interval.

        Args:
            predictions: List of prediction scores
            n_bootstrap: Number of bootstrap samples
            method: "percentile" or "bca" (bias-corrected accelerated)

        Returns:
            (mean, lower_bound, upper_bound)
        """
        predictions = np.array(predictions)
        n = len(predictions)

        if n == 0:
            return (0.0, 0.0, 0.0)

        # Bootstrap resampling
        bootstrap_means = []
        for _ in range(n_bootstrap):
            sample = np.random.choice(predictions, size=n, replace=True)
            bootstrap_means.append(np.mean(sample))

        bootstrap_means = np.array(bootstrap_means)

        # Compute confidence interval
        if method == "percentile":
            lower = np.percentile(bootstrap_means, 100 * self.alpha / 2)
            upper = np.percentile(bootstrap_means, 100 * (1 - self.alpha / 2))
        else:
            # BCa method (more accurate but complex)
            # For simplicity, fall back to percentile
            lower = np.percentile(bootstrap_means, 100 * self.alpha / 2)
            upper = np.percentile(bootstrap_means, 100 * (1 - self.alpha / 2))

        mean = np.mean(predictions)

        return (mean, lower, upper)

    def wilson_score_interval(
        self,
        successes: int,
        trials: int
    ) -> Tuple[float, float, float]:
        """
        Wilson score confidence interval for proportions.

        More accurate than normal approximation for small samples.

        Args:
            successes: Number of successes
            trials: Total number of trials

        Returns:
            (proportion, lower_bound, upper_bound)
        """
        if trials == 0:
            return (0.0, 0.0, 0.0)

        p = successes / trials

        # Z-score for desired confidence level
        z = stats.norm.ppf(1 - self.alpha / 2)

        denominator = 1 + z**2 / trials
        center = (p + z**2 / (2 * trials)) / denominator
        margin = z * np.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2)) / denominator

        lower = max(0.0, center - margin)
        upper = min(1.0, center + margin)

        return (p, lower, upper)

    def ensemble_uncertainty(
        self,
        strategy_predictions: List[float]
    ) -> Tuple[float, float]:
        """
        Estimate uncertainty from ensemble disagreement.

        High variance among strategies indicates high uncertainty.

        Args:
            strategy_predictions: Predictions from different strategies

        Returns:
            (mean_prediction, uncertainty_score)
        """
        if not strategy_predictions:
            return (0.0, 1.0)

        predictions = np.array(strategy_predictions)
        mean = np.mean(predictions)
        std = np.std(predictions)

        # Uncertainty score: normalized std deviation
        # High std = high uncertainty
        uncertainty = min(1.0, std / 0.5)  # Normalize to [0, 1]

        return (mean, uncertainty)

    def evidence_based_confidence(
        self,
        evidence_tiers: List[str],
        base_confidence: float
    ) -> Tuple[float, str]:
        """
        Adjust confidence based on evidence quality.

        Args:
            evidence_tiers: List of evidence tier labels for supporting evidence
            base_confidence: Base prediction confidence

        Returns:
            (adjusted_confidence, evidence_strength)
        """
        # Evidence tier weights
        tier_weights = {
            "MEASURED": 1.0,      # No downgrade
            "ESTABLISHED": 0.9,   # Slight downgrade
            "INFERRED": 0.7,      # Moderate downgrade
            "HYPOTHESIS": 0.5,    # Significant downgrade
            "SPECULATIVE": 0.3,   # Heavy downgrade
            "NOISE": 0.1          # Minimal confidence
        }

        if not evidence_tiers:
            return (base_confidence * 0.3, "weak")

        # Compute weighted average of evidence quality
        weights = [tier_weights.get(tier, 0.3) for tier in evidence_tiers]
        avg_weight = np.mean(weights)

        # Adjust confidence
        adjusted = base_confidence * avg_weight

        # Classify strength
        if avg_weight >= 0.8:
            strength = "strong"
        elif avg_weight >= 0.5:
            strength = "moderate"
        else:
            strength = "weak"

        return (adjusted, strength)

    def quantify_prediction_uncertainty(
        self,
        prediction: float,
        strategy_predictions: List[float],
        evidence_tiers: List[str],
        n_bootstrap: int = 1000
    ) -> UncertaintyEstimate:
        """
        Comprehensive uncertainty quantification for a prediction.

        Combines:
        1. Bootstrap CI from strategy predictions
        2. Ensemble disagreement
        3. Evidence quality adjustment

        Args:
            prediction: Final prediction score
            strategy_predictions: Individual strategy predictions
            evidence_tiers: Evidence tiers for supporting evidence
            n_bootstrap: Bootstrap iterations

        Returns:
            UncertaintyEstimate with confidence interval and metadata
        """
        # Bootstrap confidence interval
        if len(strategy_predictions) > 1:
            mean, lower, upper = self.bootstrap_confidence_interval(
                strategy_predictions, n_bootstrap
            )
            std_error = np.std(strategy_predictions) / np.sqrt(len(strategy_predictions))
        else:
            # Fallback for single prediction
            mean = prediction
            std_error = 0.2  # Assume 20% uncertainty
            lower = max(0.0, mean - 1.96 * std_error)
            upper = min(1.0, mean + 1.96 * std_error)

        # Evidence-based adjustment
        adjusted_confidence, evidence_strength = self.evidence_based_confidence(
            evidence_tiers, prediction
        )

        # Adjust bounds based on evidence quality
        if evidence_strength == "weak":
            # Widen intervals for weak evidence
            margin = (upper - lower) / 2
            lower = max(0.0, mean - margin * 1.5)
            upper = min(1.0, mean + margin * 1.5)
        elif evidence_strength == "strong":
            # Narrow intervals for strong evidence
            margin = (upper - lower) / 2
            lower = max(0.0, mean - margin * 0.7)
            upper = min(1.0, mean + margin * 0.7)

        return UncertaintyEstimate(
            point_estimate=prediction,
            lower_bound=lower,
            upper_bound=upper,
            std_error=std_error,
            method="bootstrap+evidence",
            evidence_strength=evidence_strength
        )

    def calibration_analysis(
        self,
        predictions: List[float],
        outcomes: List[int],
        n_bins: int = 10
    ) -> Dict[str, float]:
        """
        Analyze calibration of predictions.

        Perfect calibration: predicted probability matches observed frequency.

        Args:
            predictions: Predicted probabilities (0-1)
            outcomes: Actual outcomes (0 or 1)
            n_bins: Number of bins for calibration curve

        Returns:
            Dictionary with calibration metrics
        """
        predictions = np.array(predictions)
        outcomes = np.array(outcomes)

        # Bin predictions
        bins = np.linspace(0, 1, n_bins + 1)
        bin_indices = np.digitize(predictions, bins[:-1]) - 1

        calibration_error = []
        bin_accuracies = []

        for i in range(n_bins):
            mask = bin_indices == i
            if np.sum(mask) > 0:
                bin_predictions = predictions[mask]
                bin_outcomes = outcomes[mask]

                mean_predicted = np.mean(bin_predictions)
                mean_observed = np.mean(bin_outcomes)

                calibration_error.append(abs(mean_predicted - mean_observed))
                bin_accuracies.append(mean_observed)

        # Expected Calibration Error (ECE)
        ece = np.mean(calibration_error) if calibration_error else 0.0

        # Maximum Calibration Error (MCE)
        mce = np.max(calibration_error) if calibration_error else 0.0

        return {
            "expected_calibration_error": ece,
            "maximum_calibration_error": mce,
            "n_bins": n_bins,
            "bin_accuracies": bin_accuracies
        }


def format_uncertainty_report(estimate: UncertaintyEstimate) -> str:
    """
    Format uncertainty estimate as human-readable report.

    Args:
        estimate: UncertaintyEstimate object

    Returns:
        Formatted string
    """
    report = f"""
Prediction: {estimate.point_estimate:.3f}
95% Confidence Interval: [{estimate.lower_bound:.3f}, {estimate.upper_bound:.3f}]
Standard Error: {estimate.std_error:.3f}
Interval Width: {estimate.interval_width:.3f}
Relative Uncertainty: {estimate.relative_uncertainty:.1%}
Evidence Strength: {estimate.evidence_strength.upper()}
Method: {estimate.method}
    """.strip()

    return report


# Example usage
if __name__ == "__main__":
    print("="*70)
    print("UNCERTAINTY QUANTIFICATION DEMO")
    print("="*70)

    quantifier = UncertaintyQuantifier(confidence_level=0.95)

    # Example: Multiple strategy predictions for a drug-disease pair
    strategy_predictions = [0.72, 0.65, 0.78, 0.69, 0.74, 0.71, 0.68, 0.76]
    evidence_tiers = ["MEASURED", "MEASURED", "ESTABLISHED", "INFERRED"]

    print("\nStrategy predictions:", strategy_predictions)
    print("Evidence tiers:", evidence_tiers)

    # Quantify uncertainty
    uncertainty = quantifier.quantify_prediction_uncertainty(
        prediction=np.mean(strategy_predictions),
        strategy_predictions=strategy_predictions,
        evidence_tiers=evidence_tiers,
        n_bootstrap=1000
    )

    print("\n" + format_uncertainty_report(uncertainty))

    # Wilson score interval example
    print("\n" + "="*70)
    print("WILSON SCORE INTERVAL EXAMPLE")
    print("="*70)

    successes = 38
    trials = 44

    prop, lower, upper = quantifier.wilson_score_interval(successes, trials)

    print(f"\nSuccesses: {successes}/{trials}")
    print(f"Proportion: {prop:.3f}")
    print(f"95% CI: [{lower:.3f}, {upper:.3f}]")

    print("\n" + "="*70)
