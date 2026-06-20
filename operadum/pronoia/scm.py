"""
PRONOIA L3 — Structural Causal Models (predict under intervention).

A SCM is a DAG of variables, each with a structural equation
`X_i = f_i(parents(X_i), noise)`. Two query types:

  - OBSERVE:    sample the joint distribution (what we passively see).
  - INTERVENE:  do(X = x) — replace X's equation by the constant x, CUT its
                incoming edges, and propagate. This is what "predict really well
                in the world" needs, because it answers "what if WE set X?",
                not "what tends to co-occur with X?".

When a confounder drives both treatment and outcome, the observed association
`E[Y | X=1] - E[Y | X=0]` is biased, but `E[Y | do(X=1)] - E[Y | do(X=0)]` is the
true causal effect — and the backdoor-adjustment formula recovers it from purely
observational data. That gap (observation vs intervention) is why causal models
survive distribution shift when correlational ones do not.

Depends only on numpy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np

# A structural equation: (parent_data, rng, n) -> array of length n.
StructuralFn = Callable[[Dict[str, np.ndarray], np.random.Generator, int], np.ndarray]


@dataclass
class _Var:
    name: str
    parents: List[str]
    fn: StructuralFn


class SCM:
    """A structural causal model. Add variables in topological order."""

    def __init__(self) -> None:
        self._vars: List[_Var] = []
        self._names: set = set()

    def add(self, name: str, parents: Sequence[str], fn: StructuralFn) -> "SCM":
        for p in parents:
            if p not in self._names:
                raise ValueError(f"parent {p!r} must be added before {name!r}")
        self._vars.append(_Var(name, list(parents), fn))
        self._names.add(name)
        return self

    # ----------------------------------------------------------------- #

    def sample(self, n: int, seed: int = 0) -> Dict[str, np.ndarray]:
        """Ancestral sampling of the joint distribution."""
        rng = np.random.default_rng(seed)
        data: Dict[str, np.ndarray] = {}
        for v in self._vars:
            data[v.name] = np.asarray(v.fn(data, rng, n))
        return data

    def do(self, interventions: Dict[str, float]) -> "SCM":
        """Return a new SCM with each intervened variable clamped to a constant
        (its incoming edges cut)."""
        m = SCM()
        for v in self._vars:
            if v.name in interventions:
                c = float(interventions[v.name])
                m.add(v.name, [], (lambda d, r, n, _c=c: np.full(n, _c)))
            else:
                m.add(v.name, v.parents, v.fn)
        return m

    # ----------------------------------------------------------------- #

    def causal_effect(
        self, treatment: str, outcome: str,
        hi: float = 1.0, lo: float = 0.0, n: int = 20000, seed: int = 0,
    ) -> float:
        """Average causal effect E[Y|do(T=hi)] - E[Y|do(T=lo)] (ground truth)."""
        y_hi = self.do({treatment: hi}).sample(n, seed)[outcome].mean()
        y_lo = self.do({treatment: lo}).sample(n, seed + 1)[outcome].mean()
        return float(y_hi - y_lo)

    def observational_effect(
        self, treatment: str, outcome: str, n: int = 20000, seed: int = 0,
    ) -> float:
        """Naive association E[Y|T=hi] - E[Y|T=lo] (biased under confounding)."""
        d = self.sample(n, seed)
        t, y = d[treatment], d[outcome]
        hi = y[t == t.max()].mean()
        lo = y[t == t.min()].mean()
        return float(hi - lo)

    def backdoor_effect(
        self, treatment: str, outcome: str, adjust: Sequence[str],
        n: int = 20000, seed: int = 0,
    ) -> float:
        """Adjustment formula: sum_z P(z) [E(Y|T=hi,z) - E(Y|T=lo,z)].
        Recovers the causal effect from observational data given a valid
        adjustment set `adjust` (one that blocks the back-door paths)."""
        d = self.sample(n, seed)
        t, y = d[treatment], d[outcome]
        thi, tlo = t.max(), t.min()
        Z = np.stack([d[a] for a in adjust], axis=1) if adjust else np.zeros((n, 1))
        effect = 0.0
        strata, counts = np.unique(Z, axis=0, return_counts=True)
        for z, cnt in zip(strata, counts):
            in_z = np.all(Z == z, axis=1)
            hi = y[in_z & (t == thi)]
            lo = y[in_z & (t == tlo)]
            if len(hi) and len(lo):
                effect += (cnt / n) * (hi.mean() - lo.mean())
        return float(effect)
