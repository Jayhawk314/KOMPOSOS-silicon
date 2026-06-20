# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Functors and Natural Transformations

A functor F: C → D maps objects to objects and morphisms to morphisms,
preserving composition and identity. A natural transformation η: F ⟹ G
provides a family of morphisms η_A: F(A) → G(A) satisfying naturality.

These are the inter-category constructions that KOMPOSOS-III never had.
Plugins are functors. Hot-reload is a natural transformation.
The runtime-reasoning relationship is an adjunction (see adjunction.py).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, Union, TYPE_CHECKING

from .types import Object, Morphism

if TYPE_CHECKING:
    from .category import Category


@dataclass
class Functor:
    """
    A functor F: source → target between two categories.

    Maps objects to objects and morphisms to morphisms, preserving
    composition and identity.

    Fields:
        name: Identifier for this functor.
        source: The source category C.
        target: The target category D.
        _object_map: Object name in C → object name in D.
        _morphism_map: Morphism ID in C → morphism ID in D.
    """
    name: str
    source: Category
    target: Category
    _object_map: Dict[str, str] = field(default_factory=dict)
    _morphism_map: Dict[str, str] = field(default_factory=dict)

    def __call__(self, x: Union[Object, Morphism]) -> Union[Object, Morphism]:
        """Apply the functor to an object or morphism."""
        if isinstance(x, Object):
            mapped_name = self._object_map.get(x.name)
            if mapped_name is None:
                raise KeyError(f"Object '{x.name}' not in functor's object map")
            result = self.target.get(mapped_name)
            if result is None:
                raise KeyError(f"Mapped object '{mapped_name}' not found in target category")
            return result
        elif isinstance(x, Morphism):
            mapped_id = self._morphism_map.get(x.id)
            if mapped_id is None:
                raise KeyError(f"Morphism '{x.id}' not in functor's morphism map")
            result = self.target.get_morphism(mapped_id)
            if result is None:
                raise KeyError(f"Mapped morphism '{mapped_id}' not found in target category")
            return result
        else:
            raise TypeError(f"Functor applies to Object or Morphism, got {type(x)}")

    def map_object(self, name: str) -> Optional[str]:
        """Get the mapped object name, or None."""
        return self._object_map.get(name)

    def map_morphism(self, mor_id: str) -> Optional[str]:
        """Get the mapped morphism ID, or None."""
        return self._morphism_map.get(mor_id)

    def verify(self) -> Dict[str, bool]:
        """
        Check that this functor preserves composition and identity.

        Returns dict with:
            - "objects": all mapped objects exist in target
            - "morphisms": all mapped morphisms exist with correct endpoints
            - "composition": F(g∘f) = F(g)∘F(f) for composable pairs
            - "identity": F(id_A) = id_{F(A)} (identity hom-values preserved)
        """
        results = {
            "objects": True,
            "morphisms": True,
            "composition": True,
            "identity": True,
        }

        # Check objects exist in target
        for src_name, tgt_name in self._object_map.items():
            if self.source.get(src_name) is None:
                results["objects"] = False
            if self.target.get(tgt_name) is None:
                results["objects"] = False

        # Check morphisms have correct endpoints
        for src_id, tgt_id in self._morphism_map.items():
            src_mor = self.source.get_morphism(src_id)
            tgt_mor = self.target.get_morphism(tgt_id)
            if src_mor is None or tgt_mor is None:
                results["morphisms"] = False
                continue
            # F(f: A→B) must be F(A)→F(B)
            expected_source = self._object_map.get(src_mor.source)
            expected_target = self._object_map.get(src_mor.target)
            if tgt_mor.source != expected_source or tgt_mor.target != expected_target:
                results["morphisms"] = False

        # Check composition preservation
        src_morphisms = self.source.morphisms()
        for f in src_morphisms:
            for g in src_morphisms:
                if f.target == g.source:
                    # f and g are composable: g∘f
                    f_mapped = self._morphism_map.get(f.id)
                    g_mapped = self._morphism_map.get(g.id)
                    if f_mapped is None or g_mapped is None:
                        continue
                    # Check that composed morphism maps correctly
                    # Find composed in source
                    composed_id = f"{g.name}.{f.name}:{f.source}->{g.target}"
                    composed_mapped = self._morphism_map.get(composed_id)
                    if composed_mapped is not None:
                        # Verify it equals F(g)∘F(f)
                        f_img = self.target.get_morphism(f_mapped)
                        g_img = self.target.get_morphism(g_mapped)
                        if f_img and g_img:
                            expected_composed = f"{g_img.name}.{f_img.name}:{f_img.source}->{g_img.target}"
                            if composed_mapped != expected_composed:
                                results["composition"] = False

        # Check identity preservation
        for src_name, tgt_name in self._object_map.items():
            src_hom = self.source.hom(src_name, src_name)
            tgt_hom = self.target.hom(tgt_name, tgt_name)
            if src_hom is not None and tgt_hom is not None:
                if src_hom != tgt_hom:
                    results["identity"] = False

        return results

    def compose(self, other: Functor) -> Functor:
        """
        Compose self after other: self ∘ other.

        If other: A → B and self: B → C, result: A → C.
        """
        if other.target is not self.source:
            raise TypeError(
                f"Cannot compose: {self.name} sources from '{self.source.name}' "
                f"but {other.name} targets '{other.target.name}'"
            )

        # Compose object maps: A→B→C
        new_obj_map = {}
        for a_name, b_name in other._object_map.items():
            c_name = self._object_map.get(b_name)
            if c_name is not None:
                new_obj_map[a_name] = c_name

        # Compose morphism maps
        new_mor_map = {}
        for a_id, b_id in other._morphism_map.items():
            c_id = self._morphism_map.get(b_id)
            if c_id is not None:
                new_mor_map[a_id] = c_id

        return Functor(
            name=f"{self.name}.{other.name}",
            source=other.source,
            target=self.target,
            _object_map=new_obj_map,
            _morphism_map=new_mor_map,
        )

    def is_faithful(self) -> bool:
        """
        Check if functor is faithful (injective on hom-sets).

        For each pair of objects A,B in C, F restricted to Hom(A,B)→Hom(F(A),F(B))
        is injective.
        """
        # Group source morphisms by (source, target)
        hom_sets: Dict[tuple, list] = {}
        for mor in self.source.morphisms():
            key = (mor.source, mor.target)
            hom_sets.setdefault(key, []).append(mor)

        for (a, b), mors in hom_sets.items():
            mapped_ids = set()
            for m in mors:
                mapped = self._morphism_map.get(m.id)
                if mapped is None:
                    continue
                if mapped in mapped_ids:
                    return False  # Two different morphisms map to same target
                mapped_ids.add(mapped)
        return True

    def is_full(self) -> bool:
        """
        Check if functor is full (surjective on hom-sets).

        For each pair F(A),F(B), every morphism in Hom(F(A),F(B)) is hit.
        """
        mapped_mor_ids = set(self._morphism_map.values())

        for a_src, a_tgt in self._object_map.items():
            for b_src, b_tgt in self._object_map.items():
                # All morphisms F(A)→F(B) in target should be in image
                for m in self.target.morphisms():
                    if m.source == a_tgt and m.target == b_tgt:
                        if m.id not in mapped_mor_ids:
                            return False
        return True

    def is_embedding(self) -> bool:
        """Full and faithful."""
        return self.is_full() and self.is_faithful()

    def __repr__(self) -> str:
        return (
            f"Functor('{self.name}': {self.source.name} -> {self.target.name}, "
            f"|Ob|={len(self._object_map)}, |Mor|={len(self._morphism_map)})"
        )


