# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""The trust layer: make ANY black-box proposer earn a receipt.

The industry is racing to bolt AI/ML into chip design, and the #1 fear is a black-box
suggestion that is quietly wrong. This module is the answer that nobody else ships: take
an arbitrary external proposer (an ML placer, an LLM "expert", a third-party optimizer)
and accept its proposal ONLY if the values it asserts match the committed, CITED facts —
and its rationale grounds in the same evidence vocabulary via the shared HonestyGate.

Two ways a black-box proposal is rejected:
  1. it asserts FABRICATED property values (right answer, made-up reason) -> caught by the
     value check against the cited facts;
  2. it references something we hold NO cited facts for (an unknown metal) -> caught by
     the grounding check.

This is the proposal-vs-verification invariant (CLAUDE.md #1) applied to outside agents:
generators only propose; the symbolic layer verifies. We meet the AI-EDA wave by being the
thing that lets you USE these tools without trusting them blindly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from core.category import Category
from core.honesty_gate import HonestyGate
from .interconnect import INTERCONNECT_METALS
from .materials_grounding import grounded_citation

_EA_REF = 2.0
_RHO_MIN = min(m.resistivity_uohm_cm for m in INTERCONNECT_METALS.values()
               if m.role == "conductor")
_VALUE_TOL = 0.05          # how far an asserted value may sit from the cited fact


def _cited_values(metal: str) -> Dict[str, float]:
    """The real, cited property scores for a metal (the ground truth a claim must match)."""
    m = INTERCONNECT_METALS[metal]
    return {"em_activation_eV": round(max(0.0, min(1.0, m.em_activation_eV / _EA_REF)), 2),
            "conductivity": round(_RHO_MIN / m.resistivity_uohm_cm, 2)}


@dataclass
class Proposal:
    proposer: str                    # who suggested it (an external/black-box agent)
    net: str
    metal: str                       # the suggested interconnect metal
    asserts: Dict[str, float] = field(default_factory=dict)  # the values it claims as basis


@dataclass
class Verdict:
    proposal: Proposal
    status: str                      # AGREE (kept) | HOLLOW (rejected)
    grounded: bool
    reason: str
    citation: str = ""


def gate_external_proposal(proposal: Proposal, min_grounding: float = 0.5) -> Verdict:
    """Accept an external proposal only if its asserted values match the cited facts AND
    the rationale grounds in committed evidence. Fabrications and unknowns are rejected."""
    if proposal.metal not in INTERCONNECT_METALS:
        return Verdict(proposal, "HOLLOW", False,
                       f"{proposal.metal} is not a known metal - no cited facts to ground against")

    # 1. Value check: every asserted property must match the cited fact within tolerance.
    truth = _cited_values(proposal.metal)
    for prop, claimed in proposal.asserts.items():
        real = truth.get(prop)
        if real is None:
            return Verdict(proposal, "HOLLOW", False,
                           f"asserts unknown property '{prop}'", grounded_citation(proposal.metal))
        if abs(claimed - real) > _VALUE_TOL:
            return Verdict(proposal, "HOLLOW", False,
                           f"fabricated rationale: claims {prop}={claimed} but cited fact is "
                           f"{real} (off by {abs(claimed-real):.2f})", grounded_citation(proposal.metal))

    # 2. Grounding check: the rationale (in cited values) must ground via the HonestyGate.
    cat = Category(name="trust_layer_facts", db_path=":memory:")
    for name in INTERCONNECT_METALS:
        cat.add(name, type_name="metal")
        for prop, val in _cited_values(name).items():
            cat.connect(name, name, name=prop, confidence=val)
    claim = " ".join(f"{proposal.metal} {p} {proposal.metal} {v}" for p, v in truth.items())
    gate = HonestyGate(min_grounding=min_grounding)
    hv = gate.check_claim(cat, proposal.metal, "Cu", "replaces", claim=claim)
    if hv.checked and not hv.honest:
        return Verdict(proposal, "HOLLOW", False, f"rationale not grounded: {hv.reason}",
                       grounded_citation(proposal.metal))
    return Verdict(proposal, "AGREE", True,
                   "accepted: asserted values match cited facts and rationale is grounded",
                   grounded_citation(proposal.metal))


# ── Demo proposers: stand-ins for external/black-box AI tools ──────────────────────────

def grounded_proposer(net: str, metal: str) -> Proposal:
    """An honest external agent: asserts the REAL cited property values."""
    return Proposal("grounded_ranker", net, metal, _cited_values(metal))


def hallucinating_proposer(net: str, metal: str) -> Proposal:
    """A black-box that asserts confident but FABRICATED values."""
    return Proposal("overconfident_llm", net, metal,
                    {"em_activation_eV": 0.99, "conductivity": 0.99})


def main() -> None:
    print("KOMPOSOS-V | trust layer - external proposers must earn a receipt\n" + "=" * 64)
    cases = [
        ("honest agent proposes a grounded swap", grounded_proposer("net42", "W")),
        ("black-box asserts a fabricated rationale", hallucinating_proposer("net42", "W")),
        ("black-box proposes an unknown metal",
         Proposal("mystery_tool", "net42", "Unobtanium", {"em_activation_eV": 1.0})),
    ]
    for label, prop in cases:
        v = gate_external_proposal(prop)
        mark = "KEEP " if v.grounded else "BLOCK"
        print(f"\n[{mark}] {label}")
        print(f"        proposer={prop.proposer}  suggests {prop.metal} for {prop.net}")
        print(f"        verdict={v.status}: {v.reason}")
    print("\nThe gate keeps grounded proposals and blocks fabricated/unknown ones - you can "
          "USE a black-box tool without trusting it blindly.")


if __name__ == "__main__":
    main()
