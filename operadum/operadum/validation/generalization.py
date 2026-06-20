# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Generalization accuracy -- the test where OPERADUM can be WRONG.

Every other harness measures correctness-by-construction (the SemanticGate only
returns designs that pass the validator) or exhaustive optimum recall (trivially
1.0 within the depth bound). Neither tests *accuracy levels* -- a number that
varies below 1.0 and reveals limits.

This one does. We synthesize a program from a FEW input/output examples, then
test it on HELD-OUT inputs the synthesizer never saw. A program that fits the
training examples can still be wrong on new inputs (overfitting), so held-out
accuracy is a genuine number in [0, 1]. Sweeping the number of training examples
produces an accuracy *curve* that exposes OPERADUM's inductive bias: it returns
the CHEAPEST consistent program, an Occam's-razor prior that under-determined
specs can mislead.

This is exactly how programming-by-example / concept learning is evaluated, and
it is the right way to ask "what accuracy levels are possible here?"
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from statistics import mean
from typing import Callable, Dict, List, Tuple

from ..core.types import Spec
from ..gate.semantic_gate import SemanticGate
from ..domains.program_synthesis import ProgramSynthesisDomain


# Ground-truth oracles the domain can express (String -> Int).
ORACLES: Dict[str, Callable[[str], int]] = {
    "word_count":    lambda s: len(s.split()),
    "char_count":    lambda s: len(s),
    "total_letters": lambda s: sum(len(w) for w in s.split()),
    "longest_word":  lambda s: max((len(w) for w in s.split()), default=0),
}


def sample_string(rng: random.Random) -> str:
    """A random sentence: 1-5 words of 1-6 letters from a small alphabet."""
    n = rng.randint(1, 5)
    return " ".join(
        "".join(rng.choice("abcde") for _ in range(rng.randint(1, 6)))
        for _ in range(n)
    )


@dataclass
class CurvePoint:
    n_train: int
    holdout_accuracy: float     # mean fraction of held-out inputs predicted correctly
    exact_recovery: float       # fraction of trials that generalize perfectly
    solve_rate: float           # fraction of trials a consistent program was found

    def __str__(self) -> str:
        return (f"  n_train={self.n_train}: holdout_accuracy={self.holdout_accuracy:.3f}  "
                f"exact_recovery={self.exact_recovery:.3f}  solve_rate={self.solve_rate:.3f}")


def measure_generalization(n_train_values: Tuple[int, ...] = (1, 2, 3, 5),
                           n_test: int = 60, trials: int = 25,
                           seed: int = 0, max_depth: int = 5) -> List[CurvePoint]:
    """
    Accuracy curve: for each training-set size, average held-out accuracy over
    `trials` random tasks per oracle. Deterministic for a fixed seed.
    """
    op = ProgramSynthesisDomain().build_operad()
    gate = SemanticGate(op, max_depth=max_depth)
    spec = Spec(("String",), "Int")
    curve: List[CurvePoint] = []

    for n_train in n_train_values:
        rng = random.Random(seed + n_train)   # vary so points are independent draws
        accs: List[float] = []
        recoveries: List[int] = []
        solved = 0
        total = 0
        for name, oracle in ORACLES.items():
            for _ in range(trials):
                total += 1
                train_inputs = [sample_string(rng) for _ in range(n_train)]
                examples = [(s, oracle(s)) for s in train_inputs]
                design = gate.by_examples(spec, examples)
                if design is None:
                    accs.append(0.0)
                    recoveries.append(0)
                    continue
                solved += 1
                test_inputs = [sample_string(rng) for _ in range(n_test)]
                correct = sum(1 for s in test_inputs
                              if design.artifact(s) == oracle(s))
                acc = correct / n_test
                accs.append(acc)
                recoveries.append(1 if acc == 1.0 else 0)
        curve.append(CurvePoint(
            n_train=n_train,
            holdout_accuracy=mean(accs) if accs else 0.0,
            exact_recovery=mean(recoveries) if recoveries else 0.0,
            solve_rate=solved / total if total else 0.0,
        ))
    return curve


if __name__ == "__main__":
    print("Program-by-example generalization accuracy")
    print("(synthesize from n_train examples, test on held-out inputs)\n")
    for point in measure_generalization():
        print(point)
    print("\nAccuracy rises with examples: few examples under-determine the spec,")
    print("so the cheapest consistent program (Occam bias) can overfit.")
