# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Operadic net laws: n-ary semantics are canonical; graph projection is explicit."""

from domains.silicon.net_operad import arity_histogram, project_operation
from domains.silicon.netlist_bridge import NetlistBridge, SAMPLE_DEF, SAMPLE_SPEF


def _write_design(tmp_path, order, with_lef):
    connections = " ".join(f"( {inst} {pin} )" for inst, pin in order)
    def_path = tmp_path / ("ordered.def" if order[0][0] == "drv" else "shuffled.def")
    def_path.write_text(f"""
VERSION 5.8 ;
UNITS DISTANCE MICRONS 1000 ;
COMPONENTS 3 ;
- drv INV_X1 + PLACED ( 0 0 ) N ;
- sink_a NAND2_X1 + PLACED ( 1000 0 ) N ;
- sink_b NAND2_X1 + PLACED ( 0 1000 ) N ;
END COMPONENTS
NETS 1 ;
- n1 {connections} ;
END NETS
END DESIGN
""", encoding="utf-8")
    if not with_lef:
        return def_path, None

    lef_path = tmp_path / "cells.lef"
    lef_path.write_text("""
MACRO INV_X1
  SIZE 1 BY 1 ;
  PIN A
    DIRECTION INPUT ;
  PIN ZN
    DIRECTION OUTPUT ;
END INV_X1
MACRO NAND2_X1
  SIZE 1 BY 1 ;
  PIN A
    DIRECTION INPUT ;
  PIN B
    DIRECTION INPUT ;
  PIN ZN
    DIRECTION OUTPUT ;
END NAND2_X1
""", encoding="utf-8")
    return def_path, lef_path


def _bridge(def_path, lef_path=None):
    bridge = NetlistBridge(str(def_path), lef_path=str(lef_path) if lef_path else None)
    bridge.load()
    return bridge


def test_sample_has_one_nary_operation_per_signal_net():
    bridge = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF)
    bridge.load()
    assert len(bridge.net_operad.operations) == len(bridge.signal_nets)
    assert sum(arity_histogram(bridge.net_operad).values()) == len(bridge.signal_nets)
    operation_names = set(bridge.net_operad.operations)
    assert all(m.metadata["operad_operation"] in operation_names
               for m in bridge.category.morphisms())


def test_nary_semantics_ignore_def_connection_order_without_lef(tmp_path):
    ordered = [("drv", "ZN"), ("sink_a", "A"), ("sink_b", "B")]
    shuffled = [("sink_b", "B"), ("drv", "ZN"), ("sink_a", "A")]
    first = _bridge(*_write_design(tmp_path, ordered, with_lef=False))
    second = _bridge(*_write_design(tmp_path, shuffled, with_lef=False))
    op_a = first.net_operad.operations["net::n1"]
    op_b = second.net_operad.operations["net::n1"]

    assert op_a.arity == op_b.arity == 3
    assert op_a.data["terminals"] == op_b.data["terminals"]
    assert op_a.input_types == op_b.input_types == ["terminal_signal"] * 3
    assert op_a.data["projection_assumption"] == "def_order_fallback"
    assert op_b.data["projection_assumption"] == "def_order_fallback"
    assert set(project_operation(op_a)) != set(project_operation(op_b))


def test_lef_makes_graph_projection_order_invariant(tmp_path):
    ordered = [("drv", "ZN"), ("sink_a", "A"), ("sink_b", "B")]
    shuffled = [("sink_b", "B"), ("drv", "ZN"), ("sink_a", "A")]
    first = _bridge(*_write_design(tmp_path, ordered, with_lef=True))
    second = _bridge(*_write_design(tmp_path, shuffled, with_lef=True))
    op_a = first.net_operad.operations["net::n1"]
    op_b = second.net_operad.operations["net::n1"]

    assert op_a.data["terminals"] == op_b.data["terminals"]
    assert op_a.data["driver"] == op_b.data["driver"] == ("drv", "ZN", "drv")
    assert op_a.data["projection_assumption"] == "lef_output"
    assert op_b.data["projection_assumption"] == "lef_output"
    assert set(project_operation(op_a)) == set(project_operation(op_b)) == {
        ("drv", "sink_a"), ("drv", "sink_b")}
