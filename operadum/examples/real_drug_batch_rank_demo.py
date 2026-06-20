# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Real KOMPOSOS-CHEM-TB batch ranker: pick a candidate, not just an action.

Run:
    python -m examples.real_drug_batch_rank_demo

The single-candidate demo asks "what next action for THIS drug?". This one asks
the cross-candidate question OPERADUM is for: given a disease and a slate of
candidate drugs, which candidate should we back under a figure profile, and what
is its best next action? Boltz is not installed, so structure binding falls back;
graph/ABPP/drug-likeness evidence is read from the real KOMPOSOS-CHEM-TB checkout
when present.
"""

from __future__ import annotations

import os

from operadum import DRUG_PORTFOLIO, FASTEST_RECOVERY
from operadum.integrations.drug_batch_ranker import Candidate, rank_candidates
from operadum.integrations.komposos_drug_world import (
    DEFAULT_KOMPOSOS_CHEM_TB_PATH,
    KompososDrugEvidenceClient,
)


# disease -> candidate drugs (with their known primary target) competing for it.
SLATES = {
    "NSCLC": [
        Candidate("Erlotinib", "EGFR"),
        Candidate("Sotorasib", "KRAS"),
        Candidate("Osimertinib", "EGFR"),
        Candidate("Crizotinib", "ALK"),
    ],
    "Melanoma": [
        Candidate("Dabrafenib", "BRAF"),
        Candidate("Vemurafenib", "BRAF"),
        Candidate("Trametinib", "MEK1"),
    ],
}


def main() -> None:
    path = os.environ.get("KOMPOSOS_CHEM_TB_PATH", DEFAULT_KOMPOSOS_CHEM_TB_PATH)
    client = KompososDrugEvidenceClient(path, use_komposos=True)

    print(f"KOMPOSOS-CHEM-TB path: {path}")
    print("Cross-candidate ranking (lower portfolio score = better):")

    for disease, candidates in SLATES.items():
        for profile in (DRUG_PORTFOLIO, FASTEST_RECOVERY):
            slate = rank_candidates(
                disease,
                candidates,
                client=client,
                monoid=profile,
                requirements={"evidence_strength": 0.8},
            )
            print(f"\n{disease}  under {slate.monoid_name}")
            for rank, a in enumerate(slate.assessments, start=1):
                marker = "*" if a is slate.winner else " "
                print(
                    f"  {marker}{rank}. {a.candidate.drug:<12} "
                    f"score={a.score:+.3f}  "
                    f"next={a.best_action_name or 'no feasible action'}"
                )
            winner = slate.winner
            if winner is not None:
                print(f"     -> back {winner.candidate.drug}: {_evidence(winner)}")


def _evidence(assessment) -> str:
    return ", ".join(
        f"{name}={result.score:.2f}" for name, result in assessment.evidence.items()
    )


if __name__ == "__main__":
    main()
