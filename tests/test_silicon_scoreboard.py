# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Scoreboard laws: the stats are correct and the triage signal beats the control."""

import os

import pytest

from domains.silicon.scoreboard import (
    spearman, precision_at_k, score_layout, PASS_RHO, CONTROL_MAX,
)
from domains.silicon.netlist_bridge import SAMPLE_DEF, SAMPLE_SPEF


# --- stats helpers (deterministic) ----------------------------------------

def test_spearman_monotonic_extremes():
    assert spearman([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4, 5], [50, 40, 30, 20, 10]) == pytest.approx(-1.0)

def test_spearman_handles_ties_and_shortlists():
    assert spearman([1, 1, 2, 2], [1, 1, 2, 2]) == pytest.approx(1.0)
    assert spearman([1, 2], [2, 1]) == 0.0          # too few points -> 0

def test_precision_at_k_overlap():
    pred = [9, 8, 7, 1, 2]      # top-2 indices: 0,1
    target = [1, 9, 8, 2, 3]    # top-2 indices: 1,2
    assert precision_at_k(pred, target, 2) == 0.5   # only index 1 shared


# --- the falsifiable headline: signal beats the shuffle control ------------

def test_sample_passes_and_control_collapses():
    rep = score_layout(SAMPLE_DEF, SAMPLE_SPEF, design="sample")
    name, rho = rep.best
    assert rep.n_nets >= 5
    assert rho >= PASS_RHO                            # a real predictor exists
    assert abs(rep.control_rho) < CONTROL_MAX         # shuffle kills it
    assert rep.passed


def test_predictors_beat_their_own_shuffle_control():
    """Falsifiability: the best predictor must out-correlate the shuffled target."""
    rep = score_layout(SAMPLE_DEF, SAMPLE_SPEF)
    assert rep.best[1] > abs(rep.control_rho)


# --- real designs if downloaded (skips otherwise) --------------------------

_GCD_DEF = os.path.join(os.path.dirname(SAMPLE_DEF), "..", "data", "openlane", "gcd.def")
_GCD_SPEF = os.path.join(os.path.dirname(SAMPLE_DEF), "..", "data", "openlane", "gcd.spefok")


@pytest.mark.skipif(not os.path.exists(_GCD_DEF), reason="real GCD not downloaded")
def test_real_gcd_triage_is_screening_grade():
    rep = score_layout(_GCD_DEF, _GCD_SPEF, design="gcd")
    assert rep.n_nets > 100
    assert rep.best[1] >= PASS_RHO                    # structural signal predicts cost
    assert abs(rep.control_rho) < CONTROL_MAX
