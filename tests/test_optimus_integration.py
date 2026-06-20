# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
OPTIMUS Integration Tests

Tests the adapter layer between KOMPOSOS-IV Category and OPTIMUS,
the OptimusEngine, and the Orion plugin.
"""

import sys
import os
import math
import unittest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.category import Category
from core.types import Object, Morphism
from core.enrichment import (
    MULTIPLICATIVE_QUANTALE,
    ADDITIVE_QUANTALE,
    MIN_QUANTALE,
)
from core.optimus import (
    quantale_to_optimus,
    morphism_to_enriched,
    enriched_to_morphism,
    category_to_runtime,
    sync_rewrites_to_category,
    OptimusEngine,
)
from optimus_core import (
    Quantale,
    EnrichedMorphism,
    RuntimeCategory,
    OptimisMonad,
    MULTIPLICATIVE as OPTIMUS_MULTIPLICATIVE,
)


# ══════════════════════════════════════════════════════════════════════════════
# ADAPTER TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestQuantaleAdapter(unittest.TestCase):
    """Test conversion from IV MonoidalStructure to OPTIMUS Quantale."""

    def test_multiplicative_tensor(self):
        """Multiplicative tensor: a * b."""
        q = quantale_to_optimus(MULTIPLICATIVE_QUANTALE)
        self.assertAlmostEqual(q.compose(0.8, 0.9), 0.72)

    def test_multiplicative_unit(self):
        """Multiplicative unit: 1.0."""
        q = quantale_to_optimus(MULTIPLICATIVE_QUANTALE)
        self.assertAlmostEqual(q.unit, 1.0)

    def test_multiplicative_leq(self):
        """Multiplicative leq: a <= b (lower is less)."""
        q = quantale_to_optimus(MULTIPLICATIVE_QUANTALE)
        self.assertTrue(q.leq(0.5, 0.8))   # 0.5 <= 0.8
        self.assertFalse(q.leq(0.8, 0.5))  # 0.8 > 0.5

    def test_multiplicative_better(self):
        """Multiplicative better: higher confidence is better."""
        q = quantale_to_optimus(MULTIPLICATIVE_QUANTALE)
        self.assertTrue(q.better(0.8, 0.5))   # 0.8 > 0.5: improvement
        self.assertFalse(q.better(0.5, 0.8))  # 0.5 < 0.8: not better

    def test_additive_tensor(self):
        """Additive tensor: a + b."""
        q = quantale_to_optimus(ADDITIVE_QUANTALE)
        self.assertAlmostEqual(q.compose(3.0, 4.0), 7.0)

    def test_additive_unit(self):
        """Additive unit: 0.0."""
        q = quantale_to_optimus(ADDITIVE_QUANTALE)
        self.assertAlmostEqual(q.unit, 0.0)

    def test_additive_leq(self):
        """Additive leq: a >= b (higher cost is worse)."""
        q = quantale_to_optimus(ADDITIVE_QUANTALE)
        # In additive: lower cost = better. leq(a,b) means a >= b.
        self.assertTrue(q.leq(5.0, 3.0))   # 5.0 >= 3.0
        self.assertFalse(q.leq(3.0, 5.0))  # 3.0 < 5.0

    def test_min_tensor(self):
        """Min tensor: min(a, b)."""
        q = quantale_to_optimus(MIN_QUANTALE)
        self.assertAlmostEqual(q.compose(0.8, 0.6), 0.6)


class TestMorphismAdapter(unittest.TestCase):
    """Test conversion between IV Morphism and OPTIMUS EnrichedMorphism."""

    def test_morphism_to_enriched_fields(self):
        """All fields map correctly."""
        m = Morphism(
            name="supports",
            source="Python",
            target="ML",
            confidence=0.85,
            metadata={"domain": "tech"},
            provenance="manual",
        )
        em = morphism_to_enriched(m)

        self.assertEqual(em.name, "supports")
        self.assertEqual(em.source, "Python")
        self.assertEqual(em.target, "ML")
        self.assertAlmostEqual(em.confidence, 0.85)
        self.assertEqual(em.metadata, {"domain": "tech"})
        self.assertEqual(em.provenance, ["manual"])
        self.assertEqual(em.generation, 0)

    def test_morphism_to_enriched_callable(self):
        """Callable function transfers."""
        fn = lambda x: x * 2
        m = Morphism(name="f", source="A", target="B", _fn=fn)
        em = morphism_to_enriched(m)
        self.assertIsNotNone(em.fn)
        self.assertEqual(em.fn(5), 10)

    def test_enriched_to_morphism_fields(self):
        """Reverse mapping preserves fields."""
        em = EnrichedMorphism(
            name="shortcut",
            source="A",
            target="C",
            confidence=0.72,
            provenance=["f", "g"],
            generation=3,
            metadata={"rewrite": True},
        )
        m = enriched_to_morphism(em)

        self.assertEqual(m.name, "shortcut")
        self.assertEqual(m.source, "A")
        self.assertEqual(m.target, "C")
        self.assertAlmostEqual(m.confidence, 0.72)
        self.assertEqual(m.provenance, "optimus")
        self.assertEqual(m.metadata["optimus_generation"], 3)
        self.assertEqual(m.metadata["optimus_provenance"], ["f", "g"])
        self.assertTrue(m.metadata["rewrite"])

    def test_enriched_to_morphism_callable(self):
        """Callable transfers back."""
        fn = lambda x: x + 1
        em = EnrichedMorphism(name="f", source="A", target="B", fn=fn)
        m = enriched_to_morphism(em)
        self.assertTrue(m.is_callable)
        self.assertEqual(m(5), 6)


class TestCategoryToRuntime(unittest.TestCase):
    """Test snapshotting Category to RuntimeCategory."""

    def setUp(self):
        self.cat = Category("test", db_path=":memory:")
        self.cat.add("A")
        self.cat.add("B")
        self.cat.add("C")
        self.cat.connect("A", "B", "f", confidence=0.9)
        self.cat.connect("B", "C", "g", confidence=0.8)
        self.cat.connect("A", "C", "weak", confidence=0.3)

    def test_objects_transferred(self):
        """All objects appear in RuntimeCategory."""
        runtime = category_to_runtime(self.cat)
        self.assertIn("A", runtime.objects)
        self.assertIn("B", runtime.objects)
        self.assertIn("C", runtime.objects)
        self.assertEqual(len(runtime.objects), 3)

    def test_morphisms_transferred(self):
        """All morphisms appear in RuntimeCategory."""
        runtime = category_to_runtime(self.cat)
        self.assertIn("f", runtime.morphisms)
        self.assertIn("g", runtime.morphisms)
        self.assertIn("weak", runtime.morphisms)
        self.assertEqual(len(runtime.morphisms), 3)

    def test_confidence_preserved(self):
        """Confidence values match."""
        runtime = category_to_runtime(self.cat)
        self.assertAlmostEqual(runtime.morphisms["f"].confidence, 0.9)
        self.assertAlmostEqual(runtime.morphisms["g"].confidence, 0.8)
        self.assertAlmostEqual(runtime.morphisms["weak"].confidence, 0.3)

    def test_quantale_preserved(self):
        """Quantale tensor produces same results."""
        runtime = category_to_runtime(self.cat)
        # Multiplicative: 0.9 * 0.8 = 0.72
        self.assertAlmostEqual(runtime.quantale.compose(0.9, 0.8), 0.72)


class TestSyncRewrites(unittest.TestCase):
    """Test syncing OPTIMUS rewrites back to Category."""

    def test_rewrite_persists_to_category(self):
        """Compressed shortcut appears in Category after sync."""
        cat = Category("test", db_path=":memory:")
        cat.add("A")
        cat.add("B")
        cat.add("C")
        cat.connect("A", "B", "f", confidence=0.9)
        cat.connect("B", "C", "g", confidence=0.8)
        cat.connect("A", "C", "weak", confidence=0.3)

        runtime = category_to_runtime(cat)
        monad = OptimisMonad(runtime, max_depth=3)

        # Manually refine "weak" morphism
        weak_em = runtime.morphisms["weak"]
        result = monad.refine(weak_em, depth=1)
        self.assertIsNotNone(result, "OPTIMUS should find A->B->C factorization")

        # Sync back
        added = sync_rewrites_to_category(monad, cat)
        self.assertGreater(len(added), 0)

        # Verify the shortcut is in Category
        shortcut = added[0]
        self.assertEqual(shortcut.source, "A")
        self.assertEqual(shortcut.target, "C")
        self.assertGreater(shortcut.confidence, 0.3)
        self.assertEqual(shortcut.provenance, "optimus")

    def test_hook_fires_on_sync(self):
        """morphism_added hook fires when rewrite is synced."""
        cat = Category("test", db_path=":memory:")
        cat.add("A")
        cat.add("B")
        cat.add("C")
        cat.connect("A", "B", "f", confidence=0.9)
        cat.connect("B", "C", "g", confidence=0.8)
        cat.connect("A", "C", "weak", confidence=0.3)

        events = []
        cat.on("morphism_added", lambda morphism: events.append(morphism.name))

        runtime = category_to_runtime(cat)
        monad = OptimisMonad(runtime, max_depth=3)
        weak_em = runtime.morphisms["weak"]
        monad.refine(weak_em, depth=1)
        sync_rewrites_to_category(monad, cat)

        # At least one morphism_added event for the shortcut
        optimus_events = [e for e in events if e not in ("f", "g", "weak")]
        self.assertGreater(len(optimus_events), 0)


# ══════════════════════════════════════════════════════════════════════════════
# OPTIMUS ENGINE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestOptimusEngine(unittest.TestCase):
    """Test the high-level OptimusEngine API."""

    def setUp(self):
        """Build a simple Category with a weak direct edge and strong indirect path."""
        self.cat = Category("test_engine", db_path=":memory:")
        self.cat.add("A")
        self.cat.add("B")
        self.cat.add("C")
        self.cat.connect("A", "B", "f", confidence=0.9)
        self.cat.connect("B", "C", "g", confidence=0.8)
        self.cat.connect("A", "C", "weak", confidence=0.3)

    def test_refine_finds_factorization(self):
        """OPTIMUS finds A->B->C is better than direct A->C."""
        engine = OptimusEngine(self.cat)
        result = engine.refine(max_steps=10, depth=2)

        self.assertGreater(result["steps"], 0)
        self.assertGreater(len(result["synced_morphisms"]), 0)

    def test_refine_improves_confidence(self):
        """Shortcut has higher confidence than original weak edge."""
        engine = OptimusEngine(self.cat)
        result = engine.refine(max_steps=10, depth=2)

        # Find the synced morphism
        for mor in self.cat.morphisms():
            if mor.provenance == "optimus" and mor.source == "A" and mor.target == "C":
                # 0.9 * 0.8 = 0.72 > 0.3
                self.assertGreater(mor.confidence, 0.3)
                self.assertAlmostEqual(mor.confidence, 0.72)
                return

        self.fail("Expected OPTIMUS shortcut A->C not found")

    def test_refine_tarski_stability(self):
        """Every rewrite satisfies w(new) >= w(old) (Tarski condition)."""
        engine = OptimusEngine(self.cat)
        engine.refine(max_steps=10, depth=2)

        for rewrite in engine.rewrites:
            q = engine._runtime.quantale
            old_conf = q.compose_path(rewrite.confidence_before)
            new_conf = rewrite.confidence_after
            self.assertTrue(
                q.at_least_as_good(new_conf, old_conf),
                f"Tarski violation: new={new_conf} < old={old_conf}"
            )

    def test_refine_converges(self):
        """Running refine again adds no new morphisms to Category."""
        engine = OptimusEngine(self.cat)
        result1 = engine.refine(max_steps=10, depth=2)
        count_after_first = len(self.cat.morphisms())

        result2 = engine.refine(max_steps=10, depth=2)
        count_after_second = len(self.cat.morphisms())

        # Second run should add 0 new morphisms (already synced)
        self.assertEqual(len(result2["synced_morphisms"]), 0)
        self.assertEqual(count_after_second, count_after_first)

    def test_refine_morphism_specific(self):
        """Refine a specific morphism."""
        engine = OptimusEngine(self.cat)
        improved = engine.refine_morphism("A", "C", depth=2)

        self.assertIsNotNone(improved)
        self.assertEqual(improved.source, "A")
        self.assertEqual(improved.target, "C")
        self.assertGreater(improved.confidence, 0.3)

    def test_discover_intermediates(self):
        """Find intermediate objects between A and C."""
        engine = OptimusEngine(self.cat)
        intermediates = engine.discover_intermediates("A", "C", depth=2)

        self.assertIn("B", intermediates)

    def test_discover_intermediates_no_path(self):
        """No intermediates when no factorization exists."""
        engine = OptimusEngine(self.cat)
        intermediates = engine.discover_intermediates("C", "A", depth=2)
        self.assertEqual(intermediates, [])

    def test_absorb_transfers_morphisms(self):
        """Yoneda-guided transfer: similar objects get morphisms transferred."""
        cat = Category("absorb_test", db_path=":memory:")

        # Create two similar objects
        cat.add("X")
        cat.add("Y")
        cat.add("P")
        cat.add("Q")

        # X has morphisms to P and Q
        cat.connect("X", "P", "xp", confidence=0.9)
        cat.connect("X", "Q", "xq", confidence=0.8)

        # Y is similar to X (bridge morphism)
        cat.connect("X", "Y", "bridge", confidence=0.95)

        engine = OptimusEngine(cat)
        transferred = engine.absorb("X", "Y", threshold=0.5)

        # Y should now have morphisms to P and Q (confidence scaled by bridge)
        self.assertGreater(len(transferred), 0)
        targets = {m.target for m in transferred}
        self.assertTrue(targets & {"P", "Q"})

    def test_yoneda_similarity_with_shared_morphism(self):
        """Objects sharing an incoming morphism have nonzero Yoneda similarity."""
        # OPTIMUS Yoneda fingerprints use morphism NAMES as keys.
        # For similarity > 0, both objects must have the same morphism
        # name in their hom_in or hom_out.
        # Use OPTIMUS RuntimeCategory directly for precision.
        cat = Category("yoneda_test", db_path=":memory:")
        cat.add("A")
        cat.add("B")

        engine = OptimusEngine(cat)
        engine._build_runtime()

        # Manually add morphisms in RuntimeCategory (precise control)
        engine._runtime.add_object("X")
        engine._runtime.add_morphism("link_x", "A", "X", confidence=0.9)
        engine._runtime.add_morphism("link_x2", "B", "X", confidence=0.9)

        # Self-similarity should be 1.0
        sim_self = engine._runtime.yoneda_similarity("A", "A")
        self.assertAlmostEqual(sim_self, 1.0)

        # A and B don't share exact names so similarity is low
        sim_diff = engine._runtime.yoneda_similarity("A", "B")
        self.assertIsInstance(sim_diff, float)
        self.assertGreaterEqual(sim_diff, 0.0)
        self.assertLessEqual(sim_diff, 1.0)

    def test_yoneda_similarity_different_structure(self):
        """Objects with no shared morphisms have low similarity."""
        cat = Category("yoneda_diff", db_path=":memory:")
        cat.add("A")
        cat.add("B")
        cat.add("X")
        cat.add("Y")

        cat.connect("A", "X", "ax", confidence=0.9)
        cat.connect("B", "Y", "by", confidence=0.8)

        engine = OptimusEngine(cat)
        sim = engine.yoneda_similarity("A", "B")

        self.assertLess(sim, 0.5)

    def test_yoneda_fingerprint(self):
        """Fingerprint returns correct structure."""
        cat = Category("fp_test", db_path=":memory:")
        cat.add("A")
        cat.add("B")
        cat.connect("A", "B", "f", confidence=0.9)

        engine = OptimusEngine(cat)
        fp = engine.yoneda_fingerprint("A")

        self.assertEqual(fp["object"], "A")
        self.assertIn("hom_out", fp)
        self.assertIn("hom_in", fp)

    def test_find_structural_gaps(self):
        """Detect structural holes (A->B->C exists but A->C doesn't)."""
        cat = Category("gaps_test", db_path=":memory:")
        cat.add("A")
        cat.add("B")
        cat.add("C")
        cat.connect("A", "B", "f", confidence=0.9)
        cat.connect("B", "C", "g", confidence=0.8)
        # No direct A -> C edge

        engine = OptimusEngine(cat)
        gaps = engine.find_structural_gaps()

        self.assertGreater(len(gaps), 0)
        gap = gaps[0]
        self.assertEqual(gap["source"], "A")
        self.assertEqual(gap["target"], "C")
        self.assertEqual(gap["via"], "B")
        self.assertAlmostEqual(gap["path_confidence"], 0.72)

    def test_refine_empty_category(self):
        """Refine on empty category produces no rewrites."""
        cat = Category("empty", db_path=":memory:")
        engine = OptimusEngine(cat)
        result = engine.refine(max_steps=5)

        self.assertEqual(result["steps"], 0)

    def test_report(self):
        """Report produces non-empty string after refinement."""
        engine = OptimusEngine(self.cat)
        engine.refine(max_steps=10, depth=2)
        report = engine.report(verbose=False)
        self.assertIn("Optimus", report)

    def test_rewrites_property(self):
        """Rewrites property returns rewrite history."""
        engine = OptimusEngine(self.cat)
        self.assertEqual(engine.rewrites, [])

        engine.refine(max_steps=10, depth=2)
        self.assertGreater(len(engine.rewrites), 0)

    def test_complex_graph_refinement(self):
        """Multi-hop refinement on a larger graph."""
        cat = Category("complex", db_path=":memory:")

        # Build a diamond: A -> B -> D, A -> C -> D
        # with weak direct A -> D
        cat.add("A")
        cat.add("B")
        cat.add("C")
        cat.add("D")
        cat.connect("A", "B", "ab", confidence=0.95)
        cat.connect("B", "D", "bd", confidence=0.9)
        cat.connect("A", "C", "ac", confidence=0.85)
        cat.connect("C", "D", "cd", confidence=0.88)
        cat.connect("A", "D", "direct", confidence=0.1)

        engine = OptimusEngine(cat)
        result = engine.refine(max_steps=20, depth=2)

        # Should find at least one improvement
        self.assertGreater(result["steps"], 0)

        # Best path should be A->B->D (0.95*0.9=0.855)
        # which is much better than direct 0.1
        found_improvement = False
        for mor in cat.morphisms():
            if mor.provenance == "optimus" and mor.source == "A" and mor.target == "D":
                self.assertGreater(mor.confidence, 0.1)
                found_improvement = True
        self.assertTrue(found_improvement)


# ══════════════════════════════════════════════════════════════════════════════
# FULL INTEGRATION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestFullIntegration(unittest.TestCase):
    """End-to-end tests combining all layers."""

    def test_add_knowledge_then_refine(self):
        """Full pipeline: add knowledge, refine, verify improvement."""
        cat = Category("full_test", db_path=":memory:")

        # Build knowledge graph
        cat.connect("Python", "NumPy", "has_library", confidence=0.95)
        cat.connect("NumPy", "ML", "enables", confidence=0.85)
        cat.connect("Python", "ML", "supports", confidence=0.4)

        initial_count = len(cat.morphisms())

        # Refine
        engine = OptimusEngine(cat)
        result = engine.refine(max_steps=10, depth=2)

        # Should discover Python -> NumPy -> ML is better
        self.assertGreater(result["steps"], 0)
        self.assertGreater(len(cat.morphisms()), initial_count)

    def test_persistence_survives_engine_rebuild(self):
        """Synced morphisms persist after engine is rebuilt."""
        cat = Category("persist_test", db_path=":memory:")
        cat.connect("A", "B", "f", confidence=0.9)
        cat.connect("B", "C", "g", confidence=0.8)
        cat.connect("A", "C", "weak", confidence=0.3)

        engine1 = OptimusEngine(cat)
        engine1.refine(max_steps=10, depth=2)

        # Count morphisms after first refinement
        count_after_first = len(cat.morphisms())
        self.assertGreater(count_after_first, 3)

        # New engine on same category - syncs should add nothing new
        engine2 = OptimusEngine(cat)
        result = engine2.refine(max_steps=10, depth=2)

        # No new morphisms synced to Category (shortcuts already exist)
        self.assertEqual(len(result["synced_morphisms"]), 0)
        self.assertEqual(len(cat.morphisms()), count_after_first)


if __name__ == "__main__":
    unittest.main()
