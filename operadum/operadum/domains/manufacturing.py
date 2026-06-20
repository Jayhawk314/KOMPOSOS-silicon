# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Manufacturing / Bill-of-Materials Design -- the multiset-resource domain.

Assemble a product from raw materials through a sequence of fabrication steps;
the resource is MULTISET_MATERIALS, so a design's cost is the *bill of
materials* it consumes -- counts of parts accumulate. "Cheapest" means the
lightest bill. Offering two frame routes (steel vs aluminium) makes the
material trade-off a real design choice.

A third resource algebra (after additive cost and peak memory), and another
additive-style (sum) compile -> the KOMPOSOS round-trip is AGREE.
"""

from __future__ import annotations
from typing import List

from ..core.types import Operation, Spec
from ..core.enrichment import ResourceMonoid, MULTISET_MATERIALS
from .base import DomainPlugin, GroundTruthCase


def _step(name: str, inputs: List[str], output: str, bom: dict) -> Operation:
    return Operation(name=name, inputs=list(inputs), output=output, cost=dict(bom),
                     metadata={"step": name}, _fn=lambda *_p, _o=output: _o)


class ManufacturingDomain(DomainPlugin):
    """Assemble a bicycle; cost = the bill of materials consumed."""

    name = "manufacturing"

    def colours(self) -> List[str]:
        return ["Steel", "Aluminum", "Rubber", "Frame", "Wheelset", "Bicycle"]

    def operations(self) -> List[Operation]:
        return [
            _step("steel_frame", ["Steel"],    "Frame",    {"steel": 4}),
            _step("alu_frame",   ["Aluminum"], "Frame",    {"aluminum": 3}),
            _step("wheelset",    ["Rubber"],   "Wheelset", {"rubber": 2, "steel": 1}),
            _step("assemble",    ["Frame", "Wheelset"], "Bicycle", {"bolts": 6}),
        ]

    def resource_algebra(self) -> ResourceMonoid:
        return MULTISET_MATERIALS

    def ground_truth(self) -> List[GroundTruthCase]:
        return [
            GroundTruthCase(
                name="Bicycle from Steel + Rubber",
                spec=Spec(("Steel", "Rubber"), "Bicycle"),
                buildable=True, min_cost=13.0,   # steel 4+1, rubber 2, bolts 6
                note="assemble(steel_frame(Steel), wheelset(Rubber))",
            ),
            GroundTruthCase(
                name="Bicycle from Aluminum + Rubber (lighter bill)",
                spec=Spec(("Aluminum", "Rubber"), "Bicycle"),
                buildable=True, min_cost=12.0,   # aluminum 3, steel 1, rubber 2, bolts 6
                note="assemble(alu_frame(Aluminum), wheelset(Rubber))",
            ),
            GroundTruthCase(
                name="Bicycle from Rubber alone (no frame material)",
                spec=Spec(("Rubber",), "Bicycle"),
                buildable=False, min_cost=None,
                note="no frame can be built without Steel or Aluminum",
            ),
        ]
