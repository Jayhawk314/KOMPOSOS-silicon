# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Program Synthesis -- the Curry-Howard-native domain.

OPERADUM's TypeEngine *is* inhabitation, so "synthesize a function of type
String -> Int" is the most native design problem there is: colours = types,
operations = typed pure functions, and a synthesized composite is a runnable
program. Many programs share an interface (length and sum are both
IntList -> Int), so a type alone underdetermines the design -- the SemanticGate
(operadum.gate.semantic_gate) picks the right one from input/output examples.

This domain needs no math library: the operations are tiny pure Python and the
artifacts execute directly. It is the cleanest demonstration of verified design
potential -- give a target behaviour, get a correct program back.
"""

from __future__ import annotations
from typing import List

from ..core.types import Operation, Spec
from ..core.enrichment import ResourceMonoid, ADDITIVE_COST
from .base import DomainPlugin, GroundTruthCase


def _fn(name, inputs, output, fn, ops=1) -> Operation:
    return Operation(name=name, inputs=list(inputs), output=output,
                     cost={"ops": ops}, metadata={"fn": name}, _fn=fn)


class ProgramSynthesisDomain(DomainPlugin):
    """Synthesize small list/number programs from examples."""

    name = "program-synthesis"

    def colours(self) -> List[str]:
        return ["String", "Words", "Chars", "Ints", "Int", "Bool"]

    def operations(self) -> List[Operation]:
        return [
            _fn("split_words",  ["String"], "Words", lambda s: s.split()),
            _fn("to_chars",     ["String"], "Chars", lambda s: list(s)),
            _fn("word_count",   ["Words"],  "Int",   lambda ws: len(ws)),
            _fn("char_count",   ["Chars"],  "Int",   lambda cs: len(cs)),
            _fn("word_lengths", ["Words"],  "Ints",  lambda ws: [len(w) for w in ws]),
            _fn("total",        ["Ints"],   "Int",   lambda xs: sum(xs)),
            _fn("longest",      ["Ints"],   "Int",   lambda xs: max(xs) if xs else 0),
            _fn("is_long",      ["Int"],    "Bool",  lambda n: n > 10),
        ]

    def resource_algebra(self) -> ResourceMonoid:
        return ADDITIVE_COST

    def ground_truth(self) -> List[GroundTruthCase]:
        # Each case fixes a behaviour via examples; the spec's TYPE is ambiguous
        # (several String -> Int programs exist), so only the SemanticGate solves it.
        return [
            GroundTruthCase(
                name="count words",
                spec=Spec(("String",), "Int",
                          constraints={"examples": [("a b c", 3), ("x y", 2), ("one", 1)]}),
                buildable=True, min_cost=2.0,
                note="word_count(split_words(s))",
            ),
            GroundTruthCase(
                name="count characters (incl. spaces)",
                spec=Spec(("String",), "Int",
                          constraints={"examples": [("ab cd", 5), ("x", 1)]}),
                buildable=True, min_cost=2.0,
                note="char_count(to_chars(s))",
            ),
            GroundTruthCase(
                name="total letters across words",
                spec=Spec(("String",), "Int",
                          constraints={"examples": [("ab cd", 4), ("a bcd", 4), ("hi", 2)]}),
                buildable=True, min_cost=3.0,
                note="total(word_lengths(split_words(s)))",
            ),
            GroundTruthCase(
                name="longest word length",
                spec=Spec(("String",), "Int",
                          constraints={"examples": [("a bbb cc", 3), ("xxxx y", 4)]}),
                buildable=True, min_cost=3.0,
                note="longest(word_lengths(split_words(s)))",
            ),
        ]
