# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Strict 2-Categories: Morphisms Between Morphisms

A 2-category has three levels of structure:
  - 0-cells (objects): A, B, C, ...
  - 1-cells (morphisms): f, g : A -> B
  - 2-cells (2-morphisms): alpha : f => g  (where f, g : A -> B)

Two composition operations on 2-cells:
  - Vertical: alpha : f => g, beta : g => h  =>  beta . alpha : f => h
    (composing transformations that share an intermediate morphism)
  - Horizontal: alpha : f => f' (A->B), beta : g => g' (B->C)
    =>  beta * alpha : g.f => g'.f' (A->C)
    (composing transformations side by side)

Key axiom (interchange law):
  (beta1 . alpha1) * (beta2 . alpha2) = (beta1 * beta2) . (alpha1 * alpha2)
  Vertical-then-horizontal = horizontal-then-vertical.

Whiskering:
  Left:  h . alpha  for h : B -> C, alpha : f => g (A -> B)
  Right: alpha . h  for alpha : f => g (B -> C), h : A -> B

The existing HigherMorphism table in data/store.py already models 2-cells
(source_path_id, target_path_id, transformation_type). This module
provides the algebraic structure on top.

Mathematical basis:
  - Borceux, "Handbook of Categorical Algebra" Vol. 1, Ch. 7
  - Leinster, "Basic Category Theory" (2014), Ch. 1.3
  - nLab, "strict 2-category"
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Set


@dataclass
class TwoCell:
    """
    A 2-morphism (2-cell): alpha : f => g where f, g : A -> B.

    This is an arrow between arrows. In different contexts:
    - Natural transformation between functors
    - Homotopy between paths (HoTT)
    - Evidence that two relationships are related
    """
    name: str
    source_morphism: str    # f (a 1-cell name)
    target_morphism: str    # g (a 1-cell name)
    source_object: str      # A (domain of f and g)
    target_object: str      # B (codomain of f and g)
    data: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash((self.name, self.source_morphism, self.target_morphism))

    def __eq__(self, other):
        if isinstance(other, TwoCell):
            return (self.name == other.name and
                    self.source_morphism == other.source_morphism and
                    self.target_morphism == other.target_morphism)
        return False

    def __repr__(self):
        return (f"{self.name}: {self.source_morphism} => "
                f"{self.target_morphism} "
                f"({self.source_object} -> {self.target_object})")


