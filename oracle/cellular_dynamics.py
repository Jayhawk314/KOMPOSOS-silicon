# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Cellular Dynamics Strategy for KOMPOSOS-IV Oracle

Uses cellular automata as endofunctors to model dynamic processes on
the capability graph: epidemic spread, attack propagation, and
information flow.

Uses: categorical/cellular_automata.py (CellularAutomaton, EpidemicMetrics)

This activates previously dead code: cellular_automata.py

Ruliad connection: When capabilities spread through the system like an
epidemic (e.g., a new plugin adopted by many workflows), cellular
automata model the dynamics and predict which capabilities will become
dominant.
"""

from __future__ import annotations

from typing import List, Dict, Set, Any
from collections import defaultdict

from oracle.prediction import Prediction, PredictionType
from oracle.strategies import InferenceStrategy
from core.category import Category


class CellularDynamicsStrategy(InferenceStrategy):
    """
    Model capability dynamics using cellular automata.

    Treats the capability graph as a grid where each node can be in
    different states (active, dormant, emerging). The CA rules model
    how capabilities spread through the graph.

    Usage:
        strategy = CellularDynamicsStrategy(category)
        predictions = strategy.predict("emerging_capability", "established_capability")
    """

    name = "cellular_dynamics"

    def __init__(self, category: Category, steps: int = 5,
                 beta: float = 0.3, gamma: float = 0.1):
        super().__init__(category)
        self.steps = steps
        self.beta = beta
        self.gamma = gamma
        self._automaton = None

    def predict(self, source: str, target: str) -> List[Prediction]:
        """
        Predict capability adoption using cellular automata dynamics.

        Strategy:
        1. Model the capability graph as a cellular grid
        2. Set source as "infected" (emerging capability)
        3. Run CA evolution for N steps
        4. If target becomes infected, predict the adoption path
        """
        predictions = []
        existing = self._existing_morphism_pairs()

        # Model capability spread as SIR epidemic
        from categorical.cellular_automata import (
            CellularGrid, CellularAutomaton, sir_transition_rule, CellState
        )

        # Build grid from category
        objects = self.category.objects()
        morphisms = self.category.morphisms()

        if len(objects) < 2:
            return predictions

        # Assign integer IDs to objects
        obj_names = [obj.name if hasattr(obj, 'name') else str(obj) for obj in objects]
        name_to_id = {name: i for i, name in enumerate(obj_names)}

        if source not in name_to_id or target not in name_to_id:
            return predictions

        source_id = name_to_id[source]
        target_id = name_to_id[target]

        # Create adjacency for the grid (int-keyed, Set values)
        adjacency: Dict[int, Set[int]] = {i: set() for i in range(len(obj_names))}
        for mor in morphisms:
            src_name = mor.source if isinstance(mor.source, str) else getattr(mor.source, 'name', None)
            tgt_name = mor.target if isinstance(mor.target, str) else getattr(mor.target, 'name', None)
            if src_name in name_to_id and tgt_name in name_to_id:
                src_id = name_to_id[src_name]
                tgt_id = name_to_id[tgt_name]
                adjacency[src_id].add(tgt_id)
                adjacency[tgt_id].add(src_id)

        # Initialize grid: source is infected, others susceptible
        states = {i: CellState.SUSCEPTIBLE for i in range(len(obj_names))}
        states[source_id] = CellState.INFECTED

        grid = CellularGrid(
            states=states,
            adjacency=adjacency,
        )

        # Run CA with SIR rules
        rule = sir_transition_rule(beta=self.beta, gamma=self.gamma)
        automaton = CellularAutomaton(
            name="capability_spread",
            transition_rule=rule,
        )

        trajectory = automaton.evolve(grid, steps=self.steps)
        for step, evolved_grid in enumerate(trajectory[1:], 1):
            if evolved_grid.states.get(target_id) == CellState.INFECTED:
                predictions.append(Prediction(
                    source=source,
                    target=target,
                    predicted_relation=f"adopted_in_{step}_steps",
                    prediction_type=PredictionType.TEMPORAL_INFLUENCE,
                    strategy_name=self.name,
                    confidence=0.7,
                    reasoning=(
                        f"Cellular automata model predicts {target} will adopt "
                        f"{source}'s capability within {step} steps "
                        f"(SIR epidemic model with β=0.3, γ=0.1)."
                    ),
                    evidence={
                        "model": "SIR_epidemic",
                        "steps_to_adoption": step,
                        "beta": 0.3,
                        "gamma": 0.1,
                    },
                ))
                break

        return predictions
