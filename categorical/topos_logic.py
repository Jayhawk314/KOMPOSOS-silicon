# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Topos-Theoretic Logic: Intuitionistic Reasoning via Presheaf Topos

Bridges the presheaf topos (structural, multi-perspectival truth via sieves)
with ZFC logic (classical, absolute truth). Enables intuitionistic reasoning
where "not false" doesn't mean "true."

The presheaf topos already provides:
  - Sieves as truth values (partial truth from multiple perspectives)
  - Heyting algebra operations (negation, implication, conjunction, disjunction)
  - Subobject classifier (Omega = all sieves)

This module adds:
  1. ToposTruth: explicit truth values with support fractions and classical comparison
  2. IntuitionisticFormula: ZFC formulas interpreted in the internal logic
  3. ToposLogic: the bridge — interpret classical formulas in the topos
  4. ToposDelta: three-way comparison (CAT structure vs ZFC logic vs Topos)

Key insight (intuitionistic logic):
  - Classical: every statement is TRUE or FALSE (excluded middle: P ∨ ¬P)
  - Intuitionistic: a statement can be PARTIALLY true (P ∨ ¬P may fail)
  - NOT NOT P ≠ P in general! "Can't disprove it" ≠ "proved it"
  - This captures partial knowledge: some perspectives confirm, others don't

Kripke-Joyal semantics:
  A formula φ is "true at stage c" iff the maximal sieve at c forces φ.
  Stages are perspectives/observers. Truth is perspectival.

Mathematical basis:
  - Mac Lane & Moerdijk, "Sheaves in Geometry and Logic" (1992), Ch. VI
  - Goldblatt, "Topoi: The Categorial Analysis of Logic" (1984)
  - Caramello, "Theories, Sites, Toposes" (2018)
  - Johnstone, "Sketches of an Elephant" (2002), Part D
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional, Any


@dataclass
class ToposTruth:
    """
    A truth value in the internal logic of a topos.

    Not just True/False — a SIEVE of perspectives that see it as true.
    The support fraction tells you how many perspectives agree.

    Examples:
      support_fraction = 1.0 -> all perspectives agree (classical TRUE)
      support_fraction = 0.0 -> no perspectives agree (classical FALSE)
      support_fraction = 0.6 -> 60% of perspectives see it as true
    """
    support_fraction: float             # [0.0, 1.0]
    perspectives: Set[str]             # which observers see this as true
    total_perspectives: int            # total number of observers
    classical_value: Optional[bool]    # if this reduces to classical T/F
    description: str = ""

    @property
    def is_classical(self) -> bool:
        """Does this truth value reduce to classical True or False?"""
        return self.classical_value is not None

    @property
    def is_maximal(self) -> bool:
        """Is this the maximal sieve (TRUE)?"""
        return self.support_fraction >= 1.0

    @property
    def is_empty(self) -> bool:
        """Is this the empty sieve (FALSE)?"""
        return self.support_fraction <= 0.0 and len(self.perspectives) == 0

    def __repr__(self):
        if self.is_maximal:
            return "⊤ (TRUE)"
        if self.is_empty:
            return "⊥ (FALSE)"
        return f"Ω({self.support_fraction:.2f}, {len(self.perspectives)} perspectives)"


@dataclass
class IntuitionisticFormula:
    """
    A formula with both its classical form and its topos interpretation.

    Pairs a ZFC formula (classical, absolute truth) with its truth value
    in the internal logic of a topos (perspectival, partial truth).
    """
    formula_repr: str           # string representation of the formula
    topos_value: ToposTruth     # its truth value in the topos

    @property
    def is_classical(self) -> bool:
        """Does this formula have a classical (T/F) truth value?"""
        return self.topos_value.classical_value is not None

    @property
    def excluded_middle_holds(self) -> bool:
        """Is P ∨ ¬P = TRUE for this formula?"""
        return self.topos_value.is_maximal or self.topos_value.is_empty

    def __repr__(self):
        return f"⟦{self.formula_repr}⟧ = {self.topos_value}"


