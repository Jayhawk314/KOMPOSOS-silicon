# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Materials / MOF Design -- the flagship domain, on real building blocks.

A metal-organic framework is a metal node coordinated to organic linkers in a
periodic net -- literally a topological network of real fragments. This domain
makes OPERADUM the *design* complement to the KOMPOSOS-IV-CHEM base model:
KOMPOSOS interprets molecules; OPERADUM assembles a framework from a real linker
library and hands it back for audit.

It uses genuine data -- the Kulik 22-atom MOF linker set (SMILES, molecular
weight, donor counts, viability scores) -- loaded from the neighbouring repo
when present, with an embedded real subset as a dependency-free fallback. The
cost is additive molecular weight (design the lightest framework); the
SemanticGate validates by real linker descriptors (a property surrogate that a
true DFT / stability model would replace at this exact seam).

Two facets, tying Parts 1-3 together:
  * a tree design  -- choose the optimal real linker for a framework (Wright /
    SemanticGate), round-tripped to KOMPOSOS;
  * a network view -- `mof_net()` builds the framework as a Diagram (a metal hub
    coordinating k linkers), so its coordination/topology is inspectable.

HONEST SCOPING: the descriptors are real but the property "model" is a transparent
surrogate over them; swap in a real predictor at the validator/cost seam (the
"math at the leaf" pattern) for production use.
"""

from __future__ import annotations
import csv
import os
from typing import Any, Callable, Dict, List, Optional

from ..core.types import Operation, Spec
from ..core.diagram import Diagram
from ..core.enrichment import ResourceMonoid, ADDITIVE_COST
from .base import DomainPlugin, GroundTruthCase


# Embedded real subset of the Kulik 22-atom linker set (fallback when the CSV
# is not reachable). Fields: rank, SMILES, MW, heavy_atoms, N, O, S, stability,
# synthesizability, viable.
_EMBEDDED_LINKERS: List[Dict[str, Any]] = [
    {"rank": 1, "smiles": "O=C([O-])c1cc([N-][N-]c2ccc(C[O-])cc2)cc(C(=O)[O-])c1",
     "mw": 297.25, "atoms": 22, "n": 2, "o": 5, "s": 0, "stability": 0.95, "synth": 0.95, "viable": True},
    {"rank": 2, "smiles": "O=Cc1cccc(C[O-])c1-c1c(C(=O)[O-])cccc1C(=O)[O-]",
     "mw": 297.24, "atoms": 22, "n": 0, "o": 6, "s": 0, "stability": 0.95, "synth": 0.95, "viable": True},
    {"rank": 3, "smiles": "Nc1cc(-c2cc(C(=O)[O-])cc(C(=O)[O-])c2)ccc1C(=O)[O-]",
     "mw": 298.23, "atoms": 22, "n": 1, "o": 6, "s": 0, "stability": 0.95, "synth": 0.95, "viable": True},
    {"rank": 4, "smiles": "Nn1c(-c2cccc(C=O)c2)nnc1-c1cccc(C[O-])c1",
     "mw": 293.31, "atoms": 22, "n": 4, "o": 2, "s": 0, "stability": 0.95, "synth": 0.95, "viable": True},
    {"rank": 5, "smiles": "Cc1cc(C(=O)[O-])ccc1S(=O)(=O)c1ccc(C(=O)[O-])cc1",
     "mw": 318.31, "atoms": 22, "n": 0, "o": 6, "s": 1, "stability": 0.95, "synth": 0.95, "viable": True},
]

#: Default location of the real linker CSV in the base model repo.
DEFAULT_LINKER_CSV = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "KOMPOSOS-IV-CHEM", "kulik_22atom_linkers_100.csv")

#: Metal secondary building units and their coordination number.
_METALS = {"Zn4O": 6, "Cu_paddlewheel": 4}


def _load_linkers(csv_path: Optional[str], limit: int) -> List[Dict[str, Any]]:
    path = csv_path or DEFAULT_LINKER_CSV
    if not os.path.isfile(path):
        return list(_EMBEDDED_LINKERS[:limit])
    out: List[Dict[str, Any]] = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            out.append({
                "rank": int(row["rank"]),
                "smiles": row["SMILES"],
                "mw": float(row["MW"]),
                "atoms": int(row["heavy_atoms"]),
                "n": int(row["N_count"]), "o": int(row["O_count"]), "s": int(row["S_count"]),
                "stability": float(row["stability_score"]),
                "synth": float(row["synthesizability_score"]),
                "viable": row["overall_viable"].strip().lower() == "true",
            })
            if len(out) >= limit:
                break
    return out


class MaterialsDomain(DomainPlugin):
    """Design a MOF: a metal node coordinated to a real organic linker."""

    name = "materials"

    def __init__(self, csv_path: Optional[str] = None, limit: int = 5,
                 linkers: Optional[List[Dict[str, Any]]] = None):
        # Pass an explicit linker list (e.g. a held-out test split) or load from data.
        self.linkers = list(linkers) if linkers is not None else _load_linkers(csv_path, limit)

    def colours(self) -> List[str]:
        return ["Metal", "Linker", "MOF"]

    def operations(self) -> List[Operation]:
        ops: List[Operation] = []
        # Metal secondary building units (0-arity sources).
        for metal, coord in _METALS.items():
            ops.append(Operation(
                name=f"node_{metal}", inputs=[], output="Metal", cost={},
                metadata={"metal": metal, "coordination": coord},
                _fn=lambda _m=metal, _c=coord: {"metal": _m, "coordination": _c}))
        # Real linkers (0-arity sources), cost = molecular weight.
        for L in self.linkers:
            ops.append(Operation(
                name=f"linker_{L['rank']}", inputs=[], output="Linker",
                cost={"mw": round(L["mw"], 1)},
                metadata=dict(L),
                _fn=lambda _L=L: dict(_L)))
        # Framework assembly.
        ops.append(Operation(
            name="coordinate", inputs=["Metal", "Linker"], output="MOF",
            cost={"steps": 1}, metadata={"step": "coordinate"},
            _fn=lambda metal, linker: {"metal": metal, "linker": linker}))
        return ops

    def resource_algebra(self) -> ResourceMonoid:
        return ADDITIVE_COST   # lightest framework

    # ---------------- property validators (the specialized-tool seam) ----------------

    @staticmethod
    def viable() -> Callable:
        """Accept frameworks whose linker passes the viability screen."""
        def validate(artifact: Callable, _comp) -> bool:
            return bool(artifact()["linker"]["viable"])
        return validate

    @staticmethod
    def donor_rich(min_oxygen: int) -> Callable:
        """Accept frameworks whose linker has at least `min_oxygen` O-donors
        (strong, water-stable carboxylate coordination)."""
        def validate(artifact: Callable, _comp) -> bool:
            link = artifact()["linker"]
            return link["viable"] and link["o"] >= min_oxygen
        return validate

    # ---------------- the network (topology) facet ----------------

    def mof_net(self, operad, metal_op: str, linker_ops: List[str]) -> Diagram:
        """Build the framework as a Diagram: a metal hub coordinating k linkers.
        The result's graph_metrics expose its coordination/topology."""
        coordinate = operad.get_op("coordinate")
        d = Diagram("mof-net")
        metal = d.add_node(operad.get_op(metal_op), [])
        last = None
        for lop in linker_ops:
            linker = d.add_node(operad.get_op(lop), [])
            last = d.add_node(coordinate, [metal, linker])  # metal hub fans out
        d.set_output(last)
        return d

    # ---------------- ground truth ----------------

    def ground_truth(self) -> List[GroundTruthCase]:
        viable = [L for L in self.linkers if L["viable"]]
        lightest = min(viable, key=lambda L: L["mw"]) if viable else None
        min_cost = round(lightest["mw"], 1) + 1 if lightest else None  # mw + 1 coordinate step
        return [
            GroundTruthCase(
                name="lightest viable MOF",
                spec=Spec((), "MOF"),
                buildable=True, min_cost=min_cost,
                note=f"coordinate(node, linker_{lightest['rank']}) "
                     f"-- lightest viable linker (MW {lightest['mw']})" if lightest else "",
            ),
        ]
