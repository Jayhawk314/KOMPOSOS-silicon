# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
GenerativeLoop — the self-improving capability generator.

This fuses the pieces into one loop whose act step is real synthesis, not graph
shortcuts:

    OPTIMUS    observe : over the current primitive type-graph, which goals are
                         structurally reachable? (feasibility + opportunities)
    FORGE      act      : CapabilityForge synthesizes each unbuilt goal —
                         OPERADUM composes primitives, or the Claude Code harness
                         writes novel logic — behind the EXAMPLE + COG gates.
    HOST       grow     : a built capability is hot-loaded AND appended to the
                         primitive set, so it becomes a building block for later
                         goals. The system extends its own vocabulary.

Because built capabilities become primitives, a goal that was *unbuildable* this
iteration can become buildable the next, once its dependencies exist. That is
genuine self-improvement: each pass makes the next pass more capable, and the
loop converges when no new capability can be added.

Run:
    python -m core.generator
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from core.category import Category
from core.host import Host, build_host
from core.optimus import OptimusEngine
from core.synthesis import (
    CapabilityForge, Candidate, HarnessProposer, IOSpec, ImplementationRequest,
    OperadumProposer, Primitive, Proposer,
)

logger = logging.getLogger(__name__)


@dataclass
class GoalOutcome:
    goal: str
    built: bool
    iteration: int
    by: str = ""              # operadum | harness | "" (failed)
    cog_verdict: str = ""
    route: str = ""
    reachable: bool = False   # OPTIMUS: was out_type reachable from in_type?
    note: str = ""


@dataclass
class GenIteration:
    index: int
    opportunities: int        # OPTIMUS structural-gap count over current primitives
    outcomes: List[GoalOutcome] = field(default_factory=list)

    @property
    def newly_built(self) -> int:
        return sum(1 for o in self.outcomes if o.built)


class GenerativeLoop:
    """Observe (OPTIMUS) → synthesize (FORGE) → grow vocabulary → repeat."""

    def __init__(
        self,
        primitives: Sequence[Primitive],
        goals: Sequence[IOSpec],
        *,
        host: Optional[Host] = None,
        solver: Optional[Callable[[ImplementationRequest], str]] = None,
        max_depth: int = 4,
    ):
        self.primitives: List[Primitive] = list(primitives)
        self.goals: List[IOSpec] = list(goals)
        self.host = host or build_host()
        self.solver = solver
        self.max_depth = max_depth
        self._built: Dict[str, Candidate] = {}

    @property
    def built(self) -> Dict[str, Candidate]:
        return dict(self._built)

    # ---------------- observe (OPTIMUS) ----------------

    def _primitive_category(self) -> Category:
        cat = Category(db_path=":memory:")
        for p in self.primitives:
            for in_type in p.input_types:
                cat.connect(in_type, p.out_type, name=p.name, confidence=0.9)
        return cat

    def _reachable(self, src: str, dst: str) -> bool:
        adj: Dict[str, List[str]] = {}
        for p in self.primitives:
            adj.setdefault(p.in_type, []).append(p.out_type)
        seen, stack = set(), [src]
        while stack:
            node = stack.pop()
            if node == dst:
                return True
            if node in seen:
                continue
            seen.add(node)
            stack.extend(adj.get(node, []))
        return False

    def _opportunities(self) -> int:
        """OPTIMUS: how many type-pairs are bridgeable (structural holes) right now."""
        try:
            return len(OptimusEngine(self._primitive_category(),
                                     max_depth=self.max_depth).find_structural_gaps())
        except Exception:
            return 0

    def _proposers(self) -> List[Proposer]:
        proposers: List[Proposer] = [OperadumProposer(max_depth=self.max_depth)]
        if self.solver is not None:
            proposers.append(HarnessProposer(solver=self.solver))
        return proposers

    # ---------------- one pass ----------------

    async def step(self, iteration: int) -> GenIteration:
        result = GenIteration(index=iteration, opportunities=self._opportunities())

        for goal in self.goals:
            if goal.name in self._built:
                continue

            reachable = self._reachable(goal.in_type, goal.out_type)
            forge = CapabilityForge(
                self.primitives, host=self.host,
                category=self._primitive_category(),
                proposers=self._proposers(),
            )
            res = await forge.synthesize(goal)

            if res.ok:
                self._built[goal.name] = res.candidate
                # GROW: the new capability becomes a primitive for future goals.
                self.primitives.append(
                    Primitive(goal.name, goal.in_type, goal.out_type, res.candidate.fn)
                )
                result.outcomes.append(GoalOutcome(
                    goal=goal.name, built=True, iteration=iteration,
                    by=res.candidate.source, cog_verdict=res.gate.cog_verdict,
                    route=res.candidate.route, reachable=reachable,
                ))
            else:
                result.outcomes.append(GoalOutcome(
                    goal=goal.name, built=False, iteration=iteration,
                    reachable=reachable, note=res.note,
                ))
        return result

    async def run(self, *, max_iterations: int = 6) -> List[GenIteration]:
        history: List[GenIteration] = []
        for i in range(max_iterations):
            it = await self.step(i)
            history.append(it)
            logger.info("iteration %d: opportunities=%d built=%d",
                        i, it.opportunities, it.newly_built)
            if it.newly_built == 0:
                break  # no new capability could be added -> converged
        return history


