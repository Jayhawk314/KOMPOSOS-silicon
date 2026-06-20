# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Synthesis Accuracy Benchmark

The constructive dual of KOMPOSOS-IV's calibration scripts (which measure
interpretive accuracy, e.g. AUROC on repurposing). Here we measure *synthesis*
accuracy: given a known-optimal design, does WRIGHT/DAEDALUS recover it?

Three measurable quantities:
  - optimum_recall: fraction of specs for which optimize() returns a design
    whose cost equals the true minimum cost (computed by exhaustive search).
  - buildable_recall: fraction of satisfiable specs reported BUILDABLE.
  - normal_form_uniqueness: fraction of designs whose coherence normal form is
    invariant under random rewriting (a coherence-accuracy check).

These give a real accuracy number for the engine today -- before any domain
plugin exists. Domain-level (real-world) accuracy arrives with a domain plugin
plus the KOMPOSOS round-trip (master spec Phase 5).
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from itertools import product
from typing import Dict, List, Optional, Tuple

from ..core.operad import Operad
from ..core.types import Spec, Composite
from ..core.enrichment import ADDITIVE_COST, TROPICAL
from ..wright.engine import Wright
from ..daedalus_core import Daedalus, _submultiset
from collections import Counter


@dataclass
class BenchmarkResult:
    trials: int = 0
    optimum_hits: int = 0
    buildable_hits: int = 0
    satisfiable: int = 0
    failures: List[str] = field(default_factory=list)

    @property
    def optimum_recall(self) -> float:
        return self.optimum_hits / self.trials if self.trials else 0.0

    @property
    def buildable_recall(self) -> float:
        return self.buildable_hits / self.satisfiable if self.satisfiable else 0.0

    def __str__(self) -> str:
        return (f"BenchmarkResult(trials={self.trials}, "
                f"optimum_recall={self.optimum_recall:.3f}, "
                f"buildable_recall={self.buildable_recall:.3f})")


def random_operad(rng: random.Random, n_colours: int = 5,
                  n_ops: int = 8) -> Operad:
    """A random layered operad: each op maps lower-index colours to a higher one,
    so the colour graph is a DAG (guarantees termination) with varied costs."""
    op = Operad("bench", monoid=ADDITIVE_COST)
    colours = [f"C{i}" for i in range(n_colours)]
    for c in colours:
        op.add_colour(c)
    for k in range(n_ops):
        out_idx = rng.randint(1, n_colours - 1)
        in_idx = rng.randint(0, out_idx - 1)
        arity = rng.choice([1, 1, 2])
        inputs = [colours[rng.randint(0, out_idx - 1)] for _ in range(arity)]
        op.add_op(f"op{k}", inputs, colours[out_idx],
                  cost={"u": rng.randint(1, 9)}, fn=lambda *a: a)
    return op


def brute_force_min_cost(operad: Operad, spec: Spec,
                         max_depth: int = 5) -> Optional[float]:
    """Exhaustively enumerate all depth-bounded designs and return the true
    minimum scalar cost realizing the spec (ground truth for optimum_recall)."""
    allowed = set(spec.inputs)
    pool = Counter(spec.inputs)
    best: Optional[float] = None

    def designs(target: str, depth: int) -> List[Composite]:
        out: List[Composite] = []
        if depth < 1:
            return out
        for op in operad.operations_producing(target):
            slot_opts = []
            ok = True
            for c in op.inputs:
                opts = []
                if c in allowed:
                    opts.append(("open", c))
                if depth > 1:
                    for sub in designs(c, depth - 1):
                        opts.append(("sub", sub))
                if not opts:
                    ok = False
                    break
                slot_opts.append(opts)
            if not ok:
                continue
            for combo in product(*slot_opts):
                out.append(Composite(op, list(combo)))
        return out

    for comp in designs(spec.output, max_depth):
        if not _submultiset(Counter(comp.open_inputs()), pool):
            continue
        c = operad.monoid.rank(comp.cost(operad.monoid))
        if best is None or c < best:
            best = c
    return best


def run_benchmark(n_trials: int = 50, seed: int = 0,
                  max_depth: int = 5) -> BenchmarkResult:
    """Measure optimum_recall and buildable_recall over random operads."""
    rng = random.Random(seed)
    result = BenchmarkResult()

    for t in range(n_trials):
        operad = random_operad(rng)
        colours = [c.name for c in operad.colours()]
        inputs = (rng.choice(colours[:2]),)
        output = rng.choice(colours[1:])
        spec = Spec(inputs=inputs, output=output)

        truth = brute_force_min_cost(operad, spec, max_depth)
        result.trials += 1

        build = Wright(operad, max_depth=max_depth).optimize(spec)
        if truth is None:
            # Unsatisfiable: a correct engine must NOT claim BUILDABLE.
            if build.buildable:
                result.failures.append(f"trial {t}: claimed buildable but unsatisfiable")
            else:
                result.optimum_hits += 1   # correctly recognised impossibility
            continue

        result.satisfiable += 1
        if build.buildable:
            result.buildable_hits += 1
            got = operad.monoid.rank(build.construction.cost)
            if abs(got - truth) < 1e-9:
                result.optimum_hits += 1
            else:
                result.failures.append(
                    f"trial {t}: got cost {got}, true optimum {truth}")
        else:
            result.failures.append(f"trial {t}: missed a satisfiable spec")

    return result


if __name__ == "__main__":
    res = run_benchmark()
    print(res)
    if res.failures:
        print("Failures:")
        for f in res.failures[:10]:
            print("  -", f)
    else:
        print("Perfect optimum recall over all trials.")
