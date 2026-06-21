# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Track 2, real multi-die data: is 3D thermal coupling structurally visible?

The within-die partition proxy (`system_scoreboard.py`) was too weak: a synthetic cut is
not a real die boundary. Open3DBench gives REAL face-to-face 3D-IC designs (two stacked
dies, 10x10 tiles each) with committed per-tile POWER (HotSpot `.ptrace`) and per-tile
steady-state TEMPERATURE (HotSpot `.steady`). That is a genuine multi-die boundary with
measured-analogue thermal ground truth -- exactly what Track 2 needed.

The falsifiable, genuinely-3D question (a within-die view cannot ask it):

    Does a tile's temperature depend on the power of the tile STACKED ABOVE/BELOW it on
    the OTHER die -- i.e. is the die-to-die thermal coupling real and cheap to see?

We compare structural predictors of per-tile temperature:
  own              : the tile's own power (the 2D baseline)
  stacked          : the other-die tile's power at the same (row,col)
  own_plus_stacked : own + stacked   (the 3D-coupled demand)
  own_plus_neighbors, thermal_demand : add lateral heat spreading
If `own_plus_stacked` beats `own`, the 3D coupling is a real, structurally-visible effect.
Shuffle control must collapse. Temperature is real HotSpot output (Open3DBench), tier
`measured`; power is the structural/demand signal.

Data: clone Open3DBench under domains/silicon/data/open3dbench (gitignored). No multi-hour
run -- the thermal results are committed in OpenROAD-3D/flow/HotSpot/examples/3D_<design>/.

Run:
    python -m domains.silicon.thermal3d_scoreboard
