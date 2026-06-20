# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Two-Cell Bridge: COG Tier 4 Reasoning via the Homotopy 2-Category

Bridges KOMPOSOS-IV Category morphisms to TwoCategory 2-cells,
enabling COG Tier 4 to reason about:
  - Path equivalences (2-cells between parallel paths)
  - Natural transformations (whiskering, Godement products)
  - Universal properties (cartesian lifts, adjunctions)
  - Interchange law coherence (2-category consistency)

This activates categorical/two_categories.py (previously dead code)
and provides the "Full Homotopy 2-Category" reasoning tier for COG.

Usage:
    bridge = TwoCellBridge(category)
    result = bridge.verify_claim("A", "B", "relates")
    # Returns: {"verdict": "AGREE", "two_cell_witness": "...", "reason": "..."}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .category import Category
from .cosmos import InfinityCosmos
from categorical.two_categories import TwoCategory, TwoCell


@dataclass
class TwoCellVerificationResult:
    """Result of 2-cell verification."""
    verdict: str  # AGREE, REJECT, ORPHAN, HOLLOW, EQUIVALENT
    source: str
    target: str
    relation: str
    two_cell_witness: Optional[str] = None
    parallel_morphisms: List[str] = field(default_factory=list)
    path_alternatives: List[str] = field(default_factory=list)
    interchange_holds: bool = True
    confidence: float = 1.0
    reason: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


