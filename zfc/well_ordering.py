# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
Well-Ordering and Transfinite Induction — The ZFC Path System

Sits on top of universe.py the way cubical/paths.py sits on category.py.

cubical/paths.py: Interval → PathType → Square → Cube → parallel paths
well_ordering.py: Ordinal → WellOrder → TransfiniteInduction → canonical order

The fundamental difference:
- Cubical paths give you MANY paths between two points (parallel exploration)
- Well-ordering gives you ONE canonical ordering of everything (linear authority)

In HoTT, two paths can be homotopic (same journey, different routes).
In ZFC, the well-ordering is UNIQUE (up to isomorphism) for each ordinal.

This difference is WHERE the delta lives:
- CAT: "there are 3 paths from FLT3 to MYC, 2 are homotopic"
- ZFC: "FLT3 has rank 7, MYC has rank 12, the canonical chain is..."

When CAT says two paths are equivalent but ZFC ranks them differently,
that's a structural insight neither could find alone.

Components:
1. Ordinal       — transfinite numbers (0, 1, 2, ..., ω, ω+1, ...)
2. WellOrder     — a total order with no infinite descending chains
3. Rank          — the Von Neumann rank of a set (depth in the hierarchy)
4. Induction     — transfinite induction over well-ordered sets
5. OrdinalOracle — prediction via rank comparison and inductive reasoning
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any, Callable, Dict, List, Optional, Set as PySet,
    Tuple,
)

from .universe import Universe, ZFSet, Relation


# ═══════════════════════════════════════════════════════════════════
# Ordinals — transfinite numbers
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Ordinal:
    """
    An ordinal number in the Von Neumann encoding.

    0 = ∅
    1 = {∅} = {0}
    2 = {∅, {∅}} = {0, 1}
    n = {0, 1, ..., n-1}
    ω = {0, 1, 2, ...}     (first infinite ordinal)

    Mirror of: cubical DimensionVar
    DimensionVar names a dimension for parallel exploration.
    Ordinal names a POSITION in a canonical sequence.

    Ordinals are how ZFC talks about "how far along" something is.
    Cubical dimensions are how HoTT talks about "which direction" to go.
    """
    value: int  # finite ordinals for now
    name: Optional[str] = None
    is_limit: bool = False  # True for ω, ω·2, etc.

    def __post_init__(self):
        if self.name is None:
            self.name = str(self.value)

    def successor(self) -> Ordinal:
        """α + 1."""
        return Ordinal(value=self.value + 1)

    def __lt__(self, other: Ordinal) -> bool:
        return self.value < other.value

    def __le__(self, other: Ordinal) -> bool:
        return self.value <= other.value

    def __eq__(self, other) -> bool:
        if isinstance(other, Ordinal):
            return self.value == other.value
        return False

    def __hash__(self):
        return hash(self.value)

    def __repr__(self):
        if self.is_limit:
            return f"ω" if self.name == "ω" else self.name
        return self.name


# Standard ordinals
ZERO = Ordinal(0, "0")
OMEGA = Ordinal(value=0, name="ω", is_limit=True)  # placeholder for infinity


# ═══════════════════════════════════════════════════════════════════
# WellOrder — a total order with no infinite descending chains
# ═══════════════════════════════════════════════════════════════════

