# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Linear-Logic Typing: tensor, lollipop, exponential

The constructive discipline that makes OPERADUM non-cartesian. KOMPOSOS is
cartesian -- a fact, once known, is reused freely (contraction) or dropped
(weakening). A *resource* admits neither: you cannot duplicate a permit nor
silently discard a paid-for material. Linear logic is exactly the logic where
contraction and weakening are removed, restored only under the exponential `!`.

Types:
    Atom(c)        -- a base colour
    Tensor(a, b)   -- A (x) B    "having both at once"
    Lolli(a, b)    -- A -o B     "consume an A to produce a B" (a build rule)
    OfCourse(a)    -- !A         the one place copying is permitted

An operation (A1,...,An) -> B is the linear map  A1 (x) ... (x) An  -o  B.

The checker reads a Composite as a proof and reports whether every non-`!`
resource is used exactly once. In a pure wiring tree contraction cannot occur
structurally, so the teeth here are on the *resource tokens* an assembly
spends: a token consumed twice (and not banged) is a contraction violation --
the same rule the LINEAR_TOKENS monoid enforces, lifted to a whole-design
judgement that also understands `!` exemptions.
"""

from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, List, Set, Tuple, Union

from .types import Composite, Operation


# ===================================================================
# Linear types
# ===================================================================

@dataclass(frozen=True)
class Atom:
    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Tensor:
    parts: Tuple["LinearType", ...]

    def __str__(self) -> str:
        return " (x) ".join(str(p) for p in self.parts) if self.parts else "1"


@dataclass(frozen=True)
class Lolli:
    src: "LinearType"
    dst: "LinearType"

    def __str__(self) -> str:
        return f"({self.src}) -o {self.dst}"


@dataclass(frozen=True)
class OfCourse:
    inner: "LinearType"

    def __str__(self) -> str:
        return f"!{self.inner}"


LinearType = Union[Atom, Tensor, Lolli, OfCourse]


def tensor(*types: LinearType) -> LinearType:
    """Tensor several types; the empty tensor is the unit, a single type is itself."""
    if len(types) == 1:
        return types[0]
    return Tensor(tuple(types))


def colour_type(colour: str, bang: Set[str]) -> LinearType:
    """A colour becomes !A if it is declared copyable, else the bare atom A."""
    atom = Atom(colour)
    return OfCourse(atom) if colour in bang else atom


def operation_signature(op: Operation, bang: Set[str] = frozenset()) -> Lolli:
    """The linear sequent A1 (x) ... (x) An -o B for an operation."""
    src = tensor(*[colour_type(c, bang) for c in op.inputs]) if op.inputs else Tensor(())
    return Lolli(src, colour_type(op.output, bang))


def composite_signature(comp: Composite, bang: Set[str] = frozenset()) -> Lolli:
    """The linear sequent of a whole assembly: its open inputs -o its output."""
    opens = comp.open_inputs()
    src = tensor(*[colour_type(c, bang) for c in opens]) if opens else Tensor(())
    return Lolli(src, colour_type(comp.output, bang))


# ===================================================================
# Linear soundness judgement
# ===================================================================

@dataclass
class LinearJudgement:
    """
    The verdict of reading a Composite as a linear-logic proof.

    Fields:
        ok: True iff no non-`!` resource token is contracted (spent > once).
        duplicated: the offending tokens (empty when ok).
        sequent: the design's linear type, as a witness.
        bang: the set of colours/tokens exempted by the exponential.
    """
    ok: bool
    duplicated: List[str]
    sequent: str
    bang: Set[str] = field(default_factory=set)

    def __str__(self) -> str:
        head = "LINEAR-SOUND" if self.ok else "CONTRACTION"
        body = self.sequent if self.ok else f"reused {self.duplicated}"
        return f"[{head}] {body}"


class LinearChecker:
    """
    Reads a Composite as a linear-logic proof and judges its soundness.

    A design is linear-sound when every resource token it spends is spent at
    most once -- unless the token (or its colour) is banged (`!`), which
    restores the right to copy. This is the typed mirror of the LINEAR_TOKENS
    resource monoid: the monoid catches reuse while *combining* costs; the
    checker judges a finished design and explains the violation as a sequent.
    """

    def __init__(self, bang: Iterable[str] = ()):
        self.bang: Set[str] = set(bang)

    def tokens(self, comp: Composite) -> Counter:
        """The multiset of all resource tokens spent across the whole tree."""
        spent: Counter = Counter()
        for op in comp.operations():
            for token, qty in op.cost.items():
                spent[token] += qty
        return spent

    def judge(self, comp: Composite) -> LinearJudgement:
        """Judge a composite linear-sound (or name the contracted tokens)."""
        spent = self.tokens(comp)
        duplicated = sorted(
            t for t, n in spent.items() if n > 1 and t not in self.bang
        )
        return LinearJudgement(
            ok=not duplicated,
            duplicated=duplicated,
            sequent=str(composite_signature(comp, self.bang)),
            bang=set(self.bang),
        )
