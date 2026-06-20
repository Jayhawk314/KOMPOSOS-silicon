# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Emergent Axiom Discovery — ZFC learns principles from System 3 episodes.

When the same inference pattern consistently gets AGREE verdicts from the
Dual Engine, that pattern becomes an emergent axiom. The system literally
builds its own mathematical foundation from experience.

The mechanism mirrors OPTIMUS:
  OPTIMUS: weak A→C, discovers A→B→C is better → materializes B as primitive
  AxiomMiner: R(a,b)∧R(b,c)→R(a,c) gets 47 AGREE verdicts → promotes to axiom

Usage:
    miner = AxiomMiner(system3_oracle)
    axioms = miner.discover_axioms(min_support=30, min_confidence=0.8)

    # Inject evolved axioms into ZFC Theory
    from zfc.logic import Theory
    evolved_theory = Theory("EvolvedAxioms", axioms=axioms.formulas)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from .meta_kan import (
    DeltaType, Episode, Resolution, System3Oracle,
)
from .logic import Formula, Theory, var, const, conj, implies, forall, atom
from .universe import Universe


@dataclass
class AxiomPattern:
    """
    A discovered inference pattern from episode history.

    E.g., "transitive_closure": R(a,b) ∧ R(b,c) → R(a,c)
    """
    name: str                          # e.g., "transitive_closure"
    description: str                   # human-readable description
    template: str                      # e.g., "R(a,b) ∧ R(b,c) → R(a,c)"
    support: int                       # number of episodes matching this pattern
    agree_rate: float                  # fraction of matches that got AGREE verdict
    avg_confidence: float              # average confidence of matching episodes
    domains: List[str]                 # domains where pattern appears
    example_episodes: List[str]        # episode IDs as examples


@dataclass
class DiscoveredAxioms:
    """Collection of axioms discovered from episode history."""
    axioms: List[AxiomPattern]
    formulas: List[Formula]            # ZFC Formula objects for each axiom
    discovery_stats: Dict[str, Any]

    def __repr__(self):
        return (f"DiscoveredAxioms({len(self.axioms)} axioms, "
                f"from {self.discovery_stats.get('total_episodes', 0)} episodes)")


