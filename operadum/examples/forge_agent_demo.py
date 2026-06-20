# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
OPERADUM Forge + Agent + Server demo (Layer 1 + Phase 5).

Run:  python -m examples.forge_agent_demo

The whole stack through one object:
  1. Boot a Forge host; the layers register as capabilities (DI in order).
  2. Load a domain in one line; the Agent designs, optimizes, certifies, audits.
  3. Round-trip the wiring DSL (string -> design -> run).
  4. Drive everything through the MCP-style SynthesisServer.
"""

from operadum.agent import Agent
from operadum.core.types import Spec
from operadum.core.serialization import to_wiring_dsl, parse_wiring
from operadum.wright.server import SynthesisServer
from operadum.domains.synthesis_design import SynthesisDesignDomain


def main():
    print("1) Boot Forge + load a domain in one line:")
    agent = Agent.for_domain(SynthesisDesignDomain())
    print("   ", agent)
    print("    capabilities:", agent.forge.capabilities_available)
    print()

    spec = Spec(inputs=("Benzene",), output="Paracetamol")
    build = agent.optimize(spec)
    print(f"2) Agent.optimize -> {build.construction.wiring}  cost={build.construction.cost}")
    cert = agent.certify(spec)
    print(f"   Agent.certify  -> {cert}")
    rt = agent.verify(build.construction.composite)
    print(f"   Agent.verify   -> {rt}")
    print()

    print("3) Wiring DSL round-trip:")
    dsl = to_wiring_dsl(build.construction.composite)
    print("    dsl:", dsl)
    rebuilt = parse_wiring(dsl, agent.operad)
    print("    parsed & run:", agent.operad.realize(rebuilt)("Benzene"))
    print()

    print("4) MCP-style server:")
    server = SynthesisServer(agent)
    print("    tools:", [t["name"] for t in server.tools()])
    resp = server.handle({"method": "optimize",
                          "params": {"inputs": ["Benzene"], "output": "Aniline"}})
    print("    optimize(Aniline) ->", resp["result"]["design"]["wiring"],
          resp["result"]["design"]["cost"])
    v = server.handle({"method": "verify",
                       "params": {"inputs": ["Benzene"], "output": "Paracetamol"}})
    print("    verify(Paracetamol) ->", v["result"]["verdict"], "engine", v["result"]["engine"])


if __name__ == "__main__":
    main()
