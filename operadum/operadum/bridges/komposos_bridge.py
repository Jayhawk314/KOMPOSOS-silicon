# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
The Bridge to KOMPOSOS

OPERADUM designs; KOMPOSOS audits; the loop closes. Because both engines are
symmetric-monoidal at the bottom, an OPERADUM composite compiles into a
KOMPOSOS morphism graph, structure-preserving:

  - each unary operation        -> a morphism A -> B
  - each n-ary operation        -> a morphism from the monoidal product
                                   (A1 x ... x An) -> B  (recorded as a span)
  - wiring (operadic composition)-> categorical composition
  - resource cost               -> a quantale confidence via a chosen
                                   homomorphism (here: tropical-cost ->
                                   multiplicative-confidence, exp(-lambda*cost))

The compile is lossy on resources (the cost->confidence map is a modelling
choice, not a theorem) -- honest limitation #7 in the master spec. We emit a
plain graph dict so this module has NO hard dependency on a KOMPOSOS install;
`to_komposos_category` is offered as an optional adapter when one is present.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..core.types import Composite
from ..core.operad import Operad


@dataclass
class MorphismGraph:
    """A structure-preserving image of a composite as a KOMPOSOS-style graph."""
    objects: List[str] = field(default_factory=list)          # colours
    morphisms: List[Dict[str, Any]] = field(default_factory=list)
    root: Optional[str] = None                                # output colour

    def to_dict(self) -> Dict[str, Any]:
        return {"objects": self.objects, "morphisms": self.morphisms, "root": self.root}


def cost_to_confidence(cost: Dict[str, Any], lam: float = 0.05) -> float:
    """
    Tropical-cost -> multiplicative-confidence homomorphism.

    A composite's additive cost maps to a confidence in (0, 1] by
    exp(-lambda * total_cost): zero cost -> confidence 1, growing cost ->
    decaying confidence. Monoid homomorphism: cost(a)+cost(b) maps to
    conf(a)*conf(b), matching the multiplicative quantale's tensor.
    """
    total = sum(float(v) for v in cost.values()) if cost else 0.0
    return math.exp(-lam * total)


def compile_to_komposos(comp: Composite, operad: Operad,
                        lam: float = 0.05) -> MorphismGraph:
    """
    Compile an OPERADUM composite into a KOMPOSOS morphism graph.

    Each operation node becomes a morphism whose source is its (monoidal
    product of) input colours and whose target is its output colour, carrying
    a confidence derived from its own cost. Composition order is preserved by
    the shared colour names: the graph composes exactly where the wiring did.
    """
    graph = MorphismGraph(root=comp.output)
    objects: set[str] = set()

    def visit(node: Composite) -> None:
        objects.add(node.head.output)
        for c in node.head.inputs:
            objects.add(c)
        source = node.head.inputs[0] if len(node.head.inputs) == 1 else \
            "(" + " x ".join(node.head.inputs) + ")"
        graph.morphisms.append({
            "name": node.head.name,
            "source": source,
            "input_colours": list(node.head.inputs),
            "target": node.head.output,
            "arity": node.head.arity,
            "confidence": cost_to_confidence(node.head.cost, lam),
            "kind": "morphism" if node.head.arity == 1 else "span",
        })
        for kind, val in node.slots:
            if kind == "sub":
                visit(val)

    visit(comp)
    graph.objects = sorted(objects)
    return graph


def to_komposos_category(comp: Composite, operad: Operad, name: str = "operadum_design"):
    """
    Optional adapter: build an actual KOMPOSOS Category if one is importable.

    Returns the Category, or raises ImportError if KOMPOSOS is not installed.
    Kept dependency-free by importing lazily -- OPERADUM does not require
    KOMPOSOS to run.
    """
    try:
        from core.category import Category  # KOMPOSOS-IV's fused runtime
    except ImportError as exc:  # pragma: no cover - depends on external install
        raise ImportError(
            "KOMPOSOS-IV not importable; use compile_to_komposos() for a "
            "dependency-free graph dict instead."
        ) from exc

    graph = compile_to_komposos(comp, operad)
    cat = Category(name)
    for obj in graph.objects:
        cat.add(obj)
    for m in graph.morphisms:
        cat.connect(m["source"], m["target"], name=m["name"],
                    confidence=m["confidence"])
    return cat
