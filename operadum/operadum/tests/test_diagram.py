# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Part 1 tests: the Diagram (string-diagram / DAG) layer + diagram synthesis.

The headline: XOR from NAND -- distinguished inputs and fan-out that a tree
cannot express -- built, run, and verified by truth table; then synthesized.
"""

import pytest

from operadum.core.diagram import Diagram
from operadum.core.enrichment import ADDITIVE_COST
from operadum.domains.logic_circuit import LogicCircuitDomain
from operadum.gate.diagram_synth import synthesize_diagram, truth_table_validator


def nand_op():
    return LogicCircuitDomain().build_operad().get_op("nand")


# ---------------------------------------------------------------- structure

def test_distinguished_inputs_and_fanout():
    """NOT a = nand(a, a): one input fanned out to BOTH gate slots."""
    nand = nand_op()
    d = Diagram("not")
    a = d.add_input("a", "Bit")
    n = d.add_node(nand, [a, a])          # a used twice -- impossible in a tree
    d.set_output(n)
    assert d.type_check()
    run = d.realize()
    assert run(a=False) is True and run(a=True) is False


def test_xor_from_nand_by_hand():
    """XOR with the classic 4-NAND circuit: n1 fans out to n2 and n3 (a DAG)."""
    nand = nand_op()
    d = Diagram("xor")
    a = d.add_input("a", "Bit")
    b = d.add_input("b", "Bit")
    n1 = d.add_node(nand, [a, b])
    n2 = d.add_node(nand, [a, n1])
    n3 = d.add_node(nand, [b, n1])        # n1 shared by n2 AND n3
    n4 = d.add_node(nand, [n2, n3])
    d.set_output(n4)
    assert d.type_check()
    run = d.realize()
    for a_, b_ in [(False, False), (False, True), (True, False), (True, True)]:
        assert run(a=a_, b=b_) == (a_ != b_)
    # Sharing: 4 distinct gates, each costed once.
    assert d.cost(ADDITIVE_COST) == {"gates": 4}
    # The shared wire makes the underlying graph have cycles.
    assert d.graph_metrics()["cycle_rank"] >= 1


def test_realize_runs_shared_node_once():
    nand = nand_op()
    calls = {"n": 0}
    counting = nand_op()
    counting._fn = lambda a, b: (calls.__setitem__("n", calls["n"] + 1) or (not (a and b)))
    d = Diagram("share")
    a = d.add_input("a", "Bit")
    n1 = d.add_node(counting, [a, a])
    n2 = d.add_node(nand, [n1, n1])       # n1 feeds n2 twice -> still computed once
    d.set_output(n2)
    d.realize()(a=True)
    assert calls["n"] == 1                # the shared node ran a single time


# ---------------------------------------------------------------- synthesis

def test_synthesize_not_and_or_from_nand():
    op = LogicCircuitDomain().build_operad()
    domain = LogicCircuitDomain()
    wanted = {name: (ins, table) for name, ins, table in domain.targets()}
    for name in ("NOT", "AND", "OR"):
        ins, table = wanted[name]
        result = synthesize_diagram(
            op, inputs=ins, output_colour="Bit",
            validator=truth_table_validator(table),
            gate_ops=["nand"], max_nodes=3)
        assert result is not None, name
        # Verify the synthesized circuit against the full truth table.
        for assignment, expected in table:
            assert result.artifact(**assignment) == expected, (name, assignment)


def test_synthesize_xor_from_nand():
    op = LogicCircuitDomain().build_operad()
    _, ins, table = next(t for t in LogicCircuitDomain().targets() if t[0] == "XOR")
    result = synthesize_diagram(
        op, inputs=ins, output_colour="Bit",
        validator=truth_table_validator(table),
        gate_ops=["nand"], max_nodes=4)
    assert result is not None
    for assignment, expected in table:
        assert result.artifact(**assignment) == expected
    assert result.nodes <= 4
