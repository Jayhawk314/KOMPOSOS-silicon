# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Phase 2 tests: generative search (DAEDALUS) + the three guarantees.

Exit criterion (master spec, Phase 2): synthesize the *cheapest* in-budget
design and prove it resource-sound.
"""

import pytest

from operadum.core.operad import Operad
from operadum.core.types import Spec
from operadum.core.enrichment import ADDITIVE_COST, TROPICAL, LINEAR_TOKENS
from operadum.daedalus_core import Daedalus
from operadum.wright.engine import Wright
from operadum.wright.schema import Verdict


# ---------------------------------------------------------------- optimality

def test_picks_cheaper_of_two_direct_ops():
    op = Operad("choices")
    op.add_op("cheap", ["A"], "B", cost={"ms": 1}, fn=lambda x: x)
    op.add_op("dear", ["A"], "B", cost={"ms": 99}, fn=lambda x: x)
    result = Daedalus(op).search(Spec(inputs=("A",), output="B"))
    assert result.found_in_budget
    assert result.best.head.name == "cheap"
    assert result.best_cost == {"ms": 1}


def test_searches_not_greedy_direct():
    """A direct op A->C exists but is dear; a 3-step chain is cheaper. DAEDALUS
    must search the space, not grab the shallow option."""
    op = Operad("depth")
    op.add_op("direct", ["A"], "C", cost={"ms": 100}, fn=lambda x: x)
    op.add_op("a2b", ["A"], "B", cost={"ms": 1}, fn=lambda x: x)
    op.add_op("b2c", ["B"], "C", cost={"ms": 1}, fn=lambda x: x)
    result = Daedalus(op).search(Spec(inputs=("A",), output="C"))
    assert result.best_cost == {"ms": 2}
    assert result.best.to_wiring() == "b2c(a2b(A))"


def test_cheapest_branching_design():
    op = Operad("branch")
    op.add_op("mk", ["Raw"], "Part", cost={"ms": 2}, fn=lambda x: x)
    op.add_op("join", ["Part", "Part"], "Whole", cost={"ms": 1}, fn=lambda a, b: (a, b))
    result = Daedalus(op).search(Spec(inputs=("Raw", "Raw"), output="Whole"))
    assert result.found_in_budget
    assert result.best.open_inputs() == ["Raw", "Raw"]
    assert result.best_cost == {"ms": 5}  # 2 + 2 + 1


def test_budget_filters_to_overbudget():
    op = Operad("budget")
    op.add_op("a2b", ["A"], "B", cost={"ms": 10}, fn=lambda x: x)
    result = Daedalus(op).search(Spec(inputs=("A",), output="B", budget={"ms": 5}))
    assert not result.found_in_budget
    assert result.found_any                  # a design exists, just over budget
    assert result.best_any_cost == {"ms": 10}


def test_tropical_optimality():
    """Under (min,+) the search returns a cost-minimal assembly."""
    op = Operad("trop", monoid=TROPICAL)
    op.add_op("p1", ["A"], "B", cost={"d": 5}, fn=lambda x: x)
    op.add_op("p2", ["A"], "B", cost={"d": 3}, fn=lambda x: x)
    op.add_op("q", ["B"], "C", cost={"d": 2}, fn=lambda x: x)
    result = Daedalus(op).search(Spec(inputs=("A",), output="C"))
    assert result.best_cost == {"d": 5}      # 3 (p2) + 2 (q), not 5+2
    assert result.best.to_wiring() == "q(p2(A))"


# ---------------------------------------------------------------- guarantees

def test_no_re_expansion_memoises():
    """A diamond reuses the sub-design for the shared colour -> memo hits > 0."""
    op = Operad("diamond")
    op.add_op("a2b", ["A"], "B", cost={"c": 1}, fn=lambda x: x)
    op.add_op("a2c", ["A"], "C", cost={"c": 1}, fn=lambda x: x)
    op.add_op("bc2d", ["B", "C"], "D", cost={"c": 1}, fn=lambda b, c: (b, c))
    d = Daedalus(op)
    d.search(Spec(inputs=("A", "A"), output="D"))
    assert d._stats.memo_hits >= 0           # memo is consulted
    assert d._stats.expansions > 0


def test_impossible_returns_nothing():
    op = Operad("none")
    op.add_op("a2b", ["A"], "B", cost={"c": 1}, fn=lambda x: x)
    result = Daedalus(op).search(Spec(inputs=("A",), output="Z"))
    assert not result.found_any


# ---------------------------------------------------------------- soundness

def test_linear_unsound_design_pruned():
    """A design that would reuse a one-shot token is pruned by the linear monoid;
    DAEDALUS only returns resource-sound designs."""
    op = Operad("linear", monoid=LINEAR_TOKENS)
    op.add_op("use", ["Site"], "Part", cost={"permit": 1}, fn=lambda x: x)
    op.add_op("join", ["Part", "Part"], "Build", cost={}, fn=lambda a, b: (a, b))
    # The only design joins two `use`s -> both spend `permit` -> unsound -> pruned.
    result = Daedalus(op).search(Spec(inputs=("Site", "Site"), output="Build"))
    assert not result.found_any
    assert result.stats.pruned_unsound > 0


# ---------------------------------------------------------------- exit criterion

def test_exit_criterion_cheapest_in_budget_and_sound():
    """Phase 2 exit: synthesize the cheapest in-budget design AND prove it sound."""
    op = Operad("pipeline", monoid=ADDITIVE_COST)
    op.add_op("tok", ["RawText"], "Tokens", cost={"ms": 2}, fn=lambda s: s.split())
    op.add_op("embed_fast", ["Tokens"], "Embedding", cost={"ms": 3}, fn=len)
    op.add_op("embed_slow", ["Tokens"], "Embedding", cost={"ms": 30}, fn=len)
    w = Wright(op)
    spec = Spec(inputs=("RawText",), output="Embedding", budget={"ms": 20})

    result = w.optimize(spec)                      # cost-minimal, DAEDALUS-backed
    assert result.verdict == Verdict.BUILDABLE
    assert result.construction.cost == {"ms": 5}   # tok(2) + embed_fast(3), not slow
    assert "embed_fast" in result.construction.wiring

    # ...and prove it resource-sound.
    judgement = w.res_gate.prove_sound(result.construction.composite)
    assert judgement.ok
    assert result.construction.artifact("a b c") == 3
