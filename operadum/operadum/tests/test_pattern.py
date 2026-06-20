# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Phase 3 tests: PatternMiner (DAEDALUS Level 4 / System-3 analog).

Exit criterion (master spec, Phase 3): reusable patterns mined and reapplied.
"""

import pytest

from operadum.core.operad import Operad
from operadum.core.types import Spec
from operadum.wright.engine import Wright
from operadum.wright.schema import Verdict
from operadum.gate.pattern_miner import PatternMiner


def build_operad():
    op = Operad("patterns")
    op.add_op("tok", ["RawText"], "Tokens", cost={"ms": 2}, fn=lambda s: s.split())
    op.add_op("embed", ["Tokens"], "Embedding", cost={"ms": 8}, fn=len)
    op.add_op("classify", ["Embedding"], "Label", cost={"ms": 3}, fn=lambda e: e > 2)
    op.add_op("cluster", ["Embedding"], "Cluster", cost={"ms": 4}, fn=lambda e: e)
    return op


def test_mines_recurring_subdesign():
    op = build_operad()
    w = Wright(op)
    miner = PatternMiner(op, min_support=2, min_size=2)
    # Two different specs both need embed(tok(RawText)) underneath.
    for output in ("Label", "Cluster"):
        miner.record_result(w.synthesize(Spec(inputs=("RawText",), output=output)))
    patterns = miner.mine()
    wirings = [p.wiring for p in patterns]
    assert "embed(tok(RawText))" in wirings
    embed_pat = next(p for p in patterns if p.wiring == "embed(tok(RawText))")
    assert embed_pat.support == 2
    assert embed_pat.interface_inputs == ("RawText",)
    assert embed_pat.output == "Embedding"


def test_lift_makes_reusable_component_used_at_tier0():
    op = build_operad()
    w = Wright(op)
    miner = PatternMiner(op, min_support=2, min_size=2)
    for output in ("Label", "Cluster"):
        miner.record_result(w.synthesize(Spec(inputs=("RawText",), output=output)))

    pattern = next(p for p in miner.mine() if p.wiring == "embed(tok(RawText))")
    lifted = miner.lift(pattern, name="text_to_embedding")

    # The lifted op is a first-class component with the pattern's interface/cost.
    assert lifted.inputs == ["RawText"]
    assert lifted.output == "Embedding"
    assert lifted.cost == {"ms": 10}            # 2 + 8 conserved

    # Now RawText -> Embedding is a Tier-0 direct match.
    result = w.synthesize(Spec(inputs=("RawText",), output="Embedding"))
    assert result.verdict == Verdict.BUILDABLE
    assert result.tier == 0
    assert result.construction.wiring == "text_to_embedding(RawText)"

    # ...and the reusable component actually runs the original pattern.
    assert result.construction.artifact("a b c") == 3


def test_no_pattern_below_support():
    op = build_operad()
    w = Wright(op)
    miner = PatternMiner(op, min_support=2)
    miner.record_result(w.synthesize(Spec(inputs=("RawText",), output="Label")))
    assert miner.mine() == []                   # only one episode -> no support
