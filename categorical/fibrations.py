# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Domain-Agnostic Grothendieck Fibration API

Wraps the Grothendieck construction (grothendieck.py) with a generic API
that works with any domain's fiber structure. Instead of "attack surfaces"
and "techniques", this module uses generic "base categories" and "fiber objects".

The YAML domain schema defines what "fibers" mean:
  - Fraud: departments, employees
  - Engineering: subsystems, components
  - Cyber: attack surfaces, techniques
  - Pharma: pathways, targets

Mathematical specification (unchanged from grothendieck.py):
  Objects of integralF: pairs (b, x) where b in B and x in F(b)
  Morphisms: (f, phi): (b,x) -> (b',x') where f: b->b' in B
             and phi: x -> F(f)(x') in F(b)
  Composition: (g,psi) . (f,phi) = (g.f, psi . F(f)(phi))
"""

from typing import List, Dict, Tuple, Optional, Set, Any
from dataclasses import dataclass, field
import math
import heapq


@dataclass
class FiberObject:
    """
    Object in total category integralF: (base, fiber).

    Generic version of FiberedObject from grothendieck.py.
    """
    base: str       # Base category object (e.g., department, surface, pathway)
    fiber: str      # Fiber object (e.g., employee, technique, protein)

    def __hash__(self):
        return hash((self.base, self.fiber))

    def __eq__(self, other):
        if not isinstance(other, FiberObject):
            return NotImplemented
        return self.base == other.base and self.fiber == other.fiber

    def __repr__(self):
        return f"({self.base}, {self.fiber})"


@dataclass
class FiberMorphism:
    """
    Morphism in integralF.

    morphism_type classifies:
      - "within_fiber": f = id_b, phi is a transition within F(b)
      - "cross_fiber": f is a non-identity base transition
      - "cartesian_lift": the canonical lift of f at x'
    """
    source: FiberObject
    target: FiberObject
    morphism_type: str      # "within_fiber", "cross_fiber", "cartesian_lift"
    weight: float           # Enrichment weight (from store confidence)
    transition_label: str = ""  # Label for the base transition

    def __repr__(self):
        return (f"({self.source} -> {self.target}, "
                f"type={self.morphism_type}, weight={self.weight:.3f})")


class GenericFibration:
    """
    Domain-agnostic Grothendieck construction from a KomposOSStore.

    Instead of hardcoded attack surfaces, this builds the fibration
    from the store's objects and morphisms using a fiber_key that
    determines which metadata field defines the base category.

    Args:
        store: KomposOSStore with objects and morphisms
        fiber_key: Metadata key or 'type' to use as base category grouping.
                   If 'type', uses object.type_name. Otherwise looks in metadata.
        cross_fiber_relations: List of morphism names that represent cross-fiber
                               transitions. If None, any morphism between objects
                               in different fibers is treated as cross-fiber.
    """

    def __init__(self, store, fiber_key: str = "type",
                 cross_fiber_relations: Optional[List[str]] = None):
        self.store = store
        self.fiber_key = fiber_key
        self.cross_fiber_relations = cross_fiber_relations

        self.total_objects: List[FiberObject] = []
        self.total_morphisms: List[FiberMorphism] = []
        self._object_index: Dict[Tuple[str, str], FiberObject] = {}
        self._adjacency: Dict[Tuple[str, str], List[FiberMorphism]] = {}
        self._fiber_objects: Dict[str, List[FiberObject]] = {}
        self._name_to_fiber: Dict[str, str] = {}  # object name -> base

    def build(self) -> 'GenericFibration':
        """
        Construct total category from store data.

        Returns self for chaining.
        """
        objects = self.store.list_objects(limit=100000)
        morphisms = self.store.list_morphisms(limit=100000)

        # Phase 1: Build fiber objects
        for obj in objects:
            if self.fiber_key == "type":
                base = obj.type_name or "default"
            else:
                base = obj.metadata.get(self.fiber_key, "default")

            fiber_obj = FiberObject(base=base, fiber=obj.name)
            self.total_objects.append(fiber_obj)
            key = (base, obj.name)
            self._object_index[key] = fiber_obj
            self._fiber_objects.setdefault(base, []).append(fiber_obj)
            self._adjacency[key] = []
            self._name_to_fiber[obj.name] = base

        # Phase 2: Build morphisms
        for mor in morphisms:
            src_base = self._name_to_fiber.get(mor.source_name)
            tgt_base = self._name_to_fiber.get(mor.target_name)

            if src_base is None or tgt_base is None:
                continue

            src_obj = self._object_index.get((src_base, mor.source_name))
            tgt_obj = self._object_index.get((tgt_base, mor.target_name))

            if src_obj is None or tgt_obj is None:
                continue

            # Determine morphism type
            if src_base == tgt_base:
                morph_type = "within_fiber"
                label = ""
            else:
                morph_type = "cross_fiber"
                label = f"{src_base}->{tgt_base}"

            fiber_mor = FiberMorphism(
                source=src_obj,
                target=tgt_obj,
                morphism_type=morph_type,
                weight=mor.confidence,
                transition_label=label,
            )
            self.total_morphisms.append(fiber_mor)
            src_key = (src_base, mor.source_name)
            self._adjacency.setdefault(src_key, []).append(fiber_mor)

        return self

    def cartesian_lift(self, source_base: str, target_base: str,
                       fiber_name: str) -> List[str]:
        """
        Given an object in source_base fiber, find corresponding
        objects in target_base fiber via Cartesian lift.

        Returns list of fiber object names reachable in target_base.
        """
        lifted = []
        source_key = (source_base, fiber_name)

        if source_key not in self._object_index:
            return lifted

        for morphism in self._adjacency.get(source_key, []):
            if morphism.target.base == target_base:
                if morphism.target.fiber not in lifted:
                    lifted.append(morphism.target.fiber)

        return lifted

    def find_cross_fiber_paths(self, max_pivots: int = 3,
                               max_length: int = 8) -> List[List[FiberObject]]:
        """
        Find paths that cross fiber boundaries.

        Returns list of chains that cross at least one fiber boundary.
        """
        chains: List[List[FiberObject]] = []

        for start_obj in self.total_objects:
            queue = [(start_obj, [start_obj], {start_obj.base}, 0)]
            visited: Set[Tuple[str, str, int]] = set()

            while queue:
                current, chain, bases, pivots = queue.pop(0)

                if len(chain) > max_length:
                    continue

                if pivots >= 1 and len(chain) >= 2:
                    chains.append(list(chain))

                if len(chains) >= 200:
                    return chains

                current_key = (current.base, current.fiber)
                state_key = (current.base, current.fiber, pivots)
                if state_key in visited:
                    continue
                visited.add(state_key)

                for morphism in self._adjacency.get(current_key, []):
                    target = morphism.target
                    new_pivots = pivots
                    new_bases = set(bases)

                    if target.base != current.base:
                        new_pivots += 1
                        new_bases.add(target.base)

                    if new_pivots > max_pivots or len(chain) + 1 > max_length:
                        continue

                    target_state = (target.base, target.fiber, new_pivots)
                    if target_state not in visited:
                        queue.append((target, chain + [target], new_bases, new_pivots))

        return chains

    def optimal_cross_fiber_path(self, source_base: str, target_base: str,
                                 max_length: int = 6
                                 ) -> Optional[Tuple[List[FiberObject], float]]:
        """
        Find highest-weight path from any object in source_base
        to any object in target_base.

        Uses Dijkstra on -log(weight) for max-product path.
        """
        source_objs = self._fiber_objects.get(source_base, [])
        target_set = set(
            (obj.base, obj.fiber)
            for obj in self._fiber_objects.get(target_base, [])
        )

        if not source_objs or not target_set:
            return None

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

        best_key = None
        best_dist = float("inf")

        while pq:
            d, u_key = heapq.heappop(pq)

            if d > dist.get(u_key, float("inf")):
                continue

            if u_key in target_set and d < best_dist:
                best_dist = d
                best_key = u_key

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

        if best_key is None:
            return None

        path_keys = []
        current = best_key
        while current is not None:
            path_keys.append(current)
            current = prev.get(current)
        path_keys.reverse()

        path = [self._object_index[k] for k in path_keys]
        total_weight = math.exp(-best_dist)

        return (path, total_weight)

    def get_fiber_stats(self) -> Dict[str, Any]:
        """Get statistics about the total category."""
        within_count = sum(
            1 for m in self.total_morphisms if m.morphism_type == "within_fiber"
        )
        cross_count = sum(
            1 for m in self.total_morphisms if m.morphism_type == "cross_fiber"
        )

        fiber_obj_counts = {
            base: len(objs) for base, objs in self._fiber_objects.items()
        }

        return {
            "total_objects": len(self.total_objects),
            "total_morphisms": len(self.total_morphisms),
            "within_fiber_morphisms": within_count,
            "cross_fiber_morphisms": cross_count,
            "num_fibers": len(self._fiber_objects),
            "fiber_object_counts": fiber_obj_counts,
        }

    def get_fibers(self) -> List[str]:
        """Return list of base category objects (fiber names)."""
        return list(self._fiber_objects.keys())

    def get_fiber_objects(self, base: str) -> List[FiberObject]:
        """Return all objects in a given fiber."""
        return list(self._fiber_objects.get(base, []))

    def __repr__(self):
        stats = self.get_fiber_stats()
        return (
            f"GenericFibration(|Ob|={stats['total_objects']}, "
            f"|Mor|={stats['total_morphisms']}, "
            f"fibers={stats['num_fibers']})"
        )