@dataclass
class WellOrder:
    """
    A well-ordering on a set.

    A well-order is a total order where every non-empty subset
    has a LEAST element. This guarantees:
    - No infinite descending chains
    - Transfinite induction works
    - Every element has a definite ordinal rank

    Mirror of: cubical PathType (I → A with boundary conditions)
    PathType is a function from the interval with endpoints.
    WellOrder is a function from ordinals to elements with minimum.

    PathType: "here's a continuous journey from a to b"
    WellOrder: "here's the canonical ranking of everything"
    """
    name: str
    elements: List[str] = field(default_factory=list)  # in order
    _rank_map: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        self._rebuild_ranks()

    def _rebuild_ranks(self):
        """Rebuild the rank map from element list."""
        self._rank_map = {e: i for i, e in enumerate(self.elements)}

    def rank(self, element: str) -> Optional[int]:
        """Get the ordinal rank of an element."""
        return self._rank_map.get(element)

    def at_rank(self, r: int) -> Optional[str]:
        """Get the element at a given rank."""
        if 0 <= r < len(self.elements):
            return self.elements[r]
        return None

    def compare(self, a: str, b: str) -> int:
        """
        Compare two elements in the well-ordering.
        Returns: -1 if a < b, 0 if a = b, 1 if a > b.
        """
        ra = self._rank_map.get(a)
        rb = self._rank_map.get(b)
        if ra is None or rb is None:
            raise ValueError(f"Element not in well-ordering")
        if ra < rb:
            return -1
        elif ra == rb:
            return 0
        return 1

    def least(self) -> Optional[str]:
        """The least element (exists by well-ordering)."""
        return self.elements[0] if self.elements else None

    def least_in(self, subset: PySet[str]) -> Optional[str]:
        """
        Least element of a non-empty subset.

        The well-ordering property guarantees this exists.
        """
        for e in self.elements:
            if e in subset:
                return e
        return None

    def predecessors(self, element: str) -> List[str]:
        """All elements less than the given element."""
        r = self._rank_map.get(element)
        if r is None:
            return []
        return self.elements[:r]

    def successors(self, element: str) -> List[str]:
        """All elements greater than the given element."""
        r = self._rank_map.get(element)
        if r is None:
            return []
        return self.elements[r + 1:]

    def segment(self, start: str, end: str) -> List[str]:
        """Elements between start and end (inclusive)."""
        rs = self._rank_map.get(start, 0)
        re = self._rank_map.get(end, len(self.elements))
        return self.elements[rs:re + 1]

    def is_valid(self) -> bool:
        """Check that the ordering is well-founded (no duplicates, etc.)."""
        return len(self.elements) == len(set(self.elements))

    def __len__(self):
        return len(self.elements)

    def __repr__(self):
        if len(self.elements) <= 10:
            return f"WellOrder({' < '.join(self.elements)})"
        return f"WellOrder({self.name}, |elements|={len(self.elements)})"


# ═══════════════════════════════════════════════════════════════════
# Von Neumann Rank — depth in the cumulative hierarchy
# ═══════════════════════════════════════════════════════════════════

def von_neumann_rank(universe: Universe, set_name: str,
                     _cache: Optional[Dict[str, int]] = None,
                     _depth: int = 0) -> int:
    """
    Compute the Von Neumann rank of a set.

    rank(∅) = 0
    rank(A) = sup{rank(x) + 1 : x ∈ A}

    The rank measures HOW DEEP a set is in the cumulative hierarchy V_α.
    Elements at rank 0 are "atoms" (empty or with no known elements).
    Higher rank = more complex = built from more layers.

    Mirror of: cubical path length
    Path length measures how many steps a journey takes.
    Rank measures how many layers deep a construction goes.
    """
    if _cache is None:
        _cache = {}
    if set_name in _cache:
        return _cache[set_name]

    if _depth > 1000:
        return _depth  # safety

    s = universe.sets.get(set_name)
    if s is None or len(s._elements) == 0:
        _cache[set_name] = 0
        return 0

    max_elem_rank = -1
    for elem_name in s._elements:
        elem_rank = von_neumann_rank(universe, elem_name, _cache, _depth + 1)
        if elem_rank > max_elem_rank:
            max_elem_rank = elem_rank

    rank = max_elem_rank + 1
    _cache[set_name] = rank
    return rank


def rank_all(universe: Universe) -> Dict[str, int]:
    """Compute Von Neumann rank for every set in the universe."""
    cache: Dict[str, int] = {}
    for name in universe.sets:
        von_neumann_rank(universe, name, cache)
    return cache


