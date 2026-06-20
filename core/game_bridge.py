# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Game Bridge: Category ↔ OpenGameCategory converter

Connects KOMPOSOS-IV Category morphisms to open games from compositional
game theory. This enables game-theoretic reasoning (Nash equilibrium,
best response) on the capability graph.

This activates: game/open_games.py, game/nash.py

Ruliad connection: When multiple capabilities compete for the same
resources or serve the same goals, game theory identifies stable
equilibria and suggests whether capabilities should be merged or
given a shared interface.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.category import Category


def category_to_open_games(category: "Category") -> List[Any]:
    """
    Convert Category morphisms to open games.

    Each morphism f: A → B becomes an open game where:
    - Input type = A (observation)
    - Output type = B (action)
    - Payoff = morphism confidence

    Args:
        category: The source Category.

    Returns:
        List of OpenGame instances.
    """
    from game.open_games import OpenGame, decision_game

    games = []
    for mor in category.morphisms():
        if mor.source != mor.target:  # Skip identity morphisms
            game = decision_game(
                name=mor.name,
                observation_type=mor.source,
                action_type=mor.target,
                utility_fn=lambda obs, action: mor.confidence,
            )
            games.append(game)

    return games


def find_nash_equilibria_in_category(category: "Category") -> List[Dict[str, Any]]:
    """
    Find Nash equilibria in the capability graph.

    Strategy:
    1. Find all pairs of morphisms that compete (same source or target)
    2. Build a 2-player game for each pair
    3. Find Nash equilibria

    Args:
        category: The source Category.

    Returns:
        List of equilibrium descriptions.
    """
    from game.nash import find_nash_equilibria, TwoPlayerGame

    equilibria = []

    # Find competing capabilities (same source, different targets)
    objects = category.objects()
    morphisms = category.morphisms()

    for obj in objects:
        # Get all morphisms from this object
        outgoing = [m for m in morphisms if m.source == obj.name]

        if len(outgoing) < 2:
            continue

        # Build 2-player game between top 2 capabilities
        for i, mor_a in enumerate(outgoing):
            for mor_b in outgoing[i + 1:]:
                game = TwoPlayerGame(
                    name=f"game_{obj.name}",
                    player_a_strategies=[mor_a.name],
                    player_b_strategies=[mor_b.name],
                )

                # Set payoffs from confidence scores
                game.set_payoff(0, 0, mor_a.confidence)
                game.set_payoff(1, 0, mor_b.confidence)

                eqs = find_nash_equilibria(game)
                for eq in eqs:
                    equilibria.append({
                        "source": obj.name,
                        "competing_capabilities": [mor_a.name, mor_b.name],
                        "equilibrium": {
                            "strategies": eq.profile,
                            "is_strict": eq.is_strict,
                            "payoffs": eq.payoffs,
                        },
                    })

    return equilibria
