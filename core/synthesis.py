# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
CapabilityForge — synthesize REAL, executable capabilities behind two gates.

This is the non-superficial path: instead of writing graph shortcuts, the system
synthesizes a capability that *actually computes* the right answer, and only
keeps it if it survives two independent gates:

    EXAMPLE gate (behavioral) : run the candidate on input/output examples — does
                                it produce the right values? Type-correct ≠ correct.
    COG gate     (structural) : is there a mechanistic type-path input->output?
                                (the dual-narrator idea: behavior AND structure.)

A capability is *proposed* by a `Proposer`. Two are provided:

  • `OperadumProposer` — uses OPERADUM as the executable design substrate: it
    composes domain primitives (op.compose → op.realize) into a runnable artifact,
    selecting the composition that matches the examples (example-guided synthesis,
    PRONOIA-style "the program IS the explanation"). No LLM. Runs offline.

  • `HarnessProposer` — the LLM-as-implementer seam, with **Claude Code as the
    harness**. When OPERADUM can't compose a primitive solution (the task needs
    novel logic), the forge hands a structured `ImplementationRequest` to a
    `solver` callback. In live use the solver is the Claude Code session (me)
    writing the function body; in tests it's a plain Python callback. Either way
    the returned code is trusted ONLY after it passes the example + COG gates —
    which is what makes looping an LLM on your own code safe, and why a weak/slow
    model (or no local model at all) is fine: correctness is the gates' job.

The winner is hot-loaded onto the host (core.host) as a real executable
capability you can call: `await host.get_capability(name)(value)`.

Run:
    python -m core.synthesis
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from core.category import Category
from core.host import Host, Plugin, build_host

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Domain: typed, executable primitives + a capability spec
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Primitive:
    """A typed, executable build block.

    Single-input by default (`in_type`); for n-ary gates (e.g. NAND: Bit×Bit→Bit)
    set `in_types` and `fn` takes one positional arg per input. Use `gate(...)`.
    """
    name: str
    in_type: str
    out_type: str
    fn: Callable[..., Any]
    in_types: Optional[Tuple[str, ...]] = None

    @property
    def input_types(self) -> Tuple[str, ...]:
        return tuple(self.in_types) if self.in_types else (self.in_type,)

    @property
    def arity(self) -> int:
        return len(self.input_types)


def gate(name: str, in_types: Sequence[str], out_type: str,
         fn: Callable[..., Any]) -> Primitive:
    """Construct an n-ary primitive (a gate). `fn` takes one arg per input colour."""
    in_types = tuple(in_types)
    return Primitive(name=name, in_type=in_types[0] if in_types else "",
                     out_type=out_type, fn=fn, in_types=in_types)


@dataclass
class IOSpec:
    """What to build: an interface plus the examples that define correctness.

    For n-ary goals set `in_types`; each example input is then a tuple of args
    (e.g. ((0, 1), 1) for a 2-input gate). Single-input examples stay scalar.
    """
    name: str
    in_type: str
    out_type: str
    examples: List[Tuple[Any, Any]]
    in_types: Optional[Tuple[str, ...]] = None

    @property
    def input_types(self) -> Tuple[str, ...]:
        return tuple(self.in_types) if self.in_types else (self.in_type,)

    @property
    def arity(self) -> int:
        return len(self.input_types)


@dataclass
class ImplementationRequest:
    """A work-order handed to the LLM/harness when search can't compose a solution."""
    spec: IOSpec
    primitives: List[Primitive]

    def as_prompt(self) -> str:
        prims = ", ".join(
            f"{p.name}:{'×'.join(p.input_types)}->{p.out_type}" for p in self.primitives
        )
        exs = "; ".join(f"{inp!r}->{out!r}" for inp, out in self.spec.examples)
        args = ", ".join(chr(ord("a") + i) for i in range(self.spec.arity))
        sig = "×".join(self.spec.input_types)
        return (
            f"Implement Python `def solve({args}):` for capability '{self.spec.name}' "
            f"({sig} -> {self.spec.out_type}).\n"
            f"It MUST satisfy every example (input -> output): {exs}\n"
            f"Available primitives (for reference): {prims}\n"
            f"Return only the function source."
        )


@dataclass
class Candidate:
    """A proposed implementation: a runnable fn plus where it came from."""
    fn: Callable[[Any], Any]
    source: str          # "operadum" | "harness"
    route: str           # human-readable design (composition or "llm:<note>")


