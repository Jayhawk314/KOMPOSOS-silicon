# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
WRIGHT Synthesis Server -- MCP-style tool interface (Phase 5)

A dependency-free, transport-agnostic server that exposes the OPERADUM design
surface as MCP-style tools. `handle(request)` dispatches a JSON-shaped request
to a method and returns a JSON-shaped response; `tools()` advertises the schema
for discovery. A real stdio/HTTP transport can wrap this without changing the
logic (mirror of COG's wright/server.py).

Tools:
  list_colours      -> the interface types currently known
  list_operations   -> the components currently known
  synthesize        -> energy-routed synthesis (first in-budget construction)
  optimize          -> cost-minimal in-budget construction (DAEDALUS)
  certify           -> Tier-4 certificate (coherence + soundness proofs)
  verify            -> KOMPOSOS round-trip verdict
  compile           -> the design as a KOMPOSOS morphism graph
"""

from __future__ import annotations
from typing import Any, Dict, List

from ..agent import Agent
from ..core.types import Spec
from ..core.serialization import design_to_json
from ..bridges.komposos_bridge import compile_to_komposos


class SynthesisServer:
    """Routes MCP-style requests to a backing Agent."""

    def __init__(self, agent: Agent = None):
        self.agent = agent or Agent()

    # ---------------- discovery ----------------

    def tools(self) -> List[Dict[str, Any]]:
        spec_params = {
            "inputs": "list[str] (input colours)",
            "output": "str (target colour)",
            "budget": "dict[str, number] (optional resource ceiling)",
        }
        return [
            {"name": "list_colours", "params": {}},
            {"name": "list_operations", "params": {}},
            {"name": "synthesize", "params": spec_params},
            {"name": "optimize", "params": spec_params},
            {"name": "certify", "params": spec_params},
            {"name": "verify", "params": spec_params},
            {"name": "compile", "params": spec_params},
        ]

    # ---------------- dispatch ----------------

    def handle(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch one request. Returns {ok, result} or {ok: False, error}."""
        method = request.get("method")
        params = request.get("params", {})
        handler = getattr(self, f"_do_{method}", None)
        if handler is None:
            return {"ok": False, "error": f"unknown method {method!r}"}
        try:
            return {"ok": True, "result": handler(params)}
        except Exception as exc:  # surface errors as data, never crash the server
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    # ---------------- methods ----------------

    def _do_list_colours(self, params: Dict[str, Any]) -> List[str]:
        return sorted(c.name for c in self.agent.operad.colours())

    def _do_list_operations(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"name": o.name, "inputs": list(o.inputs), "output": o.output,
             "cost": dict(o.cost)}
            for o in self.agent.operad.operations()
        ]

    def _spec(self, params: Dict[str, Any]) -> Spec:
        return Spec(
            inputs=tuple(params.get("inputs", [])),
            output=params["output"],
            budget=params.get("budget"),
        )

    def _build_payload(self, result) -> Dict[str, Any]:
        payload = {"verdict": result.verdict.value, "tier": result.tier,
                   "reason": result.reason}
        if result.construction is not None:
            payload["design"] = design_to_json(result.construction.composite,
                                               self.agent.operad)
        return payload

    def _do_synthesize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._build_payload(self.agent.synthesize(self._spec(params)))

    def _do_optimize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._build_payload(self.agent.optimize(self._spec(params)))

    def _do_certify(self, params: Dict[str, Any]) -> Dict[str, Any]:
        cert = self.agent.certify(self._spec(params))
        if cert is None:
            return {"certified": False, "reason": "not buildable"}
        return {
            "certified": cert.certified,
            "normal_form": cert.normal_form.to_wiring(),
            "unique": cert.unique,
            "conservation": cert.conservation.holds if cert.conservation else None,
            "linear_sound": cert.linear.ok if cert.linear else None,
        }

    def _do_optimize_then_verify(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._do_verify(params)

    def _do_verify(self, params: Dict[str, Any]) -> Dict[str, Any]:
        build = self.agent.optimize(self._spec(params))
        if not build.buildable:
            return {"verdict": "n/a", "reason": "not buildable"}
        rt = self.agent.verify(build.construction.composite)
        return {"verdict": rt.verdict, "sound": rt.sound,
                "composed_confidence": rt.composed_confidence,
                "expected_confidence": rt.expected_confidence, "engine": rt.engine}

    def _do_compile(self, params: Dict[str, Any]) -> Dict[str, Any]:
        build = self.agent.optimize(self._spec(params))
        if not build.buildable:
            return {"error": "not buildable"}
        graph = compile_to_komposos(build.construction.composite, self.agent.operad)
        return graph.to_dict()
