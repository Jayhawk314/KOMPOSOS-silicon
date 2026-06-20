# SPDX-License-Identifier: Apache-2.0
"""
Scoreboard — a falsifiable measure of whether the loop finds REAL structure.

Self-improvement without measurement optimizes noise. This harness answers one
number: *given a graph with known structure, if we hide some edges, does the loop
recover them — and does it refrain from inventing edges that shouldn't exist?*

Protocol (link-prediction style):
  1. Build a ground-truth category: a spine chain plus derivable shortcuts
     (transitive edges A->C where A->B->C exists) and one NON-derivable pair
     (no connecting path — a trap).
  2. Hold out (remove) the shortcuts and the trap.
  3. Run the self-improvement loop on the remaining graph.
  4. Score:
       recall     = recovered_derivable / held_out_derivable
       precision  = recovered_derivable / all_edges_added
       hallucinated = added edges that match the non-derivable trap (must be 0)
       spurious   = added edges that are not ground truth at all

A healthy system: recall high, precision high, hallucinated = 0. A system that
games its metric by adding edges everywhere shows high recall but low precision
and/or hallucinated > 0 — which is exactly what the executable + honesty gates
are there to prevent. That tension is the point: the number is falsifiable.

Run:
    python -m core.scoreboard
    python -m core.scoreboard --observer conjecture
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from typing import List, Set, Tuple

from core.category import Category
from core.loop import SelfImprovementLoop

Edge = Tuple[str, str]  # (source, target)


@dataclass
class ScoreReport:
    held_out_derivable: Set[Edge]
    held_out_nonderivable: Set[Edge]
    recovered: Set[Edge]
    hallucinated: Set[Edge]          # recovered a non-derivable trap (bad)
    spurious: Set[Edge]              # added edges that are not ground truth at all
    added: Set[Edge] = field(default_factory=set)

    @property
    def recall(self) -> float:
        n = len(self.held_out_derivable)
        return len(self.recovered) / n if n else 0.0

    @property
    def precision(self) -> float:
        n = len(self.added)
        return len(self.recovered) / n if n else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def render(self) -> str:
        ok = (self.recall >= 0.99 and not self.hallucinated)
        lines = [
            "=" * 60,
            "  KOMPOSOS self-improvement scoreboard",
            "=" * 60,
            f"held-out derivable edges : {len(self.held_out_derivable)}  {sorted(self.held_out_derivable)}",
            f"held-out trap (no path)  : {len(self.held_out_nonderivable)}  {sorted(self.held_out_nonderivable)}",
            f"edges the loop added     : {len(self.added)}  {sorted(self.added)}",
            "-" * 60,
            f"recovered (correct)      : {len(self.recovered)}  {sorted(self.recovered)}",
            f"hallucinated trap edges  : {len(self.hallucinated)}  {sorted(self.hallucinated)}  (must be 0)",
            f"spurious (not in truth)  : {len(self.spurious)}  {sorted(self.spurious)}",
            "-" * 60,
            f"RECALL    = {self.recall:.2f}",
            f"PRECISION = {self.precision:.2f}",
            f"F1        = {self.f1:.2f}",
            f"VERDICT   = {'PASS' if ok else 'FAIL'}  (recall>=0.99 and no hallucination)",
            "=" * 60,
        ]
        return "\n".join(lines)


def _build_ground_truth() -> Tuple[Category, Set[Edge], Set[Edge]]:
    """Return (category_with_holdouts_removed, derivable_holdouts, trap_holdouts)."""
    cat = Category(db_path=":memory:")
    # Executable spine (str->str) so recovered shortcuts are real, verifiable composites.
    spine = [
        ("a", "b", lambda s: s + "B"),
        ("b", "c", lambda s: s + "C"),
        ("c", "d", lambda s: s + "D"),
    ]
    for src, tgt, fn in spine:
        cat.connect(src, tgt, name="step", confidence=0.9, fn=fn)

    # Derivable shortcuts (transitive edges) we will HOLD OUT and expect recovered.
    derivable: Set[Edge] = {("a", "c"), ("b", "d"), ("a", "d")}

    # A trap: an isolated pair with NO connecting path. Add the endpoints only.
    cat.add("x")
    cat.add("y")
    trap: Set[Edge] = {("x", "y")}

    # The ground truth (for scoring) is spine + derivable + trap; the live graph
    # starts as spine only (the held-out edges are simply never added).
    return cat, derivable, trap


def _current_edges(cat: Category) -> Set[Edge]:
    return {(m.source, m.target) for m in cat.morphisms()}


async def run_scoreboard(
    observer: str = "optimus", min_grounding: float = 0.5, embeddings=None,
) -> ScoreReport:
    cat, derivable, trap = _build_ground_truth()
    seed_edges = _current_edges(cat)

    loop = SelfImprovementLoop(
        category=cat, observer=observer, min_grounding=min_grounding, max_depth=4,
        embeddings=embeddings,
    )
    await loop.run(max_iterations=6, max_fills=20)

    final_edges = _current_edges(cat)
    added = final_edges - seed_edges
    held_out = derivable | trap

    recovered = added & derivable
    hallucinated = added & trap
    spurious = added - held_out

    return ScoreReport(
        held_out_derivable=derivable,
        held_out_nonderivable=trap,
        recovered=recovered,
        hallucinated=hallucinated,
        spurious=spurious,
        added=added,
    )


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--observer", default="optimus", choices=["optimus", "conjecture"])
    ap.add_argument("--min-grounding", type=float, default=0.5)
    ap.add_argument("--embeddings", default=None, help="'auto' to enable semantic proposals")
    args = ap.parse_args(argv)
    report = asyncio.run(run_scoreboard(args.observer, args.min_grounding, args.embeddings))
    print(report.render())


if __name__ == "__main__":
    main()
