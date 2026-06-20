# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
OPTIMUS Integration Layer

Bridges KOMPOSOS-IV Category to OPTIMUS RuntimeCategory, enabling
categorical gradient descent (self-refinement) on the knowledge graph.

Architecture:
    Category (IV) --snapshot--> RuntimeCategory (OPTIMUS)
                                    |
                              OptimisMonad.descend()
                                    |
                              Rewrites (shortcuts)
                                    |
                  <--sync_back-- New Morphisms persisted to Category

Key insight: OPTIMUS operates on a snapshot. After refinement,
only the newly discovered shortcuts are synced back to the Category
(which persists them, fires hooks, updates enrichment).
"""

from __future__ import annotations

import sys
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

# Add project root to path for optimus_core import
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from optimus_core import (
    Quantale,
    MULTIPLICATIVE as OPTIMUS_MULTIPLICATIVE,
    ADDITIVE as OPTIMUS_ADDITIVE,
    MIN_QUANTALE as OPTIMUS_MIN,
    FreeCategory,
    Path as OptimusPath,
    EnrichedMorphism,
    RuntimeCategory,
    Functor as OptimusFunctor,
    OptimisMonad,
    Rewrite,
)

from .types import Object, Morphism
from .enrichment import (
    MonoidalStructure,
    MULTIPLICATIVE_QUANTALE,
    ADDITIVE_QUANTALE,
    MIN_QUANTALE as IV_MIN_QUANTALE,
    PROBABILISTIC_QUANTALE,
    MAX_QUANTALE,
)

# Avoid circular import at runtime
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .category import Category


# ══════════════════════════════════════════════════════════════════════════════
# QUANTALE ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

def quantale_to_optimus(ms: MonoidalStructure) -> Quantale:
    """
    Convert a KOMPOSOS-IV MonoidalStructure to an OPTIMUS Quantale.

    Mapping:
        ms.tensor  -> q.tensor   (same: (float, float) -> float)
        ms.unit    -> q.unit     (same: float)
        ms.compare -> q.leq      (requires translation)

    OPTIMUS Quantale.leq(a, b) means "a <= b" in the quantale order.
    OPTIMUS Quantale.better(new, old) uses leq to determine improvement.

    IV MonoidalStructure.compare(a, b) semantics vary by quantale:
        - Multiplicative: compare(a,b) = a >= b (higher is better)
        - Additive: compare(a,b) = a <= b (lower is better)
        - Min: compare(a,b) = a >= b (higher min is better)

    For OPTIMUS:
        - MULTIPLICATIVE.leq(a,b) = a <= b, better(new,old) = old <= new
          (higher confidence = better, same as IV multiplicative)
        - ADDITIVE.leq(a,b) = a >= b, better(new,old) = old >= new
          (lower cost = better, same as IV additive)

    So the mapping is:
        - For "higher is better" quantales (multiplicative, min):
          IV compare(a,b) = a >= b, OPTIMUS leq(a,b) = a <= b
          -> leq = lambda a, b: not ms.compare(a, b) or a == b
          -> Actually simpler: leq(a,b) = b >= a = ms.compare(b, a)
        - For "lower is better" quantales (additive, max, probabilistic):
          IV compare(a,b) = a <= b, OPTIMUS leq(a,b) = a >= b
          -> leq(a,b) = b <= a = ms.compare(b, a)

    General rule: leq(a, b) = ms.compare(b, a)
    Wait, let's verify:
        Multiplicative IV: compare(a,b) = a >= b
        We want OPTIMUS leq(a,b) = a <= b
        ms.compare(b, a) = b >= a, which is a <= b. Correct!

        Additive IV: compare(a,b) = a <= b
        We want OPTIMUS leq(a,b) = a >= b
        ms.compare(b, a) = b <= a, which is a >= b. Correct!

    So: q.leq = lambda a, b: ms.compare(b, a)
    """
    return Quantale(
        name=ms.name,
        tensor=ms.tensor,
        unit=ms.unit,
        leq=lambda a, b, _cmp=ms.compare: _cmp(b, a),
    )


# Pre-built mapping for common quantales
_QUANTALE_MAP: Dict[str, Quantale] = {}


def _get_optimus_quantale(ms: MonoidalStructure) -> Quantale:
    """Get or create OPTIMUS Quantale for a given MonoidalStructure."""
    key = ms.name
    if key not in _QUANTALE_MAP:
        _QUANTALE_MAP[key] = quantale_to_optimus(ms)
    return _QUANTALE_MAP[key]


# ══════════════════════════════════════════════════════════════════════════════
# MORPHISM ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

def morphism_to_enriched(m: Morphism) -> EnrichedMorphism:
    """
    Convert a KOMPOSOS-IV Morphism to an OPTIMUS EnrichedMorphism.

    Field mapping:
        m.name       -> em.name
        m.source     -> em.source
        m.target     -> em.target
        m.confidence -> em.confidence
        m._fn        -> em.fn
        m.metadata   -> em.metadata
        m.provenance -> em.provenance (as list)
        (no field)   -> em.generation = 0
    """
    return EnrichedMorphism(
        name=m.name,
        source=m.source,
        target=m.target,
        confidence=m.confidence,
        fn=m._fn,
        provenance=[m.provenance] if m.provenance else [],
        generation=0,
        metadata=dict(m.metadata) if m.metadata else {},
    )


def enriched_to_morphism(em: EnrichedMorphism) -> Morphism:
    """
    Convert an OPTIMUS EnrichedMorphism to a KOMPOSOS-IV Morphism.

    Sets provenance to "optimus" and includes generation in metadata.
    """
    metadata = dict(em.metadata) if em.metadata else {}
    metadata["optimus_generation"] = em.generation
    if em.provenance:
        metadata["optimus_provenance"] = em.provenance

    return Morphism(
        name=em.name,
        source=em.source,
        target=em.target,
        confidence=em.confidence,
        metadata=metadata,
        provenance="optimus",
        _fn=em.fn,
    )


# ══════════════════════════════════════════════════════════════════════════════
# CATEGORY -> RUNTIME SNAPSHOT
# ══════════════════════════════════════════════════════════════════════════════

def category_to_runtime(cat: "Category") -> RuntimeCategory:
    """
    Snapshot a KOMPOSOS-IV Category into an OPTIMUS RuntimeCategory.

    Creates a fresh RuntimeCategory with:
    - All objects from the Category
    - All morphisms from the Category (converted to EnrichedMorphism)
    - The Category's quantale (converted to OPTIMUS Quantale)

    Note: OPTIMUS uses morphism name as dict key (must be unique).
    IV uses morphism ID (name:source->target) which is always unique.
    We use IV's morphism name directly, but append source->target if
    there are duplicate names to ensure uniqueness.
    """
    q = _get_optimus_quantale(cat.quantale)
    runtime = RuntimeCategory(name=cat.name, quantale=q)

    # Add all objects
    for obj in cat.objects():
        runtime.add_object(obj.name)

    # Add all morphisms, using unique keys
    seen_names = set()
    for mor in cat.morphisms():
        key = mor.name
        if key in seen_names:
            # Duplicate name: use full ID as key
            key = f"{mor.name}({mor.source}->{mor.target})"
        seen_names.add(key)
        runtime.add_morphism(
            name=key,
            src=mor.source,
            tgt=mor.target,
            confidence=mor.confidence,
            fn=mor._fn,
        )

    return runtime


# ══════════════════════════════════════════════════════════════════════════════
# SYNC REWRITES BACK TO CATEGORY
# ══════════════════════════════════════════════════════════════════════════════

def sync_rewrites_to_category(
    monad: OptimisMonad,
    cat: "Category",
) -> List[Morphism]:
    """
    Sync OPTIMUS rewrites back to KOMPOSOS-IV Category.

    For each rewrite (compress, absorb), the new morphism is:
    1. Converted to a KOMPOSOS-IV Morphism
    2. Added to the Category via add_morphism() (persists + fires hooks)

    Only syncs morphisms that don't already exist in the Category.

    Returns:
        List of newly added Morphisms.
    """
    added = []

    for rewrite in monad.rewrites:
        new_name = rewrite.new_morphism
        em = monad.runtime.morphisms.get(new_name)
        if em is None:
            continue

        # Check if this morphism already exists in Category
        mor_id = f"{em.name}:{em.source}->{em.target}"
        if cat.get_morphism(mor_id) is not None:
            continue

        # Ensure source/target objects exist
        if cat.get(em.source) is None:
            cat.add(em.source)
        if cat.get(em.target) is None:
            cat.add(em.target)

        # Convert and add
        mor = enriched_to_morphism(em)
        mor.metadata["rewrite_kind"] = rewrite.kind
        mor.metadata["rewrite_improvement"] = rewrite.improvement(monad.runtime.quantale)
        cat.add_morphism(mor)
        added.append(mor)

    return added


# ══════════════════════════════════════════════════════════════════════════════
# OPTIMUS ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class OptimusEngine:
    """
    Integration engine: runs OPTIMUS categorical gradient descent
    on a KOMPOSOS-IV Category.

    Usage:
        cat = Category("my_domain")
        cat.connect("A", "B", confidence=0.9)
        cat.connect("B", "C", confidence=0.8)
        cat.connect("A", "C", "weak", confidence=0.3)

        engine = OptimusEngine(cat)
        result = engine.refine(max_steps=10, depth=2)
        # result["steps"] = number of improvements
        # result["synced_morphisms"] = names of new shortcuts in Category

    The engine works by:
    1. Snapshotting the Category into an OPTIMUS RuntimeCategory
    2. Running OptimisMonad.descend() to find better factorizations
    3. Syncing discovered shortcuts back to the Category
    """

    def __init__(self, category: "Category", max_depth: int = 3):
        self.category = category
        self.max_depth = max_depth
        self._runtime: Optional[RuntimeCategory] = None
        self._monad: Optional[OptimisMonad] = None
        self._last_result: Optional[dict] = None

    def _build_runtime(self):
        """Snapshot current Category state into OPTIMUS RuntimeCategory."""
        self._runtime = category_to_runtime(self.category)
        self._monad = OptimisMonad(self._runtime, self.max_depth)

    def refine(
        self,
        max_steps: int = 20,
        depth: int = 2,
        verbose: bool = False,
    ) -> dict:
        """
        Run categorical gradient descent on the knowledge graph.

        Searches for better factorizations of morphisms and materializes
        them as shortcut morphisms in the Category.

        Args:
            max_steps: Maximum number of refinement iterations.
            depth: Maximum factorization depth (intermediates).
            verbose: Print progress to stdout.

        Returns:
            Dict with keys:
                steps: Number of improvements made
                improved: Names of improved morphisms
                rewrites: List of Rewrite objects
                synced_morphisms: Names of morphisms added to Category
        """
        self._build_runtime()
        result = self._monad.descend(
            max_steps=max_steps,
            depth=depth,
            verbose=verbose,
        )
        added = sync_rewrites_to_category(self._monad, self.category)
        result["synced_morphisms"] = [m.name for m in added]
        self._last_result = result
        return result

    def refine_morphism(
        self,
        source: str,
        target: str,
        depth: int = 2,
    ) -> Optional[Morphism]:
        """
        Refine a specific morphism between source and target.

        Args:
            source: Source object name.
            target: Target object name.
            depth: Factorization depth.

        Returns:
            The improved Morphism if found, None otherwise.
        """
        self._build_runtime()

        # Find the best morphism between source and target
        em = self._runtime.best_morphism(source, target)
        if em is None:
            return None

        refined = self._monad.refine(em, depth=depth)
        if refined is None:
            return None

        added = sync_rewrites_to_category(self._monad, self.category)
        return added[0] if added else None

    def discover_intermediates(
        self,
        source: str,
        target: str,
        depth: int = 3,
    ) -> List[str]:
        """
        Find intermediate objects between source and target.

        Uses OPTIMUS factorization search to discover objects B
        such that source -> B -> target has better confidence.

        Args:
            source: Source object name.
            target: Target object name.
            depth: Maximum factorization depth.

        Returns:
            List of intermediate object names discovered.
        """
        self._build_runtime()

        em = self._runtime.best_morphism(source, target)
        if em is None:
            return []

        factorizations = self._monad.factorizations(em, depth=depth)
        intermediates = set()
        for path in factorizations:
            for mor in path:
                if mor.source != source:
                    intermediates.add(mor.source)
                if mor.target != target:
                    intermediates.add(mor.target)

        return sorted(intermediates)

    def absorb(
        self,
        source_obj: str,
        target_obj: str,
        threshold: Optional[float] = None,
        use_yoneda_threshold: bool = True,
    ) -> List[Morphism]:
        """
        Yoneda-guided structural transfer.

        If source_obj and target_obj are structurally similar (by Yoneda
        fingerprint), transfer morphisms from source_obj to target_obj
        with confidence scaled by similarity.

        Uses the formal Yoneda proof to derive a provably-correct threshold
        when use_yoneda_threshold=True, replacing the arbitrary 0.8 default.

        The Yoneda Lemma guarantees: d(y(A), y(B)) = 0 ↔ A ≅ B
        So the threshold = 1 - d(y(A), y(B)) is the maximum similarity that
        guarantees correct transfer.

        Args:
            source_obj: Object to transfer morphisms FROM.
            target_obj: Object to transfer morphisms TO.
            threshold: Explicit threshold override. If None, uses Yoneda-derived
                      threshold (if use_yoneda_threshold=True) or 0.8 default.
            use_yoneda_threshold: If True, compute the provably-correct threshold
                                 from the Yoneda distance. Overrides threshold param.

        Returns:
            List of transferred Morphisms added to Category.
        """
        self._build_runtime()

        # Compute the provably-correct threshold from Yoneda proof
        if use_yoneda_threshold:
            try:
                from .formal_yoneda import yoneda_transfer_threshold
                yoneda_threshold = yoneda_transfer_threshold(
                    self.category, source_obj, target_obj
                )
                effective_threshold = yoneda_threshold
            except Exception:
                # Fallback to default if Yoneda proof fails
                effective_threshold = threshold if threshold is not None else 0.8
        elif threshold is not None:
            effective_threshold = threshold
        else:
            effective_threshold = 0.8  # Legacy default

        self._monad.absorb(
            source_obj, target_obj, threshold=effective_threshold
        )
        return sync_rewrites_to_category(self._monad, self.category)

    def yoneda_similarity(self, a: str, b: str) -> float:
        """
        Compute structural similarity between two objects.

        Uses OPTIMUS Yoneda fingerprinting: two objects with identical
        incoming/outgoing morphism profiles are structurally equivalent.

        Returns:
            float in [0, 1]. 1.0 = identical structure, 0.0 = no overlap.
        """
        self._build_runtime()
        return self._runtime.yoneda_similarity(a, b)

    def yoneda_fingerprint(self, obj: str) -> dict:
        """
        Get the full relational fingerprint of an object.

        Returns:
            Dict with keys: object, hom_in, hom_out.
        """
        self._build_runtime()
        return self._runtime.yoneda_fingerprint(obj)

    def find_structural_gaps(self) -> List[Dict[str, Any]]:
        """
        Find structural holes in the knowledge graph.

        A structural hole exists when A -> B -> C exists (multi-hop)
        but no direct A -> C morphism exists. These are candidate
        missing primitives.

        Returns:
            List of dicts with source, target, via, path_confidence.
        """
        self._build_runtime()
        gaps = []
        seen = set()

        for obj_name in self._runtime.objects:
            for mor in self._runtime.morphisms_from(obj_name):
                # mor goes obj_name -> X
                for mor2 in self._runtime.morphisms_from(mor.target):
                    # mor2 goes X -> Y
                    pair = (obj_name, mor2.target)
                    if pair in seen or obj_name == mor2.target:
                        continue
                    seen.add(pair)

                    # Check if direct morphism exists
                    direct = self._runtime.morphisms_between(obj_name, mor2.target)
                    if not direct:
                        q = self._runtime.quantale
                        path_conf = q.compose(mor.confidence, mor2.confidence)
                        gaps.append({
                            "source": obj_name,
                            "target": mor2.target,
                            "via": mor.target,
                            "path_confidence": path_conf,
                        })

        return sorted(gaps, key=lambda g: g["path_confidence"], reverse=True)

    @property
    def rewrites(self) -> List[Rewrite]:
        """Access the rewrite history from the last refinement."""
        return self._monad.rewrites if self._monad else []

    def report(self, verbose: bool = True) -> str:
        """Print or return the rewrite report from the last refinement."""
        if self._monad:
            return self._monad.report(verbose=verbose)
        return "No refinement run yet."
