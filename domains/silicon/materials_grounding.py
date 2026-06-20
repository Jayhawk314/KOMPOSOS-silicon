# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Ground the interconnect metal table against CITED reference data.

`interconnect.py` proposes metal swaps from a hardcoded property table. A proposal is
only trustworthy if its numbers are real, so this module cross-validates each
interconnect metal's resistivity against an independently CITED reference and attaches
the citation as a receipt. Disagreements are surfaced, not hidden — that is the point of
grounding (it caught thin-film W reading 5.60 vs the 5.28 bulk literature value).

Reference provenance:
  - Cu, Al, W, Mo, Ag, Au: lifted from KOMPOSOS-IV-CHEM `metal_bridge/material_properties`
    (electrical_resistivity_ohm_m x 1e8 = uOhm-cm), which cites ASM Handbook Vol. 2 (1990)
    and Smithells Metals Reference Book (2004). Melting points from the same source.
  - Co, Ru: D. Gall, "The search for the most conductive metal for narrow interconnect
    lines", J. Appl. Phys. 119, 085101 (2016) + CRC Handbook; the modern sub-Cu metals.
  - TaN: barrier (not a primary conductor); CRC / ITRS interconnect roadmap.

Evidence tier: `literature_value` — cited bulk properties, screening-grade, NOT a foundry
measurement of a specific process. A grounded recommendation carries these citations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .interconnect import INTERCONNECT_METALS

EVIDENCE_TIER = "literature_value"
_RHO_TOL = 0.05          # 5% relative agreement counts as cross-validated


@dataclass(frozen=True)
class MetalReference:
    name: str
    resistivity_uohm_cm: float
    melting_point_C: float          # EM-relevance proxy: refractory -> higher EM activation
    source: str


# Independently cited reference values (see module docstring for provenance).
REFERENCE: Dict[str, MetalReference] = {
    "Cu":  MetalReference("Cu", 1.68, 1085.0, "ASM Handbook Vol.2 / Smithells (via CHEM metal_bridge)"),
    "Al":  MetalReference("Al", 2.65,  660.0, "ASM Handbook Vol.2 / Smithells (via CHEM metal_bridge)"),
    "W":   MetalReference("W",  5.28, 3422.0, "Smithells (via CHEM metal_bridge); bulk value"),
    "Mo":  MetalReference("Mo", 5.34, 2623.0, "Smithells (via CHEM metal_bridge)"),
    "Ag":  MetalReference("Ag", 1.59,  962.0, "ASM Handbook Vol.2 / Smithells (via CHEM metal_bridge)"),
    "Au":  MetalReference("Au", 2.44, 1064.0, "ASM Handbook Vol.2 / Smithells (via CHEM metal_bridge)"),
    "Co":  MetalReference("Co", 6.24, 1495.0, "Gall, J. Appl. Phys. 119, 085101 (2016) / CRC"),
    "Ru":  MetalReference("Ru", 7.60, 2334.0, "Gall, J. Appl. Phys. 119, 085101 (2016) / CRC"),
    "TaN": MetalReference("TaN", 220.0, 3090.0, "CRC / ITRS interconnect roadmap (barrier)"),
}


@dataclass
class MetalGrounding:
    metal: str
    table_resistivity: float
    cited_resistivity: Optional[float]
    rel_error: Optional[float]
    grounded: bool
    citation: str
    melting_point_C: Optional[float]
    tier: str = EVIDENCE_TIER
    note: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {"metal": self.metal, "table_rho": self.table_resistivity,
                "cited_rho": self.cited_resistivity,
                "rel_error": None if self.rel_error is None else round(self.rel_error, 4),
                "grounded": self.grounded, "tier": self.tier,
                "citation": self.citation, "melting_point_C": self.melting_point_C,
                "note": self.note}