class ToposLogic:
    """
    Intuitionistic logic via a presheaf topos.

    Takes a presheaf topos (from presheaf_topos.py) and provides
    logical operations in its internal language. The key difference
    from classical logic: the law of excluded middle can fail.
    """

    def __init__(self, topos=None):
        """
        Args:
            topos: A PresheafTopos instance (from presheaf_topos.py).
                   If None, creates an empty logic system.
        """
        self.topos = topos

    def _sieve_to_truth(self, sieve, description: str = "") -> ToposTruth:
        """Convert a Sieve object to a ToposTruth."""
        perspectives = sieve.from_perspectives()
        total = self.topos.incoming_count(sieve.target) if self.topos else 0
        if total == 0:
            total = max(len(perspectives), 1)
        fraction = len(perspectives) / total if total > 0 else 0.0

        classical = None
        if fraction >= 1.0:
            classical = True
        elif fraction <= 0.0 and len(perspectives) == 0:
            classical = False

        return ToposTruth(
            support_fraction=fraction,
            perspectives=perspectives,
            total_perspectives=total,
            classical_value=classical,
            description=description,
        )

    def truth(self, target: str, description: str = "") -> ToposTruth:
        """
        The maximal truth value: TRUE (all perspectives agree).

        In the subobject classifier, this is the maximal sieve.
        """
        if self.topos is None:
            return ToposTruth(1.0, set(), 0, True, description)

        sieve = self.topos.maximal_sieve(target)
        result = self._sieve_to_truth(sieve, description)
        result.classical_value = True
        return result

    def falsity(self, target: str, description: str = "") -> ToposTruth:
        """
        The minimal truth value: FALSE (no perspectives agree).

        In the subobject classifier, this is the empty sieve.
        """
        if self.topos is None:
            return ToposTruth(0.0, set(), 0, False, description)

        return ToposTruth(
            support_fraction=0.0,
            perspectives=set(),
            total_perspectives=self.topos.incoming_count(target),
            classical_value=False,
            description=description,
        )

    def interpret_atomic(self, observed: List[str],
                         target: str) -> ToposTruth:
        """
        Interpret an atomic proposition: "target is supported by observed."

        Uses the topos's classify method to build a sieve from observations.
        The truth value is the fraction of perspectives that see evidence.
        """
        if self.topos is None:
            return ToposTruth(0.0, set(), 0, None,
                              f"No topos for {target}")

        sieve = self.topos.classify_attack(observed, target)
        return self._sieve_to_truth(
            sieve,
            f"{target} supported by {observed}"
        )

    def negate(self, truth: ToposTruth) -> ToposTruth:
        """
        Intuitionistic negation: ¬P = (P → ⊥).

        The negation of P consists of perspectives that are INCOMPATIBLE
        with P — not just "not in P" but "no extension leads to P."

        In classical logic: ¬P = everything not in P.
        In intuitionistic logic: ¬P can be SMALLER than the complement.
        This is why ¬¬P ≠ P in general.
        """
        if truth.total_perspectives == 0:
            return ToposTruth(1.0, set(), 0, True, f"¬({truth.description})")

        # Compute complement perspectives
        all_persp = self._get_all_perspectives()
        negated_persp = all_persp - truth.perspectives
        total = truth.total_perspectives

        neg_fraction = len(negated_persp) / total if total > 0 else 0.0

        classical = None
        if truth.classical_value is True:
            classical = False
        elif truth.classical_value is False:
            classical = True

        return ToposTruth(
            support_fraction=neg_fraction,
            perspectives=negated_persp,
            total_perspectives=total,
            classical_value=classical,
            description=f"¬({truth.description})",
        )

    def double_negate(self, truth: ToposTruth) -> ToposTruth:
        """
        Double negation: ¬¬P.

        In classical logic: ¬¬P = P (always).
        In intuitionistic logic: ¬¬P ≥ P but may not equal P.
        The gap ¬¬P \\ P is the "can't disprove but can't constructively prove" zone.
        """
        neg = self.negate(truth)
        return self.negate(neg)

    def conjunction(self, a: ToposTruth, b: ToposTruth) -> ToposTruth:
        """
        Conjunction: P ∧ Q.

        True at perspectives where BOTH P and Q hold.
        Intersection of perspective sets.
        """
        conj_persp = a.perspectives & b.perspectives
        total = max(a.total_perspectives, b.total_perspectives)
        fraction = len(conj_persp) / total if total > 0 else 0.0

        classical = None
        if a.classical_value is not None and b.classical_value is not None:
            classical = a.classical_value and b.classical_value

        return ToposTruth(
            support_fraction=fraction,
            perspectives=conj_persp,
            total_perspectives=total,
            classical_value=classical,
            description=f"({a.description}) ∧ ({b.description})",
        )

    def disjunction(self, a: ToposTruth, b: ToposTruth) -> ToposTruth:
        """
        Disjunction: P ∨ Q.

        True at perspectives where AT LEAST ONE of P or Q holds.
        Union of perspective sets.

        Note: In intuitionistic logic, P ∨ ¬P is NOT always TRUE.
        This is the key difference from classical logic.
        """
        disj_persp = a.perspectives | b.perspectives
        total = max(a.total_perspectives, b.total_perspectives)
        fraction = len(disj_persp) / total if total > 0 else 0.0

        classical = None
        if a.classical_value is not None and b.classical_value is not None:
            classical = a.classical_value or b.classical_value

        return ToposTruth(
            support_fraction=fraction,
            perspectives=disj_persp,
            total_perspectives=total,
            classical_value=classical,
            description=f"({a.description}) ∨ ({b.description})",
        )

    def implication(self, premise: ToposTruth,
                    conclusion: ToposTruth) -> ToposTruth:
        """
        Heyting implication: P → Q.

        True at perspectives where: if P holds here, then Q also holds.
        This is the largest sieve S such that S ∩ P ⊆ Q.

        Computed as: ¬P ∨ Q (classical approximation) but in the topos
        this is actually the exponential object.
        """
        neg_premise = self.negate(premise)
        return self.disjunction(neg_premise, conclusion)

    def excluded_middle_check(self, truth: ToposTruth) -> Dict[str, Any]:
        """
        Check if excluded middle holds for this truth value.

        Computes P ∨ ¬P and checks if it equals the maximal sieve.
        When it fails, returns the "gap" — perspectives where neither
        P nor ¬P holds.

        Returns:
            {
                "holds": bool,
                "p_or_not_p_fraction": float,
                "gap_perspectives": set (where neither holds),
                "gap_fraction": float,
            }
        """
        neg = self.negate(truth)
        p_or_not_p = self.disjunction(truth, neg)

        all_persp = self._get_all_perspectives()
        gap = all_persp - p_or_not_p.perspectives

        return {
            "holds": p_or_not_p.is_maximal,
            "p_or_not_p_fraction": p_or_not_p.support_fraction,
            "gap_perspectives": gap,
            "gap_fraction": len(gap) / max(len(all_persp), 1),
        }

    def double_negation_check(self, truth: ToposTruth) -> Dict[str, Any]:
        """
        Check if ¬¬P = P for this truth value.

        When ¬¬P > P, there are perspectives where we "can't disprove P"
        but also "can't constructively prove P." This is the zone of
        partial knowledge.

        Returns:
            {
                "holds": bool (¬¬P == P),
                "p_fraction": float,
                "not_not_p_fraction": float,
                "gap_fraction": float (¬¬P - P, the partial knowledge zone),
            }
        """
        nnp = self.double_negate(truth)

        gap = nnp.support_fraction - truth.support_fraction

        return {
            "holds": abs(gap) < 1e-9,
            "p_fraction": truth.support_fraction,
            "not_not_p_fraction": nnp.support_fraction,
            "gap_fraction": max(gap, 0.0),
        }

    def where_excluded_middle_fails(self) -> List[Dict[str, Any]]:
        """
        Find all atomic formulas where P ∨ ¬P ≠ TRUE.

        These are the places where partial knowledge matters.
        Scans all objects in the topos and checks excluded middle
        for each object's characteristic sieve.
        """
        if self.topos is None:
            return []

        failures = []
        for obj in self.topos.objects:
            # Build truth for "obj is reachable"
            sieve = self.topos.maximal_sieve(obj)
            truth = self._sieve_to_truth(sieve, f"reachable({obj})")

            check = self.excluded_middle_check(truth)
            if not check["holds"]:
                failures.append({
                    "object": obj,
                    "p_or_not_p_fraction": check["p_or_not_p_fraction"],
                    "gap_fraction": check["gap_fraction"],
                    "gap_perspectives": check["gap_perspectives"],
                })

        return failures

    def support_for(self, observed: List[str], target: str) -> float:
        """
        What fraction of perspectives support the claim about target?

        0.0 = no perspective sees it as true.
        1.0 = all perspectives see it as true (classical TRUE).
        """
        truth = self.interpret_atomic(observed, target)
        return truth.support_fraction

    def compare_with_classical(self, observed: List[str], target: str,
                               classical_truth: Optional[bool] = None
                               ) -> Dict[str, Any]:
        """
        Compare intuitionistic and classical truth for a claim.

        Returns:
            {
                "classical_says": bool or None,
                "topos_says": ToposTruth,
                "agreement": str,
                "excluded_middle_gap": float,
            }
        """
        topos_truth = self.interpret_atomic(observed, target)

        # Determine agreement
        if classical_truth is None:
            agreement = "no_classical_value"
        elif classical_truth and topos_truth.is_maximal:
            agreement = "agree"
        elif not classical_truth and topos_truth.is_empty:
            agreement = "agree"
        elif classical_truth and not topos_truth.is_maximal:
            agreement = "classical_only"
        elif not classical_truth and not topos_truth.is_empty:
            agreement = "topos_only"
        else:
            agreement = "disagree"

        em_check = self.excluded_middle_check(topos_truth)

        return {
            "classical_says": classical_truth,
            "topos_says": topos_truth,
            "agreement": agreement,
            "excluded_middle_gap": em_check["gap_fraction"],
        }

    def _get_all_perspectives(self) -> Set[str]:
        """Get all possible perspectives (objects in the topos)."""
        if self.topos is None:
            return set()
        return set(self.topos.objects)


