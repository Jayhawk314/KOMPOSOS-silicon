# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""LEF + STA laws: real cell library awareness and STA as `measured` ground truth."""

import os

import pytest

from domains.silicon.lef import parse_lef, Macro
from domains.silicon.sta import (
    ArtifactReceipt, TimingReport, load_sta, parse_sta, worst_slack,
    violating_endpoints, critical_nets,
)
from domains.silicon.netlist_bridge import NetlistBridge, SAMPLE_DEF, SAMPLE_SPEF
from domains.silicon.waste_ledger import claims_from_sta, build_waste_ledger

_SAMPLES = os.path.dirname(SAMPLE_DEF)
_STA_RPT = os.path.join(_SAMPLES, "tiny_core.sta.rpt")
_NANGATE = os.path.join(_SAMPLES, "..", "data", "openlane", "Nangate45.lef")


def _context_receipts():
    return {
        name: ArtifactReceipt(f"{name}.input", character * 64)
        for name, character in (("netlist", "a"), ("liberty", "b"),
                                ("constraints", "c"))
    }


# --- LEF parser -----------------------------------------------------------

def test_parse_lef_macro_size_and_pin_directions():
    lef = """
    MACRO INV_X1
      SIZE 0.38 BY 1.4 ;
      PIN A
        DIRECTION INPUT ;
      PIN ZN
        DIRECTION OUTPUT ;
      PIN VDD
        DIRECTION INOUT ;
    END INV_X1
    """
    macros = parse_lef(lef)
    inv = macros["INV_X1"]
    assert inv.width == 0.38 and inv.height == 1.4
    assert inv.area == pytest.approx(0.532)
    assert inv.pins["A"] == "INPUT" and inv.pins["ZN"] == "OUTPUT"
    assert inv.output_pins() == ["ZN"]


@pytest.mark.skipif(not os.path.exists(_NANGATE), reason="Nangate45.lef not downloaded")
def test_real_nangate_lef_has_known_cells():
    macros = parse_lef(open(_NANGATE, encoding="utf-8").read())
    assert "INV_X1" in macros and "NAND2_X1" in macros
    assert macros["INV_X1"].output_pins() == ["ZN"]
    assert macros["INV_X1"].area > 0


@pytest.mark.skipif(not os.path.exists(_NANGATE), reason="Nangate45.lef not downloaded")
def test_lef_picks_real_driver_direction():
    """With LEF, the net's driver is its OUTPUT pin, not the first-listed pin."""
    gcd = os.path.join(_SAMPLES, "..", "data", "openlane", "45_gcd.def")
    if not os.path.exists(gcd):
        pytest.skip("45_gcd.def not downloaded")
    b = NetlistBridge(gcd, lef_path=_NANGATE)
    b.load()
    # at least one net's chosen driver is genuinely an OUTPUT pin in the LEF
    drivers_are_outputs = 0
    for net in b.signal_nets[:50]:
        di = b._driver_index(net)
        inst, pin = net.conns[di]
        m = b._macro_of(inst)
        if m and m.pins.get(pin) == "OUTPUT":
            drivers_are_outputs += 1
    assert drivers_are_outputs > 0


# --- STA parser + measured tier -------------------------------------------

def test_parse_sta_fixture():
    paths = parse_sta(open(_STA_RPT, encoding="utf-8").read())
    assert len(paths) == 2
    viol = [p for p in paths if p.violated]
    assert len(viol) == 1 and viol[0].endpoint == "u_a2"
    assert worst_slack(paths) == pytest.approx(-0.15)
    assert violating_endpoints(paths) == [("u_a2", -0.15)]


def test_parse_common_opensta_slack_layout_and_hierarchical_pin():
    text = """
Startpoint: top/u0/Q
Endpoint: top/u1/D
  0.10  0.10  top/core/u0/Q (DFF_X1)
  0.20  0.30  top/core/u1/D (DFF_X1)
  slack (VIOLATED) -2.5e-2
"""
    paths = parse_sta(text)
    assert len(paths) == 1
    assert paths[0].slack == pytest.approx(-0.025)
    assert ("top/core/u0", "Q") in paths[0].pins


def test_critical_nets_maps_path_to_nets():
    paths = parse_sta(open(_STA_RPT, encoding="utf-8").read())
    b = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF)
    b.load()
    crit = critical_nets(paths, b)
    assert "n_a1" in crit and crit["n_a1"] == pytest.approx(0.15)
    assert "clk" not in crit


def test_load_sta_marks_fixture_and_hashes_source():
    report = load_sta(_STA_RPT)
    assert report.source_kind == "fixture"
    assert report.is_evidence is False
    assert len(report.sha256) == 64


def test_unmarked_sta_is_unverified_until_explicitly_attested(tmp_path):
    text = open(_STA_RPT, encoding="utf-8").read().replace(
        "KOMPOSOS-V silicon STA fixture", "external timing artifact")
    path = tmp_path / "unknown.rpt"
    path.write_text(text, encoding="utf-8")
    assert load_sta(path).source_kind == "unverified"
    assert load_sta(path).is_evidence is False
    assert load_sta(path, source_kind="tool").is_evidence is False
    context_paths = {}
    for name in ("netlist", "liberty", "constraints"):
        context_path = tmp_path / f"{name}.txt"
        context_path.write_text(name, encoding="utf-8")
        context_paths[name] = context_path
    report = load_sta(path, source_kind="tool", context_paths=context_paths)
    assert report.is_evidence is True
    assert report.missing_context == []


def test_sta_produces_measured_claims():
    paths = parse_sta(open(_STA_RPT, encoding="utf-8").read())
    report = TimingReport(
        paths, "real_sta.rpt", "tool", "a" * 64,
        context=_context_receipts())
    claims = claims_from_sta(report)
    assert claims and all(c.evidence_level == "measured" for c in claims)
    assert claims[0].quantity == pytest.approx(0.15)
    assert "sha256=" in claims[0].source


def test_fixture_never_produces_measured_claims():
    assert claims_from_sta(load_sta(_STA_RPT)) == []


def test_ledger_includes_measured_tier_with_sta():
    from domains.silicon.netlist_bridge import analyze_layout
    paths = parse_sta(open(_STA_RPT, encoding="utf-8").read())
    report = TimingReport(
        paths, "real_sta.rpt", "tool", "b" * 64,
        context=_context_receipts())
    b = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF)
    b.load()
    ledger = build_waste_ledger(analyze_layout(b), b, sta_report=report)
    assert ledger.counts_by_evidence().get("measured", 0) >= 1
    # measured claims rank above structural ones
    assert ledger.ranked()[0].evidence_level == "measured"


def test_parse_sta_empty_is_graceful():
    assert parse_sta("no timing here") == []
