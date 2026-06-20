"""
Identity Types - The Foundation of HoTT

In HoTT, the identity type (a =_A b) is the type of paths from a to b.
This is NOT just "a equals b" - it's "all the ways a equals b".

Key ideas:
1. Identity types are types themselves (can have multiple inhabitants)
2. refl(a) : a = a is the trivial path (reflexivity)
3. Paths can be composed, inverted, and compared
4. Higher identity types: paths between paths (homotopies)

In KOMPOSOS-III, paths represent:
- Proofs that two representations are equivalent
- Transformation chains between concepts
- Evidence for equality claims
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Callable, TypeVar, Generic
from enum import Enum

T = TypeVar('T')


class PathLevel(Enum):
    """The dimension of a path in the tower of identity types."""
    POINT = 0      # a : A (an element)
    PATH = 1       # p : a = b (a path)
    HOMOTOPY = 2   # α : p = q (a path between paths)
    HIGHER = 3     # and so on...


@dataclass
class IdentityType(Generic[T]):
    """
    The identity type (a =_A b).

    This is the TYPE of paths from a to b in type A.
    It may have zero, one, or many inhabitants.
    """
    type_A: Any         # The ambient type A
    left: T             # a (left endpoint)
    right: T            # b (right endpoint)
    level: PathLevel = PathLevel.PATH

    def __repr__(self):
        return f"({self.left} =_{self.type_A} {self.right})"


@dataclass
class Path(Generic[T]):
    """
    A path (inhabitant of an identity type).

    A path p : a =_A b is a witness/proof that a equals b.
    In HoTT, this is a continuous path in the space A.

    Paths can carry:
    - witness: the actual proof term
    - provenance: how this path was constructed
    - confidence: for rated representations
    """
    identity_type: IdentityType[T]
    witness: Any = None
    provenance: str = "unknown"
    confidence: float = 1.0

    @property
    def source(self) -> T:
        """The left endpoint."""
        return self.identity_type.left

    @property
    def target(self) -> T:
        """The right endpoint."""
        return self.identity_type.right

    @property
    def type_A(self) -> Any:
        """The ambient type."""
        return self.identity_type.type_A

    def __repr__(self):
        return f"Path[{self.source} ~> {self.target}]"


def refl(a: T, type_A: Any = None) -> Path[T]:
    """
    Reflexivity: a = a

    The trivial path from a to itself.
    This is the canonical inhabitant of (a =_A a).
    """
    if type_A is None:
        type_A = type(a).__name__

    id_type = IdentityType(type_A=type_A, left=a, right=a)
    return Path(
        identity_type=id_type,
        witness="refl",
        provenance="reflexivity",
        confidence=1.0
    )


def sym(p: Path[T]) -> Path[T]:
    """
    Symmetry: if p : a = b, then sym(p) : b = a

    Path inversion.
    """
    inv_type = IdentityType(
        type_A=p.type_A,
        left=p.target,
        right=p.source,
        level=p.identity_type.level
    )
    return Path(
        identity_type=inv_type,
        witness=("sym", p.witness),
        provenance=f"sym({p.provenance})",
        confidence=p.confidence
    )


def trans(p: Path[T], q: Path[T]) -> Path[T]:
    """
    Transitivity: if p : a = b and q : b = c, then trans(p,q) : a = c

    Path composition.
    """
    if p.target != q.source:
        raise ValueError(
            f"Cannot compose paths: {p.target} ≠ {q.source}"
        )

    comp_type = IdentityType(
        type_A=p.type_A,
        left=p.source,
        right=q.target,
        level=p.identity_type.level
    )
    return Path(
        identity_type=comp_type,
        witness=("trans", p.witness, q.witness),
        provenance=f"trans({p.provenance}, {q.provenance})",
        confidence=min(p.confidence, q.confidence)  # Conservative
    )


def concat(p: Path[T], q: Path[T]) -> Path[T]:
    """Alias for trans (path concatenation)."""
    return trans(p, q)


def ap(f: Callable[[T], Any], p: Path[T]) -> Path:
    """
    Action on paths: if p : a = b and f : A → B, then ap(f,p) : f(a) = f(b)

    Functions respect equality.
    """
    result_type = IdentityType(
        type_A=f.__annotations__.get('return', 'B'),
        left=f(p.source),
        right=f(p.target),
        level=p.identity_type.level
    )
    return Path(
        identity_type=result_type,
        witness=("ap", f.__name__ if hasattr(f, '__name__') else str(f), p.witness),
        provenance=f"ap({f.__name__ if hasattr(f, '__name__') else 'f'}, {p.provenance})",
        confidence=p.confidence
    )


@dataclass
class PathOver(Generic[T]):
    """
    A path over another path (dependent paths).

    If P : A → Type is a type family, p : a =_A b, and
    u : P(a) and v : P(b), then
    PathOver(p, u, v) is the type of paths from u to v
    lying over p.

    This is essential for dependent types in HoTT.
    """
    base_path: Path
    type_family: Callable  # P : A → Type
    source_fiber: Any      # u : P(a)
    target_fiber: Any      # v : P(b)
    witness: Any = None


class IdentitySystem:
    """
    A system for managing identity types and paths.

    This tracks:
    - Known equalities (paths)
    - Equivalences between types
    - Path compositions and inversions
    """

    def __init__(self):
        self.paths: dict[tuple, list[Path]] = {}  # (a, b) -> paths from a to b
        self.equivalences: dict[str, list] = {}    # type name -> equivalent types

    def add_path(self, p: Path):
        """Register a path."""
        key = (id(p.source), id(p.target))
        if key not in self.paths:
            self.paths[key] = []
        self.paths[key].append(p)

    def find_path(self, a: Any, b: Any) -> Optional[Path]:
        """Find a path from a to b if one exists."""
        key = (id(a), id(b))
        paths = self.paths.get(key, [])
        return paths[0] if paths else None

    def are_equal(self, a: Any, b: Any) -> bool:
        """Check if we have a path from a to b."""
        return self.find_path(a, b) is not None

    def compose_paths(self, start: Any, end: Any,
                     intermediates: list[Any]) -> Optional[Path]:
        """
        Try to compose paths through intermediates.

        Given start, [x, y, z], end, find:
        start = x = y = z = end
        """
        if not intermediates:
            return self.find_path(start, end)

        current = start
        composed = None

        for next_point in intermediates + [end]:
            p = self.find_path(current, next_point)
            if p is None:
                return None
            composed = p if composed is None else trans(composed, p)
            current = next_point

        return composed


# Example and tests
if __name__ == "__main__":
    # Basic identity
    p = refl(42, "Int")
    print(f"refl(42): {p}")

    # Symmetry
    q = sym(p)
    print(f"sym(refl(42)): {q}")

    # Create a non-trivial path (manually)
    id_type = IdentityType("Number", 2+2, 4)
    arithmetic_path = Path(
        identity_type=id_type,
        witness="arithmetic",
        provenance="2+2=4",
        confidence=1.0
    )
    print(f"Arithmetic: {arithmetic_path}")

    # Composition
    id_type2 = IdentityType("Number", 4, 2*2)
    mult_path = Path(
        identity_type=id_type2,
        witness="multiplication",
        provenance="4=2*2",
        confidence=1.0
    )

    composed = trans(arithmetic_path, mult_path)
    print(f"Composed: {composed}")
    print(f"  2+2 = 2*2: {composed.source} = {composed.target}")

    # Action on paths
    def double(x):
        return x * 2

    doubled = ap(double, arithmetic_path)
    print(f"ap(double, 2+2=4): {doubled}")
