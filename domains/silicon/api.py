# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""The one stable entry point: point it at a real design, get a receipt-backed report.

A stranger should not have to wire bridges by hand or read 37 modules. This is the single
façade (whitepaper §7.2): give it a routed DEF (plus optional SPEF/LEF) and it returns a
typed `SiliconReport` with the two findings that are validated on real silicon —

  - TRIAGE: the nets most likely to be physically heavy, ranked by cheap structure
            (fan-out / wirelength). Validated against the tool's OWN measured net delay:
            orfs_gcd rho +0.845, 45_gcd +0.65 (see tau_scoreboard). `structural_only`
            proposals; the SPEF capacitance, when present, is `measured_proxy`.
  - SEAM:   the natural place to split the design into chiplets (Fiedler spectral cut) and
            what crosses it. `structural_only`.

Everything is a proposal with an evidence tier. Nothing here simulates physics; it screens
for the expensive tools.

Run:  python -m domains.silicon.api <design.def> [--spef f.spef] [--lef f.lef] [--top 10]
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

from .flow_geometry import fiedler_seam
from .netlist_bridge import NetlistBridge
from .scoreboard import collect_features


@dataclass
class RiskyNet:
    net: str
    fanout: float
    wirelength: float
    neg_curvature: float
    cap: Optional[float]          # SPEF total capacitance (measured_proxy) if SPEF given


@dataclass
class SiliconReport:
    design: str
    n_cells: int
    n_signal_nets: int
    has_spef: bool
    has_lef: bool
    top_risky_nets: List[RiskyNet] = field(default_factory=list)
    seam_value: float = 0.0                      # Fiedler algebraic connectivity (lower = easier cut)
    seam_sizes: Tuple[int, int] = (0, 0)
    seam_crossing_nets: List[str] = field(default_factory=list)
    evidence: Dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def render(self) -> str:
        cap_tag = "  cap(pF)" if self.has_spef else ""
        lines = [
            f"KOMPOSOS-V silicon report -- {self.design}",
            f"  {self.n_cells} cells, {self.n_signal_nets} signal nets"
            f"  (SPEF={'yes' if self.has_spef else 'no'}, LEF={'yes' if self.has_lef else 'no'})",
            "",
            f"TRIAGE -- nets most likely to be physically heavy ({self.evidence.get('triage','')})",
            f"  {'net':<22}{'fanout':>8}{'wirelen':>10}{'-curv':>8}{cap_tag}",
        ]
        for r in self.top_risky_nets:
            cap = f"  {r.cap:.4f}" if (self.has_spef and r.cap is not None) else ""
            lines.append(f"  {r.net:<22}{r.fanout:>8.0f}{r.wirelength:>10.1f}"
                         f"{r.neg_curvature:>8.3f}{cap}")
        lines += [
            "",
            f"SEAM -- natural chiplet split ({self.evidence.get('seam','')})",
            f"  algebraic connectivity = {self.seam_value:.4f}  "
            f"(partition {self.seam_sizes[0]} | {self.seam_sizes[1]} cells)",
            f"  {len(self.seam_crossing_nets)} nets cross the seam"
            + (f": {self.seam_crossing_nets[:6]}" if self.seam_crossing_nets else ""),
        ]
        return "\n".join(lines)


def analyze(def_path: str, spef_path: Optional[str] = None,
            lef_path: Optional[str] = None, top: int = 10) -> SiliconReport:
    """Load a real design and return the receipt-backed triage + seam report."""
    bridge = NetlistBridge(def_path, spef_path=spef_path, lef_path=lef_path)
    bridge.load()
    cat = bridge.category

    # TRIAGE: rank nets by the validated structural predictors (fanout, then wirelength).
    feats = collect_features(bridge, require_cap=False)
    feats.sort(key=lambda f: (f.fanout, f.wirelength), reverse=True)
    top_nets = [RiskyNet(net=f.net, fanout=f.fanout, wirelength=f.wirelength,
                         neg_curvature=f.neg_curvature, cap=f.cap) for f in feats[:top]]

    # SEAM: Fiedler spectral cut + the nets whose endpoints straddle it.
    seam_value, part_a, part_b = fiedler_seam(cat)
    side = {n: 0 for n in part_a}
    side.update({n: 1 for n in part_b})
    crossing = set()
    for m in cat.morphisms():
        sa, sb = side.get(m.source), side.get(m.target)
        if sa is not None and sb is not None and sa != sb:
            crossing.add(m.metadata.get("net", f"{m.source}->{m.target}"))

    return SiliconReport(
        design=os.path.basename(def_path),
        n_cells=len(bridge.components) if hasattr(bridge, "components") else len(side),
        n_signal_nets=len(bridge.signal_nets),
        has_spef=spef_path is not None and os.path.exists(spef_path),
        has_lef=lef_path is not None and os.path.exists(lef_path),
        top_risky_nets=top_nets,
        seam_value=float(seam_value),
        seam_sizes=(len(part_a), len(part_b)),
        seam_crossing_nets=sorted(crossing),
        evidence={
            "triage": "structural_only proposals; SPEF cap is measured_proxy"
                      if spef_path else "structural_only proposals",
            "seam": "structural_only",
        })


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(
        prog="python -m domains.silicon.api",
        description="Receipt-backed triage + chiplet-seam report for a routed design.")
    ap.add_argument("def_path", help="routed DEF file")
    ap.add_argument("--spef", help="SPEF parasitics (optional; enables measured_proxy cap)")
    ap.add_argument("--lef", help="LEF cell library (optional; fixes driver direction)")
    ap.add_argument("--top", type=int, default=10, help="how many risky nets to list")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    a = ap.parse_args(argv)
    rep = analyze(a.def_path, spef_path=a.spef, lef_path=a.lef, top=a.top)
    print(rep.to_json() if a.json else rep.render())


if __name__ == "__main__":
    main()
