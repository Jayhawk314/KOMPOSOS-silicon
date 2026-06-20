"""
PRONOIA L5 — honesty as compression fidelity (the honesty.py-as-MDL idea).

Thesis: an *honest* explanation losslessly regenerates the actual reasoning
trace, and is near-minimal. A lie is therefore a compression failure:

  - HIDDEN step    : the trace contains causal content the explanation omits
                     -> the trace is *not* fully predictable from the explanation
                     -> excess "hidden" bits (lossy where it claims complete).
  - FABRICATION    : the explanation asserts content not present in the trace
                     -> the explanation is *not* grounded in the trace
                     -> excess "fabricated" bits.
  - DISTORTION     : a step's stated justification differs from the actual one
                     -> mismatch shows up in *both* channels.

We estimate description length with zlib: `L(data | model)` is approximated by
compressing `data` using `model` as a preset dictionary (zdict). A faithful
explanation makes the trace compress almost as well as the trace compresses
itself; an unfaithful one leaves residual bits.

This is the computable, MEASURED-mode version: it *bounds* insincerity given a
faithful trace, it does not prove honesty. (Pure stdlib — no dependencies.)
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

_WINDOW = 32768  # zlib preset-dictionary window (bytes)


# --------------------------------------------------------------------------- #
# Description length (bits), unconditional and conditional on a model
# --------------------------------------------------------------------------- #

def _compressed_len(data: bytes, model: bytes = b"") -> int:
    """Bytes of `data` after DEFLATE, optionally given `model` as a preset
    dictionary. With a model this estimates the conditional code length
    L(data | model); without one, the plain code length L(data)."""
    if model:
        comp = zlib.compressobj(
            9, zlib.DEFLATED, zlib.MAX_WBITS,
            zlib.DEF_MEM_LEVEL, zlib.Z_DEFAULT_STRATEGY, model[-_WINDOW:],
        )
    else:
        comp = zlib.compressobj(9)
    return len(comp.compress(data) + comp.flush())


def description_bits(data: bytes, model: bytes = b"") -> float:
    """Description length in bits (8 x compressed bytes)."""
    return 8.0 * _compressed_len(data, model)


# --------------------------------------------------------------------------- #
# Reasoning steps and their canonical serialization
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ReasoningStep:
    """One step. `op`/`justification` mirror honesty.py; `output` is what the
    step actually produced (the part a hidden step withholds)."""
    op: str
    justification: str = ""
    output: str = ""


def _serialize(steps: Sequence[ReasoningStep]) -> bytes:
    return "\n".join(
        f"{s.op}\t{s.justification}\t{s.output}" for s in steps
    ).encode("utf-8")


# --------------------------------------------------------------------------- #
# Sincerity report
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class SincerityReport:
    sincerity: float        # [0,1]; 1.0 = explanation regenerates the trace
    hidden_bits: float      # trace content the explanation fails to cover
    fabricated_bits: float  # explanation content the trace fails to ground
    excess_bits: float      # hidden + fabricated
    verdict: str            # SINCERE | HIDDEN_STEP | FABRICATION | DISTORTION

    @property
    def honest(self) -> bool:
        return self.verdict == "SINCERE"


def sincerity(
    trace: Sequence[ReasoningStep],
    stated: Sequence[ReasoningStep],
    *,
    tol: float = 0.12,
) -> SincerityReport:
    """Measure how faithfully `stated` compresses the actual `trace`.

    `tol` is the fraction of the trace's own compressibility we allow as slack
    before calling a channel a violation (heuristic, tunable).
    """
    T = _serialize(trace)
    S = _serialize(stated)

    self_T = description_bits(T, T)          # ~minimal residual: trace given itself
    self_S = description_bits(S, S)
    raw_T = description_bits(T)              # trace given nothing
    given_stated = description_bits(T, S)    # L(trace | stated)
    given_trace = description_bits(S, T)     # L(stated | trace)

    # Excess bits per channel (clamped at 0).
    hidden_bits = max(0.0, given_stated - self_T)
    fabricated_bits = max(0.0, given_trace - self_S)

    # Normaliser: the trace's compressible content (bits a perfect explanation
    # would supply). Guard against tiny/degenerate traces.
    budget = max(1.0, raw_T - self_T)
    sincerity_score = max(0.0, 1.0 - hidden_bits / budget)

    threshold = tol * budget
    h = hidden_bits > threshold
    f = fabricated_bits > threshold
    if not h and not f:
        verdict = "SINCERE"
    elif h and not f:
        verdict = "HIDDEN_STEP"
    elif f and not h:
        verdict = "FABRICATION"
    else:
        verdict = "DISTORTION"

    return SincerityReport(
        sincerity=round(sincerity_score, 4),
        hidden_bits=round(hidden_bits, 1),
        fabricated_bits=round(fabricated_bits, 1),
        excess_bits=round(hidden_bits + fabricated_bits, 1),
        verdict=verdict,
    )


def most_sincere(
    trace: Sequence[ReasoningStep],
    candidates: Sequence[Sequence[ReasoningStep]],
    *,
    abstain_above_bits: Optional[float] = None,
) -> Optional[int]:
    """Pick the candidate explanation that most faithfully regenerates the
    trace. Returns its index, or None (ABSTAIN) if even the best exceeds
    `abstain_above_bits` excess — the "abstain if no honest action" rule.
    """
    best_i, best = None, None
    for i, cand in enumerate(candidates):
        rep = sincerity(trace, cand)
        if best is None or rep.excess_bits < best.excess_bits:
            best_i, best = i, rep
    if best is None:
        return None
    if abstain_above_bits is not None and best.excess_bits > abstain_above_bits:
        return None
    return best_i
