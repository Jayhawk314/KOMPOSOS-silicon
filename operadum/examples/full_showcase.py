# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
OPERADUM full showcase -- eight domains, three design paradigms.

Run:  python -m examples.full_showcase

  cost-optimal design   (additive / max / multiset)  -> chem route, pipeline, BOM
  design by behaviour    (examples / unitaries)        -> a program, a quantum circuit
  network design         (the DAG layer)               -> XOR from NAND, a topology
  materials              (real linker data + KOMPOSOS) -> the lightest viable MOF
"""

from operadum.core.types import Spec
from operadum.wright.engine import Wright
from operadum.gate.semantic_gate import SemanticGate
from operadum.gate.diagram_synth import synthesize_diagram, truth_table_validator
from operadum.bridges.round_trip import KomposVerifier
from operadum.domains.synthesis_design import SynthesisDesignDomain
from operadum.domains.compute_pipeline import ComputePipelineDomain
from operadum.domains.manufacturing import ManufacturingDomain
from operadum.domains.program_synthesis import ProgramSynthesisDomain
from operadum.domains.quantum_circuit import QuantumCircuitDomain, phase_equal, IDENTITY, X
from operadum.domains.logic_circuit import LogicCircuitDomain
from operadum.domains.topological_network import TopologicalNetworkDomain
from operadum.domains.materials import MaterialsDomain


def line(label, body):
    print(f"  {label:22s} {body}")


def cost_optimal():
    print("== Cost-optimal design (three resource algebras) ==")
    for domain, spec in [
        (SynthesisDesignDomain(), Spec(("Benzene",), "Paracetamol")),
        (ComputePipelineDomain(), Spec(("RawLog",), "Report")),
        (ManufacturingDomain(),   Spec(("Steel", "Rubber"), "Bicycle")),
    ]:
        op = domain.build_operad()
        r = Wright(op, max_depth=8).optimize(spec)
        line(domain.name, f"{r.construction.wiring}  cost={r.construction.cost}")
    print()


def by_behaviour():
    print("== Design by behaviour (verified independently) ==")
    op = ProgramSynthesisDomain().build_operad()
    d = SemanticGate(op, 5).by_examples(Spec(("String",), "Int"),
                                        [("a b c", 3), ("x y", 2)])
    line("program (by example)", f"{d.wiring}  ->  run('hi there') = {d.artifact('hi there')}")

    qop = QuantumCircuitDomain(gates=["H", "Z", "S", "T"]).build_operad()
    qd = SemanticGate(qop, 4).synthesize(
        Spec(("Qubit",), "Qubit"),
        validator=lambda art, c: phase_equal(art(IDENTITY), X))
    line("quantum (to unitary X)", f"{qd.wiring}  unitary_ok={phase_equal(qd.artifact(IDENTITY), X)}")
    print()


def network_design():
    print("== Network design (the DAG layer fixes the fan-out wall) ==")
    lop = LogicCircuitDomain().build_operad()
    _, ins, table = next(t for t in LogicCircuitDomain().targets() if t[0] == "XOR")
    xor = synthesize_diagram(lop, ins, "Bit", truth_table_validator(table),
                             gate_ops=["nand"], max_nodes=4)
    line("XOR from NAND", f"{xor.nodes} gates, truth-table verified, "
                          f"cycle_rank={xor.diagram.graph_metrics()['cycle_rank']}")

    tdom = TopologicalNetworkDomain()
    top = synthesize_diagram(tdom.build_operad(), [("s", "Node")], "Node",
                             tdom.cycle_rank(1), max_nodes=3)
    line("fault-tolerant net", f"cycle_rank={top.diagram.graph_metrics()['cycle_rank']} "
                               f"(1 redundant path), nodes={top.nodes}")
    print()


def materials():
    print("== Materials: design a MOF from real linker data, audited by KOMPOSOS ==")
    dom = MaterialsDomain(limit=5)
    op = dom.build_operad()
    r = Wright(op, max_depth=4).optimize(Spec((), "MOF"))
    mof = r.construction.artifact()
    line("lightest viable MOF", f"{r.construction.wiring}  MW={mof['linker']['mw']}")
    line("  linker SMILES", mof["linker"]["smiles"])
    rt = KomposVerifier().verify(r.construction.composite, op)
    line("  KOMPOSOS round-trip", f"{rt.verdict} (sound={rt.sound})")
    net = dom.mof_net(op, "node_Zn4O", ["linker_2", "linker_3", "linker_4"])
    line("  as a topological net", f"metal hub coordinating 3 linkers, "
                                   f"nodes={net.graph_metrics()['nodes']}")


if __name__ == "__main__":
    cost_optimal()
    by_behaviour()
    network_design()
    materials()
    print("Eight domains, one operadic substrate. Trees AND networks. Toy data AND real linkers.")
