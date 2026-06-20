# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Resource Enrichment: Monoids over Operations

The constructive dual of KOMPOSOS-IV's enrichment.py (quantales over
hom-sets). KOMPOSOS enriches morphisms with a confidence in a quantale;
OPERADUM enriches operations with a *resource value* in a monoid.

The single most important difference from KOMPOSOS is non-cartesianness.
KOMPOSOS is cartesian: knowledge is freely copyable (a morphism's
confidence is reused as often as you like). A resource is not. The
`LINEAR_TOKENS` monoid forbids the diagonal -- combining a resource with
itself raises -- so a synthesized design literally cannot spend the same
one-shot resource twice.

Mathematical basis:
  - Symmetric monoidal categories; substructural (linear) logic.
  - A ResourceMonoid is (R, combine, unit) with `combine` associative and
    `unit` a two-sided identity, plus a `compare` partial order used to ask
    "is cost a no worse than budget b?".
"""

from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple

from .types import ResourceValue


class ResourceError(ValueError):
    """Raised when a resource discipline is violated (e.g. linear reuse)."""


@dataclass
class ResourceMonoid:
    """
    Defines (R, combine, unit, compare) -- how a domain's costs accumulate.

    The dual of KOMPOSOS's MonoidalStructure. Where a quantale's `tensor`
    combines two confidences, a ResourceMonoid's `combine` combines two
    resource values along an assembly.

    Fields:
        combine: (R, R) -> R, associative, with `unit` as identity.
        unit:    The cost of building nothing (identity for combine).
        compare: (figures, budget) -> bool. True iff `figures` is within
                 `budget` (i.e. no upper bound is exceeded, pointwise). Used
                 by the RES gate for budget feasibility.
        score:   Optional scalar ranking function. Lower scores are better.
                 If absent, ranking falls back to sum(values), preserving the
                 original "cheapest design" behavior.
        name:    Human-readable label.
    """
    combine: Callable[[ResourceValue, ResourceValue], ResourceValue]
    unit: ResourceValue
    compare: Callable[[ResourceValue, ResourceValue], bool]
    name: str = "R"
    score: Optional[Callable[[ResourceValue], float]] = None
    # True for non-cartesian (spend-once) algebras, where reusing a token is a
    # contraction violation. False for accumulative algebras (additive, max,
    # tropical, multiset), where every resource is freely reusable (a !-resource).
    linear: bool = False

    def total(self, *values: ResourceValue) -> ResourceValue:
        """Fold `combine` over many values starting from `unit`."""
        acc = dict(self.unit)
        for v in values:
            acc = self.combine(acc, v)
        return acc

    def rank(self, value: ResourceValue) -> float:
        """Scalar rank for search ordering. Lower is better."""
        if self.score is not None:
            return self.score(value)
        return _scalar_sum(value)


# ===================================================================
# Helpers
# ===================================================================

def _merge(a: ResourceValue, b: ResourceValue, op: Callable[[float, float], float],
           default: float = 0.0) -> ResourceValue:
    """Per-key merge of two resource bags using `op`, filling missing keys."""
    out: Dict[str, Any] = dict(a)
    for k, v in b.items():
        out[k] = op(out.get(k, default), v)
    return out


def _within(cost: ResourceValue, budget: ResourceValue) -> bool:
    """True iff every key in `cost` is <= the budget for that key.

    Keys absent from `budget` are treated as unbounded (allowed). This is the
    pointwise order used for 'is this design in budget?'.
    """
    for k, v in cost.items():
        if k in budget and v > budget[k]:
            return False
    return True


def _meets_minimum(figures: ResourceValue, minimum: ResourceValue) -> bool:
    """True iff every required lower bound is met."""
    for k, v in minimum.items():
        if figures.get(k, 0.0) < v:
            return False
    return True


def _scalar_sum(value: ResourceValue) -> float:
    """Original ranking: sum every numeric component, lower is better."""
    return sum(float(v) for v in value.values()) if value else 0.0


# ===================================================================
# General figure profiles
# ===================================================================

CombinePolicy = str
Direction = str


@dataclass(frozen=True)
class Figure:
    """
    A reusable design figure.

    `combine` says how this figure accumulates through a composite. `direction`
    says how it should be optimized. Lower search scores are always better, so
    a maximized figure contributes a negative weighted value to the score.
    """

    name: str
    combine: CombinePolicy = "sum"       # sum|max|min|product|prob_any
    direction: Direction = "min"         # min|max
    weight: float = 1.0
    description: str = ""

    @property
    def identity(self) -> float:
        if self.combine == "product":
            return 1.0
        if self.combine == "min":
            return float("inf")
        return 0.0


@dataclass(frozen=True)
class FigureProfile:
    """
    A heterogeneous resource algebra: different figures can compose and rank
    differently in the same design.

    This is the general-purpose layer for "not just cost": safety risk can use
    max or probabilistic union, confidence can multiply, evidence can take the
    weakest-link min, memory can use max, and schedule or labor can sum.
    """

    name: str
    figures: Tuple[Figure, ...] = field(default_factory=tuple)
    default_combine: CombinePolicy = "sum"
    default_direction: Direction = "min"
    default_weight: float = 1.0
    include_unlisted_in_score: bool = True

    def __post_init__(self):
        object.__setattr__(self, "_by_name", {f.name: f for f in self.figures})

    def get(self, name: str) -> Figure:
        figure = self._by_name.get(name)
        if figure is not None:
            return figure
        return Figure(
            name=name,
            combine=self.default_combine,
            direction=self.default_direction,
            weight=self.default_weight,
        )

    def combine_values(self, a: ResourceValue, b: ResourceValue) -> ResourceValue:
        out: Dict[str, Any] = {}
        for key in set(a) | set(b):
            figure = self.get(key)
            left = float(a.get(key, figure.identity))
            right = float(b.get(key, figure.identity))
            value = _combine_by_policy(left, right, figure.combine)
            if value != figure.identity or key in a or key in b:
                out[key] = value
        return out

    def score_value(self, value: ResourceValue) -> float:
        score = 0.0
        names: Iterable[str]
        if self.include_unlisted_in_score:
            names = value.keys()
        else:
            names = self._by_name.keys()
        for key in names:
            if key not in value:
                continue
            figure = self.get(key)
            sign = -1.0 if figure.direction == "max" else 1.0
            score += sign * figure.weight * float(value[key])
        return score

    def with_weights(self, name: str, **weights: float) -> "FigureProfile":
        """Return a copy with selected figure weights changed."""
        updated = []
        for figure in self.figures:
            updated.append(
                replace(figure, weight=weights.get(figure.name, figure.weight))
            )
        return replace(self, name=name, figures=tuple(updated))

    def to_monoid(self, name: Optional[str] = None) -> ResourceMonoid:
        return ResourceMonoid(
            combine=self.combine_values,
            unit={},
            compare=_within,
            score=self.score_value,
            name=name or f"FigureProfile({self.name})",
        )


def _combine_by_policy(a: float, b: float, policy: CombinePolicy) -> float:
    if policy == "sum":
        return a + b
    if policy == "max":
        return max(a, b)
    if policy == "min":
        return min(a, b)
    if policy == "product":
        return a * b
    if policy == "prob_any":
        return 1.0 - ((1.0 - a) * (1.0 - b))
    raise ValueError(
        f"Unknown figure combine policy {policy!r}; "
        "valid: sum, max, min, product, prob_any"
    )


GENERAL_FIGURE_PROFILE = FigureProfile(
    name="general",
    figures=(
        Figure("money_usd", "sum", "min", 1.0, "Direct spend."),
        Figure("time_hours", "sum", "min", 1.0, "Elapsed or labor time."),
        Figure("schedule_delay", "sum", "min", 1.0, "Recovery delay."),
        Figure("latency_ms", "sum", "min", 1.0, "End-to-end latency."),
        Figure("memory_mb", "max", "min", 1.0, "Peak memory or capacity."),
        Figure("energy_kwh", "sum", "min", 1.0, "Energy use."),
        Figure("emissions_kgco2e", "sum", "min", 1.0, "Carbon emissions."),
        Figure("labor_hours", "sum", "min", 1.0, "Human labor consumed."),
        Figure("certified_worker_hours", "sum", "min", 1.0, "Certified labor consumed."),
        Figure("rework_steps", "sum", "min", 1.0, "Steps that disturb prior work."),
        Figure("regulatory_burden", "sum", "min", 1.0, "Regulatory friction."),
        Figure("compliance_debt", "sum", "min", 1.0, "Open compliance violations."),
        Figure("safety_risk", "prob_any", "min", 1.0, "Probability any safety risk escapes."),
        Figure("defect_probability", "prob_any", "min", 1.0, "Probability any defect escapes."),
        Figure("toxicity", "max", "min", 1.0, "Worst toxicity in a design."),
        Figure("toxicity_risk", "prob_any", "min", 1.0, "Predicted toxicity risk."),
        Figure("off_target_risk", "prob_any", "min", 1.0, "Predicted off-target risk."),
        Figure("hERG_risk", "prob_any", "min", 1.0, "Predicted cardiac hERG risk."),
        Figure("assay_uncertainty", "max", "min", 1.0, "Worst remaining assay uncertainty."),
        Figure("ip_risk", "max", "min", 1.0, "Worst intellectual-property collision risk."),
        Figure("synthetic_steps", "sum", "min", 1.0, "Synthetic route length."),
        Figure("potency_score", "min", "max", 1.0, "Weakest predicted potency score."),
        Figure("selectivity", "min", "max", 1.0, "Weakest selectivity score."),
        Figure("drug_likeness", "min", "max", 1.0, "Weakest drug-likeness score."),
        Figure("novelty", "min", "max", 1.0, "Weakest novelty score."),
        Figure("cobalt", "sum", "min", 1.0, "Cobalt content or use."),
        Figure("supply_chain_risk", "prob_any", "min", 1.0, "Supplier/path risk."),
        Figure("confidence", "product", "max", 1.0, "Independent confidence product."),
        Figure("evidence_strength", "min", "max", 1.0, "Weakest evidence link."),
        Figure("trace_completeness", "min", "max", 1.0, "Weakest audit-trace coverage."),
        Figure("safety_margin", "min", "max", 1.0, "Weakest safety margin."),
        Figure("supply_chain_trust", "min", "max", 1.0, "Weakest supplier trust."),
        Figure("throughput", "min", "max", 1.0, "Bottleneck throughput."),
    ),
)
"""Reusable figure vocabulary for cross-domain design optimization."""


GENERAL_FIGURES = GENERAL_FIGURE_PROFILE.to_monoid("GeneralFigures")
"""General heterogeneous figure algebra. Use when a domain has mixed metrics."""


SAFETY_FIRST = GENERAL_FIGURE_PROFILE.with_weights(
    "safety-first",
    safety_risk=100.0,
    defect_probability=80.0,
    compliance_debt=60.0,
    confidence=25.0,
    evidence_strength=20.0,
    schedule_delay=1.0,
    money_usd=0.1,
).to_monoid("SafetyFirstFigures")

COMPLIANCE_FIRST = GENERAL_FIGURE_PROFILE.with_weights(
    "compliance-first",
    compliance_debt=100.0,
    regulatory_burden=30.0,
    trace_completeness=50.0,
    safety_risk=25.0,
    schedule_delay=1.0,
).to_monoid("ComplianceFirstFigures")

FASTEST_RECOVERY = GENERAL_FIGURE_PROFILE.with_weights(
    "fastest-recovery",
    schedule_delay=100.0,
    time_hours=50.0,
    rework_steps=15.0,
    safety_risk=5.0,
    compliance_debt=5.0,
).to_monoid("FastestRecoveryFigures")

LEAST_DISRUPTIVE = GENERAL_FIGURE_PROFILE.with_weights(
    "least-disruptive",
    rework_steps=100.0,
    schedule_delay=20.0,
    labor_hours=10.0,
    money_usd=1.0,
    safety_risk=10.0,
).to_monoid("LeastDisruptiveFigures")

EVIDENCE_FIRST = GENERAL_FIGURE_PROFILE.with_weights(
    "evidence-first",
    evidence_strength=100.0,
    confidence=80.0,
    trace_completeness=50.0,
    safety_risk=10.0,
).to_monoid("EvidenceFirstFigures")

SUSTAINABILITY_FIRST = GENERAL_FIGURE_PROFILE.with_weights(
    "sustainability-first",
    emissions_kgco2e=100.0,
    energy_kwh=30.0,
    toxicity=20.0,
    money_usd=1.0,
).to_monoid("SustainabilityFirstFigures")

DRUG_PORTFOLIO = GENERAL_FIGURE_PROFILE.with_weights(
    "drug-portfolio",
    # Evidence and developability dominate; shared fixed assay costs are nearly
    # neutralized so ranking a slate of candidates turns on what distinguishes
    # them (evidence, risk, developability) rather than on costs they all share.
    evidence_strength=100.0,
    confidence=80.0,
    drug_likeness=50.0,
    assay_uncertainty=40.0,
    toxicity_risk=60.0,
    off_target_risk=40.0,
    hERG_risk=40.0,
    money_usd=0.001,
    time_hours=0.001,
).to_monoid("DrugPortfolioFigures")
"""Cross-candidate drug ranking: evidence/risk/developability over shared cost."""


# ===================================================================
# Pre-built resource algebras (dual of KOMPOSOS's 5 quantales)
# ===================================================================

ADDITIVE_COST = ResourceMonoid(
    combine=lambda a, b: _merge(a, b, lambda x, y: x + y),
    unit={},
    compare=_within,
    name="AdditiveCost(+, 0)",
)
"""Costs accumulate along a build. Used for: time, money, latency.
   Composite cost = sum of part costs. Lower = better."""

MAX_CAPACITY = ResourceMonoid(
    combine=lambda a, b: _merge(a, b, max),
    unit={},
    compare=_within,
    name="MaxCapacity(max, 0)",
)
"""Peak / bottleneck resource. Used for: peak memory, max stress.
   Composite cost = max of part costs. Lower = better."""

MULTISET_MATERIALS = ResourceMonoid(
    combine=lambda a, b: _merge(a, b, lambda x, y: x + y),
    unit={},
    compare=_within,
    name="MultisetMaterials(union, empty)",
)
"""Bill of materials: parts consumed accumulate as a multiset.
   Same arithmetic as additive, different intent (counts, not time)."""

TROPICAL = ResourceMonoid(
    combine=lambda a, b: _merge(a, b, lambda x, y: x + y),
    unit={},
    compare=_within,
    name="Tropical(min,+)",
)
"""(min, +) semiring: costs add along a build, and the search minimises.
   Enables Dijkstra-style cheapest-assembly optimality in DAEDALUS."""


def _linear_combine(a: ResourceValue, b: ResourceValue) -> ResourceValue:
    """Spend-once: a token may not appear on both sides of a combine.

    This is what forbids the diagonal. A design that tries to consume the
    same permit/one-shot resource in two sub-assemblies raises here, at build
    time, rather than silently double-spending.
    """
    overlap = set(a) & set(b)
    if overlap:
        raise ResourceError(
            f"Linear resource reused (spend-once violated): {sorted(overlap)}. "
            f"Wrap it in an explicit '!' (copy) operation if duplication is intended."
        )
    return {**a, **b}


LINEAR_TOKENS = ResourceMonoid(
    combine=_linear_combine,
    unit={},
    compare=_within,
    name="LinearTokens(spend-once)",
    linear=True,
)
"""Non-copyable one-shot resources. Combining a token with itself raises --
   the load-bearing difference from cartesian KOMPOSOS. Permits, licences,
   single-use materials live here."""


# ===================================================================
# Registry
# ===================================================================

RESOURCE_REGISTRY: Dict[str, ResourceMonoid] = {
    "additive": ADDITIVE_COST,
    "max": MAX_CAPACITY,
    "multiset": MULTISET_MATERIALS,
    "tropical": TROPICAL,
    "linear": LINEAR_TOKENS,
    "figures": GENERAL_FIGURES,
    "safety": SAFETY_FIRST,
    "compliance": COMPLIANCE_FIRST,
    "fastest": FASTEST_RECOVERY,
    "least_disruptive": LEAST_DISRUPTIVE,
    "evidence": EVIDENCE_FIRST,
    "sustainability": SUSTAINABILITY_FIRST,
}


def get_resource_algebra(name: str) -> ResourceMonoid:
    """
    Look up a resource algebra by name.

    Args:
        name: One of "additive", "max", "multiset", "tropical", "linear",
              "figures", "safety", "compliance", "fastest",
              "least_disruptive", "evidence", "sustainability".

    Raises:
        KeyError: If the name is not recognized.
    """
    if name not in RESOURCE_REGISTRY:
        raise KeyError(
            f"Unknown resource algebra: {name!r}. "
            f"Valid: {', '.join(RESOURCE_REGISTRY)}"
        )
    return RESOURCE_REGISTRY[name]
