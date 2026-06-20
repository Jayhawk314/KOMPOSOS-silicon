# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Limits and Colimits — Universal Constructions

Products, coproducts, pullbacks, pushouts, equalizers, terminal and
initial objects. Each construction creates new Object(s) and Morphism(s)
in the category and returns a Cone or Cocone witnessing the universal
property.

These complete KOMPOSOS-IV's categorical vocabulary: with Category
(1-cells), Functor (inter-category maps), and now universal
constructions, the runtime can express any finite diagram.
"""

from __future__ import annotations
from typing import Tuple, TYPE_CHECKING

from .types import Cone, Cocone

if TYPE_CHECKING:
    from .category import Category


def product(cat: Category, a: str, b: str) -> Cone:
    """
    Binary product: creates A×B with projections π₁: A×B → A, π₂: A×B → B.

    Universal property: for any C with f: C→A, g: C→B, there exists a
    unique h: C→A×B such that π₁∘h = f and π₂∘h = g.

    Args:
        cat: The category to build the product in.
        a: Name of first object.
        b: Name of second object.

    Returns:
        Cone with apex "a×b" and projection legs.
    """
    apex_name = f"{a}\u00d7{b}"  # × character

    # Ensure source objects exist
    if cat.get(a) is None:
        cat.add(a)
    if cat.get(b) is None:
        cat.add(b)

    # Create product object
    cat.add(apex_name, type_name="Product", metadata={"factors": [a, b]})

    # Create projection morphisms (structural, confidence=1.0)
    pi1 = cat.connect(apex_name, a, name=f"\u03c0\u2081", confidence=1.0)
    pi2 = cat.connect(apex_name, b, name=f"\u03c0\u2082", confidence=1.0)

    return Cone(
        apex=apex_name,
        legs={a: pi1.id, b: pi2.id},
    )


def coproduct(cat: Category, a: str, b: str) -> Cocone:
    """
    Binary coproduct: creates A+B with injections ι₁: A → A+B, ι₂: B → A+B.

    Universal property: for any C with f: A→C, g: B→C, there exists a
    unique h: A+B→C such that h∘ι₁ = f and h∘ι₂ = g.

    Args:
        cat: The category to build the coproduct in.
        a: Name of first object.
        b: Name of second object.

    Returns:
        Cocone with apex "a+b" and injection legs.
    """
    apex_name = f"{a}+{b}"

    if cat.get(a) is None:
        cat.add(a)
    if cat.get(b) is None:
        cat.add(b)

    cat.add(apex_name, type_name="Coproduct", metadata={"summands": [a, b]})

    iota1 = cat.connect(a, apex_name, name="\u03b9\u2081", confidence=1.0)
    iota2 = cat.connect(b, apex_name, name="\u03b9\u2082", confidence=1.0)

    return Cocone(
        apex=apex_name,
        legs={a: iota1.id, b: iota2.id},
    )


def equalizer(cat: Category, f_id: str, g_id: str) -> Tuple[str, str]:
    """
    Equalizer of two parallel morphisms f, g: A → B.

    Creates object Eq(f,g) and morphism e: Eq(f,g) → A such that f∘e = g∘e.

    Args:
        cat: The category.
        f_id: Morphism ID of f: A → B.
        g_id: Morphism ID of g: A → B.

    Returns:
        (equalizer_object_name, equalizer_morphism_id)

    Raises:
        ValueError: If f and g are not parallel (same source and target).
    """
    f = cat.get_morphism(f_id)
    g = cat.get_morphism(g_id)
    if f is None or g is None:
        raise ValueError(f"Morphism not found: {f_id if f is None else g_id}")
    if f.source != g.source or f.target != g.target:
        raise ValueError(
            f"Morphisms must be parallel: {f.source}→{f.target} vs {g.source}→{g.target}"
        )

    eq_name = f"Eq({f.name},{g.name})"
    cat.add(eq_name, type_name="Equalizer", metadata={
        "of": [f_id, g_id],
        "source": f.source,
        "target": f.target,
    })

    e = cat.connect(eq_name, f.source, name="e", confidence=1.0)

    return (eq_name, e.id)


def pullback(cat: Category, f_id: str, g_id: str) -> Cone:
    """
    Pullback over a cospan f: A → C, g: B → C.

    Creates object A×_C B with projections π₁: A×_C B → A, π₂: A×_C B → B
    such that f∘π₁ = g∘π₂.

    Args:
        cat: The category.
        f_id: Morphism ID of f: A → C.
        g_id: Morphism ID of g: B → C.

    Returns:
        Cone with apex and projection legs.

    Raises:
        ValueError: If f and g don't share a common target.
    """
    f = cat.get_morphism(f_id)
    g = cat.get_morphism(g_id)
    if f is None or g is None:
        raise ValueError(f"Morphism not found: {f_id if f is None else g_id}")
    if f.target != g.target:
        raise ValueError(
            f"Pullback requires common target: {f.target} vs {g.target}"
        )

    a, b, c = f.source, g.source, f.target
    apex_name = f"{a}\u00d7_{c}{b}"  # A×_C B

    cat.add(apex_name, type_name="Pullback", metadata={
        "over": c, "left": a, "right": b,
        "left_morphism": f_id, "right_morphism": g_id,
    })

    # Confidence on projections inherits the weaker of f,g
    proj_conf = min(f.confidence, g.confidence)
    pi1 = cat.connect(apex_name, a, name="\u03c0\u2081", confidence=proj_conf)
    pi2 = cat.connect(apex_name, b, name="\u03c0\u2082", confidence=proj_conf)

    return Cone(
        apex=apex_name,
        legs={a: pi1.id, b: pi2.id},
    )


def pushout(cat: Category, f_id: str, g_id: str) -> Cocone:
    """
    Pushout over a span f: C → A, g: C → B.

    Creates object A+_C B with injections ι₁: A → A+_C B, ι₂: B → A+_C B
    such that ι₁∘f = ι₂∘g.

    Args:
        cat: The category.
        f_id: Morphism ID of f: C → A.
        g_id: Morphism ID of g: C → B.

    Returns:
        Cocone with apex and injection legs.

    Raises:
        ValueError: If f and g don't share a common source.
    """
    f = cat.get_morphism(f_id)
    g = cat.get_morphism(g_id)
    if f is None or g is None:
        raise ValueError(f"Morphism not found: {f_id if f is None else g_id}")
    if f.source != g.source:
        raise ValueError(
            f"Pushout requires common source: {f.source} vs {g.source}"
        )

    c, a, b = f.source, f.target, g.target
    apex_name = f"{a}+_{c}{b}"

    cat.add(apex_name, type_name="Pushout", metadata={
        "over": c, "left": a, "right": b,
        "left_morphism": f_id, "right_morphism": g_id,
    })

    inj_conf = min(f.confidence, g.confidence)
    iota1 = cat.connect(a, apex_name, name="\u03b9\u2081", confidence=inj_conf)
    iota2 = cat.connect(b, apex_name, name="\u03b9\u2082", confidence=inj_conf)

    return Cocone(
        apex=apex_name,
        legs={a: iota1.id, b: iota2.id},
    )


def terminal(cat: Category) -> str:
    """
    Create a terminal object with a unique morphism from every existing object.

    The terminal object ⊤ satisfies: for every object A, there exists a
    unique morphism !_A: A → ⊤.

    Returns:
        Name of the terminal object ("⊤").
    """
    t_name = "\u22a4"  # ⊤
    cat.add(t_name, type_name="Terminal")

    for obj in cat.objects():
        if obj.name != t_name:
            cat.connect(obj.name, t_name, name="!", confidence=1.0)

    return t_name


def initial(cat: Category) -> str:
    """
    Create an initial object with a unique morphism to every existing object.

    The initial object ⊥ satisfies: for every object A, there exists a
    unique morphism ¡_A: ⊥ → A.

    Returns:
        Name of the initial object ("⊥").
    """
    i_name = "\u22a5"  # ⊥
    cat.add(i_name, type_name="Initial")

    for obj in cat.objects():
        if obj.name != i_name:
            cat.connect(i_name, obj.name, name="\u00a1", confidence=1.0)

    return i_name