# ═══════════════════════════════════════════════════════════════════
# Well-Ordering Constructors
# ═══════════════════════════════════════════════════════════════════

def well_order_by_rank(universe: Universe) -> WellOrder:
    """
    Well-order the universe by Von Neumann rank.

    Lower rank = simpler = earlier in the ordering.
    Ties broken by name (lexicographic).

    This is the CANONICAL well-ordering — the one ZFC
    naturally induces on any universe.
    """
    ranks = rank_all(universe)
    sorted_names = sorted(ranks.keys(), key=lambda n: (ranks[n], n))
    return WellOrder(name="rank_order", elements=sorted_names)


def well_order_by_relation(universe: Universe,
                           relation: Relation) -> WellOrder:
    """
    Well-order elements using topological sort on a relation.

    If (a, b) ∈ R, then a comes before b in the ordering.
    Uses Kahn's algorithm for topological sort.

    Mirror of: Category.find_paths
    find_paths discovers all routes. This finds the ONE canonical order
    that respects all the arrows.
    """
    # Build adjacency and in-degree
    in_degree: Dict[str, int] = {}
    adjacency: Dict[str, List[str]] = {}
    all_nodes: PySet[str] = set()

    for (a, b) in relation.pairs:
        all_nodes.add(a)
        all_nodes.add(b)
        adjacency.setdefault(a, []).append(b)
        in_degree.setdefault(a, 0)
        in_degree[b] = in_degree.get(b, 0) + 1

    # Kahn's algorithm
    queue = sorted([n for n in all_nodes if in_degree.get(n, 0) == 0])
    result: List[str] = []

    while queue:
        # Take lexicographically smallest for determinism
        node = queue.pop(0)
        result.append(node)

        for neighbor in sorted(adjacency.get(node, [])):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
        queue.sort()

    # Add any remaining nodes (cycles — shouldn't happen in well-founded data)
    remaining = sorted(all_nodes - set(result))
    result.extend(remaining)

    return WellOrder(name=f"topo_{relation.name}", elements=result)


def well_order_by_key(elements: List[str],
                      key: Callable[[str], Any],
                      name: str = "custom") -> WellOrder:
    """Well-order by an arbitrary key function."""
    sorted_elems = sorted(elements, key=key)
    return WellOrder(name=name, elements=sorted_elems)


# ═══════════════════════════════════════════════════════════════════
# Transfinite Induction — reasoning over well-ordered sets
# ═══════════════════════════════════════════════════════════════════

@dataclass
class InductionResult:
    """Result of transfinite induction at a single step."""
    element: str
    rank: int
    value: Any
    predecessors_used: List[str]


def transfinite_induction(
    well_order: WellOrder,
    base_case: Callable[[str], Any],
    inductive_step: Callable[[str, int, Dict[str, Any]], Any],
    limit_step: Optional[Callable[[str, int, Dict[str, Any]], Any]] = None,
) -> Dict[str, InductionResult]:
    """
    Transfinite induction over a well-ordered set.

    For each element α in the well-ordering:
    1. If α is the least element: apply base_case(α)
    2. If α is a successor: apply inductive_step(α, rank, {predecessors → values})
    3. If α is a limit: apply limit_step(α, rank, {all predecessors → values})

    Mirror of: cubical hfill (filling the interior of a cube)
    hfill takes boundary data and computes the interior.
    Transfinite induction takes predecessor values and computes the next.

    Both are GAP-FILLING operations. One fills geometrically (interior of a shape).
    The other fills inductively (next element from previous ones).

    Args:
        well_order: the ordering to induct over
        base_case: what to compute for the first element
        inductive_step: what to compute given predecessors' values
        limit_step: what to compute at limit ordinals (default: same as inductive)

    Returns:
        Dict mapping each element to its InductionResult
    """
    if limit_step is None:
        limit_step = inductive_step

    results: Dict[str, InductionResult] = {}
    computed: Dict[str, Any] = {}

    for idx, element in enumerate(well_order.elements):
        if idx == 0:
            # Base case
            value = base_case(element)
            predecessors_used = []
        else:
            # Inductive step
            predecessors = well_order.elements[:idx]
            predecessor_values = {p: computed[p] for p in predecessors if p in computed}
            predecessors_used = list(predecessor_values.keys())
            value = inductive_step(element, idx, predecessor_values)

        computed[element] = value
        results[element] = InductionResult(
            element=element,
            rank=idx,
            value=value,
            predecessors_used=predecessors_used,
        )

    return results


