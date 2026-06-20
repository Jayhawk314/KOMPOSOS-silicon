"""
PRONOIA L4 — Tsetlin Machine (interpretable rule learning, no gradients).

A Tsetlin Machine learns predictions as votes from propositional **clauses** —
conjunctions (ANDs) of literals (a feature or its negation). Each literal in each
clause is governed by a Tsetlin automaton: a finite-state machine nudged toward
"include" or "exclude" by simple reward/penalty feedback. No backprop, no floats
in the model — and the learned clauses are human-readable if-then rules.

Reference: Granmo, "The Tsetlin Machine" (2018). This is a compact, faithful
2-class implementation (Type I / Type II feedback, specificity s, threshold T).

Depends only on numpy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

import numpy as np


@dataclass(frozen=True)
class Clause:
    polarity: int           # +1 votes for class 1, -1 votes for class 0
    literals: List[str]     # included literals (a conjunction); empty = always-on


class TsetlinMachine:
    def __init__(
        self,
        n_features: int,
        n_clauses: int = 20,
        s: float = 3.9,
        T: int = 15,
        n_states: int = 100,
        feature_names: Optional[Sequence[str]] = None,
        seed: int = 0,
    ):
        self.F = n_features
        self.C = n_clauses
        self.s = float(s)
        self.T = int(T)
        self.N = int(n_states)
        self.rng = np.random.default_rng(seed)
        self.feature_names = list(feature_names) if feature_names else [
            f"x{i}" for i in range(n_features)
        ]
        # Half the clauses vote for class 1 (+), half for class 0 (-).
        self.polarity = np.array([1 if j % 2 == 0 else -1 for j in range(self.C)])
        # 2F literals: x_0..x_{F-1}, then NOT x_0..NOT x_{F-1}.
        # Init each automaton just around the include/exclude boundary.
        self.ta = self.rng.choice(
            [self.N, self.N + 1], size=(self.C, 2 * self.F)
        ).astype(np.int32)

    # ---- literals & clause evaluation ---------------------------------- #

    def _literals(self, x: np.ndarray) -> np.ndarray:
        return np.concatenate([x, 1 - x])  # (2F,)

    def _clause_outputs(self, L: np.ndarray) -> np.ndarray:
        include = self.ta > self.N                     # (C, 2F)
        violated = include & (L == 0)[None, :]         # an included literal is false
        return (~violated.any(axis=1)).astype(np.int8)  # vacuous (empty) -> 1

    # ---- feedback ------------------------------------------------------ #

    def _type_i(self, j: int, L: np.ndarray, cj: int) -> None:
        ta = self.ta[j]
        r = self.rng.random(2 * self.F)
        if cj == 1:
            inc = (L == 1) & (r < (self.s - 1) / self.s)   # reinforce true literals
            dec = (L == 0) & (r < 1.0 / self.s)            # erase false literals
            ta[inc] = np.minimum(2 * self.N, ta[inc] + 1)
            ta[dec] = np.maximum(1, ta[dec] - 1)
        else:
            dec = r < 1.0 / self.s
            ta[dec] = np.maximum(1, ta[dec] - 1)

    def _type_ii(self, j: int, L: np.ndarray, cj: int) -> None:
        # Combat false positives: make a firing clause specific by including a
        # currently-excluded literal that is false for this input.
        if cj == 1:
            ta = self.ta[j]
            mask = (L == 0) & (ta <= self.N)
            ta[mask] = np.minimum(2 * self.N, ta[mask] + 1)

    # ---- train / predict ----------------------------------------------- #

    def fit(self, X: np.ndarray, y: np.ndarray, epochs: int = 200) -> "TsetlinMachine":
        X = np.asarray(X, dtype=np.int8)
        y = np.asarray(y, dtype=np.int8)
        T = self.T
        for _ in range(epochs):
            for i in self.rng.permutation(len(X)):
                L = self._literals(X[i])
                c = self._clause_outputs(L)
                v = int(np.clip(np.sum(self.polarity * c), -T, T))
                target = y[i]
                p = (T - v) / (2 * T) if target == 1 else (T + v) / (2 * T)
                act = self.rng.random(self.C) < p
                for j in np.nonzero(act)[0]:
                    pol = self.polarity[j]
                    type_i = (target == 1 and pol == 1) or (target == 0 and pol == -1)
                    if type_i:
                        self._type_i(j, L, int(c[j]))
                    else:
                        self._type_ii(j, L, int(c[j]))
        return self

    def _votes(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=np.int8)
        out = np.empty(len(X), dtype=int)
        for i in range(len(X)):
            c = self._clause_outputs(self._literals(X[i]))
            out[i] = int(np.sum(self.polarity * c))
        return out

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self._votes(X) >= 0).astype(int)

    def score(self, X: np.ndarray, y: np.ndarray) -> float:
        return float(np.mean(self.predict(X) == np.asarray(y)))

    # ---- interpretability ---------------------------------------------- #

    def clauses(self, polarity: Optional[int] = None) -> List[Clause]:
        """Return the learned clauses as readable conjunctions of literals."""
        out: List[Clause] = []
        for j in range(self.C):
            if polarity is not None and self.polarity[j] != polarity:
                continue
            lits: List[str] = []
            for k in range(2 * self.F):
                if self.ta[j, k] > self.N:  # included
                    if k < self.F:
                        lits.append(self.feature_names[k])
                    else:
                        lits.append(f"NOT {self.feature_names[k - self.F]}")
            out.append(Clause(int(self.polarity[j]), lits))
        return out
