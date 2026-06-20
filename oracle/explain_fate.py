#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
explain(perturbation, fate) -- a DISCIPLINED mechanism interpreter, not a predictor.

The cell-fate net-balance model is a validated apoptosis-*direction* interpreter
(8/8 control) but not an essentiality *predictor* (AUROC 0.36). This wraps it as an
honest explainer: given a perturbation, it returns the dominant signed cascade that
produces the fate -- WITH three honesty mechanisms so it explains rather than
rationalizes:

  1. ABSTENTION GATE   -- refuses ("I can't explain this") when the effect is
     negligible, the requested direction disagrees, or no coherent path exists.
  2. ABLATION CHECK    -- names the load-bearing mediator and *proves* it by
     deleting it and showing the effect collapses. If deleting the named mediator
     barely changes the outcome, the explanation is flagged non-faithful (redundant
     routes -> the story isn't doing the work).
  3. DOMINANCE CHECK   -- is the effect carried by a few strong paths or smeared
     across many weak ones? A diffuse explanation is flagged low-confidence.

This is interpretation, validated by faithfulness/coherence -- NOT prediction.

Run:  python -m oracle.explain_fate
"""

from __future__ import annotations

from typing import Dict, List, Optional

from oracle.cell_fate_netbalance import (
    load_signed_graph, propagate, death_drive, PRO_DEATH, PRO_SURVIVAL,
)

BEAM = 400


def build_topology_roles(out_edges, nodes, bet_samples=250) -> Dict[str, str]:
    """Precompute a compact structural-role tag per node (interpretive annotation).

    Tags: bottleneck (top-5% betweenness), hub (top-5% degree), feedback-loop (in a
    cyclic SCC), single-point-of-failure (articulation point), deep-core(k). These
    enrich an explanation -- 'the load-bearing mediator is also the network bottleneck'.
    """
    from oracle.topology_toolkit import Topology
    topo = Topology(nodes, {u: [(v, 1.0) for v, _ in es] for u, es in out_edges.items()})
    deg = topo.degree()
    bet = topo.betweenness(samples=bet_samples)
    loops = topo.short_cycles(max_len=3)        # tightened: tight 2/3-cycles only
    cutv = topo.cut_vertices(min_chunk=5)       # tightened: orphans a real chunk
    core = topo.kcore()

    def thresh(d, p=0.95):
        vals = sorted(v for v in d.values() if v > 0)
        return vals[int(p * (len(vals) - 1))] if vals else float("inf")

    bet_hi, deg_hi = thresh(bet), thresh(deg)
    maxcore = max(core.values()) if core else 0
    roles = {}
    for n in nodes:
        tags = []
        if bet.get(n, 0) >= bet_hi:
            tags.append("bottleneck")
        if deg.get(n, 0) >= deg_hi:
            tags.append("hub")
        if n in loops:
            tags.append("tight-feedback-loop")
        if n in cutv:
            tags.append(f"single-point-of-failure(cuts~{cutv[n]})")
        if maxcore and core.get(n, 0) >= 0.8 * maxcore:
            tags.append(f"deep-core({core[n]})")
        roles[n] = " | ".join(tags) if tags else "peripheral"
    return roles


def _dominant_path(out_edges, source, sigma, target, K, decay) -> Optional[tuple]:
    """Strongest simple signed path source->target (consistent with propagate)."""
    outdeg = {u: len(es) for u, es in out_edges.items()}
    sign_of = {(u, v): sg for u, es in out_edges.items() for (v, sg) in es}
    beam = [(source, (source,), float(sigma))]
    best = None
    for _ in range(K):
        nxt = []
        for node, path, w in beam:
            od = outdeg.get(node, 0)
            if not od:
                continue
            for (v, sg) in out_edges[node]:
                if v in path:
                    continue
                nw = w * sg / od * decay
                np = path + (v,)
                nxt.append((v, np, nw))
                if v == target and (best is None or abs(nw) > abs(best[2])):
                    best = (v, np, nw)
        nxt.sort(key=lambda x: abs(x[2]), reverse=True)
        beam = nxt[:BEAM]
    return best


def _path_str(path, out_edges) -> str:
    sign_of = {(u, v): sg for u, es in out_edges.items() for (v, sg) in es}
    parts = [path[0]]
    for a, b in zip(path, path[1:]):
        parts.append("--|" if sign_of.get((a, b)) == -1 else "-->")
        parts.append(b)
    return " ".join(parts)


def explain(out_edges, nodes, source: str, sigma: int,
            expected_fate: Optional[str] = None,
            roles: Optional[Dict[str, str]] = None,
            K: int = 4, decay: float = 0.5,
            min_effect: float = 5e-4, dominance_min: float = 0.25,
            faithful_min: float = 0.30) -> Dict:
    """Explain the fate effect of perturbing `source` by `sigma` (+1 activate / -1 inhibit)."""
    pd_ = PRO_DEATH & nodes
    ps_ = PRO_SURVIVAL & nodes

    if source not in nodes:
        return {"verdict": "ABSTAIN", "reason": f"{source} not in network"}

    total = propagate(out_edges, source, sigma, K, decay)
    dd = death_drive(total, pd_, ps_)
    direction = "death" if dd > 0 else "survival"

    # Gate 1a: negligible effect.
    if abs(dd) < min_effect:
        return {"verdict": "ABSTAIN", "reason": "effect below threshold",
                "death_drive": round(dd, 5)}

    # Gate 1b: requested direction disagrees.
    if expected_fate and expected_fate != direction:
        return {"verdict": "ABSTAIN", "reason":
                f"model direction is '{direction}', not requested '{expected_fate}' "
                "-- outside the explainable regime", "death_drive": round(dd, 5)}

    # Per-readout contribution toward the observed direction.
    contrib = {}
    for r in pd_:
        contrib[r] = total.get(r, 0.0)          # + total pushes death
    for r in ps_:
        contrib[r] = -total.get(r, 0.0)         # - total (survival down) pushes death
    aligned = {r: c for r, c in contrib.items() if (c > 0) == (dd > 0) and abs(c) > 0}
    if not aligned:
        return {"verdict": "ABSTAIN", "reason": "no readout aligns with net direction",
                "death_drive": round(dd, 5)}

    top_readout = max(aligned, key=lambda r: abs(aligned[r]))
    dominance = abs(aligned[top_readout]) / sum(abs(v) for v in aligned.values())

    # Dominant path source -> top readout.
    path_res = _dominant_path(out_edges, source, sigma, top_readout, K, decay)
    if path_res is None:
        return {"verdict": "ABSTAIN",
                "reason": f"no simple signed path to dominant readout {top_readout}",
                "death_drive": round(dd, 5)}
    _, path, pw = path_res
    mediators = list(path[1:-1])

    # Gate 2: ablation faithfulness -- delete each mediator, see how much effect remains.
    ablation = []
    for m in mediators:
        dd_m = death_drive(propagate(out_edges, source, sigma, K, decay, blocked={m}), pd_, ps_)
        drop = (dd - dd_m) / dd if dd else 0.0
        ablation.append((m, round(drop, 3)))
    best_faithful = max((d for _, d in ablation), default=0.0)

    notes = []
    if dominance < dominance_min:
        notes.append(f"diffuse: top readout carries only {dominance:.0%} of the "
                     "effect -- low-confidence explanation")
    if mediators and best_faithful < faithful_min:
        notes.append(f"non-faithful: deleting the named mediators changes the effect "
                     f"by at most {best_faithful:.0%} -- redundant routes, the story "
                     "may not be load-bearing")

    lb = max(ablation, key=lambda x: x[1])[0] if ablation else None
    roles = roles or {}
    return {
        "verdict": "EXPLAINED" + (" (caveated)" if notes else ""),
        "direction": direction,
        "death_drive": round(dd, 5),
        "dominant_cascade": _path_str(path, out_edges),
        "top_readout": top_readout,
        "dominance": round(dominance, 3),
        "mediators": mediators,
        "ablation_effect_drop": ablation,
        "load_bearing_mediator": lb,
        "load_bearing_role": roles.get(lb) if lb else None,
        "mediator_roles": {m: roles.get(m, "?") for m in mediators},
        "source_role": roles.get(source),
        "notes": notes,
    }


def _show(res: Dict):
    print(f"  verdict: {res['verdict']}")
    if res["verdict"] == "ABSTAIN":
        print(f"    reason: {res['reason']}"
              + (f"  (death_drive={res.get('death_drive')})" if 'death_drive' in res else ""))
        return
    print(f"    direction: {res['direction']}  (death_drive {res['death_drive']:+.4f})")
    print(f"    dominant cascade: {res['dominant_cascade']}")
    if res.get("source_role"):
        print(f"    source role: {res['source_role']}")
    print(f"    dominance: {res['dominance']:.0%} of effect via {res['top_readout']}")
    if res["ablation_effect_drop"]:
        print(f"    ablation (delete mediator -> effect drop): {res['ablation_effect_drop']}")
        lb, lbr = res["load_bearing_mediator"], res.get("load_bearing_role")
        print(f"    load-bearing mediator: {lb}"
              + (f"   [topology: {lbr}]" if lbr else ""))
    for n in res["notes"]:
        print(f"    NOTE: {n}")


def main() -> None:
    print("=" * 78)
    print("  explain(perturbation, fate)  --  disciplined mechanism interpreter")
    print("=" * 78)
    out_edges, nodes = load_signed_graph("data/omnipath_signed.tsv")
    print("\n(computing topological roles over the signed network ...)")
    roles = build_topology_roles(out_edges, nodes)

    print("\n[1] Nutlin-3 (inhibit MDM2) -- expect death, faithful via TP53")
    _show(explain(out_edges, nodes, "MDM2", -1, expected_fate="death", roles=roles))

    print("\n[2] Venetoclax (inhibit BCL2) -- expect death")
    _show(explain(out_edges, nodes, "BCL2", -1, expected_fate="death", roles=roles))

    print("\n[3] Activate AKT1 -- expect survival")
    _show(explain(out_edges, nodes, "AKT1", +1, expected_fate="survival", roles=roles))

    print("\n[4] DIRECTION MISMATCH: ask Nutlin to explain 'survival' (should ABSTAIN)")
    _show(explain(out_edges, nodes, "MDM2", -1, expected_fate="survival", roles=roles))

    print("\n[5] ABSTENTION: a core-essential housekeeping gene with no apoptosis route")
    # pick a CEG gene in-network with negligible death_drive to demonstrate honest refusal
    try:
        ceg = {l.split("\t")[0].strip()
               for l in open("data/CEGv2.txt", encoding="utf-8").read().splitlines()[1:]}
        cand = next((g for g in sorted(ceg & nodes)
                     if abs(death_drive(propagate(out_edges, g, -1), PRO_DEATH & nodes,
                                        PRO_SURVIVAL & nodes)) < 5e-4), None)
    except Exception:
        cand = None
    if cand:
        print(f"    (gene: {cand}, a core-essential housekeeping gene)")
        _show(explain(out_edges, nodes, cand, -1))
    else:
        print("    (no clean example found in this run)")

    print("\n" + "-" * 78)
    print("EXPLAINED comes with a proof (ablation) and a confidence (dominance);")
    print("ABSTAIN is a first-class answer. The interpreter refuses direction")
    print("mismatches and effects it cannot route -- it explains, it does not invent.")


if __name__ == "__main__":
    main()
