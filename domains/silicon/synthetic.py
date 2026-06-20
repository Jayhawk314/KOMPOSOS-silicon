# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Rung 0 — prove the V substrate carries silicon (no real data).

Generates a *synthetic chip* (two logic cores joined by one congested bus),
loads it as a `Category`, and runs the substrate's own geometry + a sheaf-style
coherence check over it. The point is plumbing, not realism: show that the
GRID-pattern analyses (Ollivier-Ricci congestion, Fiedler seam) and the
CHEM/GRID coherence verdicts (GLUE / TENSION / CONTRADICT) run on a chip graph
using engines already in this repo.

What it demonstrates
  - congestion corridor   : the most negative-curvature wire = routing bottleneck
                            (geometry/ricci.py — same module GRID uses on power flow)
  - chiplet seam          : the Fiedler partition = where to cut into chiplets
                            (geometry/spectral.py)
  - coherence verdicts    : compare the logical (netlist) view against the physical
                            (layout) view per net; a logical net with no routed wire
                            is a CONTRADICT — the honest rejector firing on a toy.

This is a PROPOSAL-side demo: curvature/seam/coherence only *describe structure*.
No verdict is persisted; nothing here simulates silicon physics. Rung 2 swaps the
synthetic graph for real OpenLane DEF/SPEF via a netlist_bridge, and Rung 1 adds
the CHEM material verdicts behind COG + HonestyGate. See docs/SILICON_PLAN.md.

Run:
    python -m domains.silicon.synthetic
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from core.category import Category
from core.types import Object, Morphism
from .flow_geometry import edge_curvatures, fiedler_seam


# ═══════════════════════════════════════════════════════════════════════════
# 1. The synthetic chip: two cores + one congested bus (a "barbell")
# ═══════════════════════════════════════════════════════════════════════════

# Eight logic blocks: core A and core B, each an internally dense cluster.
CORE_A = ["A_fetch", "A_decode", "A_alu", "A_regfile"]
CORE_B = ["B_fetch", "B_decode", "B_alu", "B_regfile"]


@dataclass
class Net:
    """A logical connection from the netlist (the RTL/GLS view)."""
    src: str
    tgt: str
    net: str
    logical_delay: float        # intended timing (ns), the spec
    fanout: int = 1


@dataclass
class SyntheticChip:
    """A toy chip with a logical (netlist) view and a physical (layout) view."""
    nets: List[Net]                          # logical view: what the netlist says
    routes: Dict[str, float]                 # physical view: net -> realized delay (ns)
    category: Category                       # the physical routing graph as a Category


def _clique(blocks: List[str], base_delay: float) -> List[Net]:
    """Densely wire a core internally (meshed => positively curved => resilient)."""
    nets: List[Net] = []
    for i, s in enumerate(blocks):
        for t in blocks[i + 1:]:
            nets.append(Net(s, t, f"n_{s}__{t}", logical_delay=base_delay, fanout=2))
    return nets


def build_synthetic_chip() -> SyntheticChip:
    """
    Build the toy chip and load its *physical* graph into a Category.

    Planted structure (so the analyses have something true to find):
      - two internally dense cores  -> positive curvature, a clear Fiedler seam
      - ONE bus wire between cores   -> strong negative curvature (the bottleneck)
      - one TENSION net              -> physical delay drifts within margin
      - one CONTRADICT net           -> declared in the netlist, never routed
    """
    nets: List[Net] = []
    nets += _clique(CORE_A, base_delay=0.10)
    nets += _clique(CORE_B, base_delay=0.10)

    # The single inter-core bus: carries all cross-core traffic -> congestion.
    nets.append(Net("A_alu", "B_alu", "n_bus_AB", logical_delay=0.20, fanout=16))

    # A logical-only net: the synthesis tool emitted it, P&R optimized it out.
    # No matching route below => CONTRADICT (the layout and netlist disagree).
    nets.append(Net("A_fetch", "B_fetch", "n_ghost_fetch", logical_delay=0.25, fanout=1))

    # Physical view: realized routes with extracted delay. Most match the spec.
    routes: Dict[str, float] = {}
    for n in nets:
        if n.net == "n_ghost_fetch":
            continue                                   # CONTRADICT: never routed
        if n.net == "n_bus_AB":
            routes[n.net] = n.logical_delay * 1.15     # TENSION: bus drifts a bit
        else:
            routes[n.net] = n.logical_delay            # GLUE: matches spec

    # Load the *physical* routing graph (only routed nets) into a Category.
    cat = Category(name="synthetic_chip", db_path=":memory:")
    placed = set()
    for n in nets:
        if n.net not in routes:
            continue
        for b in (n.src, n.tgt):
            if b not in placed:
                cat.add_object(Object(name=b, type_name="block", provenance="synthetic"))
                placed.add(b)
        cat.connect(
            n.src, n.tgt, name="wire",
            confidence=1.0,
            net=n.net, delay=routes[n.net], fanout=n.fanout,
        )
    return SyntheticChip(nets=nets, routes=routes, category=cat)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Flow geometry: congestion corridors (Ricci) + chiplet seam (Fiedler)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Corridor:
    src: str
    tgt: str
    net: str
    curvature: float


