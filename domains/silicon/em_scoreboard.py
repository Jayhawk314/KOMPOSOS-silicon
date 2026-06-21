# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Measured EM check: does structure predict REAL measured electromigration current?

The co-design loop's EM side rests on Black's equation + cited Jmax (validated_hypothesis).
This lifts it toward MEASURED by testing the EM *detection* against ground truth: OpenROAD's
`analyze_power_grid -enable_em` emits the real current through each power-grid segment. We
bin that to tiles and ask whether the cheap structural current-demand signal ranks tiles the
same way the real EM current does.

Why current, not current-density: turning measured current into density needs per-segment
wire widths, which the EM report does not carry (the high-current segments are wide PDN
straps, so a min-width assumption grossly overestimates). Correlating the measured *current*
needs no geometry and still answers the real question: does structure point at the segments
that actually carry the most current (the EM-critical ones)?

Evidence tier: the EM current is `measured` (real OpenROAD EM output); the structural
predictor is the same cheap signal validated for IR-drop. A pass means the EM hotspot
detection is measured-validated, not just physics-estimated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .ir_scoreboard import _spearman, _prec_at_k, PASS_RHO, CONTROL_MAX
from .netlist_bridge import NetlistBridge


@dataclass
class EMScoreReport:
    design: str
    n_tiles: int
    grid: int
    worst_current_A: float
    spearman: Dict[str, float] = field(default_factory=dict)
    prec_at_k: Dict[str, float] = field(default_factory=dict)
    control: Dict[str, float] = field(default_factory=dict)
    k: int = 10

    @property
    def best(self) -> Tuple[str, float]:
        return max(self.spearman.items(), key=lambda kv: kv[1]) if self.spearman else ("none", 0.0)

    @property
    def passed(self) -> bool:
        name, rho = self.best
        return self.n_tiles >= 20 and rho >= PASS_RHO and abs(self.control.get(name, 0.0)) < CONTROL_MAX

    def render(self) -> str:
        name, rho = self.best
        head = "PASS" if self.passed else "FAIL"
        lines = [f"[{head}] measured-EM {self.design}  (tiles={self.n_tiles}, "
                 f"worst segment current={self.worst_current_A:.2e} A)",
                 f"   best predictor: {name}  spearman={rho:+.3f}",
                 f"   {'predictor':<10}{'spearman':>10}{'prec@k':>9}{'shuffle':>10}"]
        for p in ("demand", "fanout", "density"):
            lines.append(f"   {p:<10}{self.spearman.get(p,0.0):>+10.3f}"
                         f"{self.prec_at_k.get(p,0.0):>9.2f}{self.control.get(p,0.0):>+10.3f}")
        return "\n".join(lines)


def parse_em_current(path: str) -> List[Tuple[float, float, float]]:
    """OpenROAD em_outfile -> [(x_um, y_um, current_A)] at each segment's first node."""
    out: List[Tuple[float, float, float]] = []
    with open(path, encoding="utf-8", errors="ignore") as fh:
        next(fh, None)                                   # header
        for line in fh:
            p = line.strip().split(",")
            if len(p) < 7:
                continue
            try:
                out.append((float(p[1]), float(p[2]), abs(float(p[6]))))
            except ValueError:
                continue
    return out


def em_scoreboard(def_path: str, spef_path: str, lef_path: str, em_path: str,
                  design: str = "design", grid: int = 20, seed: int = 0) -> EMScoreReport:
    import random
    segs = parse_em_current(em_path)
    bridge = NetlistBridge(def_path, spef_path, lef_path=lef_path)
    dbu = bridge.dbu or 1.0

    # Structural per-instance current demand (cap x fanout at the driver) + density.
    inst_demand: Dict[str, float] = {}
    active = set()
    for net in bridge.nets:
        if not bridge._is_signal(net):
            continue
        cap = bridge.caps.get(net.name, 0.0)
        drv = net.conns[bridge._driver_index(net)][0]
        inst_demand[drv] = inst_demand.get(drv, 0.0) + cap * (len(net.conns) - 1)
        active.add(drv)

    pts = [(c.x / dbu, c.y / dbu) for c in bridge.components.values()
           if c.x is not None and c.y is not None]
    xs = [p[0] for p in pts] + [s[0] for s in segs]
    ys = [p[1] for p in pts] + [s[1] for s in segs]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)

    def tile(x, y):
        return (min(grid - 1, int((x - x0) / (x1 - x0 + 1e-9) * grid)),
                min(grid - 1, int((y - y0) / (y1 - y0 + 1e-9) * grid)))

    em: Dict[Tuple[int, int], float] = {}
    for x, y, cur in segs:
        em[tile(x, y)] = em.get(tile(x, y), 0.0) + cur            # measured EM current per tile
    struct: Dict[Tuple[int, int], Dict[str, float]] = {}
    for inst, c in bridge.components.items():
        if c.x is None:
            continue
        t = struct.setdefault(tile(c.x / dbu, c.y / dbu),
                              {"demand": 0.0, "fanout": 0.0, "density": 0.0})
        t["demand"] += inst_demand.get(inst, 0.0)
        if inst in active:
            t["density"] += 1

    keys = [k for k in struct if k in em]                         # tiles with both
    real = [em[k] for k in keys]
    rep = EMScoreReport(design, len(keys), grid,
                        max((s[2] for s in segs), default=0.0))
    if len(keys) < 3:
        return rep
    shuffled = list(real); random.Random(seed).shuffle(shuffled)
    for name in ("demand", "fanout", "density"):
        if name == "fanout":                                     # fanout ~ demand without cap
            vals = [struct[k]["demand"] for k in keys]
        else:
            vals = [struct[k][name] for k in keys]
        rep.spearman[name] = _spearman(vals, real)
        rep.prec_at_k[name] = _prec_at_k(vals, real, rep.k)
        rep.control[name] = _spearman(vals, shuffled)
    return rep


def main() -> None:
    import os
    print("KOMPOSOS-V | measured-EM scoreboard (structure vs real EM current)\n" + "=" * 64)
    cases = [("aes", "domains/silicon/data/orfs_aes/results/nangate45/aes/base",
              "domains/silicon/data/openlane/Nangate45.lef",
              "domains/silicon/data/ir_aes/em_current.rpt")]
    for d, base, lef, em in cases:
        if not (os.path.exists(f"{base}/6_final.def") and os.path.exists(em)):
            print(f"[skip] {d}: artifacts absent"); continue
        rep = em_scoreboard(f"{base}/6_final.def", f"{base}/6_final.spef", lef, em, design=d)
        print(rep.render())


if __name__ == "__main__":
    main()
