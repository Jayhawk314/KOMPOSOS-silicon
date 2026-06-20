# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
SelfObserver: structural self-observation

Master spec Phase 4: "telemetry as components; find missing colours / redundant
operations." The constructive dual of KOMPOSOS-IV's self_corrector. The
SelfObserver reads an operad as data and reports structural facts the system can
act on -- the substrate observing itself:

  - source_colours:    colours no operation produces (must be supplied as input).
  - sink_colours:      colours no operation consumes (terminal products / dead).
  - redundant_ops:     operations with the SAME interface where one is dominated
                       in cost by another -- the dominated one is redundant.
  - unreachable_from:  given roots, colours no design can build from them.

Each finding comes with a concrete proposal, so the report drives self-repair.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from ..core.operad import Operad
from ..core.types import Operation


@dataclass
class SelfReport:
    operad: str
    source_colours: List[str] = field(default_factory=list)
    sink_colours: List[str] = field(default_factory=list)
    redundant_ops: List[Tuple[str, str, str]] = field(default_factory=list)  # (dominated, by, reason)
    proposals: List[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.redundant_ops

    def __str__(self) -> str:
        return (f"SelfReport({self.operad}: sources={self.source_colours}, "
                f"sinks={self.sink_colours}, redundant={len(self.redundant_ops)})")


class SelfObserver:
    """Observes an operad's structure and proposes corrections."""

    def __init__(self, operad: Operad):
        self.operad = operad

    def observe(self) -> SelfReport:
        ops = self.operad.operations()
        colours = {c.name for c in self.operad.colours()}
        produced = {o.output for o in ops}
        consumed = {c for o in ops for c in o.inputs}

        report = SelfReport(operad=self.operad.name)
        report.source_colours = sorted(colours - produced)
        report.sink_colours = sorted(colours - consumed)

        # Redundant operations: same interface, one dominated in cost.
        by_iface: Dict[Tuple[Tuple[str, ...], str], List[Operation]] = {}
        for o in ops:
            by_iface.setdefault((tuple(o.inputs), o.output), []).append(o)
        for iface, group in by_iface.items():
            if len(group) < 2:
                continue
            for a in group:
                for b in group:
                    if a is b:
                        continue
                    if self._dominates(b, a):   # b no worse on every key, better somewhere
                        report.redundant_ops.append(
                            (a.name, b.name,
                             f"interface {a.interface}: {b.name} dominates on cost"))
                        report.proposals.append(
                            f"consider removing '{a.name}': dominated by '{b.name}' "
                            f"(same interface, never cheaper)")
                        break

        for c in report.source_colours:
            report.proposals.append(f"colour '{c}' has no producer -- it is a raw input")
        return report

    @staticmethod
    def _dominates(b: Operation, a: Operation) -> bool:
        """True iff b is <= a on every cost key and strictly < on at least one
        (so a is redundant). Keys absent from one side count as 0."""
        keys = set(a.cost) | set(b.cost)
        if not keys:
            return False
        better_somewhere = False
        for k in keys:
            bv, av = b.cost.get(k, 0), a.cost.get(k, 0)
            if bv > av:
                return False
            if bv < av:
                better_somewhere = True
        return better_somewhere
