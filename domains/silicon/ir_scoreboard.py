# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Falsifiable test: does cheap STRUCTURE predict REAL IR-drop, spatially?

This is the power/reliability analogue of `scoreboard.py` (which targets SPEF cap) and
`sta.py` (timing). Timing-criticality is a weak target because the optimizer equalizes
slack (see `docs/SILICON_FINDINGS.md`). IR-drop is different: it is driven by *current
demand*, which is load, which optimization does NOT flatten — so structure should predict
*where the chip browns out*.

Ground truth: OpenROAD `analyze_power_grid -voltage_file` (per-instance supply voltage).
We bin the die into tiles and ask whether per-tile structural proxies (driven SPEF
capacitance, fanout, cell density, cell area) rank tiles like the real per-tile IR drop.
Honest pass/fail: Spearman >= +0.30 with a shuffled control < 0.20.

Evidence tier: the real IR map is `measured` EDA-workflow output (OpenROAD PDNSim).
fanout/density proxies are pure-structural (no extraction); cap uses SPEF (measured_proxy).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .netlist_bridge import NetlistBridge

PROXIES = ("cap", "fanout", "density", "area")
PASS_RHO = 0.30
CONTROL_MAX = 0.20


@dataclass
class IRScoreReport:
    design: str
    n_tiles: int
    grid: int
    supply_v: float
    worst_drop_v: float
    spearman: Dict[str, float] = field(default_factory=dict)
    prec_at_k: Dict[str, float] = field(default_factory=dict)
    control: Dict[str, float] = field(default_factory=dict)
    k: int = 10

    @property
    def best(self) -> Tuple[str, float]:
        if not self.spearman:
            return ("none", 0.0)
        return max(self.spearman.items(), key=lambda kv: kv[1])

    @property
    def passed(self) -> bool:
        name, rho = self.best
        return (self.n_tiles >= 20 and rho >= PASS_RHO
                and abs(self.control.get(name, 0.0)) < CONTROL_MAX)

    def render(self) -> str:
        name, rho = self.best
        head = "PASS" if self.passed else "FAIL"
        lines = [f"[{head}] IR-drop {self.design}  (tiles={self.n_tiles}, "
                 f"grid={self.grid}x{self.grid}, worst drop={self.worst_drop_v:.4f} V)",
                 f"   best predictor: {name}  spearman={rho:+.3f}",
                 f"   {'predictor':<12}{'spearman':>10}{'prec@k':>9}{'shuffle':>10}"]
        for p in PROXIES:
            lines.append(f"   {p:<12}{self.spearman.get(p,0.0):>+10.3f}"
                         f"{self.prec_at_k.get(p,0.0):>9.2f}{self.control.get(p,0.0):>+10.3f}")
        return "\n".join(lines)


def _spearman(a: List[float], b: List[float]) -> float:
    n = len(a)
    if n < 3:
        return 0.0
    ra = _ranks(a); rb = _ranks(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n))
    da = math.sqrt(sum((ra[i] - ma) ** 2 for i in range(n)))
    db = math.sqrt(sum((rb[i] - mb) ** 2 for i in range(n)))
    return num / (da * db) if da and db else 0.0


def _ranks(a: List[float]) -> List[int]:
    order = sorted(range(len(a)), key=lambda k: a[k])
    r = [0] * len(a)
    for i, idx in enumerate(order):
        r[idx] = i
    return r


def _prec_at_k(proxy: List[float], real: List[float], k: int) -> float:
    k = min(k, len(real))
    top_real = set(sorted(range(len(real)), key=lambda i: real[i], reverse=True)[:k])
    top_proxy = set(sorted(range(len(proxy)), key=lambda i: proxy[i], reverse=True)[:k])
    return len(top_real & top_proxy) / k if k else 0.0