class ToposDelta:
    """
    Three-way comparison: CAT structure vs ZFC logic vs Topos internal logic.

    This extends the existing Dual Engine (CAT + ZFC -> AGREE/ORPHAN/HOLLOW/REJECT)
    with a third axis: the topos's perspectival truth.

    The delta reveals:
    - full_agree: all three say yes
    - classical_agree_topos_partial: CAT+ZFC agree but topos is partial
    - topos_only: topos sees partial truth that CAT+ZFC miss
    - classical_only: CAT+ZFC agree but topos says no
    - structure_only: CAT yes, ZFC no, topos partial (structurally plausible)
    - logic_only: ZFC yes, CAT no, topos partial (logically valid)
    - none: nobody says yes
    """

    def __init__(self, topos_logic: ToposLogic):
        self.logic = topos_logic

    def classify(self, source: str, target: str,
                 cat_says: Optional[bool] = None,
                 zfc_says: Optional[bool] = None,
                 observed: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Three-way classification of a claim.

        Args:
            source: Source concept
            target: Target concept
            cat_says: Does the categorical engine find structural support?
            zfc_says: Does the ZFC engine find logical support?
            observed: Observed evidence (for topos interpretation)

        Returns:
            {
                "cat_says": bool or None,
                "zfc_says": bool or None,
                "topos_says": ToposTruth,
                "delta": str (classification),
                "insight": str (what the disagreement means),
            }
        """
        # Get topos truth
        obs = observed or [source]
        topos_truth = self.logic.interpret_atomic(obs, target)

        # Classify the delta
        topos_yes = topos_truth.support_fraction > 0.0
        topos_full = topos_truth.is_maximal

        if cat_says is None or zfc_says is None:
            delta = "incomplete"
            insight = "Missing classical engine results"
        elif cat_says and zfc_says and topos_full:
            delta = "full_agree"
            insight = "All three engines agree: strong evidence"
        elif cat_says and zfc_says and topos_yes:
            delta = "classical_agree_topos_partial"
            insight = (
                f"Structure and logic agree, but only "
                f"{topos_truth.support_fraction:.0%} of perspectives confirm"
            )
        elif cat_says and zfc_says and not topos_yes:
            delta = "classical_only"
            insight = "Structure and logic agree, but no perspective sees it"
        elif not cat_says and not zfc_says and topos_yes:
            delta = "topos_only"
            insight = (
                f"No structural or logical support, but "
                f"{topos_truth.support_fraction:.0%} of perspectives see "
                f"partial evidence — worth investigating"
            )
        elif cat_says and not zfc_says and topos_yes:
            delta = "structure_and_topos"
            insight = (
                "Structurally plausible and partially observed, "
                "but not logically proven"
            )
        elif not cat_says and zfc_says and topos_yes:
            delta = "logic_and_topos"
            insight = (
                "Logically valid and partially observed, "
                "but no structural path exists"
            )
        elif cat_says and not zfc_says:
            delta = "structure_only"
            insight = "Structural path exists but not logically supported"
        elif not cat_says and zfc_says:
            delta = "logic_only"
            insight = "Logically valid but no structural path"
        else:
            delta = "none"
            insight = "No engine finds support"

        return {
            "cat_says": cat_says,
            "zfc_says": zfc_says,
            "topos_says": topos_truth,
            "delta": delta,
            "insight": insight,
        }


# =============================================================================
# Heyting Algebra (standalone, no topos required)
# =============================================================================

class HeytingAlgebra:
    """
    A finite Heyting algebra for intuitionistic propositional logic.

    A Heyting algebra is a bounded lattice with:
    - Meet (∧): greatest lower bound
    - Join (∨): least upper bound
    - Top (⊤): greatest element
    - Bottom (⊥): least element
    - Pseudocomplement (→): a → b = max{c | c ∧ a ≤ b}
    - Negation: ¬a = a → ⊥

    Unlike Boolean algebras, ¬¬a ≠ a in general.
    This makes the logic intuitionistic rather than classical.
    """

    def __init__(self, elements: List[str],
                 order: Dict[str, Set[str]]):
        """
        Args:
            elements: The elements of the lattice
            order: Partial order as {element: {elements it's ≤ to}}
                   Must include reflexive and transitive closure.
        """
        self.elements = list(elements)
        self.order = {e: set(s) for e, s in order.items()}
        self._top = self._find_top()
        self._bottom = self._find_bottom()

    def _find_top(self) -> str:
        """Find the top element (≤ everything)."""
        for e in self.elements:
            if all(e in self.order.get(x, set()) or e == x
                   for x in self.elements):
                # Everything is ≤ e
                pass
            # Check: e is above everything
            if all(x in self.order.get(x, set()) and e in self.order.get(x, {e})
                   for x in self.elements):
                return e
        # Fallback: element that everything maps to
        for e in self.elements:
            if all(e in self.order.get(x, set()) for x in self.elements):
                return e
        return self.elements[-1] if self.elements else ""

    def _find_bottom(self) -> str:
        """Find the bottom element (everything ≤ it)."""
        for e in self.elements:
            if all(x in self.order.get(e, set()) or e == x
                   for x in self.elements):
                return e
        return self.elements[0] if self.elements else ""

    def leq(self, a: str, b: str) -> bool:
        """Check if a ≤ b in the partial order."""
        if a == b:
            return True
        return b in self.order.get(a, set())

    def meet(self, a: str, b: str) -> str:
        """
        Greatest lower bound: a ∧ b.

        The largest element c such that c ≤ a and c ≤ b.
        """
        candidates = [
            c for c in self.elements
            if self.leq(c, a) and self.leq(c, b)
        ]
        if not candidates:
            return self._bottom

        # Find the greatest among candidates
        best = candidates[0]
        for c in candidates[1:]:
            if self.leq(best, c):
                best = c
        return best

    def join(self, a: str, b: str) -> str:
        """
        Least upper bound: a ∨ b.

        The smallest element c such that a ≤ c and b ≤ c.
        """
        candidates = [
            c for c in self.elements
            if self.leq(a, c) and self.leq(b, c)
        ]
        if not candidates:
            return self._top

        # Find the least among candidates
        best = candidates[0]
        for c in candidates[1:]:
            if self.leq(c, best):
                best = c
        return best

    def implies(self, a: str, b: str) -> str:
        """
        Pseudocomplement (Heyting implication): a → b.

        The largest element c such that c ∧ a ≤ b.
        This is the relative pseudocomplement.
        """
        candidates = [
            c for c in self.elements
            if self.leq(self.meet(c, a), b)
        ]
        if not candidates:
            return self._bottom

        best = candidates[0]
        for c in candidates[1:]:
            if self.leq(best, c):
                best = c
        return best

    def negation(self, a: str) -> str:
        """
        Pseudocomplement (Heyting negation): ¬a = a → ⊥.

        Note: ¬¬a ≥ a but ¬¬a ≠ a in general!
        """
        return self.implies(a, self._bottom)

    def is_boolean(self) -> bool:
        """
        Check if this Heyting algebra is Boolean.

        Boolean iff ¬¬a = a for all a (excluded middle holds everywhere).
        """
        for a in self.elements:
            nna = self.negation(self.negation(a))
            if nna != a:
                return False
        return True

    def excluded_middle_failures(self) -> List[Dict[str, str]]:
        """Find all elements where a ∨ ¬a ≠ ⊤."""
        failures = []
        for a in self.elements:
            neg_a = self.negation(a)
            a_or_neg_a = self.join(a, neg_a)
            if a_or_neg_a != self._top:
                failures.append({
                    "element": a,
                    "negation": neg_a,
                    "join": a_or_neg_a,
                    "top": self._top,
                })
        return failures

    @property
    def top(self) -> str:
        return self._top

    @property
    def bottom(self) -> str:
        return self._bottom

    def __repr__(self):
        return (f"HeytingAlgebra(|elements|={len(self.elements)}, "
                f"boolean={self.is_boolean()})")
