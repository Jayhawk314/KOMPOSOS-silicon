# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
First-Order Logic over ZFC — The Reasoning Engine

Sits on top of universe.py the way kan_extensions.py sits on category.py.

kan_extensions.py: Functor → CommaCategory → Colimit → Prediction
logic.py:          Formula → Model → Satisfaction → Entailment

Where Kan extensions ask:
    "Given what we know (functor F), what does the universal property
     predict for this unknown object?"

Logic asks:
    "Given what we assert (axioms Γ), what must be true in every
     model satisfying Γ?"

Both are prediction engines. One predicts via structure (colimits).
The other predicts via truth (entailment).

The delta: when a Kan extension predicts X but no model satisfying
the axioms contains X, that's a construction failure — structurally
plausible but logically impossible.

Components:
1. Term / Formula    — the language (atoms, connectives, quantifiers)
2. Model             — an interpretation (universe + assignment)
3. Satisfaction      — does a model make a formula true? (M ⊨ φ)
4. Theory            — a set of axioms (formulas assumed true)
5. Entailment        — does a theory force a conclusion? (Γ ⊨ φ)
6. LogicOracle       — the prediction interface (mirror of KanExtensionOracle)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any, Callable, Dict, FrozenSet, List,
    Optional, Set as PySet, Tuple, Union,
)

from .universe import Universe, ZFSet, Relation


# ═══════════════════════════════════════════════════════════════════
# Terms and Formulas — the language
# ═══════════════════════════════════════════════════════════════════

class FormulaKind(Enum):
    """Types of formulas in first-order logic."""
    ATOM = auto()         # R(t1, t2)  — a relation holds
    MEMBERSHIP = auto()   # t1 ∈ t2    — the primitive ZFC relation
    EQUALITY = auto()     # t1 = t2    — identity
    NOT = auto()          # ¬φ
    AND = auto()          # φ ∧ ψ
    OR = auto()           # φ ∨ ψ
    IMPLIES = auto()      # φ → ψ
    IFF = auto()          # φ ↔ ψ
    FORALL = auto()       # ∀x.φ(x)
    EXISTS = auto()       # ∃x.φ(x)


@dataclass(frozen=True)
class Term:
    """
    A term in first-order logic.

    Either a variable (name, unbound) or a constant (name, bound to a set).
    """
    name: str
    is_variable: bool = True

    def __repr__(self):
        return self.name


def var(name: str) -> Term:
    """Create a variable term."""
    return Term(name=name, is_variable=True)


def const(name: str) -> Term:
    """Create a constant term."""
    return Term(name=name, is_variable=False)


@dataclass(frozen=True)
class Formula:
    """
    A formula in first-order logic over ZFC.

    Mirror of: categorical Morphism (in the internal logic of a topos)
    But simpler: no composition law, just truth values.

    Formulas are the CLAIMS we make about the universe.
    Models are the WORLDS where claims might be true.
    Satisfaction is the JUDGMENT: does this world make this claim true?
    """
    kind: FormulaKind
    # For atoms: relation name and argument terms
    relation: Optional[str] = None
    args: Tuple[Term, ...] = ()
    # For connectives: subformulas
    left: Optional[Formula] = None
    right: Optional[Formula] = None
    # For quantifiers: bound variable and body
    variable: Optional[str] = None
    body: Optional[Formula] = None

    def __repr__(self):
        if self.kind == FormulaKind.ATOM:
            args_str = ", ".join(str(a) for a in self.args)
            return f"{self.relation}({args_str})"
        elif self.kind == FormulaKind.MEMBERSHIP:
            return f"{self.args[0]} ∈ {self.args[1]}"
        elif self.kind == FormulaKind.EQUALITY:
            return f"{self.args[0]} = {self.args[1]}"
        elif self.kind == FormulaKind.NOT:
            return f"¬{self.left}"
        elif self.kind == FormulaKind.AND:
            return f"({self.left} ∧ {self.right})"
        elif self.kind == FormulaKind.OR:
            return f"({self.left} ∨ {self.right})"
        elif self.kind == FormulaKind.IMPLIES:
            return f"({self.left} → {self.right})"
        elif self.kind == FormulaKind.IFF:
            return f"({self.left} ↔ {self.right})"
        elif self.kind == FormulaKind.FORALL:
            return f"∀{self.variable}.{self.body}"
        elif self.kind == FormulaKind.EXISTS:
            return f"∃{self.variable}.{self.body}"
        return "?"

    def free_variables(self) -> PySet[str]:
        """Compute the set of free variables in this formula."""
        if self.kind in (FormulaKind.ATOM, FormulaKind.MEMBERSHIP,
                         FormulaKind.EQUALITY):
            return {t.name for t in self.args if t.is_variable}
        elif self.kind == FormulaKind.NOT:
            return self.left.free_variables()
        elif self.kind in (FormulaKind.AND, FormulaKind.OR,
                           FormulaKind.IMPLIES, FormulaKind.IFF):
            return self.left.free_variables() | self.right.free_variables()
        elif self.kind in (FormulaKind.FORALL, FormulaKind.EXISTS):
            return self.body.free_variables() - {self.variable}
        return set()


