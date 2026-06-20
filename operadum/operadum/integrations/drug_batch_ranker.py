# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Cross-candidate drug ranking on top of the KOMPOSOS-CHEM-TB world model.

KOMPOSOS alone answers "for THIS candidate, what is the next action?".
This module answers the question OPERADUM is actually for: given a disease and a
slate of candidates, *which candidate* should we back, and what is its best next
action?

The categorical content is the candidate's **evidence portfolio**: the monoidal
fold of every applicable action's figures under the active ResourceMonoid. That
fold is what makes the candidates commensurable -- total time/money sum, joint
confidence multiplies, weakest evidence link mins, risks union -- so the active
figure profile (EVIDENCE_FIRST, FASTEST_RECOVERY, ...) ranks them on one scalar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ..core.enrichment import GENERAL_FIGURES, ResourceMonoid
from ..core.types import ResourceValue
from ..world_model import ActionChoice, RuleWorldModel, WorldState
from .komposos_drug_world import (
    KompososDrugEvidenceClient,
    ScoreResult,
    build_drug_world_model,
    initial_drug_state,
)


@dataclass(frozen=True)
class Candidate:
    """A drug to evaluate against a disease, optionally with a known target."""

    drug: str
    target: Optional[str] = None


@dataclass(frozen=True)
class CandidateAssessment:
    """One candidate's folded evidence portfolio plus its best next action."""

    candidate: Candidate
    disease: str
    portfolio: ResourceValue
    score: float
    evidence: Dict[str, ScoreResult] = field(default_factory=dict)
    best_action: Optional[ActionChoice] = None

    @property
    def feasible(self) -> bool:
        """True iff an action survived the requirements gate for this candidate."""
        return self.best_action is not None

    @property
    def best_action_name(self) -> Optional[str]:
        return None if self.best_action is None else self.best_action.prediction.action


@dataclass(frozen=True)
class RankedSlate:
    """A disease, its candidates ranked best-first, and the chosen winner."""

    disease: str
    monoid_name: str
    assessments: Tuple[CandidateAssessment, ...]

    @property
    def winner(self) -> Optional[CandidateAssessment]:
        """The top-ranked candidate, or None if the slate was empty."""
        return self.assessments[0] if self.assessments else None


def assess_candidate(
    model: RuleWorldModel,
    client: KompososDrugEvidenceClient,
    *,
    candidate: Candidate,
    disease: str,
    monoid: ResourceMonoid = GENERAL_FIGURES,
    requirements: Optional[ResourceValue] = None,
) -> CandidateAssessment:
    """Fold a candidate's applicable actions into one ranked portfolio.

    The portfolio is ``monoid.total`` over every applicable prediction's figures,
    i.e. the monoidal product of the candidate's whole evidence program. The
    best next action is chosen separately under the same profile and gate.
    """
    state = initial_drug_state(
        drug=candidate.drug, disease=disease, target=candidate.target
    )
    predictions = model.predictions(state)
    portfolio = monoid.total(*(p.cost for p in predictions))
    score = monoid.rank(portfolio)
    best_action = model.choose(state, monoid=monoid, requirements=requirements)
    return CandidateAssessment(
        candidate=candidate,
        disease=disease,
        portfolio=portfolio,
        score=score,
        evidence=_collect_evidence(client, candidate, disease),
        best_action=best_action,
    )


def rank_candidates(
    disease: str,
    candidates: Sequence[Candidate],
    *,
    client: Optional[KompososDrugEvidenceClient] = None,
    monoid: ResourceMonoid = GENERAL_FIGURES,
    requirements: Optional[ResourceValue] = None,
) -> RankedSlate:
    """Rank candidates for one disease best-first under a figure profile.

    Lower ``monoid.rank`` is better, so the returned slate is sorted ascending.
    Ties break on drug name for determinism.
    """
    evidence_client = client or KompososDrugEvidenceClient()
    model = build_drug_world_model(evidence_client)
    assessments = [
        assess_candidate(
            model,
            evidence_client,
            candidate=candidate,
            disease=disease,
            monoid=monoid,
            requirements=requirements,
        )
        for candidate in candidates
    ]
    assessments.sort(key=lambda a: (a.score, a.candidate.drug))
    return RankedSlate(
        disease=disease,
        monoid_name=monoid.name,
        assessments=tuple(assessments),
    )


def _collect_evidence(
    client: KompososDrugEvidenceClient,
    candidate: Candidate,
    disease: str,
) -> Dict[str, ScoreResult]:
    """Gather the raw per-source scores for display/audit (not for ranking)."""
    out: Dict[str, ScoreResult] = {}
    graph = client.graph_evidence(candidate.drug, disease)
    out["graph"] = graph
    out["druglike"] = client.drug_likeness(candidate.drug)
    if candidate.target:
        out["engagement"] = client.target_engagement(
            candidate.drug, candidate.target, prior=graph.score
        )
        out["binding"] = client.structure_binding(candidate.drug, candidate.target)
    return out