# ══════════════════════════════════════════════════════════════════════════════
# Gates
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class GateReport:
    example_pass: bool
    example_failures: List[str]
    cog_verdict: str

    @property
    def accepted(self) -> bool:
        # Behavior must be correct; COG must not actively reject the structure.
        return self.example_pass and self.cog_verdict != "REJECT"


def example_check(fn: Callable[..., Any], spec: IOSpec) -> Tuple[bool, List[str]]:
    failures: List[str] = []
    nary = spec.arity > 1
    for inp, expected in spec.examples:
        try:
            got = fn(*inp) if nary else fn(inp)
        except Exception as exc:  # a crashing candidate fails the gate
            failures.append(f"{inp!r}: raised {exc!r}")
            continue
        if got != expected:
            failures.append(f"{inp!r}: got {got!r}, expected {expected!r}")
    return (not failures), failures


class _CogGate:
    """COG verdict on the structural claim in_type --synthesizes--> out_type."""

    def __init__(self, category: Category):
        from cog.session import CogSession
        from cog.engine import CogEngine
        self._engine = CogEngine(CogSession(category=category))

    def verdict(self, in_type: str, out_type: str, confidence: float = 0.7) -> str:
        from cog.schema import CogClaim
        claim = CogClaim(source=in_type, target=out_type,
                         relation="synthesizes", confidence=confidence)
        try:
            return self._engine.check_claim(claim).status.name
        except Exception:
            logger.exception("COG verification failed for %s->%s", in_type, out_type)
            return "error"


# ══════════════════════════════════════════════════════════════════════════════
# Proposers
# ══════════════════════════════════════════════════════════════════════════════

class Proposer:
    """Proposes a Candidate implementation for a spec, or None."""
    name = "proposer"

    def propose(self, spec: IOSpec, primitives: Sequence[Primitive]) -> Optional[Candidate]:
        raise NotImplementedError


def _load_operadum():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    operadum_root = os.path.join(repo_root, "operadum")
    if operadum_root not in sys.path:
        sys.path.insert(0, operadum_root)
    try:
        from operadum import Operad, Spec, Wright
        return Operad, Spec, Wright
    except Exception as exc:  # pragma: no cover
        logger.debug("OPERADUM unavailable: %s", exc)
        return None, None, None


def _load_diagram_synth():
    try:
        from operadum.gate.diagram_synth import synthesize_diagram, truth_table_validator
        return synthesize_diagram, truth_table_validator
    except Exception:  # pragma: no cover
        return None