# ── Formula constructors ───────────────────────────────────────

def atom(relation: str, *args: Term) -> Formula:
    """R(t1, t2, ...) — a relation holds between terms."""
    return Formula(kind=FormulaKind.ATOM, relation=relation, args=tuple(args))


def member(element: Term, container: Term) -> Formula:
    """t1 ∈ t2 — membership."""
    return Formula(kind=FormulaKind.MEMBERSHIP, args=(element, container))


def equals(t1: Term, t2: Term) -> Formula:
    """t1 = t2 — equality."""
    return Formula(kind=FormulaKind.EQUALITY, args=(t1, t2))


def neg(phi: Formula) -> Formula:
    """¬φ — negation."""
    return Formula(kind=FormulaKind.NOT, left=phi)


def conj(phi: Formula, psi: Formula) -> Formula:
    """φ ∧ ψ — conjunction."""
    return Formula(kind=FormulaKind.AND, left=phi, right=psi)


def disj(phi: Formula, psi: Formula) -> Formula:
    """φ ∨ ψ — disjunction."""
    return Formula(kind=FormulaKind.OR, left=phi, right=psi)


def implies(phi: Formula, psi: Formula) -> Formula:
    """φ → ψ — implication."""
    return Formula(kind=FormulaKind.IMPLIES, left=phi, right=psi)


def iff(phi: Formula, psi: Formula) -> Formula:
    """φ ↔ ψ — biconditional."""
    return Formula(kind=FormulaKind.IFF, left=phi, right=psi)


def forall(variable: str, body: Formula) -> Formula:
    """∀x.φ(x) — universal quantification."""
    return Formula(kind=FormulaKind.FORALL, variable=variable, body=body)


def exists(variable: str, body: Formula) -> Formula:
    """∃x.φ(x) — existential quantification."""
    return Formula(kind=FormulaKind.EXISTS, variable=variable, body=body)


# Convenience: conjoin a list of formulas
def conj_all(formulas: List[Formula]) -> Optional[Formula]:
    """Conjoin a list of formulas: φ1 ∧ φ2 ∧ ... ∧ φn."""
    if not formulas:
        return None
    result = formulas[0]
    for f in formulas[1:]:
        result = conj(result, f)
    return result


# ═══════════════════════════════════════════════════════════════════
# Model — an interpretation of formulas in a universe
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Model:
    """
    A model M = (U, I) where:
    - U is a Universe (the domain)
    - I is an interpretation (maps constants to sets, relations to Relations)

    Mirror of: categorical Functor
    A functor maps one category into another, preserving structure.
    A model maps logical language into a universe, preserving truth.

    But different: a functor preserves composition.
    A model preserves truth. These are NOT the same thing.
    A morphism can exist without being "true." A satisfied formula
    must be true in the model.
    """
    universe: Universe
    constants: Dict[str, str] = field(default_factory=dict)
    # constant_name -> set_name in universe

    def interpret_term(self, term: Term,
                       assignment: Dict[str, str]) -> Optional[str]:
        """
        Interpret a term in the model under a variable assignment.

        Variables are looked up in the assignment.
        Constants are looked up in the interpretation.
        """
        if term.is_variable:
            return assignment.get(term.name)
        else:
            return self.constants.get(term.name, term.name)

    def domain_elements(self) -> PySet[str]:
        """All elements in the domain of discourse."""
        elements: PySet[str] = set()
        for s in self.universe.sets.values():
            elements.add(s.name)
            elements |= s._elements
        return elements


# ═══════════════════════════════════════════════════════════════════
# Satisfaction — M ⊨ φ[σ]
# ═══════════════════════════════════════════════════════════════════

