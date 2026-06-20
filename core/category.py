# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
The Fused Categorical Runtime

This is the heart of KOMPOSOS-IV. A Category that IS:
  - A categorical structure (objects, morphisms, composition, identity)
  - A persistence layer (SQLite, automatic)
  - An enriched category (hom-values over a quantale)
  - A hook-enabled runtime (events on structural changes)

KOMPOSOS-III needed: KomposOSStore + Category + EnrichedCategory + StoreAdapter
KOMPOSOS-IV needs:   Category

One class. Zero translation seams.

Inspired by Orion's insight: the runtime IS the category.
Composition IS execution. Hooks ARE structural.
"""

from __future__ import annotations
import math
import heapq
from collections import defaultdict
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, Union,
)

from .types import Object, Morphism, Path, HigherMorphism, EquivalenceClass, Cone, Cocone
from .enrichment import MonoidalStructure, MULTIPLICATIVE_QUANTALE
from .persistence import SQLiteBackend
from .hooks import HookRegistry


class Category:
    """
    The fused categorical runtime.

    Objects and morphisms persist automatically.
    Enrichment scores are intrinsic to morphisms.
    Composition updates persistence + enrichment + fires hooks.
    Path finding unifies BFS and Dijkstra.

    Usage:
        cat = Category("my_domain")
        a = cat.add("A", type_name="concept")
        b = cat.add("B")
        f = cat.connect("A", "B", confidence=0.9)
        g = cat.connect("B", "C", confidence=0.8)
        h = cat.compose(f, g)
        # h.confidence == 0.72 (0.9 * 0.8 via multiplicative quantale)
        # h is already persisted in SQLite
        # hooks fired on each operation
    """

    def __init__(
        self,
        name: str = "default",
        db_path: str = ":memory:",
        quantale: MonoidalStructure = None,
    ):
        self.name = name
        self.quantale = quantale or MULTIPLICATIVE_QUANTALE
        self._backend = SQLiteBackend(db_path)
        self._hooks = HookRegistry()

        # In-memory indexes for fast access
        self._objects: Dict[str, Object] = {}
        self._morphisms: Dict[str, Morphism] = {}
        self._adjacency: Dict[str, List[str]] = defaultdict(list)
        self._reverse_adjacency: Dict[str, List[str]] = defaultdict(list)
        self._hom_values: Dict[Tuple[str, str], float] = {}

    # =================================================================
    # Object operations
    # =================================================================

    def add_object(self, obj: Object) -> Object:
        """
        Add an object to the category.

        Persists to SQLite, indexes in memory, sets identity hom-value,
        fires "object_added" hook.
        """
        obj._category = self
        self._backend.insert_object(obj)
        self._objects[obj.name] = obj
        # Identity axiom: I <= Hom(A,A)
        self._hom_values[(obj.name, obj.name)] = self.quantale.unit
        self._hooks.fire("object_added", object=obj)
        return obj

    def add(self, name: str, **kwargs) -> Object:
        """
        Shorthand for adding an object by name.

        cat.add("A", type_name="concept", metadata={"weight": 1.0})
        """
        return self.add_object(Object(name=name, **kwargs))

    def get(self, name: str) -> Optional[Object]:
        """
        Get an object by name.

        Checks in-memory cache first, falls back to SQLite.
        """
        if name in self._objects:
            return self._objects[name]
        obj = self._backend.get_object(name)
        if obj:
            obj._category = self
            self._objects[name] = obj
        return obj

    def remove_object(self, name: str) -> bool:
        """
        Remove an object and all its morphisms.

        Fires "object_removed" hook.
        """
        obj = self._objects.pop(name, None)
        if obj is None:
            return False

        # Remove morphisms touching this object
        to_remove = [
            mid for mid, m in self._morphisms.items()
            if m.source == name or m.target == name
        ]
        for mid in to_remove:
            m = self._morphisms.pop(mid)
            if m.target in self._adjacency.get(m.source, []):
                self._adjacency[m.source].remove(m.target)
            if m.source in self._reverse_adjacency.get(m.target, []):
                self._reverse_adjacency[m.target].remove(m.source)
            self._hom_values.pop((m.source, m.target), None)

        # Remove identity
        self._hom_values.pop((name, name), None)

        self._backend.delete_object(name)
        self._hooks.fire("object_removed", object=obj)
        return True

    def objects(self) -> List[Object]:
        """List all objects in the category."""
        if self._objects:
            return list(self._objects.values())
        return self._backend.list_objects()

    # =================================================================
    # Morphism operations
    # =================================================================

    def add_morphism(self, mor: Morphism) -> Morphism:
        """
        Add a morphism to the category.

        Persists to SQLite, updates adjacency + enrichment, fires hook.
        Auto-creates source/target objects if they don't exist.
        """
        # Auto-create endpoints if needed
        if mor.source not in self._objects:
            if self._backend.get_object(mor.source) is None:
                self.add(mor.source)
            else:
                obj = self._backend.get_object(mor.source)
                obj._category = self
                self._objects[mor.source] = obj

        if mor.target not in self._objects:
            if self._backend.get_object(mor.target) is None:
                self.add(mor.target)
            else:
                obj = self._backend.get_object(mor.target)
                obj._category = self
                self._objects[mor.target] = obj

        mor._category = self
        self._backend.insert_morphism(mor)
        self._morphisms[mor.id] = mor
        if mor.target not in self._adjacency[mor.source]:
            self._adjacency[mor.source].append(mor.target)
        if mor.source not in self._reverse_adjacency[mor.target]:
            self._reverse_adjacency[mor.target].append(mor.source)
        self._hom_values[(mor.source, mor.target)] = mor.confidence
        self._hooks.fire("morphism_added", morphism=mor)
        return mor

    def connect(
        self,
        source: str,
        target: str,
        name: str = "r",
        confidence: float = 1.0,
        fn: Callable = None,
        **metadata,
    ) -> Morphism:
        """
        Shorthand for adding a morphism between two objects.

        cat.connect("A", "B", name="influences", confidence=0.9)
        """
        mor = Morphism(
            name=name,
            source=source,
            target=target,
            confidence=confidence,
            metadata=metadata,
            _fn=fn,
        )
        return self.add_morphism(mor)

    def remove_morphism(self, mor_id: str) -> bool:
        """
        Remove a single morphism by id, reversing all index updates from
        add_morphism. Fires "morphism_removed" hook. Returns True if removed.

        Note: confidence is keyed per (source, target) in _hom_values, so it is
        only dropped when no other morphism remains between that pair.
        """
        m = self._morphisms.pop(mor_id, None)
        if m is None:
            self._backend.delete_morphism(mor_id)
            return False

        remaining = [
            o for o in self._morphisms.values()
            if o.source == m.source and o.target == m.target
        ]
        if not remaining:
            if m.target in self._adjacency.get(m.source, []):
                self._adjacency[m.source].remove(m.target)
            if m.source in self._reverse_adjacency.get(m.target, []):
                self._reverse_adjacency[m.target].remove(m.source)
            self._hom_values.pop((m.source, m.target), None)

        self._backend.delete_morphism(mor_id)
        self._hooks.fire("morphism_removed", morphism=m)
        return True

    def get_morphism(self, mor_id: str) -> Optional[Morphism]:
        """Get a morphism by ID."""
        if mor_id in self._morphisms:
            return self._morphisms[mor_id]
        mor = self._backend.get_morphism(mor_id)
        if mor:
            mor._category = self
            self._morphisms[mor_id] = mor
        return mor

    def morphisms_from(self, source: str) -> List[Morphism]:
        """All morphisms out of source."""
        return [
            m for m in self._morphisms.values()
            if m.source == source
        ] or self._backend.get_morphisms_from(source)

    def morphisms_to(self, target: str) -> List[Morphism]:
        """All morphisms into target."""
        return [
            m for m in self._morphisms.values()
            if m.target == target
        ] or self._backend.get_morphisms_to(target)

    def morphisms(self) -> List[Morphism]:
        """List all morphisms."""
        if self._morphisms:
            return list(self._morphisms.values())
        return self._backend.list_morphisms()

    def neighbors(self, name: str) -> Dict[str, List[str]]:
        """Outgoing and incoming neighbors of an object."""
        return {
            "outgoing": list(self._adjacency.get(name, [])),
            "incoming": list(self._reverse_adjacency.get(name, [])),
        }

    # =================================================================
    # Composition (THE key operation)
    # =================================================================

    def compose(self, f: Morphism, g: Morphism) -> Morphism:
        """
        Compose g after f: g . f (f runs first, then g).

        This is where III's 3-way split becomes IV's single operation:
          1. Creates composed morphism (categorical)
          2. Persists it (store)
          3. Updates enriched weight via quantale tensor (enriched)
          4. Composes callables if both are callable (execution)
          5. Fires "composed" hook (runtime)

        Args:
            f: First morphism (runs first).
            g: Second morphism (runs second). g.source must == f.target.

        Returns:
            The composed morphism g.f with enriched confidence.

        Raises:
            TypeError: If f.target != g.source (not composable).
        """
        if f.target != g.source:
            raise TypeError(
                f"Cannot compose: {f.name} targets '{f.target}' "
                f"but {g.name} sources '{g.source}'"
            )

        # Enriched composition via quantale tensor
        composed_confidence = self.quantale.tensor(f.confidence, g.confidence)

        # Compose callables if both have them
        composed_fn = None
        if f._fn and g._fn:
            f_fn, g_fn = f._fn, g._fn
            composed_fn = lambda *args, **kw: g_fn(f_fn(*args, **kw))

        composed = Morphism(
            name=f"{g.name}.{f.name}",
            source=f.source,
            target=g.target,
            confidence=composed_confidence,
            metadata={"composed_from": [f.name, g.name]},
            _fn=composed_fn,
        )

        result = self.add_morphism(composed)
        self._hooks.fire("composed", f=f, g=g, result=result)
        return result

    # =================================================================
    # Enrichment queries
    # =================================================================

    def hom(self, source: str, target: str) -> Optional[float]:
        """Get the enriched hom-value Hom(source, target)."""
        return self._hom_values.get((source, target))

    def path_weight(self, path: List[str]) -> Optional[float]:
        """
        Compute total weight along a path via iterated tensor.

        Args:
            path: List of object names forming the path.

        Returns:
            Total enriched weight, or None if any edge is missing.
        """
        if len(path) < 2:
            return self.quantale.unit

        weight = self.quantale.unit
        for i in range(len(path) - 1):
            h = self._hom_values.get((path[i], path[i + 1]))
            if h is None:
                return None
            weight = self.quantale.tensor(weight, h)
        return weight

    def verify_composition_axiom(self, a: str, b: str, c: str) -> bool:
        """
        Verify enrichment axiom: Hom(A,B) tensor Hom(B,C) <= Hom(A,C).

        Returns True if the axiom holds (or is vacuously true).
        """
        h_ab = self._hom_values.get((a, b))
        h_bc = self._hom_values.get((b, c))
        if h_ab is None or h_bc is None:
            return True
        composed = self.quantale.tensor(h_ab, h_bc)
        direct = self._hom_values.get((a, c))
        if direct is None:
            return True
        return self.quantale.compare(composed, direct)

    # =================================================================
    # Path finding
    # =================================================================

    def find_paths(
        self, source: str, target: str, max_length: int = 10
    ) -> List[Path]:
        """
        BFS path finding through the morphism graph.

        Returns all simple paths up to max_length edges.
        """
        results: List[Path] = []
        # (current_node, morphism_ids, visited_nodes)
        queue: List[Tuple[str, List[str], Set[str]]] = [
            (source, [], {source})
        ]

        while queue:
            current, path_so_far, visited = queue.pop(0)

            if current == target and path_so_far:
                weight = self.quantale.unit
                for mid in path_so_far:
                    mor = self._morphisms.get(mid)
                    if mor:
                        weight = self.quantale.tensor(weight, mor.confidence)
                results.append(Path(
                    morphism_ids=path_so_far,
                    source=source,
                    target=target,
                    weight=weight,
                ))
                continue

            if len(path_so_far) >= max_length:
                continue

            for m in self._morphisms.values():
                if m.source == current and m.target not in visited:
                    queue.append((
                        m.target,
                        path_so_far + [m.id],
                        visited | {m.target},
                    ))

        return results

    def optimal_path(
        self,
        source: str,
        target: str,
        maximize: bool = True,
        max_length: int = 10,
    ) -> Optional[Tuple[List[str], float]]:
        """
        Dijkstra on enriched weights.

        For multiplicative quantale (maximize=True):
          max product via -log transform (DPERO).
        For additive quantale (maximize=False):
          min sum (standard Dijkstra).

        Args:
            source: Start object name.
            target: End object name.
            maximize: True for max-product, False for min-sum.
            max_length: Maximum path length.

        Returns:
            (path_as_object_names, total_weight) or None if no path.
        """
        if source not in self._objects and self._backend.get_object(source) is None:
            return None
        if target not in self._objects and self._backend.get_object(target) is None:
            return None

        if source == target:
            return ([source], self.quantale.unit)

        def edge_cost(s: str, t: str) -> float:
            w = self._hom_values.get((s, t))
            if w is None:
                return float("inf")
            if maximize:
                if w <= 0:
                    return float("inf")
                return -math.log(w)
            else:
                return float(w)

        # Collect all known objects
        all_objects = set(self._objects.keys())
        all_objects.update(self._adjacency.keys())
        for targets in self._adjacency.values():
            all_objects.update(targets)

        dist: Dict[str, float] = {obj: float("inf") for obj in all_objects}
        prev: Dict[str, Optional[str]] = {obj: None for obj in all_objects}
        path_len: Dict[str, int] = {obj: 0 for obj in all_objects}
        dist[source] = 0.0

        pq: List[Tuple[float, str]] = [(0.0, source)]

        while pq:
            d, u = heapq.heappop(pq)

            if d > dist[u]:
                continue

            if u == target:
                break

            if path_len[u] >= max_length:
                continue

            for v in self._adjacency.get(u, []):
                cost = edge_cost(u, v)
                if cost == float("inf"):
                    continue

                new_dist = dist[u] + cost
                if new_dist < dist[v]:
                    dist[v] = new_dist
                    prev[v] = u
                    path_len[v] = path_len[u] + 1
                    heapq.heappush(pq, (new_dist, v))

        if dist.get(target, float("inf")) == float("inf"):
            return None

        # Reconstruct path
        path: List[str] = []
        current: Optional[str] = target
        while current is not None:
            path.append(current)
            current = prev.get(current)
        path.reverse()

        total_weight = self.path_weight(path)
        if total_weight is None:
            return None

        self._hooks.fire("path_found", path=path, weight=total_weight)
        return (path, total_weight)

    def top_k_paths(
        self,
        source: str,
        target: str,
        k: int = 5,
        maximize: bool = True,
        max_length: int = 10,
    ) -> List[Tuple[List[str], float]]:
        """
        Find top-k optimal paths (simplified Yen's algorithm).

        Returns list of (path, weight) sorted by optimality.
        """
        results: List[Tuple[List[str], float]] = []

        best = self.optimal_path(source, target, maximize, max_length)
        if best is None:
            return []
        results.append(best)

        # Try blocking each intermediate node to find alternatives
        for block_idx in range(1, len(best[0]) - 1):
            blocked_node = best[0][block_idx]

            # Temporarily remove from adjacency
            saved_out = self._adjacency.get(blocked_node, [])
            saved_in = [
                obj for obj in self._adjacency
                if blocked_node in self._adjacency[obj]
            ]

            self._adjacency[blocked_node] = []
            for obj in saved_in:
                self._adjacency[obj] = [
                    n for n in self._adjacency[obj] if n != blocked_node
                ]

            alt = self.optimal_path(source, target, maximize, max_length)
            if alt and alt[0] not in [r[0] for r in results]:
                results.append(alt)

            # Restore
            self._adjacency[blocked_node] = saved_out
            for obj in saved_in:
                self._adjacency[obj].append(blocked_node)

            if len(results) >= k:
                break

        if maximize:
            results.sort(
                key=lambda x: x[1] if x[1] is not None else 0,
                reverse=True,
            )
        else:
            results.sort(
                key=lambda x: x[1] if x[1] is not None else float("inf"),
            )

        return results[:k]

    # =================================================================
    # Bulk operations
    # =================================================================

    def bulk_add(
        self,
        objects: List[Object],
        morphisms: List[Morphism],
    ) -> Dict[str, int]:
        """
        Load objects and morphisms in bulk.

        For bridge compatibility: load domain data into the category
        in a single call.
        """
        obj_count = 0
        for obj in objects:
            self.add_object(obj)
            obj_count += 1

        mor_count = 0
        for mor in morphisms:
            self.add_morphism(mor)
            mor_count += 1

        self._hooks.fire(
            "bulk_loaded", objects=obj_count, morphisms=mor_count
        )
        return {"objects": obj_count, "morphisms": mor_count}

    # =================================================================
    # Statistics / introspection
    # =================================================================

    def statistics(self) -> Dict[str, Any]:
        """Object count, morphism count, type distribution."""
        stats = self._backend.get_statistics()
        stats["in_memory_objects"] = len(self._objects)
        stats["in_memory_morphisms"] = len(self._morphisms)
        stats["hom_values"] = len(self._hom_values)
        stats["quantale"] = self.quantale.name
        return stats

    # =================================================================
    # Export (for geometry/topology modules)
    # =================================================================

    def as_edges(self) -> List[Tuple[str, str, float]]:
        """
        Export as (source, target, weight) triples.

        For modules that need raw graph data (curvature, homology).
        Replaces StoreAdapter from KOMPOSOS-III.
        """
        edges = []
        for (s, t), w in self._hom_values.items():
            if s != t:  # Skip identity hom-values
                edges.append((s, t, w))
        return edges

    def as_adjacency(self) -> Dict[str, Set[str]]:
        """Export as adjacency dict for curvature computation."""
        return {k: set(v) for k, v in self._adjacency.items()}

    def as_weighted_adjacency(self) -> Dict[str, List[Tuple[str, float]]]:
        """Export as weighted adjacency dict."""
        result: Dict[str, List[Tuple[str, float]]] = {}
        for source, targets in self._adjacency.items():
            result[source] = []
            for t in targets:
                w = self._hom_values.get((source, t), self.quantale.unit)
                result[source].append((t, w))
        return result

    # =================================================================
    # Hook registration
    # =================================================================

    def on(self, event: str, fn: Callable) -> None:
        """Register a hook: cat.on("morphism_added", my_fn)"""
        self._hooks.on(event, fn)

    def off(self, event: str, fn: Callable) -> bool:
        """Unregister a hook."""
        return self._hooks.off(event, fn)

    # =================================================================
    # Functors
    # =================================================================

    def functor_to(
        self,
        target: Category,
        object_map: Dict[str, str],
        morphism_map: Dict[str, str] = None,
    ):
        """
        Create a functor from this category to target.

        If morphism_map is None, auto-infer: for each morphism A→B in self,
        map to the unique morphism F(A)→F(B) in target (if one exists).

        Args:
            target: Target category D.
            object_map: Object name in self → object name in target.
            morphism_map: Morphism ID in self → morphism ID in target.
                          Auto-inferred if None.

        Returns:
            A Functor from self to target.
        """
        from .functor import Functor

        if morphism_map is None:
            morphism_map = {}
            for mor in self.morphisms():
                mapped_src = object_map.get(mor.source)
                mapped_tgt = object_map.get(mor.target)
                if mapped_src is None or mapped_tgt is None:
                    continue
                # Find matching morphism in target
                candidates = [
                    m for m in target.morphisms()
                    if m.source == mapped_src and m.target == mapped_tgt
                ]
                if len(candidates) == 1:
                    morphism_map[mor.id] = candidates[0].id

        return Functor(
            name=f"{self.name}->{target.name}",
            source=self,
            target=target,
            _object_map=object_map,
            _morphism_map=morphism_map,
        )

    # =================================================================
    # Limits and Colimits
    # =================================================================

    def product(self, a: str, b: str) -> Cone:
        """Binary product: A×B with projections."""
        from .limits import product
        return product(self, a, b)

    def coproduct(self, a: str, b: str) -> Cocone:
        """Binary coproduct: A+B with injections."""
        from .limits import coproduct
        return coproduct(self, a, b)

    def pullback(self, f_id: str, g_id: str) -> Cone:
        """Pullback over cospan f: A→C, g: B→C."""
        from .limits import pullback
        return pullback(self, f_id, g_id)

    def pushout(self, f_id: str, g_id: str) -> Cocone:
        """Pushout over span f: C→A, g: C→B."""
        from .limits import pushout
        return pushout(self, f_id, g_id)

    def terminal(self) -> str:
        """Create terminal object with morphisms from all objects."""
        from .limits import terminal
        return terminal(self)

    def initial(self) -> str:
        """Create initial object with morphisms to all objects."""
        from .limits import initial
        return initial(self)

    # =================================================================
    # Context manager
    # =================================================================

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._backend.close()

    # =================================================================
    # Repr
    # =================================================================

    def __repr__(self) -> str:
        return (
            f"Category('{self.name}', "
            f"|Ob|={len(self._objects)}, "
            f"|Mor|={len(self._morphisms)}, "
            f"V={self.quantale.name})"
        )
