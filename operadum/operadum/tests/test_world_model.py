# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

from operadum import (
    EVIDENCE_FIRST,
    FASTEST_RECOVERY,
    GENERAL_FIGURES,
    RuleWorldModel,
    WorldPrediction,
    WorldState,
)
from operadum.integrations.komposos_drug_world import (
    KompososDrugEvidenceClient,
    ScoreResult,
    build_drug_world_model,
    initial_drug_state,
)


def test_rule_world_model_chooses_action_via_operadum_profile():
    model = RuleWorldModel("toy")
    state = WorldState("candidate")

    @model.action("cheap_weak")
    def cheap_weak(s):
        figures = {"confidence": 0.55, "evidence_strength": 0.4, "time_hours": 0.1}
        return WorldPrediction(
            "cheap_weak", s, s.with_updates(figures=figures), figures,
            confidence=0.55,
        )

    @model.action("slow_strong")
    def slow_strong(s):
        figures = {"confidence": 0.9, "evidence_strength": 0.9, "time_hours": 5.0}
        return WorldPrediction(
            "slow_strong", s, s.with_updates(figures=figures), figures,
            confidence=0.9,
        )

    unconstrained = model.choose(state, monoid=GENERAL_FIGURES)
    required = model.choose(
        state,
        monoid=GENERAL_FIGURES,
        requirements={"evidence_strength": 0.8},
    )

    assert unconstrained.prediction.action == "cheap_weak"
    assert required.prediction.action == "slow_strong"


class StaticDrugEvidence(KompososDrugEvidenceClient):
    def __init__(self):
        super().__init__(use_komposos=False)

    def graph_evidence(self, drug: str, disease: str) -> ScoreResult:
        return ScoreResult(0.55, "test", "graph")

    def target_engagement(self, drug: str, target: str, prior: float = 0.5) -> ScoreResult:
        return ScoreResult(0.94, "test", "abpp")

    def structure_binding(self, drug: str, target: str) -> ScoreResult:
        return ScoreResult(0.72, "test", "structure")

    def drug_likeness(self, drug: str) -> ScoreResult:
        return ScoreResult(0.82, "test", "druglike")


def test_drug_world_model_is_profile_driven_not_llm_driven():
    model = build_drug_world_model(StaticDrugEvidence())
    state = initial_drug_state(drug="Erlotinib", disease="TB", target="EGFR")

    evidence = model.choose(
        state,
        monoid=EVIDENCE_FIRST,
        requirements={"evidence_strength": 0.8},
    )
    fastest = model.choose(state, monoid=FASTEST_RECOVERY)

    assert evidence.prediction.action == "check_abpp_target_engagement"
    assert fastest.prediction.action == "check_drug_likeness"


def test_drug_world_model_can_emit_action_operad():
    model = build_drug_world_model(StaticDrugEvidence())
    state = initial_drug_state(drug="Erlotinib", disease="TB", target="EGFR")
    op = model.action_operad(state, monoid=EVIDENCE_FIRST)

    names = {operation.name for operation in op.operations()}

    assert "score_graph_evidence" in names
    assert "check_abpp_target_engagement" in names
    assert "run_structure_binding" in names
    assert "check_drug_likeness" in names

