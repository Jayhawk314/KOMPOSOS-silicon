# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>
"""
Grothendieck Construction: Total Category from Fibration

Given F: B^op -> Cat, the total category integralF unifies all fibers:
- B = base objects (any classification scheme)
- F(b) = subcategory of elements classified under b
- integralF = unified category with cross-base morphisms

This enables detection of patterns that cross classification boundaries.

Mathematical specification:
  Objects of integralF: pairs (b, x) where b in B and x in F(b)
  Morphisms: (f, phi): (b,x) -> (b',x') where f: b->b' in B
             and phi: x -> F(f)(x') in F(b)
  Composition: (g,psi) . (f,phi) = (g.f, psi . F(f)(phi))

References:
  - Grothendieck, "Revetements Etales et Groupe Fondamental" (SGA 1)
  - Jacobs, "Categorical Logic and Type Theory", Ch. 1
  - Loregian, "(Co)end Calculus", Ch. 2 (fibrations)
"""

from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
import math


@dataclass
class FiberedObject:
    """
    Object in total category integralF: (base_object, fiber_object).

    In the Grothendieck construction, an object is a pair (b, x)
    where b is an object of the base category B and x is an object
    of the fiber category F(b).
    """
    base: str           # Base category object
    fiber: str          # Fiber category object within that base

    def __hash__(self):
        return hash((self.base, self.fiber))

    def __eq__(self, other):
        if not isinstance(other, FiberedObject):
            return NotImplemented
        return self.base == other.base and self.fiber == other.fiber

    def __repr__(self):
        return f"({self.base}, {self.fiber})"


@dataclass
class FiberedMorphism:
    """
    Morphism in integralF.

    A morphism (f, phi): (b, x) -> (b', x') consists of:
      - f: b -> b' in B (base transition, possibly identity)
      - phi: x -> F(f)(x') in F(b) (fiber transition within source fiber)

    morphism_type classifies:
      - "within_base": f = id_b, phi is a transition within F(b)
      - "cross_base": f is a non-identity base transition
      - "cartesian_lift": the Cartesian lift of f at x'
    """
    source: FiberedObject
    target: FiberedObject
    morphism_type: str   # "within_base", "cross_base", "cartesian_lift"
    weight: float        # Enrichment weight
    transition_label: str = ""  # For cross-base: which base boundary crossed

    def __repr__(self):
        return (f"({self.source} -> {self.target}, "
                f"type={self.morphism_type}, weight={self.weight:.3f})")


