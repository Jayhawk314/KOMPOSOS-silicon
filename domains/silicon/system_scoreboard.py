# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Track 2 (system/package interconnect): does structure find stress at the BLOCK level?

The post-Moore bet (Huawei UnifiedBus, chiplets, advanced packaging) moves value to the
*system interconnect* -- the links between blocks/dies. Our flow geometry (`partition.py`
Fiedler/spatial bisection + `flow_geometry.py` Ricci corridors) was built to find chiplet
boundaries and congestion. This scoreboard tests the system-level analogue of the Phase-1
IR-drop win, on a real design, against REAL measured IR-drop.

We partition a real layout into blocks (chiplet analogues), call the nets that cross block
boundaries the **system interconnect**, and ask two falsifiable questions:

  H1 (separation): do inter-block (system) nets sit in higher real IR-drop regions than
                   intra-block nets? -- i.e. is the system interconnect where stress
                   concentrates? Control: shuffle the inter/intra labels.
  H2 (ranking):    does a block's system-connectivity (count/load of inter-block nets)
                   predict that block's real IR-drop stress? Control: shuffle the target.

HONEST SCOPE: this is a WITHIN-DIE proxy for package interconnect (blocks ~ chiplets, cut
nets ~ package links), validated against real measured IR. True package validation needs a
real multi-die/chiplet layout (a data-acquisition task) -- see docs/SILICON_POSTMOORE_PLAN.md
Track 2. The IR ground truth is `measured`; the block partition is `structural_only`.
Spatial centrality is a known confound for H2 (central blocks both drop more and connect
more), so H2 is reported with that caveat; H1 is the cleaner claim.

Run:
    python -m domains.silicon.system_scoreboard
"""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .ir_scoreboard import parse_ir_voltage, _spearman
from .netlist_bridge import NetlistBridge
from .partition import partition_category


@dataclass
class SystemReport:
    design: str
    n_blocks: int
    n_inter: int
    n_intra: int
    inter_mean_drop: float
    intra_mean_drop: float
    sep_control: float                                   # shuffled-label inter/intra ratio
    block_spearman: Dict[str, float] = field(default_factory=dict)
    block_control: Dict[str, float] = field(default_factory=dict)

    @property
    def separation(self) -> float:
        return (self.inter_mean_drop / self.intra_mean_drop
                if self.intra_mean_drop else 0.0)

    @property
    def h1_passed(self) -> bool:
        # system nets are in higher-drop regions, and the label-shuffle control is ~1.0
        return (self.n_blocks >= 8 and self.separation >= 1.10
                and abs(self.sep_control - 1.0) < 0.05)

    def render(self) -> str:
        head = "PASS" if self.h1_passed else "FAIL"
        lines = [
            f"[{head}] system interconnect -- {self.design}  ({self.n_blocks} blocks)",
            f"   inter-block (system) nets: {self.n_inter}   intra-block: {self.n_intra}",
            f"   H1 mean real IR-drop: inter={self.inter_mean_drop*1e3:.2f} mV  "
            f"intra={self.intra_mean_drop*1e3:.2f} mV  "
            f"separation={self.separation:.3f}x  (shuffle control={self.sep_control:.3f}x)",
            f"   H2 block system-connectivity vs block IR stress (spatial-centrality caveat):",
        ]
        for feat in self.block_spearman:
            lines.append(f"     {feat:<16}{self.block_spearman[feat]:>+8.3f}"
                         f"   shuffle {self.block_control.get(feat, 0.0):>+7.3f}")
        return "\n".join(lines)


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def system_scoreboard(def_path: str, spef_path: str, lef_path: str, voltage_path: str,
                      design: str = "design", supply_v: float = 1.1,
                      block_max: int = 600, seed: int = 0) -> SystemReport:
    bridge = NetlistBridge(def_path, spef_path, lef_path=lef_path)
    bridge.load()
    pos, drop = parse_ir_voltage(voltage_path, supply_v)

    # blocks = chiplet analogues (spatial bisection on real placement).
    parts = partition_category(bridge.category, max_size=block_max, method="spatial")
    block_of: Dict[str, int] = {inst: p.index for p in parts for inst in p.nodes}

    # per-net: which blocks it touches, its instances' mean real IR drop, its demand.
    inter_drops: List[float] = []
    intra_drops: List[float] = []
    is_inter: List[int] = []
    net_drops: List[float] = []
    block_links: Dict[int, int] = {p.index: 0 for p in parts}
    block_load: Dict[int, float] = {p.index: 0.0 for p in parts}

    for net in bridge.signal_nets:
        insts = [inst for (inst, _pin) in net.conns]
        blocks = {block_of[i] for i in insts if i in block_of}
        if not blocks:
            continue
        d = [drop[i] for i in insts if i in drop]
        if not d:
            continue
        nd = _mean(d)
        inter = len(blocks) > 1
        net_drops.append(nd); is_inter.append(1 if inter else 0)
        (inter_drops if inter else intra_drops).append(nd)
        if inter:
            cap = bridge.caps.get(net.name, 0.0)
            demand = cap * (len(net.conns) - 1)
            for b in blocks:
                block_links[b] += 1
                block_load[b] += demand

    # H1 label-shuffle control: separation should vanish (~1.0) under random labels.
    rng = random.Random(seed)
    shuffled = is_inter[:]; rng.shuffle(shuffled)
    s_inter = [net_drops[i] for i in range(len(net_drops)) if shuffled[i]]
    s_intra = [net_drops[i] for i in range(len(net_drops)) if not shuffled[i]]
    sep_ctrl = (_mean(s_inter) / _mean(s_intra)) if _mean(s_intra) else 0.0

    rep = SystemReport(
        design=design, n_blocks=len(parts),
        n_inter=len(inter_drops), n_intra=len(intra_drops),
        inter_mean_drop=_mean(inter_drops), intra_mean_drop=_mean(intra_drops),
        sep_control=sep_ctrl)

    # H2: per-block system-connectivity vs real IR stress.
    block_drop: Dict[int, float] = {}
    for p in parts:
        d = [drop[i] for i in p.nodes if i in drop]
        if d:
            block_drop[p.index] = _mean(d)
    idxs = [p.index for p in parts if p.index in block_drop]
    if len(idxs) >= 3:
        target = [block_drop[b] for b in idxs]
        sh = target[:]; random.Random(seed + 1).shuffle(sh)
        for feat, src in (("system_links", block_links), ("system_load", block_load)):
            vals = [float(src[b]) for b in idxs]
            rep.block_spearman[feat] = _spearman(vals, target)
            rep.block_control[feat] = _spearman(vals, sh)
    return rep


def main() -> None:
    print("KOMPOSOS-V | silicon system-interconnect scoreboard (Track 2)")
    print("=" * 62)
    print("Q: is the system interconnect (inter-block nets) where stress concentrates,")
    print("   and does structure find it? Validated vs REAL measured IR-drop.\n")
    for d in ("aes", "ibex"):
        base = f"domains/silicon/data/orfs_{d}/results/nangate45/{d}/base"
        volt = f"domains/silicon/data/ir_{d}/ir_voltage.rpt"
        if not (os.path.exists(f"{base}/6_final.def") and os.path.exists(volt)):
            print(f"[skip] {d}: real artifacts absent")
            continue
        rep = system_scoreboard(f"{base}/6_final.def", f"{base}/6_final.spef",
                                "domains/silicon/data/openlane/Nangate45.lef", volt,
                                design=d)
        print(rep.render()); print()


if __name__ == "__main__":
    main()
