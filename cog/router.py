# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-IV Commercial License (see LICENSE-COMMERCIAL file)

"""
COG Router — Tiered computation routing.

Decides which computational tier to invoke based on claim energy,
graph state, and optional explicit override.

Tiers:
  0: Graph Lookup          ~1ms
  1: Composition + Paths   ~10ms
  2: Sheaf + Kan           ~100ms  [Phase 2]
  3: ZFC Dual Engine       ~1s     [Phase 2]
  4: Full Topology + Flow  ~10s    [Phase 3]
"""

from __future__ import annotations

from enum import IntEnum
from dataclasses import dataclass
from typing import Optional

from core.category import Category

from .schema import CogClaim


class Tier(IntEnum):
    """Computational tiers, ordered by cost/depth."""
    LOOKUP = 0
    COMPOSITION = 1
    SHEAF_KAN = 2
    DUAL_ENGINE = 3
    FULL_TOPOLOGY = 4


@dataclass
class TierDecision:
    """Result of the routing decision."""
    tier: Tier
    reason: str
    should_escalate: bool = False


# Energy thresholds for tier escalation
# Raised to keep most checks at Tier 0-1 (fast) — only genuinely
# uncertain or contradictory claims escalate to higher tiers.
ENERGY_THRESHOLDS = {
    Tier.LOOKUP: 0.2,
    Tier.COMPOSITION: 0.5,
    Tier.SHEAF_KAN: 0.7,
    Tier.DUAL_ENGINE: 0.85,
    Tier.FULL_TOPOLOGY: 1.0,
}


class TierRouter:
    """
    Route claims to the appropriate computational tier.

    Priority order:
      1. Explicit request (agent specifies depth)
      2. Graph state (source/target don't exist -> Tier 0)
      3. Direct edge exists -> Tier 0
      4. Energy-based escalation
    """

    def __init__(self, category: Category):
        self.category = category

    def route(self, claim: CogClaim, energy: float,
              explicit_tier: Optional[int] = None) -> TierDecision:
        """Decide which tier to invoke for this claim."""

        # 1. Explicit request
        if explicit_tier is not None:
            tier = Tier(min(explicit_tier, 4))
            return TierDecision(tier=tier, reason=f"Explicitly requested tier {tier.value}")

        # 2. Check if source/target exist
        source_exists = self.category.get(claim.source) is not None
        target_exists = self.category.get(claim.target) is not None

        if not source_exists or not target_exists:
            return TierDecision(
                tier=Tier.LOOKUP,
                reason="Source or target not in graph",
            )

        # 3. Check for direct edge
        existing = self.category.morphisms_from(claim.source)
        for mor in existing:
            if mor.target == claim.target and mor.name == claim.relation:
                return TierDecision(
                    tier=Tier.LOOKUP,
                    reason=f"Direct edge already exists (confidence={mor.confidence:.2f})",
                )

        # 4. Energy-based routing
        if energy < ENERGY_THRESHOLDS[Tier.LOOKUP]:
            return TierDecision(
                tier=Tier.LOOKUP,
                reason="Very low energy: graph strongly supports this claim",
            )
        elif energy < ENERGY_THRESHOLDS[Tier.COMPOSITION]:
            return TierDecision(
                tier=Tier.COMPOSITION,
                reason="Low energy: checking compositional paths",
            )
        elif energy < ENERGY_THRESHOLDS[Tier.SHEAF_KAN]:
            return TierDecision(
                tier=Tier.SHEAF_KAN,
                reason="Moderate energy: Kan extension + sheaf coherence needed",
            )
        elif energy < ENERGY_THRESHOLDS[Tier.DUAL_ENGINE]:
            return TierDecision(
                tier=Tier.DUAL_ENGINE,
                reason="High energy: dual engine verification needed",
            )
        else:
            return TierDecision(
                tier=Tier.FULL_TOPOLOGY,
                reason="Very high energy: full topological analysis required",
            )
