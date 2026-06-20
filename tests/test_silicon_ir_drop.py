# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""IR-drop / EM laws: honest proxy tiers, the EM->materials tradeoff, gated proposals."""

import json

import pytest

from domains.silicon.netlist_bridge import NetlistBridge, analyze_layout, SAMPLE_DEF, SAMPLE_SPEF
from domains.silicon.tiles import build_tile_crosswalk
from domains.silicon.ir_drop import ir_drop_hotspots, em_risk_nets, claims_from_power
from domains.silicon.interconnect import (
    propose_interconnect, recommend_interconnect, INTERCONNECT_METALS,
)
from domains.silicon.waste_ledger import build_waste_ledger
from domains.silicon import agent_tools


def _bridge():
    b = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF)
    b.load()
    return b


# --- the EM-vs-resistance materials tradeoff ------------------------------

def test_severity_shifts_proposal_from_cu_to_refractory():
    benign = propose_interconnect(0.0)
    hot = propose_interconnect(1.0)
    assert benign[0].metal == "Cu"                       # conductivity wins when cool
    assert hot[0].metal in {"W", "Ru", "Co"}             # EM resistance wins when hot
    assert benign[0].metal != hot[0].metal


def test_metal_property_table_is_sane():
    cu, ru = INTERCONNECT_METALS["Cu"], INTERCONNECT_METALS["Ru"]
    assert cu.resistivity_uohm_cm < ru.resistivity_uohm_cm     # Cu conducts better
    assert ru.em_activation_eV > cu.em_activation_eV            # Ru resists EM better
    assert ru.barrierless and not cu.barrierless


def test_recommend_is_gated_and_grounded():
    hot = recommend_interconnect("n_bus", severity=1.0)
    assert hot.status in {"AGREE", "HOLLOW"}
    assert hot.recommended in INTERCONNECT_METALS
    assert hot.reasons
    cool = recommend_interconnect("n_q", severity=0.05)
    assert cool.recommended == "Cu" and cool.status == "AGREE"


# --- IR-drop hotspots + EM-risk nets --------------------------------------

def test_ir_drop_hotspots_sorted_by_demand():
    b = _bridge()
    cw = build_tile_crosswalk(b, nx=4, ny=4)
    tiles = ir_drop_hotspots(cw)
    demands = [t.current_demand_pf for t in tiles]
    assert demands == sorted(demands, reverse=True)


def test_em_risk_bus_is_worst_and_gets_recommendation():
    b = _bridge()
    risks = em_risk_nets(b, top_recommend=3)
    assert risks[0].net == "n_bus"
    assert risks[0].severity == pytest.approx(1.0)
    assert risks[0].recommendation is not None


# --- honesty: power evidence is proxy, never measured ----------------------

def test_power_claims_are_measured_proxy_not_measured():
    b = _bridge()
    cw = build_tile_crosswalk(b, nx=4, ny=4)
    claims = claims_from_power(cw, b)
    assert claims
    assert all(c.evidence_level == "measured_proxy" for c in claims)
    assert {c.problem for c in claims} >= {"ir_drop", "electromigration"}


def test_ledger_includes_power_claims():
    b = _bridge()
    cw = build_tile_crosswalk(b, nx=4, ny=4)
    ledger = build_waste_ledger(analyze_layout(b), b, power_crosswalk=cw)
    problems = {c.problem for c in ledger.claims}
    assert "ir_drop" in problems and "electromigration" in problems


# --- CLI ------------------------------------------------------------------

def test_cli_irdrop_and_emrisk_emit_json(capsys):
    agent_tools.main(["irdrop", "--nx", "4", "--ny", "4", "--top", "3"])
    out = json.loads(capsys.readouterr().out)
    assert out["tool"] == "irdrop" and "hotspots" in out

    agent_tools.main(["emrisk", "--top", "3"])
    out = json.loads(capsys.readouterr().out)
    assert out["tool"] == "emrisk" and out["em_nets"]
    assert out["em_nets"][0]["recommended"] in INTERCONNECT_METALS
