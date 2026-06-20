# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Typed Orion Capabilities — mathematical structure requirements for plugins.

Instead of string-based capability declarations (provides={"knowledge_store"}),
plugins declare what mathematical structure they need and what they provide.
The system can then verify composability at the type level.

Usage:
    class MyPlugin(Plugin):
        requires = [
            MathRequirement(
                structure="Category",
                quantale="multiplicative",
                min_confidence=0.5,
                two_cell_support=True,
            ),
        ]
        provides = [
            MathCapability(
                name="structural_verification",
                structure="TwoCellBridge",
                operations=["verify_claim", "check_interchange"],
            ),
        ]

The system can then check:
- Does this plugin's Category have the right quantale?
- Does it support 2-cell reasoning?
- Can it compose with other plugins mathematically?
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set


class QuantaleType(Enum):
    """Supported quantale types for enriched categories."""
    MULTIPLICATIVE = "multiplicative"     # [0,1], *, 1
    ADDITIVE = "additive"                  # [0,∞], +, 0
    MIN = "min"                            # [0,1], min, 1
    MAX = "max"                            # [0,∞], max, 0
    PROBABILISTIC = "probabilistic"        # [0,1], P-or, 0


class MathStructure(Enum):
    """Mathematical structures that plugins can require or provide."""
    CATEGORY = "Category"
    ENRICHED_CATEGORY = "EnrichedCategory"
    TWO_CELL_BRIDGE = "TwoCellBridge"
    INFINITY_COSMOS = "InfinityCosmos"
    OPTIMUS = "OptimusEngine"
    DUAL_ENGINE = "DualEngineBridge"
    SYSTEM3 = "System3Oracle"
    CAPABILITY_GRAPH = "CapabilityGraphBuilder"
    LINEAR_INDEPENDENCE = "LinearIndependenceTest"
    ARCHITECTURAL_ADVISOR = "ArchitecturalAdvisor"


@dataclass
class MathRequirement:
    """
    A mathematical structure requirement for a plugin.

    E.g., "I need a Category with multiplicative quantale and 2-cell support."
    """
    structure: MathStructure
    quantale: Optional[QuantaleType] = None
    min_objects: int = 0
    min_morphisms: int = 0
    two_cell_support: bool = False
    fibration_support: bool = False
    yoneda_support: bool = False
    description: str = ""

    def __repr__(self):
        parts = [self.structure.value]
        if self.quantale:
            parts.append(f"quantale={self.quantale.value}")
        if self.two_cell_support:
            parts.append("2-cells")
        if self.fibration_support:
            parts.append("fibrations")
        return f"MathRequirement({', '.join(parts)})"


@dataclass
class MathCapability:
    """
    A mathematical capability that a plugin provides.

    E.g., "I provide structural verification via TwoCellBridge."
    """
    name: str
    structure: MathStructure
    operations: List[str] = field(default_factory=list)
    quantale: Optional[QuantaleType] = None
    description: str = ""

    def __repr__(self):
        return f"MathCapability({self.name}: {self.structure.value})"


