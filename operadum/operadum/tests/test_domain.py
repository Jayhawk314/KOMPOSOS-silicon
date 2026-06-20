# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Domain plugin tests: a first domain loaded in one call, synthesized, scored.
"""

import pytest

from operadum.domains.synthesis_design import SynthesisDesignDomain
from operadum.core.types import Spec
from operadum.wright.engine import Wright
from operadum.wright.schema import Verdict
from operadum.validation.domain_accuracy import measure_domain_accuracy


def test_domain_loads_in_one_call():
    op = SynthesisDesignDomain().build_operad()
    assert {c.name for c in op.colours()} >= {"Benzene", "Paracetamol", "Aniline"}
    assert {o.name for o in op.operations()} >= {"nitrate", "reduce", "hydroxylate"}
    assert op.monoid.name.startswith("AdditiveCost")


def test_synthesize_cheapest_route_to_target():
    op = SynthesisDesignDomain().build_operad()
    result = Wright(op, max_depth=8).optimize(Spec(inputs=("Benzene",), output="Paracetamol"))
    assert result.verdict == Verdict.BUILDABLE
    assert result.construction.cost == {"usd": 26}        # the cheap nitrate+reduce route
    assert "aminate" not in result.construction.wiring     # not the $20 shortcut
    # The route is executable: running it yields the target molecule.
    assert result.construction.artifact("Benzene") == "Paracetamol"


def test_cheaper_aniline_subroute_chosen():
    op = SynthesisDesignDomain().build_operad()
    result = Wright(op, max_depth=8).optimize(Spec(inputs=("Benzene",), output="Aniline"))
    assert result.construction.cost == {"usd": 10}         # nitrate+reduce beats aminate $20
    assert result.construction.wiring == "reduce(nitrate(Benzene))"


def test_unreachable_target_is_not_buildable():
    op = SynthesisDesignDomain().build_operad()
    result = Wright(op, max_depth=8).optimize(Spec(inputs=("Toluene",), output="Paracetamol"))
    assert result.verdict != Verdict.BUILDABLE


def test_domain_accuracy_is_perfect():
    score = measure_domain_accuracy(SynthesisDesignDomain())
    assert score.buildable_accuracy == 1.0
    assert score.optimum_recall == 1.0
    assert score.roundtrip_agree == 1.0
