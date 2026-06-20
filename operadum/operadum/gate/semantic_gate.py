# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
SemanticGate: the third gate -- design by specification

The Dual Gate (TYPE + RES) decides whether a design is type-correct and
resource-sound -- but many type-correct designs realize the same interface, and
only some of them are *the right one*. The SemanticGate closes that gap: it
enumerates type-correct designs in the operad's rank order and returns the
first whose *behaviour* satisfies a domain validator.

This is the constructive heart of "design potential": OPERADUM is given only a
target behaviour (input/output examples, a target unitary, a truth table) and a
component library, and it designs a correct artifact -- which the validator then
confirms independently. The validator is exactly where a specialized toolkit
plugs in (a simulator, a solver, a test suite, KOMPOSOS).

  TYPE gate  -> does a realizer exist?
  RES gate   -> is it resource-sound / in budget?
  SEMANTIC   -> does the realized artifact actually DO the right thing?
"""

from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from itertools import product
from typing import Any, Callable, List, Optional, Tuple

from ..core.operad import Operad
from ..core.types import Composite, Spec
from ..daedalus_core import _submultiset


@dataclass
class VerifiedDesign:
    """A design that passed the semantic validator."""
    composite: Composite
    cost: dict
    artifact: Callable
    candidates_tried: int

    @property
    def wiring(self) -> str:
        return self.composite.to_wiring()

    def __str__(self) -> str:
        return f"VerifiedDesign({self.wiring}, cost={self.cost})"


def enumerate_designs(operad: Operad, spec: Spec, max_depth: int = 5,
                      limit: int = 5000) -> List[Composite]:
    """
    Every type-correct design (depth-bounded) realizing the spec interface,
    ranked by the operad's monoid. The candidate stream the SemanticGate filters.

    A design realizes the spec iff it outputs the target colour and its open
    inputs are a sub-multiset of the spec's inputs.
    """
    allowed = set(spec.inputs)
    pool = Counter(spec.inputs)
    out: List[Composite] = []
    seen: set[str] = set()

    def designs(target: str, depth: int) -> List[Composite]:
        comps: List[Composite] = []
        if depth < 1:
            return comps
        for op in operad.operations_producing(target):
            slot_opts: List[List] = []
            ok = True
            for colour in op.inputs:
                opts: List = []
                if colour in allowed:
                    opts.append(("open", colour))
                if depth > 1:
                    for sub in designs(colour, depth - 1):
                        opts.append(("sub", sub))
                if not opts:
                    ok = False
                    break
                slot_opts.append(opts)
            if not ok:
                continue
            for combo in product(*slot_opts):
                comps.append(Composite(op, list(combo)))
        return comps

    for comp in designs(spec.output, max_depth):
        if not _submultiset(Counter(comp.open_inputs()), pool):
            continue
        key = comp.to_wiring()
        if key in seen:
            continue
        seen.add(key)
        out.append(comp)
        if len(out) >= limit:
            break

    out.sort(key=lambda c: (operad.monoid.rank(c.cost(operad.monoid)), c.to_wiring()))
    return out


class SemanticGate:
    """Synthesizes the best-ranked design whose behaviour passes a validator."""

    def __init__(self, operad: Operad, max_depth: int = 6):
        self.operad = operad
        self.max_depth = max_depth

    def synthesize(self, spec: Spec,
                   validator: Callable[[Callable, Composite], bool],
                   limit: int = 5000) -> Optional[VerifiedDesign]:
        """
        Return the best-ranked type-correct design whose realized artifact passes
        `validator(artifact, composite)`, or None if none does.
        """
        tried = 0
        for comp in enumerate_designs(self.operad, spec, self.max_depth, limit):
            try:
                artifact = self.operad.realize(comp)
            except ValueError:
                continue   # not executable -> cannot validate behaviour
            tried += 1
            try:
                ok = validator(artifact, comp)
            except Exception:
                ok = False
            if ok:
                return VerifiedDesign(comp, comp.cost(self.operad.monoid),
                                      artifact, tried)
        return None

    def by_examples(self, spec: Spec,
                    examples: List[Tuple[Any, Any]],
                    limit: int = 5000) -> Optional[VerifiedDesign]:
        """
        Programming/design by example: find the best-ranked design whose artifact
        maps every example input to its expected output.

        Each example is (inputs, expected); `inputs` is a tuple of arguments
        (or a single value, auto-wrapped) matching the design's open inputs.
        """
        def normalise(args: Any) -> tuple:
            return args if isinstance(args, tuple) else (args,)

        def validator(artifact: Callable, _comp: Composite) -> bool:
            for args, expected in examples:
                if artifact(*normalise(args)) != expected:
                    return False
            return True

        return self.synthesize(spec, validator, limit)
