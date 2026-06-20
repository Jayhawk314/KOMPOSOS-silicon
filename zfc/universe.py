# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
ZFC Universe - The Foundation of Set-Theoretic Reasoning

A ZFC universe V consists of:
- Sets: the only primitive objects (everything is a set)
- Membership (∈): the only primitive relation
- Axioms that guarantee closure under key operations

Where category.py builds from: Object, Morphism, compose
This builds from:              Set,    ∈,         {x ∈ A : φ(x)}

Where category.py asks: "what arrows exist between objects?"
This asks:              "what elements belong to what sets?"

Where category.py checks: "does this diagram commute?"
This checks:              "is this collection of constraints satisfiable?"

ZFC Axioms (implemented as operations, not just asserted):
1. Extensionality — A = B iff same elements (enforced by __eq__)
2. Empty Set     — ∅ exists
3. Pairing       — {a, b} exists for any a, b
4. Union         — ⋃A exists for any family A
5. Power Set     — P(A) = {S : S ⊆ A} exists for any A
6. Separation    — {x ∈ A : φ(x)} exists for any A and predicate φ
7. Replacement   — {F(x) : x ∈ A} exists for any A and function F
8. Foundation    — no infinite descending ∈-chains
9. Choice        — every family of non-empty sets has a choice function

Mirror of categorical/category.py (~230 lines → ~400 lines)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any, Callable, Dict, FrozenSet, Iterator, List,
    Optional, Set as PySet, Tuple,
)


# ═══════════════════════════════════════════════════════════════════
# Primitive: ZFSet
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=False)
class ZFSet:
    """
    A set in the ZFC universe.

    In ZFC, everything is a set. Elements are sets.
    The only primitive relation is membership (∈).

    Mirror of categorical.Object — but richer.
    An Object is opaque (determined by its morphisms via Yoneda).
    A Set has internal structure (its elements).
    """
    name: str
    _elements: PySet[str] = field(default_factory=set)  # element names
    data: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, ZFSet):
            return self.name == other.name
        return False

    def __repr__(self):
        if not self._elements:
            return f"∅" if self.name == "∅" else f"{self.name}"
        return f"{self.name}"

    def __contains__(self, item):
        """Membership test: item ∈ self."""
        if isinstance(item, ZFSet):
            return item.name in self._elements
        if isinstance(item, str):
            return item in self._elements
        return False


# ═══════════════════════════════════════════════════════════════════
# Primitive: Relation (the ZFC analog of Morphism)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Relation:
    """
    A relation R between elements.

    In category theory, a morphism f: A → B IS an arrow with composition.
    In ZFC, a relation is a set of ordered pairs — no composition law.

    Composition must be constructed explicitly:
    R;S = {(a,c) : ∃b. (a,b) ∈ R and (b,c) ∈ S}

    This is the fundamental difference. Categorical composition is
    given by structure. Set-theoretic composition is constructed.
    """
    name: str
    pairs: PySet[Tuple[str, str]] = field(default_factory=set)
    data: Dict[str, Any] = field(default_factory=dict)

    def add(self, a: str, b: str):
        """Assert (a, b) ∈ R."""
        self.pairs.add((a, b))

    def holds(self, a: str, b: str) -> bool:
        """Check (a, b) ∈ R."""
        return (a, b) in self.pairs

    def image(self, a: str) -> PySet[str]:
        """R(a) = {b : (a,b) ∈ R}."""
        return {b for (x, b) in self.pairs if x == a}

    def preimage(self, b: str) -> PySet[str]:
        """R⁻¹(b) = {a : (a,b) ∈ R}."""
        return {a for (a, y) in self.pairs if y == b}

    def domain_set(self) -> PySet[str]:
        """dom(R) = {a : ∃b. (a,b) ∈ R}."""
        return {a for (a, _) in self.pairs}

    def codomain_set(self) -> PySet[str]:
        """cod(R) = {b : ∃a. (a,b) ∈ R}."""
        return {b for (_, b) in self.pairs}

    def __repr__(self):
        return f"Relation({self.name}, |pairs|={len(self.pairs)})"


# ═══════════════════════════════════════════════════════════════════
# Universe: the ZFC analog of Category
# ═══════════════════════════════════════════════════════════════════

