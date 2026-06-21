# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""A real learned IR-drop predictor, gated by the trust layer on HELD-OUT measured data.

This is the trust layer applied to a genuine proposer (not a stand-in): a ridge-regression
model that learns a per-tile IR-drop predictor from layout features (cap, fanout, density,
area, demand, distance-from-center), trained on one design and evaluated on a DIFFERENT
one. Two honest questions:

  1. Does learning beat the cheap single-feature baseline (fanout/density ~+0.5-0.6)?
  2. Does it survive the trust gate? The gate accepts the model ONLY if its predictions
     beat a shuffled control on held-out data. An overfit model looks great in-sample and
     is BLOCKED out-of-sample -- exactly the black-box failure the trust layer exists to
     catch (CLAUDE.md: a GNN must demonstrate held-out value and may never gate a verdict).

numpy + stdlib only; the model is proposal-side and never writes to memory or a verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from .ir_scoreboard import _spearman, parse_ir_voltage
from .netlist_bridge import NetlistBridge

FEATURES = ("cap", "fanout", "density", "area", "demand", "distc")
PASS_RHO = 0.30
CONTROL_MAX = 0.20


def _tile_table(def_path: str, spef_path: str, lef_path: str, voltage_path: str,
                supply_v: float, grid: int = 20) -> Tuple[np.ndarray, np.ndarray]:
    """Per-tile feature matrix X (z-scored) and target y (mean IR drop)."""
    pos, drop = parse_ir_voltage(voltage_path, supply_v)
    b = NetlistBridge(def_path, spef_path, lef_path=lef_path)
    inst_cap: Dict[str, float] = {}; inst_fan: Dict[str, float] = {}
    inst_dem: Dict[str, float] = {}; active = set()
    for net in b.nets:
        if not b._is_signal(net):
            continue
        cap = b.caps.get(net.name, 0.0); fo = len(net.conns) - 1
        drv = net.conns[b._driver_index(net)][0]
        inst_cap[drv] = inst_cap.get(drv, 0.0) + cap
        inst_fan[drv] = inst_fan.get(drv, 0.0) + fo
        inst_dem[drv] = inst_dem.get(drv, 0.0) + cap * fo
        active.add(drv)

    xs = [p[0] for p in pos.values()]; ys = [p[1] for p in pos.values()]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    def tile(x, y):
        return (min(grid - 1, int((x - x0) / (x1 - x0 + 1e-9) * grid)),
                min(grid - 1, int((y - y0) / (y1 - y0 + 1e-9) * grid)))

    acc: Dict[Tuple[int, int], Dict[str, float]] = {}
    for inst, (x, y) in pos.items():
        d = acc.setdefault(tile(x, y), {k: 0.0 for k in FEATURES} | {"ir": 0.0, "n": 0})
        d["cap"] += inst_cap.get(inst, 0.0); d["fanout"] += inst_fan.get(inst, 0.0)
        d["demand"] += inst_dem.get(inst, 0.0); d["area"] += b.cell_area(inst)
        d["density"] += 1.0 if inst in active else 0.0
        d["distc"] += ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        d["ir"] += drop.get(inst, 0.0); d["n"] += 1

    rows = [d for d in acc.values() if d["n"]]
    X = np.array([[d[k] / (d["n"] if k == "distc" else 1) for k in FEATURES] for d in rows])
    y = np.array([d["ir"] / d["n"] for d in rows])
    # z-score features within the design so cross-design transfer learns relative patterns
    mu, sd = X.mean(0), X.std(0) + 1e-9
    return (X - mu) / sd, y


def _ridge(X: np.ndarray, y: np.ndarray, lam: float = 1.0) -> np.ndarray:
    Xb = np.hstack([X, np.ones((len(X), 1))])
    A = Xb.T @ Xb + lam * np.eye(Xb.shape[1])
    return np.linalg.solve(A, Xb.T @ y)


def _predict(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    return np.hstack([X, np.ones((len(X), 1))]) @ w


@dataclass
class MLVerdict:
    train: str
    test: str
    ml_rho: float                 # learned model, held-out Spearman vs real IR
    baseline_rho: float           # best single cheap feature, held-out
    in_sample_rho: float          # the model's OWN-design fit (overfit temptation)
    control_rho: float            # held-out vs shuffled target
    beats_baseline: bool
    trusted: bool                 # passes the gate on HELD-OUT data
    reason: str


def evaluate_and_gate(train: Tuple, test: Tuple, seed: int = 0) -> MLVerdict:
    """Train ridge on one design, evaluate + trust-gate on a held-out design."""
    import random
    Xtr, ytr = train[0]; Xte, yte = test[0]
    w = _ridge(Xtr, ytr)
    pred = _predict(Xte, w)
    ml_rho = _spearman(list(pred), list(yte))
    in_sample = _spearman(list(_predict(Xtr, w)), list(ytr))
    base = max(_spearman(list(Xte[:, i]), list(yte)) for i in range(Xte.shape[1]))
    sh = list(yte); random.Random(seed).shuffle(sh)
    control = _spearman(list(pred), sh)
    trusted = ml_rho >= PASS_RHO and abs(control) < CONTROL_MAX
    reason = ("trusted: beats a shuffled control on a held-out design"
              if trusted else
              f"BLOCKED: held-out rho={ml_rho:+.2f} fails the gate (in-sample looked "
              f"{in_sample:+.2f}) - does not generalize")
    return MLVerdict(train[1], test[1], ml_rho, base, in_sample, control,
                     ml_rho > base + 1e-9, trusted, reason)


def main() -> None:
    import os
    designs = {
        "aes": ("domains/silicon/data/orfs_aes/results/nangate45/aes/base",
                "domains/silicon/data/ir_aes/ir_voltage.rpt", 1.1),
        "ibex": ("domains/silicon/data/orfs_ibex/results/nangate45/ibex/base",
                 "domains/silicon/data/ir_ibex/ir_voltage.rpt", 1.1),
    }
    tabs = {}
    for d, (base, volt, vdd) in designs.items():
        if not (os.path.exists(f"{base}/6_final.def") and os.path.exists(volt)):
            print(f"[skip] {d}: artifacts absent"); return
        tabs[d] = (_tile_table(f"{base}/6_final.def", f"{base}/6_final.spef",
                               "domains/silicon/data/openlane/Nangate45.lef", volt, vdd), d)
    print("KOMPOSOS-V | learned IR-drop predictor, trust-gated on held-out data\n" + "=" * 64)
    for tr, te in [("aes", "ibex"), ("ibex", "aes")]:
        v = evaluate_and_gate(tabs[tr], tabs[te])
        mark = "TRUST" if v.trusted else "BLOCK"
        print(f"\n[{mark}] train {v.train} -> test {v.test}")
        print(f"   learned model held-out rho = {v.ml_rho:+.3f}  "
              f"(in-sample {v.in_sample_rho:+.3f})")
        print(f"   cheap baseline held-out rho = {v.baseline_rho:+.3f}  "
              f"-> ML {'beats' if v.beats_baseline else 'does NOT beat'} the cheap signal")
        print(f"   gate: {v.reason}")


if __name__ == "__main__":
    main()
