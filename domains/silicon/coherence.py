# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Cross-artifact calibration nerve with exact H0/H1 computation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from topology.persistent_sheaves import simplicial_cochain_complex


@dataclass
class CrossLayerCohomology:
    artifacts: List[str]
    pairwise_calibrations: List[Tuple[str, str]]
    joint_certificates: List[Tuple[str, str, str]]
    h0_dimension: int
    h1_dimension: int
    h1_support: List[List[str]]
    coverage_findings: Dict[str, List[str]]

    def to_dict(self) -> Dict[str, object]:
        return {
            "artifacts": self.artifacts,
            "pairwise_calibrations": self.pairwise_calibrations,
            "joint_certificates": self.joint_certificates,
            "h0_dimension": self.h0_dimension,
            "h1_dimension": self.h1_dimension,
            "h1_support": self.h1_support,
            "coverage_findings": self.coverage_findings,
        }


def analyze_calibration_nerve(
        artifacts: List[str], pairwise_calibrations: List[Tuple[str, str]],
        joint_certificates: List[Tuple[str, str, str]] = None,
        coverage_findings: Dict[str, List[str]] = None) -> CrossLayerCohomology:
    complex_ = simplicial_cochain_complex(
        artifacts, pairwise_calibrations, joint_certificates or [])
    result = complex_.cohomology()
    return CrossLayerCohomology(
        artifacts=sorted(dict.fromkeys(artifacts)),
        pairwise_calibrations=sorted({tuple(sorted(edge))
                                      for edge in pairwise_calibrations}),
        joint_certificates=sorted({tuple(sorted(face))
                                   for face in (joint_certificates or [])}),
        h0_dimension=result.h0_dimension,
        h1_dimension=result.h1_dimension,
        h1_support=result.h1_support,
        coverage_findings=coverage_findings or {},
    )


def analyze_crosswalk_cohomology(crosswalk, bridge) -> CrossLayerCohomology:
    """Build only calibrations justified by current Verilog/DEF/SPEF evidence."""
    artifacts = ["verilog", "def"]
    calibrations: List[Tuple[str, str]] = []
    if crosswalk.matches:
        calibrations.append(("verilog", "def"))

    matched_physical = {match.physical_net for match in crosswalk.matches}
    if matched_physical & set(bridge.caps):
        artifacts.append("spef")
        calibrations.append(("def", "spef"))

    # Verilog<->SPEF is derived through DEF, not an independent calibration, so no
    # third edge or filled triangle is invented here.
    coverage = {
        "logical_only": list(crosswalk.logical_only),
        "physical_only": list(crosswalk.physical_only),
        "missing_instances": list(crosswalk.missing_instances),
        "extra_instances": list(crosswalk.extra_instances),
        "cell_mismatches": [name for name, _, _ in crosswalk.cell_mismatches],
    }
    return analyze_calibration_nerve(
        artifacts, calibrations, coverage_findings=coverage)
