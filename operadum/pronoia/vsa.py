"""
PRONOIA L0 — Vector Symbolic Architecture (hyperdimensional computing).

Represent every concept as a high-dimensional bipolar hypervector (+/-1). Build
structure with algebra:

  - bind(a, b)   = elementwise product  : ties a role to a filler; self-inverse
                   (bind(bind(a,b), b) == a), so unbind = bind again.
  - bundle(*vs)  = elementwise majority : superposes; the result is *similar* to
                   each ingredient (holographic / associative).
  - permute(v,k) = cyclic shift         : protects / orders (sequences).
  - similarity   = normalised dot in [-1, 1].

Two random hypervectors are near-orthogonal, so unrelated concepts don't
interfere. That gives one-shot learning, analogy, and holographic associative
memory — compositional reasoning as vector arithmetic, no backprop, fully
inspectable (unbind to read a structure back out).

Depends only on numpy.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np


class HDComputing:
    """A hyperdimensional computing space with an item ("cleanup") memory."""

    def __init__(self, dim: int = 10000, seed: int = 0):
        self.dim = int(dim)
        self.rng = np.random.default_rng(seed)
        self.memory: Dict[str, np.ndarray] = {}  # name -> atomic hypervector

    # ---- atoms --------------------------------------------------------- #

    def random_hv(self) -> np.ndarray:
        return self.rng.choice(np.array([-1, 1], dtype=np.int8), size=self.dim)

    def symbol(self, name: str) -> np.ndarray:
        """Get (or create) the atomic hypervector for a named concept."""
        if name not in self.memory:
            self.memory[name] = self.random_hv()
        return self.memory[name]

    # ---- algebra ------------------------------------------------------- #

    def bind(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return (a * b).astype(np.int8)

    def bundle(self, *vs: np.ndarray) -> np.ndarray:
        """Elementwise majority vote (ties broken randomly)."""
        s = np.sum(np.stack(vs), axis=0)
        out = np.sign(s).astype(np.int8)
        ties = out == 0
        if ties.any():
            out[ties] = self.rng.choice(
                np.array([-1, 1], dtype=np.int8), size=int(ties.sum())
            )
        return out

    def permute(self, v: np.ndarray, k: int = 1) -> np.ndarray:
        return np.roll(v, k)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        # int64 accumulation: a length-`dim` dot of +/-1 overflows int8.
        return float(np.dot(a.astype(np.int64), b.astype(np.int64)) / self.dim)

    # ---- cleanup memory ------------------------------------------------ #

    def cleanup(self, v: np.ndarray, among: Optional[Sequence[str]] = None) -> str:
        """Nearest named atom to `v` (associative recall)."""
        names = list(among) if among is not None else list(self.memory)
        v64 = v.astype(np.int64)
        return max(names, key=lambda n: float(np.dot(v64, self.symbol(n).astype(np.int64))))

    # ---- convenience: structured records ------------------------------- #

    def encode_record(self, fields: Dict[str, str]) -> np.ndarray:
        """Encode a {role: filler} record as a bundle of role*filler bindings."""
        parts = [self.bind(self.symbol(role), self.symbol(filler))
                 for role, filler in fields.items()]
        return self.bundle(*parts)

    def query_field(self, record: np.ndarray, role: str,
                    among: Sequence[str]) -> str:
        """Recover the filler bound to `role` in a record (unbind + cleanup)."""
        return self.cleanup(self.bind(record, self.symbol(role)), among=among)

    def encode_set(self, items: Iterable[str]) -> np.ndarray:
        """Encode an unordered set of concepts as their bundle."""
        return self.bundle(*[self.symbol(i) for i in items])
