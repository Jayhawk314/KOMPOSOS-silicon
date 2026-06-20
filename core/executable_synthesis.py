# SPDX-License-Identifier: Apache-2.0
"""
Executable synthesis — turn a structural gap into a *working, verified* morphism.

The self-improvement loop's weakness was that "filling a gap" only asserted a new
edge exists (and printed "started"); nothing actually computed. This module
grounds that: a structural gap source->target exists precisely because an
executable spine source --f--> B --g--> ... --> target exists. The real
capability for the gap is the **categorical composite** of that spine, and we can
*verify it runs* by executing the composite on real inputs and checking it equals
applying the spine step by step (the composite's defining property).

So a filled gap is no longer a claim — it is a function that was built, executed
on probe data, and checked against ground truth (the spine) before it is kept.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import reduce
from typing import Any, Callable, List, Optional, Tuple

from core.category import Category
from core.types import Morphism

# Generic probe inputs tried against an executable spine. We keep the first
# probe the whole spine accepts without raising; this lets the verifier work on
# any domain (str/num/list functions) without the loop knowing the types.
_DEFAULT_PROBES: Tuple[Any, ...] = ("Hello World ", "test_input", 3, [1, 2, 3], {"k": 1})


@dataclass
class SynthesisResult:
    source: str
    target: str
    spine: List[str]                 # human-readable spine, e.g. ["search","index","store"]
    executable: bool                 # was an executable spine found at all?
    executed: bool                   # did the composite actually run on a probe?
    verified: bool                   # composite(probe) == spine applied stepwise?
    probe: Any = None
    composite: Optional[Callable] = field(default=None, repr=False)
    note: str = ""


class ExecutableSynthesizer:
    """Find an executable spine for a gap, compose it, and verify it runs."""

    def __init__(self, category: Category, max_depth: int = 4):
        self.category = category
        self.max_depth = max_depth

    # -- spine discovery ----------------------------------------------------

    def find_executable_spines(
        self, source: str, target: str, max_spines: int = 8
    ) -> List[List[Morphism]]:
        """All callable paths source->...->target (capped), shortest first."""
        spines: List[List[Morphism]] = []

        def dfs(node: str, path: List[Morphism], seen: set):
            if len(path) > self.max_depth or len(spines) >= max_spines:
                return
            for m in self.category.morphisms_from(node):
                if not m.is_callable or m.target in seen:
                    continue
                if m.target == target:
                    spines.append(path + [m])
                else:
                    dfs(m.target, path + [m], seen | {m.target})

        dfs(source, [], {source})
        spines.sort(key=len)
        return spines

    def find_executable_spine(self, source: str, target: str) -> Optional[List[Morphism]]:
        spines = self.find_executable_spines(source, target, max_spines=1)
        return spines[0] if spines else None

    # -- composition + verification ----------------------------------------

    @staticmethod
    def compose(spine: List[Morphism]) -> Callable:
        """Composite callable: apply each morphism's fn left to right along the spine."""
        fns = [m._fn for m in spine]
        return lambda x: reduce(lambda acc, f: f(acc), fns, x)

    @staticmethod
    def _apply_spine(spine: List[Morphism], x: Any) -> Any:
        """Ground truth: apply the spine one morphism at a time."""
        acc = x
        for m in spine:
            acc = m(acc)  # Morphism.__call__ runs its _fn
        return acc

    def synthesize(
        self,
        source: str,
        target: str,
        probes: Tuple[Any, ...] = _DEFAULT_PROBES,
    ) -> SynthesisResult:
        spines = self.find_executable_spines(source, target)
        if not spines:
            return SynthesisResult(
                source, target, [source, target], executable=False, executed=False,
                verified=False, note="no executable spine (structural edge only)",
            )

        primary = spines[0]
        names = [source] + [m.target for m in primary]
        composite = self.compose(primary)

        # Find the first probe the primary spine accepts without raising.
        for probe in probes:
            try:
                expected = self._apply_spine(primary, probe)
            except Exception:
                continue  # probe type not in this spine's domain; try next
            try:
                got = composite(probe)
            except Exception as exc:
                return SynthesisResult(
                    source, target, names, executable=True, executed=False,
                    verified=False, probe=probe, composite=composite,
                    note=f"composite raised on probe: {exc}",
                )
            if got != expected:  # composition wiring bug (should not happen)
                return SynthesisResult(
                    source, target, names, executable=True, executed=True,
                    verified=False, probe=probe, composite=composite,
                    note="composite disagreed with its own spine",
                )

            # Path-coherence: every OTHER executable spine to target must agree on
            # this probe (the executable analog of the sheaf/horn coherence check).
            # This is the falsifiable teeth: divergent mechanisms => ambiguous => fail.
            disagree = []
            for alt in spines[1:]:
                try:
                    alt_out = self._apply_spine(alt, probe)
                except Exception:
                    continue  # alt doesn't accept this probe; not a disagreement
                if alt_out != expected:
                    disagree.append("->".join([source] + [m.target for m in alt]))

            if disagree:
                return SynthesisResult(
                    source, target, names, executable=True, executed=True,
                    verified=False, probe=probe, composite=composite,
                    note=f"path-incoherent: {len(disagree)} spine(s) disagree ({disagree[0]})",
                )
            coh = f" ({len(spines)} spines agree)" if len(spines) > 1 else ""
            return SynthesisResult(
                source, target, names, executable=True, executed=True,
                verified=True, probe=probe, composite=composite,
                note=f"composite runs; path-coherent{coh}",
            )

        # Spine exists but no probe matched its input domain — can't run it.
        return SynthesisResult(
            source, target, names, executable=True, executed=False, verified=False,
            composite=composite, note="no compatible probe input for spine domain",
        )

    def install(self, source: str, target: str, relation: str, result: SynthesisResult) -> bool:
        """Upgrade the just-written structural edge to the verified executable composite.

        Attaches the composite as the edge's _fn so the new capability is genuinely
        runnable from the graph. Returns True if an edge was upgraded.
        """
        if result.composite is None:
            return False
        for m in self.category.morphisms_from(source):
            if m.target == target and m.name == relation:
                m._fn = result.composite
                return True
        return False
