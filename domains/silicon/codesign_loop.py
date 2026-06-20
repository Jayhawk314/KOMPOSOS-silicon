# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""The reliability co-design loop: find -> fix -> PROVE -> keep/reject.

This closes the materials x layout loop nobody else runs:

  1. FIND  : the hotspot detector flags high current-demand nets (Phase 1-2, validated
             against real OpenROAD IR-drop at Spearman ~0.5).
  2. FIX   : propose a grounded interconnect metal swap (Phase 3, cited receipts).
  3. PROVE : quantify BOTH sides of the real tradeoff from cited physics, not one:
               - EM lifetime gain via Black's equation, MTTF ~ exp(Ea / kT). A higher
                 activation-energy metal multiplies lifetime by exp((Ea_new-Ea_old)/kT).
               - Resistance/IR cost via cited resistivity: rho_new / rho_old.
             A swap that cures EM but triples resistance is only worth it on a SHORT,
             local net (bounded absolute R add) — which is exactly why industry uses
             W/Co/Ru for local interconnect and keeps Cu on long lines. The net's real
             wirelength (from layout) decides; long nets get `widen_wire` instead.
  4. KEEP  : persist the fix only if it nets out, gated by the same HonestyGate that
             grounds the recommendation. Reject => rolled back (not kept).

Evidence tier: `validated_hypothesis` — cited material physics + real layout geometry,
screening-grade. NOT a foundry EM qualification or a PDN sim.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

from .interconnect import INTERCONNECT_METALS, recommend_interconnect
from .materials_grounding import EVIDENCE_TIER as MAT_TIER, grounded_citation

_KB_eV_K = 8.617e-5          # Boltzmann constant, eV/K
_T_OP_K = 378.0             # 105 C operating/stress temperature (standard EM proxy)
EVIDENCE_TIER = "validated_hypothesis"


@dataclass
class ProvenFix:
    net: str
    baseline: str
    candidate: str
    wirelength_um: float
    is_local: bool
    em_mttf_gain_orders: float       # log10 of the EM lifetime multiplier (Black's eq)
    resistance_penalty_x: float      # rho_candidate / rho_baseline (>1 = worse)
    action: str                      # swap_interconnect | widen_wire | none
    keep: bool
    status: str                      # AGREE | HOLLOW (HonestyGate on the recommendation)
    reasons: List[str] = field(default_factory=list)
    citations: List[str] = field(default_factory=list)
    tier: str = EVIDENCE_TIER

    def to_dict(self) -> dict:
        return {"net": self.net, "baseline": self.baseline, "candidate": self.candidate,
                "wirelength_um": round(self.wirelength_um, 2), "is_local": self.is_local,
                "em_mttf_gain_orders": round(self.em_mttf_gain_orders, 1),
                "resistance_penalty_x": round(self.resistance_penalty_x, 2),
                "action": self.action, "keep": self.keep, "status": self.status,
                "tier": self.tier, "reasons": self.reasons, "citations": self.citations}


def _em_gain_orders(ea_base: float, ea_new: float) -> float:
    """log10 of the Black's-equation MTTF multiplier for raising activation energy."""
    return (ea_new - ea_base) / (_KB_eV_K * _T_OP_K) / math.log(10.0)


def prove_fix(net: str, wirelength_um: float, local_threshold_um: float,
              baseline: str = "Cu") -> ProvenFix:
    """Propose + PROVE a fix for one hotspot net, weighing EM gain vs resistance cost."""
    rec = recommend_interconnect(net, severity=1.0, baseline=baseline)
    cand = rec.recommended
    is_local = wirelength_um <= local_threshold_um
    reasons: List[str] = []

    if cand == baseline:
        reasons.append(f"{baseline} already optimal; no swap")
        return ProvenFix(net, baseline, baseline, wirelength_um, is_local, 0.0, 1.0,
                         "none", False, rec.status, reasons,
                         [grounded_citation(baseline)])

    ea_base = INTERCONNECT_METALS[baseline].em_activation_eV
    ea_new = INTERCONNECT_METALS[cand].em_activation_eV
    rho_base = INTERCONNECT_METALS[baseline].resistivity_uohm_cm
    rho_new = INTERCONNECT_METALS[cand].resistivity_uohm_cm
    em_orders = _em_gain_orders(ea_base, ea_new)
    r_penalty = rho_new / rho_base

    em_helps = em_orders > 0
    if em_helps and is_local:
        action, keep = "swap_interconnect", True
        reasons.append(f"swap {baseline}->{cand}: EM lifetime x10^{em_orders:.0f} "
                       f"(Black's eq, Ea {ea_base:.2f}->{ea_new:.2f} eV); resistance "
                       f"x{r_penalty:.1f} acceptable on a local net ({wirelength_um:.1f} um)")
    elif em_helps:
        action, keep = "widen_wire", True
        reasons.append(f"reject {baseline}->{cand} swap: resistance x{r_penalty:.1f} too "
                       f"costly on a {wirelength_um:.0f} um global net; widen cross-section "
                       f"instead (lowers EM current density AND resistance)")
    else:
        action, keep = "none", False
        reasons.append(f"no EM gain from {cand}; keep {baseline}")

    if rec.status == "HOLLOW":          # recommendation failed the honesty gate -> don't keep
        keep = False
        reasons.append("recommendation HOLLOW (not grounded) -> rolled back")

    return ProvenFix(net, baseline, cand, wirelength_um, is_local, em_orders, r_penalty,
                     action, keep, rec.status, reasons,
                     [grounded_citation(baseline), grounded_citation(cand)])


