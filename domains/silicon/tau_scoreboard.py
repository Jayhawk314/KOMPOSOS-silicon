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
from pathlib import Path
from typing import Dict, Optional, Tuple

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


def tau_scoreboard_measured(def_path: str, spef_path: str, lef_path: Optional[str],
                            sta_report: str, design: Optional[str] = None, seed: int = 0,
                            sta_source_kind: str = "unverified",
                            sta_context_paths: Optional[Dict[str, str]] = None
                            ) -> ScoreReport:
    """`measured`-tier tau test: structure vs the tool's own per-net interconnect delay.

    `sta_report` is an OpenSTA/OpenROAD `report_checks` run with `-fields {input_pins ...}`
    and loaded parasitics (see `sta_flows/tau_netdelay_sta.tcl`). Evidence eligibility and
    the receipt hash come from `load_sta`: it is `measured` only when attested `tool` with
    hashed netlist/liberty/constraints context -- a fixture can exercise this but never pass.
    """
    from .net_delay import net_wire_delays
    from .sta import load_sta

    bridge = NetlistBridge(def_path, spef_path, lef_path=lef_path)
    bridge.load()
    report = load_sta(sta_report, source_kind=sta_source_kind,
                      context_paths=sta_context_paths)
    text = Path(sta_report).read_text(encoding="utf-8", errors="ignore")
    delay = net_wire_delays(text, bridge)

    feats = [f for f in collect_features(bridge, require_cap=False) if f.net in delay]
    target = [delay[f.net] for f in feats]
    return _score_features(
        feats, target,
        design=design or os.path.basename(def_path),
        target="interconnect_net_delay", seed=seed,
        evidence_eligible=report.is_evidence,
        source_kind=report.source_kind, source_sha256=report.sha256)


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

    # measured-tier upgrade: structure vs the tool's own per-net interconnect delay.
    nd = f"{base}/45_gcd.netdelay.report_checks.txt"
    if os.path.exists(nd):
        print("\n--- measured tier (STA net delay) ---")
        mrep = tau_scoreboard_measured(
            dp, sp, lp if os.path.exists(lp) else None, nd, design="45_gcd",
            sta_source_kind="tool",
            sta_context_paths={"netlist": dp, "liberty": f"{base}/nangate45_typ.lib.gz",
                               "constraints": f"{base}/45_gcd.sdc"})
        print(mrep.render())
    else:
        print(f"\n[measured tier pending] run sta_flows/tau_netdelay_sta.tcl to produce")
        print(f"  {nd}  (Docker + OpenROAD; see sta_flows/README.md)")

    # second real design (self-minted orfs_gcd): measured tier on data we hold in full.
    o = "domains/silicon/data/orfs_gcd/results/base"
    ond = f"{o}/6_final.netdelay.report_checks.txt"
    if os.path.exists(ond):
        print("\n--- measured tier on orfs_gcd (second real design) ---")
        olef = "domains/silicon/data/openlane/Nangate45.lef"
        orep = tau_scoreboard_measured(
            f"{o}/6_final.def", f"{o}/6_final.spef",
            olef if os.path.exists(olef) else None, ond, design="orfs_gcd",
            sta_source_kind="tool",
            sta_context_paths={"netlist": f"{o}/6_final.v",
                               "liberty": "domains/silicon/data/early_gcd/NangateOpenCellLibrary_typical.lib",
                               "constraints": f"{o}/6_final.sdc"})
        print(orep.render())


if __name__ == "__main__":
    main()
