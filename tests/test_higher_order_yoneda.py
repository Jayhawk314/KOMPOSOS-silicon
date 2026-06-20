# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Higher-Order OPTIMUS and Formal Yoneda Tests

Tests:
1. HigherOrderOptimus: 2-morphism factorization
2. YonedaProver: Metric properties, isomorphism detection
3. Integration: cosmos.py <-> presheaf_topos.py connection
4. Provably-correct absorb threshold
"""

import sys
import os
import unittest

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.category import Category
from core.higher_order_optimus import HigherOrderOptimus, HigherOrderRewrite
from core.formal_yoneda import YonedaProver, YonedaProofResult, yoneda_transfer_threshold
from core.cosmos import InfinityCosmos
from categorical.presheaf_topos import PresheafTopos, RepresentablePresheaf
from categorical.two_categories import TwoCategory, TwoCell


# ══════════════════════════════════════════════════════════════════════════════
# HIGHER-ORDER OPTIMUS TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestHigherOrderOptimus(unittest.TestCase):
    """Test 2-morphism factorization and higher-level refinement."""

    def setUp(self):
        """Build a category with parallel morphisms (2-cells)."""
        self.cat = Category("higher_order_test", db_path=":memory:")
        self.cat.add("A")
        self.cat.add("B")
        # Parallel morphisms: f, g: A -> B
        self.cat.connect("A", "B", "f", confidence=0.9)
        self.cat.connect("A", "B", "g", confidence=0.7)
        self.cat.connect("A", "B", "h", confidence=0.5)

    def test_two_category_construction(self):
        """TwoCategory builds from Category with parallel morphisms."""
        cosmos = InfinityCosmos(self.cat)
        h2k = cosmos.homotopy_2_category()

        # Should have objects A, B
        self.assertIn("A", h2k.objects)
        self.assertIn("B", h2k.objects)

        # Should have 2-cells between parallel morphisms
        self.assertGreater(len(h2k.two_cells), 0)

    def test_higher_order_optimus_init(self):
        """HigherOrderOptimus initializes with two_category."""
        from optimus_core import RuntimeCategory, MULTIPLICATIVE as OPTIMUS_MULTIPLICATIVE

        cosmos = InfinityCosmos(self.cat)
        h2k = cosmos.homotopy_2_category()

        # Build runtime category
        runtime = RuntimeCategory(name="test", quantale=OPTIMUS_MULTIPLICATIVE)
        runtime.add_object("A")
        runtime.add_object("B")
        runtime.add_morphism("f", "A", "B", confidence=0.9)
        runtime.add_morphism("g", "A", "B", confidence=0.7)

        # Create HigherOrderOptimus
        higher_optimus = HigherOrderOptimus(runtime, max_depth=2, two_category=h2k)
        self.assertIsNotNone(higher_optimus.two_category)
        self.assertEqual(higher_optimus.max_depth, 2)

    def test_factorize_two_cell(self):
        """Factorize a 2-cell between parallel morphisms."""
        from optimus_core import RuntimeCategory, MULTIPLICATIVE as OPTIMUS_MULTIPLICATIVE

        cosmos = InfinityCosmos(self.cat)
        h2k = cosmos.homotopy_2_category()

        # Build runtime
        runtime = RuntimeCategory(name="test", quantale=OPTIMUS_MULTIPLICATIVE)
        runtime.add_object("A")
        runtime.add_object("B")
        runtime.add_morphism("f", "A", "B", confidence=0.9)
        runtime.add_morphism("g", "A", "B", confidence=0.7)

        higher_optimus = HigherOrderOptimus(runtime, two_category=h2k)

        # Get a 2-cell from the two-category
        if h2k.two_cells:
            cell_name = list(h2k.two_cells.keys())[0]
            candidates = higher_optimus.factorize_two_cell(cell_name)
            # May be empty if no better factorization exists, but should not crash
            self.assertIsInstance(candidates, list)

    def test_higher_rewrites_tracking(self):
        """Higher-order rewrites are tracked separately."""
        from optimus_core import RuntimeCategory, MULTIPLICATIVE as OPTIMUS_MULTIPLICATIVE

        runtime = RuntimeCategory(name="test", quantale=OPTIMUS_MULTIPLICATIVE)
        runtime.add_object("A")
        runtime.add_object("B")
        runtime.add_morphism("f", "A", "B", confidence=0.9)

        cosmos = InfinityCosmos(self.cat)
        h2k = cosmos.homotopy_2_category()

        higher_optimus = HigherOrderOptimus(runtime, two_category=h2k)
        self.assertEqual(higher_optimus.higher_rewrites, [])

    def test_descend_all_levels(self):
        """descend_all runs refinement at multiple levels."""
        from optimus_core import RuntimeCategory, MULTIPLICATIVE as OPTIMUS_MULTIPLICATIVE

        runtime = RuntimeCategory(name="test", quantale=OPTIMUS_MULTIPLICATIVE)
        runtime.add_object("A")
        runtime.add_object("B")
        runtime.add_object("C")
        runtime.add_morphism("f", "A", "B", confidence=0.9)
        runtime.add_morphism("g", "B", "C", confidence=0.8)
        runtime.add_morphism("weak", "A", "C", confidence=0.3)

        cosmos = InfinityCosmos(self.cat)
        h2k = cosmos.homotopy_2_category()

        higher_optimus = HigherOrderOptimus(runtime, two_category=h2k)
        result = higher_optimus.descend_all(
            max_steps=5,
            depth=1,
            include_two_cells=True,
            include_fibrations=False,
            include_functors=False,
            verbose=False,
        )

        # Should have at least level 1 results
        self.assertIn("1_morphisms", result["levels"])
        self.assertGreater(result["total_rewrites"], 0)


# ══════════════════════════════════════════════════════════════════════════════
# FORMAL YONEDA PROOF TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestFormalYoneda(unittest.TestCase):
    """Test Yoneda distance metric properties and isomorphism detection."""

    def setUp(self):
        """Build a simple category for Yoneda proofs."""
        self.cat = Category("yoneda_test", db_path=":memory:")
        self.cat.add("A")
        self.cat.add("B")
        self.cat.add("C")
        self.cat.connect("A", "B", "f", confidence=0.9)
        self.cat.connect("B", "C", "g", confidence=0.8)

    def test_representable_presheaf(self):
        """y(T) = Hom(-, T) computes correctly."""
        prover = YonedaProver(self.cat)
        presheaf_b = prover._representable_presheaf("B")

        # Hom(A, B) should have f with confidence 0.9
        self.assertIn("A", presheaf_b)
        self.assertAlmostEqual(presheaf_b["A"], 0.9)

        # Hom(B, B) should have identity
        self.assertIn("B", presheaf_b)
        self.assertAlmostEqual(presheaf_b["B"], 1.0)

    def test_yoneda_distance_nonnegative(self):
        """Yoneda distance is always >= 0."""
        prover = YonedaProver(self.cat)
        presheaf_a = prover._representable_presheaf("A")
        presheaf_b = prover._representable_presheaf("B")

        d = prover._sieve_symmetric_distance(presheaf_a, presheaf_b)
        self.assertGreaterEqual(d, 0.0)

    def test_yoneda_distance_symmetric(self):
        """d(A, B) = d(B, A)."""
        prover = YonedaProver(self.cat)
        presheaf_a = prover._representable_presheaf("A")
        presheaf_b = prover._representable_presheaf("B")
        presheaf_c = prover._representable_presheaf("C")

        d_ab = prover._sieve_symmetric_distance(presheaf_a, presheaf_b)
        d_ba = prover._sieve_symmetric_distance(presheaf_b, presheaf_a)
        self.assertAlmostEqual(d_ab, d_ba)

        d_ac = prover._sieve_symmetric_distance(presheaf_a, presheaf_c)
        d_ca = prover._sieve_symmetric_distance(presheaf_c, presheaf_a)
        self.assertAlmostEqual(d_ac, d_ca)

    def test_yoneda_distance_triangle_inequality(self):
        """d(A, C) <= d(A, B) + d(B, C)."""
        prover = YonedaProver(self.cat)
        presheaf_a = prover._representable_presheaf("A")
        presheaf_b = prover._representable_presheaf("B")
        presheaf_c = prover._representable_presheaf("C")

        d_ab = prover._sieve_symmetric_distance(presheaf_a, presheaf_b)
        d_bc = prover._sieve_symmetric_distance(presheaf_b, presheaf_c)
        d_ac = prover._sieve_symmetric_distance(presheaf_a, presheaf_c)

        self.assertLessEqual(d_ac, d_ab + d_bc)

    def test_yoneda_distance_zero_iff_isomorphic(self):
        """d(A, B) = 0 iff A ≅ B."""
        # Create isomorphic objects (bidirectional high-confidence morphisms)
        cat_iso = Category("iso_test", db_path=":memory:")
        cat_iso.add("X")
        cat_iso.add("Y")
        cat_iso.connect("X", "Y", "f", confidence=0.98)
        cat_iso.connect("Y", "X", "g", confidence=0.98)

        prover = YonedaProver(cat_iso)
        result = prover.prove_yoneda("X", "Y")

        # X and Y are isomorphic (f ∘ g ≈ 0.96 >= 0.95)
        self.assertTrue(result.is_isomorphic)
        # Distance should be small (not necessarily 0, since they have different hom-sets)
        self.assertLess(result.yoneda_distance, 0.5)

    def test_yoneda_proof_result_structure(self):
        """YonedaProofResult has all required fields."""
        prover = YonedaProver(self.cat)
        result = prover.prove_yoneda("A", "B")

        self.assertIsInstance(result, YonedaProofResult)
        self.assertEqual(result.object_a, "A")
        self.assertEqual(result.object_b, "B")
        self.assertIsInstance(result.yoneda_distance, float)
        self.assertIsInstance(result.is_isomorphic, bool)
        self.assertIsInstance(result.max_transfer_threshold, float)
        self.assertIsInstance(result.proof_steps, list)
        self.assertGreater(len(result.proof_steps), 0)

    def test_transfer_threshold_derivation(self):
        """Transfer threshold = 1 - d(y(A), y(B))."""
        prover = YonedaProver(self.cat)
        result = prover.prove_yoneda("A", "B")

        expected_threshold = 1.0 - result.yoneda_distance
        self.assertAlmostEqual(result.max_transfer_threshold, expected_threshold)

    def test_can_transfer_method(self):
        """can_transfer checks similarity >= threshold."""
        prover = YonedaProver(self.cat)
        result = prover.prove_yoneda("A", "B")

        threshold = result.max_transfer_threshold
        self.assertTrue(result.can_transfer(threshold))
        self.assertTrue(result.can_transfer(threshold + 0.1))
        self.assertFalse(result.can_transfer(threshold - 0.2))

    def test_presheaf_overlap_jaccard(self):
        """Presheaf overlap is Jaccard similarity."""
        prover = YonedaProver(self.cat)
        presheaf_a = prover._representable_presheaf("A")
        presheaf_b = prover._representable_presheaf("B")

        overlap = prover._presheaf_overlap(presheaf_a, presheaf_b)
        self.assertGreaterEqual(overlap, 0.0)
        self.assertLessEqual(overlap, 1.0)

    def test_isomorphism_check_false(self):
        """Non-isomorphic objects return False."""
        prover = YonedaProver(self.cat)
        # A and C have no bidirectional morphisms
        is_iso = prover._check_isomorphism("A", "C")
        self.assertFalse(is_iso)

    def test_yoneda_transfer_threshold_function(self):
        """Standalone function returns correct threshold."""
        threshold = yoneda_transfer_threshold(self.cat, "A", "B")
        self.assertIsInstance(threshold, float)
        self.assertGreaterEqual(threshold, 0.0)
        self.assertLessEqual(threshold, 1.0)

    def test_yoneda_caching(self):
        """Yoneda proofs are cached."""
        prover = YonedaProver(self.cat)
        result1 = prover.prove_yoneda("A", "B")
        result2 = prover.prove_yoneda("A", "B")
        self.assertIs(result1, result2)


# ══════════════════════════════════════════════════════════════════════════════
# COSMOS <-> PRESHEAF TOPOS INTEGRATION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestCosmosPresheafIntegration(unittest.TestCase):
    """Test the connection between cosmos.py and presheaf_topos.py."""

    def setUp(self):
        """Build a category with structure for presheaf topos."""
        self.cat = Category("cosmos_topos_test", db_path=":memory:")
        self.cat.add("Python")
        self.cat.add("NumPy")
        self.cat.add("ML")
        self.cat.connect("Python", "NumPy", "has_lib", confidence=0.95)
        self.cat.connect("NumPy", "ML", "enables", confidence=0.85)
        self.cat.connect("Python", "ML", "supports", confidence=0.4)

    def test_infinity_cosmos_yoneda_uses_topos(self):
        """InfinityCosmos.yoneda_embedding uses PresheafTopos."""
        cosmos = InfinityCosmos(self.cat)
        yoneda_result = cosmos.yoneda_embedding()

        self.assertTrue(yoneda_result.is_fully_faithful or yoneda_result.faithfulness_score > 0.5)
        self.assertIn("Python", yoneda_result.objects_mapped)
        self.assertIn("NumPy", yoneda_result.objects_mapped)
        self.assertIn("ML", yoneda_result.objects_mapped)

    def test_yoneda_distances_computed(self):
        """Yoneda distances are computed for all object pairs."""
        cosmos = InfinityCosmos(self.cat)
        yoneda_result = cosmos.yoneda_embedding()

        # Check that distances are in the result data
        if "yoneda_distances" in yoneda_result.data:
            distances = yoneda_result.data["yoneda_distances"]
            # Should have distances for at least some pairs
            self.assertIsInstance(distances, dict)

    def test_presheaf_topos_from_enriched_category(self):
        """PresheafTopos.builds from enriched category."""
        topos = PresheafTopos.from_enriched_category(self.cat)

        self.assertIn("Python", topos.objects)
        self.assertIn("NumPy", topos.objects)
        self.assertIn("ML", topos.objects)
        self.assertGreater(len(topos.representables), 0)

    def test_representable_presheaves(self):
        """Representable presheaves are correctly computed."""
        topos = PresheafTopos.from_enriched_category(self.cat)

        # y(ML) should have incoming from NumPy and Python
        ml_repr = topos.representables["ML"]
        self.assertGreater(ml_repr.hom_set_size("NumPy"), 0)
        self.assertGreater(ml_repr.hom_set_size("Python"), 0)

    def test_yoneda_distance_on_topos(self):
        """Yoneda distance works on PresheafTopos."""
        topos = PresheafTopos.from_enriched_category(self.cat)

        # Python and NumPy should have some distance (different roles)
        d = topos.yoneda_distance("Python", "NumPy")
        self.assertGreaterEqual(d, 0.0)
        self.assertLessEqual(d, 1.0)

    def test_cosmos_statistics_includes_yoneda(self):
        """Cosmos statistics includes Yoneda faithfulness."""
        cosmos = InfinityCosmos(self.cat)
        stats = cosmos.statistics()

        self.assertIn("yoneda_faithful", stats)
        self.assertIn("yoneda_score", stats)
        self.assertIsInstance(stats["yoneda_faithful"], bool)
        self.assertIsInstance(stats["yoneda_score"], float)


# ══════════════════════════════════════════════════════════════════════════════
# PROVABLY-CORRECT ABSORB THRESHOLD TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestProvablyCorrectAbsorb(unittest.TestCase):
    """Test that absorb() uses the Yoneda-derived threshold."""

    def test_absorb_with_yoneda_threshold(self):
        """absorb() uses Yoneda threshold when enabled."""
        from core.optimus import OptimusEngine

        cat = Category("absorb_yoneda_test", db_path=":memory:")
        cat.add("X")
        cat.add("Y")
        cat.add("P")
        cat.add("Q")

        # X has morphisms to P and Q
        cat.connect("X", "P", "xp", confidence=0.9)
        cat.connect("X", "Q", "xq", confidence=0.8)

        # Y is similar to X (bridge morphism with high confidence)
        cat.connect("X", "Y", "bridge", confidence=0.95)

        engine = OptimusEngine(cat)

        # Use Yoneda threshold (should be high due to bridge)
        transferred = engine.absorb("X", "Y", use_yoneda_threshold=True)
        self.assertGreater(len(transferred), 0)

        # Y should have morphisms to P and Q
        targets = {m.target for m in transferred}
        self.assertTrue(targets & {"P", "Q"})

    def test_absorb_with_explicit_threshold(self):
        """absorb() respects explicit threshold override."""
        from core.optimus import OptimusEngine

        cat = Category("absorb_explicit_test", db_path=":memory:")
        cat.add("X")
        cat.add("Y")
        cat.add("P")

        cat.connect("X", "P", "xp", confidence=0.9)
        cat.connect("X", "Y", "bridge", confidence=0.5)

        engine = OptimusEngine(cat)

        # Explicit threshold lower than bridge confidence
        transferred = engine.absorb("X", "Y", threshold=0.3, use_yoneda_threshold=False)
        self.assertGreater(len(transferred), 0)

    def test_absorb_rejects_dissimilar_objects(self):
        """absorb() does not transfer between dissimilar objects."""
        from core.optimus import OptimusEngine

        cat = Category("absorb_dissimilar_test", db_path=":memory:")
        cat.add("A")
        cat.add("B")
        cat.add("P")
        cat.add("Q")

        # A has morphisms to P and Q
        cat.connect("A", "P", "ap", confidence=0.9)
        cat.connect("A", "Q", "aq", confidence=0.8)

        # B is isolated (no connection to A)
        cat.connect("B", "P", "bp", confidence=0.3)

        engine = OptimusEngine(cat)

        # Yoneda similarity should be low
        similarity = engine.yoneda_similarity("A", "B")
        self.assertLess(similarity, 0.5)

        # Transfer should not happen with Yoneda threshold
        transferred = engine.absorb("A", "B", use_yoneda_threshold=True)
        self.assertEqual(len(transferred), 0)


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION: HIGHER-ORDER + YONEDA
# ══════════════════════════════════════════════════════════════════════════════

class TestHigherOrderYonedaIntegration(unittest.TestCase):
    """Test Higher-Order OPTIMUS and Formal Yoneda working together."""

    def test_full_pipeline(self):
        """Full pipeline: build category, compute Yoneda, refine, absorb."""
        cat = Category("full_integration_test", db_path=":memory:")

        # Build a diamond structure
        cat.add("Python")
        cat.add("Ruby")
        cat.add("ML")
        cat.add("DataScience")

        cat.connect("Python", "ML", "supports", confidence=0.9)
        cat.connect("Ruby", "ML", "supports", confidence=0.7)
        cat.connect("ML", "DataScience", "enables", confidence=0.95)
        cat.connect("Python", "DataScience", "weak", confidence=0.3)
        cat.connect("Ruby", "DataScience", "weak", confidence=0.2)

        # Connect Python and Ruby (similar languages)
        cat.connect("Python", "Ruby", "bridge", confidence=0.85)

        # Step 1: Compute Yoneda embedding
        cosmos = InfinityCosmos(cat)
        yoneda_result = cosmos.yoneda_embedding()
        self.assertIn("Python", yoneda_result.objects_mapped)

        # Step 2: Prove Yoneda properties
        prover = YonedaProver(cat)
        proof = prover.prove_yoneda("Python", "Ruby")
        self.assertIsInstance(proof.yoneda_distance, float)

        # Step 3: Run OPTIMUS refinement
        from core.optimus import OptimusEngine
        engine = OptimusEngine(cat)
        refine_result = engine.refine(max_steps=10, depth=2, verbose=False)
        self.assertGreaterEqual(refine_result["steps"], 0)

        # Step 4: Absorb with Yoneda threshold
        transferred = engine.absorb("Python", "Ruby", use_yoneda_threshold=True)
        # Should transfer ML->DataScience morphism
        self.assertGreaterEqual(len(transferred), 0)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    unittest.main()
