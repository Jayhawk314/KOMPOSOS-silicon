# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Falsifiable test: does cheap STRUCTURE predict real INTERCONNECT delay?

This is the Huawei-tau analogue of `scoreboard.py` (which targets SPEF capacitance) and
`ir_scoreboard.py` (which targets real IR-drop). Huawei's tau ("Tau") Scaling Law makes
signal-propagation *delay* the scaling axis, optimized at the wire/system level
(LogicFolding shortens critical-path wiring; UnifiedBus cuts interconnect latency).

We already falsified cheap structure predicting **gate-level timing slack** (the optimizer
equalizes slack -- see `docs/SILICON_FINDINGS.md`). But interconnect delay is a *different*
quantity: wire delay ~ R * C ~ resistance * (load * length). R and C are the same physical
family our IR/EM wins live in, NOT the optimizer-flattened slack family. So the honest
question is whether structure predicts the wire-delay term Huawei just declared central.

Target (this module): per-net **lumped Elmore RC** extracted from a DETAILED SPEF --
R from the `*RES` section, C from the `*D_NET` header. Both are extraction output, so the
target tier is `measured_proxy`. Predictors (fanout/wirelength/degree/curvature/area) are
computed WITHOUT extraction. A positive Spearman with a near-zero shuffle control means the
structural signal is real. (The `measured` upgrade is an STA `-fields {net}` net-delay
re-run; see `docs/SILICON_POSTMOORE_PLAN.md` Track 1.)

Run:
    python -m domains.silicon.tau_scoreboard
"""

from __future__ import annotations

import os
import re
from typing import Dict, Tuple

from .netlist_bridge import NetlistBridge
from .scoreboard import ScoreReport, collect_features, _score_features


def parse_spef_rc(text: str) -> Dict[str, Tuple[float, float]]:
    """Parse a DETAILED SPEF into {net: (R_total_ohm, C_total_pf)}.

    C is the `*D_NET <net> <total_cap>` header value; R is the sum of the per-segment
    resistances in the net's `*RES` section. Honors `*NAME_MAP` numeric ids exactly like
    `parse_spef`. Nets without a `*RES` section (reduced/lumped SPEF) get R = 0.
    """
    name_map = dict(re.findall(r"(?m)^\*(\d+)\s+(\S+)\s*$", text))
    out: Dict[str, Tuple[float, float]] = {}
    for block in text.split("*D_NET")[1:]:
        head = re.match(r"\s+(\S+)\s+([-\d.eE+]+)", block)
        if not head:
            continue
        token, cap_s = head.group(1), head.group(2)
        net = token[1:] if token.startswith("*") else token
        net = name_map.get(net, net)
        try:
            cap = float(cap_s)
        except ValueError:
            continue
        r_total = 0.0
        res = re.search(r"\*RES\b(.*?)(?:\*END|\Z)", block, re.S)
        if res:
            for line in res.group(1).splitlines():
                parts = line.split()
                if len(parts) >= 4:                # idx nodeA nodeB value
                    try:
                        r_total += float(parts[-1])
                    except ValueError:
                        pass
        out[net] = (r_total, cap)
    return out


def elmore_rc(rc: Dict[str, Tuple[float, float]]) -> Dict[str, float]:
    """Lumped interconnect-delay proxy R_total * C_total per net (scale-free for ranking)."""
    return {net: r * c for net, (r, c) in rc.items()}


def tau_scoreboard(def_path: str, spef_path: str, lef_path: str | None = None,
                   design: str | None = None, seed: int = 0) -> ScoreReport:
    """Score structural predictors against extracted per-net interconnect RC delay."""
    bridge = NetlistBridge(def_path, spef_path, lef_path=lef_path)
    bridge.load()
    with open(spef_path, encoding="utf-8", errors="ignore") as fh:
        delay = elmore_rc(parse_spef_rc(fh.read()))

    feats = [f for f in collect_features(bridge, require_cap=False) if f.net in delay]
    target = [delay[f.net] for f in feats]
    return _score_features(
        feats, target,
        design=design or os.path.basename(def_path),
        target="interconnect_rc_delay", seed=seed,
        source_kind="measured_proxy")


def main() -> None:
    print("KOMPOSOS-V | silicon tau (interconnect-delay) scoreboard")
    print("=" * 62)
    print("Q: does cheap structure predict real interconnect RC delay (Huawei tau)?\n")
    base = "domains/silicon/data/sta_45gcd"
    dp, sp = f"{base}/45_gcd.def", f"{base}/45_gcd.spef"
    lp = f"{base}/Nangate45.lef"
    if not (os.path.exists(dp) and os.path.exists(sp)):
        print(f"[skip] 45_gcd: detailed-SPEF artifacts absent under {base}/")
        print("       regenerate via domains/silicon/sta_flows (OpenROAD 45_gcd STA).")
        return
    rep = tau_scoreboard(dp, sp, lef_path=lp if os.path.exists(lp) else None,
                         design="45_gcd")
    print(rep.render())
    print()
    print("Predictors are SPEF-free; the target IS extracted R*C. A positive spearman")
    print("with a near-zero shuffle control = interconnect delay is structurally visible")
    print("(unlike gate slack, which the optimizer flattens).")


if __name__ == "__main__":
    main()
