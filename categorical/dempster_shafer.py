# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
Dempster-Shafer Theory of Evidence

Implements belief functions and Dempster's combination rule for
multi-source evidence fusion under uncertainty.

Key concepts:
- MassFunction (Basic Probability Assignment): distributes belief
  mass over subsets of hypotheses, including the full frame (total ignorance).
- Belief: lower bound on probability of a hypothesis.
- Plausibility: upper bound on probability of a hypothesis.
- Uncertainty interval: [Belief, Plausibility] brackets the true probability.

Advantages over Bayesian:
- Distinguishes "no evidence" (mass on full frame) from
  "contradictory evidence" (high conflict degree).
- Does not require prior probabilities.
- Sources can be weighted by reliability via discounting.

References:
- Dempster (1967): Upper and lower probabilities induced by a multivalued mapping
- Shafer (1976): A Mathematical Theory of Evidence
"""

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Set, Tuple


@dataclass
class MassFunction:
    """
    Basic Probability Assignment (BPA).

    Distributes belief mass over subsets of hypotheses.
    masses[frozenset()] is always 0 (no mass on empty set).
    masses[full_frame] represents total ignorance for that mass.
    """
    masses: Dict[FrozenSet[str], float] = field(default_factory=dict)

    def __post_init__(self):
        # Remove empty set if present
        self.masses.pop(frozenset(), None)
        # Normalize
        total = sum(self.masses.values())
        if total > 0 and abs(total - 1.0) > 1e-9:
            self.masses = {k: v / total for k, v in self.masses.items()}

    @property
    def frame(self) -> FrozenSet[str]:
        """The frame of discernment (union of all hypotheses)."""
        all_elements: Set[str] = set()
        for key in self.masses:
            all_elements.update(key)
        return frozenset(all_elements)

    @property
    def focal_elements(self) -> List[FrozenSet[str]]:
        """Subsets with non-zero mass."""
        return [k for k, v in self.masses.items() if v > 0]

    def belief(self, hypothesis: FrozenSet[str]) -> float:
        """
        Belief in a hypothesis: sum of masses of all subsets of hypothesis.

        Bel(A) = sum_{B subseteq A} m(B)

        This is the lower bound on the probability of the hypothesis.
        """
        total = 0.0
        for focal, mass in self.masses.items():
            if focal <= hypothesis:  # focal is subset of hypothesis
                total += mass
        return total

    def plausibility(self, hypothesis: FrozenSet[str]) -> float:
        """
        Plausibility of a hypothesis: sum of masses of sets intersecting hypothesis.

        Pl(A) = sum_{B cap A != empty} m(B)

        This is the upper bound on the probability of the hypothesis.
        """
        total = 0.0
        for focal, mass in self.masses.items():
            if focal & hypothesis:  # non-empty intersection
                total += mass
        return total

    def uncertainty(self, hypothesis: FrozenSet[str]) -> float:
        """
        Uncertainty interval width: Plausibility - Belief.

        Large uncertainty = insufficient evidence.
        Small uncertainty = strong evidence (for or against).
        """
        return self.plausibility(hypothesis) - self.belief(hypothesis)

    def pignistic_probability(self, hypothesis_element: str) -> float:
        """
        Pignistic (betting) probability for a single hypothesis element.

        BetP(x) = sum_{A: x in A} m(A) / |A|

        Converts BPA to point probability for decision-making.
        """
        total = 0.0
        for focal, mass in self.masses.items():
            if hypothesis_element in focal and len(focal) > 0:
                total += mass / len(focal)
        return total


def combine(m1: MassFunction, m2: MassFunction) -> Tuple[MassFunction, float]:
    """
    Dempster's combination rule for two independent evidence sources.

    Computes the orthogonal sum of two mass functions, normalized by
    the conflict factor K. The conflict degree measures how much the
    two sources disagree.

    Args:
        m1: First mass function
        m2: Second mass function

    Returns:
        Tuple of (combined MassFunction, conflict_degree).
        conflict_degree in [0, 1): 0 = no conflict, approaching 1 = high conflict.

    Raises:
        ValueError: If conflict is 1.0 (total contradiction).
    """
    combined_masses: Dict[FrozenSet[str], float] = {}
    conflict = 0.0

    for a, m_a in m1.masses.items():
        for b, m_b in m2.masses.items():
            intersection = a & b
            product = m_a * m_b

            if not intersection:
                # Conflicting evidence
                conflict += product
            else:
                combined_masses[intersection] = (
                    combined_masses.get(intersection, 0.0) + product
                )

    if abs(conflict - 1.0) < 1e-12:
        raise ValueError(
            "Total conflict between evidence sources (K=1). "
            "The sources are completely contradictory."
        )

    # Normalize by (1 - conflict)
    normalization = 1.0 - conflict
    normalized: Dict[FrozenSet[str], float] = {
        k: v / normalization for k, v in combined_masses.items() if v > 0
    }

    return MassFunction(masses=normalized), conflict


def weighted_combine(
    masses: List[Tuple[MassFunction, float]]
) -> MassFunction:
    """
    Combine multiple evidence sources with reliability weights.

    Each source is first discounted by its reliability weight,
    then combined using Dempster's rule.

    Args:
        masses: List of (MassFunction, reliability_weight) pairs.
                reliability_weight in [0, 1]: 1 = fully reliable, 0 = ignore.

    Returns:
        Combined MassFunction after discounting and combination.
    """
    if not masses:
        return MassFunction(masses={})

    # Discount each source by its reliability
    discounted = [discount(m, w) for m, w in masses]

    # Combine sequentially
    result = discounted[0]
    for m in discounted[1:]:
        result, _ = combine(result, m)

    return result


def discount(m: MassFunction, reliability: float) -> MassFunction:
    """
    Discount a mass function by source reliability.

    Unreliable sources transfer mass to the full frame (ignorance).

    discounted(A) = reliability * m(A)  for A != Theta
    discounted(Theta) = reliability * m(Theta) + (1 - reliability)

    Args:
        m: Original mass function
        reliability: Source reliability in [0, 1].
                     1.0 = fully reliable (no change).
                     0.0 = completely unreliable (all mass to ignorance).

    Returns:
        Discounted MassFunction.
    """
    reliability = max(0.0, min(1.0, reliability))
    frame = m.frame

    new_masses: Dict[FrozenSet[str], float] = {}
    for focal, mass in m.masses.items():
        if focal == frame:
            # Frame gets discounted mass plus unreliability portion
            new_masses[focal] = reliability * mass + (1.0 - reliability)
        else:
            new_masses[focal] = reliability * mass

    # If frame wasn't a focal element, add the unreliability mass
    if frame not in new_masses and frame:
        new_masses[frame] = 1.0 - reliability

    # Remove zero masses
    new_masses = {k: v for k, v in new_masses.items() if v > 1e-12}

    return MassFunction(masses=new_masses)
