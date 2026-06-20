# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""IR-drop scoreboard: structure should predict real IR-drop (unlike timing).

Pure-logic tests always run. The real-design assertion runs only when the gitignored
OpenROAD IR artifacts are present (regenerate via the ORFS + analyze_power_grid flow);
it skips otherwise, mirroring the other real-data tests.
"""

import os
import pytest

from domains.silicon.ir_scoreboard import (
    IRScoreReport, _spearman, _prec_at_k, ir_scoreboard,
)


def test_spearman_monotone():
    a = [1, 2, 3, 4, 5]
    assert _spearman(a, a) == pytest.approx(1.0)
    assert _spearman(a, a[::-1]) == pytest.approx(-1.0)


def test_prec_at_k_overlap():
    real = [5, 4, 3, 2, 1]
    assert _prec_at_k([5, 4, 3, 2, 1], real, 2) == pytest.approx(1.0)
    assert _prec_at_k([1, 2, 3, 4, 5], real, 2) == pytest.approx(0.0)


def test_pass_requires_signal_and_clean_control():
    r = IRScoreReport(design="x", n_tiles=400, grid=20, supply_v=1.1, worst_drop_v=0.09)
    r.spearman = {"fanout": 0.55}; r.control = {"fanout": -0.1}
    assert r.passed
    r.control = {"fanout": 0.4}                       # dirty control -> fail
    assert not r.passed
    r.control = {"fanout": -0.1}; r.spearman = {"fanout": 0.1}   # weak signal -> fail
    assert not r.passed


_AES = "domains/silicon/data/orfs_aes/results/nangate45/aes/base"
_VOLT = "domains/silicon/data/ir_aes/ir_voltage.rpt"


@pytest.mark.skipif(not (os.path.exists(f"{_AES}/6_final.def") and os.path.exists(_VOLT)),
                    reason="real OpenROAD IR artifacts absent (gitignored)")
def test_structure_predicts_real_ir_drop_aes():
    rep = ir_scoreboard(f"{_AES}/6_final.def", f"{_AES}/6_final.spef",
                        "domains/silicon/data/openlane/Nangate45.lef", _VOLT, design="aes")
    # Unlike timing, structure must actually predict IR-drop hotspots.
    assert rep.passed, rep.render()
    name, rho = rep.best
    assert rho >= 0.30 and abs(rep.control[name]) < 0.20
