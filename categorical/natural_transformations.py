# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>
"""
Natural Transformation Detection for Pattern Variants

Mathematical basis:
  - A natural transformation eta: F => G preserves compositional structure
  - Pattern variants use different instances but same abstract shape
  - Naturality square commuting = compositional structure preserved

Construction 3 (Natural Transformation Variant Detection):
  Given two functors F, G: Shape -> Instance where Shape is an abstract
  pattern category, a natural transformation eta: F => G assigns
  to each shape object A a component eta_A: F(A) -> G(A) such that
  for every morphism f: A -> B in Shape, the naturality square commutes:

      F(A) --eta_A--> G(A)
       |                |
      F(f)            G(f)
       |                |
       v                v
      F(B) --eta_B--> G(B)

  Two patterns are related by a natural transformation when they follow
  the same abstract shape (same shape category) but instantiate each step
  with different concrete elements. The naturality condition ensures that
  compositional relationships between steps are preserved across variants.
"""

from typing import List, Dict, Tuple, Optional, Set, Callable
from dataclasses import dataclass, field


@dataclass
class PatternFunctor:
    """
    A functor from shape category to instance category.
    Represents an abstract pattern instantiated with specific elements.

    Shape: The abstract category labels at each position.
    Instance: The concrete elements chosen to realize each shape label.
    """
    name: str
    shape: List[str]         # Abstract labels (shape category objects)
    instance: List[str]      # Concrete elements (functor image)


