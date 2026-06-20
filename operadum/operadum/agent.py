# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
The OPERADUM Agent -- the unified entry point

Wires every layer through Forge into one object (master spec S17:
forge_tekton_wright/agent.py). The Agent boots a Forge with the component
store, synthesizer (WRIGHT), search (DAEDALUS), and coherence (Polytope)
plugins, then exposes a small, friendly surface:

    agent = Agent.for_domain(SynthesisDesignDomain())
    agent.optimize(Spec(("Benzene",), "Paracetamol"))     # cheapest route
    agent.certify(spec)                                    # Tier-4 certificate
    agent.verify(design)                                   # KOMPOSOS round-trip

"Add a domain in one line" (S18): agent.add_domain(MyDomain()).
"""

from __future__ import annotations
from typing import Any, List, Optional

from .core.operad import Operad
from .core.enrichment import ResourceMonoid, ADDITIVE_COST
from .core.types import Spec, Composite
from .forge.core import Forge
from .forge.plugins import (
    ComponentStorePlugin, WrightPlugin, DaedalusPlugin, PolytopePlugin,
)
from .wright.schema import BuildResult, Certificate
from .daedalus_core import SearchResult
from .gate.pattern_miner import PatternMiner
from .gate.self_observer import SelfObserver, SelfReport
from .bridges.round_trip import KomposVerifier, RoundTripResult


class Agent:
    """One object that owns a Forge with all OPERADUM layers wired in."""

    def __init__(self, name: str = "operadum", monoid: ResourceMonoid = None,
                 wright_depth: int = 6, search_depth: int = 8):
        self.forge = Forge(name)
        self._store = ComponentStorePlugin(name, monoid=monoid or ADDITIVE_COST)
        (self.forge
            .register(self._store)
            .register(WrightPlugin(max_depth=wright_depth))
            .register(DaedalusPlugin(max_depth=search_depth))
            .register(PolytopePlugin())
            .start())
        self.miner = PatternMiner(self.operad)

    @classmethod
    def for_domain(cls, domain, **kwargs) -> "Agent":
        """Boot an agent over a domain's resource algebra and load its content."""
        agent = cls(name=domain.name, monoid=domain.resource_algebra(), **kwargs)
        agent.add_domain(domain)
        return agent

    # ---------------- capabilities ----------------

    @property
    def operad(self) -> Operad:
        return self.forge.capability("component_store")

    @property
    def wright(self):
        return self.forge.capability("synthesizer")

    @property
    def daedalus(self):
        return self.forge.capability("search")

    @property
    def polytope(self):
        return self.forge.capability("coherence")

    # ---------------- domain content ----------------

    def add_domain(self, domain) -> "Agent":
        """Load a domain's colours + operations into the component store."""
        domain.load_into(self.operad)
        self.forge.emit("domain.loaded", domain=domain.name,
                        operations=len(domain.operations()))
        return self

    # ---------------- design surface ----------------

    def synthesize(self, spec: Spec) -> BuildResult:
        result = self.wright.synthesize(spec)
        self.miner.record_result(result)
        self.forge.emit("design.synthesized", spec=str(spec.interface),
                        verdict=result.verdict.value)
        return result

    def optimize(self, spec: Spec) -> BuildResult:
        result = self.wright.optimize(spec)
        self.miner.record_result(result)
        self.forge.emit("design.optimized", spec=str(spec.interface),
                        verdict=result.verdict.value)
        return result

    def search(self, spec: Spec) -> SearchResult:
        return self.daedalus.search(spec)

    def certify(self, spec: Spec) -> Optional[Certificate]:
        return self.wright.certify(spec, polytope=self.polytope)

    def verify(self, design: Composite, komposos_path: str = None) -> RoundTripResult:
        """Audit a design through the KOMPOSOS round-trip."""
        return KomposVerifier(komposos_path=komposos_path).verify(design, self.operad)

    # ---------------- self-construction ----------------

    def observe(self) -> SelfReport:
        return SelfObserver(self.operad).observe()

    def self_extend(self) -> List[Any]:
        """Mine the agent's build history and promote reusable components."""
        lifted = self.miner.auto_lift()
        for op in lifted:
            self.forge.emit("component.learned", name=op.name)
        return lifted

    def __repr__(self) -> str:
        return (f"Agent(forge={self.forge.name!r}, "
                f"capabilities={self.forge.capabilities_available}, "
                f"operations={len(self.operad.operations())})")
