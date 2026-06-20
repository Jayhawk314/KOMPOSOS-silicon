# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Phase 4: the reliability co-design loop proves both sides of the fix."""

import os
import pytest

from domains.silicon.codesign_loop import (
    prove_fix, codesign, _em_gain_orders, CoDesignPortfolio,
)


def test_em_gain_orders_positive_for_higher_activation():
    # Cu (0.80 eV) -> W (1.60 eV): Black's eq predicts a large positive lifetime gain.
    assert _em_gain_orders(0.80, 1.60) > 5
    assert _em_gain_orders(0.80, 0.80) == 0.0


def test_local_net_keeps_the_metal_swap():
    f = prove_fix("hot_local", wirelength_um=2.0, local_threshold_um=50.0)
    assert f.is_local and f.action == "swap_interconnect" and f.keep
    assert f.candidate != "Cu" and f.em_mttf_gain_orders > 0
    assert f.resistance_penalty_x > 1            # the honest cost is recorded
    assert f.citations and f.tier == "validated_hypothesis"


def test_global_net_redirects_to_widen_not_swap():
    # Same fix, but a long net: the resistance penalty makes the swap not worth it.
    f = prove_fix("hot_global", wirelength_um=2000.0, local_threshold_um=50.0)
    assert not f.is_local and f.action == "widen_wire" and f.keep
    assert "resistance" in f.reasons[0] and "widen" in f.reasons[0]


def test_resistance_penalty_is_real_cu_to_w():
    f = prove_fix("n", wirelength_um=1.0, local_threshold_um=50.0)
    # W bulk-table 5.60 / Cu 1.68 ~ 3.3x
    assert 3.0 < f.resistance_penalty_x < 3.6


_AES = "domains/silicon/data/orfs_aes/results/nangate45/aes/base"


@pytest.mark.skipif(not os.path.exists(f"{_AES}/6_final.def"),
                    reason="real ORFS layout absent (gitignored)")
def test_codesign_on_real_aes():
    p = codesign(f"{_AES}/6_final.def", f"{_AES}/6_final.spef",
                 "domains/silicon/data/openlane/Nangate45.lef", design="aes", top=6)
    assert isinstance(p, CoDesignPortfolio) and len(p.fixes) == 6
    for f in p.fixes:
        assert f.citations and f.reasons and f.status in ("AGREE", "HOLLOW")