class NaturalTransformationDetector:
    """
    Detect if two patterns are related by natural transformation.

    Same abstract shape, different concrete instances = VARIANT.

    The detector maintains a registry of known patterns expressed as
    PatternFunctors. When an observed sequence arrives it is lifted to a
    functor and checked against every known pattern for the existence of a
    natural transformation. A match indicates the observed sequence is a
    *variant* of a known pattern.
    """

    def __init__(self, catalog: Dict[str, Dict] = None):
        """
        Initialize with an optional catalog of element metadata.

        Args:
            catalog: A dictionary mapping element IDs to metadata dicts.
                     Each entry should have at least a 'categories' key
                     (list of category labels) and optionally a
                     'composable_with' key (set of element IDs this can
                     compose with). If None, category and composition
                     checks use simple heuristics.
        """
        self.catalog = catalog or {}
        self.known_patterns: Dict[str, PatternFunctor] = {}

    # ------------------------------------------------------------------
    # Pattern registration
    # ------------------------------------------------------------------

    def register_pattern(self, name: str, sequence: List[str],
                         shape: List[str] = None):
        """
        Register a known pattern as a functor.

        The shape (abstract label sequence) can be provided directly or
        derived from the catalog by looking up each element's primary
        category. If an element is unknown to the catalog, its ID is used
        as the shape label.

        Args:
            name:     Human-readable pattern identifier.
            sequence: Ordered list of element IDs comprising the pattern.
            shape:    Optional explicit shape labels. If None, derived
                      from catalog.
        """
        if shape is None:
            shape = []
            for elem_id in sequence:
                categories = self._get_categories(elem_id)
                if categories:
                    shape.append(categories[0])
                else:
                    shape.append(elem_id)

        functor = PatternFunctor(name=name, shape=shape, instance=list(sequence))
        self.known_patterns[name] = functor

    # ------------------------------------------------------------------
    # Naturality checking
    # ------------------------------------------------------------------

    def check_naturality(self, F: PatternFunctor, G: PatternFunctor) -> Dict:
        """
        Check if a natural transformation eta: F => G exists.

        For eta to exist we require:
          1. Same length shape sequences (same shape category).
          2. Each component eta_i maps F(i) to G(i) within the same
             category (component existence).
          3. Every consecutive naturality square commutes, meaning that
             the composition structure is preserved.

        Returns:
            {
                "is_natural": bool,
                "components": {
                    position: {
                        "source": elem1,
                        "target": elem2,
                        "same_category": bool
                    }
                },
                "commuting_squares": [bool, ...],
                "similarity_score": float   # in [0, 1]
            }
        """
        result: Dict = {
            "is_natural": False,
            "components": {},
            "commuting_squares": [],
            "similarity_score": 0.0,
        }

        if len(F.instance) != len(G.instance):
            return result

        n = len(F.instance)
        if n == 0:
            result["is_natural"] = True
            result["similarity_score"] = 1.0
            return result

        # ----- component checks -----
        component_scores: List[float] = []
        for i in range(n):
            src = F.instance[i]
            tgt = G.instance[i]
            same_category = self._same_category(src, tgt)

            result["components"][i] = {
                "source": src,
                "target": tgt,
                "same_category": same_category,
            }

            if src == tgt:
                component_scores.append(1.0)
            elif same_category:
                component_scores.append(0.8)
            else:
                component_scores.append(0.0)

        # ----- commuting-square checks -----
        square_scores: List[float] = []
        for i in range(n - 1):
            f_composable = self._can_compose(F.instance[i], F.instance[i + 1])
            g_composable = self._can_compose(G.instance[i], G.instance[i + 1])

            both_compose = f_composable and g_composable
            result["commuting_squares"].append(both_compose)

            if both_compose:
                square_scores.append(1.0)
            elif f_composable or g_composable:
                square_scores.append(0.5)
            else:
                square_scores.append(0.0)

        # ----- aggregate similarity score -----
        if component_scores:
            comp_avg = sum(component_scores) / len(component_scores)
        else:
            comp_avg = 1.0

        if square_scores:
            sq_avg = sum(square_scores) / len(square_scores)
        else:
            sq_avg = 1.0

        # Weight: 40% components, 60% commuting squares (compositional
        # structure preservation is more important than individual matches)
        similarity = 0.4 * comp_avg + 0.6 * sq_avg
        result["similarity_score"] = round(similarity, 4)

        all_components_valid = all(
            result["components"][i]["same_category"]
            or result["components"][i]["source"] == result["components"][i]["target"]
            for i in range(n)
        )
        all_squares_commute = all(result["commuting_squares"])
        result["is_natural"] = all_components_valid and all_squares_commute

        return result

    # ------------------------------------------------------------------
    # Variant detection
    # ------------------------------------------------------------------

    def detect_variants(self, observed_sequence: List[str],
                        threshold: float = 0.6) -> List[Dict]:
        """
        Check an observed sequence against all known patterns for variant matches.

        The observed sequence is lifted to a PatternFunctor and then each
        known pattern is tested for a natural transformation. Results with
        similarity > threshold are returned, sorted descending by score.

        Args:
            observed_sequence: Ordered list of element IDs.
            threshold: Minimum similarity score to include (default 0.6).

        Returns:
            List of match dicts, each containing:
              - pattern: name of the matched known pattern
              - similarity_score: float in [0, 1]
              - is_natural: whether a strict natural transformation exists
              - components: per-position component data
              - commuting_squares: per-edge commutativity data
        """
        shape = []
        for elem_id in observed_sequence:
            categories = self._get_categories(elem_id)
            shape.append(categories[0] if categories else elem_id)

        observed = PatternFunctor(
            name="observed",
            shape=shape,
            instance=list(observed_sequence),
        )

        matches: List[Dict] = []
        for pattern_name, known_functor in self.known_patterns.items():
            nat = self.check_naturality(known_functor, observed)
            if nat["similarity_score"] > threshold:
                matches.append({
                    "pattern": pattern_name,
                    "similarity_score": nat["similarity_score"],
                    "is_natural": nat["is_natural"],
                    "components": nat["components"],
                    "commuting_squares": nat["commuting_squares"],
                })

        matches.sort(key=lambda m: m["similarity_score"], reverse=True)
        return matches

    # Backward-compatible alias
    detect_variant = detect_variants

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _same_category(self, elem1_id: str, elem2_id: str) -> bool:
        """
        Check if two elements share at least one category.
        """
        cats1 = set(self._get_categories(elem1_id))
        cats2 = set(self._get_categories(elem2_id))
        if not cats1 or not cats2:
            return False
        return len(cats1 & cats2) > 0

    def _get_categories(self, elem_id: str) -> List[str]:
        """
        Get category labels for an element from the catalog.

        Returns a list of category name strings. Returns empty list if
        the element is not found in the catalog.
        """
        entry = self.catalog.get(elem_id)
        if entry is None:
            return []
        categories = entry.get("categories", [])
        if isinstance(categories, list):
            return categories
        return [str(categories)]

    def _can_compose(self, elem1_id: str, elem2_id: str) -> bool:
        """
        Check if two elements can compose (elem1 followed by elem2).

        Uses the catalog's 'composable_with' field if available,
        otherwise defaults to True (permissive).
        """
        entry = self.catalog.get(elem1_id)
        if entry is None:
            return True  # Permissive default
        composable = entry.get("composable_with")
        if composable is None:
            return True  # Permissive default
        return elem2_id in composable
