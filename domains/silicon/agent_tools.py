# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Rung 3 — grounded tool surface for a *local* coding agent (no online API/key).

Mirrors KOMPOSOS-GRID/domains/grid/agent_tools.py: point your own coding agent at
this CLI; it answers silicon questions by calling these tools and relaying what they
return. Every command emits JSON with a plain-English `summary` and a `provenance`
note, so the agent never invents a number — it reports computed results.

    python -m domains.silicon.agent_tools manifest
    python -m domains.silicon.agent_tools corridors --top 5
    python -m domains.silicon.agent_tools seam
    python -m domains.silicon.agent_tools ledger
    python -m domains.silicon.agent_tools --sta path/to/report.rpt sta
    python -m domains.silicon.agent_tools --sta path/to/report.rpt --sta-source tool \
        --sta-netlist netlist.v --sta-liberty cells.lib --sta-sdc constraints.sdc ledger
    python -m domains.silicon.agent_tools interface GaN AlGaN
    python -m domains.silicon.agent_tools stack GAN_ALGAN_POWER
    python -m domains.silicon.agent_tools whatif --isolate u_b0

Defaults to the committed sample (samples/tiny_core.def/.spef); pass
`--def`/`--spef`/`--lef` for real OpenLane output. STA has no default: a report must
be supplied explicitly, and the committed fixture is identified as non-evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, List, Optional

from core.category import Category
from core.types import Object
from .flow_geometry import edge_curvatures, fiedler_seam
from .netlist_bridge import NetlistBridge, analyze_layout, SAMPLE_DEF, SAMPLE_SPEF
from .material_bridge import (
    verdict_for_interface, analyze_stack,
    GAN_ALGAN_POWER, GAAS_ALGAAS_HEMT, INGAAS_INP_TELECOM, SI_SIGE_BICMOS,
    MOS2_WS2_2D, SIC_GAN_POWER, PROBLEMATIC_GAN_GAAS, PROBLEMATIC_GAAS_SI,
    PROBLEMATIC_INSB_SI,
)
from .waste_ledger import build_waste_ledger
from .sta import critical_nets, load_sta, violating_endpoints, worst_slack
from .scoreboard import score_layout, score_timing
from .net_operad import arity_histogram
from .verilog import build_crosswalk, load_verilog
from .coherence import analyze_crosswalk_cohomology

NAMED_STACKS = {
    "GAN_ALGAN_POWER": GAN_ALGAN_POWER, "GAAS_ALGAAS_HEMT": GAAS_ALGAAS_HEMT,
    "INGAAS_INP_TELECOM": INGAAS_INP_TELECOM, "SI_SIGE_BICMOS": SI_SIGE_BICMOS,
    "MOS2_WS2_2D": MOS2_WS2_2D, "SIC_GAN_POWER": SIC_GAN_POWER,
    "PROBLEMATIC_GAN_GAAS": PROBLEMATIC_GAN_GAAS,
    "PROBLEMATIC_GAAS_SI": PROBLEMATIC_GAAS_SI,
    "PROBLEMATIC_INSB_SI": PROBLEMATIC_INSB_SI,
}

MANIFEST = {
    "corridors": "Top routing-congestion corridors (Ollivier-Ricci; structural).",
    "seam": "Chiplet seam: Fiedler partition + cut nets (structural).",
    "sta": "STA paths, violations, and DEF-mapped critical nets with source hash.",
    "score": "Structural predictors vs SPEF or STA, with a shuffled control.",
    "operad": "N-ary net operations and graph-projection assumptions.",
    "crosswalk": "Gate-Verilog to DEF identity matches and mismatches.",
    "tiles": "Gates->tiles left Kan aggregation + tile-level SPEF telemetry score.",
    "irdrop": "IR-drop hotspot tiles (current-demand proxy; not a PDN sim).",
    "emrisk": "Electromigration-risk nets + interconnect metal proposal (gated).",
    "fixloop": "Self-learning: compose+verify fixes; learned remediations become primitives.",
    "cohomology": "Exact H0/H1 of justified cross-artifact calibrations.",
    "ledger": "Evidence-tiered waste ledger + action portfolio.",
    "interface": "Material interface verdict for A B (physics -> COG -> HonestyGate).",
    "stack": "Analyze a named heterostructure stack (weakest interface).",
    "whatif": "Recompute geometry with a block isolated; report the delta.",
}


