# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Scoreboard laws: the stats are correct and the triage signal beats the control."""

import os

import pytest

from domains.silicon.scoreboard import (
    spearman, precision_at_k, score_layout, score_timing, collect_features,
    PREDICTORS, PASS_RHO, CONTROL_MAX,
)
from domains.silicon.netlist_bridge import NetlistBridge, SAMPLE_DEF, SAMPLE_SPEF

_STA_RPT = os.path.join(os.path.dirname(SAMPLE_DEF), "tiny_core.sta.rpt")


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


def test_total_wirelength_is_sum_of_star_edges_and_scored():
    # total_wirelength = SUM of a net's driver->sink edge lengths (a total-wire proxy for
    # interconnect delay), so it is always >= the single longest edge (`wirelength`). It is a
    # better delay predictor than max-edge on both real measured designs (prec@10 0.6/0.8 -> 0.9).
    bridge = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF)
    bridge.load()
    feats = collect_features(bridge)
    assert feats
    assert all(f.total_wirelength >= f.wirelength for f in feats)   # sum >= max (non-negative)
    assert any(f.total_wirelength > f.wirelength for f in feats)    # multi-sink net: strictly >
    assert "total_wirelength" in PREDICTORS


# --- the falsifiable headline: signal beats the shuffle control ------------

def test_sample_fixture_metrics_are_deterministic_but_cannot_be_evidence():
    rep = score_layout(SAMPLE_DEF, SAMPLE_SPEF, design="sample")
    _, rho = rep.best
    assert rep.n_nets >= 5
    assert rho >= PASS_RHO                            # a real predictor exists
    assert rep.passed is False
    assert rep.source_kind == "fixture"
    assert "NON-EVIDENCE" in rep.render()
    assert score_layout(SAMPLE_DEF, SAMPLE_SPEF).control_rho == rep.control_rho


def test_predictors_beat_their_own_shuffle_control():
    """Falsifiability: the best predictor must out-correlate the shuffled target."""
    rep = score_layout(SAMPLE_DEF, SAMPLE_SPEF)
    assert rep.best[1] > abs(rep.control_rho)


def test_timing_score_fixture_is_computed_but_cannot_pass():
    rep = score_timing(SAMPLE_DEF, _STA_RPT, spef_path=SAMPLE_SPEF, design="fixture")
    assert rep.target == "sta_negative_slack"
    assert rep.n_positive >= 1
    assert rep.source_kind == "fixture"
    assert rep.evidence_eligible is False
    assert rep.passed is False
    assert rep.spearman
    assert "NON-EVIDENCE" in rep.render()


def test_timing_score_tool_source_is_hashed(tmp_path):
    text = open(_STA_RPT, encoding="utf-8").read().replace(
        "KOMPOSOS-V silicon STA fixture", "OpenSTA generated timing report")
    report_path = tmp_path / "tool_sta.rpt"
    report_path.write_text(text, encoding="utf-8")
    context_paths = {}
    for name in ("netlist", "liberty", "constraints"):
        context_path = tmp_path / f"{name}.txt"
        context_path.write_text(name, encoding="utf-8")
        context_paths[name] = str(context_path)
    rep = score_timing(
        SAMPLE_DEF, str(report_path), spef_path=SAMPLE_SPEF,
        sta_source_kind="tool", sta_context_paths=context_paths)
    assert rep.evidence_eligible is True
    assert rep.source_kind == "tool"
    assert len(rep.source_sha256) == 64
    assert rep.to_dict()["target"] == "sta_negative_slack"


# --- real designs if downloaded (skips otherwise) --------------------------

_GCD_DEF = os.path.join(os.path.dirname(SAMPLE_DEF), "..", "data", "openlane", "gcd.def")
_GCD_SPEF = os.path.join(os.path.dirname(SAMPLE_DEF), "..", "data", "openlane", "gcd.spefok")


@pytest.mark.skipif(not os.path.exists(_GCD_DEF), reason="real GCD not downloaded")
def test_real_gcd_triage_is_screening_grade():
    rep = score_layout(_GCD_DEF, _GCD_SPEF, design="gcd")
    assert rep.n_nets > 100
    assert rep.best[1] >= PASS_RHO                    # structural signal predicts cost
    assert abs(rep.control_rho) < CONTROL_MAX
