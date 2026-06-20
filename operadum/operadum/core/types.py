# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Fused Operadic Types

The constructive mirror of KOMPOSOS-IV's core/types.py.

Where KOMPOSOS's primitive is the Morphism (relate two existing things),
OPERADUM's primitive is the Operation -- an (A1,...,An) -> B wiring rule.

In KOMPOSOS-IV, data was fused so that a Morphism IS storable, IS
categorical, and carries enrichment natively. OPERADUM keeps the same
discipline for the dual world:

  - A Colour IS an interface type, IS a database row.
  - An Operation IS a build rule, IS a database row, carries its resource
    cost natively, and optionally IS executable (carries a callable).
  - A Composite IS a wiring tree of operations, IS its own interface, and
    knows how to combine the resource costs of its parts.

One representation. Zero translation seams.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .operad import Operad
    from .enrichment import ResourceMonoid


# A resource value is a labelled bag of costs/materials, e.g. {"ms": 8}.
# How two of them combine is decided by the operad's ResourceMonoid.
ResourceValue = Dict[str, Union[int, float]]


@dataclass
class Colour:
    """
    An interface type. The dual of KOMPOSOS's Object.

    Colours are the "ports" operations plug into. A composite is well-typed
    iff every plug connects an output colour to a matching input colour.

    Fields:
        name: Unique identifier (e.g. "RawText", "Embedding").
        metadata: Arbitrary key-value data.
        created_at: Timestamp (auto-set if None).
        provenance: Where this colour came from.
    """
    name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    provenance: str = "unknown"
    _operad: Optional["Operad"] = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, Colour):
            return self.name == other.name
        return NotImplemented


@dataclass
class Operation:
    """
    An n-input -> 1-output build rule. The dual of KOMPOSOS's Morphism.

    A morphism relates two existing objects; an Operation is a *rule for
    building* an output colour out of input colours. Its `cost` IS the
    monoidal resource weight -- not metadata -- exactly as a morphism's
    `confidence` IS its enriched hom-value.

    Fields:
        name: Identifier for the operation.
        inputs: Ordered list of input colour names (the arity).
        output: Output colour name.
        cost: Resource value consumed by applying this operation.
        metadata: Arbitrary key-value data.
        created_at: Timestamp (auto-set if None).
        provenance: Where this operation came from.
        _fn: Optional callable -- makes the operation executable. Receives
             one positional argument per input colour, returns the output.
        _operad: Back-reference to the owning Operad.
    """
    name: str
    inputs: List[str]
    output: str
    cost: ResourceValue = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    provenance: str = "unknown"
    _fn: Optional[Callable] = field(default=None, repr=False, compare=False)
    _operad: Optional["Operad"] = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    @property
    def arity(self) -> int:
        """Number of inputs this operation consumes."""
        return len(self.inputs)

    @property
    def id(self) -> str:
        """Deterministic identity from the interface signature."""
        return f"{self.name}:{','.join(self.inputs)}->{self.output}"

    @property
    def interface(self) -> "Interface":
        """The (inputs, output) interface this operation realizes."""
        return Interface(tuple(self.inputs), self.output)

    def as_composite(self) -> "Composite":
        """Lift a bare operation into a one-node composite (all inputs open)."""
        return Composite(self, [("open", c) for c in self.inputs])

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, Operation):
            return self.id == other.id
        return NotImplemented


# A slot in a composite is either an open input port awaiting a value, or a
# sub-composite plugged into that port.
#   ("open", colour_name)
#   ("sub",  Composite)
Slot = Tuple[str, Any]


@dataclass
class Composite:
    """
    A wiring tree of operations -- a point in the free operad.

    A Composite has a head operation and one slot per head input. Each slot
    is either still *open* (an input port of the whole assembly) or *filled*
    by a sub-composite whose output feeds that port.

    The open ports, read left-to-right, are the composite's own inputs; the
    head's output is the composite's output. So a Composite IS an interface,
    and the operad laws guarantee that any well-typed tree is itself a valid
    operation.

    This is the constructive dual of KOMPOSOS's Path (a chain of morphisms):
    a Path is linear, a Composite is a tree -- because designs branch.
    """
    head: Operation
    slots: List[Slot]

    @property
    def output(self) -> str:
        """Output colour of the whole assembly."""
        return self.head.output

    def open_inputs(self) -> List[str]:
        """Colours of the still-open input ports, in left-to-right order."""
        out: List[str] = []
        for kind, val in self.slots:
            if kind == "open":
                out.append(val)
            else:  # "sub"
                out.extend(val.open_inputs())
        return out

    @property
    def arity(self) -> int:
        """Number of open input ports."""
        return len(self.open_inputs())

    @property
    def interface(self) -> "Interface":
        return Interface(tuple(self.open_inputs()), self.output)

    @property
    def depth(self) -> int:
        """Height of the wiring tree (a bare operation has depth 1)."""
        subs = [val.depth for kind, val in self.slots if kind == "sub"]
        return 1 + (max(subs) if subs else 0)

    def operations(self) -> List[Operation]:
        """Every operation in the tree (pre-order)."""
        out = [self.head]
        for kind, val in self.slots:
            if kind == "sub":
                out.extend(val.operations())
        return out

    def cost(self, monoid: "ResourceMonoid") -> ResourceValue:
        """
        Total resource value = monoidal product of every part's cost.

        Conservation by construction: the composite's cost is the combine of
        the head cost with each sub-composite's cost. Nothing is created or
        lost in assembly.
        """
        total = monoid.combine(monoid.unit, self.head.cost)
        for kind, val in self.slots:
            if kind == "sub":
                total = monoid.combine(total, val.cost(monoid))
        return total

    def __repr__(self) -> str:
        return f"Composite({self.to_wiring()})"

    def to_wiring(self) -> str:
        """Compact S-expression of the wiring, e.g. embed(tokenize(RawText))."""
        parts: List[str] = []
        for kind, val in self.slots:
            if kind == "open":
                parts.append(val)
            else:
                parts.append(val.to_wiring())
        if not parts:
            return self.head.name
        return f"{self.head.name}({', '.join(parts)})"


@dataclass(frozen=True)
class Interface:
    """
    A typed signature: a tuple of input colours and one output colour.

    The dual of "which two objects does this morphism relate?" -- here it is
    "which colours does this assembly consume and produce?". Frozen so it can
    be used as a memoisation key in DAEDALUS search.
    """
    inputs: Tuple[str, ...]
    output: str

    def __str__(self) -> str:
        lhs = " x ".join(self.inputs) if self.inputs else "1"
        return f"({lhs}) -> {self.output}"


@dataclass
class Spec:
    """
    A synthesis target handed to WRIGHT: an interface, optional figure bounds,
    and optional free-form constraints.

    The dual of a KOMPOSOS verification claim. A claim asks "is this true?";
    a Spec asks "can you build something with this interface, within the
    declared figure limits?"

    Fields:
        inputs: Ordered input colours the construction may consume.
        output: Output colour the construction must produce.
        budget: Optional upper bounds (same shape as Operation.cost). Used for
                figures where lower is better: time, money, risk, emissions.
        constraints: Optional free-form constraints for higher tiers.
        requirements: Optional lower bounds. Used for figures where higher is
                      required: confidence, evidence strength, trace coverage.
    """
    inputs: Tuple[str, ...]
    output: str
    budget: Optional[ResourceValue] = None
    constraints: Dict[str, Any] = field(default_factory=dict)
    requirements: Optional[ResourceValue] = None

    @property
    def interface(self) -> Interface:
        return Interface(tuple(self.inputs), self.output)
