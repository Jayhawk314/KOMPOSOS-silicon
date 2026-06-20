#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Cell-fate net-balance via SIGNED CASCADE PROPAGATION  (DIAGNOSTIC / control experiment).

Built on the OmniPath signed causal network (passes the coverage gate at the cascade
level). A perturbation (activate/inhibit a node) is propagated through the signed
network; signs MULTIPLY along paths (so the edge-level activation skew re-balances),
with per-hop decay. We read the net signed influence onto two fate panels:

    pro-death effectors   (caspases, BAX/BAK, PUMA/NOXA, APAF1, cytochrome-c, FAS)
    pro-survival effectors (BCL2/BCL-XL/MCL1, survivin, XIAP, AKT1)

    death_drive = Σ influence(pro-death) − Σ influence(pro-survival)
    death_drive > 0  -> pushes toward apoptosis / collapse
    death_drive < 0  -> pushes toward survival

CONTROL EXPERIMENT (the honest test, no labels needed): run perturbations whose
direction is textbook pharmacology and check the predicted sign matches biology --
including two real approved drugs (Nutlin = MDM2 inhibitor, Venetoclax = BCL2
inhibitor). And compare against an UNSIGNED baseline that ignores signs: it cannot
tell "activate MDM2" from "inhibit MDM2", so it must fail the directional cases.
That is the point -- signs are necessary, and cascade propagation carries them.

Nothing here is wired into scoring. Needs data/omnipath_signed.tsv (see omnipath_gate.py).

Run:  python -m oracle.cell_fate_netbalance
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

TSV = "data/omnipath_signed.tsv"

PRO_DEATH = {"CASP3", "CASP9", "CASP7", "CASP8", "BAX", "BAK1", "BID", "BBC3",
             "PMAIP1", "APAF1", "CYCS", "DIABLO", "FAS", "FADD"}
PRO_SURVIVAL = {"BCL2", "BCL2L1", "MCL1", "BIRC5", "XIAP", "BIRC2", "BCL2A1",
                "CFLAR", "AKT1"}


def load_signed_graph(path: str):
    """out_edges[u] = [(v, sign)]; unsigned/ambiguous edges dropped."""
    out_edges: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    nodes = set()
    with open(path, encoding="utf-8") as f:
        f.readline()
        for line in f:
            c = line.rstrip("\n").split("\t")
            if len(c) < 7 or c[4] != "True":
                continue
            s, t = c[2] or c[0], c[3] or c[1]
            stim, inh = c[5] == "True", c[6] == "True"
            if stim and not inh:
                sg = 1
            elif inh and not stim:
                sg = -1
            else:
                continue
            out_edges[s].append((t, sg))
            nodes.add(s); nodes.add(t)
    return out_edges, nodes


def propagate(out_edges, source: str, sigma: int, K: int = 4, decay: float = 0.5,
              signed: bool = True, blocked=frozenset()) -> Dict[str, float]:
    """Signed random-walk influence from `source` perturbed by `sigma` (+1/-1).

    x_{k+1}[v] = Σ_{u->v} sign(u->v)/outdeg(u) * x_k[u]   (sign=+1 if unsigned mode)
    total = Σ_k decay^k x_k   -- sums signed path contributions, short paths weighted more.
    `blocked` nodes are removed from propagation (used for ablation faithfulness).
    """
    outdeg = {u: len(es) for u, es in out_edges.items()}
    x = {source: float(sigma)}
    total: Dict[str, float] = defaultdict(float)
    for k in range(1, K + 1):
        nx: Dict[str, float] = defaultdict(float)
        for u, val in x.items():
            od = outdeg.get(u, 0)
            if not od:
                continue
            w = val / od
            for (v, sg) in out_edges[u]:
                if v in blocked:
                    continue
                nx[v] += (sg if signed else 1) * w
        if not nx:
            break
        x = nx
        d = decay ** k
        for v, val in x.items():
            total[v] += d * val
    return total


def death_drive(total: Dict[str, float], present_death, present_surv) -> float:
    return (sum(total.get(r, 0.0) for r in present_death)
            - sum(total.get(r, 0.0) for r in present_surv))