class MathCompatibilityChecker:
    """
    Checks whether two plugins are mathematically compatible.

    A plugin's requirements must be satisfiable by another plugin's capabilities.
    The Category's structure must match the plugin's requirements.
    """

    def __init__(self, category=None):
        """
        Args:
            category: The Category to check against plugin requirements.
        """
        self.category = category

    def check_compatibility(
        self,
        requirements: List[MathRequirement],
        capabilities: List[MathCapability],
    ) -> Dict[str, Any]:
        """
        Check if a set of requirements is satisfiable by a set of capabilities.

        Args:
            requirements: What the consumer needs.
            capabilities: What the providers offer.

        Returns:
            Dict with "compatible", "missing", "satisfied" fields.
        """
        missing = []
        satisfied = []

        cap_structures = {cap.structure for cap in capabilities}

        for req in requirements:
            if req.structure in cap_structures:
                # Check additional constraints
                cap = next(c for c in capabilities if c.structure == req.structure)

                if req.quantale and cap.quantale and req.quantale != cap.quantale:
                    missing.append({
                        "requirement": req,
                        "reason": f"Quantale mismatch: need {req.quantale.value}, "
                                  f"have {cap.quantale.value}",
                    })
                else:
                    satisfied.append({"requirement": req, "capability": cap})
            else:
                missing.append({
                    "requirement": req,
                    "reason": f"No provider for {req.structure.value}",
                })

        return {
            "compatible": len(missing) == 0,
            "missing": missing,
            "satisfied": satisfied,
            "requirements_count": len(requirements),
            "capabilities_count": len(capabilities),
        }

    def check_category_satisfies(
        self, requirements: List[MathRequirement]
    ) -> Dict[str, Any]:
        """
        Check if the Category satisfies a plugin's requirements.

        Args:
            requirements: What the plugin needs from the Category.

        Returns:
            Dict with "satisfied", "missing", "details" fields.
        """
        if self.category is None:
            return {
                "satisfied": False,
                "missing": [
                    {"requirement": req, "reason": "No Category available"}
                    for req in requirements
                ],
                "details": {},
            }

        missing = []
        details = {}

        for req in requirements:
            ok, detail = self._check_requirement(req)
            details[req.structure.value] = detail
            if not ok:
                missing.append({"requirement": req, "detail": detail})

        return {
            "satisfied": len(missing) == 0,
            "missing": missing,
            "details": details,
        }

    def _check_requirement(self, req: MathRequirement) -> tuple:
        """Check a single requirement against the Category."""
        cat = self.category
        details = {}

        if req.structure == MathStructure.CATEGORY:
            # Check object/morphism counts
            obj_count = len(cat.objects())
            mor_count = len(cat.morphisms())
            details["objects"] = obj_count
            details["morphisms"] = mor_count

            if obj_count < req.min_objects:
                return False, {**details, "error": f"Need {req.min_objects} objects, have {obj_count}"}
            if mor_count < req.min_morphisms:
                return False, {**details, "error": f"Need {req.min_morphisms} morphisms, have {mor_count}"}

            # Check quantale
            if req.quantale:
                q_name = cat.quantale.name if hasattr(cat.quantale, 'name') else ""
                details["quantale"] = q_name
                if req.quantale.value not in q_name.lower():
                    return False, {**details, "error": f"Need quantale {req.quantale.value}, have {q_name}"}

            # Check 2-cell support
            if req.two_cell_support:
                try:
                    from core.cosmos import InfinityCosmos
                    cosmos = InfinityCosmos(cat)
                    h2k = cosmos.homotopy_2_category()
                    details["two_cells"] = len(h2k.two_cells)
                except Exception as e:
                    return False, {**details, "error": f"2-cell support unavailable: {e}"}

            # Check fibration support
            if req.fibration_support:
                try:
                    from core.cosmos import InfinityCosmos
                    cosmos = InfinityCosmos(cat)
                    fibrations = cosmos.cartesian_fibrations()
                    details["fibrations"] = len(fibrations)
                except Exception as e:
                    return False, {**details, "error": f"Fibration support unavailable: {e}"}

            # Check Yoneda support
            if req.yoneda_support:
                try:
                    from core.cosmos import InfinityCosmos
                    cosmos = InfinityCosmos(cat)
                    yoneda = cosmos.yoneda_embedding()
                    details["yoneda_faithful"] = yoneda.is_fully_faithful
                except Exception as e:
                    return False, {**details, "error": f"Yoneda support unavailable: {e}"}

            return True, details

        return False, {"error": f"Unsupported structure: {req.structure.value}"}


class TypedPluginMixin:
    """
    Mixin for plugins that declare mathematical requirements and capabilities.

    Usage:
        class MyPlugin(TypedPluginMixin, Plugin):
            math_requires = [
                MathRequirement(MathStructure.CATEGORY, quantale=QuantaleType.MULTIPLICATIVE),
            ]
            math_provides = [
                MathCapability("structural_verification", MathStructure.TWO_CELL_BRIDGE),
            ]
    """
    math_requires: List[MathRequirement] = []
    math_provides: List[MathCapability] = []

    def get_math_requirements(self) -> List[MathRequirement]:
        """Get the mathematical structures this plugin needs."""
        return self.math_requires

    def get_math_capabilities(self) -> List[MathCapability]:
        """Get the mathematical structures this plugin provides."""
        return self.math_provides

    def check_math_compatibility(
        self, checker: MathCompatibilityChecker
    ) -> Dict[str, Any]:
        """
        Check if this plugin's mathematical requirements are satisfied.

        Args:
            checker: MathCompatibilityChecker with the target Category.

        Returns:
            Compatibility check result.
        """
        reqs = self.get_math_requirements()
        return checker.check_category_satisfies(reqs)
