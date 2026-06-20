# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Generator MCP Server — drive the self-improving capability generator from a
Claude Code session (the live harness).

Tools:
  generator_status                  — built capabilities, vocabulary, open goals
  generator_run                     — synthesize everything the offline proposers can
  generator_pending                 — list open implementation requests (+ prompts)
  generator_implement(goal, source) — submit a `def solve(x):` body; GATED before load
  generator_call(capability, value) — invoke a hot-loaded capability

Typical live loop:
  generator_run → generator_pending → (write code) → generator_implement → generator_run

Run:
  python -m core.generator_server
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP

from core.harness import GeneratorService
from domains import NUMERIC_PRIMITIVES, NUMERIC_GOALS

mcp = FastMCP(
    "komposos-generator",
    instructions="Self-improving capability generator. OPERADUM composes what it "
                 "can; you (the harness) implement novel goals; example + COG gates "
                 "keep every submission honest.",
)

# Singleton service per server process. Default domain: numeric (swap freely).
_service: GeneratorService = GeneratorService(NUMERIC_PRIMITIVES, NUMERIC_GOALS)


def _run(coro):
    return asyncio.run(coro)


@mcp.tool()
def generator_status() -> str:
    """Report built capabilities, the current primitive vocabulary, and open goals."""
    return json.dumps(_service.status(), indent=2)


@mcp.tool()
def generator_run(max_iterations: int = 6) -> str:
    """Run synthesis passes: OPERADUM composes primitives; composites build once
    their dependencies exist. Returns what got built and what is still pending."""
    return json.dumps(_run(_service.run(max_iterations)), indent=2)


@mcp.tool()
def generator_pending() -> str:
    """List open implementation requests. Each item's `prompt` tells you exactly
    what `def solve(x):` to write so it passes the examples."""
    return json.dumps(_service.pending(), indent=2)


@mcp.tool()
def generator_implement(goal: str, source: str) -> str:
    """Submit a Python implementation (`def solve(x): ...`) for a goal. It is run
    against the goal's examples and checked by COG; it is loaded ONLY if accepted."""
    return json.dumps(_run(_service.implement(goal, source)), indent=2)


@mcp.tool()
def generator_call(capability: str, value: str) -> str:
    """Invoke a hot-loaded capability on a value. Numeric inputs are coerced to int."""
    coerced: object = value
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        pass
    return json.dumps(_run(_service.call(capability, coerced)), indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
