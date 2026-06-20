# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
Separation-Based Coherence — The ZFC Consistency Engine

Sits alongside logic.py the way coherence.py sits alongside strategies.py.

coherence.py:   SheafCoherenceChecker — "do local sections glue globally?"
separation.py:  SeparationChecker     — "is the filtered subset consistent?"

Both are coherence engines. Both filter predictions.
But they filter by DIFFERENT criteria:

Sheaf coherence asks: are the pieces compositionally compatible?
    "If A→B says 'inhibits' and B→C says 'activates',
     can A→C coherently be 'inhibits'?"

Separation coherence asks: does the constraint set have a model?
    "If we assert inhibits(A,B) AND activates(B,C) AND inhibits(A,C),
     is there any universe where all three hold simultaneously?"

The delta: sheaf coherence can say "these compose fine" when the
constraint set is actually unsatisfiable. And separation can say
"these are all individually satisfiable" when they don't compose.

Components:
1. ConstraintSet      — predicates extracted from predictions
2. ConsistencyCheck   — does the constraint set have a model?
3. MinimalConflict    — find the smallest inconsistent subset
4. SeparationChecker  — the main coherence engine
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any, Callable, Dict, List, Optional, Set as PySet,
    Tuple,
)

from .universe import Universe, ZFSet, Relation
from .logic import (
    Formula, FormulaKind, Term,
    atom, neg, conj, disj, implies, forall, exists,
    var, const, conj_all,
    Model, satisfies, find_witness, Theory,
)


# ═══════════════════════════════════════════════════════════════════
# Prediction → Constraint translation
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Constraint:
    """
    A constraint derived from a prediction.

    Each KOMPOSOS prediction becomes a logical constraint:
    - "Drug X inhibits Protein Y" → atom("inhibits", const("X"), const("Y"))
    - "Drug X does NOT treat Disease Z" → neg(atom("treats", const("X"), const("Z")))

    Constraints carry metadata: source prediction, confidence, strategy.
    """
    formula: Formula
    source_prediction: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    strategy: str = "unknown"

    def __repr__(self):
        return f"Constraint({self.formula}, conf={self.confidence:.2f})"


def prediction_to_constraint(prediction: Dict[str, Any]) -> Constraint:
    """
    Convert a KOMPOSOS prediction dict to a logical constraint.

    Expected prediction format:
    {
        "source": str,
        "target": str,
        "relation": str,
        "confidence": float,
        "strategy": str,
        "negated": bool (optional, default False)
    }
    """
    source = prediction.get("source", "")
    target = prediction.get("target", "")
    rel = prediction.get("relation", "")
    conf = prediction.get("confidence", 0.0)
    strategy = prediction.get("strategy", "unknown")
    negated = prediction.get("negated", False)

    formula = atom(rel, const(source), const(target))
    if negated:
        formula = neg(formula)

    return Constraint(
        formula=formula,
        source_prediction=prediction,
        confidence=conf,
        strategy=strategy,
    )


def predictions_to_constraints(
    predictions: List[Dict[str, Any]],
) -> List[Constraint]:
    """Convert a batch of predictions to constraints."""
    return [prediction_to_constraint(p) for p in predictions]


# ═══════════════════════════════════════════════════════════════════
# Contradiction Detection
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Contradiction:
    """
    A detected contradiction between constraints.

    Two constraints contradict if one asserts R(a,b) and
    the other asserts ¬R(a,b), or if they assert relations
    that are defined as mutually exclusive.
    """
    constraint_a: Constraint
    constraint_b: Constraint
    contradiction_type: str  # "direct_negation", "mutual_exclusion", "axiom_violation"
    explanation: str = ""


# Standard mutual exclusion pairs (domain-configurable)
DEFAULT_EXCLUSIONS = [
    ("inhibits", "activates"),
    ("activates", "inhibits"),
    ("upregulates", "downregulates"),
    ("downregulates", "upregulates"),
    ("causes", "prevents"),
    ("prevents", "causes"),
    ("agonist", "antagonist"),
    ("antagonist", "agonist"),
    ("increases", "decreases"),
    ("decreases", "increases"),
]


