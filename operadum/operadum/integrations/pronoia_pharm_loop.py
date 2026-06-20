# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Standing OPERADUM -> KOMPOSOS -> PRONOIA prediction loop for PHARM candidates.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Sequence

from domain_core import Candidate, EvidenceProvider, PredictionReport, TraceStep
from pronoia.domain_adapter import PronoiaPredictor

from .komposos_pharm_evidence import KompososPharmEvidenceProvider


@dataclass(frozen=True)
class PharmScoreConfig:
    """PHARM-specific score-v2 parameters.

    The base score is structured evidence strength, not raw zlib-MDL. Raw MDL
    remains in the report metrics as a transparency signal.
    """

    min_grounding: float = 0.2
    grounding_penalty_weight: float = 0.25
    contradiction_penalty: float = 0.0
    score_scale: float = 100.0


@dataclass(frozen=True)
class PharmPredictionSlate:
    """A ranked slate of PRONOIA reports for one task."""

    task: str
    reports: tuple[PredictionReport, ...]

    @property
    def winner(self) -> Optional[PredictionReport]:
        return self.reports[0] if self.reports else None


class PharmPredictionLoop:
    """Wire candidate -> evidence packet -> PRONOIA report for a slate."""

    def __init__(
        self,
        *,
        evidence_provider: EvidenceProvider | None = None,
        predictor: PronoiaPredictor | None = None,
        score_config: PharmScoreConfig | None = None,
        task: str = "rank drug repurposing hypothesis",
    ) -> None:
        self.evidence_provider = evidence_provider or KompososPharmEvidenceProvider()
        self.score_config = score_config or PharmScoreConfig()
        self.predictor = predictor or PronoiaPredictor(
            min_grounding=self.score_config.min_grounding
        )
        self.task = task

    def rank(
        self,
        candidates: Sequence[Candidate],
        *,
        task: str | None = None,
    ) -> PharmPredictionSlate:
        active_task = task or self.task
        reports = [
            score_pharm_report_v2(
                self.predictor.predict(
                    self.evidence_provider.evidence_for(candidate, active_task)
                ),
                self.score_config,
            )
            for candidate in candidates
        ]
        reports.sort(key=_report_sort_key, reverse=True)
        return PharmPredictionSlate(active_task, tuple(reports))


def rank_pharm_candidates_with_pronoia(
    candidates: Sequence[Candidate],
    *,
    evidence_provider: EvidenceProvider | None = None,
    predictor: PronoiaPredictor | None = None,
    score_config: PharmScoreConfig | None = None,
    task: str = "rank drug repurposing hypothesis",
) -> PharmPredictionSlate:
    """Convenience wrapper for the standing PHARM prediction loop."""
    return PharmPredictionLoop(
        evidence_provider=evidence_provider,
        predictor=predictor,
        score_config=score_config,
        task=task,
    ).rank(candidates)


