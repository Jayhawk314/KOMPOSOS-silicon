# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Track 3 Step A: three-view net-fidelity coherence on real chip artifacts.

Proves the (already-tested) H0/H1 obstruction engine is wired end-to-end to real silicon:
- a clean single flow is coherent (H0=1, H1=0) -- no manufactured obstruction;
- a CYCLIC inconsistency (pairwise-agree but no joint) yields H1=1, localized -- the EPE shape;
- an injected fault is localized to the offending net.
"""

import os

import pytest

from domains.silicon.fidelity_coherence import (
    fidelity_coherence, spef_view, stage_coherence, verilog_view, def_view)


def _mk(nets):
    """Each net gets a unique terminal set so cross-view identity is by terminals."""
    return {n: frozenset({(n, "A"), (n, "B")}) for n in nets}


def test_clean_flow_is_coherent():
    view = _mk(["A", "B", "C", "D"])
    rep = fidelity_coherence(view, dict(view), dict(view))
    assert rep.h0_dimension == 1 and rep.h1_dimension == 0
    assert rep.coherent
    assert rep.coherent_nets == 4


def test_cyclic_inconsistency_gives_localized_h1():
    # Each pair shares 3/4 (>=0.75) but the triple shares only 2/4 -> unfilled triangle.
    v = _mk(["A", "B", "C", "D"])
    d = _mk(["A", "B", "C", "E"])
    s = _mk(["A", "B", "D", "E"])
    rep = fidelity_coherence(v, d, s, agree_threshold=0.75)
    assert rep.h1_dimension == 1          # a real cyclic obstruction
    assert not rep.coherent
    assert rep.h1_support                 # localized to calibration edge(s)


def test_injected_fault_is_localized():
    v = _mk(["A", "B", "C"])
    d = _mk(["A", "B", "C"])
    s = dict(_mk(["A", "B", "C"]))
    s["C"] = frozenset({("C", "A"), ("BADINST", "QN")})    # corrupt C's terminals in spef
    rep = fidelity_coherence(v, d, s, agree_threshold=0.4)
    flagged = {n for nets in rep.disagreements.values() for n in nets}
    assert "C" in flagged                 # the offending net is surfaced


_BASE = "domains/silicon/data/orfs_gcd/results/base"


@pytest.mark.skipif(
    not os.path.exists(f"{_BASE}/6_final.v"),
    reason="orfs_gcd verilog/def/spef absent (self-mint via ORFS)")
def test_real_orfs_gcd_three_view_coherent():
    v = verilog_view(f"{_BASE}/6_final.v")
    d, _ = def_view(f"{_BASE}/6_final.def", f"{_BASE}/6_final.spef",
                    "domains/silicon/data/openlane/Nangate45.lef")
    s = spef_view(f"{_BASE}/6_final.spef")
    rep = fidelity_coherence(v, d, s)
    # the real self-minted flow is coherent: connected nerve, no cyclic obstruction
    assert rep.h0_dimension == 1 and rep.h1_dimension == 0
    # a large coherent core agrees exactly across verilog+def+spef
    assert rep.coherent_nets >= 400
    # the two physical views (def, spef) agree strongly after escaping normalization
    assert rep.pair_agreement["def~spef"] >= 0.85


@pytest.mark.skipif(
    not os.path.exists(f"{_BASE}/1_2_yosys.v"),
    reason="orfs_gcd synthesis netlist absent (self-mint via ORFS)")
def test_cross_stage_coherence_localizes_real_flow_changes():
    """Two REAL flow stages (synthesis vs final) of one design: logically equivalent (the
    flow's own LEC certifies it), structurally different. The engine localizes the divergence
    to the cells the flow actually inserted -- a what-changed check on real tool output."""
    rep = stage_coherence(f"{_BASE}/1_2_yosys.v", f"{_BASE}/6_final.v")
    # most nets pass through the whole flow with identical connectivity
    assert rep.preserved_fraction > 0.8
    # but there is a real, localized divergence (not "all clear")
    assert rep.divergent_nets > 0 and rep.sample_divergent
    # and it localizes to the cells the flow inserted: CTS clock buffers + opt buffers
    inserted = " ".join(rep.inserted_cells)
    assert any("BUF" in c or "CLKBUF" in c for c in rep.inserted_cells), inserted
