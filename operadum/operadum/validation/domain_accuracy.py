# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Domain Synthesis Accuracy

The first measurement of *real-world* design accuracy: run a domain plugin's
ground-truth cases through OPERADUM and score three things against the known
answers, with KOMPOSOS auditing each design:

  - buildable_accuracy: did WRIGHT correctly call each spec buildable / not?
  - optimum_recall:      for buildable specs, did optimize() find the known
                         cost-minimal route?
  - roundtrip_agree:     fraction of synthesized designs KOMPOSOS verifies
                         (structure preserved + resource homomorphism holds).

This is the dual of KOMPOSOS's calibration: instead of "how often is the
interpretation correct?" we ask "how often is the design correct, optimal, and
auditable?"
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

from ..domains.base import DomainPlugin
from ..wright.engine import Wright
from ..wright.schema import Verdict
from ..bridges.round_trip import KomposVerifier


@dataclass
class CaseScore:
    name: str
    expected_buildable: bool
    got_buildable: bool
    expected_cost: Optional[float]
    got_cost: Optional[float]
    optimal: bool
    roundtrip: str           # AGREE / HOLLOW / REJECT / n/a
    expected_roundtrip: str = "AGREE"
    route: str = ""

    @property
    def buildable_correct(self) -> bool:
        return self.expected_buildable == self.got_buildable

    @property
    def roundtrip_correct(self) -> bool:
        return self.roundtrip == self.expected_roundtrip


@dataclass
class DomainScore:
    domain: str
    cases: List[CaseScore] = field(default_factory=list)

    @property
    def buildable_accuracy(self) -> float:
        return _frac([c.buildable_correct for c in self.cases])

    @property
    def optimum_recall(self) -> float:
        relevant = [c for c in self.cases if c.expected_buildable]
        return _frac([c.optimal for c in relevant]) if relevant else 1.0

    @property
    def roundtrip_agree(self) -> float:
        """Fraction of built designs KOMPOSOS verifies AGREE (sound homomorphism)."""
        relevant = [c for c in self.cases if c.got_buildable]
        return _frac([c.roundtrip == "AGREE" for c in relevant]) if relevant else 1.0

    @property
    def roundtrip_accuracy(self) -> float:
        """Fraction of built designs whose round-trip matches the domain's
        expectation (AGREE for additive, HOLLOW for peak algebras)."""
        relevant = [c for c in self.cases if c.got_buildable]
        return _frac([c.roundtrip_correct for c in relevant]) if relevant else 1.0

    def __str__(self) -> str:
        return (f"DomainScore({self.domain}: "
                f"buildable_accuracy={self.buildable_accuracy:.3f}, "
                f"optimum_recall={self.optimum_recall:.3f}, "
                f"roundtrip_accuracy={self.roundtrip_accuracy:.3f})")


def _frac(bools: List[bool]) -> float:
    return sum(1 for b in bools if b) / len(bools) if bools else 0.0


def measure_domain_accuracy(domain: DomainPlugin,
                            komposos_path: Optional[str] = None,
                            max_depth: int = 8) -> DomainScore:
    """Run a domain's ground-truth cases through synthesis + the round-trip."""
    operad = domain.build_operad()
    wright = Wright(operad, max_depth=max_depth)
    verifier = KomposVerifier(komposos_path=komposos_path)
    score = DomainScore(domain=domain.name)

    for case in domain.ground_truth():
        build = wright.optimize(case.spec)
        got_buildable = build.buildable
        got_cost = operad.monoid.rank(build.construction.cost) if got_buildable else None

        optimal = False
        roundtrip = "n/a"
        route = ""
        if got_buildable:
            route = build.construction.wiring
            if case.min_cost is not None:
                optimal = abs((got_cost or 0.0) - case.min_cost) < 1e-9
            roundtrip = verifier.verify(build.construction.composite, operad).verdict
        elif not case.buildable:
            optimal = True  # correctly recognised as unbuildable

        score.cases.append(CaseScore(
            name=case.name,
            expected_buildable=case.buildable,
            got_buildable=got_buildable,
            expected_cost=case.min_cost,
            got_cost=got_cost,
            optimal=optimal,
            roundtrip=roundtrip,
            expected_roundtrip=case.expected_roundtrip,
            route=route,
        ))
    return score


if __name__ == "__main__":
    from ..domains.synthesis_design import SynthesisDesignDomain
    result = measure_domain_accuracy(SynthesisDesignDomain())
    print(result)
    for c in result.cases:
        tag = "ok" if c.buildable_correct and c.optimal else "MISS"
        print(f"  [{tag}] {c.name}: buildable={c.got_buildable} cost={c.got_cost} "
              f"roundtrip={c.roundtrip}")
        if c.route:
            print(f"         route: {c.route}")