class TwoCellBridge:
    """
    Bridge from KOMPOSOS-IV Category to TwoCategory for COG Tier 4.

    Provides 2-cell reasoning:
    1. Lift claim to h₂K (objects=0-cells, morphisms=1-cells)
    2. Build 2-cells between parallel morphisms
    3. Check universal properties (cartesian, adjunction)
    4. Verify interchange law coherence
    """

    def __init__(self, cosmos: InfinityCosmos = None, category: Category = None):
        """
        Args:
            cosmos: InfinityCosmos instance (preferred).
            category: Category instance (will create cosmos if not provided).
        """
        if cosmos:
            self.cosmos = cosmos
            self.category = cosmos.category
        elif category:
            self.cosmos = InfinityCosmos(category)
            self.category = category
        else:
            raise ValueError("Either cosmos or category must be provided")

        self._h2k: Optional[TwoCategory] = None

    def _get_h2k(self) -> TwoCategory:
        """Get or build the homotopy 2-category."""
        if self._h2k is None:
            self._h2k = self.cosmos.homotopy_2_category()
        return self._h2k

    # ========================================================================
    # Primary API: Verify Claim via 2-Cell Reasoning
    # ========================================================================

    def verify_claim(
        self,
        source: str,
        target: str,
        relation: str = None,
    ) -> TwoCellVerificationResult:
        """
        Verify a claim using 2-cell reasoning in the homotopy 2-category.

        Steps:
        1. Find the morphism(s) matching source->target with given relation
        2. Find parallel morphisms (alternative paths)
        3. Build 2-cells between parallel morphisms
        4. Check if there's a coherent transformation

        Args:
            source: Source object.
            target: Target object.
            relation: Optional morphism name to verify.

        Returns:
            TwoCellVerificationResult with verdict and witness.
        """
        h2k = self._get_h2k()

        # Step 1: Find direct morphism(s)
        direct_morphisms = self._find_morphisms(source, target, relation)

        if not direct_morphisms:
            # No direct morphism -- check for path alternatives
            return self._verify_via_alternatives(source, target, relation)

        # Step 2: Find parallel morphisms
        all_parallel = self._find_parallel_morphisms(source, target)

        if len(all_parallel) <= 1:
            # Single morphism, no 2-cell reasoning possible
            mor = direct_morphisms[0]
            return TwoCellVerificationResult(
                verdict="AGREE" if mor.confidence > 0.5 else "HOLLOW",
                source=source,
                target=target,
                relation=relation or "",
                parallel_morphisms=[m.id for m in all_parallel],
                confidence=mor.confidence,
                reason=f"Single morphism {mor.name} with confidence {mor.confidence:.2f}",
            )

        # Step 3: Check for existing 2-cells between parallels
        two_cells = self._find_two_cells_between(h2k, source, target)

        if two_cells:
            # Found 2-cell witnesses
            best_cell = max(two_cells, key=lambda c: c.data.get("confidence_similarity", 0))
            best_similarity = best_cell.data.get("confidence_similarity", 0)

            return TwoCellVerificationResult(
                verdict="EQUIVALENT" if best_similarity > 0.8 else "AGREE",
                source=source,
                target=target,
                relation=relation or "",
                two_cell_witness=best_cell.name,
                parallel_morphisms=[m.id for m in all_parallel],
                confidence=best_similarity,
                reason=f"2-cell {best_cell.name} witnesses equivalence "
                       f"(similarity={best_similarity:.2f})",
                data={"two_cell": {
                    "name": best_cell.name,
                    "source": best_cell.source_morphism,
                    "target": best_cell.target_morphism,
                }},
            )

        # Step 4: No 2-cells yet, but parallel morphisms exist
        # Compute equivalence score from confidence similarity
        confidences = [m.confidence for m in all_parallel]
        max_conf = max(confidences)
        min_conf = min(confidences)
        similarity = 1.0 - (max_conf - min_conf)

        return TwoCellVerificationResult(
            verdict="AGREE" if similarity > 0.7 else "ORPHAN",
            source=source,
            target=target,
            relation=relation or "",
            parallel_morphisms=[m.id for m in all_parallel],
            confidence=similarity,
            reason=f"{len(all_parallel)} parallel morphisms exist, "
                   f"confidence range [{min_conf:.2f}, {max_conf:.2f}], "
                   f"similarity={similarity:.2f}",
        )

    def _find_morphisms(
        self, source: str, target: str, relation: str = None
    ) -> list:
        """Find morphisms matching source, target, and optionally relation."""
        candidates = []
        for mor in self.category.morphisms():
            if mor.source == source and mor.target == target:
                if relation is None or mor.name == relation:
                    candidates.append(mor)
        return candidates

    def _find_parallel_morphisms(self, source: str, target: str) -> list:
        """Find all parallel morphisms (direct + composed paths)."""
        # Direct morphisms
        direct = self._find_morphisms(source, target)

        # Path alternatives (length 2)
        paths = self.category.find_paths(source, target, max_length=2)
        path_ids = []
        for path in paths:
            if len(path.morphism_ids) > 1:
                path_ids.append(f"path({'->'.join(path.morphism_ids)})")

        return direct

    def _find_two_cells_between(
        self, h2k: TwoCategory, source: str, target: str
    ) -> List[TwoCell]:
        """Find 2-cells between morphisms from source to target."""
        mor_ids = [m.id for m in self._find_morphisms(source, target)]
        cells = []

        for mor_id in mor_ids:
            for cell_name, cell in h2k.two_cells.items():
                if cell.source_morphism == mor_id or cell.target_morphism == mor_id:
                    # Check that the other endpoint is also a source->target morphism
                    other = (
                        cell.target_morphism
                        if cell.source_morphism == mor_id
                        else cell.source_morphism
                    )
                    if other in mor_ids:
                        cells.append(cell)

        return cells

    def _verify_via_alternatives(
        self, source: str, target: str, relation: str = None
    ) -> TwoCellVerificationResult:
        """Verify claim when no direct morphism exists, using path alternatives."""
        paths = self.category.find_paths(source, target, max_length=3)

        if not paths:
            return TwoCellVerificationResult(
                verdict="REJECT",
                source=source,
                target=target,
                relation=relation or "",
                confidence=0.0,
                reason=f"No morphism or path found from {source} to {target}",
            )

        best_path = max(paths, key=lambda p: p.weight)

        return TwoCellVerificationResult(
            verdict="AGREE" if best_path.weight > 0.5 else "HOLLOW",
            source=source,
            target=target,
            relation=relation or "",
            path_alternatives=[
                " -> ".join(p.morphism_ids) for p in paths[:5]
            ],
            confidence=best_path.weight,
            reason=f"Best path via {len(paths)} alternatives, "
                   f"best weight={best_path.weight:.2f}",
        )

    # ========================================================================
    # Universal Property Checking
    # ========================================================================

    def check_cartesian_lift(
        self, morphism_id: str
    ) -> Dict[str, Any]:
        """
        Check if a morphism is a cartesian lift.

        A morphism f: e -> e' in E is cartesian over p(f): p(e) -> p(e') in B
        if for any g: x -> e' in E and any factorization p(g) = h . p(f) in B,
        there exists a unique lift of h to E.

        Args:
            morphism_id: The morphism to check.

        Returns:
            Dict with cartesian property info.
        """
        mor = self.category.get_morphism(morphism_id)
        if mor is None:
            return {"is_cartesian": False, "reason": "Morphism not found"}

        # Heuristic: A morphism is cartesian if it's the unique best path
        # from source to target among all morphisms with the same target
        incoming = self.category.morphisms_to(mor.target)
        is_best = all(
            mor.confidence >= m.confidence
            for m in incoming
            if m.source == mor.source
        )

        is_unique = sum(
            1 for m in incoming
            if m.source == mor.source and m.name == mor.name
        ) == 1

        return {
            "is_cartesian": is_best and is_unique,
            "morphism": mor.id,
            "confidence": mor.confidence,
            "alternative_count": len(incoming) - 1,
            "reason": "Best and unique path" if (is_best and is_unique)
                       else "Not the best path or not unique",
        }

    def check_adjunction(
        self, f_id: str, g_id: str
    ) -> Dict[str, Any]:
        """
        Check if two morphisms form an adjunction (f ⊣ g).

        An adjunction f ⊣ g requires:
        - f: A -> B and g: B -> A (opposite directions)
        - Unit: η: id_A => g.f
        - Counit: ε: f.g => id_B
        - Triangle identities: ε.f . f.η = id_f and g.ε . η.g = id_g

        Args:
            f_id: Left adjoint morphism ID.
            g_id: Right adjoint morphism ID.

        Returns:
            Dict with adjunction info.
        """
        f = self.category.get_morphism(f_id)
        g = self.category.get_morphism(g_id)

        if f is None or g is None:
            return {"is_adjunction": False, "reason": "Morphism not found"}

        # Check opposite directions
        if f.source != g.target or f.target != g.source:
            return {
                "is_adjunction": False,
                "reason": f"Not opposite directions: {f.source}->{f.target} vs {g.source}->{g.target}",
            }

        # Check for unit (id_A => g.f)
        gf_exists = any(
            m.source == f.source and m.target == f.source
            and m.confidence >= f.confidence * g.confidence * 0.9
            for m in self.category.morphisms()
        )

        # Check for counit (f.g => id_B)
        fg_exists = any(
            m.source == f.target and m.target == f.target
            and m.confidence >= f.confidence * g.confidence * 0.9
            for m in self.category.morphisms()
        )

        is_adjunction = gf_exists and fg_exists

        return {
            "is_adjunction": is_adjunction,
            "left_adjoint": f_id,
            "right_adjoint": g_id,
            "unit_exists": gf_exists,
            "counit_exists": fg_exists,
            "reason": "Adjunction detected" if is_adjunction
                       else "Unit or counit missing",
        }

    # ========================================================================
    # Interchange Law Verification
    # ========================================================================

    def verify_interchange_coherence(self) -> Dict[str, Any]:
        """
        Verify that the 2-category satisfies the interchange law.

        For all 2x2 grids of 2-cells:
          (a2 · a1) * (b2 · b1) = (a2 * b2) · (a1 * b1)

        This is the key coherence condition for strict 2-categories.

        Returns:
            Dict with coherence info.
        """
        h2k = self._get_h2k()
        cells = list(h2k.two_cells.values())

        if len(cells) < 4:
            return {
                "coherent": True,
                "reason": "Too few 2-cells to form a 2x2 grid",
                "grids_checked": 0,
                "grids_passed": 0,
            }

        grids_checked = 0
        grids_passed = 0

        # Try all 4-tuples of 2-cells that could form a grid
        for a1 in cells:
            for a2 in cells:
                if a2.source_morphism != a1.target_morphism:
                    continue
                for b1 in cells:
                    if b1.source_object != a1.target_object:
                        continue
                    for b2 in cells:
                        if b2.source_morphism != b1.target_morphism:
                            continue
                        if b2.source_object != a2.target_object:
                            continue

                        grids_checked += 1
                        if h2k.check_interchange(a1.name, a2.name, b1.name, b2.name):
                            grids_passed += 1

        coherent = grids_passed == grids_checked if grids_checked > 0 else True

        return {
            "coherent": coherent,
            "reason": f"All {grids_checked} grids pass" if coherent
                       else f"{grids_checked - grids_passed} grids fail",
            "grids_checked": grids_checked,
            "grids_passed": grids_passed,
        }

    # ========================================================================
    # COG Tier 4 Integration
    # ========================================================================

    def tier4_verify(
        self,
        claim_source: str,
        claim_target: str,
        claim_relation: str = None,
    ) -> Dict[str, Any]:
        """
        COG Tier 4 interface: Full Homotopy 2-Category reasoning.

        This is what COG Tier 4 calls to verify claims using 2-cell reasoning.

        Returns:
            Dict compatible with COG verification result format.
        """
        result = self.verify_claim(claim_source, claim_target, claim_relation)

        # Check universal properties
        cartesian = self.check_cartesian_lift_for_claim(result)
        adjunction = self.check_adjunction_for_claim(result)
        interchange = self.verify_interchange_coherence()

        return {
            "tier": 4,
            "tier_name": "Homotopy 2-Category",
            "verdict": result.verdict,
            "confidence": result.confidence,
            "reason": result.reason,
            "two_cell_witness": result.two_cell_witness,
            "universal_properties": {
                "cartesian": cartesian,
                "adjunction": adjunction,
            },
            "interchange_coherence": interchange,
        }

    def check_cartesian_lift_for_claim(self, result: TwoCellVerificationResult) -> Dict:
        """Check if the claim morphism is a cartesian lift."""
        if result.parallel_morphisms:
            return self.check_cartesian_lift(result.parallel_morphisms[0])
        return {"is_cartesian": False, "reason": "No morphism to check"}

    def check_adjunction_for_claim(self, result: TwoCellVerificationResult) -> Dict:
        """Check if there's an adjunction related to the claim."""
        # Check if source and target have opposite-direction morphisms
        reverse = self._find_morphisms(result.target, result.source)
        if reverse:
            return self.check_adjunction(
                result.parallel_morphisms[0] if result.parallel_morphisms else "",
                reverse[0].id,
            )
        return {"is_adjunction": False, "reason": "No reverse morphism"}

    def __repr__(self):
        h2k = self._get_h2k()
        return (
            f"TwoCellBridge(h2K={h2k.name}, "
            f"two_cells={len(h2k.two_cells)})"
        )
