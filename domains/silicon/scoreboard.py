# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Silicon scoreboard — a falsifiable measure of whether the CHEAP structural triage
signal predicts the EXPENSIVE physical cost.

Mirrors `core/scoreboard.py`: self-improvement (or any analysis) without measurement
optimizes noise. This answers one question with a number:

    Do structural signals rank nets the same way an independent physical target
    does: extracted SPEF capacitance or STA timing criticality?

If yes, the bridge is screening-grade triage: run it in seconds to flag the few nets
worth an expensive tool's attention. If no, that is a real, honest finding (topology
alone is insufficient; you need LEF/placement/STA).

The two sides are genuinely independent measurements:
  predictors (cheap, no SPEF):  neg_curvature (Ollivier-Ricci, pure connectivity),
                                degree (connectivity), fanout (netlist),
                                wirelength (placement coordinates)
  targets (expensive):          SPEF total capacitance per net
                                STA negative slack mapped onto traversed nets

Metrics per predictor:
  spearman  rank correlation with the target (>0 = predicts)
  prec@k    of the top-k nets by predictor, fraction also in the top-k by cap
  control   spearman after SHUFFLING the target — must collapse to ~0, proving the
            signal is real and not an artifact of the metric.

PASS if the best predictor's spearman >= PASS_RHO, the shuffle control < CONTROL_MAX,
and the target is evidence-eligible. Fixture STA can exercise the metric but cannot pass.

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
    driver_area: float        # LEF: driver cell area (drive strength proxy); 0 w/o LEF
    sink_area: float          # LEF: sum of sink cell areas (pin-cap proxy); 0 w/o LEF
    cap: Optional[float]      # SPEF total capacitance; absent for timing-only scoring


def collect_features(bridge: NetlistBridge,
                     require_cap: bool = True) -> List[NetFeatures]:
    """Per-net structural predictors, optionally restricted to nets with SPEF."""
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
        if require_cap and cap is None:
            continue                                   # need the target
        kappas = [kappa.get(frozenset((m.source, m.target))) for m in edges]
        kappas = [k for k in kappas if k is not None]
        if not kappas:
            continue
        wls = [m.metadata.get("wirelength") for m in edges]
        wls = [w for w in wls if w is not None]
        deg = sum(degree.get(n, 0)
                  for m in edges for n in (m.source, m.target))
        driver = edges[0].source                       # star center = driver
        sinks = {m.target for m in edges}
        feats.append(NetFeatures(
            net=net,
            neg_curvature=-min(kappas),
            degree=float(deg),
            fanout=float(edges[0].metadata.get("fanout", len(edges))),
            wirelength=float(max(wls)) if wls else 0.0,
            driver_area=bridge.cell_area(driver),
            sink_area=float(sum(bridge.cell_area(s) for s in sinks)),
            cap=float(cap) if cap is not None else None))
    return feats


# ═══════════════════════════════════════════════════════════════════════════
# Scoring
# ═══════════════════════════════════════════════════════════════════════════

PREDICTORS = ("neg_curvature", "degree", "fanout", "wirelength",
              "driver_area", "sink_area")


