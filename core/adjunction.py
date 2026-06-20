# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Adjunctions — The Heart of Category Theory

An adjunction F ⊣ G says that F: C → D and G: D → C are "inverses up
to natural transformation." The unit η: id_C ⟹ G∘F measures "how far
from a retraction" and the counit ε: F∘G ⟹ id_D measures "how far
from a section."

In the KOMPOSOS runtime: plugins are left adjoints (free constructions),
the forgetful functor strips structure, and the unit/counit encode
the round-trip cost.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, Optional, TYPE_CHECKING

from .functor import Functor, NaturalTransformation

if TYPE_CHECKING:
    from .category import Category


@dataclass
class Adjunction:
    """
    An adjunction F ⊣ G with unit η and counit ε.

    F: C → D  (left adjoint — "free" / construction)
    G: D → C  (right adjoint — "forgetful" / specification)
    η: id_C ⟹ G∘F  (unit)
    ε: F∘G ⟹ id_D  (counit)

    Triangle identities:
        ε_{F(A)} ∘ F(η_A) = id_{F(A)}  for all A in C
        G(ε_B) ∘ η_{G(B)} = id_{G(B)}  for all B in D
    """
    left: Functor    # F: C → D
    right: Functor   # G: D → C
    unit: NaturalTransformation    # η: id_C ⟹ G∘F
    counit: NaturalTransformation  # ε: F∘G ⟹ id_D

    def verify(self) -> Dict[str, bool]:
        """
        Verify the adjunction: unit/counit naturality + triangle identities.

        Returns dict with:
            - "unit_natural": η is a natural transformation
            - "counit_natural": ε is a natural transformation
            - "left_triangle": ε_{F(A)} ∘ F(η_A) = id_{F(A)}
            - "right_triangle": G(ε_B) ∘ η_{G(B)} = id_{G(B)}
        """
        F = self.left
        G = self.right
        C = F.source
        D = F.target

        results = {
            "unit_natural": self.unit.verify(),
            "counit_natural": self.counit.verify(),
            "left_triangle": True,
            "right_triangle": True,
        }

        # Left triangle: ε_{F(A)} ∘ F(η_A) = id_{F(A)} for all A in C
        for obj in C.objects():
            a_name = obj.name
            fa_name = F.map_object(a_name)
            if fa_name is None:
                continue

            # η_A: A → GF(A) in C
            eta_a_id = self.unit.components.get(a_name)
            if eta_a_id is None:
                results["left_triangle"] = False
                continue

            # F(η_A): F(A) → FGF(A) in D
            f_eta_a_id = F.map_morphism(eta_a_id)
            if f_eta_a_id is None:
                results["left_triangle"] = False
                continue

            # ε_{F(A)}: FG(F(A)) → F(A) in D
            eps_fa_id = self.counit.components.get(fa_name)
            if eps_fa_id is None:
                results["left_triangle"] = False
                continue

            f_eta_a = D.get_morphism(f_eta_a_id)
            eps_fa = D.get_morphism(eps_fa_id)
            if f_eta_a is None or eps_fa is None:
                results["left_triangle"] = False
                continue

            # ε_{F(A)} ∘ F(η_A) should be identity: source=F(A), target=F(A), confidence=unit
            if f_eta_a.target != eps_fa.source:
                results["left_triangle"] = False
                continue

            composed_conf = D.quantale.tensor(f_eta_a.confidence, eps_fa.confidence)
            identity_conf = D.hom(fa_name, fa_name)
            if identity_conf is not None and abs(composed_conf - identity_conf) > 1e-10:
                results["left_triangle"] = False

        # Right triangle: G(ε_B) ∘ η_{G(B)} = id_{G(B)} for all B in D
        for obj in D.objects():
            b_name = obj.name
            gb_name = G.map_object(b_name)
            if gb_name is None:
                continue

            # ε_B: FG(B) → B in D
            eps_b_id = self.counit.components.get(b_name)
            if eps_b_id is None:
                results["right_triangle"] = False
                continue

            # G(ε_B): GFG(B) → G(B) in C
            g_eps_b_id = G.map_morphism(eps_b_id)
            if g_eps_b_id is None:
                results["right_triangle"] = False
                continue

            # η_{G(B)}: G(B) → GFG(B) in C
            eta_gb_id = self.unit.components.get(gb_name)
            if eta_gb_id is None:
                results["right_triangle"] = False
                continue

            g_eps_b = C.get_morphism(g_eps_b_id)
            eta_gb = C.get_morphism(eta_gb_id)
            if g_eps_b is None or eta_gb is None:
                results["right_triangle"] = False
                continue

            if eta_gb.target != g_eps_b.source:
                results["right_triangle"] = False
                continue

            composed_conf = C.quantale.tensor(eta_gb.confidence, g_eps_b.confidence)
            identity_conf = C.hom(gb_name, gb_name)
            if identity_conf is not None and abs(composed_conf - identity_conf) > 1e-10:
                results["right_triangle"] = False

        return results

    def is_equivalence(self) -> bool:
        """
        Check if this adjunction is an equivalence of categories.

        An adjunction is an equivalence iff both unit and counit are
        natural isomorphisms (all components are isomorphisms).
        """
        D = self.left.target
        C = self.left.source

        # Check unit components are isos: for each η_A: A → GF(A),
        # there exists an inverse GF(A) → A
        for obj_name, eta_id in self.unit.components.items():
            eta = C.get_morphism(eta_id)
            if eta is None:
                return False
            # Check for inverse morphism
            inverses = [
                m for m in C.morphisms()
                if m.source == eta.target and m.target == eta.source
            ]
            if not inverses:
                return False

        # Check counit components are isos
        for obj_name, eps_id in self.counit.components.items():
            eps = D.get_morphism(eps_id)
            if eps is None:
                return False
            inverses = [
                m for m in D.morphisms()
                if m.source == eps.target and m.target == eps.source
            ]
            if not inverses:
                return False

        return True

    def __repr__(self) -> str:
        return (
            f"Adjunction({self.left.name} -| {self.right.name}, "
            f"{self.left.source.name} <-> {self.left.target.name})"
        )


