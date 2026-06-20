# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This bridge plugin is dual-licensed (Apache-2.0 OR KOMPOSOS-IV-Commercial).
# It integrates with Orion Core, which is separately licensed under MIT.
# Orion Core © Borkwork (https://github.com/borkwork/orion-framework)

"""
Knowledge Manager Plugin for Orion

Bridges Orion events to KOMPOSOS-IV Category for persistent knowledge storage.

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
from core.types import Object, Morphism


class KnowledgeManagerPlugin(Plugin):
    """
    Bridge Orion events to KOMPOSOS-IV Category.

    Capabilities provided:
    - knowledge_store: Persistent categorical knowledge storage
    - graph_query: Query categorical graph structure

    Events consumed:
    - knowledge.* (all knowledge events)
    - fact.learned: Store a new fact
    - concept.created: Add a new concept

    Events published:
    - knowledge.stored: Fact stored successfully
    - knowledge.queried: Query completed
    """

    def __init__(
        self,
        core,
        *,
        category: Optional[Category] = None,
        db_path: str = "knowledge.db",
    ):
        """Initialize knowledge manager.

        Args:
            core: Orion Core instance
            category: Optional pre-configured Category
            db_path: Database path for persistent storage
        """
        super().__init__(
            core,
            name="knowledge_manager",
            version="0.1.0",
            description="Persistent categorical knowledge storage",
            provides={"knowledge_store", "graph_query"},
            events_published={"knowledge.stored", "knowledge.queried"},
        )

        # Initialize or use provided Category
        self.category = category or Category(db_path=db_path)

    async def on_start(self):
        """Plugin startup."""
        stats = {
            "objects": len(self.category.objects()),
            "morphisms": len(self.category.morphisms()),
        }
        logger.info(
            f"Knowledge Manager started. "
            f"Graph: {stats['objects']} objects, {stats['morphisms']} morphisms"
        )

    async def on_stop(self):
        """Plugin shutdown - log final statistics."""
        stats = {
            "objects": len(self.category.objects()),
            "morphisms": len(self.category.morphisms()),
        }
        logger.info(
            f"Knowledge Manager stopping. "
            f"Final graph: {stats['objects']} objects, {stats['morphisms']} morphisms"
        )

    # ========================================================================
    # Public API Methods (Orion capability interface)
    # ========================================================================

    async def add_object(
        self,
        name: str,
        type_name: str = "Object",
        metadata: Optional[Dict] = None,
        **kwargs,
    ) -> bool:
        """
        Add an object to the knowledge graph.

        Args:
            name: Object name
            type_name: Object type
            metadata: Optional metadata dict
            **kwargs: Additional Object fields

        Returns:
            True if added successfully
        """
        return self.category.add(
            name=name,
            type_name=type_name,
            metadata=metadata or {},
            **kwargs,
        )

    async def add_morphism(
        self,
        source: str,
        target: str,
        name: str,
        confidence: float = 1.0,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """
        Add a morphism (relationship) to the knowledge graph.

        Args:
            source: Source object name
            target: Target object name
            name: Morphism name (relationship type)
            confidence: Confidence weight (0-1)
            metadata: Optional metadata dict

        Returns:
            True if added successfully
        """
        # Ensure source and target exist
        if not self.category.get(source):
            await self.add_object(source)
        if not self.category.get(target):
            await self.add_object(target)

        return self.category.connect(
            source=source,
            target=target,
            name=name,
            confidence=confidence,
            metadata=metadata or {},
        )

    async def find_paths(
        self,
        source: str,
        target: str,
        max_length: int = 10,
    ) -> List[Dict]:
        """
        Find all paths from source to target.

        Args:
            source: Source object name
            target: Target object name
            max_length: Maximum path length

        Returns:
            List of paths (each path is a dict with morphism_ids, weight, etc.)
        """
        paths = self.category.find_paths(source, target, max_length=max_length)
        return [
            {
                "morphisms": path.morphism_ids,
                "length": path.length,
                "weight": path.weight,
                "source": path.source,
                "target": path.target,
            }
            for path in paths
        ]

    async def get_neighbors(
        self,
        name: str,
        direction: str = "outgoing",
    ) -> List[Dict]:
        """
        Get neighboring objects.

        Args:
            name: Object name
            direction: "outgoing", "incoming", or "both"

        Returns:
            List of neighbor dicts
        """
        neighbors = []

        if direction in ("outgoing", "both"):
            for mor in self.category.morphisms_from(name):
                neighbors.append({
                    "object": mor.target,
                    "relation": mor.name,
                    "confidence": mor.confidence,
                    "direction": "outgoing",
                })

        if direction in ("incoming", "both"):
            for mor in self.category.morphisms_to(name):
                neighbors.append({
                    "object": mor.source,
                    "relation": mor.name,
                    "confidence": mor.confidence,
                    "direction": "incoming",
                })

        return neighbors

    async def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge graph statistics."""
        return {
            "num_objects": len(self.category.objects()),
            "num_morphisms": len(self.category.morphisms()),
            "deterministic": self.category.is_deterministic,
        }

    # ========================================================================
    # Event Handlers (Orion event-driven interface)
    # ========================================================================

    @on("fact.learned")
    async def on_fact_learned(self, event):
        """
        Handle fact.learned events.

        Event data:
            source: Source concept
            target: Target concept
            relation: Relationship type
            confidence: Optional confidence (default 1.0)
        """
        result = await self.add_morphism(
            source=event.data["source"],
            target=event.data["target"],
            name=event.data["relation"],
            confidence=event.data.get("confidence", 1.0),
        )

        await self.emit(
            "knowledge.stored",
            {
                "source": event.data["source"],
                "target": event.data["target"],
                "relation": event.data["relation"],
                "success": result,
            },
        )

        return result

    @on("concept.created")
    async def on_concept_created(self, event):
        """
        Handle concept.created events.

        Event data:
            name: Concept name
            type: Optional type (default "Object")
            metadata: Optional metadata dict
        """
        return await self.add_object(
            name=event.data["name"],
            type_name=event.data.get("type", "Object"),
            metadata=event.data.get("metadata", {}),
        )

    @on("knowledge.query_paths")
    async def on_query_paths(self, event):
        """
        Handle knowledge.query_paths events.

        Event data:
            source: Source object
            target: Target object
            max_length: Optional max path length
        """
        paths = await self.find_paths(
            source=event.data["source"],
            target=event.data["target"],
            max_length=event.data.get("max_length", 10),
        )

        await self.emit(
            "knowledge.queried",
            {
                "source": event.data["source"],
                "target": event.data["target"],
                "paths": paths,
                "count": len(paths),
            },
        )

        return paths

    @on("knowledge.query_neighbors")
    async def on_query_neighbors(self, event):
        """
        Handle knowledge.query_neighbors events.

        Event data:
            name: Object name
            direction: Optional direction (default "both")
        """
        neighbors = await self.get_neighbors(
            name=event.data["name"],
            direction=event.data.get("direction", "both"),
        )

        await self.emit(
            "knowledge.queried",
            {
                "name": event.data["name"],
                "neighbors": neighbors,
                "count": len(neighbors),
            },
        )

        return neighbors

    # ========================================================================
    # Hooks (Orion hook-based interface)
    # ========================================================================

    @hook("knowledge.persist", priority=10)
    async def persist_knowledge_hook(self, knowledge_data):
        """
        Hook for knowledge persistence pipeline.

        This allows other plugins to participate in knowledge storage.
        """
        return await self.add_morphism(**knowledge_data)

    @hook("knowledge.retrieve", priority=5)
    async def retrieve_knowledge_hook(self, query_data):
        """
        Hook for knowledge retrieval pipeline.

        Returns paths or neighbors based on query.
        """
        if "target" in query_data:
            return await self.find_paths(
                query_data["source"], query_data["target"]
            )
        else:
            return await self.get_neighbors(query_data["source"])
