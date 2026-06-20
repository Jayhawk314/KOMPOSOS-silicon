# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Concept-learning accuracy -- PAC-style Boolean generalization.

The most rigorous "what accuracy levels are possible?" test. We learn a RANDOM
Boolean function of k inputs from a PARTIAL truth table: synthesize the smallest
circuit consistent with m training rows, then measure accuracy on the held-out
rows. This is concept learning in the PAC sense, and it spans the whole accuracy
range -- from chance (few rows) to exact (all rows) -- because a random Boolean
function is genuinely hard to pin down from partial data.

It exercises the network (Diagram) layer and reports two honest limits at once:
  * holdout_accuracy -- generalization quality of the smallest consistent circuit
    (OPERADUM's Occam inductive bias);
  * solve_rate       -- how often a consistent circuit even fits in the node
    budget (the search ceiling: hard functions need more gates than max_nodes).
"""

from __future__ import annotations
import random
from dataclasses import dataclass
from itertools import product
from statistics import mean
from typing import Dict, List, Tuple

from ..gate.diagram_synth import synthesize_diagram, truth_table_validator
from ..domains.logic_circuit import LogicCircuitDomain

_NAMES = "abcdef"


def _assignments(k: int) -> List[Dict[str, bool]]:
    names = _NAMES[:k]
    return [dict(zip(names, bits)) for bits in product((False, True), repeat=k)]


@dataclass
class ConceptPoint:
    rows_seen: int
    total_rows: int
    holdout_accuracy: float     # over solved trials with held-out rows
    solve_rate: float           # fraction of trials a consistent circuit fit the budget

    def __str__(self) -> str:
        frac = self.rows_seen / self.total_rows
        return (f"  rows_seen={self.rows_seen}/{self.total_rows} ({frac:.0%}): "
                f"holdout_accuracy={self.holdout_accuracy:.3f}  "
                f"solve_rate={self.solve_rate:.3f}")


def _random_circuit_target(op, inputs, rng, n_gates: int):
    """A target drawn from the hypothesis class: a random small circuit. Its
    truth function is therefore guaranteed synthesizable and has structure --
    the *realizable* learning setting (vs. a structureless random function)."""
    from ..core.diagram import Diagram
    gate_names = ["nand", "and", "or", "not"]
    for _attempt in range(20):
        d = Diagram("target")
        by_colour: Dict[str, list] = {}
        for name, colour in inputs:
            by_colour.setdefault(colour, []).append(d.add_input(name, colour))
        last = None
        for _ in range(n_gates):
            g = op.get_op(rng.choice(gate_names))
            srcs = [rng.choice(by_colour["Bit"]) for _ in range(g.arity)]
            last = d.add_node(g, srcs)
            by_colour["Bit"].append(last)
        if last is not None:
            d.set_output(last)
            return d.realize()
    return None


def measure_concept_learning(k: int = 3, m_values: Tuple[int, ...] = (2, 4, 6, 8),
                             trials: int = 24, seed: int = 0, max_nodes: int = 4,
                             gates: Tuple[str, ...] = ("nand", "and", "or", "not"),
                             realizable: bool = False, target_gates: int = 3,
                             limit: int = 20000) -> List[ConceptPoint]:
    """
    Accuracy vs. fraction of the truth table seen.

    `realizable=False` (default): structureless RANDOM targets -- the agnostic
    case; accuracy stays at chance until the table is complete (no free lunch).
    `realizable=True`: targets drawn from the circuit class -- a genuine learning
    curve from chance toward exact as more rows are seen.
    """
    op = LogicCircuitDomain().build_operad()
    inputs = [(n, "Bit") for n in _NAMES[:k]]
    all_rows = _assignments(k)
    total = len(all_rows)
    curve: List[ConceptPoint] = []

    for m in m_values:
        rng = random.Random(seed + m)
        accs: List[float] = []
        solved = 0
        attempts = 0
        for _ in range(trials):
            attempts += 1
            if realizable:
                target_fn = _random_circuit_target(op, inputs, rng, target_gates)
                if target_fn is None:
                    attempts -= 1
                    continue

                def oracle(assign: Dict[str, bool], _f=target_fn) -> bool:
                    return _f(**assign)
            else:
                target = {tuple(a[n] for n in _NAMES[:k]): rng.random() < 0.5
                          for a in all_rows}

                def oracle(assign: Dict[str, bool], _t=target) -> bool:
                    return _t[tuple(assign[n] for n in _NAMES[:k])]

            rng.shuffle(all_rows)
            train = all_rows[:m]
            test = all_rows[m:]
            table = [(a, oracle(a)) for a in train]
            design = synthesize_diagram(op, inputs, "Bit",
                                        truth_table_validator(table),
                                        gate_ops=list(gates), max_nodes=max_nodes,
                                        limit=limit)
            if design is None:
                continue   # no consistent circuit within the node budget
            solved += 1
            if not test:
                accs.append(1.0)
                continue
            correct = sum(1 for a in test if design.artifact(**a) == oracle(a))
            accs.append(correct / len(test))
        curve.append(ConceptPoint(
            rows_seen=m, total_rows=total,
            holdout_accuracy=mean(accs) if accs else 0.0,
            solve_rate=solved / attempts if attempts else 0.0,
        ))
    return curve


if __name__ == "__main__":
    print("PAC-style concept learning of Boolean functions (k=3 inputs)\n")
    print("REALIZABLE targets (drawn from the circuit class) -- a learning curve:")
    for point in measure_concept_learning(realizable=True, trials=20, target_gates=3,
                                          max_nodes=4, limit=8000):
        print(point)
    print("\nAGNOSTIC targets (structureless random functions) -- no free lunch:")
    for point in measure_concept_learning(realizable=False, trials=12,
                                          max_nodes=3, limit=8000):
        print(point)
    print("\nRealizable: accuracy climbs chance -> exact as rows are seen.")
    print("Agnostic: accuracy stays at chance until the table is complete --")
    print("structureless concepts are unlearnable from partial data, by ANY learner.")