def bounded_induction(
    well_order: WellOrder,
    base_case: Callable[[str], Any],
    inductive_step: Callable[[str, int, Dict[str, Any]], Any],
    max_predecessors: int = 10,
) -> Dict[str, InductionResult]:
    """
    Bounded transfinite induction — only look at recent predecessors.

    For large orderings, looking at ALL predecessors is expensive.
    This variant only passes the last N predecessors.

    Mirror of: CubicalGapFillingStrategy (bounded path length)
    """
    results: Dict[str, InductionResult] = {}
    computed: Dict[str, Any] = {}

    for idx, element in enumerate(well_order.elements):
        if idx == 0:
            value = base_case(element)
            predecessors_used = []
        else:
            start = max(0, idx - max_predecessors)
            predecessors = well_order.elements[start:idx]
            predecessor_values = {p: computed[p] for p in predecessors if p in computed}
            predecessors_used = list(predecessor_values.keys())
            value = inductive_step(element, idx, predecessor_values)

        computed[element] = value
        results[element] = InductionResult(
            element=element,
            rank=idx,
            value=value,
            predecessors_used=predecessors_used,
        )

    return results


# ═══════════════════════════════════════════════════════════════════
# Rank Comparison — the ZFC analog of curvature analysis
# ═══════════════════════════════════════════════════════════════════

@dataclass
class RankProfile:
    """
    The rank profile of a relation pair (a, b).

    Captures how a and b sit in the well-ordering:
    - rank_a, rank_b: their positions
    - rank_gap: how far apart they are
    - intermediates: elements between them
    - direction: a < b ("forward") or a > b ("backward")

    Mirror of: GeometricSignature (curvature profile of a path)
    GeometricSignature tells you WHAT KIND of space a path traverses.
    RankProfile tells you HOW FAR and WHICH DIRECTION a relation spans.
    """
    source: str
    target: str
    rank_source: int
    rank_target: int
    rank_gap: int
    direction: str  # "forward", "backward", "same"
    intermediates: List[str]


def rank_profile(well_order: WellOrder,
                 source: str, target: str) -> Optional[RankProfile]:
    """Compute the rank profile for a (source, target) pair."""
    rs = well_order.rank(source)
    rt = well_order.rank(target)
    if rs is None or rt is None:
        return None

    gap = rt - rs
    if gap > 0:
        direction = "forward"
    elif gap < 0:
        direction = "backward"
    else:
        direction = "same"

    lo, hi = min(rs, rt), max(rs, rt)
    intermediates = well_order.elements[lo + 1:hi]

    return RankProfile(
        source=source,
        target=target,
        rank_source=rs,
        rank_target=rt,
        rank_gap=abs(gap),
        direction=direction,
        intermediates=intermediates,
    )


def classify_relation_by_rank(
    well_order: WellOrder,
    relation: Relation,
) -> Dict[str, List[Tuple[str, str]]]:
    """
    Classify relation pairs by their rank profile.

    Returns buckets:
    - "local": rank gap <= 2 (nearby in the hierarchy)
    - "medium": rank gap 3-10
    - "long_range": rank gap > 10
    - "backward": target ranked below source (unusual)

    Mirror of: GeometricStrategy.classify_by_region
    Geometric classifies by curvature type (spherical/hyperbolic/euclidean).
    This classifies by rank distance (local/medium/long_range/backward).
    """
    buckets: Dict[str, List[Tuple[str, str]]] = {
        "local": [],
        "medium": [],
        "long_range": [],
        "backward": [],
    }

    for (a, b) in relation.pairs:
        profile = rank_profile(well_order, a, b)
        if profile is None:
            continue

        if profile.direction == "backward":
            buckets["backward"].append((a, b))
        elif profile.rank_gap <= 2:
            buckets["local"].append((a, b))
        elif profile.rank_gap <= 10:
            buckets["medium"].append((a, b))
        else:
            buckets["long_range"].append((a, b))

    return buckets


