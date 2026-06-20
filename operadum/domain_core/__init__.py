"""
Shared domain contracts for the OPERADUM -> KOMPOSOS -> PRONOIA stack.

This package deliberately contains no engine logic. It defines the small objects
that let the design engine, evidence adapters, and prediction engine communicate
without importing each other's internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

ResourceFigures = Mapping[str, float]


@dataclass(frozen=True)
class Candidate:
    """A proposed object/action/hypothesis to evaluate.

    OPERADUM usually creates this. PRONOIA should not care how it was created;
    it only needs a stable id/name plus the claim to score.
    """

    identifier: str
    name: str
    kind: str = "candidate"
    target: str = ""
    claim: str = ""
    figures: ResourceFigures = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceItem:
    """One grounded piece of evidence from KOMPOSOS or another source."""

    source: str
    claim: str
    score: float = 1.0
    weight: float = 1.0
    provenance: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_text(self) -> str:
        bits = [self.source, self.claim]
        bits.append(f"score={self.score:.3f}")
        bits.append(f"weight={self.weight:.3f}")
        if self.provenance:
            bits.append(f"provenance={self.provenance}")
        return " | ".join(bits)


@dataclass(frozen=True)
class EvidencePacket:
    """All evidence currently available for a candidate and task."""

    candidate: Candidate
    task: str
    items: Sequence[EvidenceItem] = field(default_factory=tuple)
    context: Mapping[str, Any] = field(default_factory=dict)

    def as_text(self) -> str:
        header = [
            f"task: {self.task}",
            f"candidate: {self.candidate.name}",
        ]
        if self.candidate.target:
            header.append(f"target: {self.candidate.target}")
        if self.candidate.claim:
            header.append(f"candidate_claim: {self.candidate.claim}")
        evidence = [item.as_text() for item in self.items]
        return "\n".join(header + evidence)


@dataclass(frozen=True)
class TraceStep:
    """One auditable step emitted by an engine."""

    op: str
    justification: str = ""
    output: str = ""


@dataclass(frozen=True)
class PredictionReport:
    """Prediction result passed back to applications or downstream engines."""

    candidate: Candidate
    decision: str
    score: float
    honest: bool
    abstained: bool
    explanation: str
    trace: Sequence[TraceStep] = field(default_factory=tuple)
    metrics: Mapping[str, float] = field(default_factory=dict)
    evidence: EvidencePacket | None = None


class CandidateDesigner(Protocol):
    """Something that proposes candidates, usually OPERADUM."""

    def propose(self, task: str) -> Sequence[Candidate]: ...


class EvidenceProvider(Protocol):
    """Something that grounds a candidate in evidence, usually a KOMPOSOS adapter."""

    def evidence_for(self, candidate: Candidate, task: str) -> EvidencePacket: ...


class Predictor(Protocol):
    """Something that turns an evidence packet into a prediction report."""

    def predict(self, packet: EvidencePacket) -> PredictionReport: ...


__all__ = [
    "Candidate",
    "CandidateDesigner",
    "EvidenceItem",
    "EvidencePacket",
    "EvidenceProvider",
    "PredictionReport",
    "Predictor",
    "ResourceFigures",
    "TraceStep",
]
