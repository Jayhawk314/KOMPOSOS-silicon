# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
PatternMiner: System-3 analog / DAEDALUS Level 4

The constructive mirror of KOMPOSOS-IV's MetaKan mining emergent axioms.
KOMPOSOS mines recurring *inference shapes* and proposes them as axioms;
OPERADUM mines recurring *design shapes* and proposes them as reusable
components -- the practical form of a Level-4 operad map (a map from a small
"pattern" operad into the concrete one).

The loop:
  1. record() every BUILDABLE construction as an episode.
  2. mine() the closed sub-designs that recur across episodes above a support
     threshold -- these are patterns that "keep working".
  3. lift() a pattern into a new compound Operation on the operad, whose
     callable is the realized pattern and whose cost is the pattern's cost.
     Future synthesis then hits it directly at WRIGHT Tier 0.

This is the engine improving its own component set from its build history --
self-construction (master spec Phase 4), seeded here in Phase 3.
"""

from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core.operad import Operad
from ..core.types import Composite, Operation, Spec


@dataclass
class Pattern:
    """A recurring design shape worth promoting to a reusable component."""
    wiring: str
    support: int                 # how many episodes contained it
    exemplar: Composite          # a concrete instance
    interface_inputs: tuple
    output: str

    def __str__(self) -> str:
        return f"Pattern({self.wiring}, support={self.support})"


class PatternMiner:
    """Mines reusable design patterns from a stream of BUILDABLE constructions."""

    def __init__(self, operad: Operad, min_support: int = 2, min_size: int = 2):
        self.operad = operad
        self.min_support = min_support
        self.min_size = min_size           # only patterns with >= this many ops
        self._episodes: List[Composite] = []
        # Outcome log: (interface signature) -> [buildable bools]. Lets the miner
        # learn which sketch shapes tend to be realizable (System-3 learning).
        self._outcomes: Dict[Tuple[Tuple[str, ...], str], List[bool]] = {}
        self._lifted: set[str] = set()

    # ---------------- recording ----------------

    def record(self, comp: Composite) -> None:
        """Record a successful design as an episode."""
        self._episodes.append(comp)

    def record_result(self, build_result) -> None:
        """Record a WRIGHT BuildResult: keep the design if BUILDABLE, and log the
        outcome (BUILDABLE/IMPOSSIBLE) against its interface shape for learning."""
        spec = build_result.spec
        buildable = getattr(build_result, "buildable", False)
        sig = (tuple(sorted(spec.inputs)), spec.output)
        self._outcomes.setdefault(sig, []).append(buildable)
        if buildable and build_result.construction:
            self.record(build_result.construction.composite)

    @property
    def episodes(self) -> int:
        return len(self._episodes)

    # ---------------- realizability learning ----------------

    def realizability_rate(self, output: Optional[str] = None) -> float:
        """Learned fraction of recorded specs that were BUILDABLE.

        With `output`, restrict to specs producing that colour -- the System-3
        signal "designs of this shape tend to succeed", used to prioritise which
        patterns are worth promoting.
        """
        flat: List[bool] = []
        for (sig_inputs, sig_output), outcomes in self._outcomes.items():
            if output is None or sig_output == output:
                flat.extend(outcomes)
        return sum(1 for b in flat if b) / len(flat) if flat else 0.0

    # ---------------- mining ----------------

    def mine(self) -> List[Pattern]:
        """
        Return the sub-designs that recur across episodes with support >=
        min_support, largest first. A sub-design counts once per episode it
        appears in (support = number of episodes, not total occurrences).
        """
        episode_subs: List[Dict[str, Composite]] = []
        for comp in self._episodes:
            subs: Dict[str, Composite] = {}
            self._collect_subdesigns(comp, subs)
            episode_subs.append(subs)

        support: Counter = Counter()
        exemplar: Dict[str, Composite] = {}
        for subs in episode_subs:
            for wiring, node in subs.items():
                support[wiring] += 1
                exemplar.setdefault(wiring, node)

        patterns: List[Pattern] = []
        for wiring, n in support.items():
            if n < self.min_support:
                continue
            node = exemplar[wiring]
            if len(node.operations()) < self.min_size:
                continue
            patterns.append(Pattern(
                wiring=wiring, support=n, exemplar=node,
                interface_inputs=tuple(node.open_inputs()), output=node.output,
            ))
        patterns.sort(key=lambda p: (len(p.exemplar.operations()), p.support),
                      reverse=True)
        return patterns

    def _collect_subdesigns(self, comp: Composite, out: Dict[str, Composite]) -> None:
        """Index every sub-design by its wiring (deduped within one episode)."""
        out.setdefault(comp.to_wiring(), comp)
        for kind, val in comp.slots:
            if kind == "sub":
                self._collect_subdesigns(val, out)

    # ---------------- lifting (operad map) ----------------

    def lift(self, pattern: Pattern, name: Optional[str] = None) -> Operation:
        """
        Promote a pattern to a reusable compound Operation on the operad. Its
        callable is the realized pattern; its cost is the pattern's combined
        cost. After lifting, WRIGHT can use the whole pattern in one step.
        """
        name = name or f"pattern_{abs(hash(pattern.wiring)) % 100000}"
        artifact = self.operad.realize(pattern.exemplar)
        cost = pattern.exemplar.cost(self.operad.monoid)
        self._lifted.add(pattern.wiring)
        return self.operad.add_op(
            name=name,
            inputs=list(pattern.interface_inputs),
            output=pattern.output,
            cost=cost,
            fn=lambda *args: artifact(*args),
            provenance="pattern_miner",
            mined_from=pattern.wiring,
            support=pattern.support,
        )

    # ---------------- autonomous self-extension ----------------

    def propose(self) -> List[Pattern]:
        """The patterns the system proposes promoting -- mined, not yet lifted,
        ordered by (learned realizability of their output, size, support)."""
        return [
            p for p in sorted(
                self.mine(),
                key=lambda p: (self.realizability_rate(p.output),
                               len(p.exemplar.operations()), p.support),
                reverse=True,
            )
            if p.wiring not in self._lifted
        ]

    def auto_lift(self) -> List[Operation]:
        """Mine the build history and promote every qualifying pattern into a
        reusable component -- the engine extending its own component set from
        what it has built (master spec Phase 4 exit criterion).
        """
        lifted: List[Operation] = []
        for pattern in self.propose():
            name = f"learned_{pattern.output.lower()}_{len(self._lifted)}"
            lifted.append(self.lift(pattern, name=name))
        return lifted
