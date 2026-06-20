# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Synthesis-Route Design -- the first OPERADUM domain.

A deliberate complement to the KOMPOSOS-IV-CHEM base model: KOMPOSOS
*interprets* chemistry (relates molecules, verifies claims); OPERADUM *designs*
a synthesis route -- a wiring of reactions that builds a target molecule from
available building blocks, cheapest-first.

  Colours    = molecular species (building blocks, intermediates, target).
  Operations = reactions: reactants -> product, costing dollars per step.
  Resource   = additive cost (dollars accumulate along the route).

The toy route graph below has two ways to reach Aniline (a cheap two-step
nitrate+reduce, or a dear one-step shortcut), so the cost-minimal route to
Paracetamol is a non-trivial choice -- ideal for measuring optimum recall and
for the KOMPOSOS round-trip (each reaction becomes a morphism; the route is a
categorical path the base engine can verify).
"""

from __future__ import annotations
from typing import List

from ..core.types import Operation, Spec
from ..core.enrichment import ResourceMonoid, ADDITIVE_COST
from .base import DomainPlugin, GroundTruthCase


def _reaction(name: str, reactants: List[str], product: str, usd: float) -> Operation:
    """A reaction as an executable operation: it 'produces' the named product."""
    return Operation(
        name=name,
        inputs=list(reactants),
        output=product,
        cost={"usd": usd},
        metadata={"reaction": name},
        _fn=lambda *_reagents, _p=product: _p,   # running the route yields the product
    )


class SynthesisDesignDomain(DomainPlugin):
    """A small organic-synthesis route-design domain."""

    name = "synthesis-design"

    def colours(self) -> List[str]:
        return [
            "Benzene", "Toluene", "Nitrobenzene", "Aniline",
            "BenzoicAcid", "Acetanilide", "Paracetamol",
        ]

    def operations(self) -> List[Operation]:
        return [
            _reaction("methylate",   ["Benzene"],      "Toluene",      usd=5),
            _reaction("oxidize",     ["Toluene"],      "BenzoicAcid",  usd=8),
            _reaction("nitrate",     ["Benzene"],      "Nitrobenzene", usd=4),
            _reaction("reduce",      ["Nitrobenzene"], "Aniline",      usd=6),
            _reaction("aminate",     ["Benzene"],      "Aniline",      usd=20),  # dear shortcut
            _reaction("acetylate",   ["Aniline"],      "Acetanilide",  usd=7),
            _reaction("hydroxylate", ["Acetanilide"],  "Paracetamol",  usd=9),
        ]

    def resource_algebra(self) -> ResourceMonoid:
        return ADDITIVE_COST

    def ground_truth(self) -> List[GroundTruthCase]:
        return [
            GroundTruthCase(
                name="Benzene -> Paracetamol",
                spec=Spec(inputs=("Benzene",), output="Paracetamol"),
                buildable=True, min_cost=26.0,   # nitrate4+reduce6+acetylate7+hydroxylate9
                note="nitrate -> reduce -> acetylate -> hydroxylate (not the $20 shortcut)",
            ),
            GroundTruthCase(
                name="Benzene -> Aniline",
                spec=Spec(inputs=("Benzene",), output="Aniline"),
                buildable=True, min_cost=10.0,   # nitrate4+reduce6, beats aminate $20
                note="cheapest Aniline is nitrate+reduce, not the one-step shortcut",
            ),
            GroundTruthCase(
                name="Benzene -> BenzoicAcid",
                spec=Spec(inputs=("Benzene",), output="BenzoicAcid"),
                buildable=True, min_cost=13.0,   # methylate5 + oxidize8
                note="methylate -> oxidize",
            ),
            GroundTruthCase(
                name="Toluene -> Paracetamol (no route)",
                spec=Spec(inputs=("Toluene",), output="Paracetamol"),
                buildable=False, min_cost=None,
                note="Toluene only reaches BenzoicAcid; Paracetamol is unreachable",
            ),
        ]
