# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Topological-Network Design -- design validated by topological invariants.

Where the logic-circuit domain validates a network by *behaviour* (a truth
table), this one validates by *shape*: a synthesized Diagram's underlying graph
must meet a topological requirement -- a target cycle rank (first Betti number),
edge-connectivity (fault tolerance), or node budget.

It makes the manual's claim concrete: when the artifact IS a network,
topological invariants become the spec and the validator -- and they are
computed in pure stdlib on the Diagram's graph (a `networkx` would attach here
at the leaf, never in the core). This is the bridge from the network layer
(Part 1) to materials, where a MOF is exactly a topological net of nodes and
linkers.

Components are typed "module" operations over a single colour `Node`; a design
wires modules into a network, and we ask for a network with a required topology.
"""

from __future__ import annotations
from typing import Callable, Dict, List

from ..core.types import Operation
from ..core.diagram import Diagram
from ..core.enrichment import ResourceMonoid, ADDITIVE_COST
from .base import DomainPlugin


def _module(name: str, fanin: int) -> Operation:
    """A network module with `fanin` incoming links, producing a Node."""
    return Operation(
        name=name, inputs=["Node"] * fanin, output="Node", cost={"modules": 1},
        metadata={"module": name},
        _fn=lambda *links, _n=name: {"module": _n, "links": list(links)},
    )


class TopologicalNetworkDomain(DomainPlugin):
    """Design networks of modules; validate by topological invariants."""

    name = "topological-network"

    def colours(self) -> List[str]:
        return ["Node"]

    def operations(self) -> List[Operation]:
        # Modules with 1, 2 or 3 incoming links -> richer topologies.
        return [_module("relay", 1), _module("join", 2), _module("hub", 3)]

    def resource_algebra(self) -> ResourceMonoid:
        return ADDITIVE_COST   # minimise module count

    # ---- topological validators (operate on a Diagram's graph) ----

    @staticmethod
    def cycle_rank(target: int) -> Callable:
        """Accept a network whose underlying graph has first Betti number == target
        (i.e. exactly `target` independent cycles -- redundant paths)."""
        def validate(_artifact: Callable, diagram: Diagram) -> bool:
            return diagram.graph_metrics()["cycle_rank"] == target
        return validate

    @staticmethod
    def min_edges(target: int) -> Callable:
        """Accept a network with at least `target` links (a crude redundancy floor)."""
        def validate(_artifact: Callable, diagram: Diagram) -> bool:
            return diagram.graph_metrics()["edges"] >= target
        return validate
