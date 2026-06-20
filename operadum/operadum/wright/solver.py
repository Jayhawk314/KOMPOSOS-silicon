# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
WRIGHT Tier-3 Solver: Resource-Constrained Synthesis

The master spec names this the ILP/SMT bridge. Rather than take a hard
dependency on an external solver for Phase 2, OPERADUM ships a self-contained
branch-and-bound resource solver (DAEDALUS) that returns the best-ranked
in-budget design directly. The interface is deliberately solver-shaped so an
ILP/SMT backend can be slotted in later without touching WRIGHT.

  Tier 0-2 (engine.py): find *a* construction, ranked within a tier.
  Tier 3   (here):      find *the* best-ranked in-budget construction, globally,
                        proven resource-sound.
"""

from __future__ import annotations
from typing import Optional

from ..core.operad import Operad
from ..core.types import Spec
from ..daedalus_core import Daedalus, SearchResult


class Solver:
    """Resource-constrained best-ranked-design solver backed by DAEDALUS."""

    def __init__(self, operad: Operad, max_depth: int = 6):
        self.operad = operad
        self.daedalus = Daedalus(operad, max_depth=max_depth)

    def cheapest(self, spec: Spec) -> SearchResult:
        """The best-ranked in-budget, resource-sound design (and the
        best-ranked overall, for OVERBUDGET reporting)."""
        return self.daedalus.search(spec)
