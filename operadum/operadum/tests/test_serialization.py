# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Phase 5 tests: wiring DSL round-trip + JSON serialization + MCP-style server.
"""

import pytest

from operadum.core.operad import Operad
from operadum.core.types import Spec
from operadum.core.serialization import to_wiring_dsl, parse_wiring, design_to_json
from operadum.wright.engine import Wright
from operadum.wright.server import SynthesisServer
from operadum.agent import Agent
from operadum.domains.synthesis_design import SynthesisDesignDomain


def pipe_operad():
    op = Operad("pipe")
    op.add_op("tok", ["RawText"], "Tokens", cost={"ms": 2}, fn=lambda s: s.split())
    op.add_op("embed", ["Tokens"], "Embedding", cost={"ms": 8}, fn=len)
    op.add_op("merge", ["Embedding", "Embedding"], "Embedding", cost={"ms": 1},
              fn=lambda a, b: a + b)
    return op


# ---------------------------------------------------------------- wiring DSL

def test_wiring_dsl_round_trips_a_chain():
    op = pipe_operad()
    design = Wright(op).synthesize(Spec(inputs=("RawText",), output="Embedding")).construction
    dsl = to_wiring_dsl(design.composite)
    assert dsl == "embed(tok(RawText))"
    rebuilt = parse_wiring(dsl, op)
    assert rebuilt.to_wiring() == dsl
    assert rebuilt.interface == design.composite.interface
    # And it still runs.
    assert op.realize(rebuilt)("a b c") == 3


def test_wiring_dsl_round_trips_branching():
    op = pipe_operad()
    rebuilt = parse_wiring("merge(embed(tok(RawText)), embed(tok(RawText)))", op)
    assert rebuilt.open_inputs() == ["RawText", "RawText"]
    assert rebuilt.cost(op.monoid) == {"ms": 21}
    assert op.realize(rebuilt)("a b", "c d e") == 5


def test_design_to_json():
    op = pipe_operad()
    design = Wright(op).synthesize(Spec(inputs=("RawText",), output="Embedding")).construction
    record = design_to_json(design.composite, op)
    assert record["wiring"] == "embed(tok(RawText))"
    assert record["output"] == "Embedding"
    assert record["cost"] == {"ms": 10}
    assert record["operations"] == ["embed", "tok"]


# ---------------------------------------------------------------- MCP server

def test_server_lists_and_synthesizes():
    server = SynthesisServer(Agent.for_domain(SynthesisDesignDomain()))
    cols = server.handle({"method": "list_colours"})
    assert cols["ok"] and "Paracetamol" in cols["result"]

    resp = server.handle({"method": "optimize",
                          "params": {"inputs": ["Benzene"], "output": "Paracetamol"}})
    assert resp["ok"]
    assert resp["result"]["verdict"] == "BUILDABLE"
    assert resp["result"]["design"]["cost"] == {"usd": 26}


def test_server_verify_and_compile():
    server = SynthesisServer(Agent.for_domain(SynthesisDesignDomain()))
    v = server.handle({"method": "verify",
                       "params": {"inputs": ["Benzene"], "output": "Paracetamol"}})
    assert v["ok"] and v["result"]["verdict"] == "AGREE"

    c = server.handle({"method": "compile",
                       "params": {"inputs": ["Benzene"], "output": "Paracetamol"}})
    assert c["ok"] and c["result"]["root"] == "Paracetamol"


def test_server_unknown_method_and_tools():
    server = SynthesisServer()
    assert {t["name"] for t in server.tools()} >= {"synthesize", "optimize", "verify"}
    bad = server.handle({"method": "nope"})
    assert not bad["ok"] and "unknown method" in bad["error"]
