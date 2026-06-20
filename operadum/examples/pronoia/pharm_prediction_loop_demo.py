"""
Demo: standing OPERADUM -> KOMPOSOS -> PRONOIA PHARM prediction loop.

Run from the consolidated repo root:

    python -m examples.pronoia.pharm_prediction_loop_demo
"""

from __future__ import annotations

from operadum.integrations.komposos_pharm_evidence import (
    KompososPharmEvidenceProvider,
    pharm_candidate,
)
from operadum.integrations.pronoia_pharm_loop import PharmPredictionLoop
from pronoia.domain_adapter import PronoiaPredictor


CANDIDATES = [
    pharm_candidate(
        "Erlotinib",
        "NSCLC",
        target="EGFR",
        claim="Erlotinib treats NSCLC by inhibiting EGFR; EGFR drives NSCLC; engagement evidence supports it",
    ),
    pharm_candidate(
        "Osimertinib",
        "NSCLC",
        target="EGFR",
        claim="Osimertinib treats NSCLC by inhibiting EGFR T790M; EGFR drives NSCLC; clinical use supports it",
    ),
    pharm_candidate(
        "Sotorasib",
        "NSCLC",
        target="KRAS",
        claim="Sotorasib treats NSCLC by inhibiting KRAS G12C in a mechanistic NSCLC subset",
    ),
    pharm_candidate(
        "Aspirin",
        "NSCLC",
        target="PTGS1",
        claim="Aspirin treats NSCLC by inhibiting COX; antiplatelet evidence is not a lung cancer mechanism",
    ),
]


def main() -> None:
    loop = PharmPredictionLoop(
        evidence_provider=KompososPharmEvidenceProvider(max_paths=5, max_mechanisms=8),
        predictor=PronoiaPredictor(min_grounding=0.2),
        task="rank NSCLC drug repurposing hypotheses from KOMPOSOS PHARM evidence",
    )
    slate = loop.rank(CANDIDATES)

    print("PRONOIA PHARM prediction loop")
    print("candidate -> KOMPOSOS EvidencePacket -> PRONOIA PredictionReport\n")
    for index, report in enumerate(slate.reports, start=1):
        metrics = report.metrics
        packet = report.evidence
        n_items = 0 if packet is None else len(packet.items)
        print(
            f"{index}. {report.candidate.name:<12} {report.decision:<7} "
            f"v2={metrics.get('pharm_v2_score', report.score):>7} "
            f"raw_gain={metrics.get('raw_mdl_gain_bits', metrics.get('gain_bits', 0.0)):>7} "
            f"base={metrics.get('pharm_base_strength', 0.0):>5} "
            f"grounding={metrics.get('grounding', 0.0):>5} "
            f"evidence_items={n_items}"
        )
        if packet and packet.items:
            top = max(packet.items, key=lambda item: item.score)
            print(f"   top evidence: {top.source} score={top.score:.3f} {top.claim[:110]}")
        print(f"   {report.explanation}")

    if slate.winner:
        print(f"\nWinner: {slate.winner.candidate.name} ({slate.winner.decision})")


if __name__ == "__main__":
    main()
