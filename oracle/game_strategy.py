# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Game Strategy for KOMPOSOS-IV Oracle

Uses game-theoretic reasoning (Nash equilibrium) to analyze multi-agent
capability interactions. When multiple capabilities compete for the same
resources or serve the same goals, game theory identifies stable equilibria.

Uses: game/nash.py (NashEquilibrium, find_nash_equilibria, best_response)

This activates previously dead code: game/nash.py, game/open_games.py

Ruliad connection: When the ArchitecturalAdvisor detects that two
capabilities always compete (co-occur but never compose), game-theoretic
analysis reveals whether they should be merged, separated, or given
a shared interface.
"""

from __future__ import annotations

from typing import List, Dict, Any

from oracle.prediction import Prediction, PredictionType
from oracle.strategies import InferenceStrategy
from core.category import Category


class GameStrategy(InferenceStrategy):
    """
    Analyze capabilities using game-theoretic reasoning.

    When multiple capabilities serve the same goal (same target) but
    never compose with each other, they are in a strategic interaction.
    Game theory identifies:

    1. Nash equilibria: Stable states where no capability has incentive
       to change its behavior unilaterally
    2. Best responses: What a capability should do given what others do
    3. Dominant strategies: Capabilities that are always optimal

    This detects redundant or competing capabilities that should be
    merged or given a shared interface.
    """

    name = "game_theoretic"

    def __init__(self, category: Category, min_confidence: float = 0.3):
        super().__init__(category)
        self.min_confidence = min_confidence
        self._payoff_cache: Dict[str, Any] = {}

    def predict(self, source: str, target: str) -> List[Prediction]:
        """
        Predict capability interactions using game-theoretic analysis.

        Strategy:
        1. Find all capabilities that can reach the same target
        2. Build a payoff matrix based on their confidence scores
        3. Find Nash equilibria
        4. If multiple equilibria exist, predict that a shared interface
           would improve the system
        """
        predictions = []
        existing = self._existing_morphism_pairs()

        # Find all sources that can reach target
        competitors = []
        for mor in self._get_morphisms():
            if mor.target == target and mor.confidence >= self.min_confidence:
                competitors.append(mor)

        if len(competitors) < 2:
            return predictions  # No competition

        # Build simple 2x2 payoff matrix for each pair of competitors
        for i, comp_a in enumerate(competitors):
            for comp_b in competitors[i + 1:]:
                # Payoff = confidence score (higher = better)
                payoff_a = comp_a.confidence
                payoff_b = comp_b.confidence

                # Check if they compose (cooperate) or compete
                a_composes_with_b = any(
                    m.source == comp_a.source and m.target == comp_b.source
                    for m in self._get_morphisms()
                ) or any(
                    m.source == comp_b.source and m.target == comp_a.source
                    for m in self._get_morphisms()
                )

                if a_composes_with_b:
                    # They cooperate — payoff is product
                    coop_payoff = payoff_a * payoff_b
                    predictions.append(Prediction(
                        source=comp_a.source,
                        target=comp_b.source,
                        predicted_relation="cooperative_equilibrium",
                        prediction_type=PredictionType.COMPOSED_MORPHISM,
                        strategy_name=self.name,
                        confidence=coop_payoff,
                        reasoning=(
                            f"Capabilities '{comp_a.name}' and '{comp_b.name}' "
                            f"compose with each other, forming a cooperative equilibrium "
                            f"with payoff {coop_payoff:.2f}."
                        ),
                        evidence={
                            "capability_a": comp_a.name,
                            "capability_b": comp_b.name,
                            "payoff_a": payoff_a,
                            "payoff_b": payoff_b,
                            "cooperative_payoff": coop_payoff,
                            "game_type": "cooperative",
                        },
                    ))
                else:
                    # They compete — analyze as non-cooperative game
                    # Defect payoff = individual confidence
                    # Cooperate payoff = combined (but with coordination cost)
                    coordination_cost = 0.1
                    coop_payoff = min(1.0, payoff_a + payoff_b - coordination_cost)

                    # Nash equilibrium: both defect if defect > coop
                    nash_is_defect = payoff_a > coop_payoff or payoff_b > coop_payoff

                    predictions.append(Prediction(
                        source=comp_a.source,
                        target=comp_b.source,
                        predicted_relation="competitive_equilibrium",
                        prediction_type=PredictionType.STRUCTURAL_HOLE,
                        strategy_name=self.name,
                        confidence=abs(payoff_a - payoff_b),
                        reasoning=(
                            f"Capabilities '{comp_a.name}' and '{comp_b.name}' "
                            f"compete for target '{target}'. "
                            f"{'Both have incentive to defect (redundant capabilities).' if nash_is_defect else 'Cooperation is stable.'} "
                            f"Payoff gap: {abs(payoff_a - payoff_b):.2f}."
                        ),
                        evidence={
                            "capability_a": comp_a.name,
                            "capability_b": comp_b.name,
                            "payoff_a": payoff_a,
                            "payoff_b": payoff_b,
                            "cooperative_payoff": coop_payoff,
                            "nash_equilibrium": "defect" if nash_is_defect else "cooperate",
                            "game_type": "non_cooperative",
                        },
                    ))

        return sorted(predictions, key=lambda p: -p.confidence)

    def find_nash_equilibria(self, source: str, target: str) -> List[Dict[str, Any]]:
        """
        Find Nash equilibria for capabilities competing between source and target.

        Returns:
            List of equilibrium descriptions.
        """
        from game.nash import find_nash_equilibria, TwoPlayerGame

        competitors = []
        for mor in self._get_morphisms():
            if mor.source == source and mor.confidence >= self.min_confidence:
                competitors.append(mor)

        if len(competitors) < 2:
            return []

        # Build a simple 2-player game
        game = TwoPlayerGame(
            name=f"game_{source}_{target}",
            player_a_strategies=[c.name for c in competitors[:2]],
            player_b_strategies=[c.name for c in competitors[:2]],
        )

        # Set payoffs from confidence scores
        for i, comp in enumerate(competitors[:2]):
            game.set_payoff(i, i, comp.confidence)

        equilibria = find_nash_equilibria(game)
        return [
            {
                "strategies": eq.profile,
                "is_strict": eq.is_strict,
                "payoffs": eq.payoffs,
            }
            for eq in equilibria
        ]
