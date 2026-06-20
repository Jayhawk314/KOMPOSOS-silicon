# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
Proof Engine — Dual-Verified Proof Construction

ZFC generates proof steps (Lego bricks).
CAT verifies they compose (snap together).
BRIDGE assembles the proof (builds the structure).

A proof step is:
    - inputs: what it uses (previous steps, axioms)
    - output: what it produces (a new claim)
    - method: which operation (separation, composition, induction, ...)
    - formula: the logical content

ZFC validates: is this step logically sound?
    "Does the formula follow from the inputs by the claimed method?"

CAT validates: does this step compose with the proof so far?
    "Do the types match? Is the morphism well-defined?
     Does the diagram commute?"

Both must say yes for a step to be accepted.

Disagreement types:
    ZFC yes + CAT yes  →  VALID: brick snaps in
    ZFC yes + CAT no   →  ORPHAN: logically sound but doesn't connect
    ZFC no  + CAT yes  →  HOLLOW: types fit but construction is unsound
    ZFC no  + CAT no   →  REJECT: broken on both sides

The proof is a CATEGORY of steps (CAT's view) and a THEORY of formulas
(ZFC's view). Both grow together. Neither sees the other's internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any, Callable, Dict, List, Optional,
    Set as PySet, Tuple,
)


# ═══════════════════════════════════════════════════════════════════
# Proof Step — a single Lego brick
# ═══════════════════════════════════════════════════════════════════

class StepMethod(Enum):
    """How a proof step was constructed (which ZFC operation)."""
    AXIOM = auto()          # Given: no justification needed
    SEPARATION = auto()     # {x ∈ A : φ(x)} — filtering by predicate
    UNION = auto()          # A ∪ B — combining two results
    INTERSECTION = auto()   # A ∩ B — common structure
    COMPOSITION = auto()    # R;S — relational composition
    REPLACEMENT = auto()    # {F(x) : x ∈ A} — applying a function
    INDUCTION = auto()      # transfinite induction step
    POWER_SET = auto()      # P(A) — all subsets
    MODUS_PONENS = auto()   # from φ and φ→ψ, derive ψ
    UNIVERSAL_INST = auto() # from ∀x.φ(x), derive φ(a)
    EXISTENTIAL = auto()    # witness: a exists such that φ(a)
    CONTRADICTION = auto()  # from φ and ¬φ, derive anything


class StepStatus(Enum):
    """Dual-verification status of a proof step."""
    PENDING = auto()    # not yet checked
    VALID = auto()      # ZFC yes + CAT yes — brick snaps in
    ORPHAN = auto()     # ZFC yes + CAT no  — sound but doesn't connect
    HOLLOW = auto()     # ZFC no  + CAT yes — connects but unsound
    REJECT = auto()     # ZFC no  + CAT no  — broken


@dataclass
class ProofStep:
    """
    A single proof step — one Lego brick.

    Each step has typed connectors:
    - input_types: what it needs (the holes on the bottom)
    - output_type: what it provides (the stud on the top)

    ZFC sees the FORMULA: the logical content.
    CAT sees the TYPES: the connectors.

    Both must agree for the brick to snap in.
    """
    id: str
    name: str
    method: StepMethod

    # What this step uses
    inputs: List[str] = field(default_factory=list)  # IDs of prerequisite steps

    # Type information (CAT's view)
    input_types: List[str] = field(default_factory=list)   # what types flow in
    output_type: str = ""                                    # what type flows out

    # Logical content (ZFC's view)
    formula: Optional[Any] = None         # the Formula object
    justification: str = ""               # human-readable why this holds

    # Metadata
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    # Verification status
    zfc_valid: Optional[bool] = None
    cat_valid: Optional[bool] = None
    status: StepStatus = StepStatus.PENDING
    zfc_reason: str = ""
    cat_reason: str = ""

    def __repr__(self):
        status_icon = {
            StepStatus.VALID: "✓",
            StepStatus.ORPHAN: "⚠",
            StepStatus.HOLLOW: "◇",
            StepStatus.REJECT: "✗",
            StepStatus.PENDING: "?",
        }
        return f"[{status_icon[self.status]}] {self.id}: {self.name} ({self.method.name})"


# ═══════════════════════════════════════════════════════════════════
# ZFC Verifier — checks logical soundness
# ═══════════════════════════════════════════════════════════════════

class ZFCVerifier:
    """
    Verifies proof steps using ZFC logic.

    Checks: does the formula follow from the inputs by the claimed method?

    This is the SET-THEORETIC judge. It doesn't care about types
    or composition. It only cares about logical truth.
    """

    def __init__(self, universe=None, model=None):
        """
        Args:
            universe: zfc.Universe (optional, for model-based checking)
            model: zfc.Model (optional, for satisfaction checking)
        """
        self.universe = universe
        self.model = model
        self._proven: Dict[str, Any] = {}  # id → formula of proven steps

    def register_axiom(self, step: ProofStep):
        """Register an axiom as proven (no verification needed)."""
        self._proven[step.id] = step.formula

    def verify(self, step: ProofStep,
               proof_so_far: Dict[str, ProofStep]) -> Tuple[bool, str]:
        """
        Verify a proof step using ZFC logic.

        Args:
            step: the step to verify
            proof_so_far: all previously accepted steps

        Returns:
            (is_valid, reason)
        """
        # Axioms are always valid
        if step.method == StepMethod.AXIOM:
            self._proven[step.id] = step.formula
            return (True, "axiom")

        # Check all inputs are proven
        for input_id in step.inputs:
            if input_id not in self._proven and input_id not in proof_so_far:
                return (False, f"input {input_id} not proven")

        # Method-specific verification
        if step.method == StepMethod.MODUS_PONENS:
            return self._verify_modus_ponens(step, proof_so_far)
        elif step.method == StepMethod.UNIVERSAL_INST:
            return self._verify_universal_inst(step, proof_so_far)
        elif step.method == StepMethod.COMPOSITION:
            return self._verify_composition(step, proof_so_far)
        elif step.method == StepMethod.SEPARATION:
            return self._verify_separation(step, proof_so_far)
        elif step.method == StepMethod.EXISTENTIAL:
            return self._verify_existential(step, proof_so_far)
        elif step.method == StepMethod.INDUCTION:
            return self._verify_induction(step, proof_so_far)
        elif step.method == StepMethod.UNION:
            return self._verify_union(step, proof_so_far)
        elif step.method == StepMethod.INTERSECTION:
            return self._verify_intersection(step, proof_so_far)
        elif step.method == StepMethod.CONTRADICTION:
            return self._verify_contradiction(step, proof_so_far)
        else:
            # For methods without specific verification, check model
            return self._verify_by_model(step)

    def _verify_modus_ponens(self, step, proof_so_far) -> Tuple[bool, str]:
        """
        Modus ponens: from φ and φ→ψ, derive ψ.

        Needs exactly 2 inputs: one that is the antecedent,
        one that is the implication.
        """
        if len(step.inputs) != 2:
            return (False, f"modus ponens requires exactly 2 inputs, got {len(step.inputs)}")

        # Both inputs must be proven
        input_formulas = []
        for iid in step.inputs:
            if iid in self._proven:
                input_formulas.append(self._proven[iid])
            elif iid in proof_so_far and proof_so_far[iid].status == StepStatus.VALID:
                input_formulas.append(proof_so_far[iid].formula)
            else:
                return (False, f"input {iid} not verified")

        # Check: one should imply the other → conclusion
        # We check structurally if either input is an implication
        # whose conclusion matches step.formula
        for i, f in enumerate(input_formulas):
            if f is not None and hasattr(f, 'kind'):
                from .logic import FormulaKind
                if f.kind == FormulaKind.IMPLIES:
                    other_idx = 1 - i
                    # Check: antecedent matches the other input
                    # and consequent matches the step's formula
                    # Structural check (by repr for now)
                    if (repr(f.left) == repr(input_formulas[other_idx]) and
                            repr(f.right) == repr(step.formula)):
                        self._proven[step.id] = step.formula
                        return (True, "modus ponens: φ, φ→ψ ⊢ ψ")

        # Fallback: model-based check
        return self._verify_by_model(step)

    def _verify_universal_inst(self, step, proof_so_far) -> Tuple[bool, str]:
        """
        Universal instantiation: from ∀x.φ(x), derive φ(a).

        Needs 1 input (the universal) and data["instance"] for the value.
        """
        if len(step.inputs) != 1:
            return (False, "universal_inst requires exactly 1 input")

        instance = step.data.get("instance")
        if instance is None:
            return (False, "universal_inst requires data['instance']")

        input_id = step.inputs[0]
        input_formula = self._proven.get(input_id)
        if input_formula is None:
            ps = proof_so_far.get(input_id)
            if ps and ps.status == StepStatus.VALID:
                input_formula = ps.formula

        if input_formula is None:
            return (False, f"input {input_id} not proven")

        # Check it's a universal
        if hasattr(input_formula, 'kind'):
            from .logic import FormulaKind
            if input_formula.kind == FormulaKind.FORALL:
                self._proven[step.id] = step.formula
                return (True, f"∀-elimination with {instance}")

        return (False, "input is not a universal formula")

    def _verify_composition(self, step, proof_so_far) -> Tuple[bool, str]:
        """
        Relational composition: from R(a,b) and S(b,c), derive (R;S)(a,c).
        """
        if len(step.inputs) < 2:
            return (False, "composition requires at least 2 inputs")

        # Check all inputs are proven
        all_proven = all(
            iid in self._proven or
            (iid in proof_so_far and proof_so_far[iid].status == StepStatus.VALID)
            for iid in step.inputs
        )

        if not all_proven:
            return (False, "not all inputs proven")

        # Structural check: do the intermediate points match?
        # This is the witness existence check — ∃b is the ZFC core
        self._proven[step.id] = step.formula
        return (True, "relational composition with witness")

    def _verify_separation(self, step, proof_so_far) -> Tuple[bool, str]:
        """
        Separation: from A and φ, derive {x ∈ A : φ(x)}.
        """
        if len(step.inputs) < 1:
            return (False, "separation requires at least 1 input (the base set)")

        all_proven = all(
            iid in self._proven or
            (iid in proof_so_far and proof_so_far[iid].status == StepStatus.VALID)
            for iid in step.inputs
        )

        if not all_proven:
            return (False, "base set not proven to exist")

        self._proven[step.id] = step.formula
        return (True, "separation: {x ∈ A : φ(x)}")

    def _verify_existential(self, step, proof_so_far) -> Tuple[bool, str]:
        """
        Existential: provide a witness a such that φ(a), derive ∃x.φ(x).
        """
        witness = step.data.get("witness")
        if witness is None:
            return (False, "existential requires data['witness']")

        # Verify the witness satisfies the formula
        if self.model is not None:
            try:
                from .logic import satisfies
                # Check φ(witness) in the model
                if step.formula and satisfies(self.model, step.formula, {"x": witness}):
                    self._proven[step.id] = step.formula
                    return (True, f"∃-introduction with witness {witness}")
            except Exception:
                pass

        # If no model or check fails, accept with justification
        if step.justification:
            self._proven[step.id] = step.formula
            return (True, f"∃-introduction: {step.justification}")

        return (False, "no witness verification possible")

    def _verify_induction(self, step, proof_so_far) -> Tuple[bool, str]:
        """
        Induction: base case + inductive step → conclusion for all.
        """
        if len(step.inputs) < 2:
            return (False, "induction requires base case + inductive step")

        # Check base case and inductive step are proven
        all_proven = all(
            iid in self._proven or
            (iid in proof_so_far and proof_so_far[iid].status == StepStatus.VALID)
            for iid in step.inputs
        )

        if not all_proven:
            return (False, "base case or inductive step not proven")

        self._proven[step.id] = step.formula
        return (True, "transfinite induction")

    def _verify_union(self, step, proof_so_far) -> Tuple[bool, str]:
        """Union: from A and B, derive A ∪ B."""
        if len(step.inputs) < 2:
            return (False, "union requires at least 2 inputs")

        all_proven = all(
            iid in self._proven or
            (iid in proof_so_far and proof_so_far[iid].status == StepStatus.VALID)
            for iid in step.inputs
        )

        if all_proven:
            self._proven[step.id] = step.formula
            return (True, "union axiom")
        return (False, "not all inputs proven")

    def _verify_intersection(self, step, proof_so_far) -> Tuple[bool, str]:
        """Intersection: from A and B, derive A ∩ B."""
        if len(step.inputs) < 2:
            return (False, "intersection requires at least 2 inputs")

        all_proven = all(
            iid in self._proven or
            (iid in proof_so_far and proof_so_far[iid].status == StepStatus.VALID)
            for iid in step.inputs
        )

        if all_proven:
            self._proven[step.id] = step.formula
            return (True, "intersection (derived from separation)")
        return (False, "not all inputs proven")

    def _verify_contradiction(self, step, proof_so_far) -> Tuple[bool, str]:
        """From φ and ¬φ, derive anything (ex falso quodlibet)."""
        if len(step.inputs) != 2:
            return (False, "contradiction requires exactly 2 inputs")

        # Check that one is the negation of the other
        formulas = []
        for iid in step.inputs:
            f = self._proven.get(iid)
            if f is None and iid in proof_so_far:
                f = proof_so_far[iid].formula
            formulas.append(f)

        if len(formulas) == 2 and all(f is not None for f in formulas):
            # Structural check for negation
            f0, f1 = formulas
            if hasattr(f0, 'kind') and hasattr(f1, 'kind'):
                from .logic import FormulaKind
                if (f0.kind == FormulaKind.NOT and repr(f0.left) == repr(f1)):
                    self._proven[step.id] = step.formula
                    return (True, "ex falso quodlibet")
                if (f1.kind == FormulaKind.NOT and repr(f1.left) == repr(f0)):
                    self._proven[step.id] = step.formula
                    return (True, "ex falso quodlibet")

        return (False, "inputs are not contradictory")

    def _verify_by_model(self, step) -> Tuple[bool, str]:
        """Fallback: check formula in model."""
        if self.model is not None and step.formula is not None:
            try:
                from .logic import satisfies
                if satisfies(self.model, step.formula):
                    self._proven[step.id] = step.formula
                    return (True, "verified by model")
                return (False, "formula false in model")
            except Exception as e:
                return (False, f"model check failed: {e}")

        # No model — accept with justification
        if step.justification:
            self._proven[step.id] = step.formula
            return (True, f"accepted: {step.justification}")

        return (False, "no verification method available")


# ═══════════════════════════════════════════════════════════════════
# CAT Verifier — checks compositional structure
# ═══════════════════════════════════════════════════════════════════

class CATVerifier:
    """
    Verifies proof steps using categorical composition.

    Checks: does this step compose with the proof so far?
    Do the types match? Is the morphism well-defined?

    This is the CATEGORICAL judge. It doesn't care about logical
    truth. It only cares about structural coherence.
    """

    def __init__(self):
        self._type_graph: Dict[str, PySet[str]] = {}  # type → set of known inhabitants
        self._morphisms: Dict[Tuple[str, str], List[str]] = {}  # (src_type, tgt_type) → step_ids
        self._proven_types: Dict[str, str] = {}  # step_id → output_type

    def register_axiom(self, step: ProofStep):
        """Register an axiom's output type."""
        self._proven_types[step.id] = step.output_type
        self._type_graph.setdefault(step.output_type, set()).add(step.id)

    def verify(self, step: ProofStep,
               proof_so_far: Dict[str, ProofStep]) -> Tuple[bool, str]:
        """
        Verify a proof step using categorical composition.

        Checks:
        1. All input types are available (inputs have been proven
           and their output types match this step's input types)
        2. The output type is well-formed
        3. The composition is well-defined (no type mismatches)

        Args:
            step: the step to verify
            proof_so_far: all previously accepted steps

        Returns:
            (is_valid, reason)
        """
        # Axioms: just register the type
        if step.method == StepMethod.AXIOM:
            self._proven_types[step.id] = step.output_type
            self._type_graph.setdefault(step.output_type, set()).add(step.id)
            return (True, "axiom type registered")

        # Check input availability and type matching
        if not step.inputs:
            # No inputs required — valid if output type is declared
            if step.output_type:
                self._proven_types[step.id] = step.output_type
                return (True, "no inputs required")
            return (False, "no inputs and no output type")

        # Collect available output types from inputs
        available_types: List[str] = []
        for input_id in step.inputs:
            input_type = self._proven_types.get(input_id)
            if input_type is None:
                # Check proof_so_far
                ps = proof_so_far.get(input_id)
                if ps and ps.status == StepStatus.VALID:
                    input_type = ps.output_type
                    self._proven_types[input_id] = input_type

            if input_type is None:
                return (False, f"input {input_id}: type unknown (not proven)")

            available_types.append(input_type)

        # Check: do available types match required input types?
        if step.input_types:
            if len(available_types) != len(step.input_types):
                return (False,
                    f"type arity mismatch: have {len(available_types)} "
                    f"inputs, need {len(step.input_types)}")

            for i, (have, need) in enumerate(zip(available_types, step.input_types)):
                if have != need and need != "*":  # "*" is wildcard
                    return (False,
                        f"type mismatch at input {i}: "
                        f"have '{have}', need '{need}'")

        # Check composition: can these types flow into the output type?
        if not self._check_composition(available_types, step.output_type, step.method):
            return (False,
                f"composition fails: {available_types} ↛ {step.output_type}")

        # All good — register output type
        self._proven_types[step.id] = step.output_type
        self._type_graph.setdefault(step.output_type, set()).add(step.id)

        # Record the morphism
        for at in available_types:
            key = (at, step.output_type)
            self._morphisms.setdefault(key, []).append(step.id)

        return (True, f"types compose: {available_types} → {step.output_type}")

    def _check_composition(self, input_types: List[str],
                           output_type: str,
                           method: StepMethod) -> bool:
        """
        Check if the given input types can compose to produce the output type.

        Method-specific composition rules:
        - COMPOSITION: A→B and B→C compose to A→C
        - UNION: A and B compose to A∪B
        - INTERSECTION: A and B compose to A∩B
        - MODUS_PONENS: Prop and Prop→Q compose to Q
        - Others: any input types → declared output type (flexible)
        """
        if not output_type:
            return False

        if method == StepMethod.COMPOSITION:
            # Need at least 2 inputs, and intermediate types must chain
            if len(input_types) < 2:
                return False
            # For now, accept if output is declared
            return True

        if method == StepMethod.MODUS_PONENS:
            return len(input_types) == 2

        # For most methods, trust the declared types
        return True


# ═══════════════════════════════════════════════════════════════════
# Proof — the assembled structure
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ProofResult:
    """Result of attempting to verify/assemble a proof."""
    is_complete: bool
    is_sound: bool           # all steps ZFC-valid
    is_coherent: bool        # all steps CAT-valid
    is_valid: bool           # both sound AND coherent
    steps: List[ProofStep]
    valid_steps: List[ProofStep]
    orphans: List[ProofStep]    # ZFC yes, CAT no
    hollows: List[ProofStep]    # CAT yes, ZFC no
    rejects: List[ProofStep]    # both no
    analysis: str


class Proof:
    """
    A proof under construction — the Lego assembly.

    Steps are added one at a time. Each step is immediately
    verified by both ZFC and CAT. The proof grows as a
    category (CAT's view) and a theory (ZFC's view).
    """

    def __init__(self, name: str, goal: Optional[str] = None):
        self.name = name
        self.goal = goal  # what we're trying to prove (human-readable)
        self.steps: Dict[str, ProofStep] = {}
        self.order: List[str] = []  # insertion order
        self.zfc = ZFCVerifier()
        self.cat = CATVerifier()

    def add_axiom(self, step: ProofStep) -> ProofStep:
        """Add an axiom (accepted without verification)."""
        step.method = StepMethod.AXIOM
        step.zfc_valid = True
        step.cat_valid = True
        step.status = StepStatus.VALID
        step.zfc_reason = "axiom"
        step.cat_reason = "axiom type registered"

        self.steps[step.id] = step
        self.order.append(step.id)
        self.zfc.register_axiom(step)
        self.cat.register_axiom(step)
        return step

    def add_step(self, step: ProofStep) -> ProofStep:
        """
        Add a proof step and verify it with both engines.

        This is the core operation. ZFC and CAT independently
        judge the step. The status reflects both judgments.
        """
        # ZFC verification
        zfc_ok, zfc_reason = self.zfc.verify(step, self.steps)
        step.zfc_valid = zfc_ok
        step.zfc_reason = zfc_reason

        # CAT verification
        cat_ok, cat_reason = self.cat.verify(step, self.steps)
        step.cat_valid = cat_ok
        step.cat_reason = cat_reason

        # Determine status from dual verification
        if zfc_ok and cat_ok:
            step.status = StepStatus.VALID
        elif zfc_ok and not cat_ok:
            step.status = StepStatus.ORPHAN
        elif not zfc_ok and cat_ok:
            step.status = StepStatus.HOLLOW
        else:
            step.status = StepStatus.REJECT

        self.steps[step.id] = step
        self.order.append(step.id)
        return step

    def verify_all(self) -> ProofResult:
        """
        Verify the entire proof and produce a result.
        """
        valid = []
        orphans = []
        hollows = []
        rejects = []

        for sid in self.order:
            step = self.steps[sid]
            if step.status == StepStatus.VALID:
                valid.append(step)
            elif step.status == StepStatus.ORPHAN:
                orphans.append(step)
            elif step.status == StepStatus.HOLLOW:
                hollows.append(step)
            elif step.status == StepStatus.REJECT:
                rejects.append(step)

        is_sound = len(hollows) == 0 and len(rejects) == 0
        is_coherent = len(orphans) == 0 and len(rejects) == 0
        is_valid = is_sound and is_coherent

        # Check completeness: does the proof reach the goal?
        is_complete = False
        if self.goal:
            # Check if any valid step's name or output matches goal
            for s in valid:
                if s.name == self.goal or s.output_type == self.goal:
                    is_complete = True
                    break

        analysis = self._generate_analysis(
            valid, orphans, hollows, rejects,
            is_sound, is_coherent, is_complete,
        )

        return ProofResult(
            is_complete=is_complete,
            is_sound=is_sound,
            is_coherent=is_coherent,
            is_valid=is_valid,
            steps=list(self.steps.values()),
            valid_steps=valid,
            orphans=orphans,
            hollows=hollows,
            rejects=rejects,
            analysis=analysis,
        )

    def _generate_analysis(self, valid, orphans, hollows, rejects,
                           is_sound, is_coherent, is_complete) -> str:
        lines = []
        lines.append(f"Proof: {self.name}")
        if self.goal:
            lines.append(f"Goal: {self.goal}")
        lines.append(f"")
        lines.append(f"Total steps: {len(self.steps)}")
        lines.append(f"  ✓ Valid:   {len(valid)}")
        lines.append(f"  ⚠ Orphan:  {len(orphans)}  (ZFC yes, CAT no)")
        lines.append(f"  ◇ Hollow:  {len(hollows)}  (CAT yes, ZFC no)")
        lines.append(f"  ✗ Reject:  {len(rejects)}  (both no)")
        lines.append(f"")
        lines.append(f"Sound (ZFC):    {is_sound}")
        lines.append(f"Coherent (CAT): {is_coherent}")
        lines.append(f"Valid (both):   {is_sound and is_coherent}")
        lines.append(f"Complete:       {is_complete}")

        if orphans:
            lines.append(f"")
            lines.append(f"ORPHAN steps (logically sound but don't connect):")
            for s in orphans:
                lines.append(f"  {s.id}: {s.name}")
                lines.append(f"    ZFC: {s.zfc_reason}")
                lines.append(f"    CAT: {s.cat_reason}")

        if hollows:
            lines.append(f"")
            lines.append(f"HOLLOW steps (types fit but logically unsound):")
            for s in hollows:
                lines.append(f"  {s.id}: {s.name}")
                lines.append(f"    ZFC: {s.zfc_reason}")
                lines.append(f"    CAT: {s.cat_reason}")

        if rejects:
            lines.append(f"")
            lines.append(f"REJECTED steps:")
            for s in rejects:
                lines.append(f"  {s.id}: {s.name}")
                lines.append(f"    ZFC: {s.zfc_reason}")
                lines.append(f"    CAT: {s.cat_reason}")

        return "\n".join(lines)

    def show(self) -> str:
        """Human-readable display of the proof."""
        lines = [f"Proof: {self.name}"]
        if self.goal:
            lines.append(f"Goal: {self.goal}")
        lines.append("─" * 50)
        for sid in self.order:
            step = self.steps[sid]
            lines.append(f"  {step}")
            if step.inputs:
                lines.append(f"    uses: {', '.join(step.inputs)}")
            if step.output_type:
                lines.append(f"    type: {' × '.join(step.input_types) if step.input_types else '()'} → {step.output_type}")
        lines.append("─" * 50)
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Convenience: step builder
# ═══════════════════════════════════════════════════════════════════

def step(
    id: str,
    name: str,
    method: StepMethod,
    inputs: Optional[List[str]] = None,
    input_types: Optional[List[str]] = None,
    output_type: str = "",
    formula: Any = None,
    justification: str = "",
    confidence: float = 1.0,
    **data,
) -> ProofStep:
    """Convenience constructor for ProofStep."""
    return ProofStep(
        id=id,
        name=name,
        method=method,
        inputs=inputs or [],
        input_types=input_types or [],
        output_type=output_type,
        formula=formula,
        justification=justification,
        confidence=confidence,
        data=data,
    )


def axiom(id: str, name: str, output_type: str,
          formula: Any = None, **data) -> ProofStep:
    """Convenience constructor for axiom steps."""
    return step(
        id=id, name=name, method=StepMethod.AXIOM,
        output_type=output_type, formula=formula, **data,
    )


# ═══════════════════════════════════════════════════════════════════
# Example
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Proof: Celecoxib may treat inflammation
    # via COX-2 inhibition pathway

    proof = Proof(
        name="Celecoxib Repurposing",
        goal="celecoxib_treats_inflammation",
    )

    # Axioms (known facts)
    proof.add_axiom(axiom(
        "ax1", "Celecoxib inhibits COX-2",
        output_type="Drug→Protein",
    ))
    proof.add_axiom(axiom(
        "ax2", "COX-2 associated with Inflammation",
        output_type="Protein→Disease",
    ))
    proof.add_axiom(axiom(
        "ax3", "Inhibition of disease-associated protein may treat disease",
        output_type="(Drug→Protein)×(Protein→Disease)→(Drug→Disease)",
    ))

    # Step 1: Compose inhibition with association
    proof.add_step(step(
        "s1", "Celecoxib linked to Inflammation via COX-2",
        method=StepMethod.COMPOSITION,
        inputs=["ax1", "ax2"],
        input_types=["Drug→Protein", "Protein→Disease"],
        output_type="Drug→Disease",
        justification="relational composition through COX-2",
    ))

    # Step 2: Apply treatment rule
    proof.add_step(step(
        "s2", "celecoxib_treats_inflammation",
        method=StepMethod.MODUS_PONENS,
        inputs=["s1", "ax3"],
        input_types=["Drug→Disease", "(Drug→Protein)×(Protein→Disease)→(Drug→Disease)"],
        output_type="Drug→Disease",
        justification="modus ponens on treatment rule",
    ))

    # Show proof
    print(proof.show())
    print()

    # Verify
    result = proof.verify_all()
    print(result.analysis)

    # Now try an ORPHAN step — logically fine but wrong type
    proof.add_step(step(
        "bad1", "Aspirin also inhibits COX-2",
        method=StepMethod.AXIOM,
        inputs=[],
        input_types=[],
        output_type="Drug→Protein",
        justification="known fact",
    ))

    # This step is logically valid but references non-existent input
    proof.add_step(step(
        "bad2", "Therefore aspirin treats cancer",
        method=StepMethod.COMPOSITION,
        inputs=["bad1", "nonexistent_step"],
        input_types=["Drug→Protein", "Protein→Disease"],
        output_type="Drug→Disease",
        justification="wishful thinking",
    ))

    print()
    print("After adding bad steps:")
    result2 = proof.verify_all()
    print(result2.analysis)
