# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Phase 3 tests: PROP lift -- declared fork/merge, resource-aware sharing.

Sharing applies to *closed* sub-designs (no open inputs): those compute the
same value every time, so forking one result is sound. We model a closed
sub-design with a 0-arity source operation.
"""

import pytest

from operadum.core.operad import Operad
from operadum.core.prop import PROP, CopyError
from operadum.core.enrichment import ADDITIVE_COST, LINEAR_TOKENS
from operadum.core.types import Composite


def shared_design(op):
    """merge(source(), source()) -- the same closed sub-design twice."""
    src = op.get_op("source")
    merge = op.get_op("merge")
    sub = Composite(src, [])          # 0-arity => closed => shareable
    return Composite(merge, [("sub", sub), ("sub", sub)])


def test_copy_allowed_for_accumulative_resource():
    op = Operad("acc", monoid=ADDITIVE_COST)
    op.add_op("f", ["A"], "B", cost={"ms": 1}, fn=lambda x: x)
    prop = PROP(op)
    prop.declare_copy("B")          # additive cost copies freely
    assert prop.can_copy("B")


def test_copy_refused_for_linear_resource():
    op = Operad("lin", monoid=LINEAR_TOKENS)
    op.add_op("f", ["A"], "B", cost={"tok": 1}, fn=lambda x: x)
    prop = PROP(op)
    assert not prop.can_copy("B")
    with pytest.raises(CopyError):
        prop.declare_copy("B")


def test_copy_allowed_for_banged_linear_resource():
    op = Operad("lin", monoid=LINEAR_TOKENS)
    op.add_op("f", ["A"], "B", cost={"tok": 1}, fn=lambda x: x)
    prop = PROP(op, bang={"B"})     # ! restores copyability
    prop.declare_copy("B")
    assert prop.can_copy("B")


def test_sharing_saves_cost():
    op = Operad("share", monoid=ADDITIVE_COST)
    op.add_op("source", [], "Mid", cost={"ms": 10}, fn=lambda: 7)
    op.add_op("merge", ["Mid", "Mid"], "Out", cost={"ms": 1}, fn=lambda a, b: a + b)
    prop = PROP(op)
    report = prop.analyze_sharing(shared_design(op))
    assert "source" in report.shareable
    assert report.cost_unshared == {"ms": 21}   # 10 + 10 + 1
    assert report.cost_shared == {"ms": 11}     # 10 once + 1
    assert report.saves


def test_sharing_refused_for_linear():
    op = Operad("share-lin", monoid=LINEAR_TOKENS)
    op.add_op("source", [], "Mid", cost={"tok": 1}, fn=lambda: 7)
    op.add_op("merge", ["Mid", "Mid"], "Out", cost={}, fn=lambda a, b: a)
    prop = PROP(op)
    report = prop.analyze_sharing(shared_design(op))
    assert report.shareable == []
    assert report.refused and "linear" in report.refused[0][1]


def test_realize_shared_runs_each_op_once():
    op = Operad("exec", monoid=ADDITIVE_COST)
    op.add_op("source", [], "Mid", cost={"ms": 10}, fn=lambda: 21)
    op.add_op("merge", ["Mid", "Mid"], "Out", cost={"ms": 1}, fn=lambda a, b: a + b)
    prop = PROP(op)
    design = shared_design(op)        # merge(source(), source()), closed
    run, counts = prop.realize_shared(design)
    assert run() == 42                # 21 + 21
    assert counts["source"] == 1      # computed once, forked
    assert counts["merge"] == 1
