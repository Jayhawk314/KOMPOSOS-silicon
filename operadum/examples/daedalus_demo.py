# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
OPERADUM Phase 2 demo: cheapest in-budget design, proven resource-sound.

Run:  python -m examples.daedalus_demo

Shows:
  1. DAEDALUS picking the cost-minimal design over several competing routes.
  2. WRIGHT.optimize() returning that design as a runnable BUILDABLE.
  3. The RES gate proving it linear-sound (its (x)/-o sequent).
  4. The non-cartesian law: a design that reuses a one-shot permit is rejected.
"""

from operadum import Operad, Spec, Wright, ADDITIVE_COST, LINEAR_TOKENS
from operadum.daedalus_core import Daedalus


def optimal_pipeline():
    op = Operad("pipeline", monoid=ADDITIVE_COST)
    op.add_op("tok", ["RawText"], "Tokens", cost={"ms": 2}, fn=lambda s: s.split())
    op.add_op("embed_fast", ["Tokens"], "Embedding", cost={"ms": 3}, fn=len)
    op.add_op("embed_slow", ["Tokens"], "Embedding", cost={"ms": 30}, fn=len)
    op.add_op("direct", ["RawText"], "Embedding", cost={"ms": 99},
              fn=lambda s: len(s.split()))

    w = Wright(op)
    spec = Spec(inputs=("RawText",), output="Embedding", budget={"ms": 20})

    print("DAEDALUS over 3 competing routes to (RawText) -> Embedding:")
    res = Daedalus(op).search(spec)
    print(f"  cheapest = {res.best.to_wiring()}  cost={res.best_cost}  "
          f"(expansions={res.stats.expansions}, frontier={res.stats.frontier_size})")
    print()

    build = w.optimize(spec)
    print("WRIGHT.optimize ->", build)
    print("  run('the quick brown fox') =", build.construction.artifact("the quick brown fox"))
    judgement = w.res_gate.prove_sound(build.construction.composite)
    print("  resource-soundness proof:", judgement)
    print()


def linear_discipline():
    print("Non-cartesian law (LINEAR_TOKENS):")
    op = Operad("site", monoid=LINEAR_TOKENS)
    op.add_op("use", ["Site"], "Part", cost={"permit_42": 1}, fn=lambda x: x)
    op.add_op("join", ["Part", "Part"], "Build", cost={}, fn=lambda a, b: (a, b))
    res = Daedalus(op).search(Spec(inputs=("Site", "Site"), output="Build"))
    print(f"  join(use, use) reuses permit_42 -> found_any={res.found_any} "
          f"(pruned_unsound={res.stats.pruned_unsound})")
    print("  the spent permit cannot be spent twice: the design is unbuildable.")


if __name__ == "__main__":
    optimal_pipeline()
    linear_discipline()
