# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Phase 2 tests: linear-logic typing (the non-cartesian discipline).
"""

import pytest

from operadum.core.operad import Operad
from operadum.core.enrichment import LINEAR_TOKENS
from operadum.core.linear import (
    LinearChecker, Atom, Tensor, Lolli, OfCourse, tensor,
    operation_signature, composite_signature,
)


def test_operation_signature_is_a_lollipop():
    op = Operad("sig")
    op.add_op("join", ["A", "B"], "C", fn=lambda a, b: (a, b))
    sig = operation_signature(op.get_op("join"))
    assert isinstance(sig, Lolli)
    assert str(sig) == "(A (x) B) -o C"


def test_bang_marks_copyable_inputs():
    op = Operad("bang")
    op.add_op("f", ["Config", "Data"], "Out", fn=lambda c, d: d)
    sig = operation_signature(op.get_op("f"), bang={"Config"})
    assert str(sig) == "(!Config (x) Data) -o Out"


def test_composite_signature_reports_open_inputs():
    op = Operad("comp")
    op.add_op("a2b", ["A"], "B", fn=lambda x: x)
    op.add_op("b2c", ["B"], "C", fn=lambda x: x)
    design = op.compose("b2c", 0, "a2b")
    assert str(composite_signature(design)) == "(A) -o C"


def test_checker_passes_a_linear_tree():
    op = Operad("ok", monoid=LINEAR_TOKENS)
    op.add_op("use", ["Site"], "Built", cost={"permit_1": 1}, fn=lambda x: x)
    design = op.get_op("use").as_composite()
    judgement = LinearChecker().judge(design)
    assert judgement.ok
    assert judgement.duplicated == []


def test_checker_flags_contraction():
    """Two operations both spend the same token -> contraction -> unsound."""
    op = Operad("dup")
    op.add_op("a", ["X"], "Y", cost={"permit": 1}, fn=lambda x: x)
    op.add_op("b", ["Y"], "Z", cost={"permit": 1}, fn=lambda x: x)
    design = op.compose("b", 0, "a")     # both legs spend `permit`
    judgement = LinearChecker().judge(design)
    assert not judgement.ok
    assert judgement.duplicated == ["permit"]
    assert "CONTRACTION" in str(judgement)


def test_bang_exempts_contraction():
    """A banged token may be reused without violating linearity."""
    op = Operad("dup")
    op.add_op("a", ["X"], "Y", cost={"license": 1}, fn=lambda x: x)
    op.add_op("b", ["Y"], "Z", cost={"license": 1}, fn=lambda x: x)
    design = op.compose("b", 0, "a")
    judgement = LinearChecker(bang={"license"}).judge(design)
    assert judgement.ok                  # ! restores the right to copy


def test_tensor_helper_collapses_singletons():
    assert tensor(Atom("A")) == Atom("A")
    assert isinstance(tensor(Atom("A"), Atom("B")), Tensor)
