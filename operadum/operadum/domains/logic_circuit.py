# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Logic-Circuit Design -- the domain the tree layer could not do.

Boolean functions are built from gates over a single colour `Bit`, where inputs
fan out to many gates and the same wire is reused -- a DAG, not a tree. With
NAND (a universal gate) as the only primitive, designing NOT/AND/OR/XOR forces
exactly the fan-out and distinguished-input structure the Diagram layer adds.

Designs are verified by their truth table: OPERADUM is given a target boolean
function and a gate library, and it synthesizes a circuit a truth-table check
then confirms. This is design + verification on networks.
"""

from __future__ import annotations
from typing import Any, Dict, List, Tuple

from ..core.types import Operation
from ..core.enrichment import ResourceMonoid, ADDITIVE_COST
from .base import DomainPlugin


def _gate(name: str, fn, arity: int = 2) -> Operation:
    return Operation(name=name, inputs=["Bit"] * arity, output="Bit",
                     cost={"gates": 1}, metadata={"gate": name}, _fn=fn)


#: A boolean target: (name, [(input_name, "Bit"), ...], truth_table)
Target = Tuple[str, List[Tuple[str, str]], List[Tuple[Dict[str, Any], Any]]]


def _table2(fn) -> List[Tuple[Dict[str, Any], Any]]:
    return [({"a": a, "b": b}, fn(a, b)) for a in (False, True) for b in (False, True)]


def _table1(fn) -> List[Tuple[Dict[str, Any], Any]]:
    return [({"a": a}, fn(a)) for a in (False, True)]


class LogicCircuitDomain(DomainPlugin):
    """Universal boolean logic from NAND (and a fuller library if you want it)."""

    name = "logic-circuit"

    def colours(self) -> List[str]:
        return ["Bit"]

    def operations(self) -> List[Operation]:
        return [
            _gate("nand", lambda a, b: not (a and b)),
            _gate("and",  lambda a, b: a and b),
            _gate("or",   lambda a, b: a or b),
            _gate("xor",  lambda a, b: a != b),
            _gate("not",  lambda a: not a, arity=1),
        ]

    def resource_algebra(self) -> ResourceMonoid:
        return ADDITIVE_COST   # minimise gate count

    # Truth-table targets (not the tree-optimize ground_truth harness).
    def targets(self) -> List[Target]:
        return [
            ("NOT", [("a", "Bit")], _table1(lambda a: not a)),
            ("AND", [("a", "Bit"), ("b", "Bit")], _table2(lambda a, b: a and b)),
            ("OR",  [("a", "Bit"), ("b", "Bit")], _table2(lambda a, b: a or b)),
            ("XOR", [("a", "Bit"), ("b", "Bit")], _table2(lambda a, b: a != b)),
        ]
