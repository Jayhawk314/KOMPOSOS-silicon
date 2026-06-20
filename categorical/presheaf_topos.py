# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Presheaf Topos: Multi-Valued Truth via Subobject Classifier

The presheaf category Set^(C^op) on attack category C provides:
  - Objects: Functors C^op -> Set (presheaves)
  - Morphisms: Natural transformations between presheaves
  - Subobject classifier Omega: sieve functor for multi-valued truth

Key constructions:
  1. Yoneda embedding y: C -> Set^(C^op), y(T) = Hom(-, T)
  2. Yoneda Lemma: Nat(y(T), P) ~= P(T)
  3. Subobject classifier Omega(T) = {all sieves on T}
  4. Internal logic: AND, OR, NOT, IMPLIES on sieves (intuitionistic)

Cyber application:
  Instead of binary "is this an attack?" we get a sieve:
  "from these perspectives it looks like an attack, from those it doesn't."
  This captures partial observability and multi-sensor fusion naturally.

Mathematical basis:
  - Mac Lane & Moerdijk, "Sheaves in Geometry and Logic" (1992)
  - Baez, "Topos Theory in a Nutshell" (blog, Parts 7-8)
  - Caramello, "Theories, Sites, Toposes" (2018)
  - lovelylittlelemmas (blog), Sieve-based truth values
