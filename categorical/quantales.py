# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Domain-Agnostic Quantale Definitions

Generic quantale types for enriched categories. A domain schema maps
domain concepts to quantale types:

  Fraud:       flow=ADDITIVE, confidence=MULTIPLICATIVE
  Engineering: stress=MAX, cost=ADDITIVE
  Cyber:       stealth=MULTIPLICATIVE, risk=PROBABILISTIC
  Fusion:      performance=MULTIPLICATIVE, cost=ADDITIVE

Each quantale is a complete lattice with an associative binary operation,
serving as the enrichment base for a V-enriched category.

Mathematical basis:
  - Lawvere, "Metric spaces, generalized logic, and closed categories" (1973)
  - Fong & Spivak, "Seven Sketches in Compositionality", Def 2.46
"""

from categorical.enriched_category import MonoidalStructure


# ===================================================================
# GENERIC QUANTALE TYPES
# ===================================================================

MULTIPLICATIVE_QUANTALE = MonoidalStructure(
    tensor=lambda a, b: a * b,
    unit=1.0,
    compare=lambda a, b: a >= b,  # Higher is "better"
    name="Multiplicative([0,1], x, 1)"
)
"""Product composition. Used for: stealth, confidence, affinity, success.
   Path weight = product of edge weights. Higher = better."""

ADDITIVE_QUANTALE = MonoidalStructure(
    tensor=lambda a, b: a + b,
    unit=0.0,
    compare=lambda a, b: a <= b,  # Lower is "better"
    name="Additive([0,inf], +, 0)"
)
"""Sum composition. Used for: cost, distance, latency, toxicity.
   Path weight = sum of edge weights. Lower = better."""

PROBABILISTIC_QUANTALE = MonoidalStructure(
    tensor=lambda a, b: 1 - (1 - a) * (1 - b),  # P(A or B)
    unit=0.0,
    compare=lambda a, b: a <= b,  # Lower risk is "better"
    name="Probabilistic([0,1], P-OR, 0)"
)
"""Probabilistic OR composition. Used for: risk, failure probability.
   Path weight = P(at least one event). Lower = better."""

MAX_QUANTALE = MonoidalStructure(
    tensor=lambda a, b: max(a, b),
    unit=0.0,
    compare=lambda a, b: a <= b,  # Lower max is "better"
    name="Max([0,inf], max, 0)"
)
"""Max composition. Used for: peak stress, maximum load, bottleneck.
   Path weight = maximum edge weight along path. Lower = better."""

MIN_QUANTALE = MonoidalStructure(
    tensor=lambda a, b: min(a, b),
    unit=1.0,
    compare=lambda a, b: a >= b,  # Higher min is "better"
    name="Min([0,1], min, 1)"
)
"""Min (bottleneck) composition. Used for: throughput, capacity, activity.
   Path weight = minimum edge weight (weakest link). Higher = better."""


# ===================================================================
# QUANTALE REGISTRY
# ===================================================================

QUANTALE_REGISTRY = {
    "multiplicative": MULTIPLICATIVE_QUANTALE,
    "additive": ADDITIVE_QUANTALE,
    "probabilistic": PROBABILISTIC_QUANTALE,
    "max": MAX_QUANTALE,
    "min": MIN_QUANTALE,
}


def get_quantale(quantale_type: str) -> MonoidalStructure:
    """
    Look up a quantale by type name.

    Args:
        quantale_type: One of "multiplicative", "additive", "probabilistic",
                       "max", "min"

    Returns:
        MonoidalStructure for the requested quantale type.

    Raises:
        KeyError: If quantale_type is not recognized.
    """
    if quantale_type not in QUANTALE_REGISTRY:
        raise KeyError(
            f"Unknown quantale type: {quantale_type!r}. "
            f"Valid types: {', '.join(QUANTALE_REGISTRY.keys())}"
        )
    return QUANTALE_REGISTRY[quantale_type]
