# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Rung 2 laws: DEF/SPEF parse correctly and the layout's planted structure is found.

Includes robustness cases that matter for real OpenLane output: routing-coordinate
parens must not be misread as connections, power/clock nets are skipped, and a
missing SPEF degrades gracefully.
"""

import os

import pytest

from domains.silicon.netlist_bridge import (
    parse_def, parse_spef, NetlistBridge, analyze_layout, SAMPLE_DEF, SAMPLE_SPEF,
)


# --- parser correctness ---------------------------------------------------

def test_parse_def_components_and_placement():
    with open(SAMPLE_DEF, encoding="utf-8") as fh:
        comps, nets, dbu = parse_def(fh.read())
    assert dbu == 1000.0
    assert comps["u_a0"].cell == "NAND2_X1"
    assert comps["u_a0"].x == 1000.0 and comps["u_a0"].y == 2000.0
    assert {"u_a0", "u_a1", "u_a2", "u_a3", "u_b0", "u_b1", "u_b2"} <= set(comps)


def test_parse_def_net_connectivity():
    with open(SAMPLE_DEF, encoding="utf-8") as fh:
        _, nets, _ = parse_def(fh.read())
    by_name = {n.name: n for n in nets}
    assert ("u_a0", "ZN") in by_name["n_bus"].conns
    assert ("u_b0", "A") in by_name["n_bus"].conns
    assert by_name["clk"].use == "CLOCK"


def test_parse_spef_total_caps():
    with open(SAMPLE_SPEF, encoding="utf-8") as fh:
        caps = parse_spef(fh.read())
    assert caps["n_bus"] == 0.0185
    assert caps["n_a0"] == 0.0042


# --- robustness for real OpenLane DEF -------------------------------------

def test_routing_coordinates_not_parsed_as_connections():
    """A '+ ROUTED met1 ( x y ) ( x y )' tail must not become a (inst,pin) conn."""
    deftext = """
    UNITS DISTANCE MICRONS 2000 ;
    COMPONENTS 2 ;
    - i0 BUF + PLACED ( 10 20 ) N ;
    - i1 BUF + PLACED ( 30 40 ) N ;
    END COMPONENTS
    NETS 1 ;
    - sig ( i0 Z ) ( i1 A )
      + ROUTED met1 ( 1000 2000 ) ( 3000 2000 ) M1M2_via ( 5000 2000 ) ;
    END NETS
    """
    comps, nets, dbu = parse_def(deftext)
    assert dbu == 2000.0
    assert nets[0].conns == [("i0", "Z"), ("i1", "A")]   # no coordinate junk


def test_power_and_clock_and_singleton_nets_skipped():
    bridge = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF)
    kept = {n.name for n in bridge.signal_nets}
    assert "clk" not in kept                # USE CLOCK skipped
    assert "n_bus" in kept and "n_a0" in kept


def test_missing_spef_degrades_gracefully():
    bridge = NetlistBridge(SAMPLE_DEF, spef_path=None)
    bridge.load()
    assert bridge.caps == {}
    a = analyze_layout(bridge)
    assert a.high_cap_nets == []           # no SPEF, no measured proxy
    assert a.corridors                     # structural geometry still works


# --- the planted structure is recovered -----------------------------------

def test_bus_is_the_congestion_bottleneck():
    bridge = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF)
    bridge.load()
    a = analyze_layout(bridge)
    assert a.corridors[0][2] == "n_bus"        # net of worst corridor
    assert a.corridors[0][3] < 0               # negative curvature


def test_fiedler_seam_cuts_the_bus_between_clusters():
    bridge = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF)
    bridge.load()
    a = analyze_layout(bridge)
    sides = [set(a.partition_a), set(a.partition_b)]
    assert {"u_a0", "u_a1", "u_a2", "u_a3"} in sides
    assert {"u_b0", "u_b1", "u_b2"} in sides
    assert a.cut_nets == ["n_bus"]


def test_highest_load_net_is_the_bus():
    bridge = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF)
    bridge.load()
    a = analyze_layout(bridge)
    assert a.high_cap_nets[0][0] == "n_bus"


# --- real-tool SPEF name-map resolution (the fix for OpenROAD .spefok) ------

def test_spef_name_map_resolves_numeric_ids():
    """Real SPEF emits '*57 _000_' then '*D_NET *57 <cap>' — resolve to the name."""
    spef = (
        '*SPEF "ieee 1481-1999"\n*C_UNIT 1 PF\n*NAME_MAP\n'
        "*57 _000_\n*58 _001_\n"
        "*D_NET *57 0.00120\n*END\n*D_NET *58 0.00035\n*END\n"
    )
    caps = parse_spef(spef)
    assert caps["_000_"] == 0.00120
    assert caps["_001_"] == 0.00035
    assert "*57" not in caps and "57" not in caps


# --- real downloaded GCD layout (skips if the gitignored download is absent) -

_GCD_DEF = os.path.join(os.path.dirname(SAMPLE_DEF), "..", "data", "openlane", "gcd.def")
_GCD_SPEF = os.path.join(os.path.dirname(SAMPLE_DEF), "..", "data", "openlane", "gcd.spefok")


@pytest.mark.skipif(not os.path.exists(_GCD_DEF),
                    reason="real GCD DEF not downloaded (gitignored data/openlane/)")
def test_real_gcd_layout_parses_and_analyzes():
    bridge = NetlistBridge(_GCD_DEF, _GCD_SPEF)
    bridge.load()
    assert len(bridge.category.objects()) > 100        # real design, hundreds of cells
    a = analyze_layout(bridge)
    assert a.corridors and a.corridors[0][3] < 0       # a real negative-curvature corridor
    assert a.high_cap_nets and a.high_cap_nets[0][1] > 0  # SPEF name-map resolved
