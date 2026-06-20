# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-IV Commercial License (see LICENSE-COMMERCIAL file)

"""
COG Session — Per-conversation cognitive state management.

Wraps a Category (in-memory by default) that accumulates
knowledge across tool calls in a single conversation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.category import Category
from core.types import Object, Morphism

from .schema import CogConcept, CogRelation, ConceptType, RelationType


@dataclass
class SessionStats:
    """Statistics about a session's activity."""
    concepts_added: int = 0
    relations_added: int = 0
    checks_performed: int = 0
    tier_histogram: Dict[int, int] = field(
        default_factory=lambda: {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    )
    total_energy_spent: float = 0.0


class CogSession:
    """
    Per-conversation cognitive state.

    Each MCP connection gets a session that maintains an in-memory
    knowledge graph across tool calls.
    """

    def __init__(self, session_id: Optional[str] = None,
                 db_path: str = ":memory:",
                 category: Optional[Category] = None):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.category = category or Category(db_path=db_path)
        self.stats = SessionStats()
        self.created_at = datetime.now()
        self._claim_history: List[Dict[str, Any]] = []

    def add_concept(self, concept: CogConcept) -> bool:
        """Add a concept to the session graph."""
        # Use add() with name and kwargs instead of creating Object manually
        result = self.category.add(
            name=concept.name,
            type_name=concept.concept_type.value,
            metadata={
                "description": concept.description,
                **concept.metadata,
            },
            provenance=concept.provenance,
        )
        if result:
            self.stats.concepts_added += 1
        return result

    def add_relation(self, relation: CogRelation) -> bool:
        """Add a relation to the session graph. Auto-creates endpoints if missing."""
        if not self.category.get(relation.source):
            self.add_concept(CogConcept(name=relation.source))
        if not self.category.get(relation.target):
            self.add_concept(CogConcept(name=relation.target))

        # Use connect() which is simpler for creating morphisms
        result = self.category.connect(
            source=relation.source,
            target=relation.target,
            name=relation.relation_type.value,
            confidence=relation.confidence,
            metadata={
                "evidence": relation.evidence,
                **relation.metadata,
            },
        )
        if result:
            self.stats.relations_added += 1
        return result

    def record_check(self, claim_source: str, claim_target: str,
                     claim_relation: str, tier: int, energy: float):
        """Record a check for statistics."""
        self.stats.checks_performed += 1
        self.stats.tier_histogram[tier] = self.stats.tier_histogram.get(tier, 0) + 1
        self.stats.total_energy_spent += energy
        self._claim_history.append({
            "claim": f"{claim_source}->{claim_target}",
            "relation": claim_relation,
            "tier": tier,
            "energy": energy,
            "timestamp": datetime.now().isoformat(),
        })

    def get_summary(self) -> Dict[str, Any]:
        """Get session summary for agent inspection."""
        category_stats = {
            "num_objects": len(self.category.objects()),
            "num_morphisms": len(self.category.morphisms()),
        }
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "category": category_stats,
            "activity": {
                "concepts_added": self.stats.concepts_added,
                "relations_added": self.stats.relations_added,
                "checks_performed": self.stats.checks_performed,
                "tier_histogram": self.stats.tier_histogram,
                "total_energy": round(self.stats.total_energy_spent, 4),
            },
            "recent_checks": self._claim_history[-10:],
        }
