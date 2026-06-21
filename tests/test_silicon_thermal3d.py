# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Laws for the 3D thermal (multi-die) scoreboard.

A synthetic case plants a known cross-die coupling (temp driven by the STACKED tile's
power, not the tile's own) and asserts the scoreboard recovers it with a clean shuffle
control. Plus a skip-if-absent test on the real cloned Open3DBench data.
"""

import os
import random

import pytest

from domains.silicon.thermal3d_scoreboard import (
    parse_ptrace, parse_steady_tiles, thermal3d_scoreboard,
)


def _write_synth(tmp_path, n=6):
    """5..n grid, 2 dies; temp = 300 + 40*stacked_power (own power is independent)."""
    rng = random.Random(0)
    dies = ("upper", "bottom")
    power = {f"{d}_{r}_{c}": rng.uniform(0.0, 1.0)
             for d in dies for r in range(n) for c in range(n)}
    names = list(power)
    ptrace = tmp_path / "test.ptrace"
    ptrace.write_text(" ".join(names) + "\n" + " ".join(f"{power[k]:.5f}" for k in names) + "\n")

    # temperature of a tile is driven by the OTHER die's tile at the same (r,c).
    def stacked(d, r, c):
        other = "bottom" if d == "upper" else "upper"
        return power[f"{other}_{r}_{c}"]

    lines = []
    layer = {"upper": (0, 1), "bottom": (2, 3)}
    for d in dies:
        for r in range(n):
            for c in range(n):
                t = 300.0 + 40.0 * stacked(d, r, c)
                for L in layer[d]:
                    lines.append(f"layer_{L}_{d}_{r}_{c}\t{t:.2f}")
    steady = tmp_path / "test.steady"
    steady.write_text("\n".join(lines) + "\n")
    return str(ptrace), str(steady)


def test_parsers_roundtrip(tmp_path):
    pt, st = _write_synth(tmp_path)
    power = parse_ptrace(pt)
    temp = parse_steady_tiles(st)
    assert ("upper", 0, 0) in temp and ("bottom", 5, 5) in temp
    assert len(power) == 72 and len(temp) == 72        # 6x6 x 2 dies


def test_cross_die_coupling_recovered(tmp_path):
    pt, st = _write_synth(tmp_path)
    rep = thermal3d_scoreboard(pt, st, design="synth")
    # planted: temp tracks STACKED power, not own.
    assert rep.spearman["stacked"] > 0.8
    assert rep.spearman["stacked"] > rep.spearman["own"]
    assert rep.coupling_gain > 0.0                     # cross-die term adds over 2D baseline
    # shuffle control on the best predictor collapses -> the signal is real
    name = rep.best[0]
    assert abs(rep.control[name]) < 0.20
    # die_filter isolates one die; the planted coupling is symmetric so it survives
    up = thermal3d_scoreboard(pt, st, design="synth", die_filter="upper")
    assert up.n_tiles == 36 and up.coupling_gain > 0.0


_EX = "domains/silicon/data/open3dbench/OpenROAD-3D/flow/HotSpot/examples/3D_bp_fe"


@pytest.mark.skipif(
    not os.path.exists(f"{_EX}/outputs/test.steady"),
    reason="Open3DBench not cloned (git clone lamda-bbo/Open3DBench)")
def test_real_open3dbench_bp_fe():
    rep = thermal3d_scoreboard(f"{_EX}/test.ptrace", f"{_EX}/outputs/test.steady",
                               design="bp_fe")
    assert rep.n_tiles == 200                          # 2 dies x 10x10
    # the real, robust finding: cross-die coupling beats the own-power baseline
    assert rep.coupling_gain > 0.0
    assert rep.spearman["stacked"] > rep.spearman["own"]
    # REFINED: the coupling survives within the sink-far (upper) die -- not a pooling
    # artifact of the two dies having different stack geometry.
    up = thermal3d_scoreboard(f"{_EX}/test.ptrace", f"{_EX}/outputs/test.steady",
                              design="bp_fe", die_filter="upper")
    assert up.n_tiles == 100 and up.coupling_gain > 0.1
