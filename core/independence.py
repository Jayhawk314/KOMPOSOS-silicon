# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Linear Independence Test (Ruliad Engine)

Automatically tests whether a new capability is truly primitive or
just a composition of existing ones.

From the Ruliad essay:
    Can this be expressed as a composition of existing capabilities?
    Yes -> it's a pattern (document it, don't add it as a primitive)
    No  -> it's a new primitive (add it to the basis)

Usage:
    test = LinearIndependenceTest(capability_graph)
    result = test.is_independent("search", "store", max_path_length=4)
    print(result["recommendation"])
    # "NEW PRIMITIVE: No existing composition reaches this. Add it."
    # or
    # "PATTERN: Already reachable via search->index->store (confidence 0.72)"
"""

from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .category import Category


class LinearIndependenceTest:
    """
    Test whether a capability is a genuine primitive or a derived pattern.

    This operates on the capability graph (Category of plugins/capabilities)
    to determine if a proposed capability adds genuine new structure or
    just replicates existing paths.
    """

    def __init__(self, capability_graph: "Category"):
        """
        Args:
            capability_graph: Category representing the system's capabilities.
        """
        self.graph = capability_graph

    def is_independent(
        self,
        new_cap_source: str,
        new_cap_target: str,
        max_path_length: int = 4,
    ) -> Dict[str, Any]:
        """
        Test if a proposed capability is linearly independent.

        Args:
            new_cap_source: What the capability takes as input.
            new_cap_target: What the capability produces as output.
            max_path_length: Max composition length to search.

        Returns:
            Dict with keys:
                - independent: bool
                - existing_paths: List of existing composition paths
                - recommendation: Human-readable recommendation
        """
        paths = self.graph.find_paths(
            new_cap_source, new_cap_target, max_length=max_path_length
        )

        if not paths:
            return {
                "independent": True,
                "existing_paths": [],
                "recommendation": (
                    f"NEW PRIMITIVE: No existing composition reaches "
                    f"{new_cap_source} -> {new_cap_target}. "
                    f"Add it as a new capability."
                )
            }

        best_path = max(paths, key=lambda p: p.weight)

        if best_path.weight > 0.8:
            return {
                "independent": False,
                "existing_paths": [
                    {
                        "morphisms": p.morphism_ids,
                        "weight": p.weight,
                        "length": p.length,
                    }
                    for p in sorted(paths, key=lambda p: -p.weight)
                ],
                "recommendation": (
                    f"PATTERN: Already reachable via "
                    f"{' -> '.join(best_path.morphism_ids)} "
                    f"(confidence {best_path.weight:.2f}). "
                    f"Document as named pattern, don't add as primitive."
                )
            }

        return {
            "independent": True,
            "existing_paths": [
                {
                    "morphisms": p.morphism_ids,
                    "weight": p.weight,
                    "length": p.length,
                }
                for p in sorted(paths, key=lambda p: -p.weight)
            ],
            "recommendation": (
                f"WEAK COVERAGE: Existing paths are low-confidence "
                f"(best={best_path.weight:.2f}). "
                f"New primitive would strengthen the basis."
            )
        }

    def basis_analysis(self, objects: List[str] = None) -> Dict[str, Any]:
        """
        Analyze the capability basis: which capabilities are primitive vs derived.

        Args:
            objects: List of object names to analyze. Defaults to all objects.

        Returns:
            Dict with:
                - primitives: List of capabilities with no incoming composition
                - derived: List of capabilities reachable via composition
                - weak_coverage: List with low-confidence paths only
                - analysis: Summary statistics
        """
        if objects is None:
            objects = [obj.name for obj in self.graph.objects()]

        primitives = []
        derived = []
        weak_coverage = []

        for i, src in enumerate(objects):
            for tgt in objects[i + 1:]:
                result = self.is_independent(src, tgt)
                if result["independent"]:
                    if result["existing_paths"]:
                        weak_coverage.append({
                            "source": src,
                            "target": tgt,
                            "best_weight": result["existing_paths"][0]["weight"],
                        })
                    else:
                        primitives.append({
                            "source": src,
                            "target": tgt,
                        })
                else:
                    derived.append({
                        "source": src,
                        "target": tgt,
                        "via": result["existing_paths"][0]["morphisms"],
                        "confidence": result["existing_paths"][0]["weight"],
                    })

        return {
            "primitives": primitives,
            "derived": derived,
            "weak_coverage": weak_coverage,
            "analysis": {
                "total_pairs": len(primitives) + len(derived) + len(weak_coverage),
                "primitive_count": len(primitives),
                "derived_count": len(derived),
                "weak_count": len(weak_coverage),
                "primitive_ratio": (
                    len(primitives) / max(
                        len(primitives) + len(derived) + len(weak_coverage), 1
                    )
                ),
            }
        }
