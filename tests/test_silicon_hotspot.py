# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Hotspot detector: predicts physical-stress tiles from the layout alone.

Pure-logic tests always run. The real-design test runs only when the gitignored ORFS
layout is present; it skips otherwise, mirroring the other real-data tests.
"""

import os
import pytest

from domains.silicon.hotspot import (
    HotspotTile, HotspotReport, predict_hotspots, EVIDENCE_TIER,
)


def test_report_ranks_by_demand_and_carries_receipt():
    tiles = [HotspotTile(0, 0, 0, 0, 1, 1, current_demand=1.0, density=5),
             HotspotTile(1, 1, 1, 1, 2, 2, current_demand=9.0, density=9)]
    tiles.sort(key=lambda t: t.current_demand, reverse=True)
    rep = HotspotReport("x", 20, 2, tiles)
    # highest demand first; every report carries the measured-proxy validation receipt.
    assert rep.tiles[0].current_demand == 9.0
    assert rep.evidence_tier == EVIDENCE_TIER
    assert "IR-drop" in rep.validation
    assert rep.to_dict()["hotspots"][0]["tile"] == [1, 1]


_AES = "domains/silicon/data/orfs_aes/results/nangate45/aes/base"


@pytest.mark.skipif(not os.path.exists(f"{_AES}/6_final.def"),
                    reason="real ORFS layout absent (gitignored)")
def test_predict_hotspots_on_real_aes():
    rep = predict_hotspots(f"{_AES}/6_final.def", f"{_AES}/6_final.spef",
                           "domains/silicon/data/openlane/Nangate45.lef", design="aes", top=8)
    assert rep.n_tiles > 100
    assert len(rep.tiles) == 8
    # ranked strictly by current demand, each hotspot names its worst net
    demands = [t.current_demand for t in rep.tiles]
    assert demands == sorted(demands, reverse=True)
    assert rep.tiles[0].top_nets and rep.tiles[0].density > 0