def _emit(tool: str, summary: str, provenance: str, **data) -> None:
    print(json.dumps({"tool": tool, "summary": summary,
                      "provenance": provenance, **data}, indent=2))


def _bridge(args) -> NetlistBridge:
    b = NetlistBridge(args.def_path, args.spef_path, lef_path=args.lef_path)
    b.load()
    return b


def _sta_report(args):
    context = {
        "netlist": args.sta_netlist,
        "liberty": args.sta_liberty,
        "constraints": args.sta_sdc,
    }
    return (load_sta(args.sta_path, source_kind=args.sta_source,
                     context_paths=context, tool=args.sta_tool)
            if args.sta_path else None)


def cmd_manifest(args) -> None:
    _emit("manifest", "KOMPOSOS-V silicon agent tools.",
          "domains/silicon", tools=MANIFEST,
          defaults={"def": SAMPLE_DEF, "spef": SAMPLE_SPEF,
                    "lef": None, "sta": None, "sta_source": "unverified",
                    "sta_netlist": None, "sta_liberty": None, "sta_sdc": None})


def cmd_corridors(args) -> None:
    b = _bridge(args)
    a = analyze_layout(b)
    rows = [{"src": s, "tgt": t, "net": net, "curvature": round(k, 3)}
            for s, t, net, k in a.corridors[:args.top]]
    worst = rows[0] if rows else None
    summary = (f"Worst congestion corridor: {worst['net']} "
               f"(kappa={worst['curvature']})" if worst else "No corridors.")
    _emit("corridors", summary, f"{b.name}: Ollivier-Ricci on routing graph",
          corridors=rows)


def cmd_seam(args) -> None:
    b = _bridge(args)
    a = analyze_layout(b)
    _emit("seam",
          f"Fiedler lambda2={a.seam_value:.4f}; cut nets: "
          f"{', '.join(a.cut_nets) or '(none)'}",
          f"{b.name}: spectral partition of routing graph",
          fiedler_value=round(a.seam_value, 4),
          partition_a=a.partition_a, partition_b=a.partition_b,
          cut_nets=a.cut_nets)


def cmd_tiles(args) -> None:
    from .tiles import build_tile_crosswalk, score_tiles
    b = _bridge(args)
    cw = build_tile_crosswalk(b, nx=args.nx, ny=args.ny)
    sc = score_tiles(cw)
    name, rho = sc.best
    _emit("tiles",
          f"{len(cw.tiles)} occupied tiles ({args.nx}x{args.ny} grid); best tile-cap "
          f"predictor: {name} spearman={rho:.3f} (shuffle control {sc.control_rho:+.3f})",
          f"{b.name}: gates->tiles LeftKanExtension; additive aggregation of "
          f"cell area / fanout / wirelength / SPEF cap per physical tile",
          grid=[args.nx, args.ny], n_tiles=len(cw.tiles),
          skipped_unplaced=len(cw.skipped_unplaced),
          score=sc.to_dict(), tiles=cw.to_dict()["tiles"])


def cmd_irdrop(args) -> None:
    from .tiles import build_tile_crosswalk
    from .ir_drop import ir_drop_hotspots
    b = _bridge(args)
    cw = build_tile_crosswalk(b, nx=args.nx, ny=args.ny)
    tiles = ir_drop_hotspots(cw)
    worst = tiles[0] if tiles else None
    _emit("irdrop",
          (f"Top IR-drop hotspot {worst.tile}: {worst.current_demand_pf} pF switching "
           f"demand" if worst else "No placed tiles."),
          f"{b.name}: tile current-demand proxy (SPEF via gates->tiles Kan). "
          f"NOT a simulated PDN/IR voltage drop.",
          grid=[args.nx, args.ny],
          hotspots=[t.__dict__ for t in tiles[:args.top]])


def cmd_fixloop(args) -> None:
    from .fix_loop import run_fix_loop, verify_em_fix, FIX_PRIMITIVES
    history, loop = run_fix_loop()
    start = {p.name for p in FIX_PRIMITIVES}
    learned = [p.name for p in loop.primitives if p.name not in start]
    vf = verify_em_fix(_bridge(args))
    _emit("fixloop",
          f"Learned {len(learned)} reusable remediation(s): {', '.join(learned) or '-'}"
          + (f"; verified {vf.fix}->{vf.metal} on {vf.net} "
             f"(risk {vf.risk_before}->{vf.risk_after}, gate {vf.status})" if vf else ""),
          "core.generator GenerativeLoop over silicon fixes; verified composites "
          "become primitives (CLAUDE.md #5). Fix magnitudes are proxies, not a sim.",
          learned=learned,
          recipes={g: c.route for g, c in loop.built.items()},
          verified_fix=(vf.__dict__ if vf else None))


