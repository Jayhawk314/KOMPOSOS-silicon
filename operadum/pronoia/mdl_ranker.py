"""
PRONOIA L2 — prediction by compression (MDL hypothesis ranker).

Thesis: the best prediction is the one that most compresses the evidence. Score a
hypothesis H against a body of evidence D by its **conditional compression
benefit** — the bits H saves on the evidence:

    gain(H) = L(D) - L(D | H)

A hypothesis whose claimed content is actually reflected in the observations makes
`L(D | H)` collapse, so it saves many bits; an unsupported hypothesis barely helps
compress D, so it saves almost none. This is the information-gain (mutual-
information) form of MDL and ranks same-shaped hypotheses robustly.

(The full two-part code `L(D) - [L(H) + L(D|H)]` is the model-*selection* variant;
it additionally charges L(H), which is right for choosing a single model but
over-penalises longer hypotheses when *ranking* candidates of similar form. We
report L(H) for transparency but rank by the conditional benefit. The whole thing
inherits worst-case regret guarantees from the universal-coding game.)

`L(. | H)` is estimated by compressing D with H as a preset dictionary (zlib),
reusing the same description-length machinery as the honesty layer. Pure stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .honesty_mdl import description_bits


@dataclass(frozen=True)
class Hypothesis:
    """A candidate claim. `claim` is the text content it asserts about the world
    (e.g. a drug's mechanism); `name` is just a label for reporting."""
    name: str
    claim: str


@dataclass(frozen=True)
class RankedHypothesis:
    hypothesis: Hypothesis
    gain_bits: float        # L(D) - L(D|H): bits the hypothesis saves on the evidence
    explained_frac: float   # gain / L(D): fraction of the evidence it accounts for
    cost_bits: float        # L(H): cost to state the hypothesis (reported, not ranked on)
    residual_bits: float    # L(D | H): evidence bits left unexplained


def compression_gain(evidence: bytes, hypothesis: bytes) -> Tuple[float, float, float]:
    """Return (gain, cost, residual) in bits.

    gain = L(D) - L(D|H) is the conditional compression benefit (what we rank on);
    cost = L(H) is reported for transparency only.
    """
    raw = description_bits(evidence)                 # L(D)
    cost = description_bits(hypothesis)              # L(H)
    residual = description_bits(evidence, hypothesis)  # L(D | H)
    gain = raw - residual
    return gain, cost, residual


def rank(
    evidence: str,
    hypotheses: Sequence[Hypothesis],
) -> List[RankedHypothesis]:
    """Rank hypotheses by how much each compresses the evidence (best first)."""
    D = evidence.encode("utf-8")
    raw = description_bits(D)
    out: List[RankedHypothesis] = []
    for h in hypotheses:
        gain, cost, residual = compression_gain(D, h.claim.encode("utf-8"))
        out.append(RankedHypothesis(
            hypothesis=h,
            gain_bits=round(gain, 1),
            explained_frac=round(gain / raw, 4) if raw > 0 else 0.0,
            cost_bits=round(cost, 1),
            residual_bits=round(residual, 1),
        ))
    out.sort(key=lambda r: r.gain_bits, reverse=True)
    return out
