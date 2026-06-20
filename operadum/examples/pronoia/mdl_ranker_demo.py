"""
Demo: prediction by compression (MDL hypothesis ranker).

Given a body of observed evidence about NSCLC, rank candidate "this drug treats
NSCLC via this mechanism" hypotheses by how much each COMPRESSES the evidence.
Candidates whose claimed mechanism is actually reflected in the observations win;
an unsupported candidate doesn't help compress the evidence, so it ranks last.

    python -m examples.mdl_ranker_demo
"""

from __future__ import annotations

from pronoia.mdl_ranker import Hypothesis, rank


# Observed evidence corpus (paths, engagement, measured facts) for NSCLC.
EVIDENCE = """
mechanistic path Erlotinib inhibits EGFR; EGFR drives NSCLC; three supporting graph paths
ABPP measured target engagement Erlotinib EGFR engagement 0.95 low nanomolar IC50
mechanistic path Osimertinib inhibits EGFR T790M; EGFR drives NSCLC; engagement 0.97
clinical use Osimertinib EGFR mutant NSCLC first line; EGFR inhibition shrinks tumor
EGFR signaling drives proliferation in NSCLC; inhibiting EGFR reduces tumor growth
Sotorasib inhibits KRAS G12C; KRAS drives NSCLC subset; engagement measured 0.8
""".strip()


CANDIDATES = [
    Hypothesis(
        "Erlotinib",
        "Erlotinib treats NSCLC by inhibiting EGFR; EGFR drives NSCLC; "
        "measured engagement low nanomolar; mechanistic graph paths support it",
    ),
    Hypothesis(
        "Osimertinib",
        "Osimertinib treats NSCLC by inhibiting EGFR T790M; EGFR drives NSCLC; "
        "engagement 0.97; clinical use EGFR mutant NSCLC first line",
    ),
    Hypothesis(
        "Sotorasib",
        "Sotorasib treats NSCLC by inhibiting KRAS G12C; KRAS drives a NSCLC subset",
    ),
    Hypothesis(
        "Aspirin",
        "Aspirin treats NSCLC by inhibiting COX; cardiovascular antiplatelet effect; "
        "no EGFR or KRAS involvement reported",
    ),
]


def main() -> None:
    print("Prediction by compression — gain = bits the hypothesis saves on the evidence:\n")
    for r in rank(EVIDENCE, CANDIDATES):
        print(f"  {r.hypothesis.name:<12} gain={r.gain_bits:>7} bits  "
              f"explained={r.explained_frac:<7} (residual L(D|H)={r.residual_bits})")
    print("\nHigher gain = the hypothesis better explains/compresses the observations.")


if __name__ == "__main__":
    main()
