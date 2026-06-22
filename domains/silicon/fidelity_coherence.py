# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Track 3, Step A: three-view net-fidelity coherence on REAL chip artifacts.

The pattern-fidelity coherence engine (`topology/persistent_sheaves.py` exact H0/H1 +
`domains/silicon/coherence.py` calibration nerve) is built and tested on synthetic nerves.
This wires it to real silicon: three INDEPENDENT tool views of "what does each net connect
to", produced by three different stages of one flow:

    verilog  -- synthesis (logical gate netlist)        -> net -> {(inst,pin)}
    def      -- place & route (physical layout)         -> net -> {(inst,pin)}
    spef     -- parasitic extraction (*CONN section)    -> net -> {(inst,pin)}

A net is identified across views by its TERMINAL SET (frozenset of (inst,pin)), so synthesis
renaming does not matter (same idea as `verilog.build_crosswalk`). We then:
  1. report per-view agreement and LOCALIZE the nets where views disagree, and
  2. build the artifact calibration nerve {verilog,def,spef} and compute H0/H1: a clean flow
     gives a filled triangle (H1=0, "globally coherent"); a CYCLIC inconsistency (the views
     pairwise-agree but not jointly) gives H1=1 with `h1_support` naming the calibration edges.

HONEST scope: spef and def are both post-route, so they are more correlated with each other
than with verilog -- "independent tools", not independent physics. Artifact-level H1 is the
coarse global-cyclic bit; per-net localization is the fine detector. A genuinely cyclic,
feature-level H1 obstruction is what multi-patterning supplies (Track 3 Step B). Tier:
`measured` (real EDA tool outputs); this is a structural coherence check, not a sim.

Run:  python -m domains.silicon.fidelity_coherence
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Tuple

from .coherence import analyze_calibration_nerve

Terminal = Tuple[str, str]
View = Dict[str, FrozenSet[Terminal]]      # net name -> terminal set


def _norm(term: Terminal) -> Terminal:
    """Normalize a (instance, pin) terminal across tools: strip Verilog/DEF/SPEF name
    escaping (`\\`) so the SAME physical pin matches regardless of how a tool escaped it."""
    i, p = term
    return (i.replace("\\", ""), p.replace("\\", ""))


def verilog_view(path: str) -> View:
    from .verilog import load_verilog
    nl = load_verilog(path)
    out: View = {}
    for net, eps in nl.endpoints_by_net().items():
        terms = frozenset(_norm((i, p)) for (i, p) in eps if i != "PIN")
        if terms:
            out[net] = terms
    return out


def def_view(def_path: str, spef_path: str, lef_path: str | None) -> Tuple[View, object]:
    from .netlist_bridge import NetlistBridge
    bridge = NetlistBridge(def_path, spef_path, lef_path=lef_path)
    out: View = {net.name: frozenset(_norm(c) for c in net.conns)
                 for net in bridge.signal_nets}
    return out, bridge


