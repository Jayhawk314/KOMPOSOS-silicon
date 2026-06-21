# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Laws for the tau (interconnect-delay) scoreboard."""

import os

import pytest

from domains.silicon.tau_scoreboard import (
    parse_spef_rc, elmore_rc, tau_scoreboard, tau_scoreboard_measured,
)

_DETAILED_SPEF = """\
*SPEF "IEEE 1481-1998"
*DESIGN "toy"
*T_UNIT 1 NS
*C_UNIT 1 PF
*R_UNIT 1 OHM

*NAME_MAP
*1 net_alpha
*2 net_beta

*D_NET *1 0.0030
*CONN
*I *10:ZN O *D INV_X1
*I *11:A I *D NAND2_X1
*CAP
1 *10:ZN 0.0015
2 *11:A 0.0015
*RES
1 *10:ZN *1:2 8.0
2 *1:2 *11:A 2.0
*END

*D_NET *2 0.0010
*CONN
*I *12:ZN O *D INV_X1
*I *13:A I *D NAND2_X1
*CAP
1 *12:ZN 0.0010
*RES
1 *12:ZN *13:A 1.0
*END
"""


def test_parse_spef_rc_resolves_names_and_sums_resistance():
    rc = parse_spef_rc(_DETAILED_SPEF)
    assert set(rc) == {"net_alpha", "net_beta"}
    r_a, c_a = rc["net_alpha"]
    assert r_a == pytest.approx(10.0)        # 8.0 + 2.0
    assert c_a == pytest.approx(0.0030)      # *D_NET header
    r_b, c_b = rc["net_beta"]
    assert r_b == pytest.approx(1.0)
    assert c_b == pytest.approx(0.0010)


def test_elmore_rc_is_product():
    delay = elmore_rc(parse_spef_rc(_DETAILED_SPEF))
    assert delay["net_alpha"] == pytest.approx(10.0 * 0.0030)
    assert delay["net_beta"] == pytest.approx(1.0 * 0.0010)
    # net_alpha (more R and more C) must rank above net_beta -- the whole point.
    assert delay["net_alpha"] > delay["net_beta"]


def test_reduced_spef_net_gets_zero_resistance():
    # A net with no *RES section (lumped/reduced SPEF) must not crash; R defaults to 0.
    reduced = "*NAME_MAP\n*1 only_cap\n\n*D_NET *1 0.005\n*CAP\n1 *9:Z 0.005\n*END\n"
    rc = parse_spef_rc(reduced)
    assert rc["only_cap"] == pytest.approx((0.0, 0.005))


_REAL_BASE = "domains/silicon/data/sta_45gcd"


@pytest.mark.skipif(
    not os.path.exists(f"{_REAL_BASE}/45_gcd.spef"),
    reason="real detailed-SPEF 45_gcd artifacts absent (regenerate via sta_flows)")
def test_tau_scoreboard_runs_on_real_45gcd():
    rep = tau_scoreboard(
        f"{_REAL_BASE}/45_gcd.def", f"{_REAL_BASE}/45_gcd.spef",
        lef_path=f"{_REAL_BASE}/Nangate45.lef", design="45_gcd")
    assert rep.n_nets >= 50
    assert rep.target == "interconnect_rc_delay"
    assert rep.source_kind == "measured_proxy"
    # The shuffle control must collapse -- proves any signal found is real, not an artifact.
    assert abs(rep.control_rho) < 0.20


@pytest.mark.skipif(
    not os.path.exists(f"{_REAL_BASE}/45_gcd.netdelay.report_checks.txt"),
    reason="net-delay report absent (run sta_flows/tau_netdelay_sta.tcl via Docker)")
def test_tau_scoreboard_measured_on_real_45gcd():
    """measured tier: structure vs the tool's OWN per-net interconnect delay."""
    rep = tau_scoreboard_measured(
        f"{_REAL_BASE}/45_gcd.def", f"{_REAL_BASE}/45_gcd.spef",
        f"{_REAL_BASE}/Nangate45.lef",
        f"{_REAL_BASE}/45_gcd.netdelay.report_checks.txt", design="45_gcd",
        sta_source_kind="tool",
        sta_context_paths={"netlist": f"{_REAL_BASE}/45_gcd.def",
                           "liberty": f"{_REAL_BASE}/nangate45_typ.lib.gz",
                           "constraints": f"{_REAL_BASE}/45_gcd.sdc"})
    assert rep.target == "interconnect_net_delay"
    assert rep.evidence_eligible           # tool-attested with hashed netlist/liberty/sdc
    assert rep.source_kind == "tool"
    assert rep.passed                      # clean PASS at full net coverage
    assert rep.best[1] > 0.4               # structure predicts measured wire delay
    assert abs(rep.control_rho) < 0.20