def cmd_emrisk(args) -> None:
    from .ir_drop import em_risk_nets
    b = _bridge(args)
    risks = em_risk_nets(b, top_recommend=args.top)
    rows = []
    for r in risks[:args.top]:
        rec = r.recommendation
        rows.append({
            "net": r.net, "current_demand": r.current_demand, "severity": r.severity,
            "fanout": r.fanout, "cap_pf": r.cap_pf,
            "recommended": rec.recommended if rec else None,
            "status": rec.status if rec else None,
            "proposals": [{"metal": p.metal, "score": p.score,
                           "em_resistance": p.em_resistance, "conductivity": p.conductivity}
                          for p in (rec.proposals[:3] if rec else [])]})
    worst = rows[0] if rows else None
    _emit("emrisk",
          (f"Worst EM-risk net {worst['net']} (severity {worst['severity']}) -> "
           f"recommend {worst['recommended']}" if worst else "No EM-risk nets."),
          f"{b.name}: EM current-demand proxy + interconnect material bridge "
          f"(HonestyGate-gated). Current is a SPEF proxy, not measured.",
          em_nets=rows)


def cmd_ledger(args) -> None:
    b = _bridge(args)
    a = analyze_layout(b)
    report = _sta_report(args)
    stacks = [analyze_stack(PROBLEMATIC_GAN_GAAS), analyze_stack(GAN_ALGAN_POWER)]
    ledger = build_waste_ledger(a, b, stacks, sta_report=report)
    portfolio = {k: [c.claim_id for c in v]
                 for k, v in ledger.action_portfolio().items()}
    _emit("ledger",
          f"{len(ledger.claims)} claims; "
          f"{len(portfolio['ready_for_scoping'])} ready for scoping",
          f"{b.name} layout + material verdicts"
          f"{f' + STA sha256={report.sha256}' if report else ''}; "
          "tiers in waste_ledger.py",
          counts_by_evidence=ledger.counts_by_evidence(),
          action_portfolio=portfolio, claims=ledger.to_rows(),
          sta_report=report.provenance() if report else None)


def cmd_sta(args) -> None:
    report = _sta_report(args)
    if report is None:
        _emit("sta", "No STA report supplied; pass --sta PATH before the command.",
              "No timing evidence loaded.", status="missing")
        return

    b = _bridge(args)
    violations = violating_endpoints(report.paths)
    critical = critical_nets(report.paths, b)
    critical_rows = [
        {"net": net, "negative_slack_ns": round(severity, 4)}
        for net, severity in sorted(critical.items(), key=lambda item: item[1], reverse=True)
    ]
    if report.source_kind == "fixture":
        qualifier = "fixture parsed; not evidence"
    elif report.source_kind == "unverified":
        qualifier = "source unverified; not evidence"
    elif not report.is_evidence:
        qualifier = ("tool source missing context receipts: " +
                     ", ".join(report.missing_context))
    else:
        qualifier = "tool report loaded as EDA evidence"
    _emit(
        "sta",
        f"{len(report.paths)} timing path(s), {len(violations)} violating endpoint(s); "
        f"{qualifier}.",
        f"{report.tool}; sha256={report.sha256}",
        status=("incomplete_provenance" if report.source_kind == "tool"
                and not report.is_evidence else
                report.source_kind if not report.is_evidence else "measured"),
        report=report.provenance(),
        worst_slack_ns=round(worst_slack(report.paths), 4),
        violating_endpoints=[{"endpoint": endpoint, "slack_ns": slack}
                             for endpoint, slack in violations],
        critical_nets=critical_rows,
    )


def cmd_score(args) -> None:
    if args.sta_path:
        report = score_timing(
            args.def_path, args.sta_path, spef_path=args.spef_path,
            lef_path=args.lef_path, sta_source_kind=args.sta_source,
            sta_context_paths={
                "netlist": args.sta_netlist,
                "liberty": args.sta_liberty,
                "constraints": args.sta_sdc,
            },
            sta_tool=args.sta_tool)
    else:
        report = score_layout(
            args.def_path, args.spef_path, lef_path=args.lef_path)

    name, rho = report.best
    status = ("NON-EVIDENCE" if not report.evidence_eligible
              else "PASS" if report.passed else "FAIL")
    _emit(
        "score",
        f"{status}: best {name} rho={rho:+.3f}; "
        f"shuffle={report.control_rho:+.3f} against {report.target}.",
        (f"scoreboard target={report.target}; source_kind={report.source_kind}; "
         f"DEF={args.def_path}; SPEF={args.spef_path}; LEF={args.lef_path}; "
         f"STA sha256={report.source_sha256 or '(none)'}"),
        report=report.to_dict(),
    )


