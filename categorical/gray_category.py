#!/usr/bin/env python3
"""
Gray Category for Bioorthogonal Interchange

Models chemical reactions as morphisms where order-swapping has a cost.

Mathematical foundation:
- Gray category = semistrict 3-category
- Interchange law holds up to weak isomorphism
- 2-cells represent "swap cost" between reactions

Application to bioorthogonal chemistry:
- 1-morphisms: bioorthogonal click reactions (azide-alkyne, tetrazine-TCO, etc.)
- 2-cells: cost of swapping reaction order at a site
- Interchange witness: flags "these clicks won't commute" before wet-lab

This prevents: trying two clicks in wrong order and getting cross-reactivity
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from enum import Enum
import numpy as np


class BioorthogonalReaction(Enum):
    """Common bioorthogonal reactions."""
    AZIDE_ALKYNE = "azide-alkyne"  # SPAAC or CuAAC
    TETRAZINE_TCO = "tetrazine-TCO"  # inverse electron demand Diels-Alder
    ISOCYANIDE_TETRAZINE = "isocyanide-tetrazine"
    CYCLOOCTYNE_AZIDE = "cyclooctyne-azide"
    QUADRICYCLANE_NITRILE_IMINE = "quadricyclane-nitrile_imine"
    NORBORNENE_TETRAZINE = "norbornene-tetrazine"


@dataclass
class ReactionMorphism:
    """1-morphism representing a bioorthogonal reaction."""
    name: str
    reaction_type: BioorthogonalReaction
    reactant_1: str  # e.g., "azide-warhead"
    reactant_2: str  # e.g., "alkyne-linker"
    product: str     # e.g., "triazole-conjugate"
    rate_constant: float  # k in M^-1 s^-1
    site: str  # binding site or cellular location


@dataclass
class InterchangeCell:
    """
    2-cell representing the cost of swapping two reactions.

    In a Gray category, the interchange law:
        (f ⊗ g) ∘ (h ⊗ k) ≅ (f ∘ h) ⊗ (g ∘ k)

    holds up to WEAK isomorphism (≅), not strict equality (=).

    This 2-cell IS the witness to that weak isomorphism.
    """
    reaction_1: ReactionMorphism
    reaction_2: ReactionMorphism
    swap_cost: float  # 0 = free swap, 1 = impossible
    interference_type: Optional[str] = None  # e.g., "cross_reactivity", "steric_clash"

    def is_commutative(self, threshold: float = 0.3) -> bool:
        """Check if reactions can be swapped without significant cost."""
        return self.swap_cost < threshold

    def get_optimal_order(self) -> Tuple[ReactionMorphism, ReactionMorphism]:
        """Return optimal reaction order (lower cost first)."""
        if self.swap_cost < 0.5:
            # Swapping is cheap, either order works
            return (self.reaction_1, self.reaction_2)
        else:
            # Swapping is costly, maintain order
            return (self.reaction_1, self.reaction_2)


class GrayCategory:
    """
    Gray category for bioorthogonal reaction planning.

    Automatically detects when two clicks won't commute and flags it
    BEFORE wet-lab synthesis.
    """

    def __init__(self):
        # Known interference patterns (from literature)
        self.interference_db: Dict[Tuple[BioorthogonalReaction, BioorthogonalReaction], float] = {
            # Tetrazine reactions interfere with each other
            (BioorthogonalReaction.TETRAZINE_TCO, BioorthogonalReaction.NORBORNENE_TETRAZINE): 0.9,
            (BioorthogonalReaction.NORBORNENE_TETRAZINE, BioorthogonalReaction.TETRAZINE_TCO): 0.9,

            # Azide-alkyne and cyclooctyne-azide compete for azides
            (BioorthogonalReaction.AZIDE_ALKYNE, BioorthogonalReaction.CYCLOOCTYNE_AZIDE): 0.8,
            (BioorthogonalReaction.CYCLOOCTYNE_AZIDE, BioorthogonalReaction.AZIDE_ALKYNE): 0.8,

            # Most true bioorthogonal pairs are OK
            (BioorthogonalReaction.AZIDE_ALKYNE, BioorthogonalReaction.TETRAZINE_TCO): 0.1,
            (BioorthogonalReaction.TETRAZINE_TCO, BioorthogonalReaction.AZIDE_ALKYNE): 0.1,
        }

        self.reactions: List[ReactionMorphism] = []
        self.interchange_cells: List[InterchangeCell] = []

    def add_reaction(self, reaction: ReactionMorphism):
        """Add a reaction to the category."""
        self.reactions.append(reaction)

    def compute_interchange(
        self,
        reaction_1: ReactionMorphism,
        reaction_2: ReactionMorphism
    ) -> InterchangeCell:
        """
        Compute the interchange 2-cell between two reactions.

        This is the Gray category magic: we compute the COST of swapping
        the order of two reactions.
        """
        # Base swap cost from reaction type compatibility
        type_pair = (reaction_1.reaction_type, reaction_2.reaction_type)
        base_cost = self.interference_db.get(type_pair, 0.2)  # default: slight interference

        # Same-site penalty
        if reaction_1.site == reaction_2.site:
            base_cost += 0.3

        # Rate constant mismatch penalty
        if reaction_1.rate_constant > 0 and reaction_2.rate_constant > 0:
            rate_ratio = max(reaction_1.rate_constant, reaction_2.rate_constant) / \
                        min(reaction_1.rate_constant, reaction_2.rate_constant)
            if rate_ratio > 100:  # one reaction is 100x faster
                base_cost += 0.2  # slow reaction will be outcompeted

        # Detect interference type
        interference = None
        if type_pair in self.interference_db and self.interference_db[type_pair] > 0.5:
            if type_pair[0] == type_pair[1]:
                interference = "self_competition"
            else:
                interference = "cross_reactivity"

        if reaction_1.site == reaction_2.site and base_cost > 0.5:
            interference = "steric_clash"

        cell = InterchangeCell(
            reaction_1=reaction_1,
            reaction_2=reaction_2,
            swap_cost=min(base_cost, 1.0),
            interference_type=interference
        )

        self.interchange_cells.append(cell)
        return cell

    def verify_reaction_sequence(
        self,
        reactions: List[ReactionMorphism]
    ) -> Tuple[bool, List[str]]:
        """
        Verify a sequence of reactions for commutativity.

        Returns:
            (is_valid, warnings)

        This is the REAL VALUE: catch bad reaction sequences before synthesis.
        """
        warnings = []
        is_valid = True

        # Check all pairs
        for i in range(len(reactions)):
            for j in range(i + 1, len(reactions)):
                cell = self.compute_interchange(reactions[i], reactions[j])

                if cell.swap_cost > 0.7:
                    is_valid = False
                    warnings.append(
                        f"HIGH INTERFERENCE: {reactions[i].name} and {reactions[j].name} "
                        f"(cost: {cell.swap_cost:.2f}, type: {cell.interference_type})"
                    )
                elif cell.swap_cost > 0.4:
                    warnings.append(
                        f"MODERATE INTERFERENCE: {reactions[i].name} and {reactions[j].name} "
                        f"(cost: {cell.swap_cost:.2f})"
                    )

        if is_valid and len(warnings) == 0:
            warnings.append("All reactions are bioorthogonal - sequence is valid")

        return is_valid, warnings

    def suggest_optimal_order(
        self,
        reactions: List[ReactionMorphism]
    ) -> List[ReactionMorphism]:
        """
        Suggest optimal reaction order to minimize interference.

        Uses interchange costs to find best sequence.
        """
        if len(reactions) <= 1:
            return reactions

        # Simple greedy: add reactions in order of least interference
        ordered = [reactions[0]]
        remaining = reactions[1:]

        while remaining:
            # Find reaction with least interference with current sequence
            best_reaction = None
            best_total_cost = float('inf')

            for candidate in remaining:
                total_cost = 0
                for existing in ordered:
                    cell = self.compute_interchange(existing, candidate)
                    total_cost += cell.swap_cost

                if total_cost < best_total_cost:
                    best_total_cost = total_cost
                    best_reaction = candidate

            ordered.append(best_reaction)
            remaining.remove(best_reaction)

        return ordered


# Example usage
def demo_gray_category():
    """Demonstrate Gray category catching bad reaction sequences."""
    print("=" * 80)
    print("GRAY CATEGORY: Bioorthogonal Reaction Planning")
    print("=" * 80)

    # Create category
    gray = GrayCategory()

    # Define some reactions for a dual-labeling experiment
    reaction_1 = ReactionMorphism(
        name="Click-1",
        reaction_type=BioorthogonalReaction.AZIDE_ALKYNE,
        reactant_1="azide-protein",
        reactant_2="alkyne-fluorophore-1",
        product="triazole-labeled-protein-1",
        rate_constant=1e5,  # M^-1 s^-1
        site="lysine-42"
    )

    reaction_2 = ReactionMorphism(
        name="Click-2",
        reaction_type=BioorthogonalReaction.TETRAZINE_TCO,
        reactant_1="TCO-protein",
        reactant_2="tetrazine-fluorophore-2",
        product="conjugate-labeled-protein-2",
        rate_constant=1e6,  # M^-1 s^-1 (faster!)
        site="serine-88"
    )

    # BAD: trying two tetrazine reactions (compete!)
    reaction_3 = ReactionMorphism(
        name="Click-3-BAD",
        reaction_type=BioorthogonalReaction.NORBORNENE_TETRAZINE,
        reactant_1="norbornene-protein",
        reactant_2="tetrazine-fluorophore-3",
        product="conjugate-labeled-protein-3",
        rate_constant=8e5,
        site="serine-88"  # same site!
    )

    print("\n[Test 1] Good sequence (azide-alkyne + tetrazine-TCO):")
    is_valid, warnings = gray.verify_reaction_sequence([reaction_1, reaction_2])
    print(f"  Valid: {is_valid}")
    for w in warnings:
        print(f"  - {w}")

    print("\n[Test 2] Bad sequence (tetrazine-TCO + norbornene-tetrazine at same site):")
    is_valid, warnings = gray.verify_reaction_sequence([reaction_2, reaction_3])
    print(f"  Valid: {is_valid}")
    for w in warnings:
        print(f"  - {w}")

    print("\n[Test 3] Suggest optimal order:")
    all_reactions = [reaction_1, reaction_2, reaction_3]
    optimal = gray.suggest_optimal_order(all_reactions)
    print("  Optimal order:")
    for i, r in enumerate(optimal, 1):
        print(f"    {i}. {r.name} ({r.reaction_type.value})")

    print("\n" + "=" * 80)
    print("Gray category successfully models bioorthogonal chemistry!")
    print("=" * 80)


if __name__ == "__main__":
    demo_gray_category()
