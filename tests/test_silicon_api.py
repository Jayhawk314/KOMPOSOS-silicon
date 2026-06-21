# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""The single façade: analyze(def, spef, lef) -> a receipt-backed triage + seam report.

Runs on the committed sample fixture (no downloads), so it always exercises the entry point.
"""

from domains.silicon.api import SiliconReport, analyze
from domains.silicon.netlist_bridge import SAMPLE_DEF, SAMPLE_SPEF


def test_analyze_returns_triage_and_seam_on_sample():
    rep = analyze(SAMPLE_DEF, spef_path=SAMPLE_SPEF, top=5)
    assert isinstance(rep, SiliconReport)
    assert rep.n_signal_nets > 0 and rep.n_cells > 0
    # TRIAGE: ranked, non-empty, and ordered by fan-out (the validated predictor)
    assert rep.top_risky_nets
    fanouts = [r.fanout for r in rep.top_risky_nets]
    assert fanouts == sorted(fanouts, reverse=True)
    # SEAM: a real partition with a finite algebraic connectivity
    assert rep.seam_sizes[0] > 0 and rep.seam_sizes[1] > 0
    assert rep.seam_value >= 0.0
    # honest evidence tiers, never promoted past proxy here
    assert "structural_only" in rep.evidence["triage"]
    assert "measured_proxy" in rep.evidence["triage"]      # SPEF cap given
    assert rep.evidence["seam"] == "structural_only"


def test_analyze_without_spef_is_structural_only():
    rep = analyze(SAMPLE_DEF, top=5)
    assert not rep.has_spef
    assert "measured_proxy" not in rep.evidence["triage"]   # no SPEF -> no proxy tier
    assert all(r.cap is None for r in rep.top_risky_nets)


def test_report_renders_and_serializes():
    rep = analyze(SAMPLE_DEF, spef_path=SAMPLE_SPEF, top=3)
    text = rep.render()
    assert "TRIAGE" in text and "SEAM" in text
    assert rep.to_json().startswith("{")
