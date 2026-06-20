# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
WRIGHT Schema: Spec, Construction, Verdict, BuildResult

The dual of KOMPOSOS-IV's COG schema. COG takes a claim and returns a
verdict (AGREE / ORPHAN / HOLLOW / REJECT). WRIGHT takes a Spec and returns
a BuildResult whose verdict is the constructive dual:

    KOMPOSOS COG          OPERADUM WRIGHT
    ------------          ---------------
    AGREE                 BUILDABLE       (type-realizable AND in-budget)
    HOLLOW (no support)   ILL_TYPED_GAP   (resources ok, no typed wiring)
    ORPHAN (over budget)  OVERBUDGET      (typed wiring exists, too costly)
    REJECT                IMPOSSIBLE      (neither type nor resources)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional

from ..core.types import Composite, Spec, Interface

# Re-export Spec so callers can `from operadum.wright import Spec`.
__all__ = ["Spec", "Verdict", "Construction", "Certificate", "BuildResult"]


class Verdict(str, Enum):
    """The four WRIGHT verdicts -- dual of COG's AGREE/HOLLOW/ORPHAN/REJECT."""
    BUILDABLE = "BUILDABLE"           # type-realizable AND in budget. Ship it.
    OVERBUDGET = "OVERBUDGET"         # wiring exists but exceeds the budget.
    ILL_TYPED_GAP = "ILL_TYPED_GAP"   # resources suffice, no type-correct wiring.
    IMPOSSIBLE = "IMPOSSIBLE"         # no realizer under current components.


@dataclass
class Construction:
    """
    A successful design: a typed composite plus its executable artifact.

    The dual of a KOMPOSOS proof object. A proof witnesses "this is true";
    a Construction witnesses "this is buildable" -- and you can actually run
    it (Curry-Howard: the design that type-checks IS a program).
    """
    composite: Composite
    cost: Dict[str, Any]
    tier: int
    artifact: Optional[Callable] = field(default=None, repr=False)

    @property
    def interface(self) -> Interface:
        return self.composite.interface

    @property
    def wiring(self) -> str:
        return self.composite.to_wiring()


@dataclass
class Certificate:
    """
    A Tier-4 certified construction: the design in coherence normal form, plus
    proofs that it is unique up to coherence, resource-conserving, and linear-
    sound. The constructive dual of a KOMPOSOS Tier-2+ verified verdict.
    """
    construction: Construction
    normal_form: "Composite"
    unique: bool                       # unique up to coherence (normal form)
    conservation: Any = None           # formal_coherence.Proof
    linear: Any = None                 # core.linear.LinearJudgement
    coherence: Any = None              # formal_coherence.Proof (optional)

    @property
    def certified(self) -> bool:
        ok = self.unique
        if self.conservation is not None:
            ok = ok and self.conservation.holds
        if self.linear is not None:
            ok = ok and self.linear.ok
        if self.coherence is not None:
            ok = ok and self.coherence.holds
        return ok

    def __str__(self) -> str:
        mark = "CERTIFIED" if self.certified else "UNCERTIFIED"
        return f"[{mark}] {self.normal_form.to_wiring()} (unique up to coherence)"


@dataclass
class BuildResult:
    """
    The outcome of WRIGHT.synthesize(spec).

    Fields:
        verdict: One of the four Verdicts.
        spec: The spec that was requested.
        construction: The design, if one was found (BUILDABLE / OVERBUDGET).
        tier: Which synthesis tier produced the result (-1 if none).
        reason: Human-readable explanation, especially for gaps/impossibilities.
    """
    verdict: Verdict
    spec: Spec
    construction: Optional[Construction] = None
    tier: int = -1
    reason: str = ""

    @property
    def buildable(self) -> bool:
        return self.verdict == Verdict.BUILDABLE

    def __str__(self) -> str:
        head = f"[{self.verdict.value}] {self.spec.interface}"
        if self.construction is not None:
            return (f"{head}  tier={self.tier}  cost={self.construction.cost}\n"
                    f"  {self.construction.wiring}")
        return f"{head}  ({self.reason})"
