# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Polytope: Higher Operadic / Resource Reasoning (Layer 2.5)

The constructive dual of KOMPOSOS-IV's ∞-Cosmos. Wraps an Operad and builds
higher structure over it:

  - Coherence cells (associahedra). Two wirings that should be equal -- the
    re-bracketings of an associative composite -- are connected by rewrite
    cells. The associahedron K_n is exactly the polytope of these bracketings;
    its vertices are the Catalan-many bracketings, its edges the single
    associativity rewrites. Mac Lane coherence says they all collapse to one
    normal form, so "the design" is well-defined independent of assembly order.

  - Unit coherence. Identity operations are two-sided units; a design may drop
    them without changing meaning.

  - Distributive laws. Two operads compose safely (a control operad over a data
    operad) only when a distributive law exists; we refuse when it does not.

Based on: Mac Lane coherence, Leinster (Higher Operads, Higher Categories),
Stasheff associahedra.

This module ships the associativity/unit coherence used by WRIGHT Tier 4 and
the formal CoherenceProver. PROP lifting lives in prop.py.
"""

from __future__ import annotations
from typing import List, Set, Tuple

from .operad import Operad
from .types import Composite, Operation, Slot


class Polytope:
    """
    Higher coherence structure over an Operad.

    Declare which operations are associative and which colours carry a unit;
    Polytope then provides one-step rewrites, a deterministic normal form, and
    associahedron enumeration. Equivalent designs share a normal form, so the
    synthesizer can treat them as one.
    """

    def __init__(self, operad: Operad):
        self.operad = operad
        self.associative: Set[str] = set()   # operation names declared associative
        self.unit_colours: Set[str] = set()  # colours with a declared unit

    # ---------------- declarations ----------------

    def declare_associative(self, op_name: str) -> "Polytope":
        """Declare a binary operation associative: f(f(a,b),c) = f(a,f(b,c))."""
        self.associative.add(op_name)
        return self

    def declare_unit(self, colour: str) -> "Polytope":
        """Declare that `colour` carries a (two-sided) identity unit."""
        self.unit_colours.add(colour)
        return self

    # ---------------- identity recognition ----------------

    @staticmethod
    def is_identity(op: Operation) -> bool:
        """An operation is an identity iff it is 1_C : (C) -> C."""
        return (op.inputs == [op.output] and op.name == f"id_{op.output}")

    # ---------------- normal form ----------------

    def normalize(self, comp: Composite) -> Composite:
        """
        The unique coherence normal form of a design:
          1. normalize sub-designs,
          2. eliminate identity (unit) nodes,
          3. right-associate every declared-associative operation.

        Confluence + termination (proved in formal_coherence) make this a true
        normal form: equivalent designs map to the *same* composite.
        """
        # 1-2. Normalize children, collapsing identity sub-nodes.
        new_slots: List[Slot] = []
        for kind, val in comp.slots:
            if kind == "sub":
                nv = self.normalize(val)
                if self.is_identity(nv.head):
                    new_slots.append(nv.slots[0])  # 1_C(x) = x
                else:
                    new_slots.append(("sub", nv))
            else:
                new_slots.append((kind, val))
        comp = Composite(comp.head, new_slots)

        # 2'. Collapse an identity at the head.
        if self.is_identity(comp.head):
            return comp  # 1_C with an open input is already minimal

        # 3. Right-associate.
        if comp.head.name in self.associative:
            operands = self._flatten_assoc(comp, comp.head.name)
            return self._build_right(comp.head, operands)
        return comp

    def _flatten_assoc(self, comp: Composite, name: str) -> List[Slot]:
        """Flatten a maximal tree of one associative op into its operand slots."""
        operands: List[Slot] = []
        for kind, val in comp.slots:
            if kind == "sub" and val.head.name == name:
                operands.extend(self._flatten_assoc(val, name))
            else:
                operands.append((kind, val))
        return operands

    def _build_right(self, op: Operation, operands: List[Slot]) -> Composite:
        """Rebuild a right-associated composite from a flat operand list."""
        if len(operands) == 2:
            return Composite(op, [operands[0], operands[1]])
        rest = self._build_right(op, operands[1:])
        return Composite(op, [operands[0], ("sub", rest)])

    # ---------------- equivalence ----------------

    def equivalent(self, a: Composite, b: Composite) -> bool:
        """True iff two designs share a coherence normal form."""
        return self.normalize(a).to_wiring() == self.normalize(b).to_wiring()

    # ---------------- one-step rewrites (coherence cells) ----------------

    def one_step_rewrites(self, comp: Composite) -> List[Tuple[str, Composite]]:
        """
        Every single coherence-cell rewrite applicable to `comp`, oriented
        toward the normal form (left-rotation + unit elimination). These are
        the edges of the associahedron; `formal_coherence` checks they are
        locally confluent.
        """
        results: List[Tuple[str, Composite]] = []

        # Associativity rotation at the root: f(f(a,b),c) -> f(a,f(b,c)).
        if comp.head.name in self.associative:
            kind, left = comp.slots[0]
            if kind == "sub" and left.head.name == comp.head.name:
                a, b = left.slots[0], left.slots[1]
                c = comp.slots[1]
                rotated = Composite(comp.head, [a, ("sub", Composite(comp.head, [b, c]))])
                results.append(("assoc-rotate", rotated))

        # Unit elimination at the root.
        if self.is_identity(comp.head):
            kind, val = comp.slots[0]
            if kind == "sub":
                results.append(("unit-elim", val))

        # Recurse into children.
        for idx, (kind, val) in enumerate(comp.slots):
            if kind == "sub":
                for rule, nv in self.one_step_rewrites(val):
                    new_slots = list(comp.slots)
                    new_slots[idx] = ("sub", nv)
                    results.append((rule, Composite(comp.head, new_slots)))
        return results

    # ---------------- associahedron ----------------

    def bracketings(self, op: Operation, operands: List[Composite]) -> List[Composite]:
        """
        Every binary bracketing of `operands` under an associative `op` -- the
        vertices of the associahedron K_n. There are Catalan(n-1) of them, and
        Mac Lane coherence says all normalize to one form.
        """
        if len(operands) == 1:
            return [operands[0]]
        out: List[Composite] = []
        for i in range(1, len(operands)):
            for left in self.bracketings(op, operands[:i]):
                for right in self.bracketings(op, operands[i:]):
                    out.append(Composite(op, [("sub", left), ("sub", right)]))
        return out
