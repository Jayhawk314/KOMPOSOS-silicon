# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

from operadum import DRUG_PORTFOLIO, EVIDENCE_FIRST, FASTEST_RECOVERY
from operadum.integrations.drug_batch_ranker import (
    Candidate,
    assess_candidate,
    rank_candidates,
)
from operadum.integrations.komposos_drug_world import (
    KompososDrugEvidenceClient,
    ScoreResult,
    build_drug_world_model,
)


class StubEvidence(KompososDrugEvidenceClient):
    """Deterministic per-drug scores so ranking is fully predictable."""

    def __init__(self, scores):
        super().__init__(use_komposos=False)
        self._scores = scores  # drug -> (graph, engagement, binding, druglike)

    def graph_evidence(self, drug, disease):
        return ScoreResult(self._scores[drug][0], "stub", "graph")

    def target_engagement(self, drug, target, prior=0.5):
        return ScoreResult(self._scores[drug][1], "stub", "abpp")

    def structure_binding(self, drug, target):
        return ScoreResult(self._scores[drug][2], "stub", "structure")

    def drug_likeness(self, drug):
        return ScoreResult(self._scores[drug][3], "stub", "druglike")


def _strong_vs_weak():
    return StubEvidence(
        {
            "Strongdrug": (0.9, 0.95, 0.8, 0.85),
            "Weakdrug": (0.4, 0.45, 0.4, 0.5),
        }
    )


def test_ranker_backs_the_better_substantiated_candidate():
    client = _strong_vs_weak()
    slate = rank_candidates(
        "NSCLC",
        [Candidate("Weakdrug", "EGFR"), Candidate("Strongdrug", "EGFR")],
        client=client,
        monoid=EVIDENCE_FIRST,
        requirements={"evidence_strength": 0.8},
    )

    assert slate.winner.candidate.drug == "Strongdrug"
    # Strong evidence (max-direction figures) drives the score lower (better).
    assert slate.assessments[0].score < slate.assessments[1].score
    # Only the strong candidate clears the 0.8 evidence gate for a next action.
    assert slate.winner.feasible
    assert slate.assessments[1].best_action is None


def test_requirements_gate_forces_the_costlier_grounding_action():
    # Cheap graph evidence is below the 0.8 gate, so it is filtered out and the
    # costlier-but-stronger ABPP engagement is the only feasible next action.
    client = StubEvidence({"Gappy": (0.6, 0.95, 0.7, 0.8)})
    slate = rank_candidates(
        "NSCLC",
        [Candidate("Gappy", "EGFR")],
        client=client,
        monoid=EVIDENCE_FIRST,
        requirements={"evidence_strength": 0.8},
    )
    assert slate.winner.best_action_name == "check_abpp_target_engagement"


def test_portfolio_folds_every_applicable_action():
    client = _strong_vs_weak()
    model = build_drug_world_model(client)
    a = assess_candidate(
        model,
        client,
        candidate=Candidate("Strongdrug", "EGFR"),
        disease="NSCLC",
        monoid=FASTEST_RECOVERY,
    )

    # All four actions are applicable (target present), so their summed costs
    # accumulate in the portfolio: money/time are sums over every action.
    assert a.portfolio["money_usd"] == 5000.0 + 150.0  # abpp + structure
    assert a.portfolio["time_hours"] > 48.0
    # Confidence multiplies across independent evidence (product policy).
    assert 0.0 < a.portfolio["confidence"] < 0.9


def test_drug_portfolio_profile_is_driven_by_evidence_not_shared_cost():
    client = _strong_vs_weak()
    slate = rank_candidates(
        "NSCLC",
        [Candidate("Weakdrug", "EGFR"), Candidate("Strongdrug", "EGFR")],
        client=client,
        monoid=DRUG_PORTFOLIO,
    )

    # Strong candidate still wins, and because the shared ~$5k assay cost is
    # nearly neutralized the score is dominated by the (negated) evidence terms:
    # the winner's score is strongly negative, not parked at the cost floor.
    assert slate.winner.candidate.drug == "Strongdrug"
    assert slate.winner.score < 0.0
    # The evidence gap between candidates is large, not a tiny delta on a big base.
    spread = slate.assessments[1].score - slate.assessments[0].score
    assert spread > 10.0


def test_ranking_is_deterministic_on_ties():
    client = StubEvidence(
        {
            "Aaa": (0.6, 0.6, 0.6, 0.6),
            "Bbb": (0.6, 0.6, 0.6, 0.6),
        }
    )
    slate = rank_candidates(
        "NSCLC",
        [Candidate("Bbb", "EGFR"), Candidate("Aaa", "EGFR")],
        client=client,
        monoid=EVIDENCE_FIRST,
    )
    # Equal scores break on drug name.
    assert [a.candidate.drug for a in slate.assessments] == ["Aaa", "Bbb"]
