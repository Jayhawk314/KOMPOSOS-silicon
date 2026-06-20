# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-IV Commercial License (see LICENSE-COMMERCIAL file)

"""
Test KOMPOSOS-IV COG Integration

Verifies that the cognitive co-processor works correctly with the
KOMPOSOS-IV Category API.
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cog.session import CogSession
from cog.engine import CogEngine
from cog.schema import (
    CogConcept, CogRelation, CogClaim,
    ConceptType, RelationType, VerificationStatus,
)


class TestCogIVIntegration(unittest.TestCase):
    """Test COG with KOMPOSOS-IV Category API."""

    def setUp(self):
        """Create a fresh session and engine for each test."""
        self.session = CogSession(session_id="test", db_path=":memory:")
        self.engine = CogEngine(self.session)

    def test_session_uses_category(self):
        """Verify session uses Category instead of KomposOSStore."""
        self.assertIsNotNone(self.session.category)
        self.assertFalse(hasattr(self.session, 'store'))

    def test_engine_uses_category(self):
        """Verify engine uses Category."""
        self.assertIsNotNone(self.engine.category)
        self.assertFalse(hasattr(self.engine, 'store'))

    def test_add_concept(self):
        """Test adding a concept through the session."""
        concept = CogConcept(
            name="Python",
            concept_type=ConceptType.CONCEPT,
            description="A programming language",
        )
        result = self.session.add_concept(concept)
        self.assertTrue(result)

        # Verify it's in the category
        obj = self.session.category.get("Python")
        self.assertIsNotNone(obj)
        self.assertEqual(obj.name, "Python")
        self.assertEqual(obj.type_name, "concept")

    def test_add_relation(self):
        """Test adding a relation through the session."""
        # Add concepts first
        self.session.add_concept(CogConcept(name="Python"))
        self.session.add_concept(CogConcept(name="JavaScript"))

        # Add relation
        relation = CogRelation(
            source="Python",
            target="JavaScript",
            relation_type=RelationType.SIMILAR_TO,
            confidence=0.7,
            evidence="Both are high-level languages",
        )
        result = self.session.add_relation(relation)
        self.assertTrue(result)

        # Verify morphism exists
        morphisms = self.session.category.morphisms_from("Python")
        matching = [m for m in morphisms if m.target == "JavaScript"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].name, "similar_to")
        self.assertEqual(matching[0].confidence, 0.7)

    def test_tier0_direct_lookup(self):
        """Test Tier 0: Direct edge lookup."""
        # Add concepts and relation
        self.session.add_concept(CogConcept(name="A"))
        self.session.add_concept(CogConcept(name="B"))
        self.session.add_relation(CogRelation(
            source="A", target="B",
            relation_type=RelationType.ENTAILS,
            confidence=0.9,
        ))

        # Check the claim
        claim = CogClaim(source="A", target="B", relation="entails", confidence=0.9)
        result = self.engine.check_claim(claim)

        self.assertEqual(result.status, VerificationStatus.AGREE)
        self.assertEqual(result.tier_reached, 0)
        self.assertGreater(result.confidence, 0.8)
        self.assertIn("Direct edge exists", result.explanation)

    def test_tier1_composition(self):
        """Test Tier 1: Compositional path finding."""
        # Create a path: A -> B -> C
        self.session.add_concept(CogConcept(name="A"))
        self.session.add_concept(CogConcept(name="B"))
        self.session.add_concept(CogConcept(name="C"))
        self.session.add_relation(CogRelation(
            source="A", target="B",
            relation_type=RelationType.ENTAILS,
            confidence=0.8,
        ))
        self.session.add_relation(CogRelation(
            source="B", target="C",
            relation_type=RelationType.ENTAILS,
            confidence=0.8,
        ))

        # Check claim A -> C (no direct edge, but compositional path exists)
        claim = CogClaim(source="A", target="C", relation="entails", confidence=0.7)
        result = self.engine.check_claim(claim)

        # Should escalate to Tier 1 and find the path
        self.assertGreaterEqual(result.tier_reached, 1)
        self.assertGreater(result.confidence, 0.0)
        self.assertGreater(len(result.supporting_paths), 0)

    def test_query_paths(self):
        """Test query() method with path finding."""
        # Create connected objects
        self.session.add_concept(CogConcept(name="X"))
        self.session.add_concept(CogConcept(name="Y"))
        self.session.add_relation(CogRelation(
            source="X", target="Y",
            relation_type=RelationType.CAUSES,
            confidence=0.8,
        ))

        # Query for paths
        result = self.engine.query(source="X", target="Y")

        self.assertTrue(result["connected"])
        self.assertGreater(len(result["paths"]), 0)

    def test_query_neighbors(self):
        """Test query() for neighborhood exploration."""
        # Create a small graph
        self.session.add_concept(CogConcept(name="Center"))
        self.session.add_concept(CogConcept(name="Out1"))
        self.session.add_concept(CogConcept(name="Out2"))
        self.session.add_relation(CogRelation(
            source="Center", target="Out1",
            relation_type=RelationType.PART_OF,
        ))
        self.session.add_relation(CogRelation(
            source="Center", target="Out2",
            relation_type=RelationType.PART_OF,
        ))

        # Query neighbors
        result = self.engine.query(source="Center")

        self.assertTrue(result["exists"])
        self.assertEqual(len(result["outgoing"]), 2)

    def test_coherence_check(self):
        """Test coherence checking across concepts."""
        # Create a coherent set
        self.session.add_concept(CogConcept(name="A"))
        self.session.add_concept(CogConcept(name="B"))
        self.session.add_relation(CogRelation(
            source="A", target="B",
            relation_type=RelationType.SUPPORTS,
            confidence=0.8,
        ))

        result = self.engine.check_coherence(["A", "B"])

        self.assertTrue(result.is_coherent)
        self.assertGreater(result.coherence_score, 0.9)

    def test_energy_computation(self):
        """Test energy computation for claims."""
        # Add a known relation (SUPPORTS)
        self.session.add_concept(CogConcept(name="A"))
        self.session.add_concept(CogConcept(name="B"))
        self.session.add_relation(CogRelation(
            source="A", target="B",
            relation_type=RelationType.SUPPORTS,
            confidence=0.9,
        ))

        # Low energy: claim matches existing knowledge
        claim_low = CogClaim(source="A", target="B", relation="supports", confidence=0.9)
        energy_low = self.engine.compute_energy(claim_low)
        self.assertLessEqual(energy_low.total_energy, 0.3)

        # High energy: contradictory claim (CONTRADICTS is antonym of SUPPORTS)
        claim_high = CogClaim(source="A", target="B", relation="contradicts", confidence=0.9)
        energy_high = self.engine.compute_energy(claim_high)
        # Energy should be higher for contradictions than for matching claims
        self.assertGreater(energy_high.total_energy, energy_low.total_energy)

    def test_session_statistics(self):
        """Test session statistics tracking."""
        # Perform some operations
        self.session.add_concept(CogConcept(name="Test1"))
        self.session.add_concept(CogConcept(name="Test2"))
        self.session.add_relation(CogRelation(
            source="Test1", target="Test2",
            relation_type=RelationType.SIMILAR_TO,
        ))

        claim = CogClaim(source="Test1", target="Test2", relation="similar_to")
        self.engine.check_claim(claim)

        # Get summary
        summary = self.session.get_summary()

        self.assertEqual(summary["activity"]["concepts_added"], 2)
        self.assertEqual(summary["activity"]["relations_added"], 1)
        self.assertEqual(summary["activity"]["checks_performed"], 1)
        self.assertGreater(summary["category"]["num_objects"], 0)

    def test_explain(self):
        """Test detailed explanation of check results."""
        self.session.add_concept(CogConcept(name="A"))
        self.session.add_concept(CogConcept(name="B"))

        claim = CogClaim(source="A", target="B", relation="entails")
        explanation = self.engine.explain(claim)

        # Should include all key sections
        self.assertIn("energy", explanation)
        self.assertIn("routing", explanation)
        self.assertIn("result", explanation)
        self.assertIn("graph_context", explanation)

    def test_no_supply_chain_references(self):
        """Verify supply_chain module is not referenced."""
        # This should not raise ImportError for missing supply_chain
        try:
            # Just verify the engine works without supply chain
            self.engine.assert_knowledge(CogConcept(name="Test"))
            success = True
        except ImportError as e:
            if "supply_chain" in str(e):
                success = False
            else:
                raise

        self.assertTrue(success, "supply_chain module should not be referenced")


class TestCogCategoryAPI(unittest.TestCase):
    """Test that COG correctly uses KOMPOSOS-IV Category API."""

    def setUp(self):
        """Create test session."""
        self.session = CogSession(db_path=":memory:")

    def test_add_uses_category_add(self):
        """Verify add_concept uses Category.add()."""
        concept = CogConcept(name="TestObj")
        self.session.add_concept(concept)

        # Should be retrievable via Category.get()
        obj = self.session.category.get("TestObj")
        self.assertIsNotNone(obj)
        self.assertEqual(obj.name, "TestObj")

    def test_morphisms_use_source_target_not_names(self):
        """Verify morphisms use .source/.target instead of .source_name/.target_name."""
        self.session.add_concept(CogConcept(name="A"))
        self.session.add_concept(CogConcept(name="B"))
        self.session.add_relation(CogRelation(
            source="A", target="B",
            relation_type=RelationType.ENTAILS,
        ))

        morphisms = self.session.category.morphisms_from("A")
        self.assertEqual(len(morphisms), 1)

        mor = morphisms[0]
        # IV API uses .source and .target (not .source_name, .target_name)
        self.assertEqual(mor.source, "A")
        self.assertEqual(mor.target, "B")
        self.assertFalse(hasattr(mor, 'source_name'))
        self.assertFalse(hasattr(mor, 'target_name'))

    def test_find_paths_returns_path_objects(self):
        """Verify find_paths returns List[Path] objects in KOMPOSOS-IV."""
        self.session.add_concept(CogConcept(name="A"))
        self.session.add_concept(CogConcept(name="B"))
        self.session.add_relation(CogRelation(
            source="A", target="B",
            relation_type=RelationType.ENTAILS,
        ))

        # find_paths expects string names, not Object instances
        paths = self.session.category.find_paths("A", "B")

        self.assertGreater(len(paths), 0)
        # Each path should be a Path object with morphism_ids
        from core.types import Path
        self.assertIsInstance(paths[0], Path)
        self.assertGreater(len(paths[0].morphism_ids), 0)


if __name__ == "__main__":
    unittest.main()
