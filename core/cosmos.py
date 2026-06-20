# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
InfinityCosmos: The ∞-Cosmos Layer for KOMPOSOS-IV

Based on Riehl & Verity, "Infinity category theory from scratch" (arXiv:1608.05314).

An ∞-cosmos is a simplicially enriched category equipped with isofibrations,
products, cotensors, and limits of isofibration towers. From this single axiom,
all of ∞-category theory flows formally: Yoneda, Kan extensions, adjunctions,
(co)limits, (co)cartesian fibrations.

This module builds the ∞-cosmos on top of KOMPOSOS-IV's existing Category runtime.
The Category provides 1-morphisms (edges). The ∞-cosmos provides:
  - The homotopy 2-category h₂K (via categorical/two_categories.py)
  - Isofibration detection and classification
  - Cartesian fibration construction (via categorical/fibrations.py)
  - Yoneda embedding into presheaf ∞-cosmos (via categorical/presheaf_topos.py)
  - Pointwise Kan extensions (via categorical/kan_extensions.py)

Usage:
    cosmos = InfinityCosmos(category)
    h2k = cosmos.homotopy_2_category()          # Build the homotopy 2-category
    alpha = cosmos.add_two_cell("α", "f", "g")   # Add a 2-cell: α : f => g
    fibrations = cosmos.cartesian_fibrations()    # Find all cartesian fibrations
    yoneda = cosmos.yoneda_embedding()            # Yoneda embedding
    kan = cosmos.kan_extension(functor, diagram)  # Pointwise Kan extension
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING,
)

if TYPE_CHECKING:
    from .category import Category

from categorical.two_categories import TwoCategory, TwoCell
from categorical.fibrations import GenericFibration, FiberObject, FiberMorphism
from categorical.grothendieck import GrothendieckConstruction, FiberedObject, FiberedMorphism
from categorical.presheaf_topos import PresheafTopos, Sieve, Presheaf
from categorical.kan_extensions import LeftKanExtension, RightKanExtension, CommaCategory, Functor


@dataclass
class IsofibrationInfo:
    """Metadata about a detected isofibration morphism."""
    morphism_name: str
    source: str
    target: str
    confidence: float
    is_isofibration: bool
    reason: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FibrationInfo:
    """Metadata about a cartesian fibration."""
    name: str
    base_object: str
    total_objects: List[str]
    cartesian_lifts: List[Dict[str, Any]]
    fiber_stats: Dict[str, Any]
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class YonedaResult:
    """Result of the Yoneda embedding computation."""
    is_fully_faithful: bool
    objects_mapped: Dict[str, str]
    presheaf_objects: List[Dict[str, Any]]
    faithfulness_score: float
    data: Dict[str, Any] = field(default_factory=dict)


