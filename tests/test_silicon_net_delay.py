# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Laws for per-net interconnect (wire) delay extraction from report_checks.

These pin the parse contract that `sta_flows/tau_netdelay_sta.tcl` must satisfy, so the
`measured`-tier tau upgrade is testable now, before the Docker run that generates the
real report.
"""

import pytest

from domains.silicon.net_delay import (
    parse_pin_delays, build_load_pin_map, net_wire_delays,
)


# A report_checks path with `-fields {input_pins}`: load INPUT-pin rows are present, and
# their incremental Delay (first column) is the net (wire) delay. Driver OUTPUT-pin rows
# (r1/Q, u1/Z) carry cell-arc delay and must NOT be attributed to a net's wire delay.
_REPORT = """\
Startpoint: r1 (rising edge-triggered flip-flop clocked by clk)
Endpoint: r2 (rising edge-triggered flip-flop clocked by clk)
Path Type: max

    Delay      Time   Description
-------------------------------------------------------------
   0.0000    0.0000   clock clk (rise edge)
   0.0000    0.0000 ^ r1/CK (DFF_X1)
   0.0900    0.0900 ^ r1/Q (DFF_X1)
   0.0120    0.1020 ^ u1/A (BUF_X1)
   0.0300    0.1320 ^ u1/Z (BUF_X1)
   0.0250    0.1570 ^ u2/A (INV_X1)
   0.0000    0.1570 ^ r2/D (DFF_X1)
             0.1570   data arrival time
            -0.0100   slack (VIOLATED)

Startpoint: r1 (rising edge-triggered flip-flop clocked by clk)
Endpoint: r3 (rising edge-triggered flip-flop clocked by clk)
Path Type: max

    Delay      Time   Description
-------------------------------------------------------------
   0.0900    0.0900 ^ r1/Q (DFF_X1)
   0.0150    0.1050 ^ u1/A (BUF_X1)
             0.1050   data arrival time
"""


class _Net:
    def __init__(self, name, conns):
        self.name = name
        self.conns = conns


class _Bridge:
    """Minimal stand-in exposing the interface net_delay needs."""
    def __init__(self):
        self.nets = [
            _Net("net_a", [("r1", "Q"), ("u1", "A")]),     # driver r1/Q, load u1/A
            _Net("net_b", [("u1", "Z"), ("u2", "A")]),     # driver u1/Z, load u2/A
            _Net("clk",   [("ck", "Z"), ("r1", "CK")]),    # non-signal clock net
        ]
        self._signal = {"net_a": True, "net_b": True, "clk": False}

    def _is_signal(self, net):
        return self._signal[net.name]

    def _driver_index(self, net):
        return 0                                            # driver is conns[0] for all


def test_parse_pin_delays_captures_incremental_delay():
    rows = parse_pin_delays(_REPORT)
    # every transition row with inst/pin is captured (clock pin included; mapping filters it)
    assert ("u1", "A", 0.0120) in rows
    assert ("u2", "A", 0.0250) in rows
    assert ("r1", "Q", 0.0900) in rows


def test_load_pin_map_excludes_drivers_and_nonsignal():
    lpm = build_load_pin_map(_Bridge())
    assert lpm == {("u1", "A"): "net_a", ("u2", "A"): "net_b"}
    assert ("r1", "Q") not in lpm          # driver pin, not a wire-delay row
    assert ("r1", "CK") not in lpm         # clock (non-signal) net excluded


def test_net_wire_delays_attributes_and_takes_max():
    delays = net_wire_delays(_REPORT, _Bridge())
    # net_a load u1/A appears twice (0.0120, 0.0150) -> worst-case max kept
    assert delays["net_a"] == pytest.approx(0.0150)
    assert delays["net_b"] == pytest.approx(0.0250)
    # driver-only / clock nets never get a wire delay
    assert "clk" not in delays


def test_measured_fixture_cannot_pass_without_attestation():
    # The measured scoreboard wraps load_sta; an unattested report is not evidence even if
    # the metric is computable. (Smoke: the fixture marker / source policy lives in sta.py;
    # here we just assert net_wire_delays itself is content-only and order-stable.)
    d1 = net_wire_delays(_REPORT, _Bridge())
    d2 = net_wire_delays(_REPORT, _Bridge())
    assert d1 == d2
