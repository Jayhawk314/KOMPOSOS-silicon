# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
TYPE Engine: Realizability (Curry-Howard inhabitation)

One half of the Dual Gate (mirror of KOMPOSOS's ZFC+CAT dual engine). The
TYPE engine answers: does a type-correct realizer exist for this spec? It is
constructive proof search -- "is the output colour inhabited, given the input
colours and the available operations?"

It does NOT consider cost; that is the RES engine's job. The two engines
together decide a candidate's verdict.
"""

from __future__ import annotations
from typing import List, Optional, Set

from ..core.operad import Operad
from ..core.types import Composite, Spec


class TypeEngine:
    """
    Realizability checker via bounded type-directed inhabitation.

    Given a target colour and a set of colours we already hold (the spec's
    inputs), repeatedly fire any operation all of whose input colours are
    already inhabited, until the target colour becomes inhabited or no
    progress is possible. This decides type-realizability; WRIGHT's tiers
    reconstruct the actual witnessing composite.
    """

    def __init__(self, operad: Operad):
        self.operad = operad

    def inhabited_colours(self, given: Set[str], max_rounds: int = 64) -> Set[str]:
        """Forward-chain the colours reachable from `given` via the operations."""
        reachable: Set[str] = set(given)
        ops = self.operad.operations()
        for _ in range(max_rounds):
            grew = False
            for op in ops:
                if op.output in reachable:
                    continue
                if all(c in reachable for c in op.inputs):
                    reachable.add(op.output)
                    grew = True
            if not grew:
                break
        return reachable

    def is_realizable(self, spec: Spec) -> bool:
        """True iff the spec's output colour is reachable from its inputs."""
        return spec.output in self.inhabited_colours(set(spec.inputs))

    def realizes(self, comp: Composite, spec: Spec) -> bool:
        """
        True iff a concrete composite genuinely realizes the spec interface:
        it outputs the target colour and its open inputs are all drawn from
        (a sub-multiset of) the spec's allowed inputs.
        """
        if comp.output != spec.output:
            return False
        allowed = list(spec.inputs)
        for c in comp.open_inputs():
            if c in allowed:
                allowed.remove(c)
            else:
                return False
        return True
