# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Higher-Order OPTIMUS — factorization at all categorical levels.

Extends the standard OPTIMUS engine (which factorizes 1-morphisms) to:
  Level 2: 2-morphism factorization (vertical and horizontal)
  Level 3: Fibration factorization
  Level 4: Functor factorization

This is the full Ruliad vision: OPTIMUS operates on the complete
∞-cosmos, not just 1-morphisms.

Usage:
    engine = HigherOrderOptimus(runtime_category, two_category)
    # Level 1: Standard 1-morphism factorization (existing)
    result = engine.refine_morphism("Python", "ML")

    # Level 2: 2-morphism factorization (NEW)
    result = engine.refine_two_cell("α:f=>g")

    # Level 3: Fibration factorization (NEW)
    result = engine.refine_fibration("search_fibration")

    # Level 4: Functor factorization (NEW)
    result = engine.refine_functor("F: Code -> Deploy")
"""

from __future__ import annotations

import time
import sys
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# Add project root to path for optimus_core import
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from optimus_core import (
    Quantale, EnrichedMorphism, RuntimeCategory,
    OptimisMonad, Rewrite,
)


@dataclass
class HigherOrderRewrite(Rewrite):
    """
    A rewrite event at any categorical level.

    Extends the standard Rewrite with level information.
    level=1: 1-morphism factorization (standard OPTIMUS)
    level=2: 2-morphism factorization (vertical/horizontal composition)
    level=3: Fibration factorization
    level=4: Functor factorization
    """
    level: int = 1
    two_cell_name: Optional[str] = None
    fibration_name: Optional[str] = None
    functor_name: Optional[str] = None


class HigherOrderOptimus(OptimisMonad):
    """
    Extended Optimus monad that operates at all categorical levels.

    Inherits standard 1-morphism factorization from OptimisMonad.
    Adds:
    - 2-morphism factorization (via TwoCategory)
    - Fibration factorization (via GenericFibration)
    - Functor factorization (via Functor mapping)
    """

    def __init__(
        self,
        runtime: RuntimeCategory,
        max_depth: int = 3,
        two_category=None,
    ):
        """
        Args:
            runtime: The RuntimeCategory for 1-morphism operations.
            max_depth: Maximum factorization depth for 1-morphisms.
            two_category: Optional TwoCategory for 2-morphism reasoning.
        """
        super().__init__(runtime, max_depth)
        self.two_category = two_category
        self._higher_rewrites: List[HigherOrderRewrite] = []

    # ── Level 2: 2-Morphism Factorization ──────────────────────────

    def factorize_two_cell(self, cell_name: str) -> List[Dict[str, Any]]:
        """
        Factorize a 2-cell α: f => g.

        Two factorization modes:
        1. Vertical: α = β · γ  (stacking 2-cells)
        2. Horizontal: α = β * γ  (side-by-side composition)

        Returns list of factorization candidates with confidence scores.
        """
        if self.two_category is None:
            return []

        cell = self.two_category.two_cells.get(cell_name)
        if cell is None:
            return []

        candidates = []

        # Mode 1: Vertical factorization
        # Find intermediate morphisms h such that f => h => g
        vertical_paths = self._vertical_factorize(cell)
        candidates.extend(vertical_paths)

        # Mode 2: Horizontal factorization
        # Find decomposition into side-by-side 2-cells
        horizontal_paths = self._horizontal_factorize(cell)
        candidates.extend(horizontal_paths)

        return candidates

    def _vertical_factorize(self, cell) -> List[Dict[str, Any]]:
        """
        Find vertical factorizations: α = β · γ.

        This means finding an intermediate morphism h: A → B such that
        there exist 2-cells β: f => h and γ: h => g.
        """
        candidates = []
        two_cat = self.two_category

        # Find all 2-cells with source = cell.source_morphism
        source_cells = two_cat.all_two_cells_from(cell.source_morphism)
        # Find all 2-cells with target = cell.target_morphism
        target_cells = two_cat.all_two_cells_to(cell.target_morphism)

        for beta in source_cells:
            for gamma in target_cells:
                # Check if they compose: beta.target = gamma.source
                if beta.target_morphism == gamma.source_morphism:
                    # Found: cell = gamma · beta (vertical composition)
                    # Confidence = product of confidences (if available)
                    beta_conf = beta.data.get("confidence", 0.5)
                    gamma_conf = gamma.data.get("confidence", 0.5)
                    composed_conf = beta_conf * gamma_conf

                    original_conf = cell.data.get("confidence", 0.0)
                    if composed_conf > original_conf:
                        candidates.append({
                            "mode": "vertical",
                            "beta": beta.name,
                            "gamma": gamma.name,
                            "intermediate": beta.target_morphism,
                            "confidence": composed_conf,
                            "original_confidence": original_conf,
                            "improvement": composed_conf - original_conf,
                        })

        return candidates

    def _horizontal_factorize(self, cell) -> List[Dict[str, Any]]:
        """
        Find horizontal factorizations: α = β * γ.

        This decomposes a 2-cell into side-by-side composition of
        smaller 2-cells.
        """
        # Horizontal factorization is more complex — requires
        # decomposing the domain/codomain objects
        # For now, check if the 2-cell data contains hint about decomposition
        if "horizontal_from" in cell.data:
            components = cell.data["horizontal_from"]
            if len(components) >= 2:
                return [{
                    "mode": "horizontal",
                    "components": components,
                    "confidence": cell.data.get("confidence", 0.5),
                    "original_confidence": cell.data.get("confidence", 0.0),
                    "improvement": 0.0,  # Decomposition, not improvement
                }]
        return []

    def refine_two_cell(self, cell_name: str) -> Optional[Dict[str, Any]]:
        """
        Refine a 2-cell by finding the best factorization.

        Args:
            cell_name: Name of the 2-cell to refine.

        Returns:
            Best factorization candidate, or None if no improvement found.
        """
        candidates = self.factorize_two_cell(cell_name)
        if not candidates:
            return None

        best = max(candidates, key=lambda c: c.get("improvement", 0))
        if best["improvement"] > 0:
            # Record the rewrite
            rewrite = HigherOrderRewrite(
                kind="refine_two_cell",
                old_morphisms=[cell_name],
                new_morphism=best.get("intermediate", "unknown"),
                confidence_before=[best["original_confidence"]],
                confidence_after=best["confidence"],
                generation=self.generation,
                level=2,
                two_cell_name=cell_name,
            )
            self._higher_rewrites.append(rewrite)
            self.rewrites.append(rewrite)  # Also in standard list
            return best

        return None

    # ── Level 3: Fibration Factorization ───────────────────────────

    def factorize_fibration(self, fibration_name: str) -> List[Dict[str, Any]]:
        """
        Factorize a fibration p: E → B.

        Find intermediate total categories E' such that
        p factors as E → E' → B with cartesian lifts preserved.

        Uses the GenericFibration from categorical/fibrations.py.
        """
        try:
            from categorical.fibrations import GenericFibration
        except ImportError:
            return []

        # The fibration factorization search looks for intermediate
        # fiber structures that preserve cartesian lifts
        candidates = []

        # This would require access to the actual fibration structure
        # For now, we detect potential factorization points by
        # analyzing the base category structure
        if self.two_category is not None:
            # Look for objects in the base that could be intermediate
            for obj_name in self.two_category.objects:
                # Check if factoring through this object preserves structure
                # (simplified check — full implementation would use
                # GenericFibration.cartesian_lift)
                candidates.append({
                    "intermediate": obj_name,
                    "confidence": 0.5,  # Placeholder — needs actual computation
                    "mode": "fibration",
                    "fibration_name": fibration_name,
                })

        return candidates

    def refine_fibration(self, fibration_name: str) -> Optional[Dict[str, Any]]:
        """
        Refine a fibration by finding the best factorization.

        Args:
            fibration_name: Name of the fibration to refine.

        Returns:
            Best factorization candidate, or None.
        """
        candidates = self.factorize_fibration(fibration_name)
        if not candidates:
            return None

        best = max(candidates, key=lambda c: c.get("confidence", 0))

        rewrite = HigherOrderRewrite(
            kind="refine_fibration",
            old_morphisms=[fibration_name],
            new_morphism=best.get("intermediate", "unknown"),
            confidence_before=[0.0],
            confidence_after=best["confidence"],
            generation=self.generation,
            level=3,
            fibration_name=fibration_name,
        )
        self._higher_rewrites.append(rewrite)
        return best

    # ── Level 4: Functor Factorization ─────────────────────────────

    def factorize_functor(self, functor_name: str) -> List[Dict[str, Any]]:
        """
        Factorize a functor F: C → D.

        Find an intermediate category E such that
        F factors as C → E → D.

        This discovers that a functor isn't primitive — it factors
        through a simpler category.
        """
        candidates = []

        # Look for objects in the runtime that could be the image
        # of an intermediate category
        for obj_name in self.runtime.objects:
            # Check if the functor factors through this object
            # (simplified — full implementation would verify
            # functor law preservation)
            candidates.append({
                "intermediate_category": obj_name,
                "confidence": 0.5,  # Placeholder
                "mode": "functor",
                "functor_name": functor_name,
            })

        return candidates

    def refine_functor(self, functor_name: str) -> Optional[Dict[str, Any]]:
        """
        Refine a functor by finding the best factorization.

        Args:
            functor_name: Name of the functor to refine.

        Returns:
            Best factorization candidate, or None.
        """
        candidates = self.factorize_functor(functor_name)
        if not candidates:
            return None

        best = max(candidates, key=lambda c: c.get("confidence", 0))

        rewrite = HigherOrderRewrite(
            kind="refine_functor",
            old_morphisms=[functor_name],
            new_morphism=best.get("intermediate_category", "unknown"),
            confidence_before=[0.0],
            confidence_after=best["confidence"],
            generation=self.generation,
            level=4,
            functor_name=functor_name,
        )
        self._higher_rewrites.append(rewrite)
        return best

    # ── Multi-Level Descent ────────────────────────────────────────

    def descend_all(
        self,
        max_steps: int = 20,
        depth: int = 1,
        include_two_cells: bool = True,
        include_fibrations: bool = False,
        include_functors: bool = False,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        Run categorical gradient descent at ALL levels.

        1. First: standard 1-morphism factorization (existing descend)
        2. Then: 2-morphism factorization (if two_category provided)
        3. Then: fibration factorization (if enabled)
        4. Then: functor factorization (if enabled)

        Each level strictly improves confidence.

        Args:
            max_steps: Maximum steps per level.
            depth: Factorization depth for 1-morphisms.
            include_two_cells: Whether to refine 2-cells.
            include_fibrations: Whether to refine fibrations.
            include_functors: Whether to refine functors.
            verbose: Print progress.

        Returns:
            Summary of improvements at all levels.
        """
        results = {"levels": {}, "total_rewrites": 0}

        # Level 1: Standard 1-morphism descent
        if verbose:
            print("\n═══ Level 1: 1-Morphism Factorization ═══")
        level1_result = self.descend(max_steps=max_steps, depth=depth,
                                     verbose=verbose)
        results["levels"]["1_morphisms"] = level1_result
        results["total_rewrites"] += len(level1_result.get("rewrites", []))

        # Level 2: 2-morphism factorization
        if include_two_cells and self.two_category is not None:
            if verbose:
                print("\n═══ Level 2: 2-Morphism Factorization ═══")
            two_cell_rewrites = 0
            for cell_name in list(self.two_category.two_cells.keys()):
                result = self.refine_two_cell(cell_name)
                if result:
                    two_cell_rewrites += 1
                    if verbose:
                        print(f"  Refined 2-cell {cell_name}: "
                              f"improvement={result.get('improvement', 0):.4f}")
            results["levels"]["2_morphisms"] = {
                "steps": two_cell_rewrites,
                "rewrites": [r for r in self._higher_rewrites if r.level == 2],
            }
            results["total_rewrites"] += two_cell_rewrites

        # Level 3: Fibration factorization
        if include_fibrations:
            if verbose:
                print("\n═══ Level 3: Fibration Factorization ═══")
            fibration_rewrites = 0
            # Would need actual fibration instances — placeholder
            results["levels"]["fibrations"] = {
                "steps": fibration_rewrites,
                "rewrites": [r for r in self._higher_rewrites if r.level == 3],
            }

        # Level 4: Functor factorization
        if include_functors:
            if verbose:
                print("\n═══ Level 4: Functor Factorization ═══")
            functor_rewrites = 0
            # Would need actual functor instances — placeholder
            results["levels"]["functors"] = {
                "steps": functor_rewrites,
                "rewrites": [r for r in self._higher_rewrites if r.level == 4],
            }

        if verbose:
            print(f"\n═══ Total: {results['total_rewrites']} rewrites across all levels ═══")

        return results

    @property
    def higher_rewrites(self) -> List[HigherOrderRewrite]:
        """Access the higher-order rewrite history."""
        return list(self._higher_rewrites)
