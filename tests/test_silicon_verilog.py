# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Gate-netlist parser and endpoint-identity crosswalk laws."""

import json

from domains.silicon import agent_tools
from domains.silicon.netlist_bridge import NetlistBridge
from domains.silicon.verilog import build_crosswalk, parse_verilog


DEF = """
VERSION 5.8 ;
UNITS DISTANCE MICRONS 1000 ;
COMPONENTS 3 ;
- drv INV_X1 + PLACED ( 0 0 ) N ;
- sink_a NAND2_X1 + PLACED ( 1000 0 ) N ;
- sink_b NAND2_X1 + PLACED ( 0 1000 ) N ;
END COMPONENTS
NETS 1 ;
- physical_42 ( sink_b B ) ( drv ZN ) ( sink_a A ) ;
END NETS
END DESIGN
"""

VERILOG = """
module tiny(input clk, output done);
  wire [3:0] unused_bus;
  wire logical_result;
  INV_X1 drv (.A(clk), .ZN(logical_result));
  NAND2_X1 sink_a (.A(logical_result), .B(1'b0), .ZN(done));
  NAND2_X1 sink_b (.A(clk), .B(logical_result), .ZN());
endmodule
"""


def _bridge(tmp_path):
    path = tmp_path / "design.def"
    path.write_text(DEF, encoding="utf-8")
    bridge = NetlistBridge(str(path))
    bridge.load()
    return bridge


def test_parse_structural_verilog_ports_buses_and_instances():
    netlist = parse_verilog(VERILOG)
    assert netlist.module == "tiny"
    assert netlist.ports == {"clk": "input", "done": "output"}
    assert "unused_bus" in netlist.nets
    assert set(netlist.instances) == {"drv", "sink_a", "sink_b"}
    assert netlist.instances["drv"].connections["ZN"] == "logical_result"
    assert "1'b0" not in netlist.endpoints_by_net()


# A sequential cell whose instance name is an *escaped identifier* (`\name[i]$... `):
# real flows (Yosys/OpenROAD) name every flop this way. The bracket must not truncate the
# instance match, or the flop -- and its Q/QN driver -- vanishes from the logical view.
ESCAPED_VERILOG = """
module seq(input clk, input d, output q);
  wire _00000_;
  DFF_X1 \\state[0]$_DFF_P_  (.D(d),
    .CK(clk),
    .Q(q),
    .QN(_00000_));
  INV_X1 load (.A(_00000_), .ZN());
endmodule
"""


def test_parse_escaped_identifier_instance_keeps_sequential_driver():
    netlist = parse_verilog(ESCAPED_VERILOG)
    # the flop instance is parsed despite the bracketed escaped name ...
    assert "state[0]$_DFF_P_" in netlist.instances
    flop = netlist.instances["state[0]$_DFF_P_"]
    assert flop.cell == "DFF_X1"
    assert flop.connections["Q"] == "q"
    assert flop.connections["QN"] == "_00000_"
    # ... so the net _00000_ carries BOTH its flop driver and its sink (not just the sink).
    endpoints = netlist.endpoints_by_net()
    assert ("state[0]$_DFF_P_", "QN") in endpoints["_00000_"]
    assert ("load", "A") in endpoints["_00000_"]


def test_crosswalk_matches_renamed_net_by_terminal_identity(tmp_path):
    crosswalk = build_crosswalk(parse_verilog(VERILOG), _bridge(tmp_path))
    match = next(match for match in crosswalk.matches
                 if match.logical_net == "logical_result")
    assert match.physical_net == "physical_42"
    assert match.renamed is True
    assert match.endpoints == (("drv", "ZN"), ("sink_a", "A"), ("sink_b", "B"))
    assert crosswalk.cell_mismatches == []


def test_crosswalk_reports_cell_and_instance_mismatches(tmp_path):
    broken = VERILOG.replace("INV_X1 drv", "BUF_X1 drv").replace(
        "endmodule", "  BUF_X1 missing (.A(clk), .Z(done));\nendmodule")
    crosswalk = build_crosswalk(parse_verilog(broken), _bridge(tmp_path))
    assert ("drv", "BUF_X1", "INV_X1") in crosswalk.cell_mismatches
    assert crosswalk.missing_instances == ["missing"]
    assert crosswalk.exact is False


def test_cli_crosswalk_reports_renamed_identity(tmp_path, capsys):
    def_path = tmp_path / "design.def"
    verilog_path = tmp_path / "design.v"
    def_path.write_text(DEF, encoding="utf-8")
    verilog_path.write_text(VERILOG, encoding="utf-8")
    agent_tools.main([
        "--def", str(def_path), "--verilog", str(verilog_path), "crosswalk"])
    output = json.loads(capsys.readouterr().out)
    assert output["matched_nets"] == 1
    assert output["renamed_nets"] == 1
    assert output["matches"][0]["physical"] == "physical_42"
