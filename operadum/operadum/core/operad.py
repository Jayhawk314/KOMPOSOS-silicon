# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
The Fused Operadic Runtime

The constructive mirror of KOMPOSOS-IV's core/category.py. An Operad that IS:
  - An operadic structure (colours, operations, composition o_i, units)
  - A persistence layer (SQLite, automatic)
  - A resource-enriched structure (cost values over a monoid)
  - An executable structure (operations carry callables; composites run)
  - A hook-enabled runtime (events on structural changes)

KOMPOSOS's primitive is the morphism: relate two existing objects.
OPERADUM's primitive is the operation: a rule for building an output colour
out of input colours. Operadic composition o_i plugs the output of one
operation into the i-th input of another; the operad axioms (associativity
of o_i, equivariance, unitality) guarantee any well-typed tree is itself a
valid operation. The space of valid designs is the free operad on your
components, quotiented by your equations.

One class. Zero translation seams.

  KOMPOSOS:  Category.compose(f, g)   ->  morphism g.f   (interpret)
  OPERADUM:  Operad.compose(o, i, p)  ->  composite o_i  (construct)
"""

from __future__ import annotations
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Union

from .types import Colour, Operation, Composite, Interface, Slot
from .enrichment import ResourceMonoid, ResourceError, ADDITIVE_COST
from .persistence import SQLiteBackend
from .hooks import HookRegistry


# Things that can stand in for an operation in compose(): a saved op name, a
# live Operation, or an already-built Composite.
OpLike = Union[str, Operation, Composite]


class Operad:
    """
    The fused operadic runtime.

    Colours and operations persist automatically. Resource costs are intrinsic
    to operations. Composition enforces the operad laws, combines costs via the
    resource monoid, composes callables, and fires hooks.

    Usage:
        op = Operad("pipeline")
        op.add_colour("RawText"); op.add_colour("Tokens"); op.add_colour("Embedding")
        op.add_op("tokenize", ["RawText"], "Tokens",  cost={"ms": 2}, fn=str.split)
        op.add_op("embed",    ["Tokens"],  "Embedding", cost={"ms": 8}, fn=len)

        pipeline = op.compose("embed", 0, "tokenize")   # RawText -> Embedding
        pipeline.cost(op.monoid)                         # {"ms": 10}
        run = op.realize(pipeline)                       # an executable artifact
        run("a b c")                                     # embed(tokenize("a b c")) == 3
    """

    def __init__(
        self,
        name: str = "default",
        db_path: str = ":memory:",
        monoid: ResourceMonoid = None,
    ):
        self.name = name
        self.monoid = monoid or ADDITIVE_COST
        self._backend = SQLiteBackend(db_path)
        self._hooks = HookRegistry()

        # In-memory indexes
        self._colours: Dict[str, Colour] = {}
        self._operations: Dict[str, Operation] = {}      # by id
        # output colour -> list of operation ids that produce it (for search)
        self._by_output: Dict[str, List[str]] = defaultdict(list)

    # =================================================================
    # Colour operations (dual of Category object operations)
    # =================================================================

    def add_colour(self, name: str, **metadata) -> Colour:
        """Add an interface type. Persists, indexes, fires 'colour_added'."""
        colour = Colour(name=name, metadata=metadata)
        colour._operad = self
        self._backend.insert_colour(colour)
        self._colours[name] = colour
        self._hooks.fire("colour_added", colour=colour)
        return colour

    def get_colour(self, name: str) -> Optional[Colour]:
        if name in self._colours:
            return self._colours[name]
        colour = self._backend.get_colour(name)
        if colour:
            colour._operad = self
            self._colours[name] = colour
        return colour

    def colours(self) -> List[Colour]:
        if self._colours:
            return list(self._colours.values())
        return self._backend.list_colours()

    def remove_colour(self, name: str) -> bool:
        """Remove a colour and cascade to every operation that mentions it."""
        if name not in self._colours and self._backend.get_colour(name) is None:
            return False
        # Cascade in memory
        doomed = [
            oid for oid, o in self._operations.items()
            if o.output == name or name in o.inputs
        ]
        for oid in doomed:
            self._drop_operation_index(self._operations.pop(oid))
        colour = self._colours.pop(name, None)
        self._backend.delete_colour(name)
        self._hooks.fire("colour_removed", colour=colour, name=name)
        return True

    # =================================================================
    # Operation operations (dual of Category morphism operations)
    # =================================================================

    def add_operation(self, op: Operation) -> Operation:
        """
        Add a build rule. Auto-creates missing colours, persists, indexes,
        fires 'operation_added'.
        """
        for c in (*op.inputs, op.output):
            if self.get_colour(c) is None:
                self.add_colour(c)
        op._operad = self
        self._backend.insert_operation(op)
        self._operations[op.id] = op
        self._by_output[op.output].append(op.id)
        self._hooks.fire("operation_added", operation=op)
        return op

    def add_op(
        self,
        name: str,
        inputs: List[str],
        output: str,
        cost: Dict[str, Any] = None,
        fn: Callable = None,
        **metadata,
    ) -> Operation:
        """
        Shorthand for adding an operation.

        op.add_op("merge", ["Embedding", "Embedding"], "Embedding",
                  cost={"ms": 1}, fn=lambda a, b: a + b)
        """
        op = Operation(
            name=name,
            inputs=list(inputs),
            output=output,
            cost=dict(cost or {}),
            metadata=metadata,
            _fn=fn,
        )
        return self.add_operation(op)

    def get_op(self, ref: OpLike) -> Operation:
        """Resolve an op reference (id, name, or live Operation) to an Operation."""
        if isinstance(ref, Operation):
            return ref
        if isinstance(ref, Composite):
            raise TypeError("Expected an Operation, got a Composite")
        # ref is a str: try id, then by name
        if ref in self._operations:
            return self._operations[ref]
        for o in self._operations.values():
            if o.name == ref:
                return o
        op = self._backend.get_operation(ref)
        if op is not None:
            op._operad = self
            self._operations[op.id] = op
            self._by_output[op.output].append(op.id)
            return op
        raise KeyError(f"No operation named or identified by {ref!r}")

    def operations(self) -> List[Operation]:
        if self._operations:
            return list(self._operations.values())
        return self._backend.list_operations()

    def operations_producing(self, output: str) -> List[Operation]:
        """Every operation whose output colour is `output` (search primitive)."""
        if self._operations:
            return [o for o in self._operations.values() if o.output == output]
        return [o for o in self._backend.list_operations() if o.output == output]

    def remove_operation(self, ref: OpLike) -> bool:
        op = self.get_op(ref)
        if op.id not in self._operations:
            return False
        self._drop_operation_index(self._operations.pop(op.id))
        self._backend.delete_operation(op.id)
        self._hooks.fire("operation_removed", operation=op)
        return True

    def _drop_operation_index(self, op: Operation) -> None:
        ids = self._by_output.get(op.output, [])
        if op.id in ids:
            ids.remove(op.id)

    # =================================================================
    # Units (dual of identity morphisms)
    # =================================================================

    def identity(self, colour: str) -> Operation:
        """
        The identity operation 1_C : (C) -> C -- a two-sided unit for o_i.

        Not persisted by default (it is structural, like Category's identity
        hom-value); it carries the pass-through callable and zero cost.
        """
        if self.get_colour(colour) is None:
            self.add_colour(colour)
        return Operation(
            name=f"id_{colour}",
            inputs=[colour],
            output=colour,
            cost={},
            _fn=lambda x: x,
            _operad=self,
        )

    # =================================================================
    # Composition -- THE key operation (dual of Category.compose)
    # =================================================================

    def compose(self, outer: OpLike, i: int, inner: OpLike) -> Composite:
        """
        Operadic composition o_i: plug `inner` into the i-th OPEN input of
        `outer`. The dual of Category.compose, but tree-shaped and typed.

        Where III/IV split this across categorical + store + enriched layers,
        OPERADUM does it in one operation:
          1. Builds the composed wiring tree (operadic structure)
          2. Type-checks the plug: inner.output must equal the i-th open colour
          3. Combines costs lazily via the resource monoid (enrichment)
          4. Persists the composite (store)
          5. Fires the 'composed' hook (runtime)

        Args:
            outer: The receiving operation/composite.
            i:     Zero-based index into outer's OPEN input ports.
            inner: The operation/composite whose output feeds that port.

        Returns:
            The composite outer o_i inner.

        Raises:
            TypeError:  colour mismatch at the plug (type safety at build time).
            IndexError: i is out of range of outer's open inputs.
        """
        outer_c = self._as_composite(outer)
        inner_c = self._as_composite(inner)

        open_cols = outer_c.open_inputs()
        if not (0 <= i < len(open_cols)):
            raise IndexError(
                f"Open-input index {i} out of range; "
                f"{outer_c.head.name} has {len(open_cols)} open input(s)."
            )
        expected = open_cols[i]
        if inner_c.output != expected:
            raise TypeError(
                f"Cannot compose: input {i} of '{outer_c.head.name}' expects "
                f"colour '{expected}', but '{inner_c.head.name}' outputs "
                f"'{inner_c.output}'."
            )

        composed = self._fill_nth_open(outer_c, i, inner_c, counter=[0])
        self._persist_composite(composed)
        self._hooks.fire("composed", outer=outer_c, index=i, inner=inner_c,
                         result=composed)
        return composed

    def _as_composite(self, ref: OpLike) -> Composite:
        if isinstance(ref, Composite):
            return ref
        return self.get_op(ref).as_composite()

    def _fill_nth_open(self, node: Composite, target: int, sub: Composite,
                       counter: List[int]) -> Composite:
        """Rebuild `node`, replacing its `target`-th open port (DFS order) with
        `sub`. `counter[0]` tracks how many open ports we have passed."""
        new_slots: List[Slot] = []
        for kind, val in node.slots:
            if kind == "open":
                if counter[0] == target:
                    new_slots.append(("sub", sub))
                else:
                    new_slots.append((kind, val))
                counter[0] += 1
            else:  # "sub": recurse to keep counting open ports in order
                new_slots.append(("sub", self._fill_nth_open(val, target, sub, counter)))
        return Composite(node.head, new_slots)

    def _persist_composite(self, comp: Composite) -> None:
        iface = comp.interface
        # Type safety is enforced in compose(); resource SOUNDNESS is the RES
        # gate's job. A resource-unsound wiring (e.g. a linear token reused) is
        # still a well-typed structure, so we persist it with an unknown cost
        # rather than refusing to build it -- the gate reports the violation.
        try:
            cost = comp.cost(self.monoid)
        except ResourceError:
            cost = {}
        self._backend.insert_composite(
            comp_id=comp.to_wiring(),
            wiring=comp.to_wiring(),
            output=iface.output,
            inputs=list(iface.inputs),
            cost=cost,
        )

    def cost_of(self, comp: Composite) -> Dict[str, Any]:
        """Total resource value of a composite under this operad's monoid."""
        return comp.cost(self.monoid)

    # =================================================================
    # Execution (dual of Category's executable morphisms)
    # =================================================================

    def realize(self, comp: Union[Composite, Operation]) -> Callable:
        """
        Turn a composite into a runnable artifact -- synthesis output is
        executable, not descriptive.

        The returned callable takes one positional argument per OPEN input,
        left-to-right, and returns the composite's output value by threading
        each input to the correct leaf and composing the operations' callables.

        Raises:
            ValueError: if any operation in the tree lacks a callable (_fn).
        """
        comp = comp.as_composite() if isinstance(comp, Operation) else comp
        self._check_executable(comp)

        def artifact(*args):
            expected = comp.arity
            if len(args) != expected:
                raise TypeError(
                    f"Artifact expects {expected} argument(s) "
                    f"({', '.join(comp.open_inputs())}), got {len(args)}."
                )
            value, consumed = self._eval(comp, list(args))
            return value

        artifact.interface = comp.interface  # type: ignore[attr-defined]
        artifact.wiring = comp.to_wiring()    # type: ignore[attr-defined]
        self._hooks.fire("realized", composite=comp, artifact=artifact)
        return artifact

    def _check_executable(self, comp: Composite) -> None:
        for op in comp.operations():
            if op._fn is None:
                raise ValueError(
                    f"Operation '{op.name}' has no callable; cannot realize. "
                    f"Add it with fn=... to make the design executable."
                )

    def _eval(self, node: Composite, args: List[Any]):
        """Evaluate the tree on `args` (the open inputs). Returns (value, n_consumed)."""
        call_args: List[Any] = []
        idx = 0
        for kind, val in node.slots:
            if kind == "open":
                call_args.append(args[idx])
                idx += 1
            else:  # "sub"
                sub_value, consumed = self._eval(val, args[idx:])
                call_args.append(sub_value)
                idx += consumed
        return node.head._fn(*call_args), idx

    # =================================================================
    # Introspection
    # =================================================================

    @property
    def hooks(self) -> HookRegistry:
        return self._hooks

    def stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "colours": len(self.colours()),
            "operations": len(self.operations()),
            "monoid": self.monoid.name,
        }

    def __repr__(self) -> str:
        return (f"Operad(name={self.name!r}, colours={len(self._colours)}, "
                f"operations={len(self._operations)}, monoid={self.monoid.name})")
