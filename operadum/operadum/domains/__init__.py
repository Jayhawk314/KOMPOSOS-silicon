# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""OPERADUM domains: pluggable content (colours + operations + resource algebra)."""

from .base import DomainPlugin, GroundTruthCase
from .synthesis_design import SynthesisDesignDomain
from .compute_pipeline import ComputePipelineDomain
from .program_synthesis import ProgramSynthesisDomain
from .quantum_circuit import QuantumCircuitDomain
from .manufacturing import ManufacturingDomain
from .logic_circuit import LogicCircuitDomain
from .topological_network import TopologicalNetworkDomain
from .materials import MaterialsDomain

#: All built-in domains, by name -- the showcase / registry.
DOMAINS = {
    d.name: d for d in (
        SynthesisDesignDomain, ComputePipelineDomain, ProgramSynthesisDomain,
        QuantumCircuitDomain, ManufacturingDomain, LogicCircuitDomain,
        TopologicalNetworkDomain, MaterialsDomain,
    )
}

__all__ = [
    "DomainPlugin", "GroundTruthCase", "DOMAINS",
    "SynthesisDesignDomain", "ComputePipelineDomain",
    "ProgramSynthesisDomain", "QuantumCircuitDomain", "ManufacturingDomain",
    "LogicCircuitDomain", "TopologicalNetworkDomain", "MaterialsDomain",
]