@dataclass
class NaturalTransformation:
    """
    A natural transformation η: F ⟹ G between functors F, G: C → D.

    For each object A in C, provides a component morphism η_A: F(A) → G(A) in D.
    These must satisfy the naturality condition: for every f: A → B in C,
        η_B ∘ F(f) = G(f) ∘ η_A

    Fields:
        name: Identifier.
        source_functor: The functor F.
        target_functor: The functor G.
        components: For each object A in C, the morphism ID of η_A: F(A) → G(A) in D.
    """
    name: str
    source_functor: Functor  # F
    target_functor: Functor  # G
    components: Dict[str, str] = field(default_factory=dict)  # obj name → morphism ID in D

    def __post_init__(self):
        if self.source_functor.source is not self.target_functor.source:
            raise TypeError(
                "Source functors must share the same source category"
            )
        if self.source_functor.target is not self.target_functor.target:
            raise TypeError(
                "Source functors must share the same target category"
            )

    @property
    def domain(self) -> Category:
        """The source category C."""
        return self.source_functor.source

    @property
    def codomain(self) -> Category:
        """The target category D."""
        return self.source_functor.target

    def verify(self) -> bool:
        """
        Check naturality: for every f: A → B in C,
            η_B ∘ F(f) = G(f) ∘ η_A
        in D.

        Returns True if all naturality squares commute.
        """
        F = self.source_functor
        G = self.target_functor
        D = self.codomain

        for f in F.source.morphisms():
            a, b = f.source, f.target

            # η_A and η_B component morphism IDs in D
            eta_a_id = self.components.get(a)
            eta_b_id = self.components.get(b)
            if eta_a_id is None or eta_b_id is None:
                return False

            eta_a = D.get_morphism(eta_a_id)
            eta_b = D.get_morphism(eta_b_id)
            if eta_a is None or eta_b is None:
                return False

            # F(f) and G(f) morphism IDs in D
            f_mapped_id = F.map_morphism(f.id)
            g_mapped_id = G.map_morphism(f.id)
            if f_mapped_id is None or g_mapped_id is None:
                return False

            f_mapped = D.get_morphism(f_mapped_id)
            g_mapped = D.get_morphism(g_mapped_id)
            if f_mapped is None or g_mapped is None:
                return False

            # Check: η_B ∘ F(f) should have same source/target as G(f) ∘ η_A
            # Left side: η_B ∘ F(f): F(A) → G(B)
            if f_mapped.target != eta_b.source:
                return False
            # Right side: G(f) ∘ η_A: F(A) → G(B)
            if eta_a.target != g_mapped.source:
                return False

            # Both paths: F(A) → G(B)
            # For enriched categories, check that confidence products match
            left_weight = D.quantale.tensor(f_mapped.confidence, eta_b.confidence)
            right_weight = D.quantale.tensor(eta_a.confidence, g_mapped.confidence)

            if abs(left_weight - right_weight) > 1e-10:
                return False

        return True

    def compose(self, other: NaturalTransformation) -> NaturalTransformation:
        """
        Vertical composition: self ∘ other.

        If other: F ⟹ G and self: G ⟹ H, result: F ⟹ H.
        Components: (self ∘ other)_A = self_A ∘ other_A.
        """
        if other.target_functor is not self.source_functor:
            raise TypeError(
                "Vertical composition requires other.target_functor == self.source_functor"
            )

        D = self.codomain
        new_components = {}

        for obj_name in other.components:
            other_a_id = other.components.get(obj_name)
            self_a_id = self.components.get(obj_name)
            if other_a_id is None or self_a_id is None:
                continue

            other_a = D.get_morphism(other_a_id)
            self_a = D.get_morphism(self_a_id)
            if other_a is None or self_a is None:
                continue

            # Compose in D: self_A ∘ other_A
            composed = D.compose(other_a, self_a)
            new_components[obj_name] = composed.id

        return NaturalTransformation(
            name=f"{self.name}.{other.name}",
            source_functor=other.source_functor,
            target_functor=self.target_functor,
            components=new_components,
        )

    def horizontal_compose(self, other: NaturalTransformation) -> NaturalTransformation:
        """
        Horizontal composition: self * other.

        If other: F ⟹ G (C → D) and self: H ⟹ K (D → E),
        result: H∘F ⟹ K∘G (C → E).
        Components: (self * other)_A = K(other_A) ∘ self_{F(A)}
                                     = self_{G(A)} ∘ H(other_A)
        """
        H = self.source_functor
        K = self.target_functor
        F = other.source_functor
        E = self.codomain

        # Compute H∘F and K∘G
        hf = H.compose(F)
        kg = K.compose(other.target_functor)

        new_components = {}
        for obj_name in other.components:
            # self_{F(A)} in E
            fa_name = F.map_object(obj_name)
            if fa_name is None:
                continue
            self_fa_id = self.components.get(fa_name)
            if self_fa_id is None:
                continue

            # K(other_A): K(F(A)) → K(G(A)) in E
            other_a_id = other.components.get(obj_name)
            if other_a_id is None:
                continue
            other_a = other.codomain.get_morphism(other_a_id)
            if other_a is None:
                continue

            k_other_a_id = K.map_morphism(other_a_id)
            if k_other_a_id is None:
                continue

            # Compose: K(other_A) ∘ self_{F(A)}
            self_fa = E.get_morphism(self_fa_id)
            k_other_a = E.get_morphism(k_other_a_id)
            if self_fa is None or k_other_a is None:
                continue

            composed = E.compose(self_fa, k_other_a)
            new_components[obj_name] = composed.id

        return NaturalTransformation(
            name=f"{self.name}*{other.name}",
            source_functor=hf,
            target_functor=kg,
            components=new_components,
        )

    def __repr__(self) -> str:
        return (
            f"NaturalTransformation('{self.name}': "
            f"{self.source_functor.name} => {self.target_functor.name}, "
            f"|components|={len(self.components)})"
        )
