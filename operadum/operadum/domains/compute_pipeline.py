# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Compute-Pipeline Design -- the second OPERADUM domain.

Its purpose is to demonstrate domain-agnosticism (master spec S18): the same
substrate that designed a chemical synthesis route now designs a data pipeline,
with a *different resource algebra*. Here the resource is MAX_CAPACITY -- peak
memory -- so "cheapest" means "lowest bottleneck", not "lowest total". The
math does not know which domain it is in.

This domain also exercises the honest limitation #7: under a peak (max) algebra
the cost -> confidence compile is lossy, so the KOMPOSOS round-trip returns
HOLLOW (structure preserved, resource homomorphism not exact) rather than
AGREE. The engine reports this correctly, and the accuracy harness scores it as
the *expected* behaviour.

  Colours    = pipeline stages (RawLog .. Report).
  Operations = transforms; cost = peak memory (MB) for that stage.
  Resource   = MAX_CAPACITY: a route's cost is its worst bottleneck stage.
"""

from __future__ import annotations
from typing import List

from ..core.types import Operation, Spec
from ..core.enrichment import ResourceMonoid, MAX_CAPACITY
from .base import DomainPlugin, GroundTruthCase


def _stage(name: str, inputs: List[str], output: str, mem: float) -> Operation:
    return Operation(
        name=name, inputs=list(inputs), output=output,
        cost={"mem": mem}, metadata={"stage": name},
        _fn=lambda *_x, _o=output: _o,
    )


class ComputePipelineDomain(DomainPlugin):
    """A log-analytics pipeline where designs are ranked by peak memory."""

    name = "compute-pipeline"

    def colours(self) -> List[str]:
        return ["RawLog", "Parsed", "Indexed", "Aggregated", "Report"]

    def operations(self) -> List[Operation]:
        return [
            _stage("parse",      ["RawLog"],     "Parsed",     mem=50),
            _stage("index_fast", ["Parsed"],     "Indexed",    mem=400),  # hungry
            _stage("index_slow", ["Parsed"],     "Indexed",    mem=120),  # lean
            _stage("aggregate",  ["Indexed"],    "Aggregated", mem=200),
            _stage("report",     ["Aggregated"], "Report",     mem=80),
        ]

    def resource_algebra(self) -> ResourceMonoid:
        return MAX_CAPACITY

    def ground_truth(self) -> List[GroundTruthCase]:
        return [
            GroundTruthCase(
                name="RawLog -> Report (min peak memory)",
                spec=Spec(inputs=("RawLog",), output="Report"),
                buildable=True, min_cost=200.0,   # max(50,120,200,80) via index_slow
                note="parse -> index_slow -> aggregate -> report; peak 200, not 400",
                expected_roundtrip="HOLLOW",       # peak algebra: lossy compile
            ),
            GroundTruthCase(
                name="RawLog -> Indexed (min peak)",
                spec=Spec(inputs=("RawLog",), output="Indexed"),
                buildable=True, min_cost=120.0,    # index_slow (120) beats index_fast (400)
                note="parse -> index_slow; peak 120",
                expected_roundtrip="HOLLOW",
            ),
            GroundTruthCase(
                name="Parsed -> Report",
                spec=Spec(inputs=("Parsed",), output="Report"),
                buildable=True, min_cost=200.0,
                note="index_slow -> aggregate -> report; peak 200",
                expected_roundtrip="HOLLOW",
            ),
            GroundTruthCase(
                name="Report -> RawLog (no route)",
                spec=Spec(inputs=("Report",), output="RawLog"),
                buildable=False, min_cost=None,
                note="pipelines run forward; RawLog is never produced",
                expected_roundtrip="HOLLOW",
            ),
        ]
