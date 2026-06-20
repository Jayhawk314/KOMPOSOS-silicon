# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Enrichment Layer: Monoidal Structures and Quantales

A V-enriched category replaces hom-SETS with hom-OBJECTS in V:
  - Hom(A,B) in V instead of Hom(A,B) in Set
  - Composition is a V-morphism: Hom(B,C) tensor Hom(A,B) -> Hom(A,C)
  - Identity is a V-morphism: I -> Hom(A,A)

In KOMPOSOS-IV, enrichment is intrinsic to morphisms. The quantale
defines how confidence scores compose.

Mathematical basis:
  - Lawvere, "Metric spaces, generalized logic, and closed categories" (1973)
  - Fong & Spivak, "Seven Sketches in Compositionality", Def 2.46
"""

from typing import TypeVar, Generic, Callable, Any, Dict
from dataclasses import dataclass

V = TypeVar('V')


@dataclass
class MonoidalStructure(Generic[V]):
    """
    Defines (V, tensor, I) -- the monoidal category we enrich over.

    For a quantale (complete lattice with associative binary operation):
      tensor: V x V -> V (the tensor operation, must be associative)
      unit: V            (identity for tensor: I tensor a = a = a tensor I)
      compare: V x V -> bool (the ordering for enrichment axioms)

    Examples:
      Multiplicative: ([0,1], x, 1, >=)  -- product, higher is better
      Additive:       ([0,inf], +, 0, <=) -- sum, lower is better
      Probabilistic:  ([0,1], P-OR, 0, <=) -- probability, lower is better
    """
    tensor: Callable[[Any, Any], Any]
    unit: Any
    compare: Callable[[Any, Any], bool]
    name: str = "V"


# ===================================================================
# Pre-built quantales
# ===================================================================

MULTIPLICATIVE_QUANTALE = MonoidalStructure(
    tensor=lambda a, b: a * b,
    unit=1.0,
    compare=lambda a, b: a >= b,  # Higher is "better"
    name="Multiplicative([0,1], x, 1)"
)
"""Product composition. Used for: confidence, affinity, success probability.
   Path weight = product of edge weights. Higher = better."""

ADDITIVE_QUANTALE = MonoidalStructure(
    tensor=lambda a, b: a + b,
    unit=0.0,
    compare=lambda a, b: a <= b,  # Lower is "better"
    name="Additive([0,inf], +, 0)"
)
"""Sum composition. Used for: cost, distance, latency.
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
"""Max composition. Used for: peak stress, bottleneck capacity.
   Path weight = maximum edge weight along path. Lower = better."""

MIN_QUANTALE = MonoidalStructure(
    tensor=lambda a, b: min(a, b),
    unit=1.0,
    compare=lambda a, b: a >= b,  # Higher min is "better"
    name="Min([0,1], min, 1)"
)
"""Min (bottleneck) composition. Used for: throughput, weakest link.
   Path weight = minimum edge weight (weakest link). Higher = better."""


# ===================================================================
# Registry
# ===================================================================

QUANTALE_REGISTRY: Dict[str, MonoidalStructure] = {
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