def adjunction_from_hom_iso(
    F: Functor,
    G: Functor,
    iso_map: Dict[tuple, tuple],
) -> Adjunction:
    """
    Build an adjunction from the hom-set isomorphism
    Hom_D(F(A), B) ≅ Hom_C(A, G(B)).

    Args:
        F: Left adjoint functor C → D.
        G: Right adjoint functor D → C.
        iso_map: Maps (A, B) to (morphism_id_in_D, morphism_id_in_C)
                 witnessing the bijection for the unit/counit.

    Returns:
        An Adjunction with derived unit and counit.
    """
    C = F.source
    D = F.target

    # Derive unit: η_A = iso_map applied to id_{F(A)}: A → GF(A)
    unit_components = {}
    for obj in C.objects():
        a = obj.name
        fa = F.map_object(a)
        if fa is None:
            continue
        key = (a, fa)
        if key in iso_map:
            _, eta_a_id = iso_map[key]
            unit_components[a] = eta_a_id

    # Derive counit: ε_B = iso_map applied to id_{G(B)}: FG(B) → B
    counit_components = {}
    for obj in D.objects():
        b = obj.name
        gb = G.map_object(b)
        if gb is None:
            continue
        key = (gb, b)
        if key in iso_map:
            eps_b_id, _ = iso_map[key]
            counit_components[b] = eps_b_id

    # Build identity functors for unit/counit source/target
    # Unit: id_C ⟹ G∘F
    gf = G.compose(F)

    # Build id_C functor
    id_c_obj = {o.name: o.name for o in C.objects()}
    id_c_mor = {m.id: m.id for m in C.morphisms()}
    id_C = Functor("id_" + C.name, C, C, id_c_obj, id_c_mor)

    unit = NaturalTransformation(
        name="η",
        source_functor=id_C,
        target_functor=gf,
        components=unit_components,
    )

    # Counit: F∘G ⟹ id_D
    fg = F.compose(G)

    id_d_obj = {o.name: o.name for o in D.objects()}
    id_d_mor = {m.id: m.id for m in D.morphisms()}
    id_D = Functor("id_" + D.name, D, D, id_d_obj, id_d_mor)

    counit = NaturalTransformation(
        name="ε",
        source_functor=fg,
        target_functor=id_D,
        components=counit_components,
    )

    return Adjunction(left=F, right=G, unit=unit, counit=counit)


def free_forgetful(
    C: Category,
    D: Category,
    embed_obj: Dict[str, str],
    embed_mor: Dict[str, str],
    project_obj: Dict[str, str],
    project_mor: Dict[str, str],
) -> Adjunction:
    """
    Build a free-forgetful adjunction from explicit embed/project maps.

    Common pattern: embed objects from a "plain" category C into a
    "richer" category D (free), then project back (forgetful).

    Args:
        C: The "plain" category.
        D: The "rich" category.
        embed_obj: Object map C → D for the left (free) functor.
        embed_mor: Morphism map C → D for the left (free) functor.
        project_obj: Object map D → C for the right (forgetful) functor.
        project_mor: Morphism map D → C for the right (forgetful) functor.

    Returns:
        An Adjunction F ⊣ G.
    """
    F = Functor("Free", C, D, embed_obj, embed_mor)
    G = Functor("Forgetful", D, C, project_obj, project_mor)

    # Build unit η: id_C ⟹ G∘F
    gf = G.compose(F)
    id_c_obj = {o.name: o.name for o in C.objects()}
    id_c_mor = {m.id: m.id for m in C.morphisms()}
    id_C = Functor("id_" + C.name, C, C, id_c_obj, id_c_mor)

    # Unit components: η_A: A → GF(A) in C
    unit_components = {}
    for obj in C.objects():
        a = obj.name
        gfa = gf.map_object(a)
        if gfa is not None:
            # Look for morphism A → GF(A) in C
            for m in C.morphisms():
                if m.source == a and m.target == gfa:
                    unit_components[a] = m.id
                    break

    # Build counit ε: F∘G ⟹ id_D
    fg = F.compose(G)
    id_d_obj = {o.name: o.name for o in D.objects()}
    id_d_mor = {m.id: m.id for m in D.morphisms()}
    id_D = Functor("id_" + D.name, D, D, id_d_obj, id_d_mor)

    # Counit components: ε_B: FG(B) → B in D
    counit_components = {}
    for obj in D.objects():
        b = obj.name
        fgb = fg.map_object(b)
        if fgb is not None:
            for m in D.morphisms():
                if m.source == fgb and m.target == b:
                    counit_components[b] = m.id
                    break

    unit = NaturalTransformation("η", id_C, gf, unit_components)
    counit = NaturalTransformation("ε", fg, id_D, counit_components)

    return Adjunction(left=F, right=G, unit=unit, counit=counit)
