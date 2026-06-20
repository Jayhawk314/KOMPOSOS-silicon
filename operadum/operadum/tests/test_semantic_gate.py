# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Design-by-specification: the SemanticGate filters type-correct designs by
behaviour. This is the verified test of design potential -- OPERADUM is given a
target behaviour and a component library, and returns a CORRECT artifact.
"""

import pytest

from operadum.core.types import Spec
from operadum.gate.semantic_gate import SemanticGate, enumerate_designs
from operadum.domains.program_synthesis import ProgramSynthesisDomain


def test_enumerate_designs_yields_many_type_correct_candidates():
    op = ProgramSynthesisDomain().build_operad()
    designs = enumerate_designs(op, Spec(("String",), "Int"), max_depth=4)
    wirings = {d.to_wiring() for d in designs}
    # Several distinct String -> Int programs are type-correct.
    assert "word_count(split_words(String))" in wirings
    assert "char_count(to_chars(String))" in wirings
    assert "total(word_lengths(split_words(String)))" in wirings
    assert len(wirings) >= 4
    # Cheapest-first ordering.
    costs = [sum(d.cost(op.monoid).values()) for d in designs]
    assert costs == sorted(costs)


def test_by_examples_picks_word_count():
    op = ProgramSynthesisDomain().build_operad()
    gate = SemanticGate(op, max_depth=5)
    design = gate.by_examples(Spec(("String",), "Int"),
                              examples=[("a b c", 3), ("x y", 2), ("one", 1)])
    assert design is not None
    assert design.wiring == "word_count(split_words(String))"
    assert design.artifact("hello world foo") == 3


def test_by_examples_picks_total_letters_not_word_count():
    """Same interface, different behaviour -> the gate must pick the other program."""
    op = ProgramSynthesisDomain().build_operad()
    gate = SemanticGate(op, max_depth=5)
    design = gate.by_examples(Spec(("String",), "Int"),
                              examples=[("ab cd", 4), ("a bcd", 4), ("hi", 2)])
    assert design is not None
    assert design.wiring == "total(word_lengths(split_words(String)))"
    assert design.artifact("aa bb cc") == 6


def test_by_examples_picks_longest_word():
    op = ProgramSynthesisDomain().build_operad()
    gate = SemanticGate(op, max_depth=5)
    design = gate.by_examples(Spec(("String",), "Int"),
                              examples=[("a bbb cc", 3), ("xxxx y", 4)])
    assert design is not None
    assert design.wiring == "longest(word_lengths(split_words(String)))"


def test_unsatisfiable_examples_return_none():
    op = ProgramSynthesisDomain().build_operad()
    gate = SemanticGate(op, max_depth=5)
    # No String -> Int program maps "a" to a negative number.
    assert gate.by_examples(Spec(("String",), "Int"), examples=[("a", -99)]) is None


def test_custom_validator():
    op = ProgramSynthesisDomain().build_operad()
    gate = SemanticGate(op, max_depth=4)
    # Find any String -> Bool design whose result on a long input is True.
    design = gate.synthesize(
        Spec(("String",), "Bool"),
        validator=lambda art, comp: art("a b c d e f g h i j k") is True,
    )
    assert design is not None
    assert design.composite.output == "Bool"
