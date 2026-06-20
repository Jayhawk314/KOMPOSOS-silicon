# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Second-domain tests: domain-agnosticism + a non-additive (peak) resource algebra.

The same substrate that designed a synthesis route now designs a data pipeline
ranked by peak memory -- proving the math does not know which domain it is in.
"""

import pytest

from operadum.domains.compute_pipeline import ComputePipelineDomain
from operadum.core.types import Spec
from operadum.core.enrichment import MAX_CAPACITY
from operadum.wright.engine import Wright
from operadum.wright.schema import Verdict
from operadum.validation.domain_accuracy import measure_domain_accuracy


def test_uses_max_capacity_algebra():
    op = ComputePipelineDomain().build_operad()
    assert op.monoid is MAX_CAPACITY


def test_minimizes_peak_not_total():
    op = ComputePipelineDomain().build_operad()
    result = Wright(op, max_depth=8).optimize(Spec(inputs=("RawLog",), output="Report"))
    assert result.verdict == Verdict.BUILDABLE
    # Peak of the chosen route, not the sum of stages.
    assert result.construction.cost == {"mem": 200}     # max(50,120,200,80)
    assert "index_slow" in result.construction.wiring   # avoided the 400MB index_fast


def test_picks_lean_indexer():
    op = ComputePipelineDomain().build_operad()
    result = Wright(op, max_depth=8).optimize(Spec(inputs=("RawLog",), output="Indexed"))
    assert result.construction.cost == {"mem": 120}     # index_slow, not index_fast (400)


def test_domain_accuracy_matches_expectations():
    """Buildable + optimum perfect; round-trips correctly reported HOLLOW (the
    peak algebra makes the cost->confidence compile lossy -- and the engine
    knows it)."""
    score = measure_domain_accuracy(ComputePipelineDomain())
    assert score.buildable_accuracy == 1.0
    assert score.optimum_recall == 1.0
    assert score.roundtrip_accuracy == 1.0          # all HOLLOW, as expected
    assert score.roundtrip_agree == 0.0             # honestly, none are AGREE
