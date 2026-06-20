"""
PRONOIA adapter for the shared domain_core contracts.

The adapter keeps PRONOIA as the prediction/certification engine while accepting
plain Candidate/EvidencePacket objects from OPERADUM and KOMPOSOS adapters.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from domain_core import Candidate, EvidencePacket, PredictionReport, TraceStep

from .honest_rank import honest_rank
from .mdl_ranker import Hypothesis


class PronoiaPredictor:
    """Rank candidate claims by MDL gain and gate them for grounding.

    `packet` supplies the real evidence for the primary candidate. `alternatives`
    may be supplied when an application wants a cross-candidate slate; otherwise
    the packet candidate is scored alone.
    """

    def __init__(self, *, min_grounding: float = 0.5) -> None:
        self.min_grounding = float(min_grounding)

    def predict(
        self,
        packet: EvidencePacket,
        alternatives: Sequence[Candidate] | None = None,
    ) -> PredictionReport:
        candidates = tuple(alternatives or (packet.candidate,))
        if not candidates:
            return PredictionReport(
                candidate=packet.candidate,
                decision="ABSTAIN",
                score=0.0,
                honest=False,
                abstained=True,
                explanation="No candidates were provided for prediction.",
                evidence=packet,
            )

        evidence_text = _evidence_only_text(packet)
        hypotheses = [
            Hypothesis(candidate.name, _claim_for(candidate))
            for candidate in candidates
        ]
        ranked = honest_rank(
            evidence_text,
            hypotheses,
            min_grounding=self.min_grounding,
        )
        best = ranked[0]
        selected = _candidate_by_name(candidates, best.hypothesis.name)
        honest = bool(best.honest)
        decision = "BACK" if honest and best.gain_bits > 0 else "ABSTAIN"
        abstained = decision == "ABSTAIN"
        metrics: Mapping[str, float] = {
            "gain_bits": best.gain_bits,
            "grounding": best.grounding,
            "fabricated_bits": best.fabricated_bits,
        }
        trace = (
            TraceStep(
                "mdl_rank",
                "Ranked candidate claims by evidence compression gain.",
                f"best={best.hypothesis.name}; gain_bits={best.gain_bits}",
            ),
            TraceStep(
                "honesty_gate",
                "Checked how much of the selected claim is grounded in the evidence packet.",
                f"grounding={best.grounding}; fabricated_bits={best.fabricated_bits}; honest={honest}",
            ),
        )
        explanation = (
            f"{best.hypothesis.name} ranked highest by MDL gain "
            f"({best.gain_bits} bits) with grounding {best.grounding}."
        )
        if abstained:
            explanation += " The gate abstained because the claim was not sufficiently grounded."

        return PredictionReport(
            candidate=selected,
            decision=decision,
            score=best.gain_bits,
            honest=honest,
            abstained=abstained,
            explanation=explanation,
            trace=trace,
            metrics=metrics,
            evidence=packet,
        )


def _evidence_only_text(packet: EvidencePacket) -> str:
    """Serialize evidence without leaking the candidate's own claim into D.

    EvidencePacket.as_text() includes `candidate_claim` for display. That is right
    for reports but wrong for MDL scoring, because it would let every candidate
    compress evidence by quoting itself. The predictor scores only task/target and
    grounded EvidenceItem content.
    """
    lines = [f"task: {packet.task}"]
    if packet.candidate.target:
        lines.append(f"target: {packet.candidate.target}")
    lines.extend(item.as_text() for item in packet.items)
    return "\n".join(lines)


def _claim_for(candidate: Candidate) -> str:
    if candidate.claim:
        return candidate.claim
    if candidate.target:
        return f"{candidate.name} -> {candidate.target}"
    return candidate.name


def _candidate_by_name(candidates: Sequence[Candidate], name: str) -> Candidate:
    for candidate in candidates:
        if candidate.name == name:
            return candidate
    return candidates[0]


__all__ = ["PronoiaPredictor"]