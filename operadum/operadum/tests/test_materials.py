# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Part 3 tests: the materials / MOF design domain on real linker data.

OPERADUM designs a framework from a real building-block library, optimizes the
lightest viable linker, designs by property (SemanticGate), exposes the MOF as a
topological net (Part 1), and round-trips to KOMPOSOS (engine=mini).
"""

import pytest

from operadum.core.types import Spec
from operadum.core.enrichment import ADDITIVE_COST
from operadum.wright.engine import Wright
from operadum.wright.schema import Verdict
from operadum.gate.semantic_gate import SemanticGate
from operadum.bridges.round_trip import KomposVerifier
from operadum.domains.materials import MaterialsDomain


def domain():
    # Force the embedded real subset for a deterministic test (rank 4 is lightest).
    return MaterialsDomain(csv_path="<<none>>", limit=5)


def test_loads_real_linker_building_blocks():
    d = domain()
    op = d.build_operad()
    assert op.monoid is ADDITIVE_COST
    linker_ops = [o for o in op.operations() if o.name.startswith("linker_")]
    assert len(linker_ops) == 5
    # Real descriptors carried as metadata.
    assert all("smiles" in o.metadata and "mw" in o.cost for o in linker_ops)


def test_optimize_lightest_viable_mof():
    d = domain()
    op = d.build_operad()
    result = Wright(op, max_depth=4).optimize(Spec((), "MOF"))
    assert result.verdict == Verdict.BUILDABLE
    # Lightest viable linker is rank 4 (MW 293.3); cost = mw + 1 coordinate step.
    assert "linker_4" in result.construction.wiring
    assert result.construction.cost == {"mw": 293.3, "steps": 1}
    # The realized framework describes the assembled MOF.
    mof = result.construction.artifact()
    assert mof["linker"]["smiles"].startswith("Nn1c")
    assert mof["metal"]["coordination"] in (4, 6)


def test_design_by_property_donor_rich():
    """Design the lightest framework whose linker is oxygen-donor rich (>= 6 O)."""
    d = domain()
    op = d.build_operad()
    design = SemanticGate(op, max_depth=4).synthesize(Spec((), "MOF"),
                                                      validator=d.donor_rich(6))
    assert design is not None
    mof = design.artifact()
    assert mof["linker"]["o"] >= 6
    # Among O>=6 linkers the lightest is rank 2 (MW 297.24).
    assert "linker_2" in design.wiring


def test_mof_as_topological_net():
    d = domain()
    op = d.build_operad()
    net = d.mof_net(op, "node_Zn4O", ["linker_2", "linker_3", "linker_4"])
    assert net.type_check()
    metrics = net.graph_metrics()
    # The metal hub fans out to 3 coordinate nodes -> a real network.
    assert metrics["nodes"] == 1 + 3 + 3      # 1 metal + 3 linkers + 3 coordinations
    framework = net.realize()()
    assert framework["metal"]["metal"] == "Zn4O"


def test_mof_round_trips_to_komposos():
    d = domain()
    op = d.build_operad()
    design = Wright(op, max_depth=4).optimize(Spec((), "MOF")).construction
    result = KomposVerifier().verify(design.composite, op)
    # Additive MW cost -> exact homomorphism -> AGREE.
    assert result.verdict == "AGREE"
