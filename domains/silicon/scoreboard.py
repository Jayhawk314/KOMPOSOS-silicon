# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Silicon scoreboard — a falsifiable measure of whether the CHEAP structural triage
signal predicts the EXPENSIVE physical cost.

Mirrors `core/scoreboard.py`: self-improvement (or any analysis) without measurement
optimizes noise. This answers one question with a number:

    Do the topology-only signals (computed WITHOUT the parasitic extraction) rank
    nets the same way the physically-extracted SPEF capacitance does?

If yes, the bridge is screening-grade triage: run it in seconds to flag the few nets
worth an expensive tool's attention. If no, that is a real, honest finding (topology
alone is insufficient; you need LEF/placement/STA).

The two sides are genuinely independent measurements:
  predictors (cheap, no SPEF):  neg_curvature (Ollivier-Ricci, pure connectivity),
                                degree (connectivity), fanout (netlist),
                                wirelength (placement coordinates)
  target (expensive):           SPEF total capacitance per net

Metrics per predictor:
  spearman  rank correlation with the target (>0 = predicts)
  prec@k    of the top-k nets by predictor, fraction also in the top-k by cap
  control   spearman after SHUFFLING the target — must collapse to ~0, proving the
            signal is real and not an artifact of the metric.

PASS if the best predictor's spearman >= PASS_RHO and the shuffle control < CONTROL_MAX.

Run:
    python -m domains.silicon.scoreboard                 # sample + real designs if present
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .flow_geometry import edge_curvatures
from .netlist_bridge import NetlistBridge, SAMPLE_DEF, SAMPLE_SPEF

PASS_RHO = 0.30          # a predictor is screening-grade above this rank correlation
CONTROL_MAX = 0.20       # the shuffled control must stay below this


# ═══════════════════════════════════════════════════════════════════════════
# Stats (numpy + stdlib only — no scipy)
# ═══════════════════════════════════════════════════════════════════════════

def _rankdata(a: np.ndarray) -> np.ndarray:
    """Average ranks (ties shared), like scipy.stats.rankdata."""
    a = np.asarray(a, dtype=float)
    order = a.argsort()
    ranks = np.empty(len(a), dtype=float)
    ranks[order] = np.arange(1, len(a) + 1, dtype=float)
    sa = a[order]
    i = 0
    while i < len(sa):
        j = i
        while j + 1 < len(sa) and sa[j + 1] == sa[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    return ranks


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, float) - np.mean(x)
    y = np.asarray(y, float) - np.mean(y)
    denom = np.sqrt(float((x * x).sum()) * float((y * y).sum()))
    return float((x * y).sum() / denom) if denom > 0 else 0.0


def spearman(x: List[float], y: List[float]) -> float:
    if len(x) < 3:
        return 0.0
    return _pearson(_rankdata(np.asarray(x)), _rankdata(np.asarray(y)))


def precision_at_k(pred: List[float], target: List[float], k: int) -> float:
    if k <= 0 or k > len(pred):
        return 0.0
    pk = set(np.argsort(pred)[::-1][:k].tolist())
    tk = set(np.argsort(target)[::-1][:k].tolist())
    return len(pk & tk) / k


# ═══════════════════════════════════════════════════════════════════════════
# Feature collection (per net)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class NetFeatures:
    net: str
    neg_curvature: float      # -min(kappa over the net's edges); topology only
    degree: float             # sum of endpoint degrees; topology only
    fanout: float             # netlist
    wirelength: float         # max edge length (microns) from placement; 0 if no coords
    cap: float                # SPEF total capacitance (the target)


def collect_features(bridge: NetlistBridge) -> List[NetFeatures]:
    """Per-net cheap predictors + the SPEF cap target, for nets that have both."""
    cat = bridge.category
    kappa = {frozenset((s, t)): k for s, t, k in edge_curvatures(cat)}

    degree: Dict[str, int] = {}
    for m in cat.morphisms():
        degree[m.source] = degree.get(m.source, 0) + 1
        degree[m.target] = degree.get(m.target, 0) + 1

    # group morphisms by net
    by_net: Dict[str, list] = {}
    for m in cat.morphisms():
        by_net.setdefault(m.metadata.get("net", "?"), []).append(m)

    feats: List[NetFeatures] = []
    for net, edges in by_net.items():
        cap = bridge.caps.get(net)
        if cap is None:
            continue                                   # need the target
        kappas = [kappa.get(frozenset((m.source, m.target))) for m in edges]
        kappas = [k for k in kappas if k is not None]
        if not kappas:
            continue
        wls = [m.metadata.get("wirelength") for m in edges]
        wls = [w for w in wls if w is not None]
        deg = sum(degree.get(n, 0)
                  for m in edges for n in (m.source, m.target))
        feats.append(NetFeatures(
            net=net,
            neg_curvature=-min(kappas),
            degree=float(deg),
            fanout=float(edges[0].metadata.get("fanout", len(edges))),
            wirelength=float(max(wls)) if wls else 0.0,
            cap=float(cap)))
    return feats


