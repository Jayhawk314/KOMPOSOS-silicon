"""
PRONOIA L1 — sheaf contradiction probe (evidence fusion + inconsistency alarm).

A cellular sheaf assigns each node a stalk and each edge a restriction map, then
asks: is there a global assignment consistent with every local constraint?

  - H^0 (global sections) = ker(L)         : the consistent assignment (a prediction)
  - H^1 (obstruction)     = min energy > 0  : the disagreement that CANNOT be glued
                                              away = a measurable "these sources
                                              can't all be right" signal.

This prototype uses the **scalar (rank-1) sheaf**: each node carries one number,
each edge asserts a signed relation x_v = sign * x_u with a confidence weight.
That is exactly Harary's signed-graph balance, the simplest cellular sheaf. The
sheaf Laplacian L = sum_e w_e b_e b_e^T with b_e = e_v - sign * e_u; the smallest
eigenvalue of L is the global inconsistency (0 iff the signed graph is balanced),
and the per-edge residual of the minimising assignment localizes the
contradiction.

Higher-rank stalks (vector restriction maps, learned from evidence) are the
general version and the next step; the scalar case is enough to prove the alarm
fires on planted contradictions and stays quiet on consistent evidence.

Depends only on numpy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np


@dataclass(frozen=True)
class SheafEdge:
    u: str
    v: str
    sign: int            # +1 = agrees/co-directional, -1 = opposes
    weight: float = 1.0  # confidence


@dataclass(frozen=True)
class ContradictionReport:
    inconsistency: float                       # H^1 proxy: min normalised disagreement
    consistent: bool                           # inconsistency ~ 0 ?
    edge_residuals: List[Tuple[SheafEdge, float]]  # sorted worst-first
    assignment: Dict[str, float]               # the minimal-disagreement section


class Sheaf:
    """Scalar cellular sheaf over a signed, weighted graph."""

    def __init__(self) -> None:
        self._nodes: List[str] = []
        self._index: Dict[str, int] = {}
        self._edges: List[SheafEdge] = []

    def add_node(self, name: str) -> None:
        if name not in self._index:
            self._index[name] = len(self._nodes)
            self._nodes.append(name)

    def add_edge(self, u: str, v: str, sign: int, weight: float = 1.0) -> None:
        if sign not in (-1, 1):
            raise ValueError("sign must be +1 (agrees) or -1 (opposes)")
        if weight <= 0:
            raise ValueError("weight must be positive")
        self.add_node(u)
        self.add_node(v)
        self._edges.append(SheafEdge(u, v, sign, float(weight)))

    # ----------------------------------------------------------------- #

    def laplacian(self) -> np.ndarray:
        """Sheaf Laplacian L = sum_e w_e b_e b_e^T, b_e = e_v - sign * e_u.

        Built entrywise in O(E): for b = e_v - s e_u, the rank-1 term b b^T has
        (v,v)=(u,u)=1, (u,v)=(v,u)=-s. Scales to large graphs (no per-edge n^2).
        """
        n = len(self._nodes)
        L = np.zeros((n, n))
        for e in self._edges:
            iu, iv = self._index[e.u], self._index[e.v]
            w, s = e.weight, e.sign
            L[iv, iv] += w
            L[iu, iu] += w
            L[iv, iu] += -s * w
            L[iu, iv] += -s * w
        return L

    def probe(self) -> ContradictionReport:
        """Find the minimal-disagreement assignment and localize contradictions."""
        n = len(self._nodes)
        if n == 0:
            return ContradictionReport(0.0, True, [], {})
        L = self.laplacian()
        # min_{||x||=1} x^T L x  = smallest eigenvalue (Rayleigh quotient).
        vals, vecs = np.linalg.eigh(L)
        inconsistency = float(max(0.0, vals[0]))
        x = vecs[:, 0]
        # Fix gauge/sign for readability.
        if np.sum(x) < 0:
            x = -x

        residuals: List[Tuple[SheafEdge, float]] = []
        for e in self._edges:
            iu, iv = self._index[e.u], self._index[e.v]
            disagreement = x[iv] - e.sign * x[iu]
            residuals.append((e, float(e.weight * disagreement * disagreement)))
        residuals.sort(key=lambda er: er[1], reverse=True)

        assignment = {name: float(x[self._index[name]]) for name in self._nodes}
        # "Consistent" = balanced signed graph: a near-zero-energy global section.
        consistent = inconsistency < 1e-8
        return ContradictionReport(
            inconsistency=inconsistency,
            consistent=consistent,
            edge_residuals=residuals,
            assignment=assignment,
        )