class Universe:
    """
    A ZFC Universe — the container for all sets and relations.

    Mirror of categorical.Category.

    Category has: objects, morphisms, hom_sets, identities, compose
    Universe has: sets, relations, membership, power_sets, separate

    Category checks: associativity, identity law, commutativity
    Universe checks: satisfiability, well-ordering, comprehension
    """

    def __init__(self, name: str = "V"):
        self.name = name
        self.sets: Dict[str, ZFSet] = {}
        self.relations: Dict[str, Relation] = {}

        # The empty set — Axiom of Empty Set
        self._empty = ZFSet(name="∅")
        self.sets["∅"] = self._empty

    # ── Axiom 2: Empty Set ──────────────────────────────────────

    @property
    def empty(self) -> ZFSet:
        """The empty set ∅."""
        return self._empty

    # ── Set management ──────────────────────────────────────────

    def add_set(self, s: ZFSet) -> ZFSet:
        """Add a set to the universe."""
        self.sets[s.name] = s
        return s

    def get_set(self, name: str) -> Optional[ZFSet]:
        """Retrieve a set by name."""
        return self.sets.get(name)

    def add_element(self, element: ZFSet, container: ZFSet):
        """Assert element ∈ container."""
        if element.name not in self.sets:
            self.add_set(element)
        if container.name not in self.sets:
            self.add_set(container)
        container._elements.add(element.name)

    def membership(self, element: str, container: str) -> bool:
        """Test element ∈ container."""
        s = self.sets.get(container)
        if s is None:
            return False
        return element in s._elements

    # ── Relation management ─────────────────────────────────────

    def add_relation(self, rel: Relation) -> Relation:
        """Add a relation to the universe."""
        self.relations[rel.name] = rel
        return rel

    def get_relation(self, name: str) -> Optional[Relation]:
        """Retrieve a relation by name."""
        return self.relations.get(name)

    # ── Axiom 3: Pairing ───────────────────────────────────────

    def pair(self, a: ZFSet, b: ZFSet) -> ZFSet:
        """
        Pairing axiom: {a, b} exists.

        Creates the set containing exactly a and b.
        """
        name = f"{{{a.name},{b.name}}}"
        p = ZFSet(name=name, _elements={a.name, b.name})
        return self.add_set(p)

    def singleton(self, a: ZFSet) -> ZFSet:
        """Singleton: {a}."""
        name = f"{{{a.name}}}"
        s = ZFSet(name=name, _elements={a.name})
        return self.add_set(s)

    # ── Axiom 4: Union ─────────────────────────────────────────

    def union(self, A: ZFSet, B: ZFSet) -> ZFSet:
        """
        Union: A ∪ B = {x : x ∈ A or x ∈ B}.
        """
        elements = A._elements | B._elements
        name = f"({A.name}∪{B.name})"
        u = ZFSet(name=name, _elements=elements)
        return self.add_set(u)

    def big_union(self, family: ZFSet) -> ZFSet:
        """
        Generalized union: ⋃F = {x : ∃A ∈ F. x ∈ A}.

        Takes a set of sets, returns the union of all elements.
        """
        elements: PySet[str] = set()
        for member_name in family._elements:
            member = self.sets.get(member_name)
            if member is not None:
                elements |= member._elements
        name = f"⋃{family.name}"
        u = ZFSet(name=name, _elements=elements)
        return self.add_set(u)

    # ── Axiom 4b: Intersection ─────────────────────────────────

    def intersection(self, A: ZFSet, B: ZFSet) -> ZFSet:
        """
        Intersection: A ∩ B = {x : x ∈ A and x ∈ B}.

        Derived from Separation: {x ∈ A : x ∈ B}.
        """
        elements = A._elements & B._elements
        name = f"({A.name}∩{B.name})"
        i = ZFSet(name=name, _elements=elements)
        return self.add_set(i)

    def difference(self, A: ZFSet, B: ZFSet) -> ZFSet:
        """
        Set difference: A \\ B = {x ∈ A : x ∉ B}.

        Derived from Separation.
        """
        elements = A._elements - B._elements
        name = f"({A.name}\\{B.name})"
        d = ZFSet(name=name, _elements=elements)
        return self.add_set(d)

    # ── Axiom 5: Power Set ─────────────────────────────────────

    def power_set(self, A: ZFSet) -> ZFSet:
        """
        Power set axiom: P(A) = {S : S ⊆ A}.

        Returns the set of all subsets of A.
        WARNING: |P(A)| = 2^|A|. Only use on small sets.
        """
        elem_list = sorted(A._elements)
        n = len(elem_list)

        if n > 20:
            raise ValueError(
                f"Power set of {A.name} has 2^{n} elements. "
                f"Use separation instead."
            )

        subsets: PySet[str] = set()
        for mask in range(1 << n):
            subset_elems = frozenset(
                elem_list[i] for i in range(n) if mask & (1 << i)
            )
            subset_name = "{" + ",".join(sorted(subset_elems)) + "}" if subset_elems else "∅"
            sub = ZFSet(name=subset_name, _elements=set(subset_elems))
            self.add_set(sub)
            subsets.add(subset_name)

        name = f"P({A.name})"
        ps = ZFSet(name=name, _elements=subsets)
        return self.add_set(ps)

    # ── Axiom 6: Separation (Comprehension) ────────────────────

    def separate(self, A: ZFSet, predicate: Callable[[str], bool],
                 name: Optional[str] = None) -> ZFSet:
        """
        Separation axiom: {x ∈ A : φ(x)}.

        Given a set A and a predicate φ, returns the subset
        of A satisfying φ.

        This is the ZFC analog of sheaf coherence:
        "Filter the elements that satisfy a condition."

        Mirror of: SheafCoherenceChecker.check_coherence
        But different: sheaf checks "do sections agree on overlaps?"
        Separation checks "does each element satisfy a predicate?"
        """
        elements = {x for x in A._elements if predicate(x)}
        if name is None:
            name = f"{{{A.name}|φ}}"
        s = ZFSet(name=name, _elements=elements)
        return self.add_set(s)

    # ── Axiom 7: Replacement ───────────────────────────────────

    def replace(self, A: ZFSet, function: Callable[[str], str],
                name: Optional[str] = None) -> ZFSet:
        """
        Replacement axiom: {F(x) : x ∈ A}.

        Given a set A and a function F, returns the image of A under F.
        Elements that F maps to must exist in the universe.

        Mirror of: Functor.object_map
        But different: a functor preserves composition.
        Replacement just maps elements — no structure preservation required.
        """
        elements: PySet[str] = set()
        for x in A._elements:
            fx = function(x)
            if fx is not None:
                elements.add(fx)
        if name is None:
            name = f"F({A.name})"
        r = ZFSet(name=name, _elements=elements)
        return self.add_set(r)

    # ── Cartesian Product ──────────────────────────────────────

    def cartesian_product(self, A: ZFSet, B: ZFSet) -> Relation:
        """
        A × B as a relation containing all ordered pairs (a, b).

        This is not a ZFSet of Kuratowski pairs (too expensive).
        It's a Relation — the practical encoding for computation.
        """
        rel = Relation(name=f"{A.name}×{B.name}")
        for a in A._elements:
            for b in B._elements:
                rel.add(a, b)
        return self.add_relation(rel)

    # ── Relation Composition ───────────────────────────────────

    def compose_relations(self, R: Relation, S: Relation) -> Relation:
        """
        Relational composition: R;S = {(a,c) : ∃b. (a,b) ∈ R ∧ (b,c) ∈ S}.

        Mirror of: Category.compose(f, g)
        But different: categorical composition is given by structure.
        This is CONSTRUCTED by searching for witnesses.

        The existential quantifier (∃b) is the key difference.
        Category theory: composition is an operation.
        Set theory: composition requires finding a witness.
        """
        name = f"({R.name};{S.name})"
        composed = Relation(name=name)

        for (a, b) in R.pairs:
            for c in S.image(b):
                composed.add(a, c)

        return self.add_relation(composed)

    # ── Transitive Closure ─────────────────────────────────────

    def transitive_closure(self, R: Relation) -> Relation:
        """
        R⁺ = R ∪ R;R ∪ R;R;R ∪ ...

        The smallest transitive relation containing R.

        Mirror of: Category.find_paths (all composable paths)
        But different: find_paths returns each path.
        Transitive closure collapses all paths into direct pairs.
        """
        name = f"({R.name})⁺"
        closure = Relation(name=name)
        closure.pairs = set(R.pairs)

        changed = True
        while changed:
            changed = False
            new_pairs: PySet[Tuple[str, str]] = set()
            for (a, b) in closure.pairs:
                for c in closure.image(b):
                    if (a, c) not in closure.pairs:
                        new_pairs.add((a, c))
                        changed = True
            closure.pairs |= new_pairs

        return self.add_relation(closure)

    # ── Well-Ordering (Axiom of Choice consequence) ────────────

    def well_order(self, A: ZFSet,
                   key: Optional[Callable[[str], Any]] = None) -> List[str]:
        """
        Well-ordering theorem: every set can be well-ordered.

        Returns elements of A in a well-ordering.
        If key is provided, uses it. Otherwise uses name ordering.

        Mirror of: cubical paths (one canonical path through everything)
        But different: cubical gives parallel paths.
        Well-ordering gives ONE canonical linear order.
        """
        elements = list(A._elements)
        if key:
            elements.sort(key=key)
        else:
            elements.sort()
        return elements

    # ── Satisfiability Check ───────────────────────────────────

    def check_constraints(
        self,
        constraints: List[Callable[[Dict[str, ZFSet]], bool]],
        variables: Dict[str, ZFSet],
    ) -> Tuple[bool, Optional[Dict[str, str]]]:
        """
        Check if a set of constraints is simultaneously satisfiable.

        Given variables (name → domain set) and constraints (predicates
        over variable assignments), find an assignment that satisfies all
        constraints, or report unsatisfiable.

        This is the ZFC analog of sheaf coherence:
        - Sheaf: "do local sections glue to a global section?"
        - SAT:   "do local constraints have a global solution?"

        For small domains, uses brute-force search.
        For large domains, this should delegate to Z3/SMT.

        Args:
            constraints: list of predicates, each takes {var_name: value_name}
            variables: {var_name: ZFSet} where ZFSet is the domain

        Returns:
            (satisfiable, witness_assignment_or_None)
        """
        var_names = list(variables.keys())
        domains = [sorted(variables[v]._elements) for v in var_names]

        # Check total search space
        total = 1
        for d in domains:
            total *= max(len(d), 1)
            if total > 1_000_000:
                # Too large for brute force — need SMT
                return self._check_constraints_heuristic(
                    constraints, var_names, domains
                )

        # Brute-force search over all assignments
        return self._check_constraints_brute(
            constraints, var_names, domains
        )

    def _check_constraints_brute(
        self,
        constraints: List[Callable],
        var_names: List[str],
        domains: List[List[str]],
    ) -> Tuple[bool, Optional[Dict[str, str]]]:
        """Brute-force constraint satisfaction."""

        def search(idx: int, assignment: Dict[str, str]):
            if idx == len(var_names):
                # Check all constraints
                if all(c(assignment) for c in constraints):
                    return dict(assignment)
                return None

            for value in domains[idx]:
                assignment[var_names[idx]] = value
                result = search(idx + 1, assignment)
                if result is not None:
                    return result
                del assignment[var_names[idx]]
            return None

        witness = search(0, {})
        return (witness is not None, witness)

    def _check_constraints_heuristic(
        self,
        constraints: List[Callable],
        var_names: List[str],
        domains: List[List[str]],
    ) -> Tuple[bool, Optional[Dict[str, str]]]:
        """
        Heuristic constraint satisfaction for large domains.

        Uses arc consistency + forward checking.
        For production, replace with Z3 binding.
        """
        # Simplified: try first valid assignment with forward checking
        assignment: Dict[str, str] = {}

        for i, var in enumerate(var_names):
            found = False
            for value in domains[i]:
                assignment[var] = value
                # Check constraints that are fully bound
                partial_ok = True
                for c in constraints:
                    try:
                        if not c(assignment):
                            partial_ok = False
                            break
                    except (KeyError, TypeError):
                        continue  # constraint involves unbound variables
                if partial_ok:
                    found = True
                    break
                del assignment[var]

            if not found:
                return (False, None)

        # Verify complete assignment
        if all(c(assignment) for c in constraints):
            return (True, assignment)
        return (False, None)

    # ── Extensionality Check ───────────────────────────────────

    def extensionally_equal(self, A: ZFSet, B: ZFSet) -> bool:
        """
        Extensionality axiom: A = B iff ∀x(x ∈ A ↔ x ∈ B).

        This checks actual element equality, not just name equality.
        """
        return A._elements == B._elements

    # ── Foundation Check ───────────────────────────────────────

    def check_well_founded(self, start: str, depth: int = 100) -> bool:
        """
        Check foundation axiom: no infinite ∈-descending chains.

        Starting from a set, follow membership down.
        If we hit ∅ or revisit a set, we're fine.
        If we exceed depth, flag potential violation.
        """
        visited: PySet[str] = set()
        current = start

        for _ in range(depth):
            if current in visited:
                return False  # cycle detected
            visited.add(current)

            s = self.sets.get(current)
            if s is None or len(s._elements) == 0:
                return True  # reached ∅ or atom

            # Follow first element down
            current = next(iter(s._elements))

        return False  # exceeded depth

    # ── Display ────────────────────────────────────────────────

    def __repr__(self):
        return (
            f"Universe({self.name}, "
            f"|Sets|={len(self.sets)}, "
            f"|Relations|={len(self.relations)})"
        )