@dataclass
class ScoreReport:
    design: str
    n_nets: int
    k: int
    target: str = "spef_capacitance"
    n_positive: int = 0
    evidence_eligible: bool = True
    source_kind: str = "tool"
    source_sha256: str = ""
    spearman: Dict[str, float] = field(default_factory=dict)
    prec_at_k: Dict[str, float] = field(default_factory=dict)
    control_rho: float = 0.0

    @property
    def best(self) -> Tuple[str, float]:
        if not self.spearman:
            return ("none", 0.0)
        return max(self.spearman.items(), key=lambda kv: kv[1])

    @property
    def metric_passed(self) -> bool:
        _, rho = self.best
        return (self.n_nets >= 5 and rho >= PASS_RHO
                and abs(self.control_rho) < CONTROL_MAX)

    @property
    def passed(self) -> bool:
        return self.metric_passed and self.evidence_eligible

    def render(self) -> str:
        name, rho = self.best
        head = ("NON-EVIDENCE" if not self.evidence_eligible
                else "PASS" if self.passed else "FAIL")
        lines = [f"[{head}] {self.design}  (n={self.n_nets} nets, k={self.k})",
                 f"   target: {self.target}  positive_nets={self.n_positive}",
                 f"   best predictor: {name}  spearman={rho:+.3f}",
                 f"   shuffle control: spearman={self.control_rho:+.3f} "
                 f"(must be < {CONTROL_MAX})",
                 "   predictor            spearman   prec@k"]
        for p in PREDICTORS:
            lines.append(f"     {p:<18} {self.spearman.get(p, 0.0):+.3f}     "
                         f"{self.prec_at_k.get(p, 0.0):.2f}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, object]:
        name, rho = self.best
        return {
            "design": self.design,
            "target": self.target,
            "n_nets": self.n_nets,
            "n_positive": self.n_positive,
            "k": self.k,
            "best_predictor": name,
            "best_spearman": rho,
            "shuffle_control": self.control_rho,
            "metric_passed": self.metric_passed,
            "passed": self.passed,
            "evidence_eligible": self.evidence_eligible,
            "source_kind": self.source_kind,
            "source_sha256": self.source_sha256,
            "spearman": self.spearman,
            "precision_at_k": self.prec_at_k,
        }


def _score_features(features: List[NetFeatures], target_values: List[float],
                    *, design: str, target: str, seed: int,
                    k: Optional[int] = None, evidence_eligible: bool = True,
                    source_kind: str = "tool", source_sha256: str = "") -> ScoreReport:
    if len(features) == len(target_values):
        ordered = sorted(zip(features, target_values), key=lambda pair: pair[0].net)
        features = [pair[0] for pair in ordered]
        target_values = [pair[1] for pair in ordered]

    n = len(features)
    n_positive = sum(value > 0 for value in target_values)
    chosen_k = k if k is not None else max(1, min(10, n // 3))
    rep = ScoreReport(
        design=design,
        n_nets=n,
        k=chosen_k,
        target=target,
        n_positive=n_positive,
        evidence_eligible=evidence_eligible,
        source_kind=source_kind,
        source_sha256=source_sha256,
    )
    if n < 3 or len(target_values) != n or n_positive == 0:
        return rep

    for predictor in PREDICTORS:
        values = [getattr(feature, predictor) for feature in features]
        rep.spearman[predictor] = spearman(values, target_values)
        rep.prec_at_k[predictor] = precision_at_k(values, target_values, chosen_k)

    best_values = [getattr(feature, rep.best[0]) for feature in features]
    shuffled = list(target_values)
    random.Random(seed).shuffle(shuffled)
    rep.control_rho = spearman(best_values, shuffled)
    return rep


def score_layout(def_path: str, spef_path: str, lef_path: Optional[str] = None,
                 design: Optional[str] = None, seed: int = 0) -> ScoreReport:
    bridge = NetlistBridge(def_path, spef_path, lef_path=lef_path)
    bridge.load()
    feats = collect_features(bridge)
    design = design or os.path.basename(def_path)
    caps = [float(feature.cap) for feature in feats if feature.cap is not None]
    canonical_fixture = (
        os.path.normcase(os.path.abspath(def_path)) ==
        os.path.normcase(os.path.abspath(SAMPLE_DEF)) and
        os.path.normcase(os.path.abspath(spef_path)) ==
        os.path.normcase(os.path.abspath(SAMPLE_SPEF)))
    return _score_features(
        feats, caps, design=design, target="spef_capacitance", seed=seed,
        evidence_eligible=not canonical_fixture,
        source_kind="fixture" if canonical_fixture else "measured_proxy")


def score_timing(def_path: str, sta_path: str,
                 spef_path: Optional[str] = None,
                 lef_path: Optional[str] = None,
                 design: Optional[str] = None, seed: int = 0,
                 sta_source_kind: str = "unverified",
                 sta_context_paths: Optional[Dict[str, str]] = None,
                 sta_tool: str = "OpenSTA/OpenROAD report_checks") -> ScoreReport:
    """Score structural predictors against per-net STA negative slack."""
    from .sta import critical_nets, load_sta

    bridge = NetlistBridge(def_path, spef_path, lef_path=lef_path)
    bridge.load()
    report = load_sta(
        sta_path, source_kind=sta_source_kind,
        context_paths=sta_context_paths, tool=sta_tool)
    criticality = critical_nets(report.paths, bridge)
    features = collect_features(bridge, require_cap=False)
    target_values = [criticality.get(feature.net, 0.0) for feature in features]
    k = max(1, min(10, len(criticality)))
    return _score_features(
        features,
        target_values,
        design=design or os.path.basename(def_path),
        target="sta_negative_slack",
        seed=seed,
        k=k,
        evidence_eligible=report.is_evidence,
        source_kind=report.source_kind,
        source_sha256=report.sha256,
    )


def _real(path: str) -> str:
    return os.path.join(os.path.dirname(SAMPLE_DEF), "..", "data", "openlane", path)


def main() -> None:
    print("KOMPOSOS-V | silicon scoreboard")
    print("=" * 60)
    print("Q: does cheap structural triage predict expensive SPEF cost?\n")

    designs = [("sample tiny_core", SAMPLE_DEF, SAMPLE_SPEF, None)]
    for name, d, s, lef in [("real gcd", "gcd.def", "gcd.spefok", None),
                            ("real 45_gcd (+LEF)", "45_gcd.def", "45_gcd.spefok",
                             "Nangate45.lef")]:
        dp, sp = _real(d), _real(s)
        lp = _real(lef) if lef else None
        if os.path.exists(dp) and os.path.exists(sp):
            designs.append((name, dp, sp, lp if (lp and os.path.exists(lp)) else None))

    any_pass = False
    for name, dp, sp, lp in designs:
        rep = score_layout(dp, sp, lef_path=lp, design=name)
        print(rep.render()); print()
        any_pass = any_pass or rep.passed

    print("Predictors are computed WITHOUT SPEF; the target IS SPEF. A positive")
    print("spearman with a near-zero shuffle control = the structural signal is real.")
    if not any_pass:
        print("\nNo design passed: topology alone underpredicts here — add LEF/placement"
              " (wirelength) or STA ground truth. That is an honest result, not a bug.")


if __name__ == "__main__":
    main()
