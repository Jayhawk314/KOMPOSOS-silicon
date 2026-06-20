# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Phase 0 tests: the operadic substrate must be right.

Exit criterion (master spec, Phase 0): can build, persist, and realize() a
multi-step pipeline with correct cost. Plus the operad laws:
associativity of o_i, equivariance, units, type-rejection, resource
conservation -- and the non-cartesian (linear) discipline.
"""

import pytest

from operadum.core.operad import Operad
from operadum.core.enrichment import (
    ADDITIVE_COST, MAX_CAPACITY, LINEAR_TOKENS, ResourceError,
)


# ---------------------------------------------------------------- fixtures

def make_pipeline_operad(db_path=":memory:"):
    op = Operad("pipeline", db_path=db_path, monoid=ADDITIVE_COST)
    op.add_colour("RawText")
    op.add_colour("Tokens")
    op.add_colour("Embedding")
    op.add_op("tokenize", ["RawText"], "Tokens", cost={"ms": 2}, fn=lambda s: s.split())
    op.add_op("embed", ["Tokens"], "Embedding", cost={"ms": 8}, fn=lambda t: len(t))
    op.add_op("merge", ["Embedding", "Embedding"], "Embedding", cost={"ms": 1},
              fn=lambda a, b: a + b)
    return op


# ---------------------------------------------------------------- structure

def test_add_and_index():
    op = make_pipeline_operad()
    assert {c.name for c in op.colours()} == {"RawText", "Tokens", "Embedding"}
    assert len(op.operations()) == 3
    assert [o.name for o in op.operations_producing("Embedding")] == ["embed", "merge"]


def test_interface_and_arity():
    op = make_pipeline_operad()
    embed = op.get_op("embed")
    assert embed.arity == 1
    assert str(embed.interface) == "(Tokens) -> Embedding"
    merge = op.get_op("merge")
    assert merge.arity == 2


# ---------------------------------------------------------------- composition

def test_single_composition_interface_and_cost():
    op = make_pipeline_operad()
    pipeline = op.compose("embed", 0, "tokenize")   # RawText -> Embedding
    assert pipeline.open_inputs() == ["RawText"]
    assert pipeline.output == "Embedding"
    assert pipeline.cost(op.monoid) == {"ms": 10}      # 2 + 8 conserved


def test_type_rejection_at_build_time():
    op = make_pipeline_operad()
    # embed expects Tokens; tokenize outputs Tokens (ok). Plug RawText producer
    # into embed should fail -- there is no op producing RawText, but try a
    # direct colour mismatch: plug 'embed' (outputs Embedding) into tokenize.
    with pytest.raises(TypeError):
        op.compose("tokenize", 0, "embed")  # tokenize input is RawText != Embedding


def test_out_of_range_input_raises():
    op = make_pipeline_operad()
    with pytest.raises(IndexError):
        op.compose("tokenize", 5, "embed")


def test_associativity_of_partial_composition():
    """o_i is associative where inputs are disjoint: merge(embed(tok), embed(tok))
    built in two plug orders yields the same interface and the same cost."""
    op = make_pipeline_operad()
    emb_pipe = op.compose("embed", 0, "tokenize")     # RawText -> Embedding

    # Order A: fill slot 0 (open inputs become [RawText, Embedding]), then slot 1
    a = op.compose("merge", 0, emb_pipe)
    a = op.compose(a, 1, emb_pipe)
    # Order B: fill slot 1 (open inputs become [Embedding, RawText]), then slot 0
    b = op.compose("merge", 1, emb_pipe)
    b = op.compose(b, 0, emb_pipe)

    assert a.open_inputs() == b.open_inputs() == ["RawText", "RawText"]
    assert a.cost(op.monoid) == b.cost(op.monoid) == {"ms": 21}  # 10+10+1


def test_unit_law():
    """The identity operation is a two-sided unit for o_i."""
    op = make_pipeline_operad()
    idT = op.identity("Tokens")
    embed = op.get_op("embed")
    # embed o_0 id_Tokens : (Tokens) -> Embedding, same interface, same cost
    comp = op.compose(embed, 0, idT)
    assert comp.open_inputs() == ["Tokens"]
    assert comp.output == "Embedding"
    assert comp.cost(op.monoid) == {"ms": 8}  # identity adds nothing


# ---------------------------------------------------------------- execution

def test_realize_multi_step_pipeline():
    """Phase 0 exit criterion: realize() a multi-step pipeline; cost correct."""
    op = make_pipeline_operad()
    pipeline = op.compose("embed", 0, "tokenize")
    run = op.realize(pipeline)
    assert run("a b c d") == 4                 # embed(tokenize("a b c d")) = len([...])
    assert pipeline.cost(op.monoid) == {"ms": 10}


def test_realize_branching_design():
    op = make_pipeline_operad()
    emb = op.compose("embed", 0, "tokenize")        # RawText -> Embedding
    design = op.compose("merge", 0, emb)
    design = op.compose(design, 1, emb)             # merge(emb(.), emb(.))
    run = op.realize(design)
    assert run("a b", "c d e") == 5                 # 2 + 3
    assert design.cost(op.monoid) == {"ms": 21}


def test_realize_requires_callables():
    op = Operad("nofn")
    op.add_op("f", ["A"], "B")  # no fn
    with pytest.raises(ValueError):
        op.realize(op.get_op("f"))


# ---------------------------------------------------------------- resources

def test_max_capacity_takes_peak_not_sum():
    op = Operad("cap", monoid=MAX_CAPACITY)
    op.add_op("a", ["X"], "Y", cost={"mem": 4})
    op.add_op("b", ["Y"], "Z", cost={"mem": 9})
    comp = op.compose("b", 0, "a")
    assert comp.cost(op.monoid) == {"mem": 9}  # peak, not 13


def test_linear_tokens_forbid_reuse():
    """The load-bearing non-cartesian law: a one-shot token cannot be spent twice."""
    op = Operad("linear", monoid=LINEAR_TOKENS)
    op.add_op("use_permit", ["Site"], "Built", cost={"permit_42": 1}, fn=lambda s: s)
    op.add_op("combine2", ["Built", "Built"], "Project", cost={},
              fn=lambda a, b: (a, b))
    use = op.get_op("use_permit").as_composite()
    design = op.compose("combine2", 0, use)
    design = op.compose(design, 1, use)  # same permit on both branches
    with pytest.raises(ResourceError):
        design.cost(op.monoid)


# ---------------------------------------------------------------- persistence

def test_persistence_round_trip(tmp_path):
    db = str(tmp_path / "comp.db")
    op = make_pipeline_operad(db_path=db)
    op.compose("embed", 0, "tokenize")  # persists colours, ops, composite

    reopened = Operad("pipeline", db_path=db)
    names = {o.name for o in reopened.operations()}
    assert {"tokenize", "embed", "merge"} <= names
    assert {c.name for c in reopened.colours()} == {"RawText", "Tokens", "Embedding"}


def test_colour_removal_cascades():
    op = make_pipeline_operad()
    op.remove_colour("Tokens")
    remaining = {o.name for o in op.operations()}
    # tokenize (outputs Tokens) and embed (inputs Tokens) both gone; merge stays.
    assert remaining == {"merge"}


# ---------------------------------------------------------------- hooks

def test_hooks_fire_on_structural_events():
    op = Operad("hooked")
    seen = []
    op.hooks.on("operation_added", lambda operation: seen.append(operation.name))
    op.hooks.on("composed", lambda **kw: seen.append("composed"))
    op.add_op("f", ["A"], "B", fn=lambda x: x)
    op.add_op("g", ["B"], "C", fn=lambda x: x)
    op.compose("g", 0, "f")
    assert seen == ["f", "g", "composed"]
