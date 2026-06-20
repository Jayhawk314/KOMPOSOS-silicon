# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Rung 3 — the silicon waste ledger.

Mirrors KOMPOSOS-GRID/domains/grid/waste_ledger.py: one ledger of waste claims,
each tagged with an HONEST evidence tier and full provenance, so an engineer (or an
agent) reads computed findings instead of inventing numbers (CLAUDE.md #8).

Silicon waste classes (the grid analogues): routing congestion / IR-drop, extracted
parasitic load, chiplet-seam opportunity, and heterostructure interface defects.

Evidence tiers, lowest-to-highest:
    structural_only       geometry alone (curvature, Fiedler) — a proposal
    validated_hypothesis  rests on cited material physics (the 5 scorers + veto)
    measured_proxy        extracted by a tool (SPEF capacitance)
    measured              design-matched EDA result (STA); not fabricated-chip data

Claims are sourced from the netlist layout analysis (Rung 2) and material verdicts
(Rung 1); nothing here simulates silicon.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

EVIDENCE_ORDER = {
    "measured": 4,
    "measured_proxy": 3,
    "validated_hypothesis": 2,
    "structural_only": 1,
}

# The Gemini "Silicon Action Portfolio" buckets, keyed by evidence tier.
PORTFOLIO_BUCKET = {
    "measured": "ready_for_scoping",
    "measured_proxy": "ready_for_scoping",
    "validated_hypothesis": "validate_proxy",
    "structural_only": "review_required",
}


@dataclass(frozen=True)
class WasteClaim:
    claim_id: str
    problem: str                # ir_drop_congestion | chiplet_seam | interface_defect ...
    title: str
    location: str               # net / block / interface
    evidence_level: str
    estimate_kind: str
    quantity: float
    unit: str
    confidence: str = ""
    source: str = ""
    recommended_action: str = ""
    notes: str = ""

    def to_row(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id, "problem": self.problem, "title": self.title,
            "location": self.location, "evidence_level": self.evidence_level,
            "estimate_kind": self.estimate_kind, "quantity": self.quantity,
            "unit": self.unit, "confidence": self.confidence, "source": self.source,
            "recommended_action": self.recommended_action, "notes": self.notes,
        }


@dataclass
class WasteLedger:
    claims: List[WasteClaim]

    def ranked(self) -> List[WasteClaim]:
        return sorted(self.claims, key=lambda c: (
            EVIDENCE_ORDER.get(c.evidence_level, 0), c.quantity), reverse=True)

    def counts_by_evidence(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for c in self.claims:
            counts[c.evidence_level] = counts.get(c.evidence_level, 0) + 1
        return dict(sorted(counts.items()))

    def action_portfolio(self) -> Dict[str, List[WasteClaim]]:
        """Bucket claims by ROI-readiness (the silicon action portfolio)."""
        buckets: Dict[str, List[WasteClaim]] = {
            "ready_for_scoping": [], "validate_proxy": [], "review_required": []}
        for c in self.ranked():
            buckets[PORTFOLIO_BUCKET.get(c.evidence_level, "review_required")].append(c)
        return buckets

    def summary(self, top: int = 12) -> str:
        counts = ", ".join(f"{k}={v}" for k, v in self.counts_by_evidence().items())
        lines = [f"Silicon waste ledger: {len(self.claims)} claims ({counts})",
                 "  top claims:"]
        for c in self.ranked()[:top]:
            lines.append(f"    [{c.evidence_level}] {c.title} "
                         f"({c.location}): {c.quantity:,.3f} {c.unit}")
        return "\n".join(lines)

    def to_rows(self) -> List[Dict[str, Any]]:
        return [c.to_row() for c in self.ranked()]

    def to_dict(self) -> Dict[str, Any]:
        return {"n_claims": len(self.claims),
                "counts_by_evidence": self.counts_by_evidence(),
                "action_portfolio": {k: [c.claim_id for c in v]
                                     for k, v in self.action_portfolio().items()},
                "claims": self.to_rows()}

    def to_markdown(self) -> str:
        lines = ["# Silicon Waste Ledger", "",
                 f"- Claims: **{len(self.claims)}**",
                 f"- Evidence mix: **{self.counts_by_evidence()}**", "",
                 "| Evidence | Problem | Location | Claim | Quantity | Action |",
                 "|---|---|---|---|---:|---|"]
        for c in self.ranked():
            lines.append(f"| {c.evidence_level} | {c.problem} | {c.location} | "
                         f"{c.title} | {c.quantity:,.3f} {c.unit} | "
                         f"{c.recommended_action} |")
        return "\n".join(lines) + "\n"

    def export_json(self, path: str | Path) -> None:
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    def export_markdown(self, path: str | Path) -> None:
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_markdown(), encoding="utf-8")

    def export_csv(self, path: str | Path) -> None:
        rows = self.to_rows()
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [])
            w.writeheader(); w.writerows(rows)


# ═══════════════════════════════════════════════════════════════════════════
# Claim generators
# ═══════════════════════════════════════════════════════════════════════════

