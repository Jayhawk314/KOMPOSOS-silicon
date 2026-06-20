# SPDX-License-Identifier: Apache-2.0
"""
Honesty gate for the REMEMBER side.

PRONOIA's honesty layer (MDL grounding) was only computed at *design* time and
its verdict was recorded but never enforced — the loop kept a claim on COG's
verdict alone. A self-improving system that can persist ungrounded claims will
reward-hack itself into delusion: it optimizes its metric by writing things it
cannot justify. This gate closes that hole.

A claim is allowed into memory only if its stated rationale is *grounded* in the
evidence already committed to the graph: grounding = 1 - fabricated_fraction,
where fabricated bits are the parts of the claim the evidence cannot account for
(zlib conditional description length). Structure (COG) says a claim is well-formed;
honesty says it isn't fabricated. Both must hold to remember.

This is the single chokepoint every persistent write should pass through — the
loop today, `komposos_kg` when it exists.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Optional


def _load_grounding_of():
    """Import PRONOIA's grounding_of, or None if OPERADUM/PRONOIA is absent."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    operadum_root = os.path.join(repo_root, "operadum")
    if operadum_root not in sys.path:
        sys.path.insert(0, operadum_root)
    try:
        from pronoia.honest_rank import grounding_of
        return grounding_of
    except Exception:
        return None


@dataclass
class HonestyVerdict:
    grounding: Optional[float]   # [0,1], or None if honesty could not be checked
    fabricated_bits: float
    honest: bool                 # grounding >= min_grounding (True if unchecked)
    checked: bool                # was PRONOIA available to actually check?
    reason: str = ""


class HonestyGate:
    """Commit-time grounding gate. Reusable across the loop and the KG write path."""

    def __init__(self, min_grounding: float = 0.5):
        self.min_grounding = min_grounding
        self._grounding_of = _load_grounding_of()

    @property
    def available(self) -> bool:
        return self._grounding_of is not None

    def evaluate(self, evidence: str, claim: str) -> HonestyVerdict:
        """Grounding of `claim` against `evidence`. Unchecked => honest=True (degrade open)."""
        if self._grounding_of is None:
            return HonestyVerdict(None, 0.0, honest=True, checked=False,
                                  reason="pronoia unavailable; honesty unchecked")
        grounding, fabricated = self._grounding_of(
            evidence.encode("utf-8"), claim.encode("utf-8")
        )
        honest = grounding >= self.min_grounding
        return HonestyVerdict(
            grounding=round(float(grounding), 3),
            fabricated_bits=round(float(fabricated), 1),
            honest=bool(honest),
            checked=True,
            reason=("grounded" if honest
                    else f"ungrounded: grounding {grounding:.2f} < {self.min_grounding}"),
        )

    # -- convenience: the gated write path ---------------------------------

    @staticmethod
    def graph_evidence(category, exclude: Optional[tuple] = None) -> str:
        """Serialize the committed graph as evidence, optionally excluding one edge
        (e.g. the candidate itself, so a claim cannot 'ground' itself)."""
        lines = []
        for m in category.morphisms():
            if exclude and (m.source, m.target, m.name) == exclude:
                continue
            lines.append(f"{m.source} {m.name} {m.target} {round(float(m.confidence), 2)}")
        return "\n".join(sorted(lines))

    def check_claim(
        self,
        category,
        source: str,
        target: str,
        relation: str,
        claim: Optional[str] = None,
    ) -> HonestyVerdict:
        """Gate a (source, relation, target) edge against the rest of the graph.

        `claim` defaults to the edge text itself; pass a richer rationale (e.g. the
        mechanism/route) for a stronger grounding signal.
        """
        evidence = self.graph_evidence(category, exclude=(source, target, relation))
        if claim is None:
            claim = f"{source} {relation} {target}"
        return self.evaluate(evidence, claim)
