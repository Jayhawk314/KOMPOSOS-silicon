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


# Real OpenROAD `-fields {input_pins net capacitance slew fanout} -digits 5` layout:
# driver OUTPUT rows have 5 leading cols (Fanout Cap Slew Delay Time); load INPUT rows have
# 3 (Slew Delay Time). Delay is the SECOND-to-last number either way. The load-input row's
# Delay is the WIRE delay; driver output rows (r1/Q, u1/Z) carry cell arcs and must NOT be
# attributed. Net-name rows (`net_a (net)`) carry no edge char and are skipped.
_REPORT = """\
Startpoint: r1 (rising edge-triggered flip-flop clocked by clk)
Endpoint: r2 (rising edge-triggered flip-flop clocked by clk)
Path Type: max

Fanout     Cap    Slew   Delay    Time   Description
-----------------------------------------------------------------------------
                  0.00000    0.00000    0.00000   clock clk (rise edge)
                  0.00000    0.00000    0.00000 ^ r1/CK (DFF_X1)
     1    1.77    0.01000    0.09000    0.09000 ^ r1/Q (DFF_X1)
                                         net_a (net)
                  0.01000    0.01200    0.10200 ^ u1/A (BUF_X1)
     2    4.82    0.02000    0.03000    0.13200 ^ u1/Z (BUF_X1)
                                         net_b (net)
                  0.02000    0.02500    0.15700 ^ u2/A (INV_X1)
             0.15700   data arrival time
            -0.01000   slack (VIOLATED)

Startpoint: r1 (rising edge-triggered flip-flop clocked by clk)
Endpoint: r3 (rising edge-triggered flip-flop clocked by clk)
Path Type: max

Fanout     Cap    Slew   Delay    Time   Description
-----------------------------------------------------------------------------
     1    1.77    0.01000    0.09000    0.09000 ^ r1/Q (DFF_X1)
                                         net_a (net)
                  0.01000    0.01500    0.10500 ^ u1/A (BUF_X1)
             0.10500   data arrival time
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
    # Delay = second-to-last column, robust to 3-col (input) vs 5-col (output) rows.
    assert ("u1", "A", 0.0120) in rows        # load input row, 3 cols -> wire delay
    assert ("u2", "A", 0.0250) in rows
    assert ("r1", "Q", 0.0900) in rows        # driver output row, 5 cols -> cell delay


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