def detect_pairwise_contradictions(
    constraints: List[Constraint],
    exclusion_pairs: Optional[List[Tuple[str, str]]] = None,
) -> List[Contradiction]:
    """
    Detect contradictions between pairs of constraints.

    Mirror of: SheafCoherenceChecker._check_antonyms
    Both check for pairwise conflicts. But sheaf uses hardcoded
    antonym lists. This uses logical negation + configurable exclusions.
    """
    if exclusion_pairs is None:
        exclusion_pairs = DEFAULT_EXCLUSIONS

    exclusion_set = set(exclusion_pairs)
    contradictions = []

    # Index constraints by (source, target) for efficient lookup
    by_pair: Dict[Tuple[str, str], List[Constraint]] = {}
    for c in constraints:
        pred = c.source_prediction
        key = (pred.get("source", ""), pred.get("target", ""))
        by_pair.setdefault(key, []).append(c)

    for key, group in by_pair.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                ci, cj = group[i], group[j]
                pi, pj = ci.source_prediction, cj.source_prediction
                ri = pi.get("relation", "")
                rj = pj.get("relation", "")
                ni = pi.get("negated", False)
                nj = pj.get("negated", False)

                # Direct negation: R(a,b) and ¬R(a,b)
                if ri == rj and ni != nj:
                    contradictions.append(Contradiction(
                        constraint_a=ci,
                        constraint_b=cj,
                        contradiction_type="direct_negation",
                        explanation=f"{ri}({key[0]},{key[1]}) asserted both true and false",
                    ))

                # Mutual exclusion: R(a,b) and S(a,b) where R,S are exclusive
                if not ni and not nj and (ri, rj) in exclusion_set:
                    contradictions.append(Contradiction(
                        constraint_a=ci,
                        constraint_b=cj,
                        contradiction_type="mutual_exclusion",
                        explanation=f"{ri} and {rj} are mutually exclusive for ({key[0]},{key[1]})",
                    ))

    return contradictions


# ═══════════════════════════════════════════════════════════════════
# Minimal Conflict Set (MUS — Minimal Unsatisfiable Subset)
# ═══════════════════════════════════════════════════════════════════

def find_minimal_conflict(
    constraints: List[Constraint],
    model: Model,
) -> Optional[List[Constraint]]:
    """
    Find a minimal unsatisfiable subset of constraints.

    If the full set is satisfiable, returns None.
    Otherwise, returns the smallest subset that is still unsatisfiable.

    This is the MUS (Minimal Unsatisfiable Subset) problem.
    For production, delegate to a MUS extractor in Z3.
    Here we use a simple deletion-based algorithm.

    Mirror of: nothing in KOMPOSOS-CAT
    This is a genuinely new capability that ZFC provides.
    Categories don't have a natural "minimal conflict" concept
    because composition either works or it doesn't.
    ZFC can find the SMALLEST set of constraints that conflict.
    """
    # First: is the full set satisfiable?
    if all(satisfies(model, c.formula) for c in constraints):
        return None  # no conflict

    # Deletion-based MUS: try removing each constraint
    # If still unsatisfiable without it, it's not needed
    # If satisfiable without it, it's essential to the conflict
    essential = list(range(len(constraints)))

    for idx in range(len(constraints)):
        # Try without constraint idx
        without = [constraints[i] for i in essential if i != idx]
        if not without:
            continue

        still_unsat = not all(satisfies(model, c.formula) for c in without)
        if still_unsat:
            # Constraint idx is not essential — remove it
            essential = [i for i in essential if i != idx]

    return [constraints[i] for i in essential]


# ═══════════════════════════════════════════════════════════════════
# SeparationChecker — the main coherence engine
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SeparationResult:
    """
    Result of separation-based coherence checking.

    Mirror of: CoherenceResult from sheaf checker
    But richer: includes MUS, contradiction classification, and
    satisfiability witness.
    """
    is_consistent: bool
    num_constraints: int
    num_contradictions: int
    contradictions: List[Contradiction]
    minimal_conflict: Optional[List[Constraint]]
    witness: Optional[Dict[str, str]]  # satisfying assignment if consistent
    filtered_predictions: List[Dict[str, Any]]  # predictions that survived
    removed_predictions: List[Dict[str, Any]]   # predictions removed for consistency
    analysis: str = ""


