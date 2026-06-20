# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Infinity Cosmos Plugin for Orion

Exposes the ∞-cosmos layer as an Orion capability, enabling:
- Homotopy 2-Category reasoning (2-cells between parallel morphisms)
- Cartesian fibration detection
- Yoneda embedding computation
- Pointwise Kan extensions
- Interchange law verification

This connects the InfinityCosmos blueprint with the Ruliad self-observation:
the system can analyze its own architecture at the 2-cell level.

Usage:
    plugin = InfinityCosmosPlugin(core, category=my_category)
    await core.register_plugin(plugin)

    # Via capability interface:
    h2k_stats = await plugin.get_homotopy_2_category_stats()
    yoneda = await plugin.compute_yoneda_embedding()
    fibrations = await plugin.find_cartesian_fibrations()
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import Orion (may not be available in all contexts)
try:
    import sys
    import os
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'orion-main', 'src'
    ))
    from orion_core import Plugin
    from orion_core.plugin import on, hook
    HAS_ORION = True
except ImportError:
    HAS_ORION = False
    # Provide stub for testing
    class Plugin:
        def __init__(self, core, **kwargs):
            self.core = core
            self.name = kwargs.get('name', 'unknown')
    def on(event):
        def decorator(fn):
            return fn
        return decorator
    def hook(event, priority=10):
        def decorator(fn):
            return fn
        return decorator

from core.category import Category
from core.cosmos import InfinityCosmos
from core.two_cell_bridge import TwoCellBridge


