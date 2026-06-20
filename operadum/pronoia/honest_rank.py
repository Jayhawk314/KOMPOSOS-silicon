"""
PRONOIA integration L2 + L5 — honesty-gated prediction.

The MDL ranker (L2) scores a hypothesis by how much it compresses the evidence.
That score is already robust to padding (fabricated claims don't help compress
real evidence), but it does NOT tell you whether the candidate's *stated
rationale* is grounded. The honesty layer (L5) adds that: for each candidate we
measure the **grounding** — the fraction of the hypothesis that the evidence
actually accounts for — and flag candidates whose rank rides on ungrounded
claims.

    grounding = 1 - fabricated_fraction
    fabricated = L(H | evidence) - L(H | H)   (hypothesis bits the evidence can't ground)

A prediction you can act on is one that both compresses the evidence AND explains
itself honestly. Pure stdlib (reuses the zlib description-length machinery).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from .honesty_mdl import description_bits
from .mdl_ranker import Hypothesis, rank as _mdl_rank


@dataclass(frozen=True)
class HonestlyRanked:
    hypothesis: Hypothesis
    gain_bits: float        # L2: evidence compression benefit (rank signal)
    grounding: float        # L5: [0,1], fraction of the claim grounded in evidence
    fabricated_bits: float  # claim bits the evidence cannot account for
    honest: bool            # grounding >= min_grounding


def grounding_of(evidence: bytes, hypothesis: bytes) -> tuple:
    """Return (grounding, fabricated_bits) for one hypothesis vs the evidence."""
    raw_H = description_bits(hypothesis)
    self_H = description_bits(hypothesis, hypothesis)
    given_ev = description_bits(hypothesis, evidence)   # L(H | evidence)
    fabricated = max(0.0, given_ev - self_H)            # H not grounded in evidence
    budget = max(1.0, raw_H - self_H)
    grounding = max(0.0, 1.0 - fabricated / budget)
    return grounding, fabricated


def honest_rank(
    evidence: str,
    hypotheses: Sequence[Hypothesis],
    *,
    min_grounding: float = 0.5,
) -> List[HonestlyRanked]:
    """Rank by compression gain (L2), annotate each with grounding (L5).

    Returns candidates sorted by gain, each flagged honest/not. Filter on
    `.honest` to drop predictions whose rationale is mostly ungrounded.
    """
    D = evidence.encode("utf-8")
    base = _mdl_rank(evidence, hypotheses)
    out: List[HonestlyRanked] = []
    for r in base:
        grounding, fabricated = grounding_of(D, r.hypothesis.claim.encode("utf-8"))
        out.append(HonestlyRanked(
            hypothesis=r.hypothesis,
            gain_bits=r.gain_bits,
            grounding=round(grounding, 3),
            fabricated_bits=round(fabricated, 1),
            honest=grounding >= min_grounding,
        ))
    return out  # already gain-sorted (base is sorted)