# ═══════════════════════════════════════════════════════════════════════════
# Scoring
# ═══════════════════════════════════════════════════════════════════════════

PREDICTORS = ("neg_curvature", "degree", "fanout", "wirelength")


@dataclass
class ScoreReport:
    design: str
    n_nets: int
    k: int
    spearman: Dict[str, float] = field(default_factory=dict)
    prec_at_k: Dict[str, float] = field(default_factory=dict)
    control_rho: float = 0.0

    @property
    def best(self) -> Tuple[str, float]:
        if not self.spearman:
            return ("none", 0.0)
        return max(self.spearman.items(), key=lambda kv: kv[1])

    @property
    def passed(self) -> bool:
        _, rho = self.best
        return (self.n_nets >= 5 and rho >= PASS_RHO
                and abs(self.control_rho) < CONTROL_MAX)

    def render(self) -> str:
        name, rho = self.best
        head = "PASS" if self.passed else "FAIL"
        lines = [f"[{head}] {self.design}  (n={self.n_nets} nets, k={self.k})",
                 f"   best predictor: {name}  spearman={rho:+.3f}",
                 f"   shuffle control: spearman={self.control_rho:+.3f} "
                 f"(must be < {CONTROL_MAX})",
                 "   predictor            spearman   prec@k"]
        for p in PREDICTORS:
            lines.append(f"     {p:<18} {self.spearman.get(p, 0.0):+.3f}     "
                         f"{self.prec_at_k.get(p, 0.0):.2f}")
        return "\n".join(lines)


def score_layout(def_path: str, spef_path: str,
                 design: Optional[str] = None, seed: int = 0) -> ScoreReport:
    bridge = NetlistBridge(def_path, spef_path)
    bridge.load()
    feats = collect_features(bridge)
    design = design or os.path.basename(def_path)

    cap = [f.cap for f in feats]
    n = len(feats)
    k = max(1, min(10, n // 3))
    rep = ScoreReport(design=design, n_nets=n, k=k)
    if n < 3:
        return rep

    for p in PREDICTORS:
        pred = [getattr(f, p) for f in feats]
        rep.spearman[p] = spearman(pred, cap)
        rep.prec_at_k[p] = precision_at_k(pred, cap, k)

    # negative control: shuffle the target, re-correlate the best predictor
    best_pred = [getattr(f, rep.best[0]) for f in feats]
    shuffled = list(cap)
    random.Random(seed).shuffle(shuffled)
    rep.control_rho = spearman(best_pred, shuffled)
    return rep


def _real(path: str) -> str:
    return os.path.join(os.path.dirname(SAMPLE_DEF), "..", "data", "openlane", path)


def main() -> None:
    print("KOMPOSOS-V | silicon scoreboard")
    print("=" * 60)
    print("Q: does cheap structural triage predict expensive SPEF cost?\n")

    designs = [("sample tiny_core", SAMPLE_DEF, SAMPLE_SPEF)]
    for name, d, s in [("real gcd", "gcd.def", "gcd.spefok"),
                       ("real 45_gcd", "45_gcd.def", "45_gcd.spefok")]:
        dp, sp = _real(d), _real(s)
        if os.path.exists(dp) and os.path.exists(sp):
            designs.append((name, dp, sp))

    any_pass = False
    for name, dp, sp in designs:
        rep = score_layout(dp, sp, design=name)
        print(rep.render()); print()
        any_pass = any_pass or rep.passed

    print("Predictors are computed WITHOUT SPEF; the target IS SPEF. A positive")
    print("spearman with a near-zero shuffle control = the structural signal is real.")
    if not any_pass:
        print("\nNo design passed: topology alone underpredicts here — add LEF/placement"
              " (wirelength) or STA ground truth. That is an honest result, not a bug.")


if __name__ == "__main__":
    main()