def satisfies(model: Model, formula: Formula,
              assignment: Optional[Dict[str, str]] = None) -> bool:
    """
    Check if a model satisfies a formula under an assignment.

    M ⊨ φ[σ]  means: formula φ is true in model M when variables
    are assigned according to σ.

    Mirror of: SheafCoherenceChecker.check_coherence
    Sheaf coherence asks: "do local sections agree on overlaps?"
    Satisfaction asks: "is this formula true in this model?"

    Both are JUDGMENT functions. One judges compositional consistency.
    The other judges logical truth.
    """
    if assignment is None:
        assignment = {}

    kind = formula.kind

    # ── Atomic formulas ──────────────────────────────────────

    if kind == FormulaKind.ATOM:
        # Look up the relation in the universe
        rel = model.universe.get_relation(formula.relation)
        if rel is None:
            return False
        # Interpret arguments
        interp_args = []
        for t in formula.args:
            val = model.interpret_term(t, assignment)
            if val is None:
                return False
            interp_args.append(val)
        # Check if the tuple is in the relation
        if len(interp_args) == 2:
            return rel.holds(interp_args[0], interp_args[1])
        return False

    if kind == FormulaKind.MEMBERSHIP:
        elem = model.interpret_term(formula.args[0], assignment)
        container = model.interpret_term(formula.args[1], assignment)
        if elem is None or container is None:
            return False
        return model.universe.membership(elem, container)

    if kind == FormulaKind.EQUALITY:
        val1 = model.interpret_term(formula.args[0], assignment)
        val2 = model.interpret_term(formula.args[1], assignment)
        return val1 == val2

    # ── Connectives ──────────────────────────────────────────

    if kind == FormulaKind.NOT:
        return not satisfies(model, formula.left, assignment)

    if kind == FormulaKind.AND:
        return (satisfies(model, formula.left, assignment) and
                satisfies(model, formula.right, assignment))

    if kind == FormulaKind.OR:
        return (satisfies(model, formula.left, assignment) or
                satisfies(model, formula.right, assignment))

    if kind == FormulaKind.IMPLIES:
        return (not satisfies(model, formula.left, assignment) or
                satisfies(model, formula.right, assignment))

    if kind == FormulaKind.IFF:
        l = satisfies(model, formula.left, assignment)
        r = satisfies(model, formula.right, assignment)
        return l == r

    # ── Quantifiers ──────────────────────────────────────────

    if kind == FormulaKind.FORALL:
        # True iff body is true for ALL elements in the domain
        for elem in model.domain_elements():
            new_assignment = {**assignment, formula.variable: elem}
            if not satisfies(model, formula.body, new_assignment):
                return False
        return True

    if kind == FormulaKind.EXISTS:
        # True iff body is true for SOME element in the domain
        for elem in model.domain_elements():
            new_assignment = {**assignment, formula.variable: elem}
            if satisfies(model, formula.body, new_assignment):
                return True
        return False

    raise ValueError(f"Unknown formula kind: {kind}")


def find_witness(model: Model, formula: Formula,
                 assignment: Optional[Dict[str, str]] = None
                 ) -> Optional[Dict[str, str]]:
    """
    Find a satisfying assignment for existential variables.

    Like check_constraints in universe.py but for logical formulas.
    Returns the first assignment that makes the formula true,
    or None if unsatisfiable in this model.
    """
    if assignment is None:
        assignment = {}

    free = formula.free_variables() - set(assignment.keys())

    if not free:
        # All variables bound — just check
        if satisfies(model, formula, assignment):
            return dict(assignment)
        return None

    # Pick a free variable, try all values
    var_name = next(iter(free))
    for elem in model.domain_elements():
        new_assignment = {**assignment, var_name: elem}
        result = find_witness(model, formula, new_assignment)
        if result is not None:
            return result

    return None


