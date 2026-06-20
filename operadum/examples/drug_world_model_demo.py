# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Cheap drug world-model demo.

Run:
    python -m examples.drug_world_model_demo

This does not call an LLM. The fixed evidence client below stands in for cached
KOMPOSOS/ABPP/Boltz scores so the OPERADUM action-selection mechanics are clear.
Swap in KompososDrugEvidenceClient(use_komposos=True) to read the neighbouring
KOMPOSOS-IV-CHEM-TB checkout when its dependencies are available.
"""

from __future__ import annotations

from operadum import EVIDENCE_FIRST, FASTEST_RECOVERY
from operadum.integrations.komposos_drug_world import (
    KompososDrugEvidenceClient,
    ScoreResult,
    build_drug_world_model,
    initial_drug_state,
)


class FixedEvidence(KompososDrugEvidenceClient):
    def __init__(self):
        super().__init__(use_komposos=False)

    def graph_evidence(self, drug: str, disease: str) -> ScoreResult:
        return ScoreResult(0.55, "cached_graph", "existing category paths")

    def target_engagement(self, drug: str, target: str, prior: float = 0.5) -> ScoreResult:
        return ScoreResult(0.94, "cached_abpp", "confirmed target engagement")

    def structure_binding(self, drug: str, target: str) -> ScoreResult:
        return ScoreResult(0.72, "cached_structure", "good pocket fit")

    def drug_likeness(self, drug: str) -> ScoreResult:
        return ScoreResult(0.82, "cached_properties", "passes cheap screen")


def main() -> None:
    state = initial_drug_state(drug="Erlotinib", disease="TB", target="EGFR")
    model = build_drug_world_model(FixedEvidence())

    evidence_first = model.choose(
        state,
        monoid=EVIDENCE_FIRST,
        requirements={"evidence_strength": 0.8},
    )
    fastest = model.choose(state, monoid=FASTEST_RECOVERY)

    print("Same lightweight world model, different OPERADUM profile:")
    for label, choice in (("EVIDENCE_FIRST", evidence_first), ("FASTEST_RECOVERY", fastest)):
        prediction = choice.prediction
        print(f"  {label:16s} -> {prediction.action}")
        print(f"    figures={_pretty(choice.figures)}")
        print(f"    why={prediction.explanation}")


def _pretty(figures):
    return {k: round(float(v), 4) for k, v in sorted(figures.items())}


if __name__ == "__main__":
    main()

