# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This bridge plugin is dual-licensed (Apache-2.0 OR KOMPOSOS-IV-Commercial).
# It integrates with Orion Core, which is separately licensed under MIT.
# Orion Core (c) Borkwork (https://github.com/borkwork/orion-framework)

"""
OPTIMUS Refinement Plugin for Orion

Exposes categorical gradient descent (OPTIMUS) as an Orion capability.
Enables self-refinement of the knowledge graph, Yoneda-guided structural
transfer, and structural gap detection.

This is a KOMPOSOS-IV plugin that integrates with Orion Core (MIT licensed).
"""

from __future__ import annotations

import logging
import sys
import os

# Add orion-main to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'orion-main', 'src'))

from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Import from Orion (MIT licensed by Borkwork)
from orion_core import Plugin
from orion_core.plugin import on, hook

from core.category import Category
from core.optimus import OptimusEngine


class OptimusPlugin(Plugin):
    """
    Expose OPTIMUS categorical refinement as an Orion capability.

    Capabilities provided:
    - optimization: Self-refine the knowledge graph via categorical gradient descent
    - factorization: Discover intermediate concepts between objects
    - yoneda: Structural similarity and fingerprinting

    Events consumed:
    - knowledge.refine: Trigger refinement
    - knowledge.absorb: Yoneda-guided structural transfer
    - knowledge.gaps: Detect structural holes

    Events published:
    - knowledge.refined: Refinement complete
    - morphism.discovered: New shortcut morphism found
    - gap.detected: Structural hole found
    """

    def __init__(
        self,
        core,
        *,
        category: Optional[Category] = None,
        max_depth: int = 3,
    ):
        """Initialize OPTIMUS refinement plugin.

        Args:
            core: Orion Core instance
            category: KOMPOSOS-IV Category to refine
            max_depth: Maximum factorization depth for OPTIMUS
        """
        super().__init__(
            core,
            name="optimus_refinement",
            version="0.1.0",
            description="Categorical gradient descent and self-refinement",
            provides={"optimization", "factorization", "yoneda"},
            events_published={"knowledge.refined", "morphism.discovered", "gap.detected"},
        )

        self.engine = OptimusEngine(category, max_depth=max_depth)

    async def on_start(self):
        """Plugin startup."""
        stats = {
            "objects": len(self.engine.category.objects()),
            "morphisms": len(self.engine.category.morphisms()),
        }
        logger.info(
            f"OPTIMUS Plugin started. "
            f"Graph: {stats['objects']} objects, {stats['morphisms']} morphisms"
        )

    async def on_stop(self):
        """Plugin shutdown."""
        rewrites = len(self.engine.rewrites)
        logger.info(f"OPTIMUS Plugin stopping. Total rewrites: {rewrites}")

    # ========================================================================
    # Public API Methods (Orion capability interface)
    # ========================================================================

    async def refine_knowledge(
        self,
        max_steps: int = 20,
        depth: int = 2,
    ) -> Dict[str, Any]:
        """
        Run categorical gradient descent on the knowledge graph.

        Searches for better factorizations of morphisms and materializes
        shortcuts in the Category.

        Args:
            max_steps: Maximum refinement iterations.
            depth: Maximum factorization depth.

        Returns:
            Summary with steps, improved morphisms, synced morphisms.
        """
        result = self.engine.refine(
            max_steps=max_steps,
            depth=depth,
            verbose=False,
        )

        # Emit events
        await self.emit("knowledge.refined", {
            "steps": result["steps"],
            "synced_morphisms": result["synced_morphisms"],
            "improved_count": len(result.get("improved", [])),
        })

        for mor_name in result["synced_morphisms"]:
            await self.emit("morphism.discovered", {
                "morphism": mor_name,
                "source": "optimus_refinement",
            })

        return result

    async def refine_morphism(
        self,
        source: str,
        target: str,
        depth: int = 2,
    ) -> Optional[Dict[str, Any]]:
        """
        Refine a specific morphism between source and target.

        Args:
            source: Source object name.
            target: Target object name.
            depth: Factorization depth.

        Returns:
            Dict with improved morphism info, or None if no improvement.
        """
        improved = self.engine.refine_morphism(source, target, depth=depth)
        if improved is None:
            return None

        await self.emit("morphism.discovered", {
            "morphism": improved.name,
            "source_obj": improved.source,
            "target_obj": improved.target,
            "confidence": improved.confidence,
        })

        return {
            "name": improved.name,
            "source": improved.source,
            "target": improved.target,
            "confidence": improved.confidence,
            "provenance": improved.provenance,
        }

    async def discover_intermediates(
        self,
        source: str,
        target: str,
        depth: int = 3,
    ) -> List[str]:
        """
        Find intermediate objects between source and target.

        Args:
            source: Source object name.
            target: Target object name.
            depth: Maximum factorization depth.

        Returns:
            List of intermediate object names.
        """
        return self.engine.discover_intermediates(source, target, depth=depth)

    async def absorb_structure(
        self,
        source_obj: str,
        target_obj: str,
        threshold: float = 0.8,
    ) -> List[Dict[str, Any]]:
        """
        Yoneda-guided structural transfer.

        Transfer morphisms from source_obj to target_obj if they
        are structurally similar.

        Args:
            source_obj: Object to transfer FROM.
            target_obj: Object to transfer TO.
            threshold: Minimum Yoneda similarity.

        Returns:
            List of transferred morphism info dicts.
        """
        transferred = self.engine.absorb(source_obj, target_obj, threshold=threshold)
        return [
            {
                "name": m.name,
                "source": m.source,
                "target": m.target,
                "confidence": m.confidence,
            }
            for m in transferred
        ]

    async def yoneda_similarity(self, a: str, b: str) -> float:
        """
        Compute structural similarity between two objects.

        Returns:
            float in [0, 1].
        """
        return self.engine.yoneda_similarity(a, b)

    async def find_capability_gaps(self) -> List[Dict[str, Any]]:
        """
        Detect structural holes in the knowledge graph.

        A structural hole exists when A -> B -> C exists but
        no direct A -> C morphism exists.

        Returns:
            List of gaps sorted by path confidence (descending).
        """
        gaps = self.engine.find_structural_gaps()

        for gap in gaps:
            await self.emit("gap.detected", gap)

        return gaps

    # ========================================================================
    # Event Handlers (Orion event-driven interface)
    # ========================================================================

    @on("knowledge.refine")
    async def on_knowledge_refine(self, event):
        """Handle knowledge refinement requests."""
        return await self.refine_knowledge(
            max_steps=event.data.get("max_steps", 20),
            depth=event.data.get("depth", 2),
        )

    @on("knowledge.absorb")
    async def on_knowledge_absorb(self, event):
        """Handle structural transfer requests."""
        return await self.absorb_structure(
            source_obj=event.data["source"],
            target_obj=event.data["target"],
            threshold=event.data.get("threshold", 0.8),
        )

    @on("knowledge.gaps")
    async def on_knowledge_gaps(self, event):
        """Handle gap detection requests."""
        return await self.find_capability_gaps()

    # ========================================================================
    # Hooks (Orion hook-based interface)
    # ========================================================================

    @hook("optimization.refine", priority=10)
    async def refine_hook(self, refine_data):
        """Hook for optimization pipeline."""
        return await self.refine_knowledge(**refine_data)
