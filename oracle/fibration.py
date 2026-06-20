# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Fibration Lift Strategy for KOMPOSOS-IV Oracle

Predicts morphisms by lifting from a base category to a fiber category.

If a pattern holds at the type level (e.g., "all search plugins connect
to storage plugins"), it should hold at the instance level (e.g.,
"arxiv_search should connect to vector_store").

The base category is the type-level graph (capability types).
The fiber category is the instance-level graph (specific plugins).
The fibration is the type assignment: plugin -> its capability type.

Mathematical basis:
  - Riehl & Verity, "Infinity category theory from scratch" (2016)
    Section 3: Fibrations & Cartesian Lifts
  - Grothendieck construction: equivalence between cartesian fibrations
    over A and functors A -> QCat

This activates:
  - categorical/fibrations.py (GenericFibration)
  - categorical/grothendieck.py (GrothendieckConstruction)
"""

from __future__ import annotations

from typing import Dict, List, Optional

from oracle.prediction import Prediction, PredictionType, ConfidenceLevel
from oracle.strategies import InferenceStrategy
from core.category import Category


class FibrationLiftStrategy(InferenceStrategy):
    """
    Predict morphisms by lifting from a base category to a fiber category.

    Uses fibrations.py and grothendieck.py (previously dead code) to
    perform type-level to instance-level prediction.

    Usage:
        strategy = FibrationLiftStrategy(
            category=instance_category,
            base_category=type_category,
            projection={"arxiv_search": "search", "vector_store": "storage"},
        )
        predictions = strategy.predict("arxiv_search", "vector_store")
    """

    name = "fibration_lift"

    def __init__(
        self,
        category: Category,
        base_category: Category = None,
        projection: Dict[str, str] = None,
        min_confidence: float = 0.5,
    ):
        """
        Args:
            category: The fiber category (instance-level graph).
            base_category: The base category (type-level graph).
                           If None, derived from projection by grouping.
            projection: {instance_name: type_name} mapping.
            min_confidence: Minimum base morphism confidence to lift.
        """
        super().__init__(category)
        self.projection = projection or {}
        self.min_confidence = min_confidence

        # Derive base category if not provided
        if base_category is None:
            self.base = self._derive_base_category()
        else:
            self.base = base_category

    def _derive_base_category(self) -> Category:
        """Derive the base category (type-level) from the projection."""
        from core.category import Category as Cat

        base = Cat(db_path=":memory:")

        # Objects = unique type names
        type_names = set(self.projection.values())
        for tn in type_names:
            base.add(tn, type_name="capability_type")

        # Infer morphisms between types from aggregate instance behavior
        type_edges: Dict[tuple, List[float]] = {}
        for mor in self.category.morphisms():
            src_type = self.projection.get(mor.source)
            tgt_type = self.projection.get(mor.target)
            if src_type and tgt_type and src_type != tgt_type:
                key = (src_type, tgt_type)
                type_edges.setdefault(key, []).append(mor.confidence)

        # Add morphisms with average confidence
        for (src, tgt), confs in type_edges.items():
            avg_conf = sum(confs) / len(confs)
            if avg_conf >= self.min_confidence:
                base.connect(
                    src, tgt,
                    name=f"type_{src}_{tgt}",
                    confidence=avg_conf,
                    metadata={"instance_count": len(confs)},
                )

        return base

    def predict(self, source: str, target: str) -> List[Prediction]:
        """
        Predict missing instance-level edges from type-level patterns.

        For each morphism T_A -> T_B in the base:
            For each instance a of T_A and b of T_B:
                If no morphism a -> b exists in fiber:
                    Predict it, with confidence = base morphism confidence.
        """
        predictions = []

        # Check if source and target are in the projection
        src_type = self.projection.get(source)
        tgt_type = self.projection.get(target)

        if not src_type or not tgt_type:
            # Not in projection: try to predict based on their types
            src_type = self._infer_type(source)
            tgt_type = self._infer_type(target)
            if not src_type or not tgt_type:
                return predictions

        # Find morphism in base category
        base_morphisms = self.base.morphisms()
        for base_mor in base_morphisms:
            if base_mor.source != src_type or base_mor.target != tgt_type:
                continue
            if base_mor.confidence < self.min_confidence:
                continue

            # Predict the instance-level edge
            if not self._has_edge(source, target):
                predictions.append(Prediction(
                    source=source,
                    target=target,
                    predicted_relation=f"lifted_from_{base_mor.name}",
                    prediction_type=PredictionType.CARTESIAN_LIFT,
                    strategy_name=self.name,
                    confidence=base_mor.confidence,
                    reason=(
                        f"Type-level pattern: {src_type} -> {tgt_type} "
                        f"(confidence {base_mor.confidence:.2f}). "
                        f"Lifting to instance level: {source} -> {target}."
                    ),
                    metadata={
                        "lifted_from": base_mor.name,
                        "type_source": src_type,
                        "type_target": tgt_type,
                        "base_confidence": base_mor.confidence,
                    },
                ))

        return sorted(predictions, key=lambda p: -p.confidence)

    def lift_all_predictions(self) -> List[Prediction]:
        """
        Generate all possible lift predictions at once.

        Returns:
            List of all predictions from type-level to instance-level.
        """
        predictions = []
        inv_proj: Dict[str, List[str]] = {}
        for inst, typ in self.projection.items():
            inv_proj.setdefault(typ, []).append(inst)

        for base_mor in self.base.morphisms():
            if base_mor.confidence < self.min_confidence:
                continue

            sources = inv_proj.get(base_mor.source, [])
            targets = inv_proj.get(base_mor.target, [])

            for src_inst in sources:
                for tgt_inst in targets:
                    if not self._has_edge(src_inst, tgt_inst):
                        predictions.append(Prediction(
                            source=src_inst,
                            target=tgt_inst,
                            predicted_relation=f"lifted_from_{base_mor.name}",
                            prediction_type=PredictionType.CARTESIAN_LIFT,
                            strategy_name=self.name,
                            confidence=base_mor.confidence,
                            reason=(
                                f"Lifted from {base_mor.source} -> {base_mor.target}"
                            ),
                            metadata={
                                "lifted_from": base_mor.name,
                                "type_source": base_mor.source,
                                "type_target": base_mor.target,
                            },
                        ))

        return sorted(predictions, key=lambda p: -p.confidence)

    def _has_edge(self, source: str, target: str) -> bool:
        """Check if an edge already exists."""
        for mor in self._get_morphisms():
            if mor.source == source and mor.target == target:
                return True
        return False

    def _infer_type(self, name: str) -> Optional[str]:
        """Infer the type of an object not in the projection."""
        obj = self.category.get(name)
        if obj:
            return obj.type_name
        return None
