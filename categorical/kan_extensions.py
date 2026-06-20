"""
Kan Extensions - The Heart of Categorical Prediction

Kan extensions are "the most important concept in category theory" (Mac Lane).

Given:
- F: C → D (a functor we want to extend)
- K: C → E (an embedding/inclusion)

We want to extend F along K to get F̂: E → D

Left Kan Extension (Lan_K F):
- "Best approximation from below"
- Computed via colimits
- Lan_K(F)(e) = colim_{(c,f) ∈ (K↓e)} F(c)
- Use case: PREDICT unknown from known (forward extrapolation)

Right Kan Extension (Ran_K F):
- "Best approximation from above"
- Computed via limits
- Ran_K(F)(e) = lim_{(c,f) ∈ (e↓K)} F(c)
- Use case: SYNTHESIZE goal from current (backward deduction)

In KOMPOSOS-III:
- Lan: "Given what we know, predict what we don't"
- Ran: "Given where we want to be, what do we need?"
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Tuple, Set
from .category import Object, Morphism, Category
import numpy as np


@dataclass
class Functor:
    """
    A functor F: C → D mapping between categories.

    A functor preserves:
    - Objects: F(A) in D for each A in C
    - Morphisms: F(f): F(A) → F(B) for each f: A → B
    - Composition: F(g ∘ f) = F(g) ∘ F(f)
    - Identity: F(id_A) = id_{F(A)}
    """
    name: str
    source_cat: Category
    target_cat: Category
    object_map: Dict[str, Any] = field(default_factory=dict)
    morphism_map: Dict[str, Any] = field(default_factory=dict)

    def __call__(self, x):
        """Apply functor to object or morphism."""
        if isinstance(x, Object):
            return self.object_map.get(x.name)
        elif isinstance(x, Morphism):
            return self.morphism_map.get(x.name)
        else:
            raise TypeError(f"Cannot apply functor to {type(x)}")

    def add_object_mapping(self, source_obj: Object, target_value: Any):
        """Add a mapping F(source_obj) = target_value."""
        self.object_map[source_obj.name] = target_value

    def add_morphism_mapping(self, source_mor: Morphism, target_mor: Any):
        """Add a mapping F(source_mor) = target_mor."""
        self.morphism_map[source_mor.name] = target_mor


@dataclass
class CommaCategory:
    """
    The comma category (K ↓ e) for computing Kan extensions.

    Objects: pairs (c, f: K(c) → e) where c ∈ C
    Morphisms: h: c → c' such that f' ∘ K(h) = f

    This is the "index category" for the colimit/limit defining Kan extensions.
    """
    K: Functor          # The embedding functor
    target: Object      # The object e we're extending to
    objects: List[Tuple[Object, Morphism]] = field(default_factory=list)
    morphisms: List[Tuple[Morphism, Tuple, Tuple]] = field(default_factory=list)

    def add_object(self, c: Object, f: Morphism):
        """Add (c, f: K(c) → e) to the comma category."""
        self.objects.append((c, f))

    def add_morphism(self, h: Morphism, source_pair: Tuple, target_pair: Tuple):
        """Add h making the triangle commute."""
        self.morphisms.append((h, source_pair, target_pair))


class LeftKanExtension:
    """
    Left Kan Extension: Lan_K(F)

    For each object e in E, computes:
    Lan_K(F)(e) = colim_{(c,f) ∈ (K↓e)} F(c)

    Intuitively: "The best approximation from below"
    - Aggregates all known information pointing toward e
    - Uses colimit (universal cocone) to combine

    In KOMPOSOS-III, this is used for PREDICTION:
    - Given known concept→value mappings F
    - And known concepts embedded in larger space K
    - Predict values for unknown concepts via Lan
    """

    def __init__(self, F: Functor, K: Functor):
        """
        Initialize Left Kan Extension.

        Args:
            F: The functor we want to extend (known mappings)
            K: The embedding functor (how known fits in larger space)
        """
        self.F = F
        self.K = K
        self._cache: Dict[str, Tuple[Any, float]] = {}

    def comma_category(self, e: Object) -> CommaCategory:
        """
        Build the comma category (K ↓ e).

        This finds all objects c in the source of K
        such that there's a morphism K(c) → e.
        """
        comma = CommaCategory(K=self.K, target=e)

        # For each object in source category of K
        for c_name, c in self.K.source_cat.objects.items():
            Kc = self.K(c)  # K(c) - the image in the target category

            if Kc is None:
                continue

            # Find morphisms from K(c) to e
            # In practice, we look for connections in the target category
            target_cat = self.K.target_cat
            morphisms_to_e = target_cat.hom(
                Object(Kc) if isinstance(Kc, str) else Kc,
                e
            )

            for f in morphisms_to_e:
                comma.add_object(c, f)

        return comma

    def extend(self, e: Object) -> Tuple[Any, float]:
        """
        Compute Lan_K(F)(e) = colim_{(K↓e)} F

        Returns:
            Tuple of (value, confidence) where:
            - value: the computed extension (colimit of F values)
            - confidence: how confident we are (based on # of contributors)
        """
        if e.name in self._cache:
            return self._cache[e.name]

        comma = self.comma_category(e)

        if not comma.objects:
            # No information pointing to e
            return None, 0.0

        # Collect F values from all objects in comma category
        values = []
        weights = []

        for c, f in comma.objects:
            Fc = self.F(c)
            if Fc is not None:
                values.append(Fc)
                # Weight by morphism "strength" if available
                weight = f.data.get("weight", 1.0)
                weights.append(weight)

        if not values:
            return None, 0.0

        # Compute colimit as weighted combination
        # For numeric values: weighted average
        # For other types: collect into structure
        result = self._compute_colimit(values, weights)
        confidence = self._compute_confidence(len(values), weights)

        self._cache[e.name] = (result, confidence)
        return result, confidence

    def _compute_colimit(self, values: List[Any], weights: List[float]) -> Any:
        """
        Compute the colimit of values.

        For numeric/vector values: weighted average (coproduct-like)
        For dictionaries: merge with weighted values
        For other: return list (disjoint union)
        """
        if not values:
            return None

        # Handle numeric values
        if all(isinstance(v, (int, float)) for v in values):
            total_weight = sum(weights)
            if total_weight == 0:
                return sum(values) / len(values)
            return sum(v * w for v, w in zip(values, weights)) / total_weight

        # Handle numpy arrays
        if all(isinstance(v, np.ndarray) for v in values):
            total_weight = sum(weights)
            if total_weight == 0:
                return np.mean(values, axis=0)
            weighted = sum(v * w for v, w in zip(values, weights))
            return weighted / total_weight

        # Handle dictionaries (merge)
        if all(isinstance(v, dict) for v in values):
            result = {}
            for v, w in zip(values, weights):
                for key, val in v.items():
                    if key not in result:
                        result[key] = []
                    result[key].append((val, w))
            # Aggregate each key
            return {
                k: self._compute_colimit([x[0] for x in vs], [x[1] for x in vs])
                for k, vs in result.items()
            }

        # Default: return collected values
        return {"values": values, "weights": weights}

    def _compute_confidence(self, num_contributors: int,
                           weights: List[float]) -> float:
        """
        Compute confidence score for the extension.

        Based on:
        - Number of contributing objects
        - Weight distribution
        """
        if num_contributors == 0:
            return 0.0

        # More contributors = higher confidence
        base_confidence = min(1.0, num_contributors / 5.0)

        # Higher total weight = higher confidence
        total_weight = sum(weights)
        weight_factor = min(1.0, total_weight / 3.0)

        return (base_confidence + weight_factor) / 2.0


class RightKanExtension:
    """
    Right Kan Extension: Ran_K(F)

    For each object e in E, computes:
    Ran_K(F)(e) = lim_{(e,f) ∈ (e↓K)} F(c)

    Intuitively: "The best approximation from above"
    - Aggregates all known information that e points to
    - Uses limit (universal cone) to combine

    In KOMPOSOS-III, this is used for SYNTHESIS:
    - Given a goal state e
    - Find what common structure all paths from e share
    - This tells us what we NEED to reach the goal
    """

    def __init__(self, F: Functor, K: Functor):
        """
        Initialize Right Kan Extension.

        Args:
            F: The functor we want to extend
            K: The embedding functor
        """
        self.F = F
        self.K = K
        self._cache: Dict[str, Tuple[Any, float]] = {}

    def comma_category(self, e: Object) -> CommaCategory:
        """
        Build the comma category (e ↓ K).

        This finds all objects c in the source of K
        such that there's a morphism e → K(c).
        """
        comma = CommaCategory(K=self.K, target=e)

        for c_name, c in self.K.source_cat.objects.items():
            Kc = self.K(c)

            if Kc is None:
                continue

            target_cat = self.K.target_cat
            morphisms_from_e = target_cat.hom(
                e,
                Object(Kc) if isinstance(Kc, str) else Kc
            )

            for f in morphisms_from_e:
                comma.add_object(c, f)

        return comma

    def extend(self, e: Object) -> Tuple[Any, float]:
        """
        Compute Ran_K(F)(e) = lim_{(e↓K)} F

        Returns:
            Tuple of (value, confidence)
        """
        if e.name in self._cache:
            return self._cache[e.name]

        comma = self.comma_category(e)

        if not comma.objects:
            return None, 0.0

        values = []
        weights = []

        for c, f in comma.objects:
            Fc = self.F(c)
            if Fc is not None:
                values.append(Fc)
                weight = f.data.get("weight", 1.0)
                weights.append(weight)

        if not values:
            return None, 0.0

        # Compute limit as intersection/meet
        result = self._compute_limit(values, weights)
        confidence = self._compute_confidence(len(values), weights)

        self._cache[e.name] = (result, confidence)
        return result, confidence

    def _compute_limit(self, values: List[Any], weights: List[float]) -> Any:
        """
        Compute the limit of values.

        For numeric values: weighted min/intersection-like
        For dictionaries: intersection of keys with min values
        For other: return common structure
        """
        if not values:
            return None

        # Handle numeric: conservative estimate (minimum)
        if all(isinstance(v, (int, float)) for v in values):
            # Weight-adjusted minimum
            adjusted = [v / max(w, 0.1) for v, w in zip(values, weights)]
            return min(adjusted) * (sum(weights) / len(weights))

        # Handle numpy arrays: element-wise minimum
        if all(isinstance(v, np.ndarray) for v in values):
            return np.min(values, axis=0)

        # Handle dictionaries: intersection
        if all(isinstance(v, dict) for v in values):
            # Find common keys
            common_keys = set(values[0].keys())
            for v in values[1:]:
                common_keys &= set(v.keys())

            result = {}
            for key in common_keys:
                key_values = [v[key] for v in values]
                key_weights = weights  # Same weights for all
                result[key] = self._compute_limit(key_values, key_weights)
            return result

        # Default
        return {"common": values[0] if values else None}

    def _compute_confidence(self, num_contributors: int,
                           weights: List[float]) -> float:
        """Compute confidence (same as Left Kan)."""
        if num_contributors == 0:
            return 0.0

        base_confidence = min(1.0, num_contributors / 5.0)
        total_weight = sum(weights)
        weight_factor = min(1.0, total_weight / 3.0)

        return (base_confidence + weight_factor) / 2.0


class KanExtensionOracle:
    """
    High-level oracle that uses Kan extensions for prediction and synthesis.

    This is the interface that KOMPOSOS-III uses to:
    - Predict properties of unknown concepts (Lan)
    - Synthesize requirements for goals (Ran)
    """

    def __init__(self, known_category: Category, full_category: Category):
        """
        Initialize the oracle.

        Args:
            known_category: Category of known concepts with values
            full_category: Larger category including unknown concepts
        """
        self.known = known_category
        self.full = full_category

        # Create embedding functor K: Known → Full
        self.K = Functor("embedding", known_category, full_category)
        for name, obj in known_category.objects.items():
            if name in full_category.objects:
                self.K.add_object_mapping(obj, full_category.objects[name])

        # Value functor F: Known → Values (will be set by user)
        self.F = Functor("values", known_category, None)

        self._lan = None
        self._ran = None

    def set_known_value(self, concept: Object, value: Any):
        """Set the known value for a concept."""
        self.F.add_object_mapping(concept, value)

    def predict(self, unknown_concept: Object) -> Tuple[Any, float]:
        """
        Predict value for unknown concept using Left Kan Extension.

        Args:
            unknown_concept: The concept to predict value for

        Returns:
            (predicted_value, confidence)
        """
        if self._lan is None:
            self._lan = LeftKanExtension(self.F, self.K)

        return self._lan.extend(unknown_concept)

    def synthesize(self, goal_concept: Object) -> Tuple[Any, float]:
        """
        Synthesize requirements for goal using Right Kan Extension.

        Args:
            goal_concept: The goal we want to reach

        Returns:
            (required_structure, confidence)
        """
        if self._ran is None:
            self._ran = RightKanExtension(self.F, self.K)

        return self._ran.extend(goal_concept)


# Example usage
if __name__ == "__main__":
    # Create categories
    known = Category("KnownParticles")
    full = Category("AllParticles")

    # Known particles
    electron = known.add_object(Object("electron"))
    proton = known.add_object(Object("proton"))
    neutron = known.add_object(Object("neutron"))

    # Full category includes unknown
    for p in [electron, proton, neutron]:
        full.add_object(p)
    quark = full.add_object(Object("quark"))
    neutrino = full.add_object(Object("neutrino"))

    # Add morphisms (relationships)
    full.add_morphism(Morphism("constituent", quark, proton, weight=0.9))
    full.add_morphism(Morphism("constituent", quark, neutron, weight=0.9))
    full.add_morphism(Morphism("weak_decay", neutron, neutrino, weight=0.5))

    # Create oracle
    oracle = KanExtensionOracle(known, full)

    # Set known values
    oracle.set_known_value(electron, {"charge": -1, "spin": 0.5, "mass": 0.511})
    oracle.set_known_value(proton, {"charge": +1, "spin": 0.5, "mass": 938.3})
    oracle.set_known_value(neutron, {"charge": 0, "spin": 0.5, "mass": 939.6})

    # Predict unknown
    quark_pred, conf = oracle.predict(quark)
    print(f"Predicted quark properties: {quark_pred} (confidence: {conf:.2f})")

    neutrino_pred, conf = oracle.predict(neutrino)
    print(f"Predicted neutrino properties: {neutrino_pred} (confidence: {conf:.2f})")
