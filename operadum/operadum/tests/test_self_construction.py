# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Phase 4 tests: self-construction & learning.

Exit criterion (master spec, Phase 4): the system proposes new reusable
components/patterns from its own build history.
"""

import pytest

from operadum.core.operad import Operad
from operadum.core.types import Spec
from operadum.core.plugin_generator import PluginGenerator
from operadum.wright.engine import Wright
from operadum.wright.schema import Verdict
from operadum.gate.pattern_miner import PatternMiner
from operadum.gate.self_observer import SelfObserver


def history_operad():
    op = Operad("history")
    op.add_op("tok", ["RawText"], "Tokens", cost={"ms": 2}, fn=lambda s: s.split())
    op.add_op("embed", ["Tokens"], "Embedding", cost={"ms": 8}, fn=len)
    op.add_op("classify", ["Embedding"], "Label", cost={"ms": 3}, fn=lambda e: e > 2)
    op.add_op("cluster", ["Embedding"], "Cluster", cost={"ms": 4}, fn=lambda e: e)
    return op


# ---------------------------------------------------------------- learning

def test_records_outcomes_and_learns_realizability():
    op = history_operad()
    w = Wright(op)
    miner = PatternMiner(op)
    miner.record_result(w.synthesize(Spec(inputs=("RawText",), output="Label")))
    miner.record_result(w.synthesize(Spec(inputs=("RawText",), output="Protein")))  # impossible
    assert miner.realizability_rate() == 0.5
    assert miner.realizability_rate(output="Label") == 1.0
    assert miner.realizability_rate(output="Protein") == 0.0


# ---------------------------------------------------------------- self-extension

def test_auto_lift_proposes_and_promotes_from_history():
    op = history_operad()
    w = Wright(op)
    miner = PatternMiner(op, min_support=2, min_size=2)
    for output in ("Label", "Cluster"):
        miner.record_result(w.synthesize(Spec(inputs=("RawText",), output=output)))

    proposed = miner.propose()
    assert any(p.wiring == "embed(tok(RawText))" for p in proposed)

    lifted = miner.auto_lift()
    assert lifted, "auto_lift should promote at least one learned component"
    # The promoted component makes RawText -> Embedding a Tier-0 direct match.
    result = w.synthesize(Spec(inputs=("RawText",), output="Embedding"))
    assert result.verdict == Verdict.BUILDABLE
    assert result.tier == 0
    assert result.construction.artifact("a b c") == 3
    # Re-proposing does not re-lift the same pattern.
    assert all(p.wiring != "embed(tok(RawText))" for p in miner.propose())


# ---------------------------------------------------------------- plugin generation

def test_materialize_packages_operad_as_plugin():
    op = history_operad()
    gen = PluginGenerator()
    plugin = gen.materialize(op, name="text-domain")
    assert plugin.name == "text-domain"
    # The generated plugin rebuilds an equivalent operad (callables preserved).
    rebuilt = plugin.build_operad()
    assert {o.name for o in rebuilt.operations()} == {o.name for o in op.operations()}
    result = Wright(rebuilt).synthesize(Spec(inputs=("RawText",), output="Embedding"))
    assert result.verdict == Verdict.BUILDABLE
    assert result.construction.artifact("a b c") == 3


def test_generate_source_is_importable_python():
    op = history_operad()
    src = PluginGenerator().generate_source(op, class_name="TextDomain",
                                            domain_name="text")
    assert "class TextDomain(DomainPlugin)" in src
    assert "ADDITIVE_COST" in src
    namespace: dict = {}
    exec(src, namespace)                       # the emitted source runs
    plugin = namespace["TextDomain"]()
    assert "embed" in {o.name for o in plugin.operations()}


# ---------------------------------------------------------------- self-observation

def test_self_observer_flags_redundant_and_sources():
    op = Operad("obs")
    op.add_op("cheap", ["A"], "B", cost={"ms": 1}, fn=lambda x: x)
    op.add_op("dear", ["A"], "B", cost={"ms": 9}, fn=lambda x: x)   # dominated -> redundant
    op.add_op("use", ["B"], "C", cost={"ms": 1}, fn=lambda x: x)
    report = SelfObserver(op).observe()
    assert "A" in report.source_colours          # A has no producer
    assert "C" in report.sink_colours            # C has no consumer
    names = {dominated for dominated, _by, _r in report.redundant_ops}
    assert "dear" in names                       # dear is dominated by cheap
    assert any("dear" in p for p in report.proposals)