class OperadumProposer(Proposer):
    """Example-guided synthesis over domain primitives, realized by OPERADUM.

    Two strategies, smallest-first:
      • unary chains (compose single-input primitives), and
      • typed DAGs via OPERADUM's `synthesize_diagram` — networks with fan-out and
        n-ary gates the tree path can't express (e.g. XOR from NAND alone).
    """
    name = "operadum"

    def __init__(self, max_depth: int = 4, diagram_nodes: int = 6):
        self.max_depth = max_depth
        self.diagram_nodes = diagram_nodes

    def propose(self, spec: IOSpec, primitives: Sequence[Primitive]) -> Optional[Candidate]:
        Operad, Spec, Wright = _load_operadum()
        prims = list(primitives)
        op, op_by_name = self._build_operad(Operad, spec, prims)

        # Unary composition path: chains of single-input primitives. (No Wright
        # verdict here — it runs a tree search that diverges on cyclic types like
        # Bit→Bit; a returned candidate is example-verified buildable anyway.)
        if spec.arity == 1:
            chain = self._search(spec, prims)
            if chain is not None:
                route = "->".join([spec.in_type] + [p.out_type for p in chain])
                fn = self._realize(op, chain, op_by_name) if op is not None \
                    else self._python_compose(chain)
                return Candidate(fn=fn, source="operadum",
                                 route=f"{route} [OPERADUM composed]")

        # Diagram path: typed DAGs with fan-out. Handles n-ary gates and
        # single-input goals that need wire reuse (NOT = NAND(a, a)).
        if op is not None:
            return self._diagram_propose(op, spec)
        return None

    @staticmethod
    def _build_operad(Operad, spec: IOSpec, prims: List[Primitive]):
        if Operad is None:
            return None, {}
        op = Operad(f"domain-{spec.name}")
        op_by_name: Dict[str, Any] = {}
        for p in prims:
            op_by_name[p.name] = op.add_op(
                p.name, list(p.input_types), p.out_type, cost={"steps": 1}, fn=p.fn
            )
        return op, op_by_name

    def _search(self, spec: IOSpec, prims: List[Primitive]) -> Optional[List[Primitive]]:
        """BFS over typed unary compositions; first chain matching all examples."""
        frontier: List[Tuple[str, List[Primitive]]] = [(spec.in_type, [])]
        while frontier:
            cur_type, chain = frontier.pop(0)
            if len(chain) > self.max_depth:
                continue
            for p in prims:
                if p.arity != 1 or p.in_type != cur_type:
                    continue
                new_chain = chain + [p]
                if p.out_type == spec.out_type:
                    fn = self._python_compose(new_chain)
                    ok, _ = example_check(fn, spec)
                    if ok:
                        return new_chain
                if len(new_chain) <= self.max_depth:
                    frontier.append((p.out_type, new_chain))
        return None

    def _diagram_propose(self, op: Any, spec: IOSpec) -> Optional[Candidate]:
        synth = _load_diagram_synth()
        if synth is None:
            return None
        synthesize_diagram, truth_table_validator = synth

        names = [f"in{i}" for i in range(spec.arity)]
        inputs = list(zip(names, spec.input_types))
        table = []
        for inp, out in spec.examples:
            vals = (inp,) if spec.arity == 1 else tuple(inp)
            table.append(({n: v for n, v in zip(names, vals)}, out))

        try:
            vd = synthesize_diagram(op, inputs, spec.out_type,
                                    truth_table_validator(table),
                                    max_nodes=self.diagram_nodes)
        except Exception:
            logger.debug("diagram synthesis failed", exc_info=True)
            return None
        if vd is None:
            return None

        artifact = vd.artifact

        def fn(*args, _a=artifact, _n=names):
            return _a(**dict(zip(_n, args)))

        return Candidate(fn=fn, source="operadum",
                         route=f"diagram[{vd.nodes} gates]: {vd.wiring}")

    @staticmethod
    def _python_compose(chain: List[Primitive]) -> Callable[[Any], Any]:
        def fn(x: Any) -> Any:
            for p in chain:
                x = p.fn(x)
            return x
        return fn

    @staticmethod
    def _realize(op: Any, chain: List[Primitive],
                 op_by_name: Dict[str, Any]) -> Callable[[Any], Any]:
        """Build the OPERADUM composite for this chain and realize it to an artifact.

        compose(outer, 0, inner) plugs `inner` into the 0-th open input of `outer`,
        so folding p1, p2, p3 gives p3∘p2∘p1 : in_type -> out_type.
        """
        try:
            composite = op_by_name[chain[0].name]
            for nxt in chain[1:]:
                composite = op.compose(op_by_name[nxt.name], 0, composite)
            return op.realize(composite)
        except Exception:
            logger.debug("OPERADUM realize failed; using python compose", exc_info=True)
            return OperadumProposer._python_compose(chain)


class HarnessProposer(Proposer):
    """LLM-as-implementer seam. `solver(request) -> python source for def solve(x)`.

    In live use the solver is the Claude Code harness (me). In tests it is a
    deterministic callback. The returned code is gated before it is ever trusted.
    """
    name = "harness"

    def __init__(self, solver: Optional[Callable[[ImplementationRequest], str]] = None,
                 note: str = "harness"):
        self.solver = solver
        self.note = note

    def propose(self, spec: IOSpec, primitives: Sequence[Primitive]) -> Optional[Candidate]:
        if self.solver is None:
            return None
        request = ImplementationRequest(spec=spec, primitives=list(primitives))
        source = self.solver(request)
        if not source:
            return None
        fn = self._compile_solve(source)
        if fn is None:
            return None
        return Candidate(fn=fn, source="harness", route=f"llm:{self.note}")

    @staticmethod
    def _compile_solve(source: str) -> Optional[Callable[[Any], Any]]:
        """Exec returned source and extract `solve`. Research-grade, not a sandbox:
        the example + COG gates are what establish trust, not this exec."""
        safe_builtins = {
            "len": len, "sum": sum, "min": min, "max": max, "sorted": sorted,
            "range": range, "enumerate": enumerate, "map": map, "filter": filter,
            "set": set, "list": list, "dict": dict, "tuple": tuple, "str": str,
            "int": int, "float": float, "bool": bool, "abs": abs, "any": any,
            "all": all, "zip": zip, "reversed": reversed,
        }
        ns: Dict[str, Any] = {"__builtins__": safe_builtins}
        try:
            exec(compile(source, "<harness-solve>", "exec"), ns)
        except Exception:
            logger.exception("harness source failed to compile")
            return None
        fn = ns.get("solve")
        return fn if callable(fn) else None


# ══════════════════════════════════════════════════════════════════════════════
# The forge
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SynthesisResult:
    spec: IOSpec
    candidate: Optional[Candidate]
    gate: Optional[GateReport]
    loaded: bool
    capability: str
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.loaded and self.gate is not None and self.gate.accepted


