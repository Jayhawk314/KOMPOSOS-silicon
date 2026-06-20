# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
KOMPOSOS-CHEM integration -- use the REAL predictor, don't reinvent it.

KOMPOSOS-IV-CHEM already does inverse/compositional design with a real, accurate
property predictor (composition_engine.predictor.CompositionPredictor: e.g.
LiFePO4 -> 170 mAh/g, 3.4 V). This module does NOT rebuild any of that. It wires
the real predictor in as OPERADUM's oracle and asks one honest question:

    Does OPERADUM's FORMAL layer add anything on top of the existing design?

The test case is battery-cathode design under a COBALT budget -- the real-world
scarce/ethical constraint the industry is engineered around. Cobalt is modelled
as an OPERADUM resource, capacity is scored by the REAL predictor, and DAEDALUS
returns the provably cost-constrained optimum. We then report, plainly, what the
formal layer contributed and what it did not (it does NOT improve predictions --
those are entirely KOMPOSOS's).

Heavy/optional: this module lazy-imports KOMPOSOS-CHEM (numpy + its DB). It lives
OUTSIDE the stdlib-only core -- the specialized tool attaches at the leaf.
"""

from __future__ import annotations
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..core.operad import Operad
from ..core.enrichment import ADDITIVE_COST
from ..core.types import Spec
from ..gate.semantic_gate import enumerate_designs

DEFAULT_KOMPOSOS_PATH = r"C:\Users\JAMES\github\KOMPOSOS-IV-CHEM"

# Real cathode building blocks: (name, formula, cobalt fraction per formula unit).
CATHODES: List[Tuple[str, str, float]] = [
    ("LiCoO2",  "LiCoO2",                 1.00),
    ("LiNiO2",  "LiNiO2",                 0.00),
    ("LiMnO2",  "LiMnO2",                 0.00),
    ("LiFePO4", "LiFePO4",                0.00),
    ("LiMn2O4", "LiMn2O4",                0.00),
    ("NMC111",  "LiNi0.33Mn0.33Co0.33O2", 0.33),
    ("NMC622",  "LiNi0.6Mn0.2Co0.2O2",   0.20),
    ("NMC811",  "LiNi0.8Mn0.1Co0.1O2",   0.10),
]


def load_predictor(komposos_path: str = DEFAULT_KOMPOSOS_PATH):
    """Import and instantiate the REAL CompositionPredictor. Raises on failure."""
    if komposos_path and komposos_path not in sys.path:
        sys.path.insert(0, komposos_path)
    from composition_engine.predictor import CompositionPredictor
    return CompositionPredictor()


# A larger discrete grammar: cation x framework. Cobalt fraction per formula unit.
# These are the compositions the real predictor actually covers (others return None).
CATHODES_LARGE: List[Tuple[str, str, float]] = [
    ("LiCoO2", "LiCoO2", 1.0), ("LiNiO2", "LiNiO2", 0.0), ("LiMnO2", "LiMnO2", 0.0),
    ("LiCoPO4", "LiCoPO4", 1.0), ("LiNiPO4", "LiNiPO4", 0.0), ("LiMnPO4", "LiMnPO4", 0.0),
    ("LiFePO4", "LiFePO4", 0.0),
    ("LiCo2O4", "LiCo2O4", 1.0), ("LiNi2O4", "LiNi2O4", 0.0), ("LiMn2O4", "LiMn2O4", 0.0),
]


def build_cathode_operad(cathodes: Optional[List[Tuple[str, str, float]]] = None) -> Operad:
    """An operad over the real cathodes; cost = cobalt content (the scarce resource)."""
    op = Operad("battery-cathode", monoid=ADDITIVE_COST)
    op.add_colour("Cathode")
    for name, formula, cobalt in (cathodes or CATHODES):
        op.add_op(f"make_{name}", [], "Cathode", cost={"cobalt": cobalt},
                  fn=lambda f=formula: f, formula=formula)
    return op


def property_oracle(predictor) -> Callable[[str], Dict[str, Any]]:
    """A memoised wrapper around the REAL predictor returning a property dict.

    Memoisation matters: a cold predictor call is ~seconds; coherence/dedup means
    each distinct composition is scored once."""
    cache: Dict[str, Dict[str, Any]] = {}
    calls = {"n": 0}

    def oracle(formula: str) -> Dict[str, Any]:
        if formula in cache:
            return cache[formula]
        calls["n"] += 1
        result = predictor.predict(formula)
        props = {k: getattr(v, "value", v) for k, v in result.properties.items()}
        cache[formula] = props
        return props

    oracle.calls = calls            # type: ignore[attr-defined]
    return oracle


@dataclass
class CathodeDesign:
    name: str
    formula: str
    capacity: float
    cobalt: float
    band_gap: float
    voltage: float

    def __str__(self) -> str:
        return (f"{self.formula:24s} cap={self.capacity:6.1f} mAh/g  "
                f"gap={self.band_gap:.2f}eV  V={self.voltage:.2f}  Co={self.cobalt}")


@dataclass
class DesignReport:
    best_unconstrained: Optional[CathodeDesign]
    best_constrained: Optional[CathodeDesign]
    max_band_gap: Optional[float]
    cobalt_budget: Optional[float]
    candidates: int
    feasible: int
    predictor_calls: int
    round_trip: str = ""

    @property
    def constraint_binds(self) -> bool:
        b, u = self.best_constrained, self.best_unconstrained
        return bool(b and u and b.formula != u.formula)

    def __str__(self) -> str:
        cons = []
        if self.max_band_gap is not None:
            cons.append(f"band_gap<={self.max_band_gap}")
        if self.cobalt_budget is not None:
            cons.append(f"cobalt<={self.cobalt_budget}")
        head = "constraints: " + (", ".join(cons) if cons else "none")
        lines = [head,
                 f"  unconstrained optimum: {self.best_unconstrained}" if self.best_unconstrained else "  none",
                 f"  constrained optimum  : {self.best_constrained}" if self.best_constrained else "  constrained: infeasible",
                 f"  candidates={self.candidates} feasible={self.feasible} "
                 f"predictor_calls={self.predictor_calls} round_trip={self.round_trip} "
                 f"constraint_binds={self.constraint_binds}"]
        return "\n".join(lines)


def design_cathode(predictor, max_band_gap: Optional[float] = None,
                   cobalt_budget: Optional[float] = None,
                   objective: str = "theoretical_capacity",
                   max_depth: int = 2,
                   cathodes_override: Optional[List[Tuple[str, str, float]]] = None) -> DesignReport:
    """
    OPERADUM designs the cathode maximising `objective` subject to a band-gap
    (conductivity) ceiling and/or a cobalt budget, scoring every candidate with
    the REAL predictor. The formal contributions are:
      * provable optimality -- enumerate_designs is exhaustive over the grammar,
        so the returned design is the constrained maximum, not a heuristic guess;
      * constraint enforcement by construction -- infeasible designs are excluded;
      * dedup -- the slow predictor is called once per distinct composition;
      * a verified KOMPOSOS round-trip on the chosen design.
    It does NOT improve the predictions -- those are entirely KOMPOSOS's.
    """
    op = build_cathode_operad(cathodes_override)
    oracle = property_oracle(predictor)
    designs = enumerate_designs(op, Spec((), "Cathode"), max_depth=max_depth)

    scored: List[Tuple[CathodeDesign, Any]] = []
    for comp in designs:
        formula = op.realize(comp)()
        props = oracle(formula)
        cap = props.get("theoretical_capacity")
        obj = props.get(objective)
        if cap is None or obj is None:
            continue
        d = CathodeDesign(
            name=comp.head.name.replace("make_", ""), formula=formula,
            capacity=cap, cobalt=comp.cost(op.monoid).get("cobalt", 0.0),
            band_gap=props.get("band_gap", float("nan")),
            voltage=props.get("voltage", float("nan")))
        scored.append((d, comp))

    def feasible(d: CathodeDesign) -> bool:
        if max_band_gap is not None:
            # A missing/NaN band gap cannot be confirmed conductive -> infeasible.
            if d.band_gap != d.band_gap or d.band_gap > max_band_gap + 1e-9:
                return False
        if cobalt_budget is not None and d.cobalt > cobalt_budget + 1e-9:
            return False
        return True

    best_unconstrained = max(scored, key=lambda s: s[0].capacity, default=(None, None))
    feas = [s for s in scored if feasible(s[0])]
    best_constrained = max(feas, key=lambda s: s[0].capacity, default=(None, None))

    round_trip = ""
    if best_constrained[1] is not None:
        try:
            from ..bridges.round_trip import KomposVerifier
            round_trip = KomposVerifier().verify(best_constrained[1], op).verdict
        except Exception:
            round_trip = "n/a"

    return DesignReport(
        best_unconstrained=best_unconstrained[0],
        best_constrained=best_constrained[0],
        max_band_gap=max_band_gap, cobalt_budget=cobalt_budget,
        candidates=len(scored), feasible=len(feas),
        predictor_calls=oracle.calls["n"],   # type: ignore[attr-defined]
        round_trip=round_trip)
