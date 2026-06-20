# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Tile laws: the gates->tiles left Kan aggregation conserves mass and scores honestly."""

import json
import os

import pytest

from domains.silicon.netlist_bridge import NetlistBridge, SAMPLE_DEF, SAMPLE_SPEF
from domains.silicon.tiles import build_tile_crosswalk, score_tiles, TILE_PREDICTORS
from domains.silicon import agent_tools


def _sample_bridge():
    b = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF)
    b.load()
    return b


# --- the additive left-Kan conservation laws ------------------------------

def test_tiles_conserve_gate_count_and_contributors():
    b = _sample_bridge()
    placed = [c for c in b.components.values() if c.x is not None and c.y is not None]
    cw = build_tile_crosswalk(b, nx=4, ny=4)
    assert sum(t.gate_count for t in cw.tiles) == pytest.approx(len(placed))
    assert sum(t.contributors for t in cw.tiles) == len(placed)
    assert cw.skipped_unplaced == []        # sample is fully placed


def test_tiles_conserve_fanout_mass():
    """Sum of per-tile fanout equals the gate-sourced edge count (colimit is additive)."""
    b = _sample_bridge()
    cw = build_tile_crosswalk(b, nx=4, ny=4)
    expected = sum(1 for m in b.category.morphisms() if m.source in b.components)
    assert sum(t.fanout for t in cw.tiles) == pytest.approx(expected)


def test_each_tile_index_is_within_grid():
    b = _sample_bridge()
    cw = build_tile_crosswalk(b, nx=4, ny=4)
    for t in cw.tiles:
        assert 0 <= t.x_index < 4 and 0 <= t.y_index < 4
        assert t.confidence > 0


def test_invalid_grid_raises():
    b = _sample_bridge()
    with pytest.raises(ValueError):
        build_tile_crosswalk(b, nx=0, ny=4)


def test_unplaced_gates_are_skipped(tmp_path):
    deftext = """
    UNITS DISTANCE MICRONS 1000 ;
    COMPONENTS 3 ;
    - i0 INV_X1 + PLACED ( 1000 1000 ) N ;
    - i1 INV_X1 + PLACED ( 9000 9000 ) N ;
    - i2 INV_X1 + UNPLACED ;
    END COMPONENTS
    NETS 2 ;
    - n0 ( i0 ZN ) ( i1 A ) ;
    - n1 ( i1 ZN ) ( i2 A ) ;
    END NETS
    """
    p = tmp_path / "u.def"
    p.write_text(deftext, encoding="utf-8")
    b = NetlistBridge(str(p)); b.load()
    cw = build_tile_crosswalk(b, nx=4, ny=4)
    assert "i2" in cw.skipped_unplaced
    assert sum(t.gate_count for t in cw.tiles) == 2     # only placed gates aggregated


# --- scoring + control ----------------------------------------------------

def test_score_tiles_shape_and_determinism():
    b = _sample_bridge()
    cw = build_tile_crosswalk(b, nx=4, ny=4)
    s1 = score_tiles(cw, seed=0)
    s2 = score_tiles(cw, seed=0)
    assert s1.control_rho == s2.control_rho       # deterministic control
    assert set(s1.spearman) <= set(TILE_PREDICTORS) or s1.spearman == {}


@pytest.mark.skipif(
    not os.path.exists(os.path.join(os.path.dirname(SAMPLE_DEF), "..",
                                    "data", "openlane", "gcd.def")),
    reason="real gcd not downloaded")
def test_real_gcd_tile_telemetry_predicts_cap():
    g = os.path.join(os.path.dirname(SAMPLE_DEF), "..", "data", "openlane", "gcd.def")
    s = os.path.join(os.path.dirname(SAMPLE_DEF), "..", "data", "openlane", "gcd.spefok")
    b = NetlistBridge(g, s); b.load()
    cw = build_tile_crosswalk(b, nx=8, ny=8)
    sc = score_tiles(cw)
    assert sc.n_tiles > 10
    assert sc.best[1] >= 0.30                       # tile fanout/wirelength predict tile cap
    assert abs(sc.control_rho) < 0.30


# --- CLI ------------------------------------------------------------------

def test_cli_tiles_emits_valid_json(capsys):
    agent_tools.main(["tiles", "--nx", "4", "--ny", "4"])
    out = json.loads(capsys.readouterr().out)
    assert out["tool"] == "tiles"
    assert out["grid"] == [4, 4]
    assert "score" in out and "tiles" in out
    assert out["provenance"]
