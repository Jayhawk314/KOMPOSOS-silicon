# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Serialization -- the wiring DSL and JSON forms (Phase 5)

A composite already prints as a compact S-expression via `to_wiring()`:

    embed(tok(RawText))

This module makes that representation a round-trippable DSL: `parse_wiring`
reconstructs a Composite from the string plus the operad (resolving operation
names and treating bare identifiers as open-input colours), and `design_to_json`
emits a portable record of a design. Together they let designs be stored,
transmitted, and rebuilt -- the substrate for the wiring DSL and MCP server.
"""

from __future__ import annotations
import json
from typing import Any, Dict, List, Tuple

from .operad import Operad
from .types import Composite, Slot


# ---------------- emit ----------------

def to_wiring_dsl(comp: Composite) -> str:
    """The compact wiring S-expression, e.g. embed(tok(RawText))."""
    return comp.to_wiring()


def design_to_json(comp: Composite, operad: Operad) -> Dict[str, Any]:
    """A portable JSON record of a design: wiring + interface + cost."""
    iface = comp.interface
    return {
        "wiring": comp.to_wiring(),
        "inputs": list(iface.inputs),
        "output": iface.output,
        "cost": comp.cost(operad.monoid),
        "depth": comp.depth,
        "operations": [op.name for op in comp.operations()],
    }


def design_to_json_str(comp: Composite, operad: Operad, indent: int = 2) -> str:
    return json.dumps(design_to_json(comp, operad), indent=indent)


# ---------------- parse ----------------

def _tokenize(s: str) -> List[str]:
    tokens: List[str] = []
    buf = ""
    for ch in s:
        if ch in "(),":
            if buf.strip():
                tokens.append(buf.strip())
            buf = ""
            if ch != " ":
                tokens.append(ch)
        else:
            buf += ch
    if buf.strip():
        tokens.append(buf.strip())
    return tokens


def parse_wiring(s: str, operad: Operad) -> Composite:
    """
    Reconstruct a Composite from a wiring string and an operad.

    Grammar:
        node := NAME '(' node (',' node)* ')'    # an operation application
              | NAME                              # a colour (open input leaf)

    A NAME that resolves to an operation becomes the head of a sub-composite;
    any other NAME is an open input of that colour.
    """
    tokens = _tokenize(s)
    pos = 0

    def op_names() -> set:
        return {o.name for o in operad.operations()}

    known_ops = op_names()

    def parse_node() -> Tuple[str, Any]:
        nonlocal pos
        name = tokens[pos]; pos += 1
        if pos < len(tokens) and tokens[pos] == "(":
            pos += 1  # consume '('
            child_slots: List[Slot] = []
            while tokens[pos] != ")":
                child_slots.append(parse_node())
                if tokens[pos] == ",":
                    pos += 1
            pos += 1  # consume ')'
            op = operad.get_op(name)
            return ("sub", Composite(op, child_slots))
        # bare name
        if name in known_ops:
            op = operad.get_op(name)
            return ("sub", Composite(op, [("open", c) for c in op.inputs]))
        return ("open", name)   # a colour leaf

    kind, val = parse_node()
    if kind != "sub":
        raise ValueError(f"top-level wiring must be an operation, got colour {val!r}")
    return val
