# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Streaming Forecast Strategy for KOMPOSOS-IV Oracle

Uses streaming Kan extensions to make temporal predictions about how
capabilities evolve over time. Unlike static Kan extensions which
analyze the current state, streaming Kan extensions learn from
observations as they arrive.

Uses: categorical/streaming_kan.py (StreamingKanExtension, StreamingCommaCategory)

This activates previously dead code: streaming_kan.py

Ruliad connection: The system's capability graph changes over time as
plugins are added/removed. This strategy forecasts which capabilities
will become needed based on the streaming observation history.
"""

from __future__ import annotations

from typing import List, Dict, Any
import time

from oracle.prediction import Prediction, PredictionType
from oracle.strategies import InferenceStrategy
from core.category import Category


class StreamingForecastStrategy(InferenceStrategy):
    """
    Forecast capability needs using streaming Kan extensions.

    Unlike the static KanExtensionStrategy which analyzes the current
    graph, this strategy learns from temporal observations and makes
    predictions about what edges will emerge.

    Usage:
        strategy = StreamingForecastStrategy(category)
        strategy.observe("plugin_a", "event_x", weight=0.9)  # Record observation
        predictions = strategy.predict("plugin_a", "event_y")
    """

    name = "streaming_forecast"

    def __init__(self, category: Category, decay_rate: float = 0.01,
                 min_confidence: float = 0.4):
        super().__init__(category)
        self.decay_rate = decay_rate
        self.min_confidence = min_confidence
        self._kan = None
        self._observation_count = 0

    def _get_kan(self):
        """Lazy import and initialize StreamingKanExtension."""
        if self._kan is None:
            from categorical.streaming_kan import (
                StreamingKanExtension, RightKanExtension
            )
            self._kan = StreamingKanExtension(
                decay_rate=self.decay_rate,
            )
        return self._kan

    def observe(self, source: str, target: str, relation: str = "observed",
                weight: float = 1.0):
        """
        Record a streaming observation.

        Args:
            source: Source object.
            target: Target object.
            relation: Relationship type.
            weight: Observation strength (0-1).
        """
        kan = self._get_kan()
        import time
        ts = time.time()
        # StreamingKanExtension.observe expects (technique_id, timestamp, composable_targets)
        # We adapt: technique_id=source, timestamp=ts, composable_targets=[(target, weight)]
        kan.observe(source, ts, [(target, weight)])
        self._observation_count += 1

    def predict(self, source: str, target: str) -> List[Prediction]:
        """
        Predict future edges using streaming Kan extensions.

        Strategy:
        1. Get predictions from the streaming Kan extension
        2. If target appears in predictions and source has observations,
           predict the edge with temporal decay confidence
        """
        predictions = []
        existing = self._existing_morphism_pairs()
        if (source, target) in existing:
            return predictions

        kan = self._get_kan()

        # Get predictions from the streaming Kan extension
        results = kan.predict(top_k=20)
        for result in results:
            if result.get("technique") == target:
                conf = result.get("confidence", 0)
                if conf >= self.min_confidence:
                    predictions.append(Prediction(
                        source=source,
                        target=target,
                        predicted_relation=f"forecast_lan_{int(time.time())}",
                        prediction_type=PredictionType.KAN_EXTENSION,
                        strategy_name=self.name,
                        confidence=conf,
                        reasoning=(
                            f"Left Kan Extension forecast based on {result.get('n_contributors', 0)} "
                            f"supporting observations with temporal decay."
                        ),
                        evidence={
                            "method": "left_kan",
                            "confidence": conf,
                            "support_count": result.get("n_contributors", 0),
                            "observations": self._observation_count,
                            "score": result.get("score", 0),
                            "supporting_evidence": result.get("supporting_evidence", []),
                        },
                    ))
                break  # Found target, no need to continue

        return sorted(predictions, key=lambda p: -p.confidence)

    def multi_step_forecast(self, source: str, target: str,
                            steps: int = 3) -> List[Prediction]:
        """
        Forecast multi-step evolution of the capability graph.

        Args:
            source: Starting object.
            target: Goal object.
            steps: Number of forecast steps.

        Returns:
            List of predictions for each step.
        """
        predictions = []
        kan = self._get_kan()

        # Get current prediction state
        results = kan.predict(top_k=20)
        current_pred = None
        for r in results:
            if r.get("technique") == target:
                current_pred = r
                break
        if not current_pred:
            return predictions

        # Project forward with decay
        for step in range(1, steps + 1):
            decayed_conf = current_pred.get("confidence", 0) * (
                1 - self.decay_rate * step
            )
            if decayed_conf >= self.min_confidence:
                predictions.append(Prediction(
                    source=source,
                    target=target,
                    predicted_relation=f"forecast_step_{step}",
                    prediction_type=PredictionType.KAN_EXTENSION,
                    strategy_name=self.name,
                    confidence=decayed_conf,
                    reasoning=f"Step {step} forecast with temporal decay",
                    evidence={"step": step, "original_confidence": current_pred.get("confidence", 0)},
                ))

        return predictions

    def prune(self, max_age: float = 3600.0):
        """Remove old observations beyond max_age seconds."""
        kan = self._get_kan()
        kan.prune(max_age)