class SeparationChecker:
    """
    Coherence checking via ZFC separation and constraint satisfaction.

    Mirror of: SheafCoherenceChecker
    Sheaf checker: groups predictions, checks pairwise antonyms,
                   filters lower-confidence member of conflicting pairs.
    Separation checker: converts predictions to logical constraints,
                        checks satisfiability, finds minimal conflicts,
                        removes minimum constraints to restore consistency.

    The key difference:
    - Sheaf checks LOCAL agreement (pairs of overlapping sections)
    - Separation checks GLOBAL consistency (all constraints simultaneously)

    Sheaf can miss global inconsistencies that emerge from chains.
    Separation catches those but might miss compositional structure.
    THAT'S the delta.
    """

    def __init__(self, universe: Universe,
                 exclusion_pairs: Optional[List[Tuple[str, str]]] = None):
        self.universe = universe
        self.exclusion_pairs = exclusion_pairs or DEFAULT_EXCLUSIONS

    def check(
        self,
        predictions: List[Dict[str, Any]],
        model: Optional[Model] = None,
    ) -> SeparationResult:
        """
        Check coherence of a prediction batch.

        Steps:
        1. Convert predictions to constraints
        2. Detect pairwise contradictions
        3. Check global satisfiability (if model provided)
        4. Find minimal conflict set
        5. Remove minimum predictions to restore consistency
        6. Return filtered set + analysis

        Args:
            predictions: list of prediction dicts
            model: Model for satisfiability checking (optional)

        Returns:
            SeparationResult with full analysis
        """
        if not predictions:
            return SeparationResult(
                is_consistent=True,
                num_constraints=0,
                num_contradictions=0,
                contradictions=[],
                minimal_conflict=None,
                witness=None,
                filtered_predictions=[],
                removed_predictions=[],
                analysis="No predictions to check.",
            )

        # Step 1: Convert
        constraints = predictions_to_constraints(predictions)

        # Step 2: Pairwise contradictions
        contradictions = detect_pairwise_contradictions(
            constraints, self.exclusion_pairs
        )

        # Step 3: Global satisfiability
        witness = None
        minimal_conflict = None

        if model is not None:
            # Check all constraints against the model
            all_sat = all(satisfies(model, c.formula) for c in constraints)

            if not all_sat:
                # Step 4: Find minimal conflict
                minimal_conflict = find_minimal_conflict(constraints, model)
        else:
            # Without a model, rely on pairwise analysis
            all_sat = len(contradictions) == 0

        # Step 5: Remove minimum predictions for consistency
        removed_indices: PySet[int] = set()

        if contradictions:
            # For each contradiction, remove the lower-confidence prediction
            for c in contradictions:
                idx_a = next(
                    (i for i, p in enumerate(predictions)
                     if p is c.constraint_a.source_prediction),
                    None
                )
                idx_b = next(
                    (i for i, p in enumerate(predictions)
                     if p is c.constraint_b.source_prediction),
                    None
                )

                if idx_a is not None and idx_b is not None:
                    if c.constraint_a.confidence <= c.constraint_b.confidence:
                        removed_indices.add(idx_a)
                    else:
                        removed_indices.add(idx_b)

        if minimal_conflict and model is not None:
            # Also remove predictions in the minimal conflict set
            for mc in minimal_conflict:
                idx = next(
                    (i for i, p in enumerate(predictions)
                     if p is mc.source_prediction),
                    None
                )
                if idx is not None:
                    removed_indices.add(idx)

        filtered = [p for i, p in enumerate(predictions) if i not in removed_indices]
        removed = [p for i, p in enumerate(predictions) if i in removed_indices]

        # Step 6: Analysis
        analysis = self._generate_analysis(
            predictions, constraints, contradictions,
            minimal_conflict, all_sat, filtered, removed,
        )

        return SeparationResult(
            is_consistent=all_sat and len(contradictions) == 0,
            num_constraints=len(constraints),
            num_contradictions=len(contradictions),
            contradictions=contradictions,
            minimal_conflict=minimal_conflict,
            witness=witness,
            filtered_predictions=filtered,
            removed_predictions=removed,
            analysis=analysis,
        )

    def _generate_analysis(
        self,
        predictions: List[Dict[str, Any]],
        constraints: List[Constraint],
        contradictions: List[Contradiction],
        minimal_conflict: Optional[List[Constraint]],
        globally_sat: bool,
        filtered: List[Dict[str, Any]],
        removed: List[Dict[str, Any]],
    ) -> str:
        lines = []
        lines.append(f"Separation Coherence Analysis")
        lines.append(f"  Predictions: {len(predictions)}")
        lines.append(f"  Constraints: {len(constraints)}")
        lines.append(f"  Contradictions: {len(contradictions)}")
        lines.append(f"  Globally satisfiable: {globally_sat}")
        lines.append(f"  Filtered (kept): {len(filtered)}")
        lines.append(f"  Removed: {len(removed)}")

        if contradictions:
            lines.append(f"")
            lines.append(f"  Contradictions found:")
            for c in contradictions:
                lines.append(f"    [{c.contradiction_type}] {c.explanation}")

        if minimal_conflict:
            lines.append(f"")
            lines.append(f"  Minimal conflict set ({len(minimal_conflict)} constraints):")
            for mc in minimal_conflict:
                lines.append(f"    {mc.formula} (conf={mc.confidence:.2f}, strategy={mc.strategy})")

        return "\n".join(lines)

    def compare_with_sheaf(
        self,
        predictions: List[Dict[str, Any]],
        sheaf_filtered: List[Dict[str, Any]],
        model: Optional[Model] = None,
    ) -> Dict[str, Any]:
        """
        Compare separation results with sheaf coherence results.

        This is the DELTA between the two coherence methods.
        Takes predictions and what sheaf coherence kept,
        runs separation, and reports disagreements.

        Args:
            predictions: original prediction batch
            sheaf_filtered: what SheafCoherenceChecker kept
            model: optional model for satisfiability

        Returns:
            Comparison report
        """
        sep_result = self.check(predictions, model)

        sheaf_set = {
            (p.get("source"), p.get("target"), p.get("relation"))
            for p in sheaf_filtered
        }
        sep_set = {
            (p.get("source"), p.get("target"), p.get("relation"))
            for p in sep_result.filtered_predictions
        }

        both_keep = sheaf_set & sep_set
        sheaf_only = sheaf_set - sep_set      # sheaf keeps, separation removes
        sep_only = sep_set - sheaf_set        # separation keeps, sheaf removes
        both_remove = (
            {(p.get("source"), p.get("target"), p.get("relation")) for p in predictions}
            - sheaf_set - sep_set
        )

        return {
            "total_predictions": len(predictions),
            "both_keep": len(both_keep),
            "sheaf_only": len(sheaf_only),
            "separation_only": len(sep_only),
            "both_remove": len(both_remove),
            "agreement_rate": len(both_keep) / max(len(predictions), 1),
            # The interesting cases:
            "sheaf_keeps_but_sep_removes": sorted(sheaf_only),
            "sep_keeps_but_sheaf_removes": sorted(sep_only),
            "separation_contradictions": len(sep_result.contradictions),
            "separation_consistent": sep_result.is_consistent,
        }


# ═══════════════════════════════════════════════════════════════════
# Example usage
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from .universe import zfset, relation as mk_relation

    V = Universe("DrugTest")

    drugs = V.add_set(zfset("Drugs"))
    aspirin = V.add_set(zfset("Aspirin"))
    celecoxib = V.add_set(zfset("Celecoxib"))
    cox2 = V.add_set(zfset("COX2"))

    V.add_element(aspirin, drugs)
    V.add_element(celecoxib, drugs)

    inhibits = mk_relation("inhibits", [("Aspirin", "COX2"), ("Celecoxib", "COX2")])
    activates = mk_relation("activates", [])
    V.add_relation(inhibits)
    V.add_relation(activates)

    checker = SeparationChecker(V)

    # Test: contradictory predictions
    predictions = [
        {"source": "Aspirin", "target": "COX2", "relation": "inhibits",
         "confidence": 0.9, "strategy": "composition"},
        {"source": "Aspirin", "target": "COX2", "relation": "activates",
         "confidence": 0.4, "strategy": "semantic"},
    ]

    result = checker.check(predictions)
    print(result.analysis)
    print(f"\nKept: {result.filtered_predictions}")
    print(f"Removed: {result.removed_predictions}")