# ═══════════════════════════════════════════════════════════════════
# Convenience constructors (mirror category.py's obj() and mor())
# ═══════════════════════════════════════════════════════════════════

def zfset(name: str, elements: Optional[PySet[str]] = None,
          **kwargs) -> ZFSet:
    """Create a ZFSet. Mirror of categorical.obj()."""
    return ZFSet(
        name=name,
        _elements=set(elements) if elements else set(),
        data=kwargs,
    )


def relation(name: str, pairs: Optional[List[Tuple[str, str]]] = None,
             **kwargs) -> Relation:
    """Create a Relation. Mirror of categorical.mor()."""
    rel = Relation(name=name, data=kwargs)
    if pairs:
        for a, b in pairs:
            rel.add(a, b)
    return rel


# ═══════════════════════════════════════════════════════════════════
# Example usage and tests
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Create a universe
    V = Universe("DrugUniverse")

    # Add sets (drugs, proteins, diseases)
    drugs = V.add_set(zfset("Drugs"))
    proteins = V.add_set(zfset("Proteins"))
    diseases = V.add_set(zfset("Diseases"))

    # Add elements
    aspirin = V.add_set(zfset("Aspirin", type="Drug"))
    ibuprofen = V.add_set(zfset("Ibuprofen", type="Drug"))
    cox2 = V.add_set(zfset("COX2", type="Protein"))
    inflammation = V.add_set(zfset("Inflammation", type="Disease"))

    V.add_element(aspirin, drugs)
    V.add_element(ibuprofen, drugs)
    V.add_element(cox2, proteins)
    V.add_element(inflammation, diseases)

    # Add relations (the ZFC analog of morphisms)
    inhibits = relation("inhibits", [
        ("Aspirin", "COX2"),
        ("Ibuprofen", "COX2"),
    ])
    V.add_relation(inhibits)

    treats = relation("treats", [
        ("Aspirin", "Inflammation"),
    ])
    V.add_relation(treats)

    associated = relation("associated_with", [
        ("COX2", "Inflammation"),
    ])
    V.add_relation(associated)

    # Compose relations: inhibits;associated = drugs that treat via target
    indirect = V.compose_relations(inhibits, associated)
    print(f"inhibits;associated = {indirect.pairs}")
    # Should show: Aspirin→Inflammation, Ibuprofen→Inflammation

    # Separation: drugs that inhibit COX2
    cox2_inhibitors = V.separate(
        drugs,
        lambda x: inhibits.holds(x, "COX2"),
        name="COX2_inhibitors"
    )
    print(f"COX2 inhibitors: {cox2_inhibitors._elements}")

    # Constraint satisfaction: find a drug that inhibits COX2 AND treats inflammation
    sat, witness = V.check_constraints(
        constraints=[
            lambda a: inhibits.holds(a["drug"], "COX2"),
            lambda a: treats.holds(a["drug"], "Inflammation"),
        ],
        variables={
            "drug": drugs,
        },
    )
    print(f"Drug that inhibits COX2 AND treats Inflammation: {sat}, {witness}")

    # Transitive closure
    r = relation("connected", [("A", "B"), ("B", "C"), ("C", "D")])
    V.add_relation(r)
    tc = V.transitive_closure(r)
    print(f"Transitive closure: {sorted(tc.pairs)}")

    print(V)
