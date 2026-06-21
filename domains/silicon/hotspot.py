# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Unified physical-stress hotspot detector — the 'find the problems' front-end.

This predicts WHERE a chip will have power/current trouble (IR-drop, electromigration)
from the layout alone — no power simulation. It is the cheap detector justified by the
measured validation in `ir_scoreboard.py`: on real designs the per-tile current-demand
structure predicts OpenROAD's real IR-drop at Spearman ~0.45-0.60 (aes/ibex). So a
hotspot here is not a hollow guess — it carries the receipt of how well it predicts
reality.

It emits, per design: the worst stress tiles (ranked by current demand), the dominant
nets inside them (the electromigration-risk drivers), and an honest evidence tier. This
is the input to the reliability co-design loop (find -> fix -> prove).

Evidence tier: `measured_proxy` (driven SPEF capacitance is tool-extracted). The fanout
and density signals are pure-structural and need no extraction at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .netlist_bridge import NetlistBridge

# Measured validation receipt that every hotspot claim carries (see ir_scoreboard.py,
# em_scoreboard.py). Validated against TWO independent measured quantities at mature nodes.
VALIDATION = ("current-demand predicts real OpenROAD IR-drop (+0.47..+0.58) AND real "
              "measured EM current (+0.64) on 45nm aes/ibex; fanout/density need no "
              "extraction. Mature-node only (fails at 7nm: IR becomes PDN-resistance-bound)")
EVIDENCE_TIER = "measured_proxy"


@dataclass
class HotspotTile:
    ix: int
    iy: int
    x0_um: float
    y0_um: float
    x1_um: float
    y1_um: float
    current_demand: float            # sum of driven-net cap x fanout in the tile (proxy)
    density: int                     # active (current-drawing) cells in the tile
    top_nets: List[Tuple[str, float]] = field(default_factory=list)  # (net, demand)

    def to_dict(self) -> Dict[str, object]:
        return {"tile": [self.ix, self.iy],
                "bbox_um": [round(self.x0_um, 2), round(self.y0_um, 2),
                            round(self.x1_um, 2), round(self.y1_um, 2)],
                "current_demand": round(self.current_demand, 6),
                "density": self.density,
                "top_nets": [[n, round(d, 6)] for n, d in self.top_nets]}


@dataclass
class HotspotReport:
    design: str
    grid: int
    n_tiles: int
    tiles: List[HotspotTile]
    evidence_tier: str = EVIDENCE_TIER
    validation: str = VALIDATION

    def to_dict(self) -> Dict[str, object]:
        return {"design": self.design, "grid": self.grid, "n_tiles": self.n_tiles,
                "evidence_tier": self.evidence_tier, "validation": self.validation,
                "hotspots": [t.to_dict() for t in self.tiles]}

    def render(self) -> str:
        lines = [f"physical-stress hotspots: {self.design}  "
                 f"(grid {self.grid}x{self.grid}, {self.n_tiles} occupied tiles)",
                 f"  evidence: {self.evidence_tier} - {self.validation}",
                 f"  {'rank':>4} {'tile':>9} {'demand':>10} {'cells':>6}  worst net"]
        for i, t in enumerate(self.tiles, 1):
            net = t.top_nets[0][0] if t.top_nets else "-"
            lines.append(f"  {i:>4} {f'({t.ix},{t.iy})':>9} "
                         f"{t.current_demand:>10.4f} {t.density:>6}  {net}")
        return "\n".join(lines)


def predict_hotspots(def_path: str, spef_path: str, lef_path: str,
                     design: str = "design", grid: int = 20, top: int = 10,
                     nets_per_tile: int = 3) -> HotspotReport:
    """Rank stress tiles from the layout alone. No power simulation."""
    bridge = NetlistBridge(def_path, spef_path, lef_path=lef_path)
    dbu = bridge.dbu or 1.0

    # Per net: driver instance + a current-demand proxy (driven cap x fanout).
    net_demand: Dict[str, float] = {}
    net_driver: Dict[str, str] = {}
    for net in bridge.nets:
        if not bridge._is_signal(net):
            continue
        cap = bridge.caps.get(net.name, 0.0)
        fanout = len(net.conns) - 1
        net_demand[net.name] = cap * fanout
        net_driver[net.name] = net.conns[bridge._driver_index(net)][0]

    # Die bbox (microns) from placed instances.
    pts = [(c.x / dbu, c.y / dbu) for c in bridge.components.values()
           if c.x is not None and c.y is not None]
    if not pts:
        return HotspotReport(design, grid, 0, [])
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    wx, wy = (x1 - x0) or 1.0, (y1 - y0) or 1.0

    def tile_of(xu: float, yu: float) -> Tuple[int, int]:
        return (min(grid - 1, int((xu - x0) / (wx + 1e-9) * grid)),
                min(grid - 1, int((yu - y0) / (wy + 1e-9) * grid)))

    # Accumulate demand + density + contributing nets per tile (by the net's driver tile).
    tiles: Dict[Tuple[int, int], Dict] = {}
    for inst, comp in bridge.components.items():
        if comp.x is None or comp.y is None:
            continue
        t = tiles.setdefault(tile_of(comp.x / dbu, comp.y / dbu),
                             {"demand": 0.0, "density": 0, "nets": []})
        t["density"] += 1
    for net, demand in net_demand.items():
        comp = bridge.components.get(net_driver[net])
        if comp is None or comp.x is None:
            continue
        key = tile_of(comp.x / dbu, comp.y / dbu)
        t = tiles.setdefault(key, {"demand": 0.0, "density": 0, "nets": []})
        t["demand"] += demand
        t["nets"].append((net, demand))

    hot: List[HotspotTile] = []
    tw, th = wx / grid, wy / grid
    for (ix, iy), d in tiles.items():
        nets = sorted(d["nets"], key=lambda kv: kv[1], reverse=True)[:nets_per_tile]
        hot.append(HotspotTile(ix, iy, x0 + ix * tw, y0 + iy * th,
                               x0 + (ix + 1) * tw, y0 + (iy + 1) * th,
                               d["demand"], d["density"], nets))
    hot.sort(key=lambda t: t.current_demand, reverse=True)
    return HotspotReport(design, grid, len(tiles), hot[:top])


def main() -> None:
    import os
    print("KOMPOSOS-V | silicon physical-stress hotspot detector\n" + "=" * 60)
    for d in ("aes", "ibex", "gcd"):
        base = f"domains/silicon/data/orfs_{d}/results/nangate45/{d}/base"
        if not os.path.exists(f"{base}/6_final.def"):
            print(f"[skip] {d}: layout absent"); continue
        rep = predict_hotspots(f"{base}/6_final.def", f"{base}/6_final.spef",
                               "domains/silicon/data/openlane/Nangate45.lef", design=d, top=8)
        print("\n" + rep.render())


if __name__ == "__main__":
    main()
