# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
WRIGHT: The Synthesis Co-Processor (the WRITE path)

The dual of KOMPOSOS-IV's COG (the read path). COG reads the category to
verify a claim; WRIGHT writes into the operad to satisfy a spec. Given a
target interface (and optional budget), WRIGHT returns a Construction -- a
typed composite plus its executable artifact -- or a principled "no realizer".

Energy-based tier routing (mirror of COG): the cheapest synthesis tier fires
first, and search stops as soon as a sound, in-budget construction is found.

This module ships Tiers 0-2 (Phase 1 MVP):
    Tier 0  ~1ms    Direct match       a single op already has the interface
    Tier 1  ~10ms   Single composition one plug-in meets the interface
    Tier 2  ~100ms  Bounded tree search a small well-typed assembly (depth<=k)

Tiers 3-4 (resource-ILP / coherence proof) are declared in the spec and arrive
with Phase 2-3.
"""

from __future__ import annotations
from typing import List, Optional

from ..core.operad import Operad
from ..core.types import Composite, Operation, Spec
from ..gate.type_engine import TypeEngine
from ..gate.res_engine import ResEngine
from .schema import BuildResult, Construction, Verdict


class Wright:
    """
    The 5-tier (here: 3-tier) synthesizer. Tightly coupled to one Operad --
    it is the operad's write path, not a peer plugin.
    """

    def __init__(self, operad: Operad, max_depth: int = 4):
        self.operad = operad
        self.max_depth = max_depth
        self.type_gate = TypeEngine(operad)
        self.res_gate = ResEngine(operad)
        # Tier 3 is the resource-constrained solver (DAEDALUS). Built lazily so
        # importing Wright never forces the search kernel.
        self._solver = None

    # =================================================================
    # Public entry point
    # =================================================================

    def synthesize(self, spec: Spec) -> BuildResult:
        """
        Energy-routed synthesis. Try tiers cheapest-first; return the first
        construction that passes the dual gate (TYPE + RES). If a typed wiring
        exists but blows the budget, report OVERBUDGET. If none type-checks,
        distinguish ILL_TYPED_GAP (resources would suffice) from IMPOSSIBLE.
        """
        candidates: List[Composite] = []

        for tier, finder in enumerate((self._tier0, self._tier1, self._tier2)):
            found = finder(spec)
            candidates.extend(found)
            for comp in found:
                feasible, cost, reason = self.res_gate.feasible(comp, spec)
                if feasible:
                    artifact = self._try_realize(comp)
                    return BuildResult(
                        verdict=Verdict.BUILDABLE,
                        spec=spec,
                        construction=Construction(comp, cost, tier, artifact),
                        tier=tier,
                        reason="sound, in-budget construction found",
                    )

        # Tier 3: resource-constrained global search. Reaches deeper than the
        # bounded tiers and returns the best-ranked in-budget design -- it can
        # find an in-budget construction the shallow tiers missed.
        tier3 = self._tier3(spec)
        if tier3 is not None:
            return tier3

        # No in-budget construction. Decide which negative verdict applies.
        return self._negative_verdict(spec, candidates)

    def optimize(self, spec: Spec) -> BuildResult:
        """
        Always synthesize the best-ranked in-budget design via DAEDALUS,
        bypassing energy routing. With additive costs this is the historical
        cheapest design; with figure profiles it can mean safest, fastest,
        strongest-evidence, least disruptive, etc. (synthesize() stops at the
        first in-budget hit; optimize() guarantees the global minimum rank
        within the depth bound.)
        """
        result = self.solver.cheapest(spec)
        return self._result_from_search(spec, result)

    def certify(self, spec: Spec, polytope=None):
        """
        WRIGHT Tier 4: synthesize the cost-minimal design, reduce it to its
        coherence normal form, and attach proofs that it is unique up to
        coherence, resource-conserving, and linear-sound.

        Pass a configured Polytope (with declared associative ops / units) to
        certify coherence over a non-trivial rewrite system; with none, the
        normal form is the design itself and conservation/soundness still hold.

        Returns a Certificate, or None if the spec is not BUILDABLE.
        """
        from ..core.polytope import Polytope
        from ..core.formal_coherence import CoherenceProver
        from .schema import Certificate

        build = self.optimize(spec)
        if not build.buildable:
            return None

        poly = polytope or Polytope(self.operad)
        prover = CoherenceProver(self.operad, poly)
        comp = build.construction.composite
        normal_form = poly.normalize(comp)

        conservation = prover.prove_conservation(comp)
        confluence = prover.prove_confluence(comp)
        linear = self.res_gate.prove_sound(normal_form)

        return Certificate(
            construction=build.construction,
            normal_form=normal_form,
            unique=confluence.holds,         # confluent rewrites => unique NF
            conservation=conservation,
            linear=linear,
            coherence=confluence,
        )

    # =================================================================
    # Tiers
    # =================================================================

    def _tier0(self, spec: Spec) -> List[Composite]:
        """Direct match: an existing operation already has the target interface."""
        out: List[Composite] = []
        for op in self.operad.operations_producing(spec.output):
            comp = op.as_composite()
            if self.type_gate.realizes(comp, spec):
                out.append(comp)
        return out

    def _tier1(self, spec: Spec) -> List[Composite]:
        """Single composition: one plug-in o_i p meets the interface."""
        out: List[Composite] = []
        for outer in self.operad.operations_producing(spec.output):
            for i, in_colour in enumerate(outer.inputs):
                if in_colour in spec.inputs:
                    continue  # leaving it open is a tier-0-style match, not a compose
                for inner in self.operad.operations_producing(in_colour):
                    try:
                        comp = self.operad.compose(outer, i, inner)
                    except (TypeError, IndexError):
                        continue
                    if self.type_gate.realizes(comp, spec):
                        out.append(comp)
        return out

    def _tier2(self, spec: Spec) -> List[Composite]:
        """
        Bounded typed tree search: depth-limited inhabitation of the output
        colour from the spec's inputs. Returns every well-typed composite (up
        to max_depth) that realizes the interface, cheapest-first.
        """
        available = list(spec.inputs)
        results: List[Composite] = []
        seen: set[str] = set()

        def build(target: str, depth: int, pool: List[str]) -> List[Composite]:
            """All composites producing `target`, consuming colours from `pool`."""
            comps: List[Composite] = []
            for op in self.operad.operations_producing(target):
                comps.extend(self._fill_inputs(op, depth, pool))
            return comps

        # We reuse _fill_inputs (defined below) which recurses through build.
        self._build = build  # bind for recursion
        for comp in build(spec.output, self.max_depth, available):
            key = comp.to_wiring()
            if key in seen:
                continue
            seen.add(key)
            if self.type_gate.realizes(comp, spec):
                results.append(comp)

        results.sort(key=lambda c: self._cost_scalar(c))
        return results

    def _fill_inputs(self, op: Operation, depth: int, pool: List[str]) -> List[Composite]:
        """
        Enumerate composites with head `op`, where each input slot is either
        left open (if its colour is in `pool`) or filled by a sub-composite
        produced recursively (if depth remains).
        """
        # slot_options[k] = list of ("open", colour) | ("sub", Composite)
        slot_options: List[List] = []
        for colour in op.inputs:
            options: List = []
            if colour in pool:
                options.append(("open", colour))
            if depth > 1:
                for sub in self._build(colour, depth - 1, pool):
                    options.append(("sub", sub))
            if not options:
                return []  # this input is a dead end -> op cannot be used
            slot_options.append(options)

        # Cartesian product of slot choices.
        combos: List[List] = [[]]
        for options in slot_options:
            combos = [combo + [opt] for combo in combos for opt in options]

        return [Composite(op, list(slots)) for slots in combos]

    # =================================================================
    # Tier 3: resource-constrained global search (DAEDALUS)
    # =================================================================

    @property
    def solver(self):
        """Lazily-built Tier-3 solver (DAEDALUS branch-and-bound)."""
        if self._solver is None:
            from .solver import Solver
            self._solver = Solver(self.operad, max_depth=max(self.max_depth, 6))
        return self._solver

    def _tier3(self, spec: Spec) -> Optional[BuildResult]:
        """Return a BUILDABLE result if DAEDALUS finds an in-budget design, else None."""
        result = self.solver.cheapest(spec)
        if not result.found_in_budget:
            return None
        comp = result.best
        return BuildResult(
            verdict=Verdict.BUILDABLE,
            spec=spec,
            construction=Construction(comp, result.best_cost, 3, self._try_realize(comp)),
            tier=3,
            reason="best-ranked in-budget design found by resource-constrained search",
        )

    def _result_from_search(self, spec: Spec, result) -> BuildResult:
        """Map a DAEDALUS SearchResult to a BuildResult with the right verdict."""
        if result.found_in_budget:
            comp = result.best
            return BuildResult(
                verdict=Verdict.BUILDABLE,
                spec=spec,
                construction=Construction(comp, result.best_cost, 3,
                                          self._try_realize(comp)),
                tier=3,
                reason="best-ranked in-budget construction (DAEDALUS)",
            )
        if result.found_any:
            comp = result.best_any
            return BuildResult(
                verdict=Verdict.OVERBUDGET,
                spec=spec,
                construction=Construction(comp, result.best_any_cost, 3,
                                          self._try_realize(comp)),
                tier=3,
                reason=f"best-ranked design {result.best_any_cost} violates figure limits",
            )
        if self.type_gate.is_realizable(spec):
            return BuildResult(
                verdict=Verdict.ILL_TYPED_GAP, spec=spec,
                reason=(f"'{spec.output}' is reachable but no design of depth "
                        f"<= {self.solver.daedalus.max_depth} realizes the interface."),
            )
        return BuildResult(
            verdict=Verdict.IMPOSSIBLE, spec=spec,
            reason=(f"no operation chain produces '{spec.output}' from "
                    f"{list(spec.inputs)}."),
        )

    # =================================================================
    # Negative verdicts
    # =================================================================

    def _negative_verdict(self, spec: Spec, candidates: List[Composite]) -> BuildResult:
        if candidates:
            # A typed wiring exists; it just isn't in budget (or isn't sound).
            best = min(candidates, key=self._cost_scalar)
            sound, cost, reason = self.res_gate.cost(best)
            return BuildResult(
                verdict=Verdict.OVERBUDGET,
                spec=spec,
                construction=Construction(best, cost or {}, -1,
                                          self._try_realize(best)),
                tier=-1,
                reason=reason or f"best-ranked wiring {cost} violates figure limits",
            )

        # No typed wiring. Is the output even reachable in principle?
        if self.type_gate.is_realizable(spec):
            # Reachable in the colour graph but no depth-bounded witness found.
            return BuildResult(
                verdict=Verdict.ILL_TYPED_GAP,
                spec=spec,
                reason=(f"'{spec.output}' is reachable but no wiring of depth "
                        f"<= {self.max_depth} realizes the interface; "
                        f"raise max_depth or add a component."),
            )
        return BuildResult(
            verdict=Verdict.IMPOSSIBLE,
            spec=spec,
            reason=(f"no operation chain produces '{spec.output}' from "
                    f"{list(spec.inputs)} -- a component is missing."),
        )

    # =================================================================
    # Helpers
    # =================================================================

    def _cost_scalar(self, comp: Composite) -> float:
        """Scalarise a composite's figures for ordering (inf if unsound)."""
        sound, cost, _ = self.res_gate.cost(comp)
        if not sound or cost is None:
            return float("inf")
        return self.operad.monoid.rank(cost)

    def _try_realize(self, comp: Composite) -> Optional[callable]:
        """Realize the composite to an artifact, or None if it isn't executable."""
        try:
            return self.operad.realize(comp)
        except ValueError:
            return None