class _CapabilityPlugin(Plugin):
    """Hot-loadable wrapper exposing a synthesized fn as a callable capability."""

    def __init__(self, cap_name: str, fn: Callable[[Any], Any]):
        super().__init__(name=cap_name, provides=[cap_name])
        self._fn = fn

    def capabilities(self) -> Dict[str, Any]:
        return {self.name: self._fn}


class CapabilityForge:
    """Propose → gate (examples + COG) → hot-load a real executable capability."""

    def __init__(self, primitives: Sequence[Primitive], *,
                 host: Optional[Host] = None,
                 category: Optional[Category] = None,
                 proposers: Optional[Sequence[Proposer]] = None):
        self.primitives = list(primitives)
        self.host = host or build_host()
        self.category = category or self._category_from_primitives(self.primitives)
        self.proposers = list(proposers) if proposers else [OperadumProposer()]
        self._cog = _CogGate(self.category)

    @staticmethod
    def _category_from_primitives(primitives: Sequence[Primitive]) -> Category:
        # Mirror primitives as type-edges so COG has structure to reason over.
        # Each input colour of an n-ary gate gets an edge to the output colour.
        cat = Category(db_path=":memory:")
        for p in primitives:
            for in_type in p.input_types:
                cat.connect(in_type, p.out_type, name=p.name, confidence=0.9)
        return cat

    async def synthesize(self, spec: IOSpec) -> SynthesisResult:
        for proposer in self.proposers:
            candidate = proposer.propose(spec, self.primitives)
            if candidate is None:
                continue

            passed, failures = example_check(candidate.fn, spec)
            cog = self._cog.verdict(spec.in_type, spec.out_type)
            gate = GateReport(example_pass=passed, example_failures=failures,
                              cog_verdict=cog)

            if not gate.accepted:
                logger.info("[%s] %s rejected: examples=%s cog=%s",
                            proposer.name, spec.name, passed, cog)
                continue  # try the next proposer

            await self.host.register_plugin(_CapabilityPlugin(spec.name, candidate.fn))
            return SynthesisResult(spec, candidate, gate, loaded=True,
                                   capability=spec.name,
                                   note=f"by {proposer.name}: {candidate.route}")

        return SynthesisResult(spec, None, None, loaded=False, capability=spec.name,
                               note="no proposer produced an accepted candidate")


# ══════════════════════════════════════════════════════════════════════════════
# Demo
# ══════════════════════════════════════════════════════════════════════════════

TEXT_PRIMITIVES = [
    Primitive("tokenize", "Text", "Tokens", str.split),
    Primitive("word_len", "Tokens", "Int", len),
    Primitive("char_count", "Text", "Int", len),     # type-correct Text->Int, wrong for word_count
    Primitive("upper", "Text", "Text", str.upper),
]


def _demo_solver(request: ImplementationRequest) -> str:
    """Stand-in for the Claude Code harness: writes the novel function it's asked for.

    In live use, this is the LLM session reading request.as_prompt() and replying
    with code. Here we answer the one novel task (vowel counting) directly."""
    if request.spec.name == "vowel_count":
        return "def solve(s):\n    return sum(1 for c in s.lower() if c in 'aeiou')\n"
    return ""


async def _demo() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    forge = CapabilityForge(
        TEXT_PRIMITIVES,
        proposers=[OperadumProposer(), HarnessProposer(solver=_demo_solver)],
    )
    print(f"host backend: {getattr(forge.host, 'backend', '?')}\n")

    specs = [
        IOSpec("word_count", "Text", "Int",
               [("a b c", 3), ("hello world there", 3), ("x", 1)]),
        IOSpec("vowel_count", "Text", "Int",
               [("hello", 2), ("sky", 0), ("aeiou", 5)]),
    ]

    for spec in specs:
        res = await forge.synthesize(spec)
        if res.ok:
            print(f"[BUILT] {spec.name:<12} examples=PASS  COG={res.gate.cog_verdict:<6} "
                  f"{res.note}")
        else:
            print(f"[FAIL ] {spec.name:<12} {res.note}")

    # Prove the synthesized capabilities are real and executable on NEW inputs.
    print("\nrunning the hot-loaded capabilities on fresh inputs:")
    for cap, arg in [("word_count", "the quick brown fox"), ("vowel_count", "education")]:
        fn = await forge.host.get_capability(cap)
        print(f"   {cap}({arg!r}) = {fn(arg) if fn else 'MISSING'}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_demo())
