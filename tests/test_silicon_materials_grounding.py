# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Phase 3: interconnect metal properties grounded against cited reference data."""

from domains.silicon.materials_grounding import (
    ground_metal, ground_interconnect_table, ground_em_against_melting_point,
    grounded_citation, REFERENCE,
)
from domains.silicon.interconnect import recommend_interconnect, INTERCONNECT_METALS


def test_cu_al_cross_validate_against_citation():
    for name in ("Cu", "Al", "Co", "TaN"):
        g = ground_metal(name)
        assert g.grounded, g.note
        assert g.cited_resistivity is not None and g.citation


def test_grounding_catches_table_discrepancies():
    # W (5.60 thin-film vs 5.28 bulk) must be FLAGGED, not silently accepted.
    g = ground_metal("W")
    assert not g.grounded
    assert g.rel_error and g.rel_error > 0.05
    assert "bulk" in g.note or "below cited" in g.note


def test_every_interconnect_metal_has_a_grounding_row():
    rows = ground_interconnect_table()
    assert {r.metal for r in rows} == set(INTERCONNECT_METALS)


def test_em_robustness_grounded_in_melting_point():
    # The EM-activation ordering must match the independent melting-point ordering.
    em = ground_em_against_melting_point()
    assert em.concordant
    assert em.ordered_by_tm == em.ordered_by_ea       # perfectly concordant here


def test_recommendation_carries_cited_receipts():
    r = recommend_interconnect("hot_net", severity=0.9, baseline="Cu")
    assert r.recommended != "Cu"                      # a hot net should move off Cu
    assert r.evidence_tier == "literature_value"
    assert r.citations and any("Smithells" in c or "Gall" in c or "CRC" in c
                               for c in r.citations)


def test_grounded_citation_string():
    c = grounded_citation("Cu")
    assert "Cu" in c and "grounded" in c and REFERENCE["Cu"].source in c