def congestion_corridors(chip: SyntheticChip) -> List[Corridor]:
    """Ricci congestion corridors (via shared flow_geometry), tagged with net names."""
    net_of = {frozenset((m.source, m.target)): m.metadata.get("net", "?")
              for m in chip.category.morphisms()}
    return [Corridor(s, t, net_of.get(frozenset((s, t)), "?"), kappa)
            for s, t, kappa in edge_curvatures(chip.category)]


@dataclass
class Seam:
    fiedler_value: float
    partition_a: List[str]
    partition_b: List[str]
    cut_nets: List[str]


def chiplet_seam(chip: SyntheticChip) -> Seam:
    """
    Spectral (Fiedler) analysis: the algebraic connectivity measures how hard the
    chip is to cut; the Fiedler vector's sign pattern exhibits the weakest seam —
    the ideal boundary to sever a monolith into chiplets.
    """
    fiedler_value, part_a, part_b = fiedler_seam(chip.category)

    # Nets whose endpoints fall on opposite sides of the seam = the cut.
    names = set(part_a) | set(part_b)
    side = {name: ("a" if name in part_a else "b") for name in names}
    cut_nets = [n.net for n in chip.nets
                if n.net in chip.routes and side.get(n.src) != side.get(n.tgt)]
    return Seam(fiedler_value, part_a, part_b, cut_nets)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Sheaf-style coherence: logical (netlist) vs physical (layout) per net
# ═══════════════════════════════════════════════════════════════════════════

# Same verdict scheme as KOMPOSOS-GRID/domains/grid/coherence.py.
TOLERANCE = 0.05          # relative discrepancy treated as "agrees"


@dataclass
class CoherenceVerdict:
    net: str
    verdict: str          # GLUE | TENSION | CONTRADICT
    detail: str


def coherence_check(chip: SyntheticChip) -> List[CoherenceVerdict]:
    """
    Treat each net as a section of a presheaf over the chip's blocks. The logical
    view (netlist) and physical view (layout) must agree on overlaps to glue.
        GLUE       <= TOLERANCE        sections agree; gluable
        TENSION    <= 5x TOLERANCE     within engineering margin
        CONTRADICT  > 5x  OR unrouted  layout and netlist disagree
    """
    out: List[CoherenceVerdict] = []
    for n in chip.nets:
        if n.net not in chip.routes:
            out.append(CoherenceVerdict(
                n.net, "CONTRADICT",
                f"declared {n.src}->{n.tgt} in netlist but no routed wire (optimized out)"))
            continue
        phys = chip.routes[n.net]
        rel = abs(phys - n.logical_delay) / max(n.logical_delay, 1e-9)
        if rel <= TOLERANCE:
            verdict = "GLUE"
        elif rel <= 5 * TOLERANCE:
            verdict = "TENSION"
        else:
            verdict = "CONTRADICT"
        out.append(CoherenceVerdict(
            n.net, verdict,
            f"logical {n.logical_delay:.3f}ns vs physical {phys:.3f}ns "
            f"({rel*100:.0f}% discrepancy)"))
    return out


# ═══════════════════════════════════════════════════════════════════════════
# 4. Report
# ═══════════════════════════════════════════════════════════════════════════

def run() -> Dict:
    """Build the chip, run all three passes, return a structured result."""
    chip = build_synthetic_chip()
    corridors = congestion_corridors(chip)
    seam = chiplet_seam(chip)
    coherence = coherence_check(chip)
    return {"chip": chip, "corridors": corridors, "seam": seam, "coherence": coherence}


def main() -> None:
    r = run()
    chip, corridors, seam, coherence = (
        r["chip"], r["corridors"], r["seam"], r["coherence"])

    stats = chip.category.statistics()
    print("KOMPOSOS-V | silicon Rung 0 - synthetic chip")
    print("=" * 60)
    print(f"blocks: {len(chip.category.objects())}   "
          f"routed wires: {len(chip.category.morphisms())}   "
          f"logical nets: {len(chip.nets)}")
    print()

    print("CONGESTION CORRIDORS  (Ollivier-Ricci; most negative = worst bottleneck)")
    for c in corridors[:3]:
        flag = "  <-- bottleneck" if c is corridors[0] else ""
        print(f"   kappa={c.curvature:+.3f}  {c.src:>9} -> {c.tgt:<9} [{c.net}]{flag}")
    print()

    print(f"CHIPLET SEAM  (Fiedler value lambda_2 = {seam.fiedler_value:.4f}; "
          f"lower = easier to cut)")
    print(f"   chiplet A: {', '.join(seam.partition_a)}")
    print(f"   chiplet B: {', '.join(seam.partition_b)}")
    print(f"   cut nets : {', '.join(seam.cut_nets) or '(none)'}")
    print()

    print("COHERENCE  (netlist view vs layout view)")
    order = {"CONTRADICT": 0, "TENSION": 1, "GLUE": 2}
    for v in sorted(coherence, key=lambda x: order[x.verdict]):
        print(f"   {v.verdict:<10} {v.net:<16} {v.detail}")
    print()

    n_bad = sum(1 for v in coherence if v.verdict == "CONTRADICT")
    print(f"verdict: {n_bad} CONTRADICT net(s) would block a clean tape-out. "
          f"All findings are structural proposals - no claim persisted.")


if __name__ == "__main__":
    main()
