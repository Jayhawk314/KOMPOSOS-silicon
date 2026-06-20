# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Exact cohomology laws and honest silicon calibration-nerve behavior."""

import json

from domains.silicon import agent_tools
from domains.silicon.coherence import (
    analyze_calibration_nerve, analyze_crosswalk_cohomology,
)
from domains.silicon.netlist_bridge import NetlistBridge
from domains.silicon.verilog import build_crosswalk, parse_verilog


def test_filled_triangle_has_h0_one_h1_zero():
    result = analyze_calibration_nerve(
        ["rtl", "def", "spef"],
        [("rtl", "def"), ("def", "spef"), ("rtl", "spef")],
        [("rtl", "def", "spef")])
    assert result.h0_dimension == 1
    assert result.h1_dimension == 0


def test_unfilled_pairwise_cycle_has_localized_h1_obstruction():
    result = analyze_calibration_nerve(
        ["rtl", "def", "spef"],
        [("rtl", "def"), ("def", "spef"), ("rtl", "spef")])
    assert result.h0_dimension == 1
    assert result.h1_dimension == 1
    assert set(result.h1_support[0]) == {
        "def<->rtl", "def<->spef", "rtl<->spef"}


def test_disconnected_artifacts_raise_h0_not_false_h1():
    result = analyze_calibration_nerve(
        ["rtl", "def", "spef"], [("rtl", "def")])
    assert result.h0_dimension == 2
    assert result.h1_dimension == 0


def test_current_two_step_crosswalk_does_not_invent_h1(tmp_path):
    def_path = tmp_path / "tiny.def"
    def_path.write_text("""
VERSION 5.8 ; UNITS DISTANCE MICRONS 1000 ;
COMPONENTS 2 ;
- a INV_X1 + PLACED ( 0 0 ) N ;
- b INV_X1 + PLACED ( 1000 0 ) N ;
END COMPONENTS
NETS 1 ;
- physical ( a ZN ) ( b A ) ;
END NETS
END DESIGN
""", encoding="utf-8")
    spef_path = tmp_path / "tiny.spef"
    spef_path.write_text("*D_NET physical 0.2\n", encoding="utf-8")
    logical = parse_verilog("""
module tiny();
wire logical;
INV_X1 a(.ZN(logical));
INV_X1 b(.A(logical));
endmodule
""")
    bridge = NetlistBridge(str(def_path), str(spef_path)); bridge.load()
    result = analyze_crosswalk_cohomology(build_crosswalk(logical, bridge), bridge)
    assert result.h0_dimension == 1
    assert result.h1_dimension == 0
    assert result.pairwise_calibrations == [("def", "spef"), ("def", "verilog")]


def test_cli_reports_exact_dimensions_without_false_obstruction(tmp_path, capsys):
    def_path = tmp_path / "tiny.def"
    def_path.write_text("""
VERSION 5.8 ; UNITS DISTANCE MICRONS 1000 ;
COMPONENTS 2 ;
- a INV_X1 + PLACED ( 0 0 ) N ;
- b INV_X1 + PLACED ( 1000 0 ) N ;
END COMPONENTS
NETS 1 ; - physical ( a ZN ) ( b A ) ; END NETS
END DESIGN
""", encoding="utf-8")
    verilog_path = tmp_path / "tiny.v"
    verilog_path.write_text("""
module tiny();
wire logical;
INV_X1 a(.ZN(logical));
INV_X1 b(.A(logical));
endmodule
""", encoding="utf-8")
    agent_tools.main([
        "--def", str(def_path), "--verilog", str(verilog_path), "cohomology"])
    output = json.loads(capsys.readouterr().out)
    assert output["h0_dimension"] == 1
    assert output["h1_dimension"] == 0
    assert output["status"] == "COHERENT"
