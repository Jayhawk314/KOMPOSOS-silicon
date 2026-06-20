# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Rung 2 — the netlist bridge: real chip layout -> a `Category`.

This is the one genuinely new piece (the materials side was Rung 1). It ingests the
files an RTL->GDSII flow (OpenLane/OpenROAD) actually emits:

  - DEF   : COMPONENTS (instances + placement) and NETS (connectivity).
  - SPEF  : per-net parasitic capacitance (the load / a measured proxy for congestion).

and turns them into the same kind of `Category` Rung 0 analyzed, so the shared
flow_geometry (Ricci congestion + Fiedler seam) runs on *real* silicon topology.

Honesty (CLAUDE.md #1, #8): the structural geometry (curvature, seam) is a PROPOSAL.
The SPEF capacitance is `measured_proxy` evidence (extracted by a tool), kept distinct
from the structural ranking. Nothing here simulates silicon — it reads tool output.

Connectivity model: each net is a star from its first listed pin (driver) to the rest
(sinks). Power/ground/clock and very-high-fanout nets are skipped by default — they
connect everything and would drown out signal-routing structure.

Built against a committed sample (`samples/tiny_core.def/.spef`) but written to the
LEF/DEF 5.8 and IEEE-1481 SPEF grammars, so real OpenLane output parses unchanged.

Run:
    python -m domains.silicon.netlist_bridge                      # uses the sample
    python -m domains.silicon.netlist_bridge path/to.def path/to.spef
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.bridge import Bridge
from core.category import Category
from core.types import Object, Morphism
from .flow_geometry import edge_curvatures, fiedler_seam

_SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "samples")
SAMPLE_DEF = os.path.join(_SAMPLE_DIR, "tiny_core.def")
SAMPLE_SPEF = os.path.join(_SAMPLE_DIR, "tiny_core.spef")

# Nets that aren't signal routing (skipped from the congestion graph by default).
_GLOBAL_NET_NAMES = {"vdd", "vss", "gnd", "vcc", "vpwr", "vgnd", "power", "ground"}
_GLOBAL_USE = ("POWER", "GROUND", "CLOCK")


# ═══════════════════════════════════════════════════════════════════════════
# 1. Parsers  (DEF connectivity + placement, SPEF capacitance)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Component:
    inst: str
    cell: str
    x: Optional[float] = None      # placement, DB units
    y: Optional[float] = None


@dataclass
class Net:
    name: str
    conns: List[Tuple[str, str]] = field(default_factory=list)  # (inst, pin)
    use: str = ""                  # SIGNAL | CLOCK | POWER | GROUND | ""


def _section(text: str, head: str) -> str:
    """Return the body between '<HEAD> ... ;' and 'END <HEAD>' (empty if absent)."""
    m = re.search(rf"\b{head}\b.*?;(.*?)\bEND\s+{head}\b", text, re.DOTALL)
    return m.group(1) if m else ""


def parse_def(text: str) -> Tuple[Dict[str, Component], List[Net], float]:
    """Parse DEF COMPONENTS + NETS. Returns (components, nets, dbu_per_micron)."""
    units = 1000.0
    um = re.search(r"UNITS\s+DISTANCE\s+MICRONS\s+(\d+)", text)
    if um:
        units = float(um.group(1))

    components: Dict[str, Component] = {}
    for entry in _section(text, "COMPONENTS").split(";"):
        toks = entry.split()
        if len(toks) < 3 or toks[0] != "-":
            continue
        inst, cell = toks[1], toks[2]
        x = y = None
        place = re.search(r"(?:PLACED|FIXED|COVER)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)", entry)
        if place:
            x, y = float(place.group(1)), float(place.group(2))
        components[inst] = Component(inst, cell, x, y)

    nets: List[Net] = []
    for entry in _section(text, "NETS").split(";"):
        s = entry.strip()
        if not s.startswith("-"):
            continue
        # net name is the first token after '-'
        body = s[1:].strip()
        name = body.split()[0] if body.split() else ""
        if not name:
            continue
        # connectivity '( inst pin )' groups appear BEFORE the first '+' attribute;
        # everything after '+' is routing/use and may contain coordinate parens.
        conn_part = body.split("+", 1)[0]
        conns = []
        for inst, pin in re.findall(r"\(\s*([^\s()]+)\s+([^\s()]+)\s*\)", conn_part):
            conns.append((inst, pin))
        use = ""
        um2 = re.search(r"\+\s*USE\s+(\w+)", body)
        if um2:
            use = um2.group(1).upper()
        nets.append(Net(name, conns, use))
    return components, nets, units


