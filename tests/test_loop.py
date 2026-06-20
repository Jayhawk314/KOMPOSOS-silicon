# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""End-to-end test for the SelfImprovementLoop (observe→act→load→judge)."""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.category import Category
from core.loop import SelfImprovementLoop


def run(coro):
    return asyncio.run(coro)


def seed():
    cat = Category(db_path=":memory:")
    cat.connect("search", "index", name="feeds", confidence=0.9)
    cat.connect("index", "store", name="writes", confidence=0.85)
    cat.connect("parse", "search", name="emits", confidence=0.8)
    return cat


class TestSelfImprovementLoop(unittest.TestCase):
    def test_loop_fills_holes_and_converges(self):
        loop = SelfImprovementLoop(category=seed())
        start = len(loop.category.morphisms())

        history = run(loop.run(max_iterations=5))

        # It found and filled at least the obvious hole (search->store).
        edges = {(m.source, m.target) for m in loop.category.morphisms()}
        self.assertIn(("search", "store"), edges)

        # Capabilities were hot-loaded onto the host.
        self.assertIn("search_to_store", loop.host.capabilities_available)

        # The graph grew (self-extension) and the loop terminated by converging.
        self.assertGreater(len(loop.category.morphisms()), start)
        self.assertEqual(history[-1].kept, 0, "loop should converge to no new fills")

    def test_cog_gate_records_verdicts(self):
        loop = SelfImprovementLoop(category=seed())
        report = run(loop.step())
        self.assertGreater(report.gaps_found, 0)
        for fill in report.fills:
            self.assertIn(fill.cog_verdict,
                          {"AGREE", "ORPHAN", "HOLLOW", "REJECT", "PENDING", "PARTIAL"})
            self.assertTrue(fill.loaded)

    def test_operadum_and_pronoia_are_wired(self):
        loop = SelfImprovementLoop(category=seed())
        # OPERADUM + PRONOIA ship in this repo, so design should be enabled.
        self.assertTrue(loop.design_enabled)

        report = run(loop.step())
        self.assertGreater(report.gaps_found, 0)
        for fill in report.fills:
            # OPERADUM gave a design verdict...
            self.assertIn(fill.operadum_verdict,
                          {"BUILDABLE", "OVERBUDGET", "ILL_TYPED_GAP", "IMPOSSIBLE"})
            # ...and PRONOIA scored the route (compression gain in bits).
            self.assertGreaterEqual(fill.pronoia_gain, 0.0)
            self.assertIsInstance(fill.pronoia_honest, bool)

    def test_degrades_without_design(self):
        loop = SelfImprovementLoop(category=seed(), use_design=False)
        self.assertFalse(loop.design_enabled)
        report = run(loop.step())
        for fill in report.fills:
            self.assertEqual(fill.operadum_verdict, "n/a")


if __name__ == "__main__":
    unittest.main()