class InfinityCosmosPlugin(Plugin):
    """
    Bridge ∞-cosmos reasoning to Orion as a capability.

    Capabilities provided:
    - homotopy_2_category: 2-cell reasoning between parallel morphisms
    - yoneda_embedding: Structural equivalence via Yoneda
    - cartesian_fibrations: Fibration detection
    - kan_extension: Pointwise Kan extensions
    - interchange_check: 2-category coherence verification

    Events published:
    - cosmos.two_cell_added: New 2-cell created
    - cosmos.fibration_detected: New cartesian fibration found
    """

    def __init__(
        self,
        core,
        category: Category = None,
        db_path: str = ":memory:",
    ):
        super().__init__(
            core,
            name="infinity_cosmos",
            version="0.1.0",
            description="∞-cosmos layer: higher categorical reasoning",
            provides={
                "homotopy_2_category",
                "yoneda_embedding",
                "cartesian_fibrations",
                "kan_extension",
                "interchange_check",
            },
            events_published={
                "cosmos.two_cell_added",
                "cosmos.fibration_detected",
            },
        )

        self.category = category or Category(db_path=db_path)
        self.cosmos = InfinityCosmos(self.category)
        self.bridge = TwoCellBridge(self.cosmos)

    async def on_start(self):
        """Plugin startup."""
        stats = self.cosmos.statistics()
        logger.info(
            f"InfinityCosmosPlugin started. "
            f"Objects={stats['objects']}, Morphisms={stats['morphisms']}, "
            f"TwoCells={stats['two_cells']}"
        )

    async def on_stop(self):
        """Plugin shutdown."""
        logger.info("InfinityCosmosPlugin stopping")

    # ========================================================================
    # Public API: Homotopy 2-Category
    # ========================================================================

    async def get_homotopy_2_category_stats(self) -> Dict[str, Any]:
        """Get statistics about the homotopy 2-category."""
        h2k = self.cosmos.homotopy_2_category()
        return {
            "name": h2k.name,
            "objects": len(h2k.objects),
            "morphisms": len(h2k.morphisms),
            "two_cells": len(h2k.two_cells),
        }

    async def add_two_cell(
        self,
        name: str,
        source_morphism: str,
        target_morphism: str,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Add a 2-cell α: f => g to the homotopy 2-category.

        Args:
            name: Name for the 2-cell.
            source_morphism: Source 1-cell ID.
            target_morphism: Target 1-cell ID.
            data: Optional metadata.

        Returns:
            Dict with 2-cell info.
        """
        cell = self.cosmos.add_two_cell(name, source_morphism, target_morphism, data)
        return {
            "name": cell.name,
            "source": cell.source_morphism,
            "target": cell.target_morphism,
        }

    async def verify_claim_2cell(
        self,
        source: str,
        target: str,
        relation: str = None,
    ) -> Dict[str, Any]:
        """
        Verify a claim using 2-cell reasoning (COG Tier 4 interface).

        Args:
            source: Source object.
            target: Target object.
            relation: Optional morphism name.

        Returns:
            Verification result with verdict and witnesses.
        """
        return self.bridge.tier4_verify(source, target, relation)

    # ========================================================================
    # Public API: Yoneda Embedding
    # ========================================================================

    async def compute_yoneda_embedding(self) -> Dict[str, Any]:
        """
        Compute the Yoneda embedding y: C -> [C^op, Set].

        Returns:
            Dict with embedding info and faithfulness score.
        """
        result = self.cosmos.yoneda_embedding()
        return {
            "is_fully_faithful": result.is_fully_faithful,
            "faithfulness_score": result.faithfulness_score,
            "objects_mapped": result.objects_mapped,
            "presheaf_count": len(result.presheaf_objects),
        }

    async def yoneda_similarity(
        self, object_a: str, object_b: str
    ) -> Dict[str, Any]:
        """
        Check structural similarity via Yoneda embedding.

        Args:
            object_a: First object name.
            object_b: Second object name.

        Returns:
            Dict with similarity info.
        """
        from core.optimus import OptimusEngine
        engine = OptimusEngine(self.category)
        sim = engine.yoneda_similarity(object_a, object_b)
        return {
            "object_a": object_a,
            "object_b": object_b,
            "similarity": sim,
            "structurally_equivalent": sim > 0.9,
        }

    # ========================================================================
    # Public API: Cartesian Fibrations
    # ========================================================================

    async def find_cartesian_fibrations(self) -> Dict[str, Any]:
        """
        Find cartesian fibrations in the category.

        Returns:
            Dict of fibration_name -> info.
        """
        fibrations = self.cosmos.cartesian_fibrations()
        return {
            name: {
                "objects": fib.total_objects,
                "cartesian_lifts": fib.cartesian_lifts,
                "stats": fib.fiber_stats,
            }
            for name, fib in fibrations.items()
        }

    async def check_cartesian_lift(self, morphism_id: str) -> Dict[str, Any]:
        """Check if a specific morphism is a cartesian lift."""
        return self.bridge.check_cartesian(morphism_id)

    # ========================================================================
    # Public API: Kan Extensions
    # ========================================================================

    async def compute_kan_extension(
        self,
        functor_obj_map: Dict[str, str],
        diagram_objects: List[str],
        target_object: str,
        left: bool = True,
    ) -> Dict[str, Any]:
        """
        Compute pointwise Kan extension.

        Args:
            functor_obj_map: Object mapping for the functor.
            diagram_objects: Objects of the source category.
            target_object: The object to extend to.
            left: True for Left Kan (colimit), False for Right (limit).

        Returns:
            Dict with extension result.
        """
        return self.cosmos.kan_extension(
            functor_obj_map, diagram_objects, target_object, left
        )

    # ========================================================================
    # Public API: Interchange Law
    # ========================================================================

    async def check_interchange_coherence(self) -> Dict[str, Any]:
        """
        Verify that the 2-category satisfies the interchange law.

        Returns:
            Dict with coherence info.
        """
        return self.bridge.verify_interchange_coherence()

    # ========================================================================
    # Public API: ∞-Cosmos Axioms
    # ========================================================================

    async def verify_cosmos_axioms(self) -> Dict[str, Any]:
        """Verify that the underlying Category satisfies ∞-cosmos axioms."""
        return self.cosmos.verify_cosmos_axioms()

    async def get_cosmos_statistics(self) -> Dict[str, Any]:
        """Get comprehensive ∞-cosmos statistics."""
        return self.cosmos.statistics()

    # ========================================================================
    # Event Handlers
    # ========================================================================

    @on("morphism.added")
    async def on_morphism_added(self, event):
        """Rebuild cosmos caches when morphisms change."""
        # Invalidate cached structures
        self.cosmos._h2k = None
        self.cosmos._isofibrations = {}
        self.cosmos._fibrations = {}
        self.cosmos._yoneda_result = None