def parse_spef(text: str) -> Dict[str, float]:
    """Parse SPEF per-net total capacitance: '*D_NET <net> <total_cap>'.

    Honors a SPEF *NAME_MAP (real tools emit numeric ids: '*57 _000_' then
    '*D_NET *57 <cap>'); falls back to literal names (our sample) unchanged.
    """
    name_map = dict(re.findall(r"(?m)^\*(\d+)\s+(\S+)\s*$", text))
    caps: Dict[str, float] = {}
    for token, cap in re.findall(r"\*D_NET\s+(\S+)\s+([-\d.eE+]+)", text):
        net = token[1:] if token.startswith("*") else token
        net = name_map.get(net, net)          # resolve numeric id -> real net name
        try:
            caps[net] = float(cap)
        except ValueError:
            continue
    return caps


# ═══════════════════════════════════════════════════════════════════════════
# 2. The bridge
# ═══════════════════════════════════════════════════════════════════════════

class NetlistBridge(Bridge):
    """Load a DEF (+ optional SPEF) into a `Category` of blocks and wires."""

    def __init__(self, def_path: str, spef_path: Optional[str] = None,
                 name: str = "netlist", max_fanout: int = 32,
                 skip_globals: bool = True, **kw):
        super().__init__(name=name, **kw)
        with open(def_path, "r", encoding="utf-8", errors="ignore") as fh:
            self.components, self.nets, self.dbu = parse_def(fh.read())
        self.caps: Dict[str, float] = {}
        if spef_path and os.path.exists(spef_path):
            with open(spef_path, "r", encoding="utf-8", errors="ignore") as fh:
                self.caps = parse_spef(fh.read())
        self.max_fanout = max_fanout
        self.skip_globals = skip_globals
        self.signal_nets = [n for n in self.nets if self._is_signal(n)]

    def _is_signal(self, net: Net) -> bool:
        if len(net.conns) < 2:
            return False
        if self.skip_globals:
            if net.use in _GLOBAL_USE:
                return False
            if net.name.lower() in _GLOBAL_NET_NAMES:
                return False
        if len(net.conns) - 1 > self.max_fanout:   # fanout = sinks
            return False
        return True

    def _node(self, inst: str, pin: str) -> str:
        return f"PIN:{pin}" if inst.upper() == "PIN" else inst

    def get_objects(self) -> List[Object]:
        names = {self._node(i, p) for n in self.signal_nets for i, p in n.conns}
        objs = []
        for name in sorted(names):
            comp = self.components.get(name)
            meta = {"cell": comp.cell, "x": comp.x, "y": comp.y} if comp else {"io": True}
            objs.append(Object(name=name, type_name="block",
                               provenance="def", metadata=meta))
        return objs

    def get_morphisms(self) -> List[Morphism]:
        """Star model: driver (first pin) -> each sink, per signal net."""
        mors = []
        for net in self.signal_nets:
            driver = self._node(*net.conns[0])
            cap = self.caps.get(net.name)
            for inst, pin in net.conns[1:]:
                sink = self._node(inst, pin)
                if sink == driver:
                    continue
                mors.append(Morphism(
                    name="wire", source=driver, target=sink, confidence=1.0,
                    metadata={"net": net.name, "fanout": len(net.conns) - 1,
                              "cap_pf": cap, "wirelength": self._wirelen(driver, sink)}))
        return mors

    def _wirelen(self, a: str, b: str) -> Optional[float]:
        ca, cb = self.components.get(a), self.components.get(b)
        if not ca or not cb or None in (ca.x, ca.y, cb.x, cb.y):
            return None
        return round(math.hypot(ca.x - cb.x, ca.y - cb.y) / self.dbu, 3)  # microns

    def score_pair(self, source: str, target: str) -> Dict[str, float]:
        wl = self._wirelen(source, target)
        return {"wirelength_um": wl if wl is not None else 0.0}


