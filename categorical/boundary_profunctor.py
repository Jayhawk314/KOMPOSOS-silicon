# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Boundary Objects and Profunctors for Inter-Activity-System Mediation

When two activity systems interact (e.g., a DeFi protocol and a money
laundering operation), shared artifacts serve as boundary objects.
Category-theoretically, these are profunctors between activity system
categories.

Key concepts:
  - Boundary Object (Star & Griesemer, 1989): artifact shared between
    activity systems, plastic enough to serve both but maintaining
    common identity.
  - Profunctor B: Act1^op x Act2 -> Set: formal model of inter-system
    mediation through shared artifacts.
  - Plasticity: how differently two systems use the same object.
  - Robustness: how stable the shared identity remains.

Mathematical basis:
  - Star, S.L. & Griesemer, J.R. (1989). Institutional Ecology,
    'Translations' and Boundary Objects.
  - Benabou, J. (1973). Les distributeurs.
  - Fong & Spivak (2019). Seven Sketches in Compositionality, Ch. 4.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from .activity_system import (
    ActivityComponent,
    ActivitySystem,
    ClassifiedMorphism,
)


@dataclass
class BoundaryObject:
    """
    An artifact shared between two activity systems.

    A boundary object sits at the interface of two activity systems.
    It may play different roles in each system (high plasticity) while
    maintaining a recognizable shared identity (robustness).

    Example: A mixer pool is a TOOL for a ransomware cash-out system
    and a COMMUNITY for the mixer operator system.
    """
    name: str
    system_a_name: str
    system_b_name: str
    role_in_a: ActivityComponent
    role_in_b: ActivityComponent
    morphisms_in_a: List[str] = field(default_factory=list)
    morphisms_in_b: List[str] = field(default_factory=list)

    def plasticity(self) -> float:
        """
        How differently the two systems use this object.

        0.0 = identical role and usage pattern.
        1.0 = completely different role and usage.

        Computed from:
          - Role difference (different component type = 0.5 base)
          - Usage pattern difference (morphism count ratio asymmetry)
        """
        # Role component (0.5 if different types)
        role_score = 0.0 if self.role_in_a == self.role_in_b else 0.5

        # Usage pattern component (asymmetry in morphism counts)
        count_a = max(len(self.morphisms_in_a), 1)
        count_b = max(len(self.morphisms_in_b), 1)
        ratio = min(count_a, count_b) / max(count_a, count_b)
        usage_score = (1.0 - ratio) * 0.5  # Scale to [0, 0.5]

        return round(role_score + usage_score, 4)

    def robustness(self) -> float:
        """
        How stable the shared identity is.

        robustness = 1.0 - plasticity
        """
        return round(1.0 - self.plasticity(), 4)


@dataclass
class ProfunctorElement:
    """
    An element of the profunctor B: Act1^op x Act2 -> Set.

    Represents a mediation relationship between a component in
    system A and a component in system B, through boundary objects.
    """
    source_component: str    # Component in system A
    target_component: str    # Component in system B
    boundary_objects: List[str]   # Boundary objects mediating this relationship
    mediation_paths: List[List[str]] = field(default_factory=list)
    strength: float = 0.0    # How strongly mediated (0 to 1)


