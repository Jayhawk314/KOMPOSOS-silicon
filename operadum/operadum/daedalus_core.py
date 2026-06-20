# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
DAEDALUS: Generative Search (Layer 4)

The dual of KOMPOSOS-IV's OPTIMUS. OPTIMUS *factors a morphism* into a better
path; DAEDALUS *searches the space of composites* for a better whole design:

    OPTIMUS:   m_{t+1} = argmax_{f in factorizations(m_t)} weight(f)
    DAEDALUS:  d_{t+1} = argmin_{c in composites(spec)}     rank(cost(c))
               subject to: c realizes spec  and  c is resource-sound

Instead of discovering intermediate *objects*, DAEDALUS discovers intermediate
*assemblies*, pruning by type (only well-typed plug-ins expand) and by resource
(branch-and-bound on the selected figure rank, plus a frontier per interface).

Three guarantees (master spec S8):
  1. Monotone improvement -- the returned design is best-ranked among all
     depth-bounded sound designs (we keep the whole frontier, then take min).
  2. No re-expansion -- sub-designs are memoised by (target, depth, allowed),
     the dual of OPTIMUS's "no cycles".
  3. Provable termination -- bounded depth + finite components => finite search;
     under the tropical algebra this is Dijkstra-style optimality.

This module ships Level 1 (assemble existing operations). Level 2 (coherence
rewrites) lands with Polytope in Phase 3.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from collections import Counter
from itertools import product
from typing import Dict, FrozenSet, List, Optional, Tuple

from .core.operad import Operad
from .core.types import Composite, Spec, ResourceValue
from .core.enrichment import ResourceError, _meets_minimum


# A frontier maps an open-input signature (sorted colours) to sound composites
# realizing it, each with its scalar rank and full resource value. We retain
# multiple entries because hard lower-bound requirements can make a worse-ranked
# unconstrained design the only feasible one (e.g. slower but higher confidence).
OpenSig = Tuple[str, ...]
FrontierEntry = Tuple[float, ResourceValue, Composite]
Frontier = Dict[OpenSig, List[FrontierEntry]]


@dataclass
class SearchStats:
    """Bookkeeping that witnesses the three guarantees."""
    expansions: int = 0
    memo_hits: int = 0
    frontier_size: int = 0
    pruned_unsound: int = 0


@dataclass
class SearchResult:
    """
    The outcome of DAEDALUS.search(spec).

    `best` is the best-ranked in-budget, resource-sound design; `best_any` is
    the best-ranked sound design ignoring budget (used to distinguish
    OVERBUDGET from a true gap upstream in WRIGHT).
    """
    spec: Spec
    best: Optional[Composite] = None
    best_cost: Optional[ResourceValue] = None
    best_any: Optional[Composite] = None
    best_any_cost: Optional[ResourceValue] = None
    stats: SearchStats = field(default_factory=SearchStats)

    @property
    def found_in_budget(self) -> bool:
        return self.best is not None

    @property
    def found_any(self) -> bool:
        return self.best_any is not None


class Daedalus:
    """
    Branch-and-bound generative search over the free operad.

    Operates on a snapshot of the operad (it reads operations; it does not
    mutate the store). Returns the best-ranked design realizing a spec.
    """

    def __init__(self, operad: Operad, max_depth: int = 6):
        self.operad = operad
        self.monoid = operad.monoid
        self.max_depth = max_depth
        self._memo: Dict[Tuple[str, int, FrozenSet[str]], Frontier] = {}
        self._stats = SearchStats()

    # =================================================================
    # Public entry point
    # =================================================================

    def search(self, spec: Spec, max_depth: Optional[int] = None) -> SearchResult:
        """
        Find the best-ranked resource-sound design realizing `spec`.

        Builds the full Pareto frontier of designs producing the target colour
        from the spec's inputs, then selects the best-ranked design whose open
        inputs are a sub-multiset of the spec's inputs -- in budget if a budget
        is given.
        """
        self._memo.clear()
        self._stats = SearchStats()
        depth = max_depth or self.max_depth
        allowed = frozenset(spec.inputs)
        pool = Counter(spec.inputs)

        frontier = self._designs(spec.output, depth, allowed)
        self._stats.frontier_size = sum(len(entries) for entries in frontier.values())

        best: Optional[FrontierEntry] = None
        best_any: Optional[FrontierEntry] = None
        for sig, entries in frontier.items():
            if not _submultiset(Counter(sig), pool):
                continue
            for entry in entries:
                scalar, cost, comp = entry
                if best_any is None or scalar < best_any[0]:
                    best_any = entry
                if spec.budget is not None and not self.monoid.compare(cost, spec.budget):
                    continue
                if spec.requirements is not None and not _meets_minimum(cost, spec.requirements):
                    continue
                if best is None or scalar < best[0]:
                    best = entry

        result = SearchResult(spec=spec, stats=self._stats)
        if best is not None:
            result.best, result.best_cost = best[2], best[1]
        if best_any is not None:
            result.best_any, result.best_any_cost = best_any[2], best_any[1]
        return result

    # =================================================================
    # Core recursion: the Pareto frontier of designs for one colour
    # =================================================================

    def _designs(self, target: str, depth: int, allowed: FrozenSet[str]) -> Frontier:
        """
        All ranked composites producing `target` within `depth`, keyed by
        their open-input signature. Memoised -- the "no re-expansion" guarantee.
        """
        key = (target, depth, allowed)
        if key in self._memo:
            self._stats.memo_hits += 1
            return self._memo[key]

        frontier: Frontier = {}
        if depth >= 1:
            for op in self.operad.operations_producing(target):
                self._expand_operation(op, depth, allowed, frontier)
        self._memo[key] = frontier
        return frontier

    def _expand_operation(self, op, depth: int, allowed: FrozenSet[str],
                          frontier: Frontier) -> None:
        """Fold every well-typed filling of `op`'s inputs into the frontier."""
        # Per-input options: leave open (if the colour is an allowed input) or
                # plug in a ranked sub-design (if depth remains).
        slot_options: List[List[Tuple[OpenSig, ResourceValue, tuple]]] = []
        for colour in op.inputs:
            options: List[Tuple[OpenSig, ResourceValue, tuple]] = []
            if colour in allowed:
                options.append(((colour,), dict(self.monoid.unit), ("open", colour)))
            if depth > 1:
                for sig, entries in self._designs(colour, depth - 1, allowed).items():
                    for _sc, cost, sub in entries:
                        options.append((sig, cost, ("sub", sub)))
            if not options:
                return  # this input is a dead end -> op unusable here
            slot_options.append(options)

        for combo in product(*slot_options):
            self._stats.expansions += 1
            try:
                cost = self.monoid.combine(dict(self.monoid.unit), op.cost)
                opens: List[str] = []
                slots = []
                for sig, slot_cost, slot in combo:
                    cost = self.monoid.combine(cost, slot_cost)
                    opens.extend(sig)
                    slots.append(slot)
            except ResourceError:
                self._stats.pruned_unsound += 1
                continue  # resource-unsound assembly -> pruned by linear discipline

            comp = Composite(op, list(slots))
            osig: OpenSig = tuple(sorted(opens))
            scalar = self.monoid.rank(cost)
            frontier.setdefault(osig, []).append((scalar, cost, comp))


# ===================================================================
# Helpers
# ===================================================================

def _submultiset(a: Counter, b: Counter) -> bool:
    """True iff multiset `a` is contained in multiset `b`."""
    return all(b[k] >= n for k, n in a.items())
