# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Diagrams -- typed DAGs / string diagrams (the network layer)

A Composite is a *tree*: one output, each input used once, fan-out only through
the limited PROP sharing. Real designs -- circuits, multi-input/multi-use
functions, MOF topologies, networks -- are *graphs*. A Diagram is the graph
form: a typed DAG of operation instances (a cospan / string diagram) with

  * NAMED boundary inputs, so two ports of the same colour are distinguishable
    (this is what trees could not do -- the "fan-out wall");
  * shared node outputs, so one result may feed many consumers (a true DAG);
  * sharing for free -- a node is COSTED ONCE and RUN ONCE, however many
    consumers it has.

This is the substrate for genuine network design (DAEDALUS Levels 3-4). It sits
beside Composite, not over it: trees remain the default; diagrams handle the
graph-shaped domains.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .types import Operation, ResourceValue
from .enrichment import ResourceMonoid


@dataclass(frozen=True)
class Source:
    """A wire endpoint: a boundary input (`in`) or a node's output (`node`)."""
    kind: str   # "in" | "node"
    ref: str    # input name | node id

    def __str__(self) -> str:
        return self.ref


class Diagram:
    """A typed DAG of operation instances with named boundary inputs."""

    def __init__(self, name: str = "diagram"):
        self.name = name
        self._inputs: List[Tuple[str, str]] = []        # ordered (name, colour)
        self._input_colour: Dict[str, str] = {}
        self._nodes: Dict[str, Tuple[Operation, List[Source]]] = {}
        self._output: Optional[Source] = None
        self._counter = 0

    # ---------------- construction ----------------

    def add_input(self, name: str, colour: str) -> Source:
        """Declare a named boundary input of a given colour. Returns its Source."""
        if name in self._input_colour:
            raise ValueError(f"duplicate input name {name!r}")
        self._inputs.append((name, colour))
        self._input_colour[name] = colour
        return Source("in", name)

    def add_node(self, op: Operation, sources: List[Source]) -> Source:
        """Wire `op`'s inputs from `sources` (one per input slot). Returns the
        node's output Source, which may feed any number of later nodes."""
        if len(sources) != op.arity:
            raise TypeError(
                f"{op.name} has arity {op.arity}, got {len(sources)} sources")
        nid = f"{op.name}#{self._counter}"
        self._counter += 1
        self._nodes[nid] = (op, list(sources))
        return Source("node", nid)

    def set_output(self, source: Source) -> "Diagram":
        self._output = source
        return self

    # ---------------- typing ----------------

    def colour_of(self, source: Source) -> str:
        if source.kind == "in":
            return self._input_colour[source.ref]
        op, _ = self._nodes[source.ref]
        return op.output

    def type_check(self) -> bool:
        """Every wire connects matching colours; an output is set. Raises on error."""
        if self._output is None:
            raise ValueError("diagram has no output")
        for nid, (op, sources) in self._nodes.items():
            for slot, (want, src) in enumerate(zip(op.inputs, sources)):
                got = self.colour_of(src)
                if got != want:
                    raise TypeError(
                        f"node {nid} input {slot} expects {want!r}, "
                        f"wired from {src.ref!r}:{got!r}")
        return True

    @property
    def output(self) -> str:
        return self.colour_of(self._output)

    @property
    def interface(self):
        from .types import Interface
        return Interface(tuple(c for _n, c in self._inputs), self.output)

    def input_names(self) -> List[str]:
        return [n for n, _c in self._inputs]

    # ---------------- resources ----------------

    def cost(self, monoid: ResourceMonoid) -> ResourceValue:
        """Total cost = each DISTINCT node counted once -- sharing is free."""
        total = dict(monoid.unit)
        for _nid, (op, _s) in self._nodes.items():
            total = monoid.combine(total, op.cost)
        return total

    # ---------------- execution ----------------

    def realize(self) -> Callable:
        """A callable(**inputs) -> output value. Each node runs once (memoised),
        so a shared sub-result is computed a single time."""
        for op, _s in self._nodes.values():
            if op._fn is None:
                raise ValueError(f"operation {op.name!r} has no callable")

        def artifact(**inputs: Any):
            missing = set(self._input_colour) - set(inputs)
            if missing:
                raise TypeError(f"missing inputs: {sorted(missing)}")
            memo: Dict[str, Any] = {}

            def evaluate(src: Source) -> Any:
                if src.kind == "in":
                    return inputs[src.ref]
                if src.ref in memo:
                    return memo[src.ref]
                op, sources = self._nodes[src.ref]
                value = op._fn(*[evaluate(s) for s in sources])
                memo[src.ref] = value
                return value

            return evaluate(self._output)

        artifact.interface = self.interface       # type: ignore[attr-defined]
        return artifact

    # ---------------- graph view (for topological validators) ----------------

    def graph_metrics(self) -> Dict[str, int]:
        """Underlying-graph invariants. Vertices = inputs + nodes; edges = wires.
        cycle_rank (first Betti number) = edges - vertices + components."""
        vertices = set(self._input_colour) | set(self._nodes)
        edges = 0
        adj: Dict[str, set] = {v: set() for v in vertices}
        for nid, (_op, sources) in self._nodes.items():
            for src in sources:
                edges += 1
                adj[src.ref].add(nid)
                adj[nid].add(src.ref)
        # connected components over the (undirected) wiring graph
        seen: set = set()
        components = 0
        for v in vertices:
            if v in seen:
                continue
            components += 1
            stack = [v]
            while stack:
                u = stack.pop()
                if u in seen:
                    continue
                seen.add(u)
                stack.extend(adj[u] - seen)
        return {
            "nodes": len(self._nodes),
            "inputs": len(self._input_colour),
            "vertices": len(vertices),
            "edges": edges,
            "components": components,
            "cycle_rank": edges - len(vertices) + components,
        }

    def to_wiring(self) -> str:
        """A readable rendering: output = expression with shared nodes labelled."""
        def render(src: Source) -> str:
            if src.kind == "in":
                return src.ref
            op, sources = self._nodes[src.ref]
            return f"{op.name}({', '.join(render(s) for s in sources)})"
        return render(self._output) if self._output else "<no output>"

    def __repr__(self) -> str:
        m = self.graph_metrics()
        return (f"Diagram({self.name!r}, inputs={self.input_names()}, "
                f"nodes={m['nodes']}, cycle_rank={m['cycle_rank']})")