class AxiomMiner:
    """
    Discovers emergent axioms from System 3 episode history.

    The process:
    1. Cluster episodes by reasoning pattern
    2. For each cluster, compute the AGREE rate
    3. If AGREE rate exceeds threshold, synthesize an axiom
    4. Convert axiom patterns into ZFC Formula objects

    This is the ZFC parallel to OPTIMUS:
    - OPTIMUS discovers intermediate concepts (structural)
    - AxiomMiner discovers inference principles (logical)
    """

    def __init__(
        self,
        system3_oracle: System3Oracle,
        category=None,
    ):
        """
        Args:
            system3_oracle: The System3Oracle with episode history.
            category: Optional Category for domain inference.
        """
        self.system3 = system3_oracle
        self.category = category
        self._discovered: Optional[DiscoveredAxioms] = None

    def discover_axioms(
        self,
        min_support: int = 10,
        min_agree_rate: float = 0.8,
        min_confidence: float = 0.5,
    ) -> DiscoveredAxioms:
        """
        Discover axioms from episode history.

        Args:
            min_support: Minimum number of episodes matching a pattern.
            min_agree_rate: Minimum fraction of AGREE verdicts.
            min_confidence: Minimum average confidence.

        Returns:
            DiscoveredAxioms with axiom patterns and ZFC formulas.
        """
        episodes = list(self.system3.history._resolved.values())
        all_episodes = episodes + list(self.system3.history._unresolved.values())

        if not all_episodes:
            return DiscoveredAxioms(
                axioms=[], formulas=[],
                discovery_stats={"total_episodes": 0},
            )

        # Step 1: Cluster episodes by reasoning pattern
        clusters = self._cluster_by_pattern(all_episodes)

        # Step 2: Evaluate each cluster
        candidates = []
        for pattern_name, cluster in clusters.items():
            stats = self._evaluate_cluster(pattern_name, cluster)
            if (stats["support"] >= min_support and
                stats["agree_rate"] >= min_agree_rate and
                stats["avg_confidence"] >= min_confidence):
                candidates.append(stats)

        # Step 3: Synthesize axioms from candidates
        axiom_patterns = []
        formulas = []
        for cand in candidates:
            pattern = self._synthesize_axiom(cand)
            axiom_patterns.append(pattern)
            formula = self._axiom_to_formula(pattern)
            if formula:
                formulas.append(formula)

        self._discovered = DiscoveredAxioms(
            axioms=axiom_patterns,
            formulas=formulas,
            discovery_stats={
                "total_episodes": len(all_episodes),
                "resolved_episodes": len(episodes),
                "clusters_found": len(clusters),
                "candidates": len(candidates),
                "axioms_discovered": len(axiom_patterns),
            },
        )
        return self._discovered

    # ----------------------------------------------------------------
    # Step 1: Cluster episodes by reasoning pattern
    # ----------------------------------------------------------------

    def _cluster_by_pattern(
        self, episodes: List[Episode]
    ) -> Dict[str, List[Episode]]:
        """
        Group episodes by their reasoning pattern.

        Patterns detected:
        - "transitive_closure": source→X→target path found, claim verified
        - "symmetry": claim A→R verified, then R→A also verified
        - "identity": A→A self-relation claims
        - "kan_extension": predicted from similar objects
        - "fibration_lift": lifted from type-level pattern
        - "composition": chain of morphisms supports claim
        """
        clusters: Dict[str, List[Episode]] = defaultdict(list)

        for ep in episodes:
            pattern = self._classify_episode_pattern(ep)
            clusters[pattern].append(ep)

        return clusters

    def _classify_episode_pattern(self, ep: Episode) -> str:
        """Classify an episode into a reasoning pattern."""
        # Transitive closure: paths found between source and target
        if ep.cat_path_count > 0:
            if ep.delta_type == DeltaType.AGREE:
                return "transitive_closure"
            else:
                return "transitive_disputed"

        # Direct edge verification
        if ep.cat_confidence > 0.8 and ep.zfc_confidence > 0.8:
            return "direct_edge"

        # High disagreement: one says yes, one says no
        if ep.delta_type == DeltaType.ORPHAN:
            return "logically_forced_structurally_disconnected"
        elif ep.delta_type == DeltaType.HOLLOW:
            return "structurally_plausible_logically_unfounded"

        # Low confidence on both sides
        if ep.cat_confidence < 0.3 and ep.zfc_confidence < 0.3:
            return "unknown"

        return f"mixed_{ep.delta_type.name.lower()}"

    # ----------------------------------------------------------------
    # Step 2: Evaluate each cluster
    # ----------------------------------------------------------------

    def _evaluate_cluster(
        self, pattern_name: str, cluster: List[Episode]
    ) -> Dict[str, Any]:
        """Compute statistics for a pattern cluster."""
        agree_count = sum(
            1 for ep in cluster if ep.delta_type == DeltaType.AGREE
        )
        total = len(cluster)
        agree_rate = agree_count / total if total > 0 else 0.0

        avg_confidence = sum(
            (ep.cat_confidence + ep.zfc_confidence) / 2 for ep in cluster
        ) / total if total > 0 else 0.0

        domains = list(set(ep.domain for ep in cluster if ep.domain))
        example_ids = [ep.id for ep in cluster[:5]]

        # Detect common relations
        relations = defaultdict(int)
        for ep in cluster:
            relations[ep.relation] += 1
        top_relations = sorted(relations.items(), key=lambda x: -x[1])[:3]

        return {
            "pattern_name": pattern_name,
            "support": total,
            "agree_count": agree_count,
            "agree_rate": agree_rate,
            "avg_confidence": avg_confidence,
            "domains": domains,
            "example_episodes": example_ids,
            "top_relations": top_relations,
            "episodes": cluster,
        }

    # ----------------------------------------------------------------
    # Step 3: Synthesize axioms
    # ----------------------------------------------------------------

    def _synthesize_axiom(self, stats: Dict[str, Any]) -> AxiomPattern:
        """Create an AxiomPattern from cluster statistics."""
        pattern_name = stats["pattern_name"]

        templates = {
            "transitive_closure": "∀a,b,c. R(a,b) ∧ R(b,c) → R(a,c)",
            "direct_edge": "∀a,b. edge(a,b) → verified(a,b)",
            "logically_forced_structurally_disconnected":
                "∀a,b. zfc_proves(a,b) ∧ ¬cat_supports(a,b) → missing_bridge(a,b)",
            "structurally_plausible_logically_unfounded":
                "∀a,b. cat_supports(a,b) ∧ ¬zfc_proves(a,b) → needs_axiom(a,b)",
            "transitive_disputed": "∀a,b,c. R(a,b) ∧ R(b,c) ↛ R(a,c) [domain-dependent]",
        }

        descriptions = {
            "transitive_closure": (
                f"Transitive closure: when R(a,b) and R(b,c) both hold, "
                f"R(a,c) follows. Verified {stats['agree_count']}/{stats['support']} times "
                f"({stats['agree_rate']:.0%} agreement, avg conf={stats['avg_confidence']:.2f})."
            ),
            "direct_edge": (
                f"Direct edge verification: when a direct edge exists, "
                f"claims are verified by both engines. "
                f"({stats['agree_rate']:.0%} agreement)."
            ),
            "logically_forced_structurally_disconnected": (
                f"ZFC proves claims that CAT doesn't structurally support. "
                f"Missing structural bridge detected {stats['support']} times."
            ),
            "structurally_plausible_logically_unfounded": (
                f"CAT finds structural support that ZFC can't prove. "
                f"New axiom needed. Detected {stats['support']} times."
            ),
            "transitive_disputed": (
                f"Transitive closure is domain-dependent. "
                f"Disputed in {stats['support']} cases. "
                f"May need domain-specific transitivity axioms."
            ),
        }

        return AxiomPattern(
            name=pattern_name,
            description=descriptions.get(pattern_name, pattern_name),
            template=templates.get(pattern_name, "Unknown pattern"),
            support=stats["support"],
            agree_rate=stats["agree_rate"],
            avg_confidence=stats["avg_confidence"],
            domains=stats["domains"],
            example_episodes=stats["example_episodes"],
        )

    # ----------------------------------------------------------------
    # Step 4: Convert to ZFC Formulas
    # ----------------------------------------------------------------

    def _axiom_to_formula(self, pattern: AxiomPattern) -> Optional[Formula]:
        """
        Convert an AxiomPattern into a ZFC Formula.

        For transitive closure: ∀a,b,c. R(a,b) ∧ R(b,c) → R(a,c)
        """
        if pattern.name == "transitive_closure":
            # ∀a,b,c. R(a,b) ∧ R(b,c) → R(a,c)
            a, b, c = var("a"), var("b"), var("c")
            R = "R"  # generic relation
            antecedent = conj(atom(R, a, b), atom(R, b, c))
            consequent = atom(R, a, c)
            return forall(c, implies(antecedent, consequent))

        elif pattern.name == "direct_edge":
            # ∀a,b. edge(a,b) → verified(a,b)
            a, b = var("a"), var("b")
            return forall(b, implies(atom("edge", a, b), atom("verified", a, b)))

        elif pattern.name == "logically_forced_structurally_disconnected":
            # ∀a,b. zfc_proves(a,b) → cat_supports(a,b) ∨ missing_bridge(a,b)
            a, b = var("a"), var("b")
            antecedent = atom("zfc_proves", a, b)
            consequent = atom("cat_supports", a, b)
            # This is a conditional: if ZFC proves but CAT doesn't support,
            # there's a missing bridge
            return forall(b, implies(antecedent, consequent))

        return None

    # ----------------------------------------------------------------
    # Integration: inject evolved axioms into ZFC Theory
    # ----------------------------------------------------------------

    def inject_into_theory(self, theory: Theory) -> Theory:
        """
        Add discovered axioms to an existing ZFC Theory.

        Args:
            theory: The existing ZFC Theory.

        Returns:
            New Theory with evolved axioms added.
        """
        if self._discovered is None:
            self.discover_axioms()

        new_axioms = list(theory.axioms) + self._discovered.formulas
        return Theory(
            name=f"{theory.name}+evolved",
            axioms=new_axioms,
        )

    def inject_into_universe(self, universe: Universe) -> Universe:
        """
        Add discovered axioms as relations in the ZFC Universe.

        Args:
            universe: The existing ZFC Universe.

        Returns:
            Universe with evolved axiom relations added.
        """
        if self._discovered is None:
            self.discover_axioms()

        for axiom in self._discovered.axioms:
            universe.add_relation(
                f"axiom_{axiom.name}",
                [(f"pattern_{i}", f"axiom_{axiom.name}")
                 for i in range(axiom.support)],
            )

        return universe

    def report(self) -> str:
        """Generate a report on discovered axioms."""
        if self._discovered is None:
            return "No axioms discovered yet. Call discover_axioms() first."

        lines = [
            f"Emergent Axiom Discovery Report",
            f"{'=' * 50}",
            f"Total episodes analyzed: {self._discovered.discovery_stats['total_episodes']}",
            f"Resolved episodes: {self._discovered.discovery_stats.get('resolved_episodes', 0)}",
            f"Pattern clusters found: {self._discovered.discovery_stats['clusters_found']}",
            f"Strong candidates: {self._discovered.discovery_stats['candidates']}",
            f"Axioms discovered: {self._discovered.discovery_stats['axioms_discovered']}",
            f"",
        ]

        for axiom in self._discovered.axioms:
            lines.append(f"Axiom: {axiom.name}")
            lines.append(f"  Template: {axiom.template}")
            lines.append(f"  Support: {axiom.support} episodes")
            lines.append(f"  Agreement rate: {axiom.agree_rate:.0%}")
            lines.append(f"  Avg confidence: {axiom.avg_confidence:.2f}")
            lines.append(f"  Domains: {', '.join(axiom.domains) if axiom.domains else 'all'}")
            lines.append(f"  Description: {axiom.description}")
            lines.append(f"")

        return "\n".join(lines)
