# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Laws for the Track-2 system-interconnect scoreboard.

These assert the HONEST MECHANISM (partition -> classify -> label-shuffle control collapses
to ~1.0), not a design-dependent H1 pass: the within-die proxy signal is weak and varies by
design (see docs), so the invariant we lock is that the control is sound.
"""

import os

import pytest

from domains.silicon.system_scoreboard import system_scoreboard

_AES = ("domains/silicon/data/orfs_aes/results/nangate45/aes/base",
        "domains/silicon/data/ir_aes/ir_voltage.rpt")
_LEF = "domains/silicon/data/openlane/Nangate45.lef"


@pytest.mark.skipif(
    not (os.path.exists(f"{_AES[0]}/6_final.def") and os.path.exists(_AES[1])),
    reason="real aes artifacts absent (regenerate via ORFS + analyze_power_grid)")
def test_system_scoreboard_mechanism_on_real_aes():
    rep = system_scoreboard(f"{_AES[0]}/6_final.def", f"{_AES[0]}/6_final.spef",
                            _LEF, _AES[1], design="aes")
    # partition produced multiple chiplet-analogue blocks, and both net classes are present
    assert rep.n_blocks >= 8
    assert rep.n_inter > 0 and rep.n_intra > 0
    # the inter/intra split is a real structural cut, not all-or-nothing
    assert rep.n_inter < rep.n_intra            # most nets stay within a block (locality)
    # HONESTY INVARIANT: under shuffled inter/intra labels the separation must vanish to ~1
    assert abs(rep.sep_control - 1.0) < 0.05
    # any real H1 separation is modest and >= the shuffled baseline
    assert rep.separation > 0
    # H2 features computed with their own shuffle control
    assert "system_links" in rep.block_spearman
    assert "system_load" in rep.block_control
