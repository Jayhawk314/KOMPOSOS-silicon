# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""A learned IR-drop predictor, trust-gated on held-out data.

The gate must have teeth: a model that genuinely generalizes is trusted; one whose
predictions do not match held-out reality is BLOCKED, even if it fit its own data.
"""

import os
import numpy as np
import pytest

from domains.silicon.ml_hotspot import evaluate_and_gate, FEATURES


def _table(n, signal=True, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, len(FEATURES)))
    y = X[:, 0] + 0.3 * X[:, 4] + 0.1 * rng.normal(size=n) if signal else rng.normal(size=n)
    return (X, y)


def test_generalizing_model_is_trusted():
    # train and test drawn from the same real relationship -> should generalize and pass.
    v = evaluate_and_gate((_table(300, True, 1), "train"), (_table(300, True, 2), "test"))
    assert v.trusted and v.ml_rho >= 0.30 and abs(v.control_rho) < 0.20


def test_nongeneralizing_model_is_blocked():
    # held-out target is pure noise, unrelated to the features -> gate must BLOCK it.
    v = evaluate_and_gate((_table(300, True, 1), "train"), (_table(300, False, 3), "test"))
    assert not v.trusted
    assert "BLOCKED" in v.reason


_AES = "domains/silicon/data/orfs_aes/results/nangate45/aes/base"
_IBEX = "domains/silicon/data/orfs_ibex/results/nangate45/ibex/base"


@pytest.mark.skipif(
    not (os.path.exists(f"{_AES}/6_final.def") and os.path.exists(f"{_IBEX}/6_final.def")
         and os.path.exists("domains/silicon/data/ir_aes/ir_voltage.rpt")
         and os.path.exists("domains/silicon/data/ir_ibex/ir_voltage.rpt")),
    reason="real IR artifacts absent (gitignored)")
def test_learned_model_beats_cheap_baseline_on_real_designs():
    from domains.silicon.ml_hotspot import _tile_table
    aes = (_tile_table(f"{_AES}/6_final.def", f"{_AES}/6_final.spef",
                       "domains/silicon/data/openlane/Nangate45.lef",
                       "domains/silicon/data/ir_aes/ir_voltage.rpt", 1.1), "aes")
    ibex = (_tile_table(f"{_IBEX}/6_final.def", f"{_IBEX}/6_final.spef",
                        "domains/silicon/data/openlane/Nangate45.lef",
                        "domains/silicon/data/ir_ibex/ir_voltage.rpt", 1.1), "ibex")
    v = evaluate_and_gate(aes, ibex)
    # cross-design: the learned model must generalize and (modestly) beat the cheap baseline.
    assert v.trusted and v.beats_baseline