# ═══════════════════════════════════════════════════════════════════
# Theory — a set of axioms
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Theory:
    """
    A theory Γ = {φ1, φ2, ..., φn} — a set of formulas assumed true.

    Mirror of: Category (a category IS a theory of composition)
    A category's axioms are: associativity, identity.
    A theory's axioms are: whatever you assert.

    The power of ZFC: axioms are EXPLICIT and CHECKABLE.
    The power of categories: axioms are STRUCTURAL and COMPOSITIONAL.
    """
    name: str
    axioms: List[Formula] = field(default_factory=list)

    def add_axiom(self, formula: Formula):
        """Add an axiom to the theory."""
        self.axioms.append(formula)

    def is_consistent_in(self, model: Model) -> bool:
        """
        Check if all axioms are satisfied in a model.

        Γ is consistent in M iff M ⊨ φ for every φ ∈ Γ.
        """
        return all(satisfies(model, ax) for ax in self.axioms)

    def entails(self, conclusion: Formula, model: Model) -> bool:
        """
        Check if the theory entails a conclusion in a model.

        Γ ⊨_M φ iff: if M satisfies all of Γ, then M satisfies φ.

        This is model-specific entailment. For logical entailment
        (true in ALL models), you'd need to check all possible models.

        Mirror of: KanExtensionOracle.predict
        Kan extension: "given known values, predict unknown."
        Entailment: "given assumed truths, deduce conclusion."
        """
        if not self.is_consistent_in(model):
            # Inconsistent theory entails everything (ex falso)
            return True
        return satisfies(model, conclusion)

    def find_consequences(self, candidates: List[Formula],
                          model: Model) -> List[Tuple[Formula, bool]]:
        """
        Check which candidate formulas are entailed by the theory.

        Returns list of (formula, is_entailed) pairs.

        Mirror of: ConjectureEngine
        Conjecture: "which missing edges should exist?"
        Consequences: "which candidate claims follow from the axioms?"
        """
        if not self.is_consistent_in(model):
            # Everything follows from inconsistency
            return [(f, True) for f in candidates]

        results = []
        for f in candidates:
            entailed = satisfies(model, f)
            results.append((f, entailed))
        return results

    def __repr__(self):
        return f"Theory({self.name}, |axioms|={len(self.axioms)})"


# ═══════════════════════════════════════════════════════════════════
# LogicOracle — the prediction interface
# ═══════════════════════════════════════════════════════════════════

