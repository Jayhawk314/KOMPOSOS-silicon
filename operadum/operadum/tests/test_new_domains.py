# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Verified design potential across three new domains:
  * program synthesis  -- verified by input/output examples
  * quantum circuits   -- verified by 2x2 unitary matrices
  * manufacturing      -- verified by the bill of materials (multiset algebra)
"""

import pytest

from operadum.core.types import Spec
from operadum.core.enrichment import MULTISET_MATERIALS
from operadum.gate.semantic_gate import SemanticGate
from operadum.wright.engine import Wright
from operadum.wright.schema import Verdict
from operadum.domains.program_synthesis import ProgramSynthesisDomain
from operadum.domains.quantum_circuit import (
    QuantumCircuitDomain, phase_equal, mul, IDENTITY, Z, S, X,
)
from operadum.domains.manufacturing import ManufacturingDomain


# ---------------------------------------------------------------- program synthesis

def test_program_domain_ground_truth_all_verified():
    domain = ProgramSynthesisDomain()
    op = domain.build_operad()
    gate = SemanticGate(op, max_depth=5)
    for case in domain.ground_truth():
        examples = case.spec.constraints["examples"]
        design = gate.by_examples(case.spec, examples)
        assert design is not None, case.name
        # Designed program satisfies every example.
        for args, expected in examples:
            a = args if isinstance(args, tuple) else (args,)
            assert design.artifact(*a) == expected
        # And it found the cost-minimal correct program.
        assert sum(design.cost.values()) == case.min_cost, case.name


# ---------------------------------------------------------------- quantum circuits

def test_quantum_matrix_helpers():
    assert mul(S, S) == Z                      # S^2 = Z exactly
    assert phase_equal(Z, Z)
    assert phase_equal(mul(X, IDENTITY), X)
    assert not phase_equal(X, Z)


def test_quantum_synthesizes_target_unitaries():
    for case in QuantumCircuitDomain().ground_truth():
        target = case.spec.constraints["target"]
        library = case.spec.constraints["library"]
        op = QuantumCircuitDomain(gates=library).build_operad()
        gate = SemanticGate(op, max_depth=4)
        design = gate.synthesize(
            case.spec,
            validator=lambda art, comp, _t=target: phase_equal(art(IDENTITY), _t),
        )
        assert design is not None, case.name
        # The synthesized circuit's unitary matches the target (up to global phase).
        assert phase_equal(design.artifact(IDENTITY), target), case.name
        assert sum(design.cost.values()) == case.min_cost, case.name


def test_quantum_finds_Z_as_two_S_gates():
    op = QuantumCircuitDomain(gates=["H", "X", "S", "T"]).build_operad()
    design = SemanticGate(op, max_depth=4).synthesize(
        Spec(("Qubit",), "Qubit"),
        validator=lambda art, comp: phase_equal(art(IDENTITY), Z),
    )
    assert design.wiring == "S(S(Qubit))"


# ---------------------------------------------------------------- manufacturing

def test_manufacturing_uses_multiset_algebra():
    op = ManufacturingDomain().build_operad()
    assert op.monoid is MULTISET_MATERIALS


def test_manufacturing_bill_of_materials_accumulates():
    op = ManufacturingDomain().build_operad()
    result = Wright(op, max_depth=6).optimize(Spec(("Steel", "Rubber"), "Bicycle"))
    assert result.verdict == Verdict.BUILDABLE
    # The cost IS the bill of materials.
    assert result.construction.cost == {"steel": 5, "rubber": 2, "bolts": 6}


def test_manufacturing_lighter_aluminum_route():
    op = ManufacturingDomain().build_operad()
    result = Wright(op, max_depth=6).optimize(Spec(("Aluminum", "Rubber"), "Bicycle"))
    assert result.construction.cost == {"aluminum": 3, "steel": 1, "rubber": 2, "bolts": 6}


def test_manufacturing_unbuildable_without_frame_material():
    op = ManufacturingDomain().build_operad()
    result = Wright(op, max_depth=6).optimize(Spec(("Rubber",), "Bicycle"))
    assert result.verdict != Verdict.BUILDABLE
