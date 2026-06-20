# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Diagram synthesis -- search over typed DAGs

The SemanticGate enumerates *trees*; this enumerates *diagrams* (DAGs with
distinguished inputs and fan-out), so it can design networks the tree
synthesizer cannot -- e.g. a boolean function from a single NAND gate, where
the same wire fans out to several gates.

It grows diagrams a node at a time (smallest-first), wiring each new node from
any existing sources of matching colour (reuse and fan-out allowed), and accepts
the first whose realized artifact passes a validator. Search over DAGs is
combinatorial; this is a bounded, honest enumerator for small designs (the place
a SAT/ILP backend would slot in for scale).
"""

from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..core.diagram import Diagram, Source
from ..core.operad import Operad
from ..core.types import Operation


@dataclass
class VerifiedDiagram:
    diagram: Diagram
    artifact: Callable
    nodes: int
    candidates_tried: int

    @property
    def wiring(self) -> str:
        return self.diagram.to_wiring()


def _candidate_wirings(op: Operation, sources_by_colour: Dict[str, List[Source]]):
    """All ways to wire `op`'s inputs from available sources of each colour."""
    per_slot = [sources_by_colour.get(c, []) for c in op.inputs]
    if any(len(s) == 0 for s in per_slot):
        return
    for combo in product(*per_slot):
        yield list(combo)


def synthesize_diagram(operad: Operad,
                       inputs: List[Tuple[str, str]],
                       output_colour: str,
                       validator: Callable[[Callable, Diagram], bool],
                       gate_ops: Optional[List[str]] = None,
                       max_nodes: int = 4,
                       limit: int = 200000) -> Optional[VerifiedDiagram]:
    """
    Design the smallest typed DAG with the given named boundary `inputs` and a
    node producing `output_colour`, whose artifact passes `validator`.

    `inputs` is a list of (name, colour). `gate_ops` restricts the operation
    library (default: all of the operad's operations).
    """
    ops = [operad.get_op(n) for n in gate_ops] if gate_ops else operad.operations()
    tried = 0

    def base_diagram() -> Tuple[Diagram, Dict[str, List[Source]]]:
        d = Diagram("synth")
        by_colour: Dict[str, List[Source]] = {}
        for name, colour in inputs:
            src = d.add_input(name, colour)
            by_colour.setdefault(colour, []).append(src)
        return d, by_colour

    # Breadth-first over node count: returns the smallest passing diagram.
    # A "frontier" item is (diagram, sources_by_colour, last_node_src).
    frontier: List[Tuple[Diagram, Dict[str, List[Source]], Optional[Source]]] = []
    d0, by0 = base_diagram()
    frontier.append((d0, by0, None))

    for _depth in range(max_nodes):
        next_frontier = []
        for diagram, by_colour, _last in frontier:
            for op in ops:
                for wiring in _candidate_wirings(op, by_colour):
                    tried += 1
                    if tried > limit:
                        return None
                    new_d = _clone(diagram)
                    new_by = {c: list(v) for c, v in by_colour.items()}
                    src = new_d.add_node(op, wiring)
                    new_by.setdefault(op.output, []).append(src)
                    # Try this node as the output if it has the right colour.
                    if op.output == output_colour:
                        new_d.set_output(src)
                        try:
                            artifact = new_d.realize()
                        except ValueError:
                            artifact = None
                        if artifact is not None:
                            try:
                                ok = validator(artifact, new_d)
                            except Exception:
                                ok = False
                            if ok:
                                return VerifiedDiagram(new_d, artifact,
                                                       len(new_d._nodes), tried)
                        new_d._output = None  # keep growing with output unset
                    next_frontier.append((new_d, new_by, src))
        frontier = next_frontier
    return None


def _clone(d: Diagram) -> Diagram:
    """A shallow structural clone (nodes/inputs copied; ops shared)."""
    c = Diagram(d.name)
    c._inputs = list(d._inputs)
    c._input_colour = dict(d._input_colour)
    c._nodes = {nid: (op, list(srcs)) for nid, (op, srcs) in d._nodes.items()}
    c._output = d._output
    c._counter = d._counter
    return c


def truth_table_validator(table: List[Tuple[Dict[str, Any], Any]]):
    """A validator that checks an artifact against (named-inputs, expected) rows."""
    def validate(artifact: Callable, _diagram: Diagram) -> bool:
        for assignment, expected in table:
            if artifact(**assignment) != expected:
                return False
        return True
    return validate