# ═══════════════════════════════════════════════════════════════════
# OrdinalOracle — prediction via rank and induction
# ═══════════════════════════════════════════════════════════════════

class OrdinalOracle:
    """
    Prediction oracle using well-ordering and transfinite induction.

    Mirror of: KanEngine (cubical path-based prediction)
    KanEngine fills gaps using Kan operations on paths.
    OrdinalOracle fills gaps using inductive reasoning on well-orders.

    KanEngine: "given walls of a box, compute the cap"
    OrdinalOracle: "given predecessors' values, compute the next"
    """

    def __init__(self, universe: Universe, relation: Relation):
        self.universe = universe
        self.relation = relation
        self.well_order = well_order_by_relation(universe, relation)
        self.ranks = rank_all(universe)

    def predict_by_rank(self, source: str,
                        target: str) -> Tuple[bool, float, Dict[str, Any]]:
        """
        Predict whether source relates to target using rank analysis.

        Confidence based on:
        - Rank gap (smaller = more confident for "local" relations)
        - Direction (forward = expected, backward = surprising)
        - Number of intermediates with known connections

        Returns:
            (prediction, confidence, evidence)
        """
        profile = rank_profile(self.well_order, source, target)
        if profile is None:
            return (False, 0.0, {"reason": "elements not in well-ordering"})

        # Check if relation already exists
        if self.relation.holds(source, target):
            return (True, 1.0, {"reason": "direct_evidence", "profile": profile})

        # Check intermediate connections
        intermediates_connected = 0
        for inter in profile.intermediates:
            if (self.relation.holds(source, inter) or
                    self.relation.holds(inter, target)):
                intermediates_connected += 1

        # Scoring
        if profile.direction == "backward":
            # Backward relations are unusual — lower base confidence
            base_confidence = 0.3
        elif profile.rank_gap <= 2:
            base_confidence = 0.7
        elif profile.rank_gap <= 5:
            base_confidence = 0.5
        else:
            base_confidence = 0.3

        # Boost for intermediate connections
        if profile.intermediates:
            connection_ratio = intermediates_connected / len(profile.intermediates)
            confidence = min(0.95, base_confidence + 0.3 * connection_ratio)
        else:
            confidence = base_confidence

        evidence = {
            "rank_source": profile.rank_source,
            "rank_target": profile.rank_target,
            "rank_gap": profile.rank_gap,
            "direction": profile.direction,
            "intermediates": len(profile.intermediates),
            "intermediates_connected": intermediates_connected,
        }

        prediction = confidence >= 0.5
        return (prediction, confidence, evidence)

    def predict_by_induction(
        self,
        target: str,
        value_function: Callable[[str, int, Dict[str, Any]], Any],
    ) -> Any:
        """
        Predict a value for target using transfinite induction.

        Computes values for all predecessors in the well-ordering,
        then uses the inductive step to compute the target's value.

        Mirror of: LeftKanExtension.extend
        Kan extension: aggregate F(c) over comma category via colimit.
        Induction: aggregate predecessor values via inductive step.
        """
        results = bounded_induction(
            self.well_order,
            base_case=lambda e: value_function(e, 0, {}),
            inductive_step=value_function,
            max_predecessors=20,
        )

        result = results.get(target)
        if result is None:
            return None
        return result.value

    def compare_paths_vs_order(
        self,
        source: str,
        target: str,
        cat_paths: Optional[List[List[str]]] = None,
    ) -> Dict[str, Any]:
        """
        Compare categorical paths with the well-ordering.

        Takes paths from KOMPOSOS-CAT and compares them against
        the canonical well-ordering from ZFC.

        This is a BRIDGE operation — it's where CAT and ZFC meet.

        Returns analysis of agreement/disagreement.
        """
        profile = rank_profile(self.well_order, source, target)
        if profile is None:
            return {"error": "elements not in ordering"}

        result = {
            "source": source,
            "target": target,
            "zfc_rank_gap": profile.rank_gap,
            "zfc_direction": profile.direction,
            "zfc_intermediates": profile.intermediates,
        }

        if cat_paths:
            path_lengths = [len(p) - 1 for p in cat_paths]
            result["cat_num_paths"] = len(cat_paths)
            result["cat_min_length"] = min(path_lengths) if path_lengths else 0
            result["cat_max_length"] = max(path_lengths) if path_lengths else 0

            # The delta: do path lengths agree with rank gap?
            min_len = min(path_lengths) if path_lengths else 0
            if min_len > 0 and profile.rank_gap > 0:
                ratio = min_len / profile.rank_gap
                if 0.5 <= ratio <= 2.0:
                    result["agreement"] = "consistent"
                elif ratio < 0.5:
                    result["agreement"] = "zfc_sees_farther"
                    # ZFC thinks they're far apart but CAT has a short path
                    # This means there's a shortcut CAT found that ZFC's
                    # linear ordering misses
                else:
                    result["agreement"] = "cat_sees_farther"
                    # CAT needs many steps but ZFC thinks they're close
                    # This means the linear proximity is misleading
            else:
                result["agreement"] = "incomparable"

        return result


