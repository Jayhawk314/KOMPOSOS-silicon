# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Topos Logic Strategy for KOMPOSOS-IV Oracle

Reasons via intuitionistic logic when classical logic fails.

Uses:
  - categorical/topos_logic.py (ToposLogic, HeytingAlgebra)
  - categorical/presheaf_topos.py (PresheafTopos, Sieve, subobject classifier)

Riehl-Verity connection:
  The subobject classifier in a presheaf topos encodes multi-valued truth.
  Truth values are sieves (sets of perspectives), not booleans.
  This gives the right semantics for uncertain reasoning.

When to use:
  - Claims with partial evidence AND partial counter-evidence
  - Claims where excluded middle fails (P ∨ ¬P ≠ TRUE)
  - Claims requiring intuitionistic implication (P → Q = ¬P ∨ Q)

This activates:
  - categorical/topos_logic.py (previously dead)
  - categorical/presheaf_topos.py (previously dead)
"""

from __future__ import annotations

from typing import List, Dict, Any

from oracle.prediction import Prediction, PredictionType, ConfidenceLevel
from oracle.strategies import InferenceStrategy, REPURPOSING_INTERMEDIATE_TYPES
from core.category import Category


class ToposLogicStrategy(InferenceStrategy):
    """
    Reason via intuitionistic logic for partial-evidence claims.

    Uses the Heyting algebra from topos_logic.py to give nuanced
    truth values when classical boolean reasoning is insufficient.

    Usage:
        strategy = ToposLogicStrategy(category)
        predictions = strategy.predict("A", "B")
        # Returns predictions with multi-valued truth from the subobject classifier
    """

    name = "topos_logic"

    def __init__(self, category: Category):
        super().__init__(category)
        self._topos_logic = None
        self._presheaf_topos = None

    def _get_topos_logic(self):
        """Lazy import and initialize ToposLogic."""
        if self._topos_logic is None:
            from categorical.topos_logic import ToposLogic
            self._topos_logic = ToposLogic(self.category)
        return self._topos_logic

    def _get_presheaf_topos(self):
        """Lazy import and initialize PresheafTopos."""
        if self._presheaf_topos is None:
            from categorical.presheaf_topos import PresheafTopos
            try:
                self._presheaf_topos = PresheafTopos.from_enriched_category(
                    self.category
                )
            except Exception:
                self._presheaf_topos = None
        return self._presheaf_topos

    def predict(self, source: str, target: str) -> List[Prediction]:
        """
        Predict using intuitionistic logic.

        Strategy:
        For Drug->Disease pairs (repurposing task):
          - ONLY use pathway-based prediction (no direct edge lookup)
          - This avoids data leakage: the "treats" edge IS the ground truth
        For all other pairs:
          - Full logic: direct edge, Heyting algebra, presheaf, pathway
        """
        predictions = []

        # Detect Drug->Disease pairs to avoid data leakage
        source_obj = self.category.get(source)
        target_obj = self.category.get(target)
        is_repurposing_pair = (
            source_obj and target_obj
            and source_obj.type_name == "Drug"
            and target_obj.type_name == "Disease"
        )

        if is_repurposing_pair:
            # For Drug->Disease: ONLY pathway prediction (no leakage)
            pathway_result = self._check_pathway_support(source, target)
            if pathway_result:
                predictions.append(Prediction(
                    source=source,
                    target=target,
                    predicted_relation="pathway_supported",
                    prediction_type=PredictionType.COMPOSED_MORPHISM,
                    strategy_name=self.name,
                    confidence=pathway_result["confidence"],
                    reasoning=pathway_result["reason"],
                    evidence={
                        "truth_type": "pathway",
                        "num_paths": pathway_result.get("num_paths", 0),
                        "avg_path_confidence": pathway_result.get("avg_confidence", 0),
                    },
                ))
            return predictions

        # For non-repurposing pairs: full intuitionistic logic
        topos = self._get_topos_logic()

        # Step 1: Check classical truth (direct edge)
        direct = self._has_direct_edge(source, target)
        if direct:
            predictions.append(Prediction(
                source=source,
                target=target,
                predicted_relation="classically_true",
                prediction_type=PredictionType.KAN_EXTENSION,
                strategy_name=self.name,
                confidence=direct.confidence,
                reasoning=f"Direct morphism exists (confidence={direct.confidence:.2f})",
                evidence={"truth_type": "classical"},
            ))

        # Step 2: Check Heyting algebra for partial truth
        heyting_result = self._check_heyting(source, target, topos)
        if heyting_result:
            predictions.append(Prediction(
                source=source,
                target=target,
                predicted_relation=f"heyting_{heyting_result['truth_type']}",
                prediction_type=PredictionType.KAN_EXTENSION,
                strategy_name=self.name,
                confidence=heyting_result["confidence"],
                reasoning=heyting_result["reason"],
                evidence={
                    "truth_type": heyting_result["truth_type"],
                    "excluded_middle_holds": heyting_result.get(
                        "excluded_middle_holds", True
                    ),
                },
            ))

        # Step 3: Check presheaf subobject classifier
        presheaf_result = self._check_subobject_classifier(source, target)
        if presheaf_result:
            predictions.append(Prediction(
                source=source,
                target=target,
                predicted_relation="sieve_truth",
                prediction_type=PredictionType.CARTESIAN_LIFT,
                strategy_name=self.name,
                confidence=presheaf_result["confidence"],
                reasoning=presheaf_result["reason"],
                evidence={
                    "truth_type": "sieve",
                    "perspectives": presheaf_result.get("perspectives", []),
                    "support_fraction": presheaf_result.get("support_fraction", 0),
                },
            ))

        return sorted(predictions, key=lambda p: -p.confidence)

    def _has_direct_edge(self, source: str, target: str):
        """Check for a direct morphism."""
        for mor in self._get_morphisms():
            if mor.source == source and mor.target == target:
                return mor
        return None

    def _check_heyting(
        self, source: str, target: str, topos
    ) -> Dict[str, Any]:
        """
        Check the Heyting algebra for partial truth.

        Returns dict with truth_type, confidence, reason, etc.
        """
        try:
            # Check if excluded middle fails for these objects
            failures = topos.where_excluded_middle_fails()

            source_fails = any(f["object"] == source for f in failures)
            target_fails = any(f["object"] == target for f in failures)

            if source_fails or target_fails:
                # Excluded middle fails -- use intuitionistic truth
                return {
                    "truth_type": "intuitionistic_partial",
                    "confidence": 0.5,  # Maximum partial truth
                    "reason": (
                        f"Excluded middle fails for "
                        f"{'source' if source_fails else 'target'}. "
                        f"Using intuitionistic partial truth."
                    ),
                    "excluded_middle_holds": False,
                    "failures": failures[:5],
                }

            # Check intuitionistic implication: source -> target
            # In Heyting algebra: ¬source ∨ target
            source_negation = topos.negate(source)
            if source_negation:
                return {
                    "truth_type": "negation_implication",
                    "confidence": 0.6,
                    "reason": (
                        f"Intuitionistic implication: ¬{source} ∨ {target}. "
                        f"Negation of source has support."
                    ),
                    "excluded_middle_holds": True,
                }

        except Exception:
            pass

        return None

    def _check_subobject_classifier(
        self, source: str, target: str
    ) -> Dict[str, Any]:
        """
        Use the presheaf subobject classifier for multi-perspective truth.

        Ω (subobject classifier): truth values are sieves.
        A sieve on T is a downward-closed set of morphisms into T.
        """
        topos = self._get_presheaf_topos()
        if topos is None:
            return None

        try:
            # Get the sieve for target
            target_morphisms = self.category.morphisms_to(target)
            if not target_morphisms:
                return None

            # Build the principal sieve for target
            from categorical.presheaf_topos import Sieve
            sieve = Sieve.principal(
                target,
                {m.name: m for m in target_morphisms},
            )

            # Check if source factors through the sieve
            source_outgoing = self.category.morphisms_from(source)
            supporting = [
                m for m in source_outgoing
                if m.target == target or any(
                    p.target == target
                    for p in self.category.find_paths(m.target, target, max_length=2)
                )
            ]

            if not supporting:
                return None

            support_fraction = len(supporting) / max(len(source_outgoing), 1)
            confidence = sieve.truth_value() if hasattr(sieve, 'truth_value') else support_fraction

            return {
                "confidence": confidence,
                "reason": (
                    f"Subobject classifier: sieve on {target} has "
                    f"{len(target_morphisms)} perspectives. "
                    f"Source supports {len(supporting)}/{len(source_outgoing)}."
                ),
                "perspectives": [m.name for m in target_morphisms],
                "support_fraction": support_fraction,
            }

        except Exception:
            return None

    def _check_pathway_support(
        self, source: str, target: str
    ) -> Dict[str, Any]:
        """
        For missing edges, check if pathways exist (Drug→Protein→Disease).

        This provides pathway-based support for repurposing predictions.
        """
        # Type filtering: only for Drug→Disease
        source_obj = self.category.get(source)
        target_obj = self.category.get(target)

        if not (source_obj and target_obj):
            return None

        if source_obj.type_name != "Drug" or target_obj.type_name != "Disease":
            return None

        outgoing, _ = self._build_morphism_index()
        confidences = []

        for drug_edge in outgoing.get(source, []):
            intermediate_obj = self.category.get(drug_edge.target)
            if (
                not intermediate_obj
                or intermediate_obj.type_name not in REPURPOSING_INTERMEDIATE_TYPES
            ):
                continue

            for disease_edge in outgoing.get(drug_edge.target, []):
                if disease_edge.target == target:
                    confidences.append(drug_edge.confidence * disease_edge.confidence)

        if not confidences:
            return None

        avg_confidence = sum(confidences) / len(confidences)
        max_confidence = max(confidences)

        # Scale cap by path count: more independent paths -> higher ceiling.
        path_count_factor = 1.0 + 0.1 * min(len(confidences) - 1, 4)
        final_confidence = min(0.85, avg_confidence * path_count_factor)

        return {
            "confidence": final_confidence,
            "reason": (
                f"Found {len(confidences)} Drug->protein->disease pathway(s). "
                f"Average pathway confidence: {avg_confidence:.2f}"
            ),
            "num_paths": len(confidences),
            "avg_confidence": avg_confidence,
            "max_confidence": max_confidence,
        }

        # Find paths via proteins (up to 3 hops)
        try:
            paths = self.category.find_paths(source, target, max_length=4)
            if not paths:
                return None

            # Use path weights directly (they're already calculated)
            # Paths with 2 morphisms (Drug->Protein->Disease) are ideal
            valid_paths = []
            confidences = []

            for path in paths:
                # Path objects have a weight attribute (min confidence along path)
                if hasattr(path, 'weight') and path.weight > 0:
                    # Check if path goes through protein intermediates
                    # Parse morphism_ids to get intermediate nodes
                    if hasattr(path, 'morphism_ids') and len(path.morphism_ids) >= 2:
                        # Extract intermediate node from morphism IDs
                        # Format: "relation:source->target"
                        first_mor = path.morphism_ids[0]
                        if '->' in first_mor:
                            intermediate = first_mor.split('->')[1]
                            intermediate_obj = self.category.get(intermediate)

                            if (
                                intermediate_obj
                                and intermediate_obj.type_name in REPURPOSING_INTERMEDIATE_TYPES
                            ):
                                valid_paths.append(path)
                                confidences.append(path.weight)

            if not confidences:
                return None

            avg_confidence = sum(confidences) / len(confidences)
            max_confidence = max(confidences)

            # Scale cap by path count: more independent paths → higher ceiling
            path_count_factor = 1.0 + 0.1 * min(len(valid_paths) - 1, 4)
            final_confidence = min(0.85, avg_confidence * path_count_factor)

            return {
                "confidence": final_confidence,
                "reason": (
                    f"Found {len(valid_paths)} pathway(s) via proteins. "
                    f"Average pathway confidence: {avg_confidence:.2f}"
                ),
                "num_paths": len(valid_paths),
                "avg_confidence": avg_confidence,
                "max_confidence": max_confidence,
            }

        except Exception as e:
            # Silently fail
            return None

    def _get_edge(self, source: str, target: str):
        """Get the morphism between source and target."""
        for mor in self._get_morphisms():
            if mor.source == source and mor.target == target:
                return mor
        return None

    def get_partial_knowledge_zones(self) -> List[Dict[str, Any]]:
        """
        Find all objects where excluded middle fails.

        These are the "partial knowledge zones" -- areas where
        classical true/false reasoning is insufficient.

        Returns:
            List of object descriptions with partial knowledge info.
        """
        topos = self._get_topos_logic()
        try:
            return topos.where_excluded_middle_fails()
        except Exception:
            return []