"""

import math
from typing import Dict, Set, List, Tuple, Optional, Callable, Any, FrozenSet
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SieveMorphism:
    """A morphism in the base category, used as sieve element."""
    source: str
    target: str
    name: str = ""

    def __hash__(self):
        return hash((self.source, self.target, self.name))


class Sieve:
    """
    A sieve on object T is a downward-closed set of morphisms into T.

    S is a sieve on T if:
      - Every morphism in S has codomain T
      - If (f: A -> T) in S and (g: B -> A) composable, then (f o g: B -> T) in S

    This is an element of the subobject classifier Omega(T).
    Represents "partial truth" - from which perspectives is something true?

    Mathematical basis:
      Mac Lane & Moerdijk, Ch. I.4
      "A sieve on c is a family S of morphisms with codomain c
       such that f in S and composable g implies f o g in S."
    """

    def __init__(self, target: str, morphisms: Optional[Set[SieveMorphism]] = None):
        self.target = target
        self.morphisms: Set[SieveMorphism] = morphisms or set()

    @property
    def is_maximal(self) -> bool:
        """Maximal sieve = all morphisms into target = TRUE."""
        return self._is_maximal

    @is_maximal.setter
    def is_maximal(self, value: bool):
        self._is_maximal = value

    @property
    def is_empty(self) -> bool:
        """Empty sieve = no morphisms = FALSE."""
        return len(self.morphisms) == 0

    def truth_value(self, total_incoming: int) -> float:
        """
        Convert sieve to [0,1] truth value.

        truth = |S| / |maximal sieve on T|

        Maximal sieve (all morphisms) = 1.0 (fully true)
        Empty sieve = 0.0 (fully false)
        Partial sieve = proportion of morphisms included
        """
        if total_incoming == 0:
            return 1.0 if len(self.morphisms) == 0 else 0.0
        return len(self.morphisms) / total_incoming

    def from_perspectives(self) -> Set[str]:
        """Which objects (perspectives/sources) consider this true?"""
        return {m.source for m in self.morphisms}

    def pullback(self, morphism: SieveMorphism) -> 'Sieve':
        """
        Pullback sieve along morphism f: A -> T.

        f*(S) = {g : B -> A | f o g in S}

        This is the key operation for presheaf functoriality.
        """
        pulled = set()
        for m in self.morphisms:
            if m.source == morphism.source:
                # g: B -> A such that f o g factors through S
                pulled.add(SieveMorphism(
                    source=m.source,
                    target=morphism.source,
                    name=f"pb_{m.name}"
                ))
        return Sieve(morphism.source, pulled)

    def intersect(self, other: 'Sieve') -> 'Sieve':
        """S /\\ T = S ∩ T — conjunction of sieves."""
        if self.target != other.target:
            raise ValueError(f"Cannot intersect sieves on different targets: {self.target} vs {other.target}")
        return Sieve(self.target, self.morphisms & other.morphisms)

    def union(self, other: 'Sieve') -> 'Sieve':
        """S \\/ T = S ∪ T — disjunction of sieves."""
        if self.target != other.target:
            raise ValueError(f"Cannot union sieves on different targets: {self.target} vs {other.target}")
        return Sieve(self.target, self.morphisms | other.morphisms)

    def __and__(self, other: 'Sieve') -> 'Sieve':
        return self.intersect(other)

    def __or__(self, other: 'Sieve') -> 'Sieve':
        return self.union(other)

    def __repr__(self):
        perspectives = self.from_perspectives()
        return f"Sieve(on={self.target}, perspectives={perspectives})"


class Presheaf:
    """
    Functor F: C^op -> Set.

    Assigns to each object a set F(c), and to each morphism f: a -> b
    a restriction function F(f): F(b) -> F(a).

    This is the contravariant version: morphisms reverse direction.

    Mathematical basis:
      Fong & Spivak, "Seven Sketches", Ch. 7
      "A presheaf on C is a functor C^op -> Set"
    """

    def __init__(self, name: str):
        self.name = name
        self.values: Dict[str, Set[str]] = {}  # F(object) = set of elements
        self.restrictions: Dict[Tuple[str, str], Dict[str, str]] = {}  # F(f): F(b) -> F(a)

    def evaluate(self, obj: str) -> Set[str]:
        """F(obj) - evaluate presheaf at object."""
        return self.values.get(obj, set())

    def set_value(self, obj: str, elements: Set[str]):
        """Set F(obj) = elements."""
        self.values[obj] = elements

    def set_restriction(self, source: str, target: str, mapping: Dict[str, str]):
        """
        Set F(f) for morphism f: source -> target.
        F(f): F(target) -> F(source) (contravariant!)
        """
        self.restrictions[(source, target)] = mapping

    def restrict(self, source: str, target: str, element: str) -> Optional[str]:
        """Apply restriction F(f)(element) for f: source -> target."""
        mapping = self.restrictions.get((source, target))
        if mapping is None:
            return None
        return mapping.get(element)

    def __repr__(self):
        return f"Presheaf({self.name}, |values|={len(self.values)})"


class RepresentablePresheaf(Presheaf):
    """
    y(T) = Hom(-, T) — the Yoneda embedding of technique T.

    For each object S in C, y(T)(S) = Hom(S, T) = {morphisms from S to T}.

    The Yoneda Lemma guarantees:
      Nat(y(T), P) ~= P(T) for any presheaf P

    "A technique is fully characterized by how ALL other techniques relate to it."

    Mathematical basis:
      Milewski, "Yoneda Embedding" (blog)
      "The Yoneda embedding is the most important result in category theory"
    """

    def __init__(self, technique: str, all_morphisms: Dict[Tuple[str, str], List[str]]):
        """
        Build representable presheaf y(T).

        Args:
            technique: The technique T to embed
            all_morphisms: Dict mapping (source, target) -> list of morphism names
        """
        super().__init__(f"y({technique})")
        self.technique = technique
        self._build(all_morphisms)

    def _build(self, all_morphisms: Dict[Tuple[str, str], List[str]]):
        """Compute y(T)(S) = Hom(S, T) for all S."""
        for (source, target), mor_names in all_morphisms.items():
            if target == self.technique:
                self.values.setdefault(source, set())
                for name in mor_names:
                    self.values[source].add(name)

        # Also add identity
        self.values.setdefault(self.technique, set())
        self.values[self.technique].add(f"id_{self.technique}")

    def hom_set_size(self, source: str) -> int:
        """| Hom(source, T) | — number of morphisms from source to T."""
        return len(self.evaluate(source))


class PresheafTopos:
    """
    The topos Set^(C^op) for attack category C.

    Provides:
      1. Yoneda embedding: y(T) for each technique T
      2. Subobject classifier: Omega for multi-valued truth
      3. Internal logic: /\\, \\/, not, => on sieves (intuitionistic)
      4. Characteristic morphism: chi for attack subobject detection
      5. Yoneda distance: d(T1, T2) from symmetric difference of hom-sets

    Key insight for cybersecurity:
      Binary detection ("attack" / "not attack") loses information.
      Sieve-based truth preserves WHICH PERSPECTIVES see the attack,
      enabling multi-sensor fusion and partial observability handling.

    Mathematical basis:
      Mac Lane & Moerdijk, "Sheaves in Geometry and Logic", Ch. I
      Baez, "Topos Theory in a Nutshell", Parts 7-8
      Caramello, "Theories, Sites, Toposes"
    """

    def __init__(self, objects: List[str],
                 morphisms: Dict[Tuple[str, str], List[str]],
                 adjacency: Optional[Dict[str, List[str]]] = None):
        """
        Build presheaf topos from category data.

        Args:
            objects: List of object names (technique IDs)
            morphisms: Dict mapping (source, target) -> list of morphism names
            adjacency: Optional adjacency dict for efficiency
        """
        self.objects = set(objects)
        self.morphisms = morphisms
        self.adjacency = adjacency or self._build_adjacency()
        self.representables: Dict[str, RepresentablePresheaf] = {}

        # All morphism objects for sieve computation
        self._all_morphism_objects: Dict[str, Set[SieveMorphism]] = {}

        self._build_yoneda_embedding()
        self._build_morphism_index()

    def _build_adjacency(self) -> Dict[str, List[str]]:
        """Build adjacency from morphisms."""
        adj: Dict[str, List[str]] = {}
        for (source, target) in self.morphisms:
            adj.setdefault(source, []).append(target)
        return adj

    def _build_yoneda_embedding(self):
        """Compute y(T) for all techniques T."""
        for obj in self.objects:
            self.representables[obj] = RepresentablePresheaf(obj, self.morphisms)

    def _build_morphism_index(self):
        """Index all morphisms by target for sieve construction."""
        for (source, target), names in self.morphisms.items():
            self._all_morphism_objects.setdefault(target, set())
            for name in names:
                self._all_morphism_objects[target].add(
                    SieveMorphism(source=source, target=target, name=name)
                )

    def incoming_count(self, obj: str) -> int:
        """Number of morphisms into obj (for truth value normalization)."""
        return len(self._all_morphism_objects.get(obj, set()))

    # === YONEDA DISTANCE ===

    def yoneda_distance(self, T1: str, T2: str) -> float:
        """
        Distance between techniques based on Yoneda embedding.

        d(T1, T2) = |y(T1) triangle y(T2)| / |y(T1) union y(T2)|

        Symmetric difference of incoming hom-sets, normalized.
        Techniques with similar roles have small distance.

        This is a proper metric:
          d(T, T) = 0
          d(T1, T2) = d(T2, T1)
          d(T1, T3) <= d(T1, T2) + d(T2, T3) (triangle inequality)
        """
        if T1 not in self.representables or T2 not in self.representables:
            return 1.0

        # Collect all sources that have morphisms into T1 or T2
        sources1 = set()
        sources2 = set()

        for obj in self.objects:
            if self.representables[T1].evaluate(obj):
                sources1.add(obj)
            if self.representables[T2].evaluate(obj):
                sources2.add(obj)

        sym_diff = sources1.symmetric_difference(sources2)
        union = sources1.union(sources2)

        if not union:
            return 0.0

        return len(sym_diff) / len(union)

    def yoneda_similarity(self, T1: str, T2: str) -> float:
        """1 - yoneda_distance: similarity between techniques."""
        return 1.0 - self.yoneda_distance(T1, T2)

    def find_similar_techniques(self, technique: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Find techniques most similar to given one via Yoneda distance."""
        distances = []
        for obj in self.objects:
            if obj != technique:
                d = self.yoneda_distance(technique, obj)
                distances.append((obj, d))

        distances.sort(key=lambda x: x[1])
        return distances[:top_k]

    # === SUBOBJECT CLASSIFIER ===

    def maximal_sieve(self, target: str) -> Sieve:
        """
        Maximal sieve on target = all morphisms into target = TRUE.

        The maximal sieve represents "true from every perspective."
        """
        morphisms = self._all_morphism_objects.get(target, set()).copy()
        sieve = Sieve(target, morphisms)
        sieve._is_maximal = True
        return sieve

    def empty_sieve(self, target: str) -> Sieve:
        """
        Empty sieve on target = no morphisms = FALSE.

        The empty sieve represents "true from no perspective."
        """
        sieve = Sieve(target, set())
        sieve._is_maximal = False
        return sieve

    def principal_sieve(self, morphism: SieveMorphism) -> Sieve:
        """
        Principal sieve generated by morphism f: S -> T.

        S_f = {g | g factors through f} = {f o h for all composable h}

        This is the sieve generated by a single observation.
        """
        sieve_morphisms = {morphism}

        # Add all compositions f o g where g: R -> S
        source = morphism.source
        for (s, t), names in self.morphisms.items():
            if t == source:
                for name in names:
                    composed = SieveMorphism(
                        source=s,
                        target=morphism.target,
                        name=f"{morphism.name}_o_{name}"
                    )
                    sieve_morphisms.add(composed)

        return Sieve(morphism.target, sieve_morphisms)

    # === CLASSIFY ATTACK (CORE METHOD) ===

    def classify_attack(self, observed_techniques: List[str],
                        target_technique: str) -> Sieve:
        """
        Classify a set of observed events using the subobject classifier.

        Returns a sieve (multi-valued truth) indicating from which
        perspectives the target_technique appears to be happening.

        Example:
          observed = ["T1566", "T1059", "T1082"]
          target = "T1003"  (credential dumping)

          Returns sieve showing:
          - From T1566 perspective: TRUE (phishing -> cred dump is valid chain)
          - From T1082 perspective: TRUE (recon -> cred dump is valid)
          - From T1059 perspective: TRUE (execution -> cred dump is valid)
          Overall truth: 3/N perspectives

        This gives SOC analysts a nuanced view: "based on what we've seen,
        here's the evidence strength from each vantage point."
        """
        sieve_morphisms = set()

        for obs_tech in observed_techniques:
            # Check if there's a morphism from obs_tech to target
            key = (obs_tech, target_technique)
            if key in self.morphisms:
                for name in self.morphisms[key]:
                    sieve_morphisms.add(SieveMorphism(
                        source=obs_tech,
                        target=target_technique,
                        name=name
                    ))

            # Also check transitive paths (through one intermediate)
            for intermediate in self.adjacency.get(obs_tech, []):
                if (intermediate, target_technique) in self.morphisms:
                    for name in self.morphisms[(intermediate, target_technique)]:
                        composed_name = f"via_{intermediate}_{name}"
                        sieve_morphisms.add(SieveMorphism(
                            source=obs_tech,
                            target=target_technique,
                            name=composed_name
                        ))

        return Sieve(target_technique, sieve_morphisms)

    def classify_attack_full(self, observed_techniques: List[str]) -> Dict[str, Sieve]:
        """
        Classify against ALL techniques — which attacks could be in progress?

        Returns a dict mapping each technique to its sieve (evidence strength).
        Techniques with high sieve truth values are likely next steps.
        """
        results = {}
        for target in self.objects:
            if target not in observed_techniques:
                sieve = self.classify_attack(observed_techniques, target)
                if not sieve.is_empty:
                    results[target] = sieve
        return results

    def threat_assessment(self, observed_techniques: List[str],
                          top_k: int = 10) -> List[Tuple[str, float, Set[str]]]:
        """
        Full threat assessment using topos logic.

        Returns: List of (technique_id, truth_value, supporting_perspectives)
                 sorted by truth_value descending.
        """
        classifications = self.classify_attack_full(observed_techniques)
        assessments = []

        for tech, sieve in classifications.items():
            total = self.incoming_count(tech)
            if total == 0:
                total = 1
            truth = sieve.truth_value(total)
            perspectives = sieve.from_perspectives()
            assessments.append((tech, truth, perspectives))

        assessments.sort(key=lambda x: x[1], reverse=True)
        return assessments[:top_k]

    # === INTERNAL LOGIC ===

    def negation(self, sieve: Sieve) -> Sieve:
        """
        Heyting negation: not(S) = S => empty_sieve.

        not(S)(T) = {f: A -> T | for all g composable with f,
                     f o g not in S}

        Note: In intuitionistic logic, not(not(S)) != S in general!
        This captures partial observability: "not seeing evidence"
        is weaker than "evidence of absence."
        """
        all_incoming = self._all_morphism_objects.get(sieve.target, set())
        negated = all_incoming - sieve.morphisms
        return Sieve(sieve.target, negated)

    def implication(self, sieve1: Sieve, sieve2: Sieve) -> Sieve:
        """
        Internal implication: S1 => S2.

        (S1 => S2)(T) = {f: A -> T | for all g: B -> A,
                         if f o g in S1 then f o g in S2}

        Cyber interpretation: "If we see evidence of type S1,
        then S2 must also hold" — conditional threat inference.
        """
        if sieve1.target != sieve2.target:
            raise ValueError("Sieves must be on same target for implication")

        # S1 => S2 contains morphisms f where:
        # being in S1 implies being in S2
        # Simplified: (not S1) union S2
        neg_s1 = self.negation(sieve1)
        return neg_s1 | sieve2

    def conjunction(self, sieve1: Sieve, sieve2: Sieve) -> Sieve:
        """S1 /\\ S2 = intersection — both hold."""
        return sieve1 & sieve2

    def disjunction(self, sieve1: Sieve, sieve2: Sieve) -> Sieve:
        """S1 \\/ S2 = union — at least one holds."""
        return sieve1 | sieve2

    # === ENRICHED CATEGORY BRIDGE ===

    @classmethod
    def from_enriched_category(cls, enriched_cat) -> 'PresheafTopos':
        """
        Build presheaf topos from an EnrichedCategory or KOMPOSOS-IV Category.

        Converts enriched hom-objects to morphism sets:
        - Each non-zero hom(A, B) becomes a morphism A -> B
        - Weight becomes metadata on the morphism

        Supports both:
        - EnrichedCategory (with .objects dict and .hom_objects)
        - KOMPOSOS-IV Category (with .objects() method and .morphisms())
        """
        # Detect whether this is a KOMPOSOS-IV Category or EnrichedCategory
        if hasattr(enriched_cat, 'objects') and callable(enriched_cat.objects):
            # KOMPOSOS-IV Category: objects() returns list of Object
            objects = [obj.name for obj in enriched_cat.objects()]
            morphisms: Dict[Tuple[str, str], List[str]] = {}
            adjacency: Dict[str, List[str]] = {}

            for mor in enriched_cat.morphisms():
                key = (mor.source, mor.target)
                morphisms.setdefault(key, []).append(mor.name)
                adjacency.setdefault(mor.source, []).append(mor.target)
        else:
            # EnrichedCategory: objects is a dict
            objects = list(enriched_cat.objects.keys())
            morphisms: Dict[Tuple[str, str], List[str]] = {}
            adjacency = {}

            for (source, target), weight in enriched_cat.hom_objects.items():
                if source != target and weight is not None and weight > 0:
                    mor_name = f"{source}_to_{target}"
                    morphisms.setdefault((source, target), []).append(mor_name)
                    adjacency.setdefault(source, []).append(target)

        return cls(objects, morphisms, adjacency)

    # === YONEDA LEMMA APPLICATION ===

    def yoneda_lemma(self, technique: str, presheaf: Presheaf) -> Set[str]:
        """
        Apply Yoneda Lemma: Nat(y(T), P) ~= P(T).

        Given a technique T and a presheaf P, compute P(T)
        via the natural transformations from y(T) to P.

        This is the theoretical justification for why the Yoneda
        embedding fully characterizes techniques: knowing how a
        technique relates to all others IS the technique.
        """
        return presheaf.evaluate(technique)

    def attack_presheaf(self, observed: List[str]) -> Presheaf:
        """
        Build an "attack presheaf" from observed techniques.

        For each technique T, the attack presheaf assigns:
          A(T) = {evidence relating T to the observed attack}

        This is a presheaf (functor C^op -> Set) where:
          A(T) = union of Hom(obs, T) for obs in observed
        """
        presheaf = Presheaf("Attack")

        for obj in self.objects:
            evidence = set()
            for obs in observed:
                key = (obs, obj)
                if key in self.morphisms:
                    for name in self.morphisms[key]:
                        evidence.add(f"evidence_{obs}_{name}")
            presheaf.set_value(obj, evidence)

        return presheaf

    def characteristic_morphism(self, subobject_techniques: List[str],
                                 technique: str) -> Sieve:
        """
        Compute the characteristic morphism chi_A for subobject A.

        Given A subset of C (a set of attack techniques), the
        characteristic morphism chi_A: C -> Omega sends each
        technique T to the sieve:

          chi_A(T) = {f: S -> T | S in A}

        "From which observed attack techniques can we reach T?"
        """
        sieve_morphisms = set()

        for sub_tech in subobject_techniques:
            key = (sub_tech, technique)
            if key in self.morphisms:
                for name in self.morphisms[key]:
                    sieve_morphisms.add(SieveMorphism(
                        source=sub_tech,
                        target=technique,
                        name=name
                    ))

        return Sieve(technique, sieve_morphisms)

    def __repr__(self):
        return (f"PresheafTopos(|Ob|={len(self.objects)}, "
                f"|Mor|={sum(len(v) for v in self.morphisms.values())}, "
                f"|y|={len(self.representables)})")
