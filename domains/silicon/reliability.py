# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""The product: a receipt-backed reliability co-design report for a chip layout.

Point it at a real layout (DEF/SPEF/LEF) and get one honest answer:

  WHERE  : physical-stress hotspots (high current demand), structurally detected and
           VALIDATED against real OpenROAD IR-drop at Spearman ~0.5 (Phase 1-2).
  WHAT   : a grounded material/geometry action per hotspot net, with BOTH sides of the
           tradeoff proven (EM lifetime gain vs resistance cost), kept only if it nets
           out and passes the honesty gate (Phase 3-4).
  WHY YOU CAN TRUST IT : every claim carries an evidence tier and provenance. Nothing is
           asserted; a guess never poses as a verified fact. That receipt discipline is
           the differentiator - it is what caught our own timing idea over-claiming and
           certified the IR-drop win against measured ground truth.

This is the wedge incumbents leave open: they compute EM/IR; they do not connect that
stress to a grounded materials fix and prove it. We meet the market by speaking standard
OpenROAD/STA/IR evidence, and keep the outlier features (materials bridge + honesty
engine) in front.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .hotspot import predict_hotspots, HotspotReport
from .codesign_loop import codesign, CoDesignPortfolio

# The evidence ladder this product emits, strongest first.
EVIDENCE_LADDER = {
    "measured": "real tool output (OpenROAD IR-drop / STA), hashed design context",
    "measured_proxy": "tool-extracted parasitics (SPEF) - structural hotspot signal, "
                      "validated vs measured IR-drop at Spearman ~0.5",
    "validated_hypothesis": "cited material physics (Black's eq EM, resistivity) + real "
                            "layout geometry - screening-grade co-design actions",
    "literature_value": "cited bulk material properties (ASM/Smithells/Gall), "
                        "cross-validated; discrepancies flagged",
}


@dataclass
class ReliabilityReport:
    design: str
    hotspots: HotspotReport
    actions: CoDesignPortfolio
    tiers_used: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "design": self.design,
            "evidence_ladder": {t: EVIDENCE_LADDER[t] for t in self.tiers_used},
            "hotspots": self.hotspots.to_dict(),
            "actions": {"tier": self.actions.tier,
                        "fixes": [f.to_dict() for f in self.actions.fixes]},
        }

    def render(self) -> str:
        swaps = sum(f.action == "swap_interconnect" for f in self.actions.fixes)
        widens = sum(f.action == "widen_wire" for f in self.actions.fixes)
        rejects = sum(not f.keep for f in self.actions.fixes)
        lines = [
            f"RELIABILITY CO-DESIGN REPORT - {self.design}",
            "=" * 64,
            "WHERE (physical-stress hotspots; validated vs real IR-drop, ~0.5):",
        ]
        for i, t in enumerate(self.hotspots.tiles[:5], 1):
            net = t.top_nets[0][0] if t.top_nets else "-"
            lines.append(f"   {i}. tile ({t.ix},{t.iy})  demand={t.current_demand:.3f}  "
                         f"{t.density} cells  worst net {net}")
        lines.append("")
        lines.append(f"WHAT (proven co-design actions): {swaps} metal-swap, "
                     f"{widens} widen, {rejects} reject")
        for f in self.actions.fixes[:6]:
            verdict = {"swap_interconnect": "SWAP", "widen_wire": "WIDEN",
                       "none": "keep-as-is"}.get(f.action, "reject")
            lines.append(f"   [{verdict:>10}] {f.net:<12} {f.baseline}->{f.candidate}  "
                         f"EM x10^{f.em_mttf_gain_orders:.0f}  R x{f.resistance_penalty_x:.1f}"
                         f"  len={f.wirelength_um:.0f}um  gate={f.status}")
        lines.append("")
        lines.append("WHY YOU CAN TRUST IT (evidence ladder):")
        for t in self.tiers_used:
            lines.append(f"   - {t}: {EVIDENCE_LADDER[t]}")
        return "\n".join(lines)


def assess_reliability(def_path: str, spef_path: str, lef_path: str,
                       design: str = "design", top: int = 6) -> ReliabilityReport:
    """Run the full find -> fix -> prove pipeline and assemble the tiered report."""
    hotspots = predict_hotspots(def_path, spef_path, lef_path, design=design, top=top)
    actions = codesign(def_path, spef_path, lef_path, design=design, top=top)
    tiers = ["measured_proxy", "validated_hypothesis", "literature_value"]
    return ReliabilityReport(design, hotspots, actions, tiers)


def main() -> None:
    import os
    for d in ("aes", "ibex"):
        base = f"domains/silicon/data/orfs_{d}/results/nangate45/{d}/base"
        if not os.path.exists(f"{base}/6_final.def"):
            print(f"[skip] {d}: layout absent"); continue
        rep = assess_reliability(f"{base}/6_final.def", f"{base}/6_final.spef",
                                 "domains/silicon/data/openlane/Nangate45.lef", design=d)
        print("\n" + rep.render() + "\n")


if __name__ == "__main__":
    main()
