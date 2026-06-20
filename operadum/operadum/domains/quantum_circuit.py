# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Quantum Gate Synthesis -- design verified by linear algebra.

Synthesize a single-qubit gate sequence realizing a target unitary, from a gate
library that omits the target as a primitive (so the design must be composed).
Each operation carries its 2x2 unitary; a synthesized chain's artifact computes
the product, and the SemanticGate accepts the cheapest chain whose product
equals the target up to global phase.

This domain illustrates two manual points at once:
  * "math at the leaf" -- the substrate stays stdlib-only; the numerics
    (2x2 complex matrices) live in this domain's operations and validator, via
    the standard-library `cmath`. A production version would swap in numpy with
    no change to OPERADUM.
  * the no-cloning theorem -- a qubit cannot be copied, which is exactly the
    LINEAR_TOKENS / PROP.can_copy discipline; single-qubit chains never fork, so
    they are linear-sound by construction.
"""

from __future__ import annotations
import cmath
import math
from typing import List, Tuple

from ..core.types import Operation, Spec
from ..core.enrichment import ResourceMonoid, ADDITIVE_COST
from .base import DomainPlugin, GroundTruthCase

# A 2x2 complex matrix as (a, b, c, d) = [[a, b], [c, d]].
Matrix = Tuple[complex, complex, complex, complex]

IDENTITY: Matrix = (1, 0, 0, 1)
_R = 1 / math.sqrt(2)
H: Matrix = (_R, _R, _R, -_R)
X: Matrix = (0, 1, 1, 0)
Y: Matrix = (0, -1j, 1j, 0)
Z: Matrix = (1, 0, 0, -1)
S: Matrix = (1, 0, 0, 1j)
T: Matrix = (1, 0, 0, cmath.exp(1j * math.pi / 4))


def mul(p: Matrix, q: Matrix) -> Matrix:
    """Matrix product p @ q."""
    a, b, c, d = p
    e, f, g, h = q
    return (a * e + b * g, a * f + b * h, c * e + d * g, c * f + d * h)


def phase_equal(p: Matrix, q: Matrix, tol: float = 1e-9) -> bool:
    """True iff p == alpha * q for some global phase alpha (|alpha| = 1)."""
    alpha = None
    for x, y in zip(p, q):
        if abs(y) > tol:
            cand = x / y
            if alpha is None:
                alpha = cand
            elif abs(cand - alpha) > 1e-6:
                return False
        elif abs(x) > tol:
            return False
    if alpha is None:
        return True
    return abs(abs(alpha) - 1.0) < 1e-6


def _gate(name: str, matrix: Matrix) -> Operation:
    """A gate as a unary Qubit -> Qubit operation that left-multiplies its matrix."""
    return Operation(
        name=name, inputs=["Qubit"], output="Qubit", cost={"gates": 1},
        metadata={"gate": name},   # matrix lives in the closure; metadata stays JSON-safe
        _fn=lambda m, _g=matrix: mul(_g, m),
    )


class QuantumCircuitDomain(DomainPlugin):
    """Single-qubit Clifford+T gate-sequence synthesis."""

    name = "quantum-circuit"

    #: The full gate library; specific targets omit themselves to force composition.
    _library = {"H": H, "X": X, "Z": Z, "S": S, "T": T}

    def __init__(self, gates: List[str] = None):
        self._gates = gates or list(self._library)

    def colours(self) -> List[str]:
        return ["Qubit"]

    def operations(self) -> List[Operation]:
        return [_gate(name, self._library[name]) for name in self._gates]

    def resource_algebra(self) -> ResourceMonoid:
        return ADDITIVE_COST   # minimise gate count

    def ground_truth(self) -> List[GroundTruthCase]:
        # Each target is realizable only by composing the (restricted) library.
        return [
            GroundTruthCase(
                name="Z from {H,X,S,T}  (= S then S)",
                spec=Spec(("Qubit",), "Qubit", constraints={"target": Z, "library": ["H", "X", "S", "T"]}),
                buildable=True, min_cost=2.0, note="S(S(Qubit)) since S^2 = Z",
            ),
            GroundTruthCase(
                name="S from {H,X,Z,T}  (= T then T)",
                spec=Spec(("Qubit",), "Qubit", constraints={"target": S, "library": ["H", "X", "Z", "T"]}),
                buildable=True, min_cost=2.0, note="T(T(Qubit)) since T^2 = S",
            ),
            GroundTruthCase(
                name="X from {H,Z,S,T}  (= H Z H)",
                spec=Spec(("Qubit",), "Qubit", constraints={"target": X, "library": ["H", "Z", "S", "T"]}),
                buildable=True, min_cost=3.0, note="H(Z(H(Qubit))) since HZH = X",
            ),
        ]