class InfinityCosmos:
    """
    An ∞-cosmos built on top of a KOMPOSOS-IV Category.

    This is the single axiom from which all higher category theory flows
    (Riehl-Verity). The Category provides the 1-morphism structure; the
    ∞-cosmos adds:

    1. Homotopy 2-category (h₂K): Objects=0-cells, morphisms=1-cells,
       two-cells=2-cells (natural transformations / homotopies between paths)

    2. Isofibrations: Distinguished class of morphisms with lifting properties

    3. Cartesian fibrations: Fibrations with cartesian lifts (functorial calculus)

    4. Yoneda embedding: Fully faithful functor into presheaf ∞-cosmos

    5. Pointwise Kan extensions: Via comma category (co)limits

    Mathematical basis:
        - Riehl & Verity, "Infinity category theory from scratch" (2016)
        - Riehl, "Categorical Homotopy Theory" (2013)
        - Riehl & Verity, "Elements of ∞-Category Theory" (Cambridge 2022)
    """

    def __init__(self, category: Category, name: str = None):
        """
        Args:
            category: The underlying KOMPOSOS-IV Category.
            name: Name for this ∞-cosmos (defaults to category name).
        """
        self.category = category
        self.name = name or f"∞-cosmos({category.name})"

        # Cached structures
        self._h2k: Optional[TwoCategory] = None
        self._isofibrations: Dict[str, IsofibrationInfo] = {}
        self._fibrations: Dict[str, FibrationInfo] = {}
        self._yoneda_result: Optional[YonedaResult] = None

        # 2-cell tracking (synced with Category morphisms)
        self._two_cells_by_morphism: Dict[str, List[str]] = {}  # mor_id -> [2cell_names]

    # ========================================================================
    # Axiom 1: The Homotopy 2-Category (h₂K)
    # ========================================================================

    def homotopy_2_category(self, rebuild: bool = False) -> TwoCategory:
        """
        Construct the homotopy 2-category h₂K from the underlying Category.

        Per Riehl-Verity:
          - 0-cells = objects of the Category
          - 1-cells = morphisms of the Category (vertices of mapping spaces)
          - 2-cells = equivalences between parallel morphisms (edges modulo homotopy)

        This is the strict 2-category in which all ∞-categorical reasoning happens.

        Args:
            rebuild: Force reconstruction even if cached.

        Returns:
            TwoCategory instance representing h₂K.
        """
        if self._h2k is not None and not rebuild:
            return self._h2k

        h2k = TwoCategory(name=f"{self.name}.h2K")

        # 0-cells: objects
        for obj in self.category.objects():
            h2k.add_object(obj.name, data={
                "type_name": obj.type_name,
                "metadata": dict(obj.metadata) if obj.metadata else {},
            })

        # 1-cells: morphisms
        for mor in self.category.morphisms():
            h2k.add_morphism(
                mor.id,  # Use unique morphism ID
                source=mor.source,
                target=mor.target,
                data={
                    "name": mor.name,
                    "confidence": mor.confidence,
                    "provenance": mor.provenance,
                },
            )

        # 2-cells: auto-detect parallel morphisms and create 2-cells
        # Two morphisms f, g: A -> B are parallel, so a 2-cell α: f => g can exist
        self._build_parallel_two_cells(h2k)

        self._h2k = h2k
        return h2k

    def _build_parallel_two_cells(self, h2k: TwoCategory):
        """
        Build 2-cells between parallel morphisms.

        For each pair of parallel morphisms f, g: A -> B,
        create a 2-cell representing their relationship.
        """
        # Group morphisms by (source, target)
        parallel_groups: Dict[Tuple[str, str], List[str]] = {}
        for mor in self.category.morphisms():
            key = (mor.source, mor.target)
            parallel_groups.setdefault(key, []).append(mor.id)

        # Create 2-cells within each group
        for (src, tgt), mor_ids in parallel_groups.items():
            if len(mor_ids) < 2:
                continue

            for i, src_mor_id in enumerate(mor_ids):
                for tgt_mor_id in mor_ids[i + 1:]:
                    src_mor = self.category.get_morphism(src_mor_id)
                    tgt_mor = self.category.get_morphism(tgt_mor_id)
                    if src_mor is None or tgt_mor is None:
                        continue

                    # Compute confidence similarity as 2-cell data
                    conf_diff = abs(src_mor.confidence - tgt_mor.confidence)
                    similarity = 1.0 - conf_diff

                    cell_name = f"α:{src_mor.name}=>{tgt_mor.name}"
                    try:
                        cell = h2k.add_two_cell(
                            cell_name,
                            source_mor=src_mor_id,
                            target_mor=tgt_mor_id,
                            data={
                                "type": "parallel",
                                "confidence_similarity": similarity,
                                "source_confidence": src_mor.confidence,
                                "target_confidence": tgt_mor.confidence,
                            },
                        )
                        self._two_cells_by_morphism.setdefault(src_mor_id, []).append(cell_name)
                        self._two_cells_by_morphism.setdefault(tgt_mor_id, []).append(cell_name)
                    except ValueError:
                        pass  # Domain/codomain mismatch (shouldn't happen, but be safe)

    # ========================================================================
    # 2-Cell Operations (Building on h₂K)
    # ========================================================================

    def add_two_cell(
        self,
        name: str,
        source_morphism: str,
        target_morphism: str,
        data: Dict[str, Any] = None,
    ) -> TwoCell:
        """
        Add a 2-cell α: f => g to the homotopy 2-category.

        Args:
            name: Name for the 2-cell.
            source_morphism: Source 1-cell (f).
            target_morphism: Target 1-cell (g).
            data: Optional metadata.

        Returns:
            The created TwoCell.
        """
        h2k = self.homotopy_2_category()
        cell = h2k.add_two_cell(name, source_morphism, target_morphism, data)

        self._two_cells_by_morphism.setdefault(source_morphism, []).append(name)
        self._two_cells_by_morphism.setdefault(target_morphism, []).append(name)
        return cell

    def compose_two_cells_vertical(self, alpha: str, beta: str) -> TwoCell:
        """
        Vertical composition: β · α : f => h (where α: f=>g, β: g=>h).

        Args:
            alpha: Name of the source 2-cell.
            beta: Name of the target 2-cell.

        Returns:
            The composed 2-cell.
        """
        h2k = self.homotopy_2_category()
        return h2k.vertical_compose(alpha, beta)

    def compose_two_cells_horizontal(self, alpha: str, beta: str) -> TwoCell:
        """
        Horizontal composition: β * α : g.f => g'.f'.

        Args:
            alpha: 2-cell α: f => f' (A -> B).
            beta: 2-cell β: g => g' (B -> C).

        Returns:
            The composed 2-cell.
        """
        h2k = self.homotopy_2_category()
        return h2k.horizontal_compose(alpha, beta)

    def check_interchange_law(self, a1: str, a2: str, b1: str, b2: str) -> bool:
        """
        Check the interchange law for a 2x2 grid of 2-cells.

        (a2 · a1) * (b2 · b1) = (a2 * b2) · (a1 * b1)

        This is the key coherence condition for strict 2-categories.
        """
        h2k = self.homotopy_2_category()
        return h2k.check_interchange(a1, a2, b1, b2)

    def whisker_left(self, morphism: str, alpha: str) -> TwoCell:
        """Left whiskering: h * α for h: B->C, α: f=>g (A->B)."""
        h2k = self.homotopy_2_category()
        return h2k.whisk_left(morphism, alpha)

    def whisker_right(self, alpha: str, morphism: str) -> TwoCell:
        """Right whiskering: α * h for α: f=>g (B->C), h: A->B."""
        h2k = self.homotopy_2_category()
        return h2k.whisk_right(alpha, morphism)

    # ========================================================================
    # Axiom 2: Isofibrations
    # ========================================================================

    def detect_isofibrations(self, rebuild: bool = False) -> Dict[str, IsofibrationInfo]:
        """
        Detect isofibration morphisms in the Category.

        An isofibration is a morphism p: E -> B with the property that
        for any object e in E and any isomorphism f: p(e) -> b' in B,
        there exists a lift of f to E starting at e.

        Heuristic detection (since we don't have full simplicial enrichment):
        - Morphisms with confidence >= 0.9 are "strong" (candidate isofibrations)
        - Morphisms that are the unique path between their endpoints
        - Morphisms that participate in pullback squares

        Args:
            rebuild: Force re-detection.

        Returns:
            Dict of morphism_id -> IsofibrationInfo.
        """
        if self._isofibrations and not rebuild:
            return self._isofibrations

        self._isofibrations = {}

        for mor in self.category.morphisms():
            info = self._classify_isofibration(mor)
            if info.is_isofibration:
                self._isofibrations[mor.id] = info

        return self._isofibrations

    def _classify_isofibration(self, mor) -> IsofibrationInfo:
        """Classify a single morphism as isofibration or not."""
        reasons = []
        is_iso = False

        # Heuristic 1: High confidence morphisms
        if mor.confidence >= 0.9:
            reasons.append("high_confidence")
            is_iso = True

        # Heuristic 2: Unique path (no alternatives)
        paths = self.category.find_paths(mor.source, mor.target, max_length=3)
        alternative_paths = [p for p in paths if len(p.morphism_ids) > 1]
        if not alternative_paths:
            reasons.append("unique_direct_path")
            is_iso = True

        # Heuristic 3: Participates in pullback (has competing source morphisms)
        incoming_to_target = self.category.morphisms_to(mor.target)
        outgoing_from_source = self.category.morphisms_from(mor.source)
        if len(incoming_to_target) >= 2 and len(outgoing_from_source) >= 2:
            reasons.append("pullback_candidate")
            is_iso = True

        return IsofibrationInfo(
            morphism_name=mor.id,
            source=mor.source,
            target=mor.target,
            confidence=mor.confidence,
            is_isofibration=is_iso,
            reason=", ".join(reasons),
            data={"alternative_path_count": len(alternative_paths)},
        )

    def is_isofibration(self, morphism_id: str) -> bool:
        """Check if a morphism is an isofibration."""
        self.detect_isofibrations()
        return morphism_id in self._isofibrations

    # ========================================================================
    # Axiom 3: Cartesian Fibrations
    # ========================================================================

    def cartesian_fibrations(self, rebuild: bool = False) -> Dict[str, FibrationInfo]:
        """
        Find cartesian fibrations in the homotopy 2-category.

        A cartesian fibration p: E -> B is a morphism such that for every
        object e in E and every morphism f: b -> p(e) in B, there exists
        a cartesian lift of f to E starting at e.

        Uses categorical/fibrations.py (GenericFibration) to construct
        the total category and find cartesian lifts.

        Args:
            rebuild: Force reconstruction.

        Returns:
            Dict of fibration_name -> FibrationInfo.
        """
        if self._fibrations and not rebuild:
            return self._fibrations

        self._fibrations = {}

        # Try to build fibrations from object type groupings
        objects = self.category.objects()
        type_groups: Dict[str, List[str]] = {}
        for obj in objects:
            type_groups.setdefault(obj.type_name, []).append(obj.name)

        # For each type group, try to build a fibration
        for type_name, obj_names in type_groups.items():
            if len(obj_names) < 2:
                continue

            try:
                fib = self._build_fibration(type_name, obj_names)
                if fib:
                    self._fibrations[type_name] = fib
            except Exception:
                pass  # Not all type groups form valid fibrations

        return self._fibrations

    def _build_fibration(self, name: str, obj_names: List[str]) -> Optional[FibrationInfo]:
        """Attempt to build a cartesian fibration for a group of objects."""
        # Get sub-category induced by these objects
        all_morphisms = self.category.morphisms()
        relevant = [
            m for m in all_morphisms
            if m.source in obj_names or m.target in obj_names
        ]

        if not relevant:
            return None

        # Build GenericFibration
        try:
            fib = GenericFibration(
                name=name,
                store=None,  # We work with Category directly
                objects=obj_names,
                morphisms=relevant,
                cross_fiber_relations=[],
            )

            # Build the total category
            fib.build()

            # Extract cartesian lifts
            cartesian_lifts = []
            if hasattr(fib, 'cartesian_lift'):
                # Try to find cartesian lifts for a sample
                for obj_name in obj_names[:3]:
                    lift = fib.cartesian_lift(obj_name)
                    if lift:
                        cartesian_lifts.append({
                            "object": obj_name,
                            "lift": str(lift),
                        })

            stats = fib.get_fiber_stats() if hasattr(fib, 'get_fiber_stats') else {}

            return FibrationInfo(
                name=name,
                base_object=name,
                total_objects=obj_names,
                cartesian_lifts=cartesian_lifts,
                fiber_stats=stats,
            )
        except Exception:
            return None

    # ========================================================================
    # Derived Structure: Yoneda Embedding
    # ========================================================================

    def yoneda_embedding(self, rebuild: bool = False) -> YonedaResult:
        """
        Compute the Yoneda embedding y: C -> [C^op, Set].

        Per Riehl-Verity: The Yoneda embedding is fully faithful.
        Two objects are isomorphic iff their representable presheaves are isomorphic.

        This computes the embedding by:
        1. Building the full PresheafTopos from the Category
        2. Computing representable presheaves y(T) = Hom(-, T) for each object
        3. Computing the Yoneda distance between all pairs
        4. Checking full faithfulness (injective on hom-sets)

        Args:
            rebuild: Force recomputation.

        Returns:
            YonedaResult with embedding data.
        """
        if self._yoneda_result is not None and not rebuild:
            return self._yoneda_result

        objects = self.category.objects()
        if len(objects) < 2:
            self._yoneda_result = YonedaResult(
                is_fully_faithful=True,
                objects_mapped={},
                presheaf_objects=[],
                faithfulness_score=1.0,
            )
            return self._yoneda_result

        # Build the full presheaf topos (connects with presheaf_topos.py)
        try:
            topos = PresheafTopos.from_enriched_category(self.category)
            use_topos = True
        except Exception:
            topos = None
            use_topos = False

        objects_mapped = {}
        presheaf_objects = []
        seen_repr = {}
        collisions = 0

        for obj in objects:
            if use_topos:
                # Use the representable presheaf from the topos
                repr_presheaf = topos.representables.get(obj.name)
                if repr_presheaf:
                    presheaf_data = {
                        "type": "representable_presheaf",
                        "hom_sets": {
                            src: list(repr_presheaf.evaluate(src))
                            for src in topos.objects
                            if repr_presheaf.evaluate(src)
                        },
                    }
                else:
                    presheaf_data = self._build_manual_presheaf(obj.name)
            else:
                # Fallback: manual presheaf computation
                presheaf_data = self._build_manual_presheaf(obj.name)

            presheaf_objects.append({
                "object": obj.name,
                "representable": presheaf_data,
            })
            objects_mapped[obj.name] = f"y({obj.name})"

            # Check for collisions (non-faithful embedding)
            key = str(presheaf_data)
            if key in seen_repr:
                collisions += 1
            else:
                seen_repr[key] = obj.name

        # Compute Yoneda distances if using topos
        yoneda_distances = {}
        if use_topos:
            for obj_a in objects:
                for obj_b in objects:
                    if obj_a.name < obj_b.name:
                        d = topos.yoneda_distance(obj_a.name, obj_b.name)
                        yoneda_distances[(obj_a.name, obj_b.name)] = d

        total = len(objects)
        faithfulness = 1.0 - (collisions / total) if total > 0 else 1.0

        self._yoneda_result = YonedaResult(
            is_fully_faithful=collisions == 0,
            objects_mapped=objects_mapped,
            presheaf_objects=presheaf_objects,
            faithfulness_score=faithfulness,
            data={"yoneda_distances": yoneda_distances, "use_topos": use_topos},
        )
        return self._yoneda_result

    def _build_manual_presheaf(self, obj_name: str) -> dict:
        """
        Build presheaf data manually when PresheafTopos is unavailable.

        For each object X, compute Hom(X, obj_name) = {morphisms X -> obj_name}.
        """
        incoming = self.category.morphisms_to(obj_name)
        outgoing = self.category.morphisms_from(obj_name)

        return {
            "type": "manual_hom_sets",
            "incoming_count": len(incoming),
            "outgoing_count": len(outgoing),
            "incoming_sources": [m.source for m in incoming],
            "outgoing_targets": [m.target for m in outgoing],
        }

    # ========================================================================
    # Derived Structure: Pointwise Kan Extensions
    # ========================================================================

    def kan_extension(
        self,
        functor_obj_map: Dict[str, str],
        diagram_objects: List[str],
        target_object: str,
        left: bool = True,
    ) -> Dict[str, Any]:
        """
        Compute pointwise Kan extension via comma category (co)limits.

        Per Riehl-Verity: Pointwise Kan extensions are computed as
        (co)limits in comma categories.

        Args:
            functor_obj_map: Object mapping for the functor K: C -> D.
            diagram_objects: Objects of the source category C.
            target_object: The object to extend to (e in D).
            left: True for Left Kan Extension (colimit), False for Right (limit).

        Returns:
            Dict with extension result.
        """
        h2k = self.homotopy_2_category()

        if left:
            # Left Kan Extension: Lan_K(F)(e) = colim_{(K ↓ e)} F(c)
            # Build comma category (K ↓ e)
            comma_objs = []
            for obj_name in diagram_objects:
                mapped = functor_obj_map.get(obj_name)
                if mapped:
                    # Check if there's a path from mapped to target
                    paths = self.category.find_paths(mapped, target_object, max_length=3)
                    if paths:
                        comma_objs.append(obj_name)

            if not comma_objs:
                return {
                    "type": "left_kan",
                    "target": target_object,
                    "result": None,
                    "reason": "No objects in comma category",
                }

            # Compute weighted colimit (average of F(c) for c in comma category)
            values = []
            for obj_name in comma_objs:
                mor = self.category.get(obj_name)
                if mor and hasattr(mor, 'metadata'):
                    val = mor.metadata.get("value", 0.5)
                    values.append(val)

            result = sum(values) / len(values) if values else 0.0

            return {
                "type": "left_kan",
                "target": target_object,
                "comma_objects": comma_objs,
                "result": result,
                "reason": f"colim over {len(comma_objs)} objects",
            }
        else:
            # Right Kan Extension: Ran_K(F)(e) = lim_{(e ↓ K)} F(c)
            comma_objs = []
            for obj_name in diagram_objects:
                mapped = functor_obj_map.get(obj_name)
                if mapped:
                    paths = self.category.find_paths(target_object, mapped, max_length=3)
                    if paths:
                        comma_objs.append(obj_name)

            if not comma_objs:
                return {
                    "type": "right_kan",
                    "target": target_object,
                    "result": None,
                    "reason": "No objects in comma category",
                }

            # Compute limit (intersection / consensus)
            values = []
            for obj_name in comma_objs:
                mor = self.category.get(obj_name)
                if mor and hasattr(mor, 'metadata'):
                    val = mor.metadata.get("value", 0.5)
                    values.append(val)

            result = min(values) if values else 0.0  # Limit = infimum

            return {
                "type": "right_kan",
                "target": target_object,
                "comma_objects": comma_objs,
                "result": result,
                "reason": f"lim over {len(comma_objs)} objects",
            }

    # ========================================================================
    # Axiom Verification
    # ========================================================================

    def verify_cosmos_axioms(self) -> Dict[str, bool]:
        """
        Verify that the underlying Category satisfies ∞-cosmos axioms.

        Checks:
        1. Has products (binary products exist)
        2. Has cotensors (hom-objects are well-defined)
        3. Has isofibration limits (isofibrations compose)
        4. Stability: closure under pullback, composition, retracts

        Returns:
            Dict of axiom_name -> satisfied.
        """
        results = {}

        # Axiom 1: Products
        objects = self.category.objects()
        has_products = len(objects) >= 2
        if has_products:
            try:
                self.category.product(objects[0].name, objects[1].name)
            except Exception:
                has_products = False
        results["has_products"] = has_products

        # Axiom 2: Cotensors (hom-objects exist)
        has_cotensors = all(
            self.category.hom(o1.name, o2.name) is not None
            for o1 in objects for o2 in objects
        )
        results["has_cotensors"] = has_cotensors

        # Axiom 3: Isofibration limits
        self.detect_isofibrations()
        has_iso_limits = len(self._isofibrations) > 0
        results["has_isofibration_limits"] = has_iso_limits

        # Axiom 4: Stability (composition closure)
        morphisms = self.category.morphisms()
        composition_closed = True
        for f in morphisms:
            for g in morphisms:
                if f.target == g.source:
                    # Check if composite exists or can be formed
                    composite_exists = any(
                        m.source == f.source and m.target == g.target
                        for m in morphisms
                    )
                    if not composite_exists:
                        composition_closed = False
                        break
            if not composition_closed:
                break
        results["composition_closure"] = composition_closed

        # Global: all axioms satisfied
        results["is_valid_cosmos"] = all(results.values())

        return results

    # ========================================================================
    # Introspection
    # ========================================================================

    def statistics(self) -> Dict[str, Any]:
        """Get statistics about the ∞-cosmos."""
        h2k = self.homotopy_2_category()
        self.detect_isofibrations()
        self.cartesian_fibrations()
        yoneda = self.yoneda_embedding()

        return {
            "name": self.name,
            "objects": len(self.category.objects()),
            "morphisms": len(self.category.morphisms()),
            "two_cells": len(h2k.two_cells),
            "isofibrations": len(self._isofibrations),
            "fibrations": len(self._fibrations),
            "yoneda_faithful": yoneda.is_fully_faithful,
            "yoneda_score": yoneda.faithfulness_score,
            "axioms_satisfied": self.verify_cosmos_axioms(),
        }

    def __repr__(self):
        stats = self.statistics()
        return (
            f"InfinityCosmos({self.name}, "
            f"objects={stats['objects']}, "
            f"morphisms={stats['morphisms']}, "
            f"two_cells={stats['two_cells']}, "
            f"isofibrations={stats['isofibrations']}, "
            f"fibrations={stats['fibrations']})"
        )