def cmd_operad(args) -> None:
    bridge = _bridge(args)
    operations = sorted(
        bridge.net_operad.operations.values(),
        key=lambda operation: (-operation.arity, operation.name))
    fallbacks = sum(
        operation.data["projection_assumption"] == "def_order_fallback"
        for operation in operations)
    rows = [{
        "operation": operation.name,
        "net": operation.data["net"],
        "arity": operation.arity,
        "driver": operation.data["driver"],
        "projection_assumption": operation.data["projection_assumption"],
    } for operation in operations[:args.top]]
    _emit(
        "operad",
        f"{len(operations)} n-ary net operation(s); "
        f"{fallbacks} graph projection(s) use DEF-order fallback.",
        "categorical.operads.ColoredOperad; graph edges are explicit projections",
        colors=sorted(bridge.net_operad.colors),
        arity_histogram=arity_histogram(bridge.net_operad),
        fallback_projections=fallbacks,
        operations=rows,
    )


def cmd_crosswalk(args) -> None:
    if not args.verilog_path:
        _emit("crosswalk", "No gate Verilog supplied; pass --verilog PATH.",
              "No logical netlist loaded.", status="missing")
        return
    bridge = _bridge(args)
    crosswalk = build_crosswalk(load_verilog(args.verilog_path), bridge)
    data = crosswalk.to_dict()
    summary = (f"{data['matched_nets']} endpoint-identical net(s), "
               f"{data['renamed_nets']} renamed; "
               f"{len(crosswalk.logical_only)} logical-only and "
               f"{len(crosswalk.physical_only)} physical-only.")
    _emit("crosswalk", summary,
          f"gate Verilog={args.verilog_path}; DEF={args.def_path}", **data)


def cmd_cohomology(args) -> None:
    if not args.verilog_path:
        _emit("cohomology", "No gate Verilog supplied; pass --verilog PATH.",
              "No cross-artifact complex built.", status="missing")
        return
    bridge = _bridge(args)
    crosswalk = build_crosswalk(load_verilog(args.verilog_path), bridge)
    result = analyze_crosswalk_cohomology(crosswalk, bridge)
    status = "H1_OBSTRUCTION" if result.h1_dimension else (
        "DISCONNECTED" if result.h0_dimension > 1 else "COHERENT")
    _emit(
        "cohomology",
        f"{status}: H0={result.h0_dimension}, H1={result.h1_dimension}; "
        f"{sum(len(items) for items in result.coverage_findings.values())} "
        "coverage finding(s).",
        "explicit delta0/delta1 ranks; no inferred artifact calibration edges",
        status=status,
        **result.to_dict(),
    )


def cmd_interface(args) -> None:
    v = verdict_for_interface(args.a, args.b, context=args.context or None)
    _emit("interface",
          f"{args.a}/{args.b}: {v.status} (composite={v.composite}, "
          f"persist={v.persisted})",
          "material_bridge: 5-scorer -> physics gate -> COG -> HonestyGate",
          status=v.status, composite=v.composite, viable=v.viable,
          cog_status=v.cog_status, grounded=v.grounded,
          honesty_checked=v.honesty_checked, persisted=v.persisted,
          reasons=v.reasons)


def cmd_stack(args) -> None:
    stack = NAMED_STACKS.get(args.name)
    if stack is None:
        _emit("stack", f"Unknown stack '{args.name}'.", "material_bridge",
              available=sorted(NAMED_STACKS)); return
    a = analyze_stack(stack)
    w = a.weakest
    _emit("stack",
          f"{stack.name}: {'viable' if a.viable else 'UNVIABLE'}; "
          f"weakest {w.sc_a}->{w.sc_b} total={w.total:.2f}",
          "material_bridge.analyze_stack",
          viable=a.viable, layers=stack.layers,
          interfaces=[{"a": s.sc_a, "b": s.sc_b, "total": round(s.total, 3),
                       "viable": s.viable} for s in a.interfaces])


