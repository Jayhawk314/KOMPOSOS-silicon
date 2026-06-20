# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""Tests for core/generator.py — compositional self-improvement."""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.generator import GenerativeLoop, DEMO_PRIMITIVES, DEMO_GOALS, _demo_solver
from core.synthesis import Primitive, IOSpec, ImplementationRequest


def run(coro):
    return asyncio.run(coro)


def fresh_primitives():
    return [Primitive(p.name, p.in_type, p.out_type, p.fn) for p in DEMO_PRIMITIVES]


class TestGenerativeLoop(unittest.TestCase):
    def test_builds_all_goals_and_grows_vocabulary(self):
        loop = GenerativeLoop(fresh_primitives(), DEMO_GOALS, solver=_demo_solver)
        run(loop.run())

        for name in ("word_count", "is_long", "text_is_long"):
            self.assertIn(name, loop.built, msg=f"{name} not built")
            self.assertIn(name, [p.name for p in loop.primitives])

        # Generated capabilities are real and executable on fresh inputs.
        wc = run(loop.host.get_capability("word_count"))
        til = run(loop.host.get_capability("text_is_long"))
        self.assertEqual(wc("a b c d"), 4)
        self.assertFalse(til("two words"))     # 2 words, not > 3
        self.assertTrue(til("one two three four five"))

    def test_composite_goal_needs_a_second_pass(self):
        """text_is_long depends on capabilities built in iteration 0, so it can
        only be built in a later iteration — genuine compositional improvement."""
        loop = GenerativeLoop(fresh_primitives(), DEMO_GOALS, solver=_demo_solver)
        history = run(loop.run())

        built_at = {}
        for it in history:
            for o in it.outcomes:
                if o.built and o.goal not in built_at:
                    built_at[o.goal] = o.iteration

        self.assertEqual(built_at["word_count"], 0)
        self.assertEqual(built_at["is_long"], 0)
        self.assertGreater(built_at["text_is_long"], 0)  # strictly later

    def test_converges(self):
        loop = GenerativeLoop(fresh_primitives(), DEMO_GOALS, solver=_demo_solver)
        history = run(loop.run())
        self.assertEqual(history[-1].newly_built, 0)

    def test_no_solver_leaves_novel_goal_unbuilt(self):
        # Without the harness, is_long (novel logic) and the composite can't be built.
        loop = GenerativeLoop(fresh_primitives(), DEMO_GOALS, solver=None)
        run(loop.run())
        self.assertIn("word_count", loop.built)      # OPERADUM still composes this
        self.assertNotIn("is_long", loop.built)      # needs the harness
        self.assertNotIn("text_is_long", loop.built)  # depends on is_long


if __name__ == "__main__":
    unittest.main()
