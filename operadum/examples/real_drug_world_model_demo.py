# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Real KOMPOSOS-CHEM-TB drug world-model smoke test.

Run:
    python -m examples.real_drug_world_model_demo

This is still not an LLM. It reads evidence from the neighbouring
KOMPOSOS-IV-CHEM-TB checkout when present, converts it into OPERADUM figures,
and asks WRIGHT to choose a next action.
"""

from __future__ import annotations

import os

from operadum import EVIDENCE_FIRST, FASTEST_RECOVERY
from operadum.integrations.komposos_drug_world import (
    DEFAULT_KOMPOSOS_CHEM_TB_PATH,
    KompososDrugEvidenceClient,
    build_drug_world_model,
    initial_drug_state,
)


CASES = [
    # drug, target, disease label in KOMPOSOS-CHEM-TB tier1.db
    ("Erlotinib", "EGFR", "NSCLC"),
    ("Imatinib", "ABL1", "CML"),
    ("Sotorasib", "KRAS", "NSCLC"),
    ("Dabrafenib", "BRAF", "Melanoma"),
]


def main() -> None:
    path = os.environ.get("KOMPOSOS_CHEM_TB_PATH", DEFAULT_KOMPOSOS_CHEM_TB_PATH)
    client = KompososDrugEvidenceClient(path, use_komposos=True)
    model = build_drug_world_model(client)

    print(f"KOMPOSOS-CHEM-TB path: {path}")
    print("Real evidence smoke test:")

    for drug, target, disease in CASES:
        state = initial_drug_state(drug=drug, disease=disease, target=target)
        graph = client.graph_evidence(drug, disease)
        abpp = client.target_engagement(drug, target, prior=graph.score)
        binding = client.structure_binding(drug, target)
        likeness = client.drug_likeness(drug)

        evidence_choice = model.choose(
            state,
            monoid=EVIDENCE_FIRST,
            requirements={"evidence_strength": 0.8},
        )
        fastest_choice = model.choose(state, monoid=FASTEST_RECOVERY)

        print(f"\n{drug} -> {target} -> {disease}")
        print(f"  graph       {graph.score:.3f}  {graph.source}: {graph.detail}")
        print(f"  engagement  {abpp.score:.3f}  {abpp.source}: {abpp.detail}")
        print(f"  binding     {binding.score:.3f}  {binding.source}: {binding.detail}")
        print(f"  druglike    {likeness.score:.3f}  {likeness.source}: {likeness.detail}")
        print(f"  EVIDENCE_FIRST   -> {_action(evidence_choice)}")
        print(f"  FASTEST_RECOVERY -> {_action(fastest_choice)}")


def _action(choice) -> str:
    if choice is None:
        return "no feasible action"
    return f"{choice.prediction.action}  figures={_pretty(choice.figures)}"


def _pretty(figures):
    keep = ("confidence", "evidence_strength", "time_hours", "money_usd", "assay_uncertainty")
    return {k: round(float(figures[k]), 4) for k in keep if k in figures}


if __name__ == "__main__":
    main()