def parse_ir_voltage(path: str, supply_v: float) -> Tuple[Dict[str, Tuple[float, float]],
                                                          Dict[str, float]]:
    """OpenROAD voltage_file -> {inst:(x,y)}, {inst: worst IR drop (V)}."""
    pos: Dict[str, Tuple[float, float]] = {}
    drop: Dict[str, float] = {}
    with open(path, encoding="utf-8", errors="ignore") as fh:
        next(fh, None)                       # header
        for line in fh:
            p = line.strip().split(",")
            if len(p) < 6:
                continue
            inst, x, y, v = p[0], float(p[3]), float(p[4]), float(p[5])
            pos[inst] = (x, y)
            drop[inst] = max(drop.get(inst, 0.0), supply_v - v)
    return pos, drop


def ir_scoreboard(def_path: str, spef_path: str, lef_path: str, voltage_path: str,
                  design: str = "design", supply_v: float = 1.1, grid: int = 20,
                  seed: int = 0) -> IRScoreReport:
    pos, drop = parse_ir_voltage(voltage_path, supply_v)

    bridge = NetlistBridge(def_path, spef_path, lef_path=lef_path)
    bridge.load()
    inst_cap: Dict[str, float] = {}
    inst_fanout: Dict[str, float] = {}
    active = set()
    for net in bridge.nets:
        if not bridge._is_signal(net):
            continue
        cap = bridge.caps.get(net.name, 0.0)
        drv = net.conns[bridge._driver_index(net)][0]
        inst_cap[drv] = inst_cap.get(drv, 0.0) + cap
        inst_fanout[drv] = inst_fanout.get(drv, 0.0) + (len(net.conns) - 1)
        active.add(drv)

    xs = [p[0] for p in pos.values()]; ys = [p[1] for p in pos.values()]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)

    def tile_of(x: float, y: float) -> Tuple[int, int]:
        ix = min(grid - 1, int((x - x0) / (x1 - x0 + 1e-9) * grid))
        iy = min(grid - 1, int((y - y0) / (y1 - y0 + 1e-9) * grid))
        return (ix, iy)

    tiles: Dict[Tuple[int, int], Dict[str, float]] = {}
    for inst, (x, y) in pos.items():
        d = tiles.setdefault(tile_of(x, y),
                             {"ir": 0.0, "n": 0, "cap": 0.0, "fanout": 0.0,
                              "area": 0.0, "density": 0.0})
        d["ir"] += drop.get(inst, 0.0); d["n"] += 1
        d["cap"] += inst_cap.get(inst, 0.0)
        d["fanout"] += inst_fanout.get(inst, 0.0)
        d["area"] += bridge.cell_area(inst)
        if inst in active:
            d["density"] += 1

    rows = [t for t in tiles.values() if t["n"]]
    real = [t["ir"] / t["n"] for t in rows]                 # mean IR drop per tile
    rep = IRScoreReport(design=design, n_tiles=len(rows), grid=grid, supply_v=supply_v,
                        worst_drop_v=max(drop.values()) if drop else 0.0)
    shuffled = list(real); random.Random(seed).shuffle(shuffled)
    for name in PROXIES:
        proxy = [t[name] for t in rows]
        rep.spearman[name] = _spearman(proxy, real)
        rep.prec_at_k[name] = _prec_at_k(proxy, real, rep.k)
        rep.control[name] = _spearman(proxy, shuffled)
    return rep


def main() -> None:
    import os
    print("KOMPOSOS-V | silicon IR-drop scoreboard")
    print("=" * 60)
    print("Q: does cheap structure predict REAL IR-drop (where the chip browns out)?\n")
    for d in ("aes", "ibex"):
        base = f"domains/silicon/data/orfs_{d}/results/nangate45/{d}/base"
        volt = f"domains/silicon/data/ir_{d}/ir_voltage.rpt"
        if not (os.path.exists(f"{base}/6_final.def") and os.path.exists(volt)):
            print(f"[skip] {d}: real artifacts absent (regenerate via sta_flows ORFS+IR)")
            continue
        rep = ir_scoreboard(f"{base}/6_final.def", f"{base}/6_final.spef",
                            "domains/silicon/data/openlane/Nangate45.lef", volt, design=d)
        print(rep.render()); print()


if __name__ == "__main__":
    main()