def ground_metal(name: str) -> MetalGrounding:
    """Cross-validate one interconnect metal's resistivity against the cited reference."""
    m = INTERCONNECT_METALS[name]
    ref = REFERENCE.get(name)
    if ref is None:
        return MetalGrounding(name, m.resistivity_uohm_cm, None, None, False,
                              "no cited reference", None, note="ungrounded — needs a source")
    rel = abs(m.resistivity_uohm_cm - ref.resistivity_uohm_cm) / ref.resistivity_uohm_cm
    grounded = rel <= _RHO_TOL
    if grounded:
        note = ""
    else:
        direction = ("thin-film/CVD exceeds bulk; flag for the process value"
                     if m.resistivity_uohm_cm > ref.resistivity_uohm_cm
                     else "below cited; within the literature spread, flag the source")
        note = (f"table {m.resistivity_uohm_cm:.2f} vs cited {ref.resistivity_uohm_cm:.2f} "
                f"uOhm-cm ({rel*100:.0f}% off) - {direction}")
    return MetalGrounding(name, m.resistivity_uohm_cm, ref.resistivity_uohm_cm, rel,
                          grounded, ref.source, ref.melting_point_C, note=note)


def ground_interconnect_table() -> List[MetalGrounding]:
    return [ground_metal(n) for n in INTERCONNECT_METALS]


@dataclass
class EMGroundingCheck:
    """Sanity: EM activation energy should track melting point (refractory => robust)."""
    ordered_by_tm: List[str]
    ordered_by_ea: List[str]
    concordant: bool
    note: str = ""


def ground_em_against_melting_point() -> EMGroundingCheck:
    """Refractory metals (high Tm) should have higher EM activation energy.

    A monotone (Spearman = 1) match between the Tm ranking and the Ea ranking grounds the
    EM-robustness claim in an independent physical property, instead of asserting it.
    """
    conductors = [n for n, m in INTERCONNECT_METALS.items()
                  if m.role == "conductor" and n in REFERENCE]
    by_tm = sorted(conductors, key=lambda n: REFERENCE[n].melting_point_C)
    by_ea = sorted(conductors, key=lambda n: INTERCONNECT_METALS[n].em_activation_eV)
    # Spearman rank correlation between Tm and Ea across the conductors.
    tm_rank = {n: i for i, n in enumerate(by_tm)}
    ea_rank = {n: i for i, n in enumerate(by_ea)}
    n = len(conductors)
    d2 = sum((tm_rank[c] - ea_rank[c]) ** 2 for c in conductors)
    rho = 1 - 6 * d2 / (n * (n * n - 1)) if n > 1 else 0.0
    concordant = rho >= 0.7
    return EMGroundingCheck(by_tm, by_ea, concordant,
                            note=f"Spearman(Tm, EM activation) = {rho:+.2f} over {n} conductors")


def grounded_citation(metal: str) -> str:
    """A receipt string for a recommendation: the cited basis for a metal's properties."""
    g = ground_metal(metal)
    status = "grounded" if g.grounded else ("ungrounded" if g.cited_resistivity is None
                                            else "flagged")
    return f"{metal}: rho~{g.table_resistivity:.2f} uOhm-cm [{status}; {g.citation}]"


def main() -> None:
    print("KOMPOSOS-V | interconnect materials grounding\n" + "=" * 64)
    print(f"{'metal':<6}{'table':>8}{'cited':>8}{'err':>7}  grounded  source")
    for g in ground_interconnect_table():
        cited = "-" if g.cited_resistivity is None else f"{g.cited_resistivity:.2f}"
        err = "-" if g.rel_error is None else f"{g.rel_error*100:.0f}%"
        print(f"{g.metal:<6}{g.table_resistivity:>8.2f}{cited:>8}{err:>7}  "
              f"{'yes' if g.grounded else 'NO ':>8}  {g.citation}")
        if g.note:
            print(f"        ^ {g.note}")
    print()
    em = ground_em_against_melting_point()
    print(f"EM-vs-melting-point grounding: {em.note} -> "
          f"{'CONCORDANT' if em.concordant else 'DISCORDANT'}")
    print(f"  by melting point: {' < '.join(em.ordered_by_tm)}")
    print(f"  by EM activation: {' < '.join(em.ordered_by_ea)}")


if __name__ == "__main__":
    main()
