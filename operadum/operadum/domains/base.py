# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Domain Plugin Base

Master spec S18: "How to Add a Domain -- One Line." A domain plugin brings
*content*, not infrastructure:

    colours()          -> list[str]            # interface types in this domain
    operations()       -> list[Operation]      # components: inputs/output/cost/fn
    resource_algebra() -> ResourceMonoid       # how this domain's costs combine

The substrate (Operad / WRIGHT / DAEDALUS / Polytope) does the synthesis; the
domain only declares what composes with what and what it costs. Every strategy
then works on every domain -- the math does not know which domain it is in.

`ground_truth()` is OPERADUM-specific: known (spec -> expected) cases used by
the accuracy harness to measure real-world synthesis accuracy on the domain.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..core.operad import Operad
from ..core.types import Operation, Spec
from ..core.enrichment import ResourceMonoid, ADDITIVE_COST


@dataclass
class GroundTruthCase:
    """A labelled synthesis problem with its known answer.

    Fields:
        name: Human label.
        spec: The synthesis target.
        buildable: Whether a valid design exists at all.
        min_cost: The known cost-minimal scalar (sum of cost components), if any.
        note: Free text (e.g. the expected route).
    """
    name: str
    spec: Spec
    buildable: bool
    min_cost: Optional[float] = None
    note: str = ""
    # The round-trip verdict KOMPOSOS should return. "AGREE" for additive-style
    # (sum) algebras where the cost->confidence map is an exact homomorphism;
    # "HOLLOW" for peak/bottleneck algebras where it is lossy (spec limit #7).
    expected_roundtrip: str = "AGREE"


class DomainPlugin(ABC):
    """A domain's content, loadable into an Operad in one call."""

    #: Short identifier for the domain.
    name: str = "domain"

    @abstractmethod
    def colours(self) -> List[str]:
        """The interface types (ports) this domain exposes."""

    @abstractmethod
    def operations(self) -> List[Operation]:
        """The components: typed, costed, executable build rules."""

    def resource_algebra(self) -> ResourceMonoid:
        """How this domain's costs combine. Default: additive cost."""
        return ADDITIVE_COST

    def ground_truth(self) -> List[GroundTruthCase]:
        """Known (spec -> expected) cases for the accuracy harness. Default: none."""
        return []

    # ---------------- loading ----------------

    def load_into(self, operad: Operad) -> Operad:
        """Register this domain's colours and operations into an operad."""
        for c in self.colours():
            if operad.get_colour(c) is None:
                operad.add_colour(c)
        for op in self.operations():
            operad.add_operation(op)
        return operad

    def build_operad(self, db_path: str = ":memory:") -> Operad:
        """Create a fresh operad over this domain's resource algebra and load it."""
        operad = Operad(self.name, db_path=db_path, monoid=self.resource_algebra())
        return self.load_into(operad)
