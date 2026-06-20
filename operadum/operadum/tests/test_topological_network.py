# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Part 2 tests: design a network to a TOPOLOGICAL specification.

OPERADUM is given a target invariant (cycle rank, edge count) and a module
library, and synthesizes a network whose graph meets it -- verified by computing
the invariant on the synthesized Diagram.
"""

import pytest

from operadum.core.diagram import Diagram
from operadum.domains.topological_network import TopologicalNetworkDomain
from operadum.gate.diagram_synth import synthesize_diagram


def domain_operad():
    return TopologicalNetworkDomain().build_operad()


def test_graph_metrics_count_cycles():
    op = domain_operad()
    join = op.get_op("join")
    d = Diagram("diamond")
    s = d.add_input("s", "Node")
    a = d.add_node(op.get_op("relay"), [s])
    b = d.add_node(op.get_op("relay"), [s])     # s fans out to a and b
    top = d.add_node(join, [a, b])              # a and b rejoin -> one cycle
    d.set_output(top)
    m = d.graph_metrics()
    assert m["cycle_rank"] == 1                 # exactly one independent cycle


def test_synthesize_acyclic_network():
    op = domain_operad()
    domain = TopologicalNetworkDomain()
    result = synthesize_diagram(
        op, inputs=[("s", "Node")], output_colour="Node",
        validator=domain.cycle_rank(0), max_nodes=2)
    assert result is not None
    assert result.diagram.graph_metrics()["cycle_rank"] == 0   # a tree/path


def test_synthesize_network_with_required_cycles():
    """Demand a redundant (fault-tolerant) network: cycle rank >= 1."""
    op = domain_operad()
    domain = TopologicalNetworkDomain()
    result = synthesize_diagram(
        op, inputs=[("s", "Node")], output_colour="Node",
        validator=domain.cycle_rank(1), max_nodes=3)
    assert result is not None
    assert result.diagram.graph_metrics()["cycle_rank"] == 1


def test_synthesize_by_edge_budget():
    op = domain_operad()
    domain = TopologicalNetworkDomain()
    result = synthesize_diagram(
        op, inputs=[("s", "Node")], output_colour="Node",
        validator=domain.min_edges(3), max_nodes=3)
    assert result is not None
    assert result.diagram.graph_metrics()["edges"] >= 3
