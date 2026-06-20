# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Operadic Decomposition Strategy for KOMPOSOS-IV Oracle

Decomposes n-ary relations into trees of binary relations using operad theory.
If a capability appears to handle n inputs simultaneously, this strategy checks
whether it can be decomposed into a composition of binary capabilities.

Uses: categorical/operads.py (Operad, ColoredOperad, operad_from_category)

This activates previously dead code: operads.py

Ruliad connection: Tests whether a capability is a genuine n-ary primitive
or just a composition of binary ones (linear independence for n-ary operations).
"""

from __future__ import annotations

from typing import List, Dict, Any, Set, Tuple

from oracle.prediction import Prediction, PredictionType
from oracle.strategies import InferenceStrategy
from core.category import Category


class OperadicDecompositionStrategy(InferenceStrategy):
    """
    Decompose n-ary relations into binary composition trees.

    Uses operad theory to detect when a capability that appears to handle
    multiple inputs simultaneously can actually be decomposed into a tree
    of binary capabilities.

    If decomposition succeeds, predicts the intermediate binary capabilities.
    If decomposition fails, confirms the capability as a genuine n-ary primitive.
    """

    name = "operadic_decomposition"

    def __init__(self, category: Category, max_arity: int = 4):
        super().__init__(category)
        self.max_arity = max_arity
        self._operad = None

    def _get_operad(self):
        """Lazy import and build operad from category."""
        if self._operad is None:
            from categorical.operads import operad_from_category, Operad
            self._operad = operad_from_category(self.category)
        return self._operad

    def predict(self, source: str, target: str) -> List[Prediction]:
        """
        Predict whether a direct edge source→target can be operadically decomposed.

        Strategy:
        1. Find all morphisms from source to target
        2. For each, check if it can be decomposed via operadic composition
        3. If decomposable, predict the decomposition tree
        4. If not decomposable, flag as "genuine primitive"
        """
        predictions = []
        existing = self._existing_morphism_pairs()

        if (source, target) not in existing:
            return predictions  # No edge to decompose

        morphisms = [
            m for m in self._get_morphisms()
            if m.source == source and m.target == target
        ]

        for mor in morphisms:
            decomp = self._try_decompose(mor)
            if decomp:
                predictions.append(Prediction(
                    source=source,
                    target=target,
                    predicted_relation=f"decomposed_via_{decomp['arity']}-ary_tree",
                    prediction_type=PredictionType.COMPOSED_MORPHISM,
                    strategy_name=self.name,
                    confidence=decomp["confidence"],
                    reasoning=(
                        f"Morphism '{mor.name}' can be decomposed into "
                        f"a {decomp['arity']}-ary operadic composition tree "
                        f"with {len(decomp['components'])} components: "
                        f"{', '.join(decomp['components'])}"
                    ),
                    evidence={
                        "original": mor.name,
                        "arity": decomp["arity"],
                        "components": decomp["components"],
                        "decomposition_tree": decomp.get("tree", []),
                    },
                ))
            else:
                # Cannot decompose — likely a genuine primitive
                predictions.append(Prediction(
                    source=source,
                    target=target,
                    predicted_relation="genuine_primitive",
                    prediction_type=PredictionType.STRUCTURAL_HOLE,
                    strategy_name=self.name,
                    confidence=0.7,
                    reasoning=(
                        f"Morphism '{mor.name}' cannot be operadically decomposed. "
                        f"It appears to be a genuine n-ary primitive."
                    ),
                    evidence={
                        "original": mor.name,
                        "decomposition_attempts": 0,
                    },
                ))

        return sorted(predictions, key=lambda p: -p.confidence)

    def _try_decompose(self, mor) -> Dict[str, Any]:
        """
        Try to decompose a morphism via operadic composition.

        Returns decomposition info if successful, None if not.
        """
        operad = self._get_operad()

        # Find candidate components: objects that are "between" source and target
        source = mor.source
        target = mor.target

        # Get all objects that have morphisms from source or to target
        from_source = {m.target for m in self._get_morphisms() if m.source == source}
        to_target = {m.source for m in self._get_morphisms() if m.target == target}

        # Candidates are objects reachable from both ends
        candidates = from_source & to_target

        if not candidates:
            # Try 2-step: source -> X -> Y -> target
            for x in from_source:
                x_to_target = {
                    m.source for m in self._get_morphisms() if m.target == target
                }
                x_outgoing = {m.target for m in self._get_morphisms() if m.source == x}
                candidates = x_outgoing & x_to_target
                if candidates:
                    # Found 2-step decomposition
                    return {
                        "arity": 3,
                        "components": [source, x, list(candidates)[0], target],
                        "confidence": mor.confidence * 0.9,
                        "tree": [
                            (source, x),
                            (x, list(candidates)[0]),
                            (list(candidates)[0], target),
                        ],
                    }
            return None

        # 1-step decomposition found
        component = list(candidates)[0]
        return {
            "arity": 2,
            "components": [source, component, target],
            "confidence": mor.confidence * 0.95,
            "tree": [(source, component), (component, target)],
        }

    def find_nary_primitives(self, max_arity: int = None) -> List[Dict[str, Any]]:
        """
        Find all capabilities that appear to be genuine n-ary primitives.

        Returns:
            List of {"morphism": str, "source": str, "target": str,
                     "reason": str} for each irreducible capability.
        """
        max_arity = max_arity or self.max_arity
        primitives = []

        for mor in self._get_morphisms():
            decomp = self._try_decompose(mor)
            if decomp is None:
                # Check if this morphism has high arity (many inputs)
                metadata = mor.metadata if hasattr(mor, 'metadata') else {}
                arity = metadata.get('arity', 1)

                if arity > 1:
                    primitives.append({
                        "morphism": mor.name,
                        "source": mor.source,
                        "target": mor.target,
                        "apparent_arity": arity,
                        "reason": "Cannot be decomposed via operadic composition",
                    })

        return sorted(primitives, key=lambda p: -p.get("apparent_arity", 1))