# ═══════════════════════════════════════════════════════════════════
# Example usage and tests
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from .universe import zfset, relation as mk_relation

    V = Universe("ProteinUniverse")

    # Add proteins
    for name in ["FLT3", "STAT5", "PI3K", "AKT", "MYC", "RAF1", "MEK1", "ERK1"]:
        s = V.add_set(zfset(name, type="Protein"))

    # Signaling pathway
    signals = mk_relation("signals", [
        ("FLT3", "STAT5"), ("FLT3", "PI3K"), ("FLT3", "RAF1"),
        ("STAT5", "MYC"),
        ("PI3K", "AKT"), ("AKT", "MYC"),
        ("RAF1", "MEK1"), ("MEK1", "ERK1"), ("ERK1", "MYC"),
    ])
    V.add_relation(signals)

    # Well-order by topology
    wo = well_order_by_relation(V, signals)
    print(f"Well-ordering: {wo}")
    print(f"Ranks: {wo._rank_map}")

    # Rank profiles
    p1 = rank_profile(wo, "FLT3", "MYC")
    print(f"\nFLT3 → MYC: gap={p1.rank_gap}, dir={p1.direction}, "
          f"intermediates={p1.intermediates}")

    p2 = rank_profile(wo, "PI3K", "MYC")
    print(f"PI3K → MYC: gap={p2.rank_gap}, dir={p2.direction}, "
          f"intermediates={p2.intermediates}")

    # Classify relations
    buckets = classify_relation_by_rank(wo, signals)
    for bucket, pairs in buckets.items():
        if pairs:
            print(f"\n{bucket}: {pairs}")

    # Oracle prediction
    oracle = OrdinalOracle(V, signals)
    pred, conf, evidence = oracle.predict_by_rank("FLT3", "MYC")
    print(f"\nPredict FLT3→MYC: {pred}, conf={conf:.2f}")
    print(f"  Evidence: {evidence}")

    # Compare with categorical paths
    cat_paths = [
        ["FLT3", "STAT5", "MYC"],
        ["FLT3", "PI3K", "AKT", "MYC"],
        ["FLT3", "RAF1", "MEK1", "ERK1", "MYC"],
    ]
    comparison = oracle.compare_paths_vs_order("FLT3", "MYC", cat_paths)
    print(f"\nPath vs Order comparison: {comparison}")