def main() -> None:
    print("=" * 78)
    print("  CELL-FATE NET-BALANCE  --  signed cascade propagation on OmniPath")
    print("=" * 78)

    out_edges, nodes = load_signed_graph(TSV)
    pd_ = sorted(PRO_DEATH & nodes)
    ps_ = sorted(PRO_SURVIVAL & nodes)
    print(f"\nnetwork: {len(nodes)} nodes, signed edges loaded")
    print(f"pro-death panel in graph:   {len(pd_)}/{len(PRO_DEATH)}  {pd_}")
    print(f"pro-survival panel in graph:{len(ps_)}/{len(PRO_SURVIVAL)}  {ps_}")

    # (perturbation node, sign, expected death_drive sign, note)
    cases = [
        ("TP53", +1, +1, "activate p53 -> apoptosis"),
        ("MDM2", +1, -1, "activate MDM2 -> suppress p53 -> survival"),
        ("MDM2", -1, +1, "INHIBIT MDM2 = Nutlin-3 (real drug) -> reactivate p53 -> apoptosis"),
        ("AKT1", +1, -1, "activate AKT -> survival"),
        ("AKT1", -1, +1, "inhibit AKT -> apoptosis"),
        ("BCL2", +1, -1, "activate BCL2 -> survival"),
        ("BCL2", -1, +1, "INHIBIT BCL2 = Venetoclax (real drug) -> apoptosis"),
        ("MAPK1", +1, -1, "activate ERK -> proliferation/survival"),
    ]

    print("\n[control experiment]  does the predicted direction match known biology?")
    print(f"    {'perturbation':18s} {'expect':>6s} {'signed':>9s} {'match':>6s}   "
          f"{'unsigned':>9s} {'match':>6s}")
    s_hit = u_hit = total_cases = 0
    for node, sigma, exp, note in cases:
        if node not in nodes:
            print(f"    {node+('+' if sigma>0 else '-'):18s}  (not in graph)")
            continue
        total_cases += 1
        sd = death_drive(propagate(out_edges, node, sigma, signed=True), pd_, ps_)
        ud = death_drive(propagate(out_edges, node, sigma, signed=False), pd_, ps_)
        s_ok = (sd > 0) == (exp > 0)
        u_ok = (ud > 0) == (exp > 0)
        s_hit += s_ok; u_hit += u_ok
        tag = f"{node}{'+' if sigma>0 else '-'}"
        print(f"    {tag:18s} {('death' if exp>0 else 'surv'):>6s} "
              f"{sd:+9.4f} {'OK' if s_ok else 'X':>6s}   "
              f"{ud:+9.4f} {'OK' if u_ok else 'X':>6s}")
    print(f"\n    SIGNED cascade matches biology:   {s_hit}/{total_cases}")
    print(f"    UNSIGNED baseline matches biology: {u_hit}/{total_cases}  "
          f"(can't tell activate from inhibit -> must fail directional cases)")

    # Showcase the Nutlin cascade: inhibit MDM2 -> p53 up -> effectors.
    print("\n[2] Cascade detail: INHIBIT MDM2 (Nutlin-3)  -- top fate effectors moved")
    tot = propagate(out_edges, "MDM2", -1, signed=True)
    contrib = sorted(((r, tot.get(r, 0.0)) for r in pd_ + ps_),
                     key=lambda x: abs(x[1]), reverse=True)
    for r, v in contrib[:8]:
        panel = "death" if r in PRO_DEATH else "surv "
        print(f"      {r:8s} ({panel}) influence {v:+.4f}")

    print("\n" + "-" * 78)
    print("Read: signed cascade propagation should recover textbook directions,")
    print("including Nutlin (MDM2 inhibitor) and Venetoclax (BCL2 inhibitor) as")
    print("pro-apoptotic. The unsigned baseline cannot -- proving signs (carried")
    print("through the cascade) are what make fate direction computable. This is a")
    print("structural control experiment, NOT a validated quantitative predictor.")


if __name__ == "__main__":
    main()
