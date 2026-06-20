# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-IV Commercial License (see LICENSE-COMMERCIAL file)

"""
COG Energy — Quantifies how much the knowledge graph resists a claim.

Low energy = claim fits naturally into existing graph.
High energy = claim is surprising, contradictory, or unsupported.

Five components:
  1. NOVELTY      (0.15) — Are source/target known?
  2. PATH_RESISTANCE (0.30) — How far apart in the graph?
  3. CONTRADICTION (0.35) — Does this conflict with existing knowledge?
  4. CONFIDENCE_GAP (0.10) — Differs from existing confidence?
  5. TYPE_MISMATCH  (0.10) — Valid relation for these types?
"""

from __future__ import annotations

from typing import Dict

from core.category import Category

from .schema import CogClaim, EnergyResult


# Antonym relation pairs — if one exists, the other is a contradiction
ANTONYM_RELATIONS: Dict[str, str] = {
    "supports": "contradicts",
    "contradicts": "supports",
    "causes": "prevents",
    "prevents": "causes",
    "entails": "refutes",
    "refutes": "entails",
    "precedes": "follows",
    "follows": "precedes",
    # Security-specific
    "trusts": "distrusts",
    "distrusts": "trusts",
    "mitigates": "exposes",
    "exposes": "mitigates",
    "sanitizes": "bypasses",
    "bypasses": "sanitizes",
    "guards": "circumvents",
    "circumvents": "guards",
    # Supply chain
    "depends_on": "independent_of",
    "independent_of": "depends_on",
}

# Relations that make no sense for certain type combinations
INVALID_TYPE_RELATIONS = {
    ("data_source", "sink", "trusts"),        # sources should NOT trust sinks
    ("sink", "data_source", "guards"),         # sinks don't guard sources
    ("sanitizer", "data_source", "flows_to"),  # sanitizers don't flow TO sources
    ("trust_boundary", "trust_boundary", "flows_to"),  # boundaries don't flow to each other
    ("auth_check", "data_source", "exposes"),  # auth checks don't expose sources
}

# Component weights (sum to 1.0)
WEIGHTS: Dict[str, float] = {
    "novelty": 0.15,
    "path_resistance": 0.30,
    "contradiction": 0.35,
    "confidence_gap": 0.10,
    "type_mismatch": 0.10,
}


class EnergyComputer:
    """Compute the energy (resistance) of a claim relative to the knowledge graph."""

    def __init__(self, category: Category):
        self.category = category

    def compute(self, claim: CogClaim) -> EnergyResult:
        """Compute total energy of a claim."""
        components: Dict[str, float] = {}

        source_obj = self.category.get(claim.source)
        target_obj = self.category.get(claim.target)
        source_exists = source_obj is not None
        target_exists = target_obj is not None

        # 1. Novelty
        novelty = 0.0
        if not source_exists:
            novelty += 0.5
        if not target_exists:
            novelty += 0.5
        components["novelty"] = novelty

        # 2. Path resistance
        if source_exists and target_exists:
            paths = self.category.find_paths(source_obj, target_obj, max_length=5)
            if paths:
                shortest = min(len(p) for p in paths)
                components["path_resistance"] = min(1.0, (shortest - 1) * 0.25)
            else:
                components["path_resistance"] = 1.0
        else:
            components["path_resistance"] = 1.0

        # 3. Contradiction
        components["contradiction"] = self._check_contradiction(claim)

        # 4. Confidence gap
        components["confidence_gap"] = self._check_confidence_gap(claim)

        # 5. Type mismatch
        components["type_mismatch"] = self._check_type_mismatch(claim)

        total = sum(WEIGHTS[k] * v for k, v in components.items())

        return EnergyResult(
            total_energy=round(total, 4),
            components={k: round(v, 4) for k, v in components.items()},
            interpretation=_interpret(total, components),
        )

    def _check_contradiction(self, claim: CogClaim) -> float:
        """Check if existing morphisms contradict this claim."""
        existing = self.category.morphisms_from(claim.source)
        antonym = ANTONYM_RELATIONS.get(claim.relation)

        for mor in existing:
            if mor.target == claim.target:
                if antonym and mor.name == antonym:
                    return 1.0
                if mor.name == claim.relation:
                    return 0.0

        reverse = self.category.morphisms_from(claim.target)
        for mor in reverse:
            if mor.target == claim.source:
                if antonym and mor.name == antonym:
                    return 0.8
        return 0.0

    def _check_confidence_gap(self, claim: CogClaim) -> float:
        """Check confidence difference from existing evidence."""
        existing = self.category.morphisms_from(claim.source)
        for mor in existing:
            if mor.target == claim.target and mor.name == claim.relation:
                return abs(mor.confidence - claim.confidence)
        return 0.0

    def _check_type_mismatch(self, claim: CogClaim) -> float:
        """Check if relation type is valid for these object types."""
        source_obj = self.category.get(claim.source)
        target_obj = self.category.get(claim.target)
        if source_obj and target_obj:
            key = (source_obj.type_name, target_obj.type_name, claim.relation)
            if key in INVALID_TYPE_RELATIONS:
                return 1.0
        return 0.0


def _interpret(total: float, components: Dict[str, float]) -> str:
    """Generate human-readable interpretation."""
    if total < 0.1:
        return "Very low energy: claim fits naturally into existing graph"
    elif total < 0.3:
        return "Low energy: claim is consistent with existing knowledge"
    elif total < 0.5:
        return "Moderate energy: claim extends existing knowledge"
    elif total < 0.7:
        return "High energy: claim requires significant graph extension"
    else:
        highest = max(components, key=components.get)
        return f"Very high energy: claim faces resistance, primarily from {highest}"
