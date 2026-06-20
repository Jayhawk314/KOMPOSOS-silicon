# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Phase 6b: the trust layer gates external/black-box proposals against cited facts."""

from domains.silicon.trust_layer import (
    Proposal, gate_external_proposal, grounded_proposer, hallucinating_proposer,
)


def test_grounded_proposal_is_kept():
    v = gate_external_proposal(grounded_proposer("net1", "W"))
    assert v.status == "AGREE" and v.grounded
    assert v.citation


def test_fabricated_values_are_blocked():
    # A black-box that asserts confident but wrong numbers must be rejected.
    v = gate_external_proposal(hallucinating_proposer("net1", "W"))
    assert v.status == "HOLLOW" and not v.grounded
    assert "fabricated" in v.reason


def test_unknown_metal_is_blocked():
    v = gate_external_proposal(Proposal("x", "net1", "Unobtanium", {"em_activation_eV": 1.0}))
    assert v.status == "HOLLOW" and not v.grounded
    assert "not a known metal" in v.reason


def test_unknown_property_is_blocked():
    v = gate_external_proposal(Proposal("x", "net1", "W", {"made_up_prop": 0.5}))
    assert v.status == "HOLLOW" and not v.grounded


def test_grounded_and_hallucinated_for_each_conductor():
    for metal in ("Al", "Co", "Ru", "W"):
        assert gate_external_proposal(grounded_proposer("n", metal)).grounded
        assert not gate_external_proposal(hallucinating_proposer("n", metal)).grounded
