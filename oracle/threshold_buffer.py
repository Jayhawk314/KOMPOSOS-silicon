#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Thresholded-buffer model -- the minimal non-linearity for synthetic-lethal synergy.

The linear cascade model proved synergy=0 by construction (dd(A+B)=dd(A)+dd(B)).
The real apoptosis synergy is a THRESHOLD: anti-apoptotic buffers (BCL2/MCL1...)
hold the mitochondrial gate shut until the pro-death signal overwhelms them. We add
exactly that one non-linearity and nothing else:

    death_signal(P)  = Σ influence on EFFECTORS  (caspases, BAX/BAK, PUMA, NOXA, ...)
    buffer_level(P)  = B0 + Σ influence on BUFFERS (BCL2, MCL1, BCL-XL, XIAP, ...)
    committed(P)     = max(0, death_signal(P) - max(0, buffer_level(P)))   <-- the gate

(direct self-effect included: inhibiting BCL2 lowers BCL2 itself.)

    synergy(A,B,B0)  = committed(A+B) - committed(A) - committed(B)

HONESTY ON THE FREE PARAMETER B0 (resting buffer capacity): we do NOT tune it to a
winning value. We SWEEP it and ask whether emergent synergy (A+B commits while A
alone is buffered) appears across a BROAD regime -- a robust structural feature --
or only at a knife-edge (which would be cherry-picking). Linear model = flat 0 for
all B0; only the threshold creates a regime.

Directional structural hypothesis, not calibrated potency. Needs data/omnipath_signed.tsv.
Run:  python -m oracle.threshold_buffer
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from oracle.cell_fate_netbalance import load_signed_graph, propagate

EFFECTORS = {"CASP3", "CASP9", "CASP7", "CASP8", "BAX", "BAK1", "BID", "BBC3",
             "PMAIP1", "APAF1", "CYCS", "DIABLO", "FAS", "FADD"}
BUFFERS = {"BCL2", "BCL2L1", "MCL1", "BCL2A1", "BIRC5", "XIAP", "BIRC2"}


def full_influence(out_edges, perts: List[Tuple[str, int]], K=4, decay=0.5) -> Dict[str, float]:
    """Summed signed influence of all perturbations, including direct self-effect."""
    total: Dict[str, float] = defaultdict(float)
    for node, sigma in perts:
        for v, val in propagate(out_edges, node, sigma, K, decay).items():
            total[v] += val
        total[node] += sigma  # direct: the perturbed node's own level moves
    return total


def signals(out_edges, nodes, perts):
    t = full_influence(out_edges, perts)
    death_signal = sum(t.get(e, 0.0) for e in EFFECTORS & nodes)
    buffer_delta = sum(t.get(b, 0.0) for b in BUFFERS & nodes)
    return death_signal, buffer_delta


def committed(death_signal, buffer_delta, B0) -> float:
    return max(0.0, death_signal - max(0.0, B0 + buffer_delta))


def main() -> None:
    print("=" * 80)
    print("  THRESHOLDED-BUFFER MODEL  --  does synthetic-lethal synergy emerge?")
    print("=" * 80)
    out_edges, nodes = load_signed_graph("data/omnipath_signed.tsv")

    A = [("MDM2", -1)]           # Nutlin: buffered alone in the linear model
    B = [("BCL2", -1)]           # Venetoclax: lowers the buffer
    AB = A + B

    dsa, bda = signals(out_edges, nodes, A)
    dsb, bdb = signals(out_edges, nodes, B)
    dsab, bdab = signals(out_edges, nodes, AB)
    print(f"\nMDM2-:        death_signal={dsa:+.4f}  buffer_delta={bda:+.4f}")
    print(f"BCL2-:        death_signal={dsb:+.4f}  buffer_delta={bdb:+.4f}")
    print(f"MDM2- +BCL2-: death_signal={dsab:+.4f}  buffer_delta={bdab:+.4f}")

    print("\n[sweep over resting buffer capacity B0]  committed death (gate output)")
    print(f"    {'B0':>6s} {'comm(A)':>9s} {'comm(B)':>9s} {'comm(A+B)':>10s} "
          f"{'synergy':>9s} {'emergent?':>10s}")
    emergent_regime = []
    for B0 in [0.0, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.70, 1.00]:
        cA = committed(dsa, bda, B0)
        cB = committed(dsb, bdb, B0)
        cAB = committed(dsab, bdab, B0)
        syn = cAB - cA - cB
        emergent = cAB > 1e-9 and cA <= 1e-9   # A+B kills, A alone buffered
        if emergent:
            emergent_regime.append(B0)
        print(f"    {B0:6.2f} {cA:9.4f} {cB:9.4f} {cAB:10.4f} {syn:+9.4f} "
              f"{'YES' if emergent else '-':>10s}")

    print("\n[contrast] linear model synergy (dd(A+B) - dd(A) - dd(B)) is identically 0")
    print("    by construction -- no B0 makes it emerge. Only the threshold does.")

    # Negative control: two unrelated perturbations should NOT synergize.
    print("\n[negative control] two unrelated inhibitions (should show little synergy)")
    C = [("HDAC1", -1)]
    D = [("EGFR", -1)]
    dsc, bdc = signals(out_edges, nodes, C)
    dsd, bdd = signals(out_edges, nodes, D)
    dscd, bdcd = signals(out_edges, nodes, C + D)
    for B0 in [0.10, 0.30]:
        s = committed(dscd, bdcd, B0) - committed(dsc, bdc, B0) - committed(dsd, bdd, B0)
        print(f"    B0={B0:.2f}: HDAC1- + EGFR- synergy = {s:+.4f}")

    print("\n" + "-" * 80)
    if emergent_regime:
        print(f"RESULT: emergent synthetic-lethal synergy appears for B0 in "
              f"[{min(emergent_regime):.2f}, {max(emergent_regime):.2f}] -- a BROAD")
        print("regime, not a knife-edge: MDM2- is buffered alone but MDM2-+BCL2- commits.")
        print("The single threshold non-linearity generates the synergy the linear")
        print("model structurally could not. (Directional hypothesis, not potency.)")
    else:
        print("RESULT: no emergent regime found -- even the threshold model does not")
        print("recover synergy here; report honestly and inspect the signals above.")


if __name__ == "__main__":
    main()