def cmd_whatif(args) -> None:
    """Isolate a block and report how connectivity (Fiedler) and the worst
    corridor change — the grounded counterfactual."""
    b = _bridge(args)
    base = analyze_layout(b)
    block = args.isolate

    # rebuild the routing graph without any wire touching `block`
    cat = Category(name="whatif", db_path=":memory:")
    kept_names = set()
    for m in b.category.morphisms():
        if block in (m.source, m.target):
            continue
        for n in (m.source, m.target):
            if n not in kept_names:
                cat.add(n, type_name="block"); kept_names.add(n)
        cat.connect(m.source, m.target, name="wire", confidence=1.0,
                    **{k: v for k, v in m.metadata.items() if k == "net"})

    new_fv, pa, pb = fiedler_seam(cat)
    new_corr = edge_curvatures(cat)
    worst = (f"{new_corr[0][0]}->{new_corr[0][1]} ({new_corr[0][2]:+.3f})"
             if new_corr else "(none)")
    present = any(block in (m.source, m.target) for m in b.category.morphisms())
    _emit("whatif",
          (f"Isolating {block}: Fiedler lambda2 {base.seam_value:.4f} -> "
           f"{new_fv:.4f}; worst corridor now {worst}."
           if present else f"Block '{block}' not found in routing graph."),
          f"{b.name}: recomputed flow geometry with {block} removed",
          isolate=block, found=present,
          fiedler_before=round(base.seam_value, 4), fiedler_after=round(new_fv, 4),
          blocks_remaining=len(kept_names))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="domains.silicon.agent_tools")
    p.add_argument("--def", dest="def_path", default=SAMPLE_DEF)
    p.add_argument("--spef", dest="spef_path", default=SAMPLE_SPEF)
    p.add_argument("--lef", dest="lef_path")
    p.add_argument("--sta", dest="sta_path")
    p.add_argument(
        "--sta-source", choices=("unverified", "tool"), default="unverified",
        help="attest a non-fixture STA artifact as tool output (default: unverified)")
    p.add_argument("--sta-tool", default="OpenSTA/OpenROAD report_checks")
    p.add_argument("--sta-netlist", help="gate netlist used by STA")
    p.add_argument("--sta-liberty", help="Liberty library used by STA")
    p.add_argument("--sta-sdc", help="timing constraints used by STA")
    p.add_argument("--verilog", dest="verilog_path", help="gate-level Verilog netlist")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("manifest").set_defaults(func=cmd_manifest)

    c = sub.add_parser("corridors"); c.add_argument("--top", type=int, default=5)
    c.set_defaults(func=cmd_corridors)

    sub.add_parser("seam").set_defaults(func=cmd_seam)
    sub.add_parser("sta").set_defaults(func=cmd_sta)
    sub.add_parser("score").set_defaults(func=cmd_score)
    o = sub.add_parser("operad"); o.add_argument("--top", type=int, default=10)
    o.set_defaults(func=cmd_operad)
    sub.add_parser("crosswalk").set_defaults(func=cmd_crosswalk)
    t = sub.add_parser("tiles")
    t.add_argument("--nx", type=int, default=8); t.add_argument("--ny", type=int, default=8)
    t.set_defaults(func=cmd_tiles)

    ir = sub.add_parser("irdrop")
    ir.add_argument("--nx", type=int, default=8); ir.add_argument("--ny", type=int, default=8)
    ir.add_argument("--top", type=int, default=5)
    ir.set_defaults(func=cmd_irdrop)

    em = sub.add_parser("emrisk"); em.add_argument("--top", type=int, default=5)
    em.set_defaults(func=cmd_emrisk)

    sub.add_parser("fixloop").set_defaults(func=cmd_fixloop)
    sub.add_parser("cohomology").set_defaults(func=cmd_cohomology)
    sub.add_parser("ledger").set_defaults(func=cmd_ledger)

    i = sub.add_parser("interface")
    i.add_argument("a"); i.add_argument("b")
    i.add_argument("--context", nargs="*", default=["GaAs", "Si", "AlGaN"])
    i.set_defaults(func=cmd_interface)

    s = sub.add_parser("stack"); s.add_argument("name")
    s.set_defaults(func=cmd_stack)

    w = sub.add_parser("whatif"); w.add_argument("--isolate", required=True)
    w.set_defaults(func=cmd_whatif)
    return p


def main(argv: Optional[List[str]] = None) -> None:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    args.func(args)


if __name__ == "__main__":
    main()
