# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Interconnect / barrier metal proposal bridge — the layout<->materials loop.

When the power analysis flags an electromigration (EM) risk net (high current density),
the question becomes a *materials* one: what metal carries that current without atoms
migrating into voids — and without spiking line resistance? This bridge proposes
candidate interconnect metals and ranks them on the real EM-vs-resistance tradeoff.

PROPOSAL side (this module): score candidates from cited metal properties.
VERIFICATION side: the recommended swap is gated by HonestyGate — its rationale must be
grounded in the committed metal-property facts (same vocabulary), never asserted.

Properties are bulk literature values (resistivity, EM activation energy Ea). Higher Ea
= exponentially better EM lifetime (Black's equation). This is screening-grade material
triage, not a foundry qualification.

Sources: resistivity — CRC Handbook; Ea(EM) — Hu/Rosenberg reviews, ITRS interconnect
roadmap (Cu ~0.8 eV grain-boundary; Co/Ru/W refractory ~1.5+ eV).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from core.category import Category


@dataclass(frozen=True)
class InterconnectMetal:
    name: str
    resistivity_uohm_cm: float     # bulk resistivity (lower = better conductor)
    em_activation_eV: float        # EM activation energy (higher = better EM lifetime)
    barrierless: bool              # can it be deposited without a separate diffusion barrier?
    role: str                      # "conductor" | "barrier"
    note: str = ""


# Bulk literature values (screening-grade).
INTERCONNECT_METALS: Dict[str, InterconnectMetal] = {
    "Cu":  InterconnectMetal("Cu", 1.68, 0.80, False, "conductor",
                             "Lowest resistivity; EM-prone, needs Ta/TaN barrier"),
    "Al":  InterconnectMetal("Al", 2.65, 0.60, True, "conductor",
                             "Legacy; most EM-prone of the conductors"),
    "W":   InterconnectMetal("W", 5.60, 1.60, True, "conductor",
                             "Refractory; local interconnect / vias; strong EM"),
    "Co":  InterconnectMetal("Co", 6.24, 1.50, True, "conductor",
                             "Scaled-node alternative; strong EM; thin liner"),
    "Ru":  InterconnectMetal("Ru", 7.10, 1.55, True, "conductor",
                             "Barrierless; excellent EM; good at scaled dimensions"),
    "TaN": InterconnectMetal("TaN", 220.0, 2.00, False, "barrier",
                             "Diffusion barrier for Cu; not a primary conductor"),
}

_RHO_MIN = min(m.resistivity_uohm_cm for m in INTERCONNECT_METALS.values()
               if m.role == "conductor")          # Cu sets the conductivity reference
_EA_REF = 2.0                                       # normalization ceiling for EM score


@dataclass
class MetalProposal:
    metal: str
    em_resistance: float       # 0..1 from Ea
    conductivity: float        # 0..1 from 1/resistivity (Cu = 1.0)
    score: float               # severity-weighted tradeoff
    rationale: str


def _norm(metal: InterconnectMetal) -> tuple[float, float]:
    em = max(0.0, min(1.0, metal.em_activation_eV / _EA_REF))
    cond = _RHO_MIN / metal.resistivity_uohm_cm
    return em, cond


def propose_interconnect(severity: float,
                         candidates: Optional[List[str]] = None) -> List[MetalProposal]:
    """Rank conductor metals for a net of EM `severity` in [0,1].

    severity weights EM resistance vs conductivity: a hot, high-current net (severity->1)
    favors EM-robust metals (Co/Ru/W); a benign net (severity->0) favors low resistance (Cu).
    """
    s = max(0.0, min(1.0, severity))
    names = candidates or [n for n, m in INTERCONNECT_METALS.items()
                           if m.role == "conductor"]
    out: List[MetalProposal] = []
    for name in names:
        m = INTERCONNECT_METALS.get(name)
        if m is None:
            continue
        em, cond = _norm(m)
        score = s * em + (1.0 - s) * cond
        rationale = (f"rho={m.resistivity_uohm_cm:.2f} uOhm-cm, Ea={m.em_activation_eV:.2f} eV"
                     + ("; barrierless" if m.barrierless else "; needs barrier"))
        out.append(MetalProposal(name, round(em, 3), round(cond, 3),
                                 round(score, 3), rationale))
    out.sort(key=lambda p: p.score, reverse=True)
    return out


@dataclass
class MetalRecommendation:
    net: str
    severity: float
    baseline: str
    recommended: str
    status: str                # AGREE | HOLLOW (proposal grounded in committed facts?)
    proposals: List[MetalProposal]
    reasons: List[str]


def recommend_interconnect(net: str, severity: float, baseline: str = "Cu",
                           min_grounding: float = 0.5) -> MetalRecommendation:
    """Propose a metal swap for an EM-risk net and gate it through HonestyGate.

    The recommendation persists only if its rationale is grounded in the committed
    metal-property facts (CLAUDE.md #4). Mirrors material_bridge.verdict_for_interface.
    """
    proposals = propose_interconnect(severity)
    reasons: List[str] = []
    top = proposals[0].metal if proposals else baseline

    if top == baseline:
        reasons.append(f"baseline {baseline} already optimal at severity {severity:.2f}")
        return MetalRecommendation(net, round(severity, 3), baseline, baseline,
                                   "AGREE", proposals, reasons)

    # Commit metal-property facts as evidence in the claim's vocabulary, then ground
    # the recommendation against them (the candidate edge itself is never added).
    cat = Category(name="interconnect_verdict", db_path=":memory:")
    for name in {top, baseline}:
        cat.add(name, type_name="metal")
    for name, m in INTERCONNECT_METALS.items():
        if name not in (top, baseline):
            continue
        cat.add(name, type_name="metal")
        cat.connect(name, name, name="em_activation_eV", confidence=round(_norm(m)[0], 3))
        cat.connect(name, name, name="conductivity", confidence=round(_norm(m)[1], 3))

    from core.honesty_gate import HonestyGate
    gate = HonestyGate(min_grounding=min_grounding)
    claim = (f"{top} replaces {baseline} on {net} em_activation_eV "
             f"{round(_norm(INTERCONNECT_METALS[top])[0], 2)}")
    hv = gate.check_claim(cat, top, baseline, "replaces", claim=claim)

    if hv.checked and not hv.honest:
        reasons.append(hv.reason)
        status = "HOLLOW"
    else:
        reasons.append(f"swap {baseline}->{top}: EM {proposals[0].em_resistance:.2f} "
                       f"vs cond {proposals[0].conductivity:.2f}"
                       + ("" if hv.checked else "; honesty unchecked (degraded open)"))
        status = "AGREE"
    return MetalRecommendation(net, round(severity, 3), baseline, top,
                               status, proposals, reasons)