class GrothendieckConstruction:
    """
    Total category integralF from fibration F: B -> Cat.

    Unifies all base objects into one category where cross-base
    transitions are first-class morphisms.

    Constructor parameters:
      - base_objects: List of base category object names.
      - fiber_classification: Dict mapping each base object to a list
        of fiber element IDs classified under it.
      - base_transitions: Dict mapping (src_base, tgt_base) pairs to
        a transition weight (morphisms in the base category B).
      - can_compose: Callable (elem1, elem2) -> bool, determining if
        two fiber elements can compose. Defaults to always True.
      - composition_weight: Callable (elem1, elem2) -> float, returning
        the weight of composing two elements. Defaults to 0.7.
    """

    def __init__(self,
                 base_objects: List[str],
                 fiber_classification: Dict[str, List[str]],
                 base_transitions: Dict[Tuple[str, str], float],
                 can_compose=None,
                 composition_weight=None):
        self.base_objects = list(base_objects)
        self.fiber_classification = dict(fiber_classification)
        self.base_transitions = dict(base_transitions)
        self._can_compose = can_compose or (lambda a, b: True)
        self._composition_weight = composition_weight or (lambda a, b: 0.7)

        self.total_objects: List[FiberedObject] = []
        self.total_morphisms: List[FiberedMorphism] = []
        self._object_index: Dict[Tuple[str, str], FiberedObject] = {}
        self._adjacency: Dict[Tuple[str, str], List[FiberedMorphism]] = {}
        self._base_fiber_objects: Dict[str, List[FiberedObject]] = {
            b: [] for b in self.base_objects
        }

        # Build reverse lookup: fiber element -> list of base objects
        self._fiber_to_bases: Dict[str, List[str]] = {}
        for base_obj, fibers in self.fiber_classification.items():
            for fiber in fibers:
                self._fiber_to_bases.setdefault(fiber, []).append(base_obj)

        self.build()

    def build(self):
        """
        Construct total category from base objects + fiber elements.

        Phase 1: Add all (base, fiber) objects from fiber_classification.
        Phase 2: Add within-base morphisms using can_compose.
        Phase 3: Add cross-base transition morphisms using base_transitions.
        """
        # Phase 1: Build objects of integralF
        for base_obj in self.base_objects:
            fiber_ids = self.fiber_classification.get(base_obj, [])
            for fiber_id in fiber_ids:
                obj = FiberedObject(base=base_obj, fiber=fiber_id)
                self.total_objects.append(obj)
                key = (base_obj, fiber_id)
                self._object_index[key] = obj
                self._base_fiber_objects[base_obj].append(obj)
                self._adjacency[key] = []

        # Phase 2: Within-base morphisms
        for base_obj in self.base_objects:
            base_objs = self._base_fiber_objects[base_obj]
            for src_obj in base_objs:
                for tgt_obj in base_objs:
                    if src_obj == tgt_obj:
                        continue
                    if self._can_compose(src_obj.fiber, tgt_obj.fiber):
                        weight = self._composition_weight(
                            src_obj.fiber, tgt_obj.fiber
                        )
                        morphism = FiberedMorphism(
                            source=src_obj,
                            target=tgt_obj,
                            morphism_type="within_base",
                            weight=weight,
                            transition_label=""
                        )
                        self.total_morphisms.append(morphism)
                        src_key = (src_obj.base, src_obj.fiber)
                        self._adjacency[src_key].append(morphism)

        # Phase 3: Cross-base transition morphisms
        for (src_base, tgt_base), transition_weight in self.base_transitions.items():
            src_objs = self._base_fiber_objects.get(src_base, [])
            tgt_objs = self._base_fiber_objects.get(tgt_base, [])
            for src_obj in src_objs:
                for tgt_obj in tgt_objs:
                    if self._can_compose(src_obj.fiber, tgt_obj.fiber):
                        elem_weight = self._composition_weight(
                            src_obj.fiber, tgt_obj.fiber
                        )
                        cross_weight = elem_weight * transition_weight
                        morphism = FiberedMorphism(
                            source=src_obj,
                            target=tgt_obj,
                            morphism_type="cross_base",
                            weight=cross_weight,
                            transition_label=f"{src_base}->{tgt_base}"
                        )
                        self.total_morphisms.append(morphism)
                        src_key = (src_obj.base, src_obj.fiber)
                        self._adjacency[src_key].append(morphism)

    def cartesian_lift(self, source_base: str, target_base: str,
                       fiber_elem: str) -> List[str]:
        """
        Given a fiber element in source_base, find corresponding
        elements in target_base via Cartesian lift.

        In fibration theory, the Cartesian lift of a morphism f: b -> b'
        at an object x' in F(b') is the universal morphism (f, phi)
        above f with codomain (b', x').
        """
        lifted = []
        source_key = (source_base, fiber_elem)

        if source_key not in self._object_index:
            return lifted

        for morphism in self._adjacency.get(source_key, []):
            if morphism.target.base == target_base:
                if morphism.target.fiber not in lifted:
                    lifted.append(morphism.target.fiber)

        return lifted

    def find_cross_base_chains(self, max_transitions: int = 3,
                               max_length: int = 8) -> List[List[FiberedObject]]:
        """
        Find valid chains that cross base category boundaries.

        Uses BFS to discover chains that traverse at least 2 base objects.

        Args:
            max_transitions: Maximum number of base boundaries to cross.
            max_length: Maximum total chain length.

        Returns:
            List of chains that cross at least one base boundary.
        """
        chains: List[List[FiberedObject]] = []

        start_objects = []
        for base_obj in self.base_objects:
            start_objects.extend(self._base_fiber_objects.get(base_obj, []))

        for start_obj in start_objects:
            queue = [(start_obj, [start_obj], {start_obj.base}, 0)]
            visited_states: Set[Tuple[str, str, int]] = set()

            while queue:
                current, chain, bases, transitions = queue.pop(0)

                if len(chain) > max_length:
                    continue

                if transitions >= 1 and len(chain) >= 2:
                    chains.append(list(chain))

                if len(chains) >= 500:
                    return chains

                current_key = (current.base, current.fiber)
                state_key = (current.base, current.fiber, transitions)
                if state_key in visited_states:
                    continue
                visited_states.add(state_key)

                for morphism in self._adjacency.get(current_key, []):
                    target = morphism.target
                    new_transitions = transitions
                    new_bases = set(bases)

                    if target.base != current.base:
                        new_transitions += 1
                        new_bases.add(target.base)

                    if new_transitions > max_transitions:
                        continue
                    if len(chain) + 1 > max_length:
                        continue

                    target_state = (target.base, target.fiber, new_transitions)
                    if target_state not in visited_states:
                        queue.append((target, chain + [target], new_bases, new_transitions))

        return chains

    def classify_fiber_element(self, fiber_id: str) -> List[str]:
        """Get which base objects a fiber element belongs to."""
        return self._fiber_to_bases.get(fiber_id, [])

    def get_stats(self) -> Dict:
        """Get statistics about the total category integralF."""
        within_count = sum(
            1 for m in self.total_morphisms if m.morphism_type == "within_base"
        )
        cross_count = sum(
            1 for m in self.total_morphisms if m.morphism_type == "cross_base"
        )

        base_obj_counts = {}
        for base_obj in self.base_objects:
            base_obj_counts[base_obj] = len(self._base_fiber_objects.get(base_obj, []))

        base_morphism_counts = {}
        for base_obj in self.base_objects:
            count = 0
            for obj in self._base_fiber_objects.get(base_obj, []):
                key = (obj.base, obj.fiber)
                count += len(self._adjacency.get(key, []))
            base_morphism_counts[base_obj] = count

        transition_counts: Dict[str, int] = {}
        for m in self.total_morphisms:
            if m.morphism_type == "cross_base" and m.transition_label:
                transition_counts[m.transition_label] = (
                    transition_counts.get(m.transition_label, 0) + 1
                )

        within_weight_vals = [
            m.weight for m in self.total_morphisms if m.morphism_type == "within_base"
        ]
        cross_weight_vals = [
            m.weight for m in self.total_morphisms if m.morphism_type == "cross_base"
        ]
        avg_within_weight = (
            sum(within_weight_vals) / len(within_weight_vals)
            if within_weight_vals else 0.0
        )
        avg_cross_weight = (
            sum(cross_weight_vals) / len(cross_weight_vals)
            if cross_weight_vals else 0.0
        )

        shared_fibers = {
            fiber: bases
            for fiber, bases in self._fiber_to_bases.items()
            if len(bases) > 1
        }

        return {
            "total_objects": len(self.total_objects),
            "total_morphisms": len(self.total_morphisms),
            "within_base_morphisms": within_count,
            "cross_base_morphisms": cross_count,
            "base_object_counts": base_obj_counts,
            "base_morphism_counts": base_morphism_counts,
            "transition_counts": transition_counts,
            "avg_within_weight": round(avg_within_weight, 4),
            "avg_cross_weight": round(avg_cross_weight, 4),
            "shared_fibers": len(shared_fibers),
            "num_base_objects": len(self.base_objects),
        }

    def get_fibered_morphisms_from(self, base: str, fiber: str) -> List[FiberedMorphism]:
        """Get all outgoing morphisms from a fibered object."""
        key = (base, fiber)
        return list(self._adjacency.get(key, []))

    def get_fibered_morphisms_to(self, base: str, fiber: str) -> List[FiberedMorphism]:
        """Get all incoming morphisms to a fibered object."""
        target_obj = self._object_index.get((base, fiber))
        if target_obj is None:
            return []
        return [
            m for m in self.total_morphisms
            if m.target == target_obj
        ]

    def compose_morphisms(self, m1: FiberedMorphism,
                          m2: FiberedMorphism) -> Optional[FiberedMorphism]:
        """
        Compose two fibered morphisms: m2 . m1.

        In the Grothendieck construction:
          (g, psi) . (f, phi) = (g.f, psi . F(f)(phi))

        Composition is valid only if m1.target == m2.source.
        The composed weight is the product (monoidal composition in [0,1]).
        """
        if m1.target != m2.source:
            return None

        if m1.morphism_type == "cross_base" or m2.morphism_type == "cross_base":
            composed_type = "cross_base"
            labels = []
            if m1.transition_label:
                labels.append(m1.transition_label)
            if m2.transition_label:
                labels.append(m2.transition_label)
            composed_label = " | ".join(labels) if labels else ""
        else:
            composed_type = "within_base"
            composed_label = ""

        composed_weight = m1.weight * m2.weight

        return FiberedMorphism(
            source=m1.source,
            target=m2.target,
            morphism_type=composed_type,
            weight=composed_weight,
            transition_label=composed_label,
        )

    def optimal_cross_base_path(self, source_base: str,
                                target_base: str,
                                max_length: int = 6) -> Optional[Tuple[List[FiberedObject], float]]:
        """
        Find the optimal-weight path from any element in source_base
        to any element in target_base.

        Uses Dijkstra on -log(weight) to find the max-product path.

        Returns:
            (path, total_weight) or None if no path exists.
        """
        source_objs = self._base_fiber_objects.get(source_base, [])
        target_base_set = set(
            (obj.base, obj.fiber) for obj in self._base_fiber_objects.get(target_base, [])
        )

        if not source_objs or not target_base_set:
            return None

        import heapq

        dist: Dict[Tuple[str, str], float] = {}
        prev: Dict[Tuple[str, str], Optional[Tuple[str, str]]] = {}
        path_len: Dict[Tuple[str, str], int] = {}

        pq = []

        for obj in source_objs:
            key = (obj.base, obj.fiber)
            dist[key] = 0.0
            prev[key] = None
            path_len[key] = 1
            heapq.heappush(pq, (0.0, key))

        best_target_key = None
        best_target_dist = float("inf")

        while pq:
            d, u_key = heapq.heappop(pq)

            if d > dist.get(u_key, float("inf")):
                continue

            if u_key in target_base_set and d < best_target_dist:
                best_target_dist = d
                best_target_key = u_key

            if path_len.get(u_key, 0) >= max_length:
                continue

            for morphism in self._adjacency.get(u_key, []):
                v_key = (morphism.target.base, morphism.target.fiber)
                if morphism.weight <= 0:
                    continue
                edge_cost = -math.log(morphism.weight)
                new_dist = d + edge_cost

                if new_dist < dist.get(v_key, float("inf")):
                    dist[v_key] = new_dist
                    prev[v_key] = u_key
                    path_len[v_key] = path_len.get(u_key, 0) + 1
                    heapq.heappush(pq, (new_dist, v_key))

        if best_target_key is None:
            return None

        path_keys = []
        current = best_target_key
        while current is not None:
            path_keys.append(current)
            current = prev.get(current)
        path_keys.reverse()

        path = [self._object_index[k] for k in path_keys]
        total_weight = math.exp(-best_target_dist)

        return (path, total_weight)

    def __repr__(self):
        stats = self.get_stats()
        return (
            f"GrothendieckConstruction(|Ob|={stats['total_objects']}, "
            f"|Mor|={stats['total_morphisms']}, "
            f"bases={stats['num_base_objects']}, "
            f"cross={stats['cross_base_morphisms']})"
        )
