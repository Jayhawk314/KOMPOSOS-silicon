# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Enriched Category Theory: Categories over Monoidal Categories

A V-enriched category C replaces hom-SETS with hom-OBJECTS in V:
  - Hom(A,B) ∈ V instead of Hom(A,B) ∈ Set
  - Composition is a V-morphism: Hom(B,C) ⊗ Hom(A,B) → Hom(A,C)
  - Identity is a V-morphism: I → Hom(A,A)

Key instances:
  - V = ([0,1], ×, 1): Multiplicative quantale — product composition
  - V = ([0,∞], +, 0): Additive quantale — sum composition (Lawvere metric)
  - V = ([0,1], P-OR, 0): Probabilistic quantale — probabilistic OR composition

Mathematical basis:
  - Lawvere, "Metric spaces, generalized logic, and closed categories" (1973)
  - Fong & Spivak, "Seven Sketches in Compositionality", Def 2.46
  - Milewski, "Enriched Categories" (blog)
"""

import math
import heapq
from typing import TypeVar, Generic, Dict, Tuple, Callable, List, Optional, Any
from dataclasses import dataclass, field


V = TypeVar('V')


@dataclass
class MonoidalStructure(Generic[V]):
    """
    Defines (V, ⊗, I) — the monoidal category we enrich over.

    For a quantale (complete lattice with associative binary operation):
      tensor: V × V → V (the ⊗ operation, must be associative)
      unit: V            (identity for ⊗: I ⊗ a = a = a ⊗ I)
      compare: V × V → bool (the ≤ ordering for enrichment axioms)

    Examples:
      Multiplicative: ([0,1], ×, 1, ≥)  — product, higher is better
      Additive:       ([0,∞], +, 0, ≤)  — sum, lower is better
      Probabilistic:  ([0,1], P-OR, 0, ≤) — probability, lower is better
    """
    tensor: Callable[[Any, Any], Any]
    unit: Any
    compare: Callable[[Any, Any], bool] = field(default=lambda: lambda a, b: a <= b)
    name: str = "V"

    def __post_init__(self):
        if callable(self.compare) and not isinstance(self.compare, type(lambda: None)):
            pass  # Already a callable


# Pre-built monoidal structures (common quantale types)

MULTIPLICATIVE_QUANTALE = MonoidalStructure(
    tensor=lambda a, b: a * b,
    unit=1.0,
    compare=lambda a, b: a >= b,  # Higher is "better" (reversed order)
    name="Multiplicative([0,1], ×, 1)"
)

ADDITIVE_QUANTALE = MonoidalStructure(
    tensor=lambda a, b: a + b,
    unit=0.0,
    compare=lambda a, b: a <= b,  # Lower is "better"
    name="Additive([0,∞], +, 0)"
)

PROBABILISTIC_QUANTALE = MonoidalStructure(
    tensor=lambda a, b: 1 - (1 - a) * (1 - b),  # Probabilistic OR
    unit=0.0,
    compare=lambda a, b: a <= b,  # Lower is "better"
    name="Probabilistic([0,1], P-OR, 0)"
)

SUCCESS_QUANTALE = MonoidalStructure(
    tensor=lambda a, b: a * b,  # Joint probability
    unit=1.0,
    compare=lambda a, b: a >= b,  # Higher success is "better"
    name="Success([0,1], ×, 1)"
)

MIN_QUANTALE = MonoidalStructure(
    tensor=lambda a, b: min(a, b),  # Bottleneck: weakest link limits path quality
    unit=1.0,
    compare=lambda a, b: a >= b,  # Higher = better
    name="Min([0,1], min, 1)"
)

# Backward-compatible aliases
STEALTH_QUANTALE = MULTIPLICATIVE_QUANTALE
COST_QUANTALE = ADDITIVE_QUANTALE
RISK_QUANTALE = PROBABILISTIC_QUANTALE
ACTIVITY_QUANTALE = MIN_QUANTALE


class EnrichedCategory:
    """
    Category enriched over monoidal category (V, ⊗, I).

    Instead of Hom-SETS, we have Hom-OBJECTS in V.
    Composition is a V-morphism, not a set function.

    Axioms satisfied:
      1. Identity: I ≤ Hom(A,A) for all objects A
      2. Composition: Hom(A,B) ⊗ Hom(B,C) ≤ Hom(A,C) for all A,B,C
    """

    def __init__(self, monoidal: MonoidalStructure):
        self.monoidal = monoidal
        self.objects: Dict[str, dict] = {}
        self.hom_objects: Dict[Tuple[str, str], Any] = {}
        self._adjacency: Dict[str, List[str]] = {}  # Forward adjacency for path finding

    def add_object(self, name: str, metadata: dict = None) -> str:
        """Add an object to the enriched category."""
        self.objects[name] = metadata or {}
        if name not in self._adjacency:
            self._adjacency[name] = []
        # Identity axiom: I ≤ Hom(A,A)
        self.hom_objects[(name, name)] = self.monoidal.unit
        return name

    def set_hom(self, source: str, target: str, value: Any):
        """
        Set the hom-object Hom(source, target) = value ∈ V.

        For stealth: value ∈ [0,1] is the stealth of the transition.
        For cost: value ∈ [0,∞] is the cost of the transition.
        """
        if source not in self.objects:
            self.add_object(source)
        if target not in self.objects:
            self.add_object(target)

        self.hom_objects[(source, target)] = value

        if target not in self._adjacency.get(source, []):
            self._adjacency.setdefault(source, []).append(target)

    def get_hom(self, source: str, target: str) -> Optional[Any]:
        """Get the hom-object Hom(source, target)."""
        return self.hom_objects.get((source, target))

    def compose(self, A: str, B: str, C: str) -> Optional[Any]:
        """
        Compute enriched composition: Hom(A,B) ⊗ Hom(B,C) → Hom(A,C).

        Returns the ⊗-product, or None if either hom-object doesn't exist.
        """
        h_ab = self.hom_objects.get((A, B))
        h_bc = self.hom_objects.get((B, C))
        if h_ab is None or h_bc is None:
            return None
        return self.monoidal.tensor(h_ab, h_bc)

    def path_weight(self, path: List[str]) -> Optional[Any]:
        """
        Compute total weight along a path via iterated ⊗.

        For stealth: product of individual stealth scores.
        For cost: sum of individual costs.
        """
        if len(path) < 2:
            return self.monoidal.unit

        weight = self.monoidal.unit
        for i in range(len(path) - 1):
            h = self.hom_objects.get((path[i], path[i + 1]))
            if h is None:
                return None
            weight = self.monoidal.tensor(weight, h)
        return weight

    def verify_composition_axiom(self, A: str, B: str, C: str) -> bool:
        """
        Verify: Hom(A,B) ⊗ Hom(B,C) ≤ Hom(A,C).

        If Hom(A,C) doesn't exist, the axiom is trivially satisfied
        (the enriched hom defaults to a "bottom" value).
        """
        composed = self.compose(A, B, C)
        if composed is None:
            return True

        direct = self.hom_objects.get((A, C))
        if direct is None:
            return True

        return self.monoidal.compare(composed, direct)

    def check_commutativity(self, path1: List[str], path2: List[str]) -> Dict[str, Any]:
        """
        Check whether two paths between the same endpoints yield the same
        enriched hom-value. Non-commutativity = AT contradiction.

        Args:
            path1: First path as list of object names.
            path2: Second path as list of object names.

        Returns:
            {
                "commutes": bool,
                "path1_weight": enriched value or None,
                "path2_weight": enriched value or None,
                "tension": float (0.0 = commutes, higher = greater contradiction)
            }
        """
        w1 = self.path_weight(path1)
        w2 = self.path_weight(path2)

        result: Dict[str, Any] = {
            "commutes": False,
            "path1_weight": w1,
            "path2_weight": w2,
            "tension": 0.0,
        }

        if w1 is None or w2 is None:
            # Cannot compare — treat as non-commuting with zero tension
            result["tension"] = 0.0
            return result

        # Check equality within tolerance
        try:
            diff = abs(float(w1) - float(w2))
            result["commutes"] = diff < 1e-9

            # Compute tension: magnitude of non-commutativity
            if diff < 1e-9:
                result["tension"] = 0.0
            else:
                # For multiplicative quantales, use log-ratio
                # For additive quantales, use absolute difference
                fw1, fw2 = float(w1), float(w2)
                if fw1 > 0 and fw2 > 0:
                    result["tension"] = abs(math.log(fw1) - math.log(fw2))
                else:
                    result["tension"] = diff
        except (TypeError, ValueError):
            # Non-numeric hom-objects — fall back to equality check
            result["commutes"] = w1 == w2
            result["tension"] = 0.0 if result["commutes"] else 1.0

        return result

    def optimal_path(self, source: str, target: str,
                     maximize: bool = True,
                     max_length: int = 10) -> Optional[Tuple[List[str], Any]]:
        """
        Find optimal path from source to target.

        For stealth (V = [0,1], ⊗ = ×, maximize=True):
          Stealthiest path: max ∏ stealth_i
          Uses DPERO log transform: max ∏ w_i ↔ min ∑ (-log w_i)

        For cost (V = [0,∞], ⊗ = +, maximize=False):
          Cheapest path: min ∑ cost_i (standard Dijkstra)

        Args:
            source: Start node
            target: End node
            maximize: True for max-product (stealth), False for min-sum (cost)
            max_length: Maximum path length

        Returns:
            (path, total_weight) or None if no path exists
        """
        if source not in self.objects or target not in self.objects:
            return None

        if source == target:
            return ([source], self.monoidal.unit)

        # Transform multiplicative optimization to additive via log
        # max ∏ w_i ↔ min ∑ (-log w_i)  [DPERO transform]
        def edge_cost(s: str, t: str) -> float:
            w = self.hom_objects.get((s, t))
            if w is None:
                return float('inf')
            if maximize:
                # Multiplicative: convert to additive via -log
                if w <= 0:
                    return float('inf')
                return -math.log(w)
            else:
                # Already additive
                return float(w)

        # Dijkstra's algorithm on transformed weights
        dist: Dict[str, float] = {obj: float('inf') for obj in self.objects}
        prev: Dict[str, Optional[str]] = {obj: None for obj in self.objects}
        path_len: Dict[str, int] = {obj: 0 for obj in self.objects}
        dist[source] = 0.0

        # Priority queue: (distance, node_id)
        pq = [(0.0, source)]

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
                if cost == float('inf'):
                    continue

                new_dist = dist[u] + cost
                if new_dist < dist[v]:
                    dist[v] = new_dist
                    prev[v] = u
                    path_len[v] = path_len[u] + 1
                    heapq.heappush(pq, (new_dist, v))

        # Reconstruct path
        if dist[target] == float('inf'):
            return None

        path = []
        current = target
        while current is not None:
            path.append(current)
            current = prev[current]
        path.reverse()

        # Compute actual weight using original ⊗
        total_weight = self.path_weight(path)

        return (path, total_weight)

    def top_k_paths(self, source: str, target: str,
                    k: int = 5, maximize: bool = True,
                    max_length: int = 10) -> List[Tuple[List[str], Any]]:
        """
        Find top-k optimal paths using Yen's algorithm variant.

        Returns list of (path, weight) tuples sorted by optimality.
        """
        results = []

        # Get the best path first
        best = self.optimal_path(source, target, maximize, max_length)
        if best is None:
            return []
        results.append(best)

        # Find alternatives by removing edges from best path
        # Simplified Yen's: try blocking each intermediate node
        for block_idx in range(1, len(best[0]) - 1):
            blocked_node = best[0][block_idx]

            # Temporarily remove adjacency
            saved = self._adjacency.get(blocked_node, [])
            saved_incoming = []
            for obj in self.objects:
                if blocked_node in self._adjacency.get(obj, []):
                    saved_incoming.append(obj)

            self._adjacency[blocked_node] = []
            for obj in saved_incoming:
                self._adjacency[obj] = [n for n in self._adjacency[obj] if n != blocked_node]

            alt = self.optimal_path(source, target, maximize, max_length)
            if alt and alt[0] not in [r[0] for r in results]:
                results.append(alt)

            # Restore
            self._adjacency[blocked_node] = saved
            for obj in saved_incoming:
                self._adjacency[obj].append(blocked_node)

            if len(results) >= k:
                break

        # Sort by weight
        if maximize:
            results.sort(key=lambda x: x[1] if x[1] is not None else 0, reverse=True)
        else:
            results.sort(key=lambda x: x[1] if x[1] is not None else float('inf'))

        return results[:k]

    def get_composable_successors(self, technique_id: str) -> List[Tuple[str, Any]]:
        """
        Get all objects that can follow technique_id with their hom-weights.

        Returns: List of (successor_id, hom_weight) tuples.
        """
        successors = []
        for target in self._adjacency.get(technique_id, []):
            weight = self.hom_objects.get((technique_id, target))
            if weight is not None:
                successors.append((target, weight))
        return successors

    def defense_priority(self) -> List[Tuple[str, float, int]]:
        """
        Rank techniques by how critical they are to high-weight paths.

        For each technique, compute how many optimal paths pass through it
        and how much blocking it degrades the max path weight.

        Returns: List of (technique_id, impact_score, path_count)
                 sorted by impact_score descending.
        """
        technique_impact: Dict[str, float] = {}
        technique_count: Dict[str, int] = {}

        # Get all initial access and impact/exfil techniques
        starts = [t for t, meta in self.objects.items()
                  if 'initial_access' in str(meta.get('tactics', ''))]
        ends = [t for t, meta in self.objects.items()
                if any(x in str(meta.get('tactics', ''))
                       for x in ['exfiltration', 'impact'])]

        if not starts or not ends:
            # Fallback: use all objects
            starts = list(self.objects.keys())[:5]
            ends = list(self.objects.keys())[-5:]

        # For each start/end pair, find optimal path and measure impact of removing each node
        for start in starts:
            for end in ends:
                if start == end:
                    continue

                best = self.optimal_path(start, end, maximize=True)
                if best is None:
                    continue

                best_path, best_weight = best
                if best_weight is None or best_weight <= 0:
                    continue

                for node in best_path[1:-1]:  # Skip start and end
                    technique_count[node] = technique_count.get(node, 0) + 1

                    # Measure impact of blocking this node
                    saved_adj = self._adjacency.get(node, [])
                    self._adjacency[node] = []

                    alt = self.optimal_path(start, end, maximize=True)
                    alt_weight = alt[1] if alt else 0

                    self._adjacency[node] = saved_adj

                    # Impact = how much blocking reduces the best path weight
                    impact = best_weight - (alt_weight or 0)
                    technique_impact[node] = technique_impact.get(node, 0) + impact

        # Sort by impact
        results = [
            (tech, impact, technique_count.get(tech, 0))
            for tech, impact in technique_impact.items()
        ]
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def __repr__(self):
        return (f"EnrichedCategory(V={self.monoidal.name}, "
                f"|Ob|={len(self.objects)}, "
                f"|Hom|={len(self.hom_objects)})")
