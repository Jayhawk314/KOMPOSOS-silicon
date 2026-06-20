#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
explain_combination(A, B) -- combination reasoning over the cell-fate interpreter.

HONEST FOUNDATION (stated up front): signed cascade propagation is LINEAR, so
    death_drive(A + B) = death_drive(A) + death_drive(B)   exactly.
A naive sum therefore captures only ADDITIVE combination (two weak hits summing) --
NOT genuine epistatic synergy. True synthetic lethality needs the structural
non-linearity that the ablation primitive provides:

    model "B inhibits node N" as REMOVING N as a conduit, then re-propagate A.
    conduit interaction = death_drive(A | N removed) - death_drive(A)

If N was a survival route buffering A, removing it amplifies A's death drive
(structural synergy); if N carried A's death signal, removing it antagonises A.
This is non-additive and reuses the ablation machinery directly.

So every call reports two clearly-labelled tiers:
  [additive]  exact linear sum (independent action) + emergent-crossing flag
  [structural] conduit interaction via ablation -- the genuine non-linearity,
               with the buffer/antagonist node NAMED

Genuine threshold/logic epistasis (AND-gates) is beyond a linear+ablation model --
flagged as the honest limitation.

Run:  python -m oracle.explain_combination
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from oracle.cell_fate_netbalance import (
    load_signed_graph, propagate, death_drive, PRO_DEATH, PRO_SURVIVAL,
)

EFFECT_FLOOR = 5e-4  # below this, an individual perturbation is "sub-threshold"


def _dd(out_edges, src, sg, nodes, blocked=frozenset()):
    return death_drive(propagate(out_edges, src, sg, blocked=blocked),
                       PRO_DEATH & nodes, PRO_SURVIVAL & nodes)


def explain_combination(out_edges, nodes, a, sa: int, b, sb: int) -> Dict:
    """Explain the combined fate effect of perturbing a (by sa) and b (by sb)."""
    for x in (a, b):
        if x not in nodes:
            return {"verdict": "ABSTAIN", "reason": f"{x} not in network"}
    if a == b:
        return {"verdict": "ABSTAIN", "reason": "A and B are the same node"}

    dd_a = _dd(out_edges, a, sa, nodes)
    dd_b = _dd(out_edges, b, sb, nodes)
    additive = dd_a + dd_b

    # [additive] emergent crossing: each weak alone, but the sum is a real effect.
    weak_a = abs(dd_a) < EFFECT_FLOOR
    weak_b = abs(dd_b) < EFFECT_FLOOR
    emergent = (weak_a or weak_b) and abs(additive) >= EFFECT_FLOOR

    # [structural] conduit interaction: B removes its target as a route for A.
    # Defined when B is inhibitory (knockout-like); activation isn't a conduit removal.
    interaction = None
    a_given_b = None
    if sb < 0:
        a_given_b = _dd(out_edges, a, sa, nodes, blocked={b})
        interaction = a_given_b - dd_a   # how A's death drive changes when B's target is gone

    # classify the structural relationship (relative to A's own magnitude)
    rel = (interaction / abs(dd_a)) if (interaction is not None and abs(dd_a) > 1e-12) else 0.0
    if interaction is None:
        structural = "n/a (B is activating; conduit model needs inhibitory B)"
    elif rel > 0.25:
        structural = (f"SYNERGY: removing {b} amplifies A's death drive by "
                      f"{rel:+.0%} -- {b} was a survival route buffering {a}")
    elif rel < -0.25:
        structural = (f"ANTAGONISM: removing {b} cuts A's death drive by {rel:+.0%} "
                      f"-- {b} carried part of {a}'s death route")
    else:
        structural = f"independent: removing {b} changes A's death drive by only {rel:+.0%}"

    direction = "death" if additive > 0 else "survival"
    return {
        "verdict": "EXPLAINED",
        "dd_A": round(dd_a, 5), "dd_B": round(dd_b, 5),
        "additive": round(additive, 5), "additive_direction": direction,
        "emergent_crossing": emergent,
        "a_given_b": None if a_given_b is None else round(a_given_b, 5),
        "conduit_interaction": None if interaction is None else round(interaction, 5),
        "structural": structural,
    }


def propose_partner(out_edges, nodes, a, sa: int, k: int = 6) -> List[Tuple[str, float]]:
    """Scan inhibitory partners B; rank by how much knocking out B amplifies A's death drive.

    The synthetic-lethality hypothesis generator: find the survival route to co-target.
    """
    dd_a = _dd(out_edges, a, sa, nodes)
    cands = sorted((PRO_SURVIVAL & nodes) | {n for n in nodes if n != a})
    scored = []
    # limit scan to survival panel + the nodes A's cascade actually touches (keep it cheap+relevant)
    touched = {n for n, v in propagate(out_edges, a, sa).items() if abs(v) > 1e-4}
    scan = sorted((PRO_SURVIVAL & nodes) | (touched & nodes))
    for b in scan:
        if b == a:
            continue
        gain = _dd(out_edges, a, sa, nodes, blocked={b}) - dd_a
        scored.append((b, gain))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


def _show(tag, res: Dict):
    print(f"\n{tag}")
    if res["verdict"] == "ABSTAIN":
        print(f"  ABSTAIN: {res['reason']}")
        return
    print(f"  dd(A)={res['dd_A']:+.4f}  dd(B)={res['dd_B']:+.4f}")
    print(f"  [additive] sum={res['additive']:+.4f} -> {res['additive_direction']}"
          + ("   EMERGENT (weak alone, real together)" if res["emergent_crossing"] else ""))
    if res["conduit_interaction"] is not None:
        print(f"  [structural] A|removed(B)={res['a_given_b']:+.4f}  "
              f"interaction={res['conduit_interaction']:+.4f}")
    print(f"  {res['structural']}")


def main() -> None:
    print("=" * 78)
    print("  explain_combination(A, B)  --  additive (exact) + structural (ablation)")
    print("=" * 78)
    out_edges, nodes = load_signed_graph("data/omnipath_signed.tsv")

    # Real clinical combination: MDM2 inhibitor (Nutlin/idasanutlin) + BCL2 inhibitor (Venetoclax).
    _show("[1] Nutlin (MDM2-) + Venetoclax (BCL2-)  [real clinical combo]",
          explain_combination(out_edges, nodes, "MDM2", -1, "BCL2", -1))

    # MDM2- + MCL1-  (MCL1 is the other major apoptosis buffer)
    _show("[2] Nutlin (MDM2-) + MCL1 inhibitor",
          explain_combination(out_edges, nodes, "MDM2", -1, "MCL1", -1))

    # Activating B -> conduit model n/a (honest)
    _show("[3] Nutlin (MDM2-) + activate AKT1 (survival push)",
          explain_combination(out_edges, nodes, "MDM2", -1, "AKT1", +1))

    print("\n[4] propose_partner for Nutlin (MDM2-): which survival route to co-target?")
    for b, gain in propose_partner(out_edges, nodes, "MDM2", -1):
        flag = " (survival panel)" if b in PRO_SURVIVAL else ""
        print(f"      co-inhibit {b:10s}  death-drive gain {gain:+.5f}{flag}")

    print("\n" + "-" * 78)
    print("[additive] is exact in the linear model (independent action). [structural]")
    print("is the genuine non-linearity: B knocking out a buffer changes A's mechanism.")
    print("Neither is calibrated magnitude -- these are DIRECTIONAL combination")
    print("hypotheses (the model is validated for direction, 8/8, not for potency).")
    print("True threshold/logic epistasis needs a non-linear model -- next step.")


if __name__ == "__main__":
    main()