class LogicOracle:
    """
    High-level oracle that uses logical reasoning for prediction.

    Mirror of: KanExtensionOracle
    KanExtensionOracle: known_category + full_category → predict via colimit
    LogicOracle:        theory + model → predict via entailment

    Both answer: "what should be true about this unknown?"
    One uses universal properties. The other uses logical consequence.
    """

    def __init__(self, theory: Theory, model: Model):
        self.theory = theory
        self.model = model

    def predict(self, claim: Formula) -> Tuple[bool, float, Optional[Dict[str, str]]]:
        """
        Predict whether a claim follows from the theory.

        Returns:
            (is_entailed, confidence, witness_or_None)

        Confidence scoring:
        - 1.0: entailed (every model of Γ satisfies φ, checked in this model)
        - 0.0: refuted (this model satisfies Γ but not φ)
        - 0.5: underdetermined (theory is inconsistent in this model)

        Mirror of: KanExtensionOracle.predict
        But different: Kan returns a VALUE (the colimit).
        Logic returns a JUDGMENT (true/false/unknown).
        """
        if not self.theory.is_consistent_in(self.model):
            return (True, 0.5, None)  # ex falso, low confidence

        is_true = satisfies(self.model, claim)

        if is_true:
            # Find a witness for existential claims
            witness = find_witness(self.model, claim)
            return (True, 1.0, witness)
        else:
            return (False, 0.0, None)

    def predict_relation(self, rel_name: str, source: str,
                         target: str) -> Tuple[bool, float, Optional[Dict[str, str]]]:
        """
        Predict whether a relation holds between two elements.

        Convenience method for the common case.
        """
        claim = atom(rel_name, const(source), const(target))
        return self.predict(claim)

    def find_all_entailed(self, relation_name: str,
                          source: str) -> List[Tuple[str, float]]:
        """
        Find all targets such that relation(source, target) is entailed.

        Mirror of: LeftKanExtension.extend (predict all values for an object)
        """
        rel = self.model.universe.get_relation(relation_name)
        if rel is None:
            return []

        results = []
        targets = rel.image(source)
        for t in targets:
            claim = atom(relation_name, const(source), const(t))
            entailed, conf, _ = self.predict(claim)
            if entailed:
                results.append((t, conf))

        return sorted(results, key=lambda x: -x[1])

    def check_consistency(self) -> Tuple[bool, List[Formula]]:
        """
        Check if the theory is consistent in the current model.

        Returns (is_consistent, list_of_violated_axioms).
        """
        violated = []
        for ax in self.theory.axioms:
            if not satisfies(self.model, ax):
                violated.append(ax)
        return (len(violated) == 0, violated)

    def compare_with_prediction(
        self,
        cat_prediction: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compare a categorical prediction with logical entailment.

        This is the DELTA — the core of the KOMPOSOS bridge.

        Takes a prediction from KOMPOSOS-CAT and checks it against
        the logical theory. Returns a comparison report.

        Args:
            cat_prediction: must have 'source', 'target', 'relation', 'confidence'

        Returns:
            {
                'cat_says': True/False,
                'zfc_says': True/False,
                'agreement': True/False,
                'cat_confidence': float,
                'zfc_confidence': float,
                'delta_type': str,  # 'agree', 'cat_only', 'zfc_only', 'conflict'
                'witness': optional assignment
            }
        """
        source = cat_prediction.get("source", "")
        target = cat_prediction.get("target", "")
        rel = cat_prediction.get("relation", "")
        cat_conf = cat_prediction.get("confidence", 0.0)
        cat_says = cat_conf >= 0.4  # CAT's threshold

        zfc_says, zfc_conf, witness = self.predict_relation(rel, source, target)

        if cat_says and zfc_says:
            delta_type = "agree"
        elif cat_says and not zfc_says:
            delta_type = "cat_only"  # compositional but not constructible
        elif not cat_says and zfc_says:
            delta_type = "zfc_only"  # constructible but doesn't compose
        else:
            delta_type = "neither"

        return {
            "cat_says": cat_says,
            "zfc_says": zfc_says,
            "agreement": cat_says == zfc_says,
            "cat_confidence": cat_conf,
            "zfc_confidence": zfc_conf,
            "delta_type": delta_type,
            "witness": witness,
        }


# ═══════════════════════════════════════════════════════════════════
# Example usage and tests
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from .universe import zfset, relation as mk_relation

    # Build a universe
    V = Universe("PharmUniverse")

    # Sets
    drugs = V.add_set(zfset("Drugs"))
    proteins = V.add_set(zfset("Proteins"))
    diseases = V.add_set(zfset("Diseases"))

    aspirin = V.add_set(zfset("Aspirin"))
    ibuprofen = V.add_set(zfset("Ibuprofen"))
    celecoxib = V.add_set(zfset("Celecoxib"))
    cox1 = V.add_set(zfset("COX1"))
    cox2 = V.add_set(zfset("COX2"))
    inflammation = V.add_set(zfset("Inflammation"))
    pain = V.add_set(zfset("Pain"))

    V.add_element(aspirin, drugs)
    V.add_element(ibuprofen, drugs)
    V.add_element(celecoxib, drugs)
    V.add_element(cox1, proteins)
    V.add_element(cox2, proteins)
    V.add_element(inflammation, diseases)
    V.add_element(pain, diseases)

    # Relations
    inhibits = mk_relation("inhibits", [
        ("Aspirin", "COX1"), ("Aspirin", "COX2"),
        ("Ibuprofen", "COX1"), ("Ibuprofen", "COX2"),
        ("Celecoxib", "COX2"),  # selective COX-2 inhibitor
    ])
    V.add_relation(inhibits)

    associated = mk_relation("associated_with", [
        ("COX1", "Pain"), ("COX2", "Inflammation"),
        ("COX2", "Pain"),
    ])
    V.add_relation(associated)

    treats = mk_relation("treats", [
        ("Aspirin", "Inflammation"),
        ("Ibuprofen", "Pain"),
    ])
    V.add_relation(treats)

    # Create model
    M = Model(universe=V)

    # Build a theory: "if drug inhibits protein and protein is
    # associated with disease, then drug treats disease"
    x, y, z = var("x"), var("y"), var("z")
    transitivity_axiom = forall("x", forall("y", forall("z",
        implies(
            conj(
                atom("inhibits", var("x"), var("y")),
                atom("associated_with", var("y"), var("z"))
            ),
            atom("treats", var("x"), var("z"))
        )
    )))

    T = Theory("DrugRepurposing")
    T.add_axiom(transitivity_axiom)

    print(f"Theory: {T}")
    print(f"Axiom: {transitivity_axiom}")
    print()

    # Create oracle
    oracle = LogicOracle(T, M)

    # Check: does Celecoxib treat Inflammation?
    claim = atom("treats", const("Celecoxib"), const("Inflammation"))
    entailed, conf, witness = oracle.predict(claim)
    print(f"Celecoxib treats Inflammation? {entailed} (conf={conf})")

    # Check: does Celecoxib treat Pain?
    claim2 = atom("treats", const("Celecoxib"), const("Pain"))
    entailed2, conf2, witness2 = oracle.predict(claim2)
    print(f"Celecoxib treats Pain? {entailed2} (conf={conf2})")

    # Compare with a categorical prediction
    cat_pred = {
        "source": "Celecoxib",
        "target": "Inflammation",
        "relation": "treats",
        "confidence": 0.75,
    }
    delta = oracle.compare_with_prediction(cat_pred)
    print(f"\nDelta analysis: {delta}")

    # Check theory consistency
    consistent, violated = oracle.check_consistency()
    print(f"\nTheory consistent: {consistent}")
    if violated:
        print(f"Violated axioms: {violated}")
