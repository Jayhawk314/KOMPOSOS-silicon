# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Rung 3 laws: the ledger tiers claims honestly and the agent CLI emits grounded JSON."""

import json

import pytest

from domains.silicon.netlist_bridge import (
    NetlistBridge, analyze_layout, SAMPLE_DEF, SAMPLE_SPEF,
)
from domains.silicon.material_bridge import (
    analyze_stack, PROBLEMATIC_GAN_GAAS, GAN_ALGAN_POWER,
)
from domains.silicon.waste_ledger import (
    build_waste_ledger, claims_from_stack, EVIDENCE_ORDER, PORTFOLIO_BUCKET,
)
from domains.silicon import agent_tools


@pytest.fixture
def ledger():
    b = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF)
    b.load()
    a = analyze_layout(b)
    stacks = [analyze_stack(PROBLEMATIC_GAN_GAAS), analyze_stack(GAN_ALGAN_POWER)]
    return build_waste_ledger(a, b, stacks)


# --- ledger laws ----------------------------------------------------------

def test_every_claim_has_a_valid_evidence_tier_and_provenance(ledger):
    assert ledger.claims
    for c in ledger.claims:
        assert c.evidence_level in EVIDENCE_ORDER
        assert c.source                      # provenance is never blank
        assert c.recommended_action


def test_spef_load_is_measured_proxy_geometry_is_structural(ledger):
    by_problem = {c.claim_id: c for c in ledger.claims}
    assert by_problem["load_n_bus"].evidence_level == "measured_proxy"
    assert by_problem["congestion_n_bus"].evidence_level == "structural_only"
    assert by_problem["chiplet_seam"].evidence_level == "structural_only"


def test_ranked_by_evidence_tier(ledger):
    ranked = ledger.ranked()
    tiers = [EVIDENCE_ORDER[c.evidence_level] for c in ranked]
    assert tiers == sorted(tiers, reverse=True)


def test_action_portfolio_buckets_match_tiers(ledger):
    portfolio = ledger.action_portfolio()
    for bucket, items in portfolio.items():
        for c in items:
            assert PORTFOLIO_BUCKET[c.evidence_level] == bucket


def test_unviable_stack_yields_defect_claim_viable_yields_none():
    assert claims_from_stack(analyze_stack(PROBLEMATIC_GAN_GAAS))      # GaAs/GaN unviable
    assert claims_from_stack(analyze_stack(GAN_ALGAN_POWER)) == []     # all viable


def test_ledger_exports_round_trip(tmp_path, ledger):
    p = tmp_path / "ledger.json"
    ledger.export_json(p)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["n_claims"] == len(ledger.claims)
    assert "action_portfolio" in data


# --- agent CLI laws (grounded JSON with summary + provenance) --------------

def _run(capsys, argv):
    agent_tools.main(argv)
    return json.loads(capsys.readouterr().out)

def test_cli_interface_rejects_gan_gaas(capsys):
    out = _run(capsys, ["interface", "GaN", "GaAs"])
    assert out["status"] == "REJECT" and out["persisted"] is False
    assert out["summary"] and out["provenance"]

def test_cli_seam_reports_cut_net(capsys):
    out = _run(capsys, ["seam"])
    assert out["cut_nets"] == ["n_bus"]
    assert "provenance" in out

def test_cli_whatif_isolating_bus_block_disconnects(capsys):
    out = _run(capsys, ["whatif", "--isolate", "u_b0"])
    assert out["found"] is True
    assert out["fiedler_after"] <= out["fiedler_before"]

def test_cli_ledger_has_portfolio(capsys):
    out = _run(capsys, ["ledger"])
    assert set(out["action_portfolio"]) == {
        "ready_for_scoping", "validate_proxy", "review_required"}
