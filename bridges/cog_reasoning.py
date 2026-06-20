# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This bridge plugin is dual-licensed (Apache-2.0 OR KOMPOSOS-IV-Commercial).
# It integrates with Orion Core, which is separately licensed under MIT.
# Orion Core © Borkwork (https://github.com/borkwork/orion-framework)

"""
COG Reasoning Plugin for Orion

Provides categorical reasoning and tiered verification as Orion capabilities.

This is a KOMPOSOS-IV plugin that integrates with Orion Core (MIT licensed).
"""

from __future__ import annotations

import logging
import sys
import os

# Add orion-main to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'orion-main', 'src'))

from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Import from Orion (MIT licensed by Borkwork)
from orion_core import Plugin
from orion_core.plugin import on, hook

from cog.session import CogSession
from cog.engine import CogEngine
from cog.schema import (
    CogClaim,
    CogConcept,
    CogRelation,
    CheckResult,
    ConceptType,
    RelationType,
    VerificationStatus,
)


class CogReasoningPlugin(Plugin):
    """
    Provide COG tiered verification as an Orion capability.

    Capabilities provided:
    - reasoning: Verify claims through 5-tier categorical verification
    - verification: Formal proof checking (ZFC + CAT dual-engine)
    - knowledge_graph: Query categorical knowledge structure

    Events consumed:
    - claim.verify: Verify a claim
    - knowledge.query: Query knowledge graph

    Events published:
    - claim.verified: Claim verification complete
    - knowledge.result: Query results
    """

    def __init__(
        self,
        core,
        *,
        cog_session: Optional[CogSession] = None,
        db_path: str = ":memory:",
    ):
        """Initialize COG reasoning plugin.

        Args:
            core: Orion Core instance
            cog_session: Optional pre-configured COG session
            db_path: Database path for persistent memory (default: in-memory)
        """
        super().__init__(
            core,
            name="cog_reasoning",
            version="0.1.0",
            description="Categorical reasoning and tiered verification",
            provides={"reasoning", "verification", "knowledge_graph"},
            events_published={"claim.verified", "knowledge.result"},
        )

        # Initialize COG session and engine
        self.session = cog_session or CogSession(db_path=db_path)
        self.engine = CogEngine(self.session)

    async def on_start(self):
        """Plugin startup - log COG initialization."""
        summary = self.session.get_summary()
        logger.info(
            f"COG Reasoning Plugin started. Session: {summary['session_id']}"
        )

    async def on_stop(self):
        """Plugin shutdown - save session summary."""
        summary = self.session.get_summary()
        logger.info(
            f"COG Reasoning Plugin stopping. "
            f"Processed {summary['activity']['checks_performed']} claims."
        )

    # ========================================================================
    # Public API Methods (Orion capability interface)
    # ========================================================================

    async def verify_claim(
        self,
        source: str,
        target: str,
        relation: str,
        confidence: float = 0.5,
        max_tier: int = 4,
    ) -> CheckResult:
        """
        Verify a claim through tiered categorical verification.

        Args:
            source: Source concept
            target: Target concept
            relation: Relationship type
            confidence: Initial confidence (0-1)
            max_tier: Maximum tier to use (0-4)

        Returns:
            CheckResult with verification status and proof path

        Example:
            result = await cog.verify_claim(
                source="Python",
                target="ML",
                relation="supports"
            )
        """
        claim = CogClaim(
            source=source,
            target=target,
            relation=relation,
            confidence=confidence,
        )
        result = self.engine.check_claim(claim, depth=max_tier)

        # Emit event
        await self.emit(
            "claim.verified",
            {
                "source": source,
                "target": target,
                "relation": relation,
                "status": result.status.value,
                "confidence": result.confidence,
                "tier": result.tier_reached,
            },
        )

        return result

    async def add_knowledge(
        self,
        source: str,
        target: str,
        relation: str,
        confidence: float = 1.0,
        evidence: str = "",
    ) -> bool:
        """
        Add knowledge to the categorical knowledge graph.

        Args:
            source: Source concept
            target: Target concept
            relation: Relationship type
            confidence: Confidence weight (0-1)
            evidence: Supporting evidence text

        Returns:
            True if added successfully

        Example:
            await cog.add_knowledge(
                source="Python",
                target="typing",
                relation="supports",
                confidence=0.9,
                evidence="Python 3.5+ has typing module"
            )
        """
        # Auto-create concepts if needed
        if not self.session.category.get(source):
            self.session.add_concept(CogConcept(name=source))
        if not self.session.category.get(target):
            self.session.add_concept(CogConcept(name=target))

        # Add relation
        try:
            relation_type = RelationType[relation.upper()]
        except KeyError:
            # Default to SIMILAR_TO if unknown
            relation_type = RelationType.SIMILAR_TO

        return self.session.add_relation(
            CogRelation(
                source=source,
                target=target,
                relation_type=relation_type,
                confidence=confidence,
                evidence=evidence,
            )
        )

    async def query_knowledge(
        self,
        source: str,
        target: Optional[str] = None,
        relation: Optional[str] = None,
        max_results: int = 20,
    ) -> Dict[str, Any]:
        """
        Query the categorical knowledge graph.

        Args:
            source: Source concept
            target: Optional target (finds paths if provided)
            relation: Optional relation filter
            max_results: Maximum results to return

        Returns:
            Query results with paths, neighbors, or relationships

        Example:
            # Find all relationships from Python
            result = await cog.query_knowledge("Python")

            # Find paths from Python to ML
            result = await cog.query_knowledge("Python", "ML")
        """
        result = self.engine.query(
            source=source,
            target=target,
            relation=relation,
            max_results=max_results,
        )

        await self.emit("knowledge.result", result)
        return result

    async def explain_verification(
        self, source: str, target: str, relation: str
    ) -> Dict[str, Any]:
        """
        Get detailed explanation of verification process.

        Args:
            source: Source concept
            target: Target concept
            relation: Relationship type

        Returns:
            Detailed explanation with energy, routing, and results
        """
        claim = CogClaim(source=source, target=target, relation=relation)
        return self.engine.explain(claim)

    async def get_session_summary(self) -> Dict[str, Any]:
        """Get session statistics."""
        return self.session.get_summary()

    # ========================================================================
    # Event Handlers (Orion event-driven interface)
    # ========================================================================

    @on("claim.verify")
    async def on_claim_verify(self, event):
        """Handle claim verification events."""
        result = await self.verify_claim(
            source=event.data["source"],
            target=event.data["target"],
            relation=event.data["relation"],
            confidence=event.data.get("confidence", 0.5),
            max_tier=event.data.get("max_tier", 4),
        )
        return result

    @on("knowledge.add")
    async def on_knowledge_add(self, event):
        """Handle knowledge addition events."""
        return await self.add_knowledge(
            source=event.data["source"],
            target=event.data["target"],
            relation=event.data["relation"],
            confidence=event.data.get("confidence", 1.0),
            evidence=event.data.get("evidence", ""),
        )

    @on("knowledge.query")
    async def on_knowledge_query(self, event):
        """Handle knowledge query events."""
        return await self.query_knowledge(
            source=event.data["source"],
            target=event.data.get("target"),
            relation=event.data.get("relation"),
            max_results=event.data.get("max_results", 20),
        )

    # ========================================================================
    # Hooks (Orion hook-based interface)
    # ========================================================================

    @hook("claim.validate", priority=10)
    async def validate_claim_hook(self, claim_data):
        """
        Hook for claim validation pipeline.

        This allows other plugins to participate in claim verification.
        """
        return await self.verify_claim(**claim_data)

    @hook("knowledge.enrich", priority=5)
    async def enrich_knowledge_hook(self, concept_name):
        """
        Hook for knowledge enrichment pipeline.

        Returns related concepts and relationships.
        """
        return await self.query_knowledge(concept_name)
