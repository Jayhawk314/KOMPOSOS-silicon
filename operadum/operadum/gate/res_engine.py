# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
RES Engine: Resource Soundness + Budget Feasibility

The other half of the Dual Gate. The RES engine answers two questions:

  1. Soundness: does combining the design's costs respect the resource
     discipline? For the linear algebra this means no one-shot resource is
     spent twice -- computing the cost itself raises if it is.
  2. Feasibility: is the (sound) cost within the spec's budget?

Together with the TYPE engine it assigns the WRIGHT verdict.
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Tuple

from ..core.operad import Operad
from ..core.enrichment import ResourceError, _meets_minimum
from ..core.linear import LinearChecker, LinearJudgement
from ..core.types import Composite, Spec


class ResEngine:
    """Resource-soundness and budget gate over the operad's monoid."""

    def __init__(self, operad: Operad, bang=()):
        self.operad = operad
        self.linear = LinearChecker(bang=bang)

    def prove_sound(self, comp: Composite) -> LinearJudgement:
        """
        Prove the design resource-sound (the master spec's S12 conservation
        claim, Phase-2 form): no non-`!` resource token is spent twice. Returns
        a LinearJudgement that either witnesses the linear sequent or names the
        contracted tokens.

        Linearity is read off the operad's monoid. A spend-once monoid
        (LINEAR_TOKENS) judges every token strictly; an accumulative monoid
        (additive/max/tropical) treats every resource as a !-resource, so its
        designs are linear-sound by construction.
        """
        if self.operad.monoid.linear:
            return self.linear.judge(comp)
        # Accumulative algebra: every resource key is freely reusable (banged).
        keys = set(self.linear.bang)
        for op in comp.operations():
            keys |= set(op.cost)
        return LinearChecker(bang=keys).judge(comp)

    def cost(self, comp: Composite) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Compute the composite's total cost under the operad's monoid.

        Returns (sound, cost, reason). `sound` is False (with cost=None) only
        when the resource algebra rejects the assembly -- e.g. a linear token
        reused. Otherwise cost is the combined resource value.
        """
        try:
            return True, comp.cost(self.operad.monoid), ""
        except ResourceError as exc:
            return False, None, str(exc)

    def feasible(self, comp: Composite, spec: Spec) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        True iff the design is resource-sound, within the spec's upper-bound
        budget, and meets any lower-bound requirements.

        With no budget, any sound design is feasible. The pointwise budget
        check is delegated to the monoid's `compare`.
        """
        sound, cost, reason = self.cost(comp)
        if not sound:
            return False, None, reason
        if spec.budget is None:
            within_budget = True
        else:
            within_budget = self.operad.monoid.compare(cost, spec.budget)
        if not within_budget:
            return False, cost, f"figures {cost} exceed budget {spec.budget}"
        if spec.requirements is not None and not _meets_minimum(cost, spec.requirements):
            return False, cost, f"figures {cost} do not meet requirements {spec.requirements}"
        return True, cost, ""
