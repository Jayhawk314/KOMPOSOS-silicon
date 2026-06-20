# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Tests for core/host.py — the FORGE-backed plugin-host seam.

Proves the self-improvement loop (plugin_generator → hot-load) runs end to end
with ZERO dependency on any external Orion framework.
"""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.host import build_host, ForgeHost, Plugin, on, Event


def run(coro):
    return asyncio.run(coro)


class TestOrionIndependence(unittest.TestCase):
    def test_orion_core_is_not_required(self):
        """The whole point: orion_core is not importable here, and we don't need it."""
        with self.assertRaises(ImportError):
            import orion_core  # noqa: F401


class TestForgeHost(unittest.TestCase):
    def test_builds_on_forge_backend(self):
        host = build_host()
        self.assertIsInstance(host, ForgeHost)
        # FORGE ships in this repo (operadum.forge), so we expect the forge backend.
        self.assertEqual(host.backend, "forge")

    def test_register_emit_capability_unload(self):
        host = build_host()
        seen = []

        class Greeter(Plugin):
            name = "greeter"
            provides = ["greeting"]

            def __init__(self, core=None):
                super().__init__(core)
                self.started = False

            async def on_start(self):
                self.started = True

            @on("say.hello")
            async def _on_hello(self, event: Event):
                seen.append(event.data.get("who"))

        g = Greeter()
        run(host.register_plugin(g))

        self.assertTrue(g.started)
        self.assertTrue(host.has_capability("greeting"))
        self.assertIs(run(host.get_capability("greeting")), g)

        # Orion-style positional-dict emit reaches the @on handler with an Event.
        run(host.emit("say.hello", {"who": "sol"}))
        self.assertEqual(seen, ["sol"])

        # Hot-unload removes the capability and its subscription.
        self.assertTrue(run(host.unload_capability("greeting")))
        self.assertFalse(host.has_capability("greeting"))
        run(host.emit("say.hello", {"who": "lux"}))
        self.assertEqual(seen, ["sol"])  # no new delivery after unload


class TestSelfExtensionLoop(unittest.TestCase):
    """plugin_generator → ForgeHost hot-load, the actual self-improvement step."""

    def test_implement_missing_primitive_hot_loads(self):
        from core.category import Category
        from core.plugin_generator import SelfExtensionEngine

        cat = Category(db_path=":memory:")
        host = build_host()
        engine = SelfExtensionEngine(orion_core=host, category=cat)

        result = run(engine.implement_missing_primitive(
            source="search",
            target="store",
            relation="requires",
            confidence=0.9,
            evidence={"source": "unit-test"},
            auto_load=True,
        ))

        # The generated plugin was loaded by our FORGE-backed host.
        self.assertTrue(result["loaded"], msg=result)
        self.assertTrue(host.has_capability("search_to_store"))

        # on_start established the missing morphism in the Category.
        edges = [(m.source, m.target) for m in cat.morphisms()]
        self.assertIn(("search", "store"), edges)


class TestSelfCorrectorOnHost(unittest.TestCase):
    def test_redundant_capability_emits_event_on_host(self):
        from core.self_corrector import SelfCorrector

        host = build_host()
        captured = []
        host.subscribe(
            "capability.redundant",
            lambda **d: captured.append(d),
            wants_event=False,
        )

        corrector = SelfCorrector(orion_core=host, category=None, approval_mode="auto")
        recs = [{
            "type": "redundant_capability",
            "description": "search and lookup may be redundant",
            "confidence": 0.9,
        }]
        out = run(corrector.act_on_recommendations(recs))

        self.assertEqual(out["actions_taken"], 1)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["cap_a"], "search")


if __name__ == "__main__":
    unittest.main()