class TwoCategory:
    """
    A strict 2-category.

    Strict means associativity and identity laws hold on the nose
    (not just up to isomorphism). This is sufficient for most
    applications and avoids the complexity of bicategories.
    """

    def __init__(self, name: str):
        self.name = name
        self.objects: Dict[str, Dict[str, Any]] = {}              # 0-cells
        self.morphisms: Dict[str, Dict[str, Any]] = {}            # 1-cells
        self.two_cells: Dict[str, TwoCell] = {}                   # 2-cells
        self._identity_2cells: Dict[str, TwoCell] = {}            # id_f for each 1-cell

    # === Construction ===

    def add_object(self, name: str, data: Dict = None) -> str:
        """Add a 0-cell (object)."""
        self.objects[name] = data or {}
        return name

    def add_morphism(self, name: str, source: str, target: str,
                     data: Dict = None) -> str:
        """Add a 1-cell (morphism) f : source -> target."""
        if source not in self.objects:
            self.add_object(source)
        if target not in self.objects:
            self.add_object(target)

        self.morphisms[name] = {
            "source": source,
            "target": target,
            "data": data or {},
        }
        return name

    def add_two_cell(self, name: str, source_mor: str, target_mor: str,
                     data: Dict = None) -> TwoCell:
        """
        Add a 2-cell alpha : source_mor => target_mor.

        Source and target morphisms must have the same domain and codomain.
        """
        if source_mor not in self.morphisms:
            raise ValueError(f"Unknown 1-cell: {source_mor}")
        if target_mor not in self.morphisms:
            raise ValueError(f"Unknown 1-cell: {target_mor}")

        src_data = self.morphisms[source_mor]
        tgt_data = self.morphisms[target_mor]

        if src_data["source"] != tgt_data["source"]:
            raise ValueError(
                f"Domain mismatch: {source_mor} has domain "
                f"{src_data['source']}, {target_mor} has domain "
                f"{tgt_data['source']}"
            )
        if src_data["target"] != tgt_data["target"]:
            raise ValueError(
                f"Codomain mismatch: {source_mor} has codomain "
                f"{src_data['target']}, {target_mor} has codomain "
                f"{tgt_data['target']}"
            )

        cell = TwoCell(
            name=name,
            source_morphism=source_mor,
            target_morphism=target_mor,
            source_object=src_data["source"],
            target_object=src_data["target"],
            data=data or {},
        )
        self.two_cells[name] = cell
        return cell

    # === Identity 2-cells ===

    def identity_two_cell(self, morphism: str) -> TwoCell:
        """
        The identity 2-cell id_f : f => f.

        For every 1-cell f, there is a 2-cell that does nothing:
        the identity transformation from f to itself.
        """
        if morphism not in self.morphisms:
            raise ValueError(f"Unknown 1-cell: {morphism}")

        if morphism not in self._identity_2cells:
            mor_data = self.morphisms[morphism]
            cell = TwoCell(
                name=f"id2_{morphism}",
                source_morphism=morphism,
                target_morphism=morphism,
                source_object=mor_data["source"],
                target_object=mor_data["target"],
                data={"is_identity": True},
            )
            self._identity_2cells[morphism] = cell
            self.two_cells[cell.name] = cell

        return self._identity_2cells[morphism]

    # === Vertical Composition ===

    def vertical_compose(self, alpha_name: str, beta_name: str) -> TwoCell:
        """
        Vertical composition: alpha : f => g, beta : g => h  =>  beta . alpha : f => h.

        This is "stacking" 2-cells: first transform f to g, then g to h.
        The intermediate morphism g must match.

            f
        A ====> B    alpha : f => g
            g
        A ====> B    beta : g => h
            h
        A ====> B

        Result: beta . alpha : f => h
        """
        if alpha_name not in self.two_cells:
            raise ValueError(f"Unknown 2-cell: {alpha_name}")
        if beta_name not in self.two_cells:
            raise ValueError(f"Unknown 2-cell: {beta_name}")

        alpha = self.two_cells[alpha_name]
        beta = self.two_cells[beta_name]

        # Identity shortcuts
        if alpha.data.get("is_identity"):
            return beta
        if beta.data.get("is_identity"):
            return alpha

        # Check compatibility: alpha.target = beta.source
        if alpha.target_morphism != beta.source_morphism:
            raise ValueError(
                f"Cannot vertically compose: {alpha_name} targets "
                f"{alpha.target_morphism} but {beta_name} sources from "
                f"{beta.source_morphism}"
            )

        # Check same globular cell (same domain/codomain objects)
        if (alpha.source_object != beta.source_object or
                alpha.target_object != beta.target_object):
            raise ValueError(
                f"Globular mismatch: {alpha_name} is over "
                f"({alpha.source_object} -> {alpha.target_object}) but "
                f"{beta_name} is over "
                f"({beta.source_object} -> {beta.target_object})"
            )

        composed_name = f"{beta_name}·{alpha_name}"
        cell = TwoCell(
            name=composed_name,
            source_morphism=alpha.source_morphism,
            target_morphism=beta.target_morphism,
            source_object=alpha.source_object,
            target_object=alpha.target_object,
            data={
                "vertical_from": [alpha_name, beta_name],
            },
        )
        self.two_cells[composed_name] = cell
        return cell

    # === Horizontal Composition ===

    def horizontal_compose(self, alpha_name: str, beta_name: str) -> TwoCell:
        """
        Horizontal composition:
          alpha : f => f'  (A -> B)
          beta  : g => g'  (B -> C)
          =>  beta * alpha : g.f => g'.f'  (A -> C)

        This is "side by side" composition: alpha transforms the first
        arrow while beta transforms the second.

            f       g
        A ====> B ====> C     alpha, beta
            f'      g'
        A ====> B ====> C

        Result: beta * alpha : g.f => g'.f'  (A -> C)
        """
        if alpha_name not in self.two_cells:
            raise ValueError(f"Unknown 2-cell: {alpha_name}")
        if beta_name not in self.two_cells:
            raise ValueError(f"Unknown 2-cell: {beta_name}")

        alpha = self.two_cells[alpha_name]
        beta = self.two_cells[beta_name]

        # Check compatibility: alpha.target_object = beta.source_object
        if alpha.target_object != beta.source_object:
            raise ValueError(
                f"Cannot horizontally compose: {alpha_name} targets "
                f"object {alpha.target_object} but {beta_name} sources "
                f"from object {beta.source_object}"
            )

        # Compose the source and target 1-cells
        src_composed = f"{beta.source_morphism}∘{alpha.source_morphism}"
        tgt_composed = f"{beta.target_morphism}∘{alpha.target_morphism}"

        # Ensure composed 1-cells exist
        if src_composed not in self.morphisms:
            self.add_morphism(
                src_composed, alpha.source_object, beta.target_object
            )
        if tgt_composed not in self.morphisms:
            self.add_morphism(
                tgt_composed, alpha.source_object, beta.target_object
            )

        composed_name = f"{beta_name}*{alpha_name}"
        cell = TwoCell(
            name=composed_name,
            source_morphism=src_composed,
            target_morphism=tgt_composed,
            source_object=alpha.source_object,
            target_object=beta.target_object,
            data={
                "horizontal_from": [alpha_name, beta_name],
            },
        )
        self.two_cells[composed_name] = cell
        return cell

    # === Whiskering ===

    def whisk_left(self, morphism: str, alpha_name: str) -> TwoCell:
        """
        Left whiskering: h * alpha  for h : B -> C, alpha : f => g (A -> B).

        Compose a 1-cell with a 2-cell on the left. This is horizontal
        composition where one side is an identity 2-cell.

            f       h
        A ====> B ----> C     alpha on left, h on right
            g       h
        A ====> B ----> C

        Result: h * alpha : h.f => h.g
        """
        id_h = self.identity_two_cell(morphism)
        return self.horizontal_compose(alpha_name, id_h.name)

    def whisk_right(self, alpha_name: str, morphism: str) -> TwoCell:
        """
        Right whiskering: alpha * h  for alpha : f => g (B -> C), h : A -> B.

        Compose a 1-cell with a 2-cell on the right.

            h       f
        A ----> B ====> C     h on left, alpha on right
            h       g
        A ----> B ====> C

        Result: alpha * h : f.h => g.h
        """
        id_h = self.identity_two_cell(morphism)
        return self.horizontal_compose(id_h.name, alpha_name)

    # === Godement Decomposition ===

    def godement_decompose(self, alpha_name: str,
                           beta_name: str) -> Dict[str, Any]:
        """
        Decompose horizontal composition via whiskering + vertical.

        The Godement product β * α can be computed two equivalent ways
        (this equivalence IS the interchange law):

          Way 1: (β . f) · (g' . α)
          Way 2: (g . α) · (β . f')

        where α : f => f' (A->B) and β : g => g' (B->C).

        Returns both decompositions and verifies they agree.

        Ref: nLab "Godement product"; Lack, "A 2-Categories Companion"
        """
        alpha = self.two_cells[alpha_name]
        beta = self.two_cells[beta_name]

        f = alpha.source_morphism
        f_prime = alpha.target_morphism
        g = beta.source_morphism
        g_prime = beta.target_morphism

        # Way 1: (β whisker f) then (g' whisker α)
        beta_f = self.whisk_right(beta_name, f)       # β . f  : g.f => g'.f
        g_prime_alpha = self.whisk_left(g_prime, alpha_name)  # g'.α : g'.f => g'.f'
        way1 = self.vertical_compose(beta_f.name, g_prime_alpha.name)

        # Way 2: (g whisker α) then (β whisker f')
        g_alpha = self.whisk_left(g, alpha_name)       # g.α : g.f => g.f'
        beta_f_prime = self.whisk_right(beta_name, f_prime)  # β.f' : g.f' => g'.f'
        way2 = self.vertical_compose(g_alpha.name, beta_f_prime.name)

        return {
            "way1": way1,
            "way2": way2,
            "agree": (way1.source_morphism == way2.source_morphism and
                      way1.target_morphism == way2.target_morphism),
        }

    # === Interchange Law ===

    def check_interchange(self, a1: str, a2: str,
                          b1: str, b2: str) -> bool:
        """
        Check the interchange law for a grid of four 2-cells.

        Given:
          a1 : f => g (A -> B)    b1 : h => k (B -> C)
          a2 : g => m (A -> B)    b2 : k => n (B -> C)

        The interchange law says:
          (a2 . a1) * (b2 . b1) = (a2 * b2) . (a1 * b1)

        Vertical-then-horizontal = horizontal-then-vertical.
        This is the key coherence condition for 2-categories.

        Returns True if the law holds (both sides give same type signature).
        """
        try:
            # Left side: vertical first, then horizontal
            vert_left = self.vertical_compose(a1, a2)
            vert_right = self.vertical_compose(b1, b2)
            lhs = self.horizontal_compose(vert_left.name, vert_right.name)

            # Right side: horizontal first, then vertical
            horiz_top = self.horizontal_compose(a1, b1)
            horiz_bot = self.horizontal_compose(a2, b2)
            rhs = self.vertical_compose(horiz_top.name, horiz_bot.name)

            # Compare: same source/target morphisms and same objects
            return (lhs.source_morphism == rhs.source_morphism and
                    lhs.target_morphism == rhs.target_morphism and
                    lhs.source_object == rhs.source_object and
                    lhs.target_object == rhs.target_object)
        except (ValueError, KeyError):
            return False

    # === Queries ===

    def two_cells_between(self, source_mor: str,
                          target_mor: str) -> List[TwoCell]:
        """Find all 2-cells from source_mor to target_mor."""
        return [
            cell for cell in self.two_cells.values()
            if (cell.source_morphism == source_mor and
                cell.target_morphism == target_mor)
        ]

    def all_two_cells_from(self, morphism: str) -> List[TwoCell]:
        """Find all 2-cells with source = morphism."""
        return [
            cell for cell in self.two_cells.values()
            if cell.source_morphism == morphism
        ]

    def all_two_cells_to(self, morphism: str) -> List[TwoCell]:
        """Find all 2-cells with target = morphism."""
        return [
            cell for cell in self.two_cells.values()
            if cell.target_morphism == morphism
        ]

    def morphisms_between(self, source_obj: str,
                          target_obj: str) -> List[str]:
        """Find all 1-cells from source_obj to target_obj."""
        return [
            name for name, data in self.morphisms.items()
            if data["source"] == source_obj and data["target"] == target_obj
        ]

    # === Store Bridge ===

    def to_store(self, store) -> None:
        """
        Persist 2-category to a KomposOSStore.

        Objects -> StoredObjects
        1-cells -> StoredMorphisms
        2-cells -> HigherMorphisms
        """
        from data.store import StoredObject, StoredMorphism, HigherMorphism

        for obj_name, obj_data in self.objects.items():
            store.add_object(StoredObject(
                name=obj_name,
                type_name="2cat_object",
                metadata=obj_data,
            ))

        for mor_name, mor_data in self.morphisms.items():
            store.add_morphism(StoredMorphism(
                name=mor_name,
                source_name=mor_data["source"],
                target_name=mor_data["target"],
                metadata=mor_data.get("data", {}),
            ))

        for cell in self.two_cells.values():
            store.add_higher_morphism(HigherMorphism(
                name=cell.name,
                source_path_id=cell.source_morphism,
                target_path_id=cell.target_morphism,
                transformation_type="2-cell",
                metadata={
                    "source_object": cell.source_object,
                    "target_object": cell.target_object,
                    **cell.data,
                },
            ))

    @classmethod
    def from_store(cls, store, name: str = "FromStore") -> 'TwoCategory':
        """
        Build a 2-category from store data.

        StoredObjects -> 0-cells
        StoredMorphisms -> 1-cells
        HigherMorphisms -> 2-cells
        """
        tc = cls(name)

        for obj in store.get_all_objects():
            tc.add_object(obj.name, obj.metadata)

        for mor in store.get_all_morphisms():
            tc.add_morphism(mor.name, mor.source_name, mor.target_name,
                            mor.metadata)

        for hm in store.get_all_higher_morphisms():
            src_mor = hm.source_path_id
            tgt_mor = hm.target_path_id

            # Determine source/target objects from metadata or morphism data
            src_obj = hm.metadata.get("source_object", "")
            tgt_obj = hm.metadata.get("target_object", "")

            if src_mor in tc.morphisms and tgt_mor in tc.morphisms:
                if not src_obj:
                    src_obj = tc.morphisms[src_mor]["source"]
                if not tgt_obj:
                    tgt_obj = tc.morphisms[src_mor]["target"]

                cell = TwoCell(
                    name=hm.name,
                    source_morphism=src_mor,
                    target_morphism=tgt_mor,
                    source_object=src_obj,
                    target_object=tgt_obj,
                    data=hm.metadata,
                )
                tc.two_cells[hm.name] = cell

        return tc

    def __repr__(self):
        return (f"TwoCategory({self.name}, "
                f"|0-cells|={len(self.objects)}, "
                f"|1-cells|={len(self.morphisms)}, "
                f"|2-cells|={len(self.two_cells)})")
