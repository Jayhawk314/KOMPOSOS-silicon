# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Live harness bridge — Claude Code (this session) as the generator's implementer.

The generator's offline proposer (OPERADUM) composes what it can. For goals that
need novel logic, the implementation has to come from an LLM. Rather than embed a
model, we make the LLM the *driver* via a small tool protocol — the exact shape an
MCP client (a Claude Code session) speaks:

    run()                    synthesize everything the offline proposers can;
                             leave novel goals unbuilt
    pending()                list the ImplementationRequests still open
                             (each carries a prompt the session answers)
    implement(goal, source)  submit a `def solve(x):` body; it is GATED
                             (examples + COG) before it is ever accepted/loaded
    run()                    composite goals depending on freshly-built ones now build
    call(capability, value)  invoke a hot-loaded capability

The gates are why this is safe to let an LLM drive: a wrong implementation is
rejected, never loaded. `GeneratorService` is pure Python (testable offline);
`core/generator_server.py` wraps it as a FastMCP server for live use.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from core.generator import GenerativeLoop
from core.synthesis import ImplementationRequest, IOSpec, Primitive


# ══════════════════════════════════════════════════════════════════════════════
# Registry-backed solver
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class HarnessRegistry:
    """Holds implementations the harness has submitted, keyed by goal name."""
    sources: Dict[str, str] = field(default_factory=dict)

    def submit(self, goal: str, source: str) -> None:
        self.sources[goal] = source

    def get(self, goal: str) -> str:
        return self.sources.get(goal, "")


def registry_solver(registry: HarnessRegistry) -> Callable[[ImplementationRequest], str]:
    """A forge solver that answers from whatever the harness has submitted so far."""
    def solver(request: ImplementationRequest) -> str:
        return registry.get(request.spec.name)
    return solver


# ══════════════════════════════════════════════════════════════════════════════
# GeneratorService — the tool surface
# ══════════════════════════════════════════════════════════════════════════════

class GeneratorService:
    """Stateful facade over a GenerativeLoop, driven by the harness via tools."""

    def __init__(self, primitives: Sequence[Primitive], goals: Sequence[IOSpec],
                 *, max_depth: int = 5):
        self.registry = HarnessRegistry()
        self.goals: List[IOSpec] = list(goals)
        self.loop = GenerativeLoop(
            primitives, goals,
            solver=registry_solver(self.registry),
            max_depth=max_depth,
        )

    # ---- tools ----

    async def run(self, max_iterations: int = 6) -> Dict[str, Any]:
        history = await self.loop.run(max_iterations=max_iterations)
        return {
            "iterations": len(history),
            "built": sorted(self.loop.built.keys()),
            "pending": [g.name for g in self.goals if g.name not in self.loop.built],
            "vocabulary": [p.name for p in self.loop.primitives],
        }

    def pending(self) -> List[Dict[str, Any]]:
        """Open implementation requests — what the harness still needs to write."""
        out: List[Dict[str, Any]] = []
        for goal in self.goals:
            if goal.name in self.loop.built:
                continue
            req = ImplementationRequest(spec=goal, primitives=list(self.loop.primitives))
            out.append({
                "goal": goal.name,
                "in_type": goal.in_type,
                "out_type": goal.out_type,
                "examples": goal.examples,
                "prompt": req.as_prompt(),
            })
        return out

    async def implement(self, goal: str, source: str) -> Dict[str, Any]:
        """Submit an implementation; it is gated (examples + COG) before acceptance."""
        self.registry.submit(goal, source)
        # One synthesis pass: the just-submitted goal (and any now-unblocked
        # composites) go through the forge gates.
        before = set(self.loop.built)
        await self.loop.step(iteration=-1)
        now_built = set(self.loop.built) - before
        accepted = goal in self.loop.built
        return {
            "goal": goal,
            "accepted": accepted,
            "reason": "passed example + COG gates" if accepted
                      else "rejected by gates (examples failed or COG REJECT)",
            "also_built": sorted(now_built - {goal}),
        }

    async def call(self, capability: str, value: Any) -> Dict[str, Any]:
        fn = await self.loop.host.get_capability(capability)
        if fn is None:
            return {"capability": capability, "error": "not built"}
        # n-ary capabilities take multiple positional args; pass a list/tuple to splat.
        output = fn(*value) if isinstance(value, (list, tuple)) else fn(value)
        return {"capability": capability, "input": value, "output": output}

    def status(self) -> Dict[str, Any]:
        return {
            "built": sorted(self.loop.built.keys()),
            "vocabulary": [p.name for p in self.loop.primitives],
            "open_goals": [g.name for g in self.goals if g.name not in self.loop.built],
            "backend": getattr(self.loop.host, "backend", "?"),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Demo: the live two-phase exchange (harness supplies is_prime)
# ══════════════════════════════════════════════════════════════════════════════

async def _demo() -> None:
    from domains import NUMERIC_PRIMITIVES, NUMERIC_GOALS

    svc = GeneratorService(NUMERIC_PRIMITIVES, NUMERIC_GOALS)

    print("phase 1 — run offline proposers (OPERADUM):")
    print("  ", await svc.run())

    print("\nphase 2 — pending implementation requests (for the harness):")
    for req in svc.pending():
        print(f"   - {req['goal']}: {req['in_type']}->{req['out_type']}")

    # phase 3 — the harness (this session) writes the novel primitive and submits it.
    is_prime_src = (
        "def solve(n):\n"
        "    n = int(n)\n"
        "    if n < 2:\n"
        "        return False\n"
        "    i = 2\n"
        "    while i * i <= n:\n"
        "        if n % i == 0:\n"
        "            return False\n"
        "        i += 1\n"
        "    return True\n"
    )
    print("\nphase 3 — harness submits is_prime (gated on submission):")
    print("  ", await svc.implement("is_prime", is_prime_src))

    print("\nphase 4 — run again; the composite goal can now build:")
    print("  ", await svc.run())

    print("\nphase 5 — call the generated capabilities on fresh inputs:")
    for cap, val in [("digit_sum", 778), ("is_prime", 97), ("digit_sum_is_prime", 41)]:
        print("  ", await svc.call(cap, val))


if __name__ == "__main__":
    asyncio.run(_demo())
