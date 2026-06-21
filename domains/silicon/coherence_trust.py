# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Track 3 Step C: trust-gate the coherence verdict (3A net-fidelity + 3B double-patterning).

The obstruction engines (3A `fidelity_coherence`, 3B `dp_conflict`) PROPOSE localized
deviations -- a non-coherent net, a native double-patterning conflict edge. This module is
the VERIFICATION half (CLAUDE.md invariant #1): a localized deviation is TRUSTED only if
multiple INDEPENDENT views corroborate it, specificity-weighted so a non-specific/global
view cannot over-vouch -- then the rationale is grounded through the shared `HonestyGate`,
and the verdict carries an HONEST evidence tier (`structural_only`; foundry-measured EPE
stays gated, never promoted).

The corroboration math is the oracle coherence cluster's, reused (not reinvented):
`oracle/coherence_specificity.py`'s IDF specificity `spec(w)=log(N/breadth(w))/log(N)` and
the specificity-weighted noisy-OR `1 - prod(1 - conf*spec)`. A witness that flags a large
FRACTION of all items (a hub naming-convention mismatch in 3A; the spectral per-component
signal in 3B) gets spec ~ 0 and contributes little; a witness that localizes to FEW items
(BFS Z/2 frustrated edges; a specific view-pair disagreement) gets spec ~ 1 and carries the
verdict.

Run:  python -m domains.silicon.coherence_trust
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from core.category import Category
from core.honesty_gate import HonestyGate

TIER = "structural_only"        # topological/geometric obstruction over real artifacts;
#                                 NOT foundry-measured EPE -- that stays gated.


def _clamp(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


@dataclass
class Witness:
    """One independent view/method flagging an item, with its breadth (for IDF specificity)."""
    name: str                   # e.g. "bfs_z2", "spectral", "verilog~def"
    confidence: float           # this witness's confidence in THIS item, [0,1]
    breadth: int                # # distinct items this witness flags (the IDF numerator's b)
    total: int                  # N items in scope (IDF denominator)

    @property
    def specificity(self) -> float:
        """IDF: a witness flagging everything (breadth ~ total) -> ~0; a localized one -> ~1."""
        if self.total <= 1:
            return 1.0
        b = max(1, min(self.breadth, self.total))
        return _clamp(math.log(self.total / b) / math.log(self.total))

    @property
    def weight(self) -> float:
        return _clamp(self.confidence) * self.specificity


@dataclass
class Obstruction:
    item: str                   # the localized thing (a net, or a "u--v" conflict edge)
    witnesses: List[Witness] = field(default_factory=list)


@dataclass
class TrustVerdict:
    item: str
    status: str                 # TRUSTED | UNCORROBORATED | HOLLOW
    corroboration: float
    n_witnesses: int
    n_specific: int             # witnesses with non-trivial specificity-weighted contribution
    grounded: bool
    tier: str
    reason: str
    support: List[str] = field(default_factory=list)   # localized members (e.g. conflict edges)

    @property
    def trusted(self) -> bool:
        return self.status == "TRUSTED"


def corroboration(obs: Obstruction) -> float:
    """Specificity-weighted noisy-OR over the distinct witnesses (oracle coherence cluster)."""
    pr = 1.0
    for w in obs.witnesses:
        pr *= (1.0 - w.weight)
    return 1.0 - pr


def gate_obstruction(obs: Obstruction, *, min_corroboration: float = 0.5,
                     min_specific: int = 2, specific_floor: float = 0.05,
                     min_grounding: float = 0.5,
                     support: List[str] | None = None) -> TrustVerdict:
    """Verify a proposed obstruction: require independent specificity-weighted corroboration,
    then ground the rationale through the HonestyGate. Tier stays `structural_only`."""
    support = support or []
    specific = [w for w in obs.witnesses if w.weight >= specific_floor]
    corr = corroboration(obs)
    if len(specific) < min_specific or corr < min_corroboration:
        return TrustVerdict(
            obs.item, "UNCORROBORATED", corr, len(obs.witnesses), len(specific),
            grounded=False, tier=TIER,
            reason=(f"only {len(specific)} specific corroborating view(s) "
                    f"(need {min_specific}); corroboration {corr:.2f} "
                    f"(need {min_corroboration:.2f}) -- may be a single-view artifact"),
            support=support)

    # Ground the rationale in the evidence vocabulary (CLAUDE.md #4): build the witness->item
    # support as committed evidence, then check the claim grounds in it. With >=2 witnesses the
    # excluded candidate edge is grounded by the others; a lone witness would read ~0.
    cat = Category(name="coherence_trust", db_path=":memory:")
    cat.add(obs.item, type_name="obstruction")
    for w in obs.witnesses:
        cat.add(w.name, type_name="witness")
        cat.connect(w.name, obs.item, name="flags", confidence=round(_clamp(w.weight), 2))
    claim = " ".join(f"{w.name} flags {obs.item} {round(_clamp(w.weight), 2)}"
                     for w in obs.witnesses)
    gate = HonestyGate(min_grounding=min_grounding)
    hv = gate.check_claim(cat, obs.witnesses[0].name, obs.item, "flags", claim=claim)
    if hv.checked and not hv.honest:
        return TrustVerdict(obs.item, "HOLLOW", corr, len(obs.witnesses), len(specific),
                            grounded=False, tier=TIER,
                            reason=f"rationale not grounded: {hv.reason}", support=support)
    return TrustVerdict(
        obs.item, "TRUSTED", corr, len(obs.witnesses), len(specific),
        grounded=True, tier=TIER,
        reason=(f"corroborated by {len(specific)} independent specificity-weighted views "
                f"(corroboration {corr:.2f}); rationale grounded"),
        support=support)


# ── Track 3B adapter: native double-patterning conflicts ────────────────────────────────────

def _components(names: List[str], adj: Dict[str, set]) -> List[List[str]]:
    seen: set = set()
    comps: List[List[str]] = []
    for s in names:
        if s in seen:
            continue
        comp: List[str] = []
        q = deque([s]); seen.add(s)
        while q:
            u = q.popleft(); comp.append(u)
            for v in adj[u]:
                if v not in seen:
                    seen.add(v); q.append(v)
        comps.append(comp)
    return comps


def trust_dp_conflicts(names: List[str], adj: Dict[str, set], *,
                       rule_validated: bool = True, **gate_kw) -> List[TrustVerdict]:
    """Gate each native-conflict COMPONENT of a double-patterning layer.

    A single conflict EDGE has only one edge-level localizer (BFS), so it cannot be
    independently corroborated -- that would be dishonest. But the two methods genuinely and
    INDEPENDENTLY agree at COMPONENT granularity: combinatorial BFS finds an odd cycle in the
    component, and the linear-algebraic signless-Laplacian finds lambda_min(D+A) > 0 for the
    same component. So the trusted unit is the frustrated component (the native-conflict
    region); its BFS frustrated edges are the localized `support`.

    Witnesses per frustrated component:
      - `bfs_z2`      : the component contains an odd cycle (exact, combinatorial);
      - `spectral`    : lambda_min(D+A) > 0 for the component (independent, linear-algebraic);
      - `openmpl_rule`: the conflict graph uses OpenMPL's validated euclidean-distance rule
                        (broad corroborator of the CONSTRUCTION; only if rule_validated).
    Specificity is IDF over how many of the layer's components are frustrated: if frustration
    is rare it is specific; if every component is frustrated the layer is globally
    over-constrained and a lone component is less individually specific.
    """
    from .dp_conflict import (_lambda_min_signless_dense, _lambda_min_signless_sparse,
                              two_color_conflicts)
    _, _, frustrated = two_color_conflicts(names, adj)

    comps = [c for c in _components(names, adj) if len(c) >= 3]
    n_comps = len(comps) or 1
    comp_index = {id(c): i for i, c in enumerate(comps)}
    node_comp: Dict[str, int] = {u: comp_index[id(c)] for c in comps for u in c}

    # per-component: BFS frustrated edges (localization) + spectral lambda_min (independent).
    bfs_edges: Dict[int, List[str]] = {}
    for (u, v) in frustrated:
        ci = node_comp.get(u)
        if ci is not None:
            bfs_edges.setdefault(ci, []).append(f"{u}--{v}")
    lam_of: Dict[int, float] = {}
    for ci, comp in enumerate(comps):
        lam_of[ci] = (_lambda_min_signless_dense(comp, adj) if len(comp) <= 2000
                      else _lambda_min_signless_sparse(comp, adj))

    bfs_frustrated = {ci for ci in bfs_edges}
    spec_frustrated = {ci for ci, lam in lam_of.items() if lam > 1e-6}
    n_bfs = len(bfs_frustrated) or 1
    n_spec = len(spec_frustrated) or 1

    verdicts: List[TrustVerdict] = []
    for ci in sorted(bfs_frustrated):
        comp = comps[ci]
        ws = [Witness("bfs_z2", 1.0, n_bfs, n_comps)]
        lam = lam_of.get(ci, 0.0)
        if lam > 1e-6:
            ws.append(Witness("spectral", _clamp(min(1.0, lam)), n_spec, n_comps))
        if rule_validated:
            ws.append(Witness("openmpl_rule", 1.0, n_comps, n_comps))
        edges = sorted(bfs_edges[ci])
        item = f"component[{ci}] ({len(comp)} features, {len(edges)} native conflicts)"
        verdicts.append(gate_obstruction(Obstruction(item, ws), support=edges, **gate_kw))
    return verdicts


# ── Track 3A adapter: three-view net-fidelity divergences ───────────────────────────────────

def trust_fidelity_divergences(disagreements: Dict[str, List[str]], n_total_nets: int,
                               **gate_kw) -> List[TrustVerdict]:
    """Gate each divergent net from a `FidelityReport`. Witnesses = the view-PAIRS that flag
    the net; a pair flagging a huge fraction of nets (a global rename/escaping mismatch) gets
    low specificity and cannot, alone, make a net a trusted logical divergence."""
    pair_breadth = {pair: len(nets) for pair, nets in disagreements.items()}
    flags: Dict[str, List[str]] = {}
    for pair, nets in disagreements.items():
        for net in nets:
            flags.setdefault(net, []).append(pair)
    total = max(n_total_nets, 1)
    verdicts: List[TrustVerdict] = []
    for net, pairs in flags.items():
        ws = [Witness(pair, 1.0, pair_breadth[pair], total) for pair in pairs]
        verdicts.append(gate_obstruction(Obstruction(net, ws), **gate_kw))
    return verdicts


def summarize(verdicts: List[TrustVerdict]) -> Dict[str, int]:
    out = {"TRUSTED": 0, "UNCORROBORATED": 0, "HOLLOW": 0}
    for v in verdicts:
        out[v.status] = out.get(v.status, 0) + 1
    return out


def main() -> None:
    print("KOMPOSOS-V | silicon coherence trust gate (Track 3 Step C)")
    print("=" * 70)
    print("A localized obstruction is TRUSTED only if independent, specificity-weighted")
    print("views corroborate it and the rationale grounds -- proposal != verification.\n")

    import os
    # 3B: gate the real flattened-M1 native conflicts.
    gds = "domains/silicon/data/orfs_gcd/results/base/6_final.gds"
    if os.path.exists(gds):
        from .dp_conflict import build_conflict_graph_bbox
        from .gds import gds_features
        names, adj = build_conflict_graph_bbox(gds_features(gds, 11, flatten=True), 700.0)
        vs = trust_dp_conflicts(names, adj)
        s = summarize(vs)
        n_edges = sum(len(v.support) for v in vs if v.trusted)
        print(f"--- 3B: real flattened M1 native-conflict regions (orfs_gcd L11) ---")
        print(f"   {len(vs)} frustrated components gated -> {s}")
        print(f"   trusted regions localize {n_edges} native conflict edges")
        for v in vs[:3]:
            print(f"     [{v.status}] {v.item}  corrob={v.corroboration:.2f}  "
                  f"specific_views={v.n_specific}  grounded={v.grounded}  tier={v.tier}")
    else:
        print("[skip] orfs_gcd GDS absent")

    # 3A: gate the real three-view net divergences.
    base = "domains/silicon/data/orfs_gcd/results/base"
    vp, dp_, sp = f"{base}/6_final.v", f"{base}/6_final.def", f"{base}/6_final.spef"
    if all(os.path.exists(p) for p in (vp, dp_, sp)):
        from .fidelity_coherence import def_view, fidelity_coherence, spef_view, verilog_view
        lef = "domains/silicon/data/openlane/Nangate45.lef"
        v = verilog_view(vp)
        d, _ = def_view(dp_, sp, lef if os.path.exists(lef) else None)
        s_ = spef_view(sp)
        rep = fidelity_coherence(v, d, s_)
        vs = trust_fidelity_divergences(rep.disagreements, rep.n_common_nets)
        print(f"\n--- 3A: real three-view net divergences (orfs_gcd) ---")
        print(f"   {len(vs)} divergent nets gated -> {summarize(vs)}")
    else:
        print("\n[skip] orfs_gcd verilog/def/spef absent")


if __name__ == "__main__":
    main()
