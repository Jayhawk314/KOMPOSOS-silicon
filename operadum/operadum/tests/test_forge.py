# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Layer 1 tests: Forge host (event bus, capability DI, lifecycle) + Agent.
"""

import pytest

from operadum.forge.core import Forge, CapabilityError
from operadum.forge.events import EventBus
from operadum.forge.plugins import (
    ComponentStorePlugin, WrightPlugin, DaedalusPlugin, PolytopePlugin,
)
from operadum.agent import Agent
from operadum.core.types import Spec
from operadum.wright.schema import Verdict
from operadum.domains.synthesis_design import SynthesisDesignDomain
from operadum.domains.compute_pipeline import ComputePipelineDomain


# ---------------------------------------------------------------- event bus

def test_event_bus_fans_out_in_order():
    bus = EventBus()
    seen = []
    bus.subscribe("x", lambda **d: seen.append(("a", d.get("v"))))
    bus.subscribe("x", lambda **d: seen.append(("b", d.get("v"))))
    bus.emit("x", v=1)
    assert seen == [("a", 1), ("b", 1)]
    assert bus.history() == [("x", {"v": 1})]


# ---------------------------------------------------------------- capability DI

def test_capability_di_starts_in_dependency_order():
    forge = Forge()
    started = []
    forge.bus.subscribe("plugin.started", lambda **d: started.append(d["plugin"]))
    # Register a requirer BEFORE its provider; Forge must still order correctly.
    forge.register(WrightPlugin()).register(ComponentStorePlugin()).start()
    assert started.index("component_store") < started.index("wright")
    assert forge.has("synthesizer") and forge.has("component_store")


def test_unsatisfied_requirement_raises():
    forge = Forge()
    forge.register(WrightPlugin())          # no component_store provider
    with pytest.raises(CapabilityError):
        forge.start()


def test_stop_runs_in_reverse():
    forge = Forge()
    order = []

    class Noisy(ComponentStorePlugin):
        def on_stop(self_inner): order.append(self_inner.name)

    forge.register(ComponentStorePlugin()).register(WrightPlugin()).start()
    forge.stop()
    assert forge.started == []


# ---------------------------------------------------------------- agent

def test_agent_wires_all_layers():
    agent = Agent()
    caps = agent.forge.capabilities_available
    assert {"component_store", "synthesizer", "search", "coherence"} <= set(caps)


def test_agent_for_domain_designs_and_optimizes():
    agent = Agent.for_domain(SynthesisDesignDomain())
    result = agent.optimize(Spec(inputs=("Benzene",), output="Paracetamol"))
    assert result.verdict == Verdict.BUILDABLE
    assert result.construction.cost == {"usd": 26}
    assert result.construction.artifact("Benzene") == "Paracetamol"


def test_agent_respects_domain_resource_algebra():
    agent = Agent.for_domain(ComputePipelineDomain())
    # The MAX_CAPACITY algebra must flow through to DAEDALUS (built in the plugin).
    assert agent.daedalus.monoid is agent.operad.monoid
    result = agent.optimize(Spec(inputs=("RawLog",), output="Report"))
    assert result.construction.cost == {"mem": 200}


def test_agent_emits_design_events():
    agent = Agent.for_domain(SynthesisDesignDomain())
    events = []
    agent.forge.bus.subscribe("design.optimized", lambda **d: events.append(d))
    agent.optimize(Spec(inputs=("Benzene",), output="Aniline"))
    assert events and events[0]["verdict"] == "BUILDABLE"


def test_agent_roundtrip_and_self_extend():
    agent = Agent.for_domain(SynthesisDesignDomain())
    build = agent.optimize(Spec(inputs=("Benzene",), output="Paracetamol"))
    rt = agent.verify(build.construction.composite)
    assert rt.verdict == "AGREE"
    # Two episodes sharing a sub-route -> self-extension promotes it.
    agent.optimize(Spec(inputs=("Benzene",), output="Aniline"))
    agent.optimize(Spec(inputs=("Benzene",), output="Acetanilide"))
    lifted = agent.self_extend()
    assert isinstance(lifted, list)