class BoundaryProfunctor:
    """
    Profunctor modeling mediation between two activity systems.

    B: Act_A^op x Act_B -> Set

    For components a in Act_A and b in Act_B, B(a, b) is the set
    of boundary objects through which a and b are related.
    The strength of mediation is computed from the number and
    robustness of shared boundary objects.
    """

    def __init__(
        self, system_a: ActivitySystem, system_b: ActivitySystem,
        boundary_objects: Optional[List[BoundaryObject]] = None
    ):
        self.system_a = system_a
        self.system_b = system_b
        self.boundary_objects = boundary_objects or []

    def compute(self) -> List[ProfunctorElement]:
        """
        Compute profunctor elements for all component pairs.

        For each (component_a, component_b) pair, finds which boundary
        objects mediate between them and computes mediation strength.

        Returns:
            List of ProfunctorElements with non-zero strength.
        """
        if not self.boundary_objects:
            return []

        elements = []

        for comp_a in self.system_a.components.values():
            for comp_b in self.system_b.components.values():
                # Find boundary objects that connect these components
                mediating = []
                for bo in self.boundary_objects:
                    # Check if bo connects comp_a's type in system_a
                    # to comp_b's type in system_b
                    a_connected = self._is_connected(
                        comp_a.name, bo.name, self.system_a
                    )
                    b_connected = self._is_connected(
                        bo.name, comp_b.name, self.system_b
                    ) or self._is_connected(
                        comp_b.name, bo.name, self.system_b
                    )

                    if a_connected and b_connected:
                        mediating.append(bo.name)

                if mediating:
                    # Strength = average robustness of mediating boundary objects
                    bo_map = {bo.name: bo for bo in self.boundary_objects}
                    robustness_values = [
                        bo_map[name].robustness()
                        for name in mediating if name in bo_map
                    ]
                    strength = (
                        sum(robustness_values) / len(robustness_values)
                        if robustness_values else 0.0
                    )

                    elements.append(ProfunctorElement(
                        source_component=comp_a.name,
                        target_component=comp_b.name,
                        boundary_objects=mediating,
                        strength=round(strength, 4)
                    ))

        return elements

    def composition_strength(self) -> float:
        """
        Overall coupling between the two systems.

        Computed as the mean strength across all profunctor elements,
        weighted by the fraction of component pairs that are connected.
        """
        elements = self.compute()
        if not elements:
            return 0.0

        total_pairs = (
            len(self.system_a.components) * len(self.system_b.components)
        )
        if total_pairs == 0:
            return 0.0

        coverage = len(elements) / total_pairs
        mean_strength = sum(e.strength for e in elements) / len(elements)

        return round(coverage * mean_strength, 4)

    def _is_connected(
        self, comp_name: str, other_name: str, system: ActivitySystem
    ) -> bool:
        """Check if two components are connected by any morphism in the system."""
        for mor in system.morphisms:
            if (mor.source == comp_name and mor.target == other_name) or \
               (mor.source == other_name and mor.target == comp_name):
                return True
        return False


class BoundaryObjectDetector:
    """
    Detect boundary objects between activity systems.

    A boundary object is a component that appears in multiple activity
    systems. Detection is based on name matching — components with
    the same name in different systems are potential boundary objects.
    """

    def detect(
        self, system_a: ActivitySystem, system_b: ActivitySystem
    ) -> List[BoundaryObject]:
        """
        Find boundary objects shared between two activity systems.

        Args:
            system_a: First activity system.
            system_b: Second activity system.

        Returns:
            List of BoundaryObjects found at the interface.
        """
        shared_names = self._find_shared_names(system_a, system_b)
        boundary_objects = []

        for name in shared_names:
            comp_a = system_a.components[name]
            comp_b = system_b.components[name]

            # Collect morphisms involving this component in each system
            morphisms_a = [
                f"{m.source}->{m.target}"
                for m in system_a.morphisms
                if m.source == name or m.target == name
            ]
            morphisms_b = [
                f"{m.source}->{m.target}"
                for m in system_b.morphisms
                if m.source == name or m.target == name
            ]

            boundary_objects.append(BoundaryObject(
                name=name,
                system_a_name=system_a.name,
                system_b_name=system_b.name,
                role_in_a=comp_a.component_type,
                role_in_b=comp_b.component_type,
                morphisms_in_a=morphisms_a,
                morphisms_in_b=morphisms_b
            ))

        return boundary_objects

    def detect_across_many(
        self, systems: List[ActivitySystem]
    ) -> List[BoundaryObject]:
        """
        Find boundary objects across multiple activity systems.

        Checks all pairs of systems.

        Args:
            systems: List of activity systems to compare.

        Returns:
            List of all BoundaryObjects found. A single component
            may appear as multiple BoundaryObjects if shared across
            more than two systems.
        """
        all_boundary_objects = []
        seen_pairs: Set[Tuple[str, str, str]] = set()

        for i, sys_a in enumerate(systems):
            for sys_b in systems[i + 1:]:
                for bo in self.detect(sys_a, sys_b):
                    pair_key = (bo.name, bo.system_a_name, bo.system_b_name)
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        all_boundary_objects.append(bo)

        return all_boundary_objects

    def _find_shared_names(
        self, system_a: ActivitySystem, system_b: ActivitySystem
    ) -> Set[str]:
        """Find component names that appear in both systems."""
        return set(system_a.components.keys()) & set(system_b.components.keys())