def _net_wirelength(bridge, net) -> float:
    """Total driver->sink wirelength of a net in microns (real layout geometry)."""
    if len(net.conns) < 2:
        return 0.0
    di = bridge._driver_index(net)
    driver = net.conns[di][0]
    dists = [bridge._wirelen(driver, sink)
             for i, (sink, _pin) in enumerate(net.conns) if i != di]
    return float(sum(d for d in dists if d is not None))


@dataclass
class CoDesignPortfolio:
    design: str
    fixes: List[ProvenFix]
    tier: str = EVIDENCE_TIER

    def render(self) -> str:
        swaps = sum(f.action == "swap_interconnect" for f in self.fixes)
        widens = sum(f.action == "widen_wire" for f in self.fixes)
        rejects = sum(not f.keep for f in self.fixes)
        lines = [f"reliability co-design portfolio: {self.design}  tier={self.tier}",
                 f"  {swaps} metal-swap, {widens} widen, {rejects} reject "
                 f"(of {len(self.fixes)} worst-current nets)"]
        for f in self.fixes:
            verdict = {"swap_interconnect": "SWAP", "widen_wire": "WIDEN",
                       "none": "reject"}.get(f.action, "reject")
            lines.append(f"  [{verdict:>6}] {f.net:<12} {f.baseline}->{f.candidate} "
                         f"EMx10^{f.em_mttf_gain_orders:>3.0f} R x{f.resistance_penalty_x:.1f} "
                         f"len={f.wirelength_um:>6.0f}um  gate={f.status}")
            lines.append(f"           {f.reasons[0]}")
        return "\n".join(lines)


def codesign(def_path: str, spef_path: str, lef_path: str,
             design: str = "design", top: int = 6) -> CoDesignPortfolio:
    """Run find->fix->prove on a real layout's worst current-demand nets."""
    from .netlist_bridge import NetlistBridge
    bridge = NetlistBridge(def_path, spef_path, lef_path=lef_path)
    bridge.load()

    demand = []
    for net in bridge.nets:
        if not bridge._is_signal(net):
            continue
        cap = bridge.caps.get(net.name, 0.0)
        demand.append((net, cap * (len(net.conns) - 1)))
    demand.sort(key=lambda kv: kv[1], reverse=True)

    # "local" threshold: median net wirelength across the design (real geometry).
    wls = sorted(_net_wirelength(bridge, n) for n, _ in demand) or [0.0]
    local_threshold = wls[len(wls) // 2]

    fixes = [prove_fix(net.name, _net_wirelength(bridge, net), local_threshold)
             for net, _d in demand[:top]]
    return CoDesignPortfolio(design, fixes)


def main() -> None:
    import os
    print("KOMPOSOS-V | reliability co-design loop (find -> fix -> prove)\n" + "=" * 64)
    for d in ("aes", "ibex"):
        base = f"domains/silicon/data/orfs_{d}/results/nangate45/{d}/base"
        if not os.path.exists(f"{base}/6_final.def"):
            print(f"[skip] {d}: layout absent"); continue
        p = codesign(f"{base}/6_final.def", f"{base}/6_final.spef",
                     "domains/silicon/data/openlane/Nangate45.lef", design=d)
        print("\n" + p.render())


if __name__ == "__main__":
    main()