# ═══════════════════════════════════════════════════════════════════════════
# 3. Analysis (shared geometry + SPEF-backed congestion evidence)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class LayoutAnalysis:
    corridors: List[Tuple[str, str, str, float]]   # (src, tgt, net, curvature)
    seam_value: float
    partition_a: List[str]
    partition_b: List[str]
    cut_nets: List[str]
    high_cap_nets: List[Tuple[str, float]]         # measured_proxy evidence (SPEF)


def analyze_layout(bridge: NetlistBridge) -> LayoutAnalysis:
    cat = bridge.category
    net_of = {frozenset((m.source, m.target)): m.metadata.get("net", "?")
              for m in cat.morphisms()}
    corridors = [(s, t, net_of.get(frozenset((s, t)), "?"), k)
                 for s, t, k in edge_curvatures(cat)]

    seam_value, part_a, part_b = fiedler_seam(cat)
    side = {n: "a" for n in part_a}
    side.update({n: "b" for n in part_b})
    cut_nets = sorted({m.metadata.get("net", "?") for m in cat.morphisms()
                       if side.get(m.source) != side.get(m.target)})

    high_cap = sorted(((n, c) for n, c in bridge.caps.items()
                       if any(net.name == n for net in bridge.signal_nets)),
                      key=lambda kv: -kv[1])
    return LayoutAnalysis(corridors, seam_value, part_a, part_b, cut_nets, high_cap)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Report
# ═══════════════════════════════════════════════════════════════════════════

def main(argv: Optional[List[str]] = None) -> None:
    import sys
    args = argv if argv is not None else sys.argv[1:]
    def_path = args[0] if len(args) >= 1 else SAMPLE_DEF
    spef_path = args[1] if len(args) >= 2 else (
        SAMPLE_SPEF if def_path == SAMPLE_DEF else None)

    bridge = NetlistBridge(def_path, spef_path)
    bridge.load()
    a = analyze_layout(bridge)

    print("KOMPOSOS-V | silicon Rung 2 - netlist bridge")
    print("=" * 60)
    print(f"source: {os.path.basename(def_path)}"
          + (f" + {os.path.basename(spef_path)}" if spef_path else " (no SPEF)"))
    print(f"blocks: {len(bridge.category.objects())}   "
          f"wires: {len(bridge.category.morphisms())}   "
          f"signal nets: {len(bridge.signal_nets)} "
          f"(of {len(bridge.nets)} total; power/clock skipped)")
    print()

    print("CONGESTION CORRIDORS  (Ollivier-Ricci; structural proposal)")
    for s, t, net, k in a.corridors[:4]:
        flag = "  <-- bottleneck" if (s, t, net, k) == a.corridors[0] else ""
        print(f"   kappa={k:+.3f}  {s:>5} -> {t:<5} [{net}]{flag}")
    print()

    print(f"CHIPLET SEAM  (Fiedler lambda_2 = {a.seam_value:.4f})")
    print(f"   partition A: {', '.join(a.partition_a)}")
    print(f"   partition B: {', '.join(a.partition_b)}")
    print(f"   cut nets   : {', '.join(a.cut_nets) or '(none)'}")
    print()

    if a.high_cap_nets:
        print("HIGHEST-LOAD NETS  (SPEF total cap; measured_proxy evidence)")
        for net, cap in a.high_cap_nets[:4]:
            print(f"   {cap:.4f} pF  [{net}]")
        print()

    print("Structural findings are proposals; SPEF caps are measured_proxy. "
          "No physics simulated.")


if __name__ == "__main__":
    main()