# ══════════════════════════════════════════════════════════════════════════════
# Demo: compositional self-improvement
# ══════════════════════════════════════════════════════════════════════════════

DEMO_PRIMITIVES = [
    Primitive("tokenize", "Text", "Tokens", str.split),
    Primitive("count", "Tokens", "Int", len),
]

# Goals are ordered so the composite goal (text_is_long) is attempted BEFORE its
# dependencies exist — proving the loop needs a second pass once they're built.
DEMO_GOALS = [
    IOSpec("text_is_long", "Text", "Bool",            # composite: word_count then is_long
           [("a b c d e f", True), ("hi there", False),
            ("one two three four", True), ("solo", False)]),
    IOSpec("word_count", "Text", "Int",               # OPERADUM: tokenize -> count
           [("a b c", 3), ("hello world there", 3), ("x", 1)]),
    IOSpec("is_long", "Int", "Bool",                  # novel logic -> harness
           [(5, True), (2, False), (4, True), (3, False)]),
]


def _demo_solver(request: ImplementationRequest) -> str:
    """The Claude Code harness stand-in: writes the one novel primitive (is_long)."""
    if request.spec.name == "is_long":
        return "def solve(n):\n    return n > 3\n"
    return ""


async def _demo() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    loop = GenerativeLoop(DEMO_PRIMITIVES, DEMO_GOALS, solver=_demo_solver)
    print(f"host backend: {getattr(loop.host, 'backend', '?')}")
    print(f"start vocabulary: {[p.name for p in loop.primitives]}\n")

    history = await loop.run()

    for it in history:
        print(f"iteration {it.index}: OPTIMUS opportunities={it.opportunities}, "
              f"built={it.newly_built}")
        for o in it.outcomes:
            if o.built:
                print(f"   [BUILT] {o.goal:<13} by {o.by:<8} COG={o.cog_verdict:<7} "
                      f"reachable={o.reachable}  {o.route}")
            else:
                print(f"   [defer] {o.goal:<13} (reachable={o.reachable}) {o.note}")
        print()

    print(f"final vocabulary: {[p.name for p in loop.primitives]}")
    print("running the generated capabilities on fresh inputs:")
    for cap, arg in [("word_count", "a b c d"), ("is_long", 9), ("text_is_long", "two words")]:
        fn = await loop.host.get_capability(cap)
        print(f"   {cap}({arg!r}) = {fn(arg) if fn else 'MISSING'}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_demo())