"""

from __future__ import annotations

import os
import random
import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .ir_scoreboard import _spearman

_TILE = re.compile(r"^(upper|bottom)_(\d+)_(\d+)$")
_STEADY = re.compile(r"^layer_\d+_(upper|bottom)_(\d+)_(\d+)$")
PASS_RHO = 0.30
CONTROL_MAX = 0.20
PREDICTORS = ("own", "stacked", "own_plus_stacked", "own_plus_neighbors", "thermal_demand")


def parse_ptrace(path: str) -> Dict[str, float]:
    """HotSpot power trace: header row of block names, one row of per-block power."""
    with open(path, encoding="utf-8", errors="ignore") as fh:
        names = fh.readline().split()
        vals = fh.readline().split()
    out: Dict[str, float] = {}
    for n, v in zip(names, vals):
        try:
            out[n] = float(v)
        except ValueError:
            continue
    return out


def parse_steady_tiles(path: str) -> Dict[Tuple[str, int, int], float]:
    """HotSpot steady temps -> {(die,row,col): mean device-layer temperature (K)}."""
    acc: Dict[Tuple[str, int, int], List[float]] = {}
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) < 2:
                continue
            m = _STEADY.match(parts[0])
            if not m:
                continue
            try:
                t = float(parts[1])
            except ValueError:
                continue
            acc.setdefault((m.group(1), int(m.group(2)), int(m.group(3))), []).append(t)
    return {k: sum(v) / len(v) for k, v in acc.items()}


@dataclass
class Thermal3DReport:
    design: str
    n_tiles: int
    spearman: Dict[str, float] = field(default_factory=dict)
    control: Dict[str, float] = field(default_factory=dict)

    @property
    def coupling_gain(self) -> float:
        """How much the cross-die term adds over the 2D (own-power) baseline."""
        return self.spearman.get("own_plus_stacked", 0.0) - self.spearman.get("own", 0.0)

    @property
    def best(self) -> Tuple[str, float]:
        return max(self.spearman.items(), key=lambda kv: kv[1]) if self.spearman else ("none", 0.0)

    @property
    def passed(self) -> bool:
        name, rho = self.best
        return (self.n_tiles >= 20 and rho >= PASS_RHO
                and abs(self.control.get(name, 0.0)) < CONTROL_MAX)

    def render(self) -> str:
        head = "PASS" if self.passed else "FAIL"
        coup = ("3D-coupling HELPS" if self.coupling_gain > 0.01
                else "no 3D-coupling gain")
        lines = [f"[{head}] 3D thermal -- {self.design}  ({self.n_tiles} tiles, 2 dies)",
                 f"   {'predictor':<20}{'spearman':>10}{'shuffle':>10}"]
        for p in PREDICTORS:
            lines.append(f"   {p:<20}{self.spearman.get(p, 0.0):>+10.3f}"
                         f"{self.control.get(p, 0.0):>+10.3f}")
        lines.append(f"   own->temp {self.spearman.get('own',0.0):+.3f}  "
                     f"+stacked->temp {self.spearman.get('own_plus_stacked',0.0):+.3f}  "
                     f"(coupling gain {self.coupling_gain:+.3f}: {coup})")
        return "\n".join(lines)


def thermal3d_scoreboard(ptrace_path: str, steady_path: str,
                         design: str = "design", seed: int = 0) -> Thermal3DReport:
    power = {k: v for k, v in parse_ptrace(ptrace_path).items() if _TILE.match(k)}
    temp = parse_steady_tiles(steady_path)

    def tile(name: str) -> Tuple[str, int, int]:
        m = _TILE.match(name)
        return (m.group(1), int(m.group(2)), int(m.group(3)))

    def other(die: str) -> str:
        return "bottom" if die == "upper" else "upper"

    rows: List[Dict[str, float]] = []
    targets: List[float] = []
    for name, own in power.items():
        die, r, c = tile(name)
        if (die, r, c) not in temp:
            continue
        stacked = power.get(f"{other(die)}_{r}_{c}", 0.0)
        neigh = sum(power.get(f"{die}_{r+dr}_{c+dc}", 0.0)
                    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        rows.append({
            "own": own,
            "stacked": stacked,
            "own_plus_stacked": own + stacked,
            "own_plus_neighbors": own + 0.5 * neigh,
            "thermal_demand": own + stacked + 0.25 * neigh,
        })
        targets.append(temp[(die, r, c)])

    rep = Thermal3DReport(design=design, n_tiles=len(rows))
    if len(rows) < 20:
        return rep
    shuffled = list(targets); random.Random(seed).shuffle(shuffled)
    for p in PREDICTORS:
        vals = [row[p] for row in rows]
        rep.spearman[p] = _spearman(vals, targets)
        rep.control[p] = _spearman(vals, shuffled)
    return rep


_EX = ("domains/silicon/data/open3dbench/OpenROAD-3D/flow/HotSpot/examples")


def main() -> None:
    print("KOMPOSOS-V | silicon 3D thermal scoreboard (Track 2, real multi-die)")
    print("=" * 64)
    print("Q: on REAL stacked dies, does cheap structure predict tile temperature,")
    print("   and is the die-to-die thermal coupling structurally visible?\n")
    if not os.path.isdir(_EX):
        print(f"[skip] Open3DBench not cloned at {_EX}")
        print("       git clone https://github.com/lamda-bbo/Open3DBench"
              " domains/silicon/data/open3dbench")
        return
    designs = sorted(d for d in os.listdir(_EX) if d.startswith("3D_"))
    gains = []
    for d in designs:
        pt = f"{_EX}/{d}/test.ptrace"
        st = f"{_EX}/{d}/outputs/test.steady"
        if not (os.path.exists(pt) and os.path.exists(st)):
            continue
        rep = thermal3d_scoreboard(pt, st, design=d.replace("3D_", ""))
        print(rep.render()); print()
        gains.append(rep.coupling_gain)
    if gains:
        pos = sum(1 for g in gains if g > 0.01)
        print(f"3D-coupling gain positive on {pos}/{len(gains)} designs "
              f"(mean {sum(gains)/len(gains):+.3f}).")


if __name__ == "__main__":
    main()