def claims_from_layout(analysis, bridge, top_corridors: int = 5) -> List[WasteClaim]:
    """Congestion corridors (structural), parasitic load (measured_proxy), seam."""
    claims: List[WasteClaim] = []

    seen_nets: set = set()
    for (s, t, net, k) in analysis.corridors:
        if k >= 0:
            continue                                  # only bottlenecks (kappa < 0)
        if net in seen_nets:                          # one claim per net (worst edge)
            continue
        seen_nets.add(net)
        if len(seen_nets) > top_corridors:
            break
        claims.append(WasteClaim(
            claim_id=f"congestion_{net}", problem="ir_drop_congestion",
            title=f"{s}->{t} routing congestion corridor [{net}]",
            location=net, evidence_level="structural_only",
            estimate_kind="negative_ricci_curvature",
            quantity=round(-k, 3), unit="kappa severity",
            confidence=f"Ollivier-Ricci kappa={k:+.3f}",
            source="netlist_bridge flow_geometry",
            recommended_action="Reroute through higher metal layer (M7/M8) to relieve RC delay.",
            notes="Structural proposal; attach STA slack or IR-drop sim to promote."))

    for net, cap in analysis.high_cap_nets[:top_corridors]:
        claims.append(WasteClaim(
            claim_id=f"load_{net}", problem="ir_drop_congestion",
            title=f"High parasitic load on [{net}]",
            location=net, evidence_level="measured_proxy",
            estimate_kind="extracted_capacitance",
            quantity=round(cap, 4), unit="pF total cap",
            confidence="SPEF parasitic extraction",
            source="netlist_bridge SPEF parse",
            recommended_action="Buffer/insert repeaters or widen wire; candidate for spreading.",
            notes="Measured proxy (tool-extracted), not a device measurement."))

    if analysis.cut_nets:
        claims.append(WasteClaim(
            claim_id="chiplet_seam", problem="chiplet_seam",
            title="Chiplet seam candidate (weak Fiedler coupling)",
            location=", ".join(analysis.cut_nets),
            evidence_level="structural_only", estimate_kind="fiedler_seam",
            quantity=round(analysis.seam_value, 4), unit="lambda2",
            confidence=f"partitions {len(analysis.partition_a)}|{len(analysis.partition_b)}",
            source="netlist_bridge flow_geometry (spectral)",
            recommended_action="Convert seam nets to a UCIe die-to-die interface.",
            notes="Lower lambda2 = cleaner cut."))
    return claims


def claims_from_stack(stack_analysis) -> List[WasteClaim]:
    """Heterostructure interface defects from a material stack analysis (Rung 1)."""
    claims: List[WasteClaim] = []
    for s in stack_analysis.interfaces:
        if s.viable:
            continue
        claims.append(WasteClaim(
            claim_id=f"interface_{s.sc_a}_{s.sc_b}".lower(),
            problem="interface_defect",
            title=f"{s.sc_a}/{s.sc_b} unviable heterostructure interface",
            location=f"{s.sc_a}/{s.sc_b}", evidence_level="validated_hypothesis",
            estimate_kind="interface_viability_composite",
            quantity=round(s.total, 3), unit="composite score",
            confidence=s.details.get("veto", f"lattice_match={s.lattice_match:.2f}"),
            source="material_bridge 5-scorer + lattice veto",
            recommended_action="Insert buffer/metamorphic layer or substitute material.",
            notes=f"In stack '{stack_analysis.name}'. Rests on cited material physics."))
    return claims


def claims_from_sta(sta_report) -> List[WasteClaim]:
    """Setup violations from a provenance-bearing, evidence-eligible STA report."""
    from .sta import violating_endpoints
    if not sta_report.is_evidence:
        return []

    claims: List[WasteClaim] = []
    source = (f"{sta_report.tool}; {sta_report.source_path}; "
              f"sha256={sta_report.sha256}")
    for endpoint, slack in violating_endpoints(sta_report.paths):
        claims.append(WasteClaim(
            claim_id=f"timing_{endpoint}".lower().replace("/", "_"),
            problem="timing_violation",
            title=f"Setup timing violation at {endpoint}",
            location=endpoint, evidence_level="measured",
            estimate_kind="sta_negative_slack",
            quantity=round(-slack, 4), unit="ns negative slack",
            confidence=sta_report.tool,
            source=source,
            recommended_action="Upsize/buffer the critical path or retime; re-run STA.",
            notes="Design-matched EDA timing evidence; not a fabricated-chip measurement."))
    return claims


def build_waste_ledger(layout_analysis=None, bridge=None,
                       stack_analyses: Optional[Iterable] = None,
                       sta_report=None) -> WasteLedger:
    claims: List[WasteClaim] = []
    if layout_analysis is not None and bridge is not None:
        claims.extend(claims_from_layout(layout_analysis, bridge))
    for sa in (stack_analyses or []):
        claims.extend(claims_from_stack(sa))
    if sta_report is not None:
        claims.extend(claims_from_sta(sta_report))
    return WasteLedger(claims=claims)


def main() -> None:
    from .netlist_bridge import NetlistBridge, analyze_layout, SAMPLE_DEF, SAMPLE_SPEF
    from .material_bridge import analyze_stack, PROBLEMATIC_GAN_GAAS, GAN_ALGAN_POWER

    bridge = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF)
    bridge.load()
    analysis = analyze_layout(bridge)
    stacks = [analyze_stack(PROBLEMATIC_GAN_GAAS), analyze_stack(GAN_ALGAN_POWER)]
    ledger = build_waste_ledger(analysis, bridge, stacks)

    print("KOMPOSOS-V | silicon Rung 3 - waste ledger")
    print("=" * 60)
    print(ledger.summary())
    print()
    print("ACTION PORTFOLIO (by engineering ROI readiness)")
    for bucket, items in ledger.action_portfolio().items():
        print(f"   {bucket:18} {len(items):2} claim(s): "
              f"{', '.join(c.claim_id for c in items) or '-'}")
    print()
    print("Every claim carries an evidence tier + provenance. "
          "structural_only/validated_hypothesis are proposals, not measured waste.")


if __name__ == "__main__":
    main()
