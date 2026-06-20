# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Phase 1 tests: the write path.

Exit criterion (master spec, Phase 1): give a Spec (target interface), get
back a BUILDABLE construction or a principled gap. Covers all four verdicts
plus the OPERADUM -> KOMPOSOS compile.
"""

import pytest

from operadum.core.operad import Operad
from operadum.core.types import Spec
from operadum.core.enrichment import ADDITIVE_COST
from operadum.wright.engine import Wright
from operadum.wright.schema import Verdict
from operadum.bridges.komposos_bridge import compile_to_komposos


def make_operad():
    op = Operad("pipeline", monoid=ADDITIVE_COST)
    op.add_op("tokenize", ["RawText"], "Tokens", cost={"ms": 2}, fn=lambda s: s.split())
    op.add_op("embed", ["Tokens"], "Embedding", cost={"ms": 8}, fn=lambda t: len(t))
    return op


def test_tier0_direct_match():
    op = make_operad()
    w = Wright(op)
    result = w.synthesize(Spec(inputs=("Tokens",), output="Embedding"))
    assert result.verdict == Verdict.BUILDABLE
    assert result.tier == 0
    assert result.construction.wiring == "embed(Tokens)"


def test_tier1_single_composition():
    op = make_operad()
    w = Wright(op)
    result = w.synthesize(Spec(inputs=("RawText",), output="Embedding"))
    assert result.verdict == Verdict.BUILDABLE
    assert result.tier == 1
    assert result.construction.cost == {"ms": 10}
    # The construction is executable.
    run = result.construction.artifact
    assert run("a b c") == 3


def test_tier2_bounded_tree_search():
    op = Operad("multi")
    op.add_op("a", ["In"], "Mid1", cost={"c": 1}, fn=lambda x: x)
    op.add_op("b", ["Mid1"], "Mid2", cost={"c": 1}, fn=lambda x: x)
    op.add_op("c", ["Mid2"], "Out", cost={"c": 1}, fn=lambda x: x)
    w = Wright(op)
    result = w.synthesize(Spec(inputs=("In",), output="Out"))
    assert result.verdict == Verdict.BUILDABLE
    assert result.tier == 2
    assert result.construction.wiring == "c(b(a(In)))"
    assert result.construction.cost == {"c": 3}


def test_overbudget_verdict():
    op = make_operad()
    w = Wright(op)
    spec = Spec(inputs=("RawText",), output="Embedding", budget={"ms": 5})
    result = w.synthesize(spec)
    assert result.verdict == Verdict.OVERBUDGET
    assert result.construction is not None  # a wiring exists, it's just too dear


def test_in_budget_is_buildable():
    op = make_operad()
    w = Wright(op)
    spec = Spec(inputs=("RawText",), output="Embedding", budget={"ms": 20})
    assert w.synthesize(spec).verdict == Verdict.BUILDABLE


def test_impossible_verdict():
    op = make_operad()
    w = Wright(op)
    result = w.synthesize(Spec(inputs=("RawText",), output="Protein"))
    assert result.verdict == Verdict.IMPOSSIBLE


def test_ill_typed_gap_when_inputs_missing():
    op = make_operad()
    w = Wright(op)
    # Embedding is producible in the operad, but not from a Picture input.
    result = w.synthesize(Spec(inputs=("Picture",), output="Embedding"))
    assert result.verdict == Verdict.IMPOSSIBLE  # no chain from Picture at all


def test_cheapest_wins_when_multiple():
    op = Operad("choices")
    op.add_op("cheap", ["A"], "B", cost={"ms": 1}, fn=lambda x: x)
    op.add_op("dear", ["A"], "B", cost={"ms": 99}, fn=lambda x: x)
    w = Wright(op)
    result = w.synthesize(Spec(inputs=("A",), output="B"))
    assert result.verdict == Verdict.BUILDABLE
    assert result.construction.wiring == "cheap(A)"


def test_compile_to_komposos_preserves_structure():
    op = make_operad()
    w = Wright(op)
    design = w.synthesize(Spec(inputs=("RawText",), output="Embedding")).construction
    graph = compile_to_komposos(design.composite, op)
    assert graph.root == "Embedding"
    assert {"RawText", "Tokens", "Embedding"} <= set(graph.objects)
    names = {m["name"] for m in graph.morphisms}
    assert names == {"tokenize", "embed"}
    # Lower-cost ops carry higher confidence.
    by_name = {m["name"]: m["confidence"] for m in graph.morphisms}
    assert by_name["tokenize"] > by_name["embed"]  # cost 2 < cost 8
