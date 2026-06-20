# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
OPERADUM design showcase -- five domains, one substrate, verified results.

Run:  python -m examples.design_showcase

Demonstrates the full reach of the design engine:
  * synthesis-design  (additive USD)       -- cheapest synthesis route
  * compute-pipeline  (max / peak memory)  -- lowest-bottleneck pipeline
  * manufacturing     (multiset / BOM)     -- lightest bill of materials
  * program-synthesis (verified by examples)   -- a CORRECT program, by behaviour
  * quantum-circuit   (verified by unitaries)  -- a CORRECT gate sequence

The last two are the real test of design potential: OPERADUM is given only a
target behaviour (input/output examples, or a target unitary) and a component
library, and it designs an artifact the validator then confirms independently.
The math used to verify lives in the domain (stdlib cmath), never in the core.
"""

from operadum.core.types import Spec
from operadum.wright.engine import Wright
from operadum.gate.semantic_gate import SemanticGate
from operadum.domains.synthesis_design import SynthesisDesignDomain
from operadum.domains.compute_pipeline import ComputePipelineDomain
from operadum.domains.manufacturing import ManufacturingDomain
from operadum.domains.program_synthesis import ProgramSynthesisDomain
from operadum.domains.quantum_circuit import QuantumCircuitDomain, phase_equal, IDENTITY


def optimize_domains():
    print("=== Cost-optimal design across three resource algebras ===")
    cases = [
        (SynthesisDesignDomain(), Spec(("Benzene",), "Paracetamol")),
        (ComputePipelineDomain(), Spec(("RawLog",), "Report")),
        (ManufacturingDomain(),   Spec(("Steel", "Rubber"), "Bicycle")),
    ]
    for domain, spec in cases:
        op = domain.build_operad()
        r = Wright(op, max_depth=8).optimize(spec)
        print(f"  [{domain.name:16s}] {spec.output:12s} <- {r.construction.wiring}")
        print(f"   {'':18s} algebra={op.monoid.name.split('(')[0]:16s} cost={r.construction.cost}")
    print()


def program_by_example():
    print("=== Program synthesis: designed from examples, verified by running ===")
    op = ProgramSynthesisDomain().build_operad()
    gate = SemanticGate(op, max_depth=5)
    for case in ProgramSynthesisDomain().ground_truth():
        ex = case.spec.constraints["examples"]
        d = gate.by_examples(case.spec, ex)
        ok = all(d.artifact(*( (a,) if not isinstance(a, tuple) else a)) == e for a, e in ex)
        print(f"  {case.name:32s} -> {d.wiring}")
        print(f"   {'':34s} examples {ex[:2]}  verified={ok}  (tried {d.candidates_tried})")
    print()


def quantum_synthesis():
    print("=== Quantum gate synthesis: designed to a unitary, verified by matrix ===")
    for case in QuantumCircuitDomain().ground_truth():
        target = case.spec.constraints["target"]
        library = case.spec.constraints["library"]
        op = QuantumCircuitDomain(gates=library).build_operad()
        d = SemanticGate(op, max_depth=4).synthesize(
            case.spec, validator=lambda art, c, _t=target: phase_equal(art(IDENTITY), _t))
        ok = phase_equal(d.artifact(IDENTITY), target)
        print(f"  {case.name:28s} -> {d.wiring:22s} gates={int(sum(d.cost.values()))}  unitary_ok={ok}")
    print()


if __name__ == "__main__":
    optimize_domains()
    program_by_example()
    quantum_synthesis()
    print("Five domains, one operadic substrate. The math doesn't know which domain it's in.")