def spef_view(path: str) -> View:
    """Parse SPEF *CONN terminal sets, resolving the *NAME_MAP for net + instance ids."""
    with open(path, encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    name_map = dict(re.findall(r"(?m)^\*(\d+)\s+(\S+)\s*$", text))
    out: View = {}
    for block in text.split("*D_NET")[1:]:
        head = re.match(r"\s+(\S+)", block)
        if not head:
            continue
        net = name_map.get(head.group(1).lstrip("*"), head.group(1).lstrip("*"))
        conn = re.search(r"\*CONN(.*?)(?:\*CAP|\*RES|\*END)", block, re.S)
        terms = set()
        if conn:
            for inst_id, pin in re.findall(r"\*I\s+\*?(\w+):(\S+)", conn.group(1)):
                terms.add(_norm((name_map.get(inst_id, inst_id), pin)))
        if terms:
            out[net] = frozenset(terms)
    return out


def _containment(a: set, b: set) -> float:
    """Fraction of the smaller view matched in the other (calibration coverage)."""
    m = min(len(a), len(b))
    return len(a & b) / m if m else 1.0


@dataclass
class FidelityReport:
    n_common_nets: int
    coherent_nets: int
    pair_agreement: Dict[str, float]                 # "verilog~def" -> Jaccard of net-sets
    disagreements: Dict[str, List[str]] = field(default_factory=dict)  # view-pair -> nets
    h0_dimension: int = 0
    h1_dimension: int = 0
    h1_support: List[List[str]] = field(default_factory=list)

    @property
    def coherent(self) -> bool:
        # one connected global section AND no cyclic obstruction
        return self.h0_dimension == 1 and self.h1_dimension == 0

    def render(self) -> str:
        head = "COHERENT (H1=0)" if self.coherent else f"OBSTRUCTION (H1={self.h1_dimension})"
        lines = [f"[{head}] three-view net fidelity  "
                 f"(common nets={self.n_common_nets}, fully-coherent={self.coherent_nets})",
                 f"   H0={self.h0_dimension} (global sections)  H1={self.h1_dimension}"]
        for pair, j in sorted(self.pair_agreement.items()):
            n_bad = len(self.disagreements.get(pair, []))
            lines.append(f"   {pair:<16} terminal-set agreement {j:.3f}   disagreeing nets: {n_bad}")
        if self.h1_support:
            lines.append(f"   H1 localized to calibration edges: {self.h1_support}")
        bad = {n for ns in self.disagreements.values() for n in ns}
        if bad:
            lines.append(f"   sample localized disagreements: {sorted(bad)[:6]}")
        return "\n".join(lines)


def fidelity_coherence(v: View, d: View, s: View, agree_threshold: float = 0.75) -> FidelityReport:
    """Three net-terminal views -> per-net localization + artifact-nerve H0/H1."""
    views = {"verilog": v, "def": d, "spef": s}
    # index each view by terminal set for cross-view identity (rename-proof).
    by_terms = {name: {terms: net for net, terms in view.items()} for name, view in views.items()}
    common = set.intersection(*(set(b) for b in by_terms.values())) if by_terms else set()
    coherent = len(common)

    # pairwise agreement + localized disagreements (nets whose terminal set is not shared).
    pair_agreement: Dict[str, float] = {}
    disagreements: Dict[str, List[str]] = {}
    names = ["verilog", "def", "spef"]
    edges: List[Tuple[str, str]] = []
    for i in range(len(names)):
        for jx in range(i + 1, len(names)):
            x, y = names[i], names[jx]
            sx, sy = set(by_terms[x]), set(by_terms[y])
            j = _containment(sx, sy)
            pair_agreement[f"{x}~{y}"] = j
            only = (sx ^ sy)
            disagreements[f"{x}~{y}"] = sorted(
                {by_terms[x].get(t) or by_terms[y].get(t) for t in only})[:50]
            if j >= agree_threshold:
                edges.append((x, y))

    # filled triangle (joint certificate) iff the three jointly agree on most nets.
    faces = []
    min3 = min(len(by_terms["verilog"]), len(by_terms["def"]), len(by_terms["spef"])) or 1
    if len(edges) == 3 and len(common) / min3 >= agree_threshold:
        faces.append(("verilog", "def", "spef"))

    coh = analyze_calibration_nerve(["verilog", "def", "spef"], edges, faces)
    return FidelityReport(
        n_common_nets=len(common), coherent_nets=coherent,
        pair_agreement=pair_agreement, disagreements=disagreements,
        h0_dimension=coh.h0_dimension, h1_dimension=coh.h1_dimension,
        h1_support=coh.h1_support)


@dataclass
class StageDivergence:
    """Cross-stage netlist coherence: where two flow stages of ONE design diverge."""
    early: str
    late: str
    n_early_nets: int
    n_late_nets: int
    identical_nets: int                          # same terminal set across stages
    divergent_nets: int                          # nets that exist only in the later stage
    inserted_cells: Dict[str, int] = field(default_factory=dict)   # cell type -> count
    sample_divergent: List[str] = field(default_factory=list)

    @property
    def preserved_fraction(self) -> float:
        return self.identical_nets / self.n_early_nets if self.n_early_nets else 1.0

    def render(self) -> str:
        cells = ", ".join(f"{c}x{n}" for c, n in
                          sorted(self.inserted_cells.items(), key=lambda kv: -kv[1])[:6])
        return "\n".join([
            f"[CROSS-STAGE COHERENCE] {self.early} -> {self.late}",
            f"   {self.identical_nets}/{self.n_early_nets} nets preserved with IDENTICAL "
            f"connectivity ({self.preserved_fraction:.0%})",
            f"   {self.divergent_nets} divergent nets localized to inserted cells: {cells}",
            f"   sample divergent nets: {self.sample_divergent[:6]}",
        ])


def _norm_inst(inst: str) -> str:
    return inst.replace(chr(92), "")


def stage_coherence(early_path: str, late_path: str) -> StageDivergence:
    """Run the coherence engine on TWO real flow stages of one design (e.g. synthesis vs
    final). They are logically equivalent (the flow's own LEC certifies it) but structurally
    different; this localizes the divergence to the cells the flow actually inserted (CTS
    clock buffers, hold/fanout buffers). A structural what-changed check on real tool output,
    not a synthetic fault. Tier: structural_only."""
    from .verilog import load_verilog
    e_view, l_view = verilog_view(early_path), verilog_view(late_path)
    late_nl = load_verilog(late_path)
    early_nl = load_verilog(early_path)
    cell_of = {_norm_inst(i): vi.cell for i, vi in late_nl.instances.items()}
    early_insts = {_norm_inst(i) for i in early_nl.instances}

    e_ts = set(e_view.values())
    late_only = {net: ts for net, ts in l_view.items() if ts not in e_ts}
    identical = sum(1 for ts in e_view.values() if ts in set(l_view.values()))

    inserted: Dict[str, int] = {}
    for ts in late_only.values():
        for inst, _pin in ts:
            ni = _norm_inst(inst)
            if ni not in early_insts:             # genuinely inserted by the flow
                ct = cell_of.get(ni)
                if ct:
                    inserted[ct] = inserted.get(ct, 0) + 1
    return StageDivergence(
        early=os.path.basename(early_path), late=os.path.basename(late_path),
        n_early_nets=len(e_view), n_late_nets=len(l_view),
        identical_nets=identical, divergent_nets=len(late_only),
        inserted_cells=inserted, sample_divergent=sorted(late_only)[:8])


def main() -> None:
    print("KOMPOSOS-V | silicon three-view net-fidelity coherence (Track 3, Step A)")
    print("=" * 70)
    base = "domains/silicon/data/orfs_gcd/results/base"
    vp, dp, sp = f"{base}/6_final.v", f"{base}/6_final.def", f"{base}/6_final.spef"
    lef = "domains/silicon/data/openlane/Nangate45.lef"
    if not all(os.path.exists(p) for p in (vp, dp, sp)):
        print(f"[skip] orfs_gcd verilog/def/spef absent under {base}/")
        return
    v = verilog_view(vp)
    d, _ = def_view(dp, sp, lef if os.path.exists(lef) else None)
    s = spef_view(sp)
    print(f"views: verilog={len(v)} nets  def={len(d)} nets  spef={len(s)} nets\n")
    print(fidelity_coherence(v, d, s).render())

    # Cross-stage coherence: a REAL divergence (synthesis vs final), not "all clear".
    synth = f"{base}/1_2_yosys.v"
    if os.path.exists(synth):
        print("\n--- cross-stage coherence: synthesis vs final (real divergence) ---")
        print(stage_coherence(synth, vp).render())


if __name__ == "__main__":
    main()
