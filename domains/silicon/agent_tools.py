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
    python -m domains.silicon.agent_tools interface GaN AlGaN
    python -m domains.silicon.agent_tools stack GAN_ALGAN_POWER
    python -m domains.silicon.agent_tools whatif --isolate u_b0

Defaults to the committed sample (samples/tiny_core.def/.spef); pass --def/--spef
for real OpenLane output.
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
    "ledger": "Evidence-tiered waste ledger + action portfolio.",
    "interface": "Material interface verdict for A B (physics -> COG -> HonestyGate).",
    "stack": "Analyze a named heterostructure stack (weakest interface).",
    "whatif": "Recompute geometry with a block isolated; report the delta.",
}


def _emit(tool: str, summary: str, provenance: str, **data) -> None:
    print(json.dumps({"tool": tool, "summary": summary,
                      "provenance": provenance, **data}, indent=2))


def _bridge(args) -> NetlistBridge:
    b = NetlistBridge(args.def_path, args.spef_path)
    b.load()
    return b


def cmd_manifest(args) -> None:
    _emit("manifest", "KOMPOSOS-V silicon agent tools.",
          "domains/silicon", tools=MANIFEST,
          defaults={"def": SAMPLE_DEF, "spef": SAMPLE_SPEF})


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


def cmd_ledger(args) -> None:
    b = _bridge(args)
    a = analyze_layout(b)
    stacks = [analyze_stack(PROBLEMATIC_GAN_GAAS), analyze_stack(GAN_ALGAN_POWER)]
    ledger = build_waste_ledger(a, b, stacks)
    portfolio = {k: [c.claim_id for c in v]
                 for k, v in ledger.action_portfolio().items()}
    _emit("ledger",
          f"{len(ledger.claims)} claims; "
          f"{len(portfolio['ready_for_scoping'])} ready for scoping",
          f"{b.name} layout + material verdicts; tiers in waste_ledger.py",
          counts_by_evidence=ledger.counts_by_evidence(),
          action_portfolio=portfolio, claims=ledger.to_rows())


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
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("manifest").set_defaults(func=cmd_manifest)

    c = sub.add_parser("corridors"); c.add_argument("--top", type=int, default=5)
    c.set_defaults(func=cmd_corridors)

    sub.add_parser("seam").set_defaults(func=cmd_seam)
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
