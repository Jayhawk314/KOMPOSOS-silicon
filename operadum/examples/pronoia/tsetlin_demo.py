"""
Demo: Tsetlin Machine — interpretable rules, no gradients.

Part 1: XOR, the textbook non-linear problem a single linear model cannot solve.
The machine should hit 100% and the positive clauses should read like
(x0 AND NOT x1) / (NOT x0 AND x1).

Part 2: a small drug-advancement rule. Label = advance iff a strong mechanistic
graph path AND low toxicity. The machine should recover that rule as a clause.

    python -m examples.tsetlin_demo
"""

from __future__ import annotations

import numpy as np

from pronoia.tsetlin import TsetlinMachine


def xor_demo() -> None:
    X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
    y = np.array([0, 1, 1, 0])  # XOR
    tm = TsetlinMachine(n_features=2, n_clauses=10, s=3.9, T=15,
                        feature_names=["x0", "x1"], seed=1)
    tm.fit(np.repeat(X, 50, axis=0), np.repeat(y, 50), epochs=200)

    print("XOR")
    print(f"  accuracy: {tm.score(X, y):.2f}")
    print("  positive clauses (vote for class 1):")
    for cl in tm.clauses(polarity=1):
        if cl.literals:
            print(f"    IF {' AND '.join(cl.literals)}  -> class 1")


def drug_rule_demo() -> None:
    # features: strong_path, high_engagement, low_tox, has_mechanism
    names = ["strong_path", "high_engagement", "low_tox", "has_mechanism"]
    rng = np.random.default_rng(0)
    X = rng.integers(0, 2, size=(400, 4))
    # Ground truth rule: advance iff strong_path AND low_tox.
    y = ((X[:, 0] == 1) & (X[:, 2] == 1)).astype(int)

    tm = TsetlinMachine(n_features=4, n_clauses=20, s=3.9, T=15,
                        feature_names=names, seed=2)
    tm.fit(X, y, epochs=200)

    print("\nDrug advancement (truth: advance IFF strong_path AND low_tox)")
    print(f"  accuracy: {tm.score(X, y):.2f}")
    print("  positive clauses (vote to ADVANCE):")
    seen = set()
    for cl in tm.clauses(polarity=1):
        key = tuple(sorted(cl.literals))
        if cl.literals and key not in seen:
            seen.add(key)
            print(f"    IF {' AND '.join(cl.literals)}  -> ADVANCE")


def main() -> None:
    xor_demo()
    drug_rule_demo()


if __name__ == "__main__":
    main()
