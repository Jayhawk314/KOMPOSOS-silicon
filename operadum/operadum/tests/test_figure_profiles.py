# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

import pytest

from operadum import (
    Operad,
    Spec,
    Wright,
    GENERAL_FIGURES,
    SAFETY_FIRST,
    FASTEST_RECOVERY,
)


def test_general_figures_compose_per_metric_policy():
    op = Operad("figures", monoid=GENERAL_FIGURES)
    op.add_op(
        "prep",
        ["Raw"],
        "Mid",
        cost={
            "confidence": 0.9,
            "safety_risk": 0.1,
            "evidence_strength": 0.8,
            "memory_mb": 4,
            "schedule_delay": 2,
        },
    )
    op.add_op(
        "finish",
        ["Mid"],
        "Out",
        cost={
            "confidence": 0.8,
            "safety_risk": 0.2,
            "evidence_strength": 0.6,
            "memory_mb": 10,
            "schedule_delay": 3,
        },
    )

    design = op.compose("finish", 0, "prep")
    figures = design.cost(op.monoid)

    assert figures["confidence"] == pytest.approx(0.72)       # product
    assert figures["safety_risk"] == pytest.approx(0.28)      # prob_any
    assert figures["evidence_strength"] == pytest.approx(0.6) # weakest link
    assert figures["memory_mb"] == 10                         # peak
    assert figures["schedule_delay"] == 5                     # sum


def _release_operad(monoid):
    op = Operad("release", monoid=monoid)
    op.add_op(
        "quick_release",
        [],
        "Released",
        cost={"schedule_delay": 1, "safety_risk": 0.7, "compliance_debt": 1},
    )
    op.add_op(
        "safe_release",
        [],
        "Released",
        cost={"schedule_delay": 8, "safety_risk": 0.01, "compliance_debt": 0},
    )
    return op


def test_global_profiles_can_choose_different_designs_over_same_operations():
    safety = Wright(_release_operad(SAFETY_FIRST)).optimize(Spec((), "Released"))
    fastest = Wright(_release_operad(FASTEST_RECOVERY)).optimize(Spec((), "Released"))

    assert safety.construction.wiring == "safe_release"
    assert fastest.construction.wiring == "quick_release"


def test_requirements_are_lower_bounds_for_high_is_better_figures():
    op = Operad("confidence", monoid=GENERAL_FIGURES)
    op.add_op("weak_fast", [], "Decision", cost={"confidence": 0.6, "schedule_delay": 1})
    op.add_op("strong_slow", [], "Decision", cost={"confidence": 0.9, "schedule_delay": 4})

    unconstrained = Wright(op).optimize(Spec((), "Decision"))
    required = Wright(op).optimize(
        Spec((), "Decision", requirements={"confidence": 0.8})
    )

    assert unconstrained.construction.wiring == "weak_fast"
    assert required.construction.wiring == "strong_slow"
