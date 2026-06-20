# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
PROP Lift: many-in / many-out, sharing & forking

A PROP is a symmetric monoidal category whose objects are the natural numbers
-- it adds *many outputs* to an operad, so designs may fork a result and feed
it to several consumers. The catch, and the whole point of doing it here rather
than in a cartesian setting: forking is duplication, and duplication of a
resource is forbidden unless the resource is banged (`!`). So copy/discard
exist ONLY where explicitly declared, and declaring `copy` on a colour whose
resource is linear is refused.

This is the Level-3 payoff for DAEDALUS: when a design computes the same
sub-result twice from the same inputs, a declared copy lets it compute once and
fork -- a genuine resource win -- but only when that is sound.

  Operad:  tree wirings, every output consumed once (linear by default).
  PROP:    DAG wirings, outputs may fork through DECLARED copy nodes.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Set, Tuple

from .operad import Operad
from .enrichment import ResourceError
from .types import Composite


class CopyError(ValueError):
    """Raised when a colour cannot be forked soundly (linear, not banged)."""


@dataclass
class ShareReport:
    """The result of analysing a design for sound sharing opportunities."""
    shareable: List[str]                       # sub-wirings safe to share
    refused: List[Tuple[str, str]]             # (sub-wiring, reason)
    cost_unshared: Dict[str, Any]
    cost_shared: Dict[str, Any]

    @property
    def saves(self) -> bool:
        return self.cost_shared != self.cost_unshared


class PROP:
    """
    Promotes an Operad to a PROP: declared copy/merge + resource-aware sharing.

    `bang` is the set of colours whose resource is freely copyable (the `!`
    exponential). Under a linear monoid, only banged colours may be forked.
    """

    def __init__(self, operad: Operad, bang: Set[str] = frozenset()):
        self.operad = operad
        self.bang: Set[str] = set(bang)
        self.copyable: Set[str] = set()

    def can_copy(self, colour: str) -> bool:
        """A colour may be forked iff its resource is not linear, or it is banged."""
        if not self.operad.monoid.linear:
            return True                # accumulative resources copy freely
        return colour in self.bang     # linear: only the banged exponential copies

    def declare_copy(self, colour: str) -> "PROP":
        """Declare a fork (copy) operation on `colour`. Refused when unsound."""
        if not self.can_copy(colour):
            raise CopyError(
                f"Cannot declare copy on '{colour}': it carries a linear "
                f"(spend-once) resource. Bang it (!) to permit duplication."
            )
        self.copyable.add(colour)
        return self

    # ---------------- sharing analysis ----------------

    def analyze_sharing(self, comp: Composite) -> ShareReport:
        """
        Find repeated sub-designs that consume only open inputs (so they yield
        the same value) and report which may be shared soundly and the cost
        saved by computing each once instead of per-occurrence.
        """
        counts = self._subtree_counts(comp)
        shareable: List[str] = []
        refused: List[Tuple[str, str]] = []
        for sub, (n, node) in counts.items():
            if n < 2:
                continue
            colour = node.output
            if self.can_copy(colour):
                shareable.append(sub)
            else:
                refused.append((sub, f"'{colour}' is linear and not banged"))

        # The unshared cost may be resource-unsound (e.g. a linear token spent
        # on both legs); that is precisely why sharing was refused. Report the
        # cost as None rather than crash.
        cost_unshared = self._safe_cost(comp)
        try:
            cost_shared = self._shared_cost(comp, set(shareable))
        except ResourceError:
            cost_shared = None
        return ShareReport(shareable, refused, cost_unshared, cost_shared)

    def _safe_cost(self, comp: Composite):
        try:
            return comp.cost(self.operad.monoid)
        except ResourceError:
            return None

    def _subtree_counts(self, comp: Composite):
        """Map each closed (input-free) sub-design wiring to (count, node)."""
        counts: Dict[str, Tuple[int, Composite]] = {}

        def visit(node: Composite):
            for kind, val in node.slots:
                if kind == "sub":
                    visit(val)
            if not node.open_inputs():  # closed: same value every time
                key = node.to_wiring()
                n, _ = counts.get(key, (0, node))
                counts[key] = (n + 1, node)

        visit(comp)
        return counts

    def _shared_cost(self, comp: Composite, shared: Set[str]) -> Dict[str, Any]:
        """Cost when each shared sub-design is paid for exactly once."""
        monoid = self.operad.monoid
        paid: Set[str] = set()

        def cost_of(node: Composite):
            key = node.to_wiring()
            if key in shared:
                if key in paid:
                    return dict(monoid.unit)   # already computed: forked for free
                paid.add(key)
            total = monoid.combine(dict(monoid.unit), node.head.cost)
            for kind, val in node.slots:
                if kind == "sub":
                    total = monoid.combine(total, cost_of(val))
            return total

        return cost_of(comp)

    # ---------------- shared execution ----------------

    def realize_shared(self, comp: Composite) -> Tuple[Callable, Dict[str, int]]:
        """
        Realize a design with common-subexpression sharing: identical closed
        sub-designs evaluate once. Returns (artifact, eval_counts) where
        eval_counts[op_name] is how many times each operation actually ran --
        the runtime witness that forking saved work.
        """
        base = self.operad.realize(comp)  # ensures every op is executable
        counts: Dict[str, int] = {}

        def instrumented(*args):
            memo: Dict[str, Any] = {}
            return self._eval(comp, list(args), memo, counts)[0]

        instrumented.interface = comp.interface  # type: ignore[attr-defined]
        return instrumented, counts

    def _eval(self, node: Composite, args: List[Any], memo: Dict[str, Any],
              counts: Dict[str, int]):
        key = node.to_wiring()
        closed = not node.open_inputs()
        if closed and key in memo:
            return memo[key], 0
        call_args: List[Any] = []
        idx = 0
        for kind, val in node.slots:
            if kind == "open":
                call_args.append(args[idx]); idx += 1
            else:
                sub_value, consumed = self._eval(val, args[idx:], memo, counts)
                call_args.append(sub_value); idx += consumed
        counts[node.head.name] = counts.get(node.head.name, 0) + 1
        value = node.head._fn(*call_args)
        if closed:
            memo[key] = value
        return value, idx