def score_pharm_report_v2(
    report: PredictionReport,
    config: PharmScoreConfig | None = None,
) -> PredictionReport:
    """Return a PHARM-scored report while preserving raw PRONOIA metrics.

    v2 uses the strongest structured Drug->Protein->Disease/path evidence as
    the primary score, then applies the L5 grounding gate as a penalty/abstain
    signal. A sheaf contradiction penalty is represented in the formula and left
    at zero until residuals are attached to evidence packets.
    """
    cfg = config or PharmScoreConfig()
    stats = pharm_evidence_strength(report)
    raw_gain = float(report.metrics.get("gain_bits", report.score))
    grounding = float(report.metrics.get("grounding", 0.0))
    fabricated = float(report.metrics.get("fabricated_bits", 0.0))

    base_strength = max(stats["mechanism_max"], stats["path_max"])
    ungrounded_gap = max(0.0, cfg.min_grounding - grounding)
    ungrounded_penalty = cfg.grounding_penalty_weight * ungrounded_gap
    contradiction_penalty = max(0.0, cfg.contradiction_penalty)
    final_strength = max(
        0.0,
        base_strength - ungrounded_penalty - contradiction_penalty,
    )
    v2_score = round(cfg.score_scale * final_strength, 4)
    abstained = base_strength <= 0.0 or grounding < cfg.min_grounding
    decision = "BACK" if not abstained and v2_score > 0.0 else "ABSTAIN"

    metrics = dict(report.metrics)
    metrics.update({
        "raw_mdl_gain_bits": raw_gain,
        "raw_mdl_fabricated_bits": fabricated,
        "pharm_v2_score": v2_score,
        "pharm_base_strength": round(base_strength, 6),
        "pharm_final_strength": round(final_strength, 6),
        "pharm_ungrounded_penalty": round(ungrounded_penalty, 6),
        "pharm_contradiction_penalty": round(contradiction_penalty, 6),
        "pharm_evidence_sum": round(stats["evidence_sum"], 6),
        "pharm_evidence_max": round(stats["evidence_max"], 6),
        "pharm_edge_max": round(stats["edge_max"], 6),
        "pharm_path_max": round(stats["path_max"], 6),
        "pharm_direct_path_max": round(stats["direct_path_max"], 6),
        "pharm_mechanism_max": round(stats["mechanism_max"], 6),
        "pharm_evidence_items": float(stats["evidence_items"]),
    })
    trace = tuple(report.trace) + (
        TraceStep(
            "pharm_score_v2",
            "Scored PHARM candidate by structured path/mechanism evidence strength with grounding penalty.",
            (
                f"base={base_strength:.3f}; grounding={grounding:.3f}; "
                f"ungrounded_penalty={ungrounded_penalty:.3f}; score={v2_score:.3f}"
            ),
        ),
    )
    explanation = (
        f"PHARM v2 score {v2_score:.1f}: base path/mechanism strength "
        f"{base_strength:.3f}, grounding {grounding:.3f}."
    )
    if decision == "ABSTAIN":
        explanation += " The PHARM gate abstained because evidence strength or grounding was insufficient."
    else:
        explanation += f" Raw MDL gain remains {raw_gain:.1f} bits for transparency."

    return replace(
        report,
        decision=decision,
        score=v2_score,
        honest=bool(report.honest and not abstained),
        abstained=abstained,
        explanation=explanation,
        trace=trace,
        metrics=metrics,
    )


def pharm_evidence_strength(report: PredictionReport) -> dict[str, float]:
    """Extract PHARM structured-evidence strengths from a report packet."""
    packet = report.evidence
    items = tuple(getattr(packet, "items", ()) or ())
    scores = [float(getattr(item, "score", 0.0) or 0.0) for item in items]
    by_source: dict[str, list[float]] = {}
    for item, score in zip(items, scores):
        by_source.setdefault(str(getattr(item, "source", "")), []).append(score)

    path_scores: list[float] = []
    direct_path_scores: list[float] = []
    for item in items:
        if str(getattr(item, "source", "")) != "komposos_path":
            continue
        score = float(getattr(item, "score", 0.0) or 0.0)
        if _is_direct_treats_path(item):
            direct_path_scores.append(score)
        else:
            path_scores.append(score)

    return {
        "evidence_items": float(len(items)),
        "evidence_sum": sum(scores),
        "evidence_max": max(scores) if scores else 0.0,
        "edge_max": max(by_source.get("komposos_edge", [0.0])),
        "path_max": max(path_scores or [0.0]),
        "direct_path_max": max(direct_path_scores or [0.0]),
        "mechanism_max": max(by_source.get("komposos_mechanism", [0.0])),
    }


def _is_direct_treats_path(item) -> bool:
    metadata = getattr(item, "metadata", {}) or {}
    ids = tuple(metadata.get("morphism_ids", ()) or ())
    if len(ids) != 1:
        return False
    return str(ids[0]).startswith("treats:")


def _report_sort_key(report: PredictionReport) -> tuple[bool, float, float]:
    return (
        not report.abstained,
        float(report.score),
        float(report.metrics.get("grounding", 0.0)),
    )


__all__ = [
    "PharmScoreConfig",
    "PharmPredictionLoop",
    "PharmPredictionSlate",
    "pharm_evidence_strength",
    "rank_pharm_candidates_with_pronoia",
    "score_pharm_report_v2",
]
