# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
IR-drop / current-density evidence — a HONEST proxy, plus the EM->materials handoff.

There is no power-grid simulator on this laptop, so this never claims a measured voltage
drop. Instead it derives a current-DEMAND proxy from data we already trust:

  - per tile (gates->tiles aggregation): switching-capacitance demand ~ aggregated SPEF
    cap; high-demand tiles are IR-drop hotspot candidates (more current to deliver).
  - per net: a current-demand proxy ~ SPEF cap x fanout flags electromigration (EM) risk
    (more switched charge over the wire). High-EM nets are handed to the interconnect
    material bridge for a barrier/metal proposal.

Evidence tier: `measured_proxy` (the cap is tool-extracted by SPEF), NOT `measured`.
A real OpenROAD/Voltus PDN/IR report would be the `measured` upgrade (deferred, like a
real STA report). Nothing here simulates power.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .interconnect import recommend_interconnect, MetalRecommendation


# ═══════════════════════════════════════════════════════════════════════════
# 1. IR-drop hotspots (per tile)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class IRDropTile:
    tile: str
    x_index: int
    y_index: int
    current_demand_pf: float       # aggregated SPEF switching cap in the tile
    cell_area_um2: float           # leakage-current proxy
    gate_count: float


def ir_drop_hotspots(crosswalk) -> List[IRDropTile]:
    """Rank physical tiles by current-demand proxy (worst IR-drop risk first)."""
    tiles = [IRDropTile(t.tile, t.x_index, t.y_index,
                        round(t.spef_cap_pf, 5), round(t.cell_area_um2, 4),
                        t.gate_count)
             for t in crosswalk.tiles]
    tiles.sort(key=lambda t: (t.current_demand_pf, t.cell_area_um2), reverse=True)
    return tiles


# ═══════════════════════════════════════════════════════════════════════════
# 2. Electromigration-risk nets (per net) + material handoff
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class EMRiskNet:
    net: str
    cap_pf: float
    fanout: float
    wirelength_um: float
    current_demand: float          # cap * fanout (proxy)
    severity: float                # normalized 0..1 across nets
    recommendation: Optional[MetalRecommendation] = None


def em_risk_nets(bridge, top_recommend: int = 3) -> List[EMRiskNet]:
    """Per-net EM-risk proxy (cap x fanout); attach a metal proposal to the worst nets."""
    by_net = {}
    for m in bridge.category.morphisms():
        net = m.metadata.get("net", "?")
        rec = by_net.setdefault(net, {"cap": m.metadata.get("cap_pf"),
                                      "fanout": m.metadata.get("fanout", 0),
                                      "wl": 0.0})
        rec["wl"] = max(rec["wl"], float(m.metadata.get("wirelength") or 0.0))

    risks: List[EMRiskNet] = []
    for net, r in by_net.items():
        cap = r["cap"]
        if cap is None:
            continue
        demand = float(cap) * float(r["fanout"])
        risks.append(EMRiskNet(net, round(float(cap), 5), float(r["fanout"]),
                               round(r["wl"], 3), round(demand, 6), 0.0))
    if not risks:
        return risks

    worst = max(r.current_demand for r in risks) or 1.0
    for r in risks:
        r.severity = round(r.current_demand / worst, 3)
    risks.sort(key=lambda r: r.current_demand, reverse=True)

    for r in risks[:top_recommend]:
        r.recommendation = recommend_interconnect(r.net, r.severity)
    return risks


# ═══════════════════════════════════════════════════════════════════════════
# 3. Claims for the waste ledger
# ═══════════════════════════════════════════════════════════════════════════

def claims_from_power(crosswalk, bridge, top_tiles: int = 3, top_nets: int = 3):
    """IR-drop hotspot + EM-risk claims (measured_proxy: SPEF-extracted, not simulated)."""
    from .waste_ledger import WasteClaim
    claims: List[WasteClaim] = []

    for t in ir_drop_hotspots(crosswalk)[:top_tiles]:
        if t.current_demand_pf <= 0:
            continue
        claims.append(WasteClaim(
            claim_id=f"irdrop_{t.tile}", problem="ir_drop",
            title=f"IR-drop hotspot candidate at {t.tile}",
            location=t.tile, evidence_level="measured_proxy",
            estimate_kind="tile_switching_capacitance",
            quantity=t.current_demand_pf, unit="pF tile switching cap",
            confidence=f"{int(t.gate_count)} gates aggregated (gates->tiles Kan)",
            source="ir_drop tile current-demand proxy (SPEF)",
            recommended_action="Add PDN straps/decap near tile; confirm with PDN/IR sim.",
            notes="Demand proxy, NOT a simulated voltage drop."))

    for r in em_risk_nets(bridge, top_recommend=top_nets)[:top_nets]:
        if r.current_demand <= 0:
            continue
        metal = r.recommendation.recommended if r.recommendation else "Co/Ru"
        action = (f"High current density: consider {metal} interconnect "
                  f"(higher EM Ea than Cu) or widen wire.")
        claims.append(WasteClaim(
            claim_id=f"em_{r.net}", problem="electromigration",
            title=f"Electromigration-risk net [{r.net}]",
            location=r.net, evidence_level="measured_proxy",
            estimate_kind="current_demand_cap_x_fanout",
            quantity=r.current_demand, unit="pF*fanout demand",
            confidence=f"severity {r.severity:.2f}; fanout {int(r.fanout)}",
            source="ir_drop EM proxy + interconnect material bridge",
            recommended_action=action,
            notes="Material proposal is validated_hypothesis; current is a SPEF proxy."))
    return claims
