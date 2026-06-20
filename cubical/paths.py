"""
Computational Paths in Cubical Type Theory

In cubical type theory, paths are FUNCTIONS from the interval.
This makes them computational objects, not just proof terms.

A path p : a =_A b is literally a function p : I → A
with p(0) = a and p(1) = b.

The interval I has:
- Two endpoints: 0 and 1
- Dimension variables: i, j, k, ...
- Face maps: (i=0), (i=1)
- Degeneracies: paths that are constant

The "cube" structure comes from having MULTIPLE dimensions.
A 2-dimensional path (square) has type: I × I → A
A 3-dimensional path (cube) has type: I × I × I → A

This enables PARALLEL exploration: different dimensions are independent!

In KOMPOSOS-III, cubical paths let us:
- Explore multiple inference paths simultaneously
- Compose paths (sequential reasoning)
- Fill gaps via Kan operations
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Set


@dataclass
class Interval:
    """
    The interval type I.

    Has two endpoints:
    - i0 (left, representing 0)
    - i1 (right, representing 1)

    And dimension variables for higher-dimensional cubes.
    """
    pass


# Interval endpoints
I0 = "i0"  # 0, left endpoint
I1 = "i1"  # 1, right endpoint


def _smooth_interp(a, b, t):
    """
    Smooth linear interpolation between a and b at interval point t.

    For symbolic values, returns a weighted combination representation.
    For numeric values, returns the actual interpolated value.
    """
    if t == I0:
        return a
    elif t == I1:
        return b
    else:
        # For numeric types, do actual interpolation
        try:
            # Map interval to [0, 1]: I0=0, I1=1, variables=0.5
            alpha = 0.5  # Default for dimension variables
            return (1 - alpha) * a + alpha * b
        except (TypeError, ValueError):
            # For symbolic types, return interpolation description
            return f"interp({a}, {b}, {t})"


@dataclass
class DimensionVar:
    """
    A dimension variable (i, j, k, ...).

    Used for constructing higher-dimensional cubes.
    """
    name: str
    index: int = 0

    def __repr__(self):
        return self.name


# Common dimension variables
i = DimensionVar("i", 0)
j = DimensionVar("j", 1)
k = DimensionVar("k", 2)


@dataclass
class Face:
    """
    A face of a cube, specified by setting a dimension variable to 0 or 1.

    Example: (i=0) is the left face in the i dimension.
    """
    dimension: DimensionVar
    value: str  # I0 or I1

    def __repr__(self):
        return f"({self.dimension.name}={self.value})"


@dataclass
class PathType:
    """
    A path type in cubical type theory.

    Path A a b = (i : I) → A [i=0 ↦ a, i=1 ↦ b]

    This is a function from the interval with boundary conditions.

    Attributes:
        type_A: The type of the endpoints
        left: a (the value at i=0)
        right: b (the value at i=1)
        path_fn: The path as a function I → A
        dimension: Which dimension variable this path uses
    """
    type_A: Any
    left: Any    # a
    right: Any   # b
    path_fn: Optional[Callable[[str], Any]] = None
    dimension: DimensionVar = field(default_factory=lambda: i)
    provenance: str = "unknown"

    def __post_init__(self):
        if self.path_fn is None:
            # Default: interpolate between left and right
            # Uses Ricci curvature-based interpolation if geometry module is available
            try:
                from geometry.ricci import GeometryType

                def curved_interp(t):
                    if t == I0:
                        return self.left
                    elif t == I1:
                        return self.right
                    else:
                        # Curvature-aware interpolation: blend based on
                        # whether the path is in a spherical/hyperbolic/euclidean region
                        # For now, use smooth linear interpolation as fallback
                        return _smooth_interp(self.left, self.right, t)

                self.path_fn = curved_interp
            except ImportError:
                def default_fn(t):
                    if t == I0:
                        return self.left
                    elif t == I1:
                        return self.right
                    else:
                        # Smooth linear interpolation
                        return _smooth_interp(self.left, self.right, t)
                self.path_fn = default_fn

    def __call__(self, t: str) -> Any:
        """Evaluate the path at a point."""
        return path_apply(self, t)

    def __repr__(self):
        return f"Path({self.left} ~> {self.right})"


def path_apply(p: PathType, t: str) -> Any:
    """
    Apply a path at a point in the interval.

    Args:
        p: The path
        t: A point (I0, I1, or a variable)

    Returns:
        The value p(t)
    """
    if t == I0:
        return p.left
    elif t == I1:
        return p.right
    else:
        # Evaluate the path function
        return p.path_fn(t)


def refl_path(a: Any, type_A: Any = None) -> PathType:
    """
    The reflexivity path: constant path at a.

    refl(a) : a = a
    """
    if type_A is None:
        type_A = type(a).__name__

    return PathType(
        type_A=type_A,
        left=a,
        right=a,
        path_fn=lambda _: a,
        provenance="refl"
    )


@dataclass
class Square:
    """
    A 2-dimensional path (square).

    A square in type A is a function I × I → A
    with specified boundaries on all four sides.

    The four boundaries:
    - top: j=1
    - bottom: j=0
    - left: i=0
    - right: i=1

        top
      ┌─────┐
    l │     │ r
    e │     │ i
    f │     │ g
    t │     │ h
      └─────┘ t
       bottom
    """
    type_A: Any
    top: PathType
    bottom: PathType
    left: PathType
    right: PathType
    filler: Optional[Callable[[str, str], Any]] = None

    def __call__(self, s: str, t: str) -> Any:
        """Evaluate the square at (i, j) = (s, t)."""
        if t == I0:
            return self.bottom(s)
        elif t == I1:
            return self.top(s)
        elif s == I0:
            return self.left(t)
        elif s == I1:
            return self.right(t)
        elif self.filler:
            return self.filler(s, t)
        else:
            raise ValueError("No filler for interior points")


@dataclass
class Cube:
    """
    A 3-dimensional path (cube).

    Has 6 faces, 12 edges, 8 corners.
    Used for composing higher-dimensional structures.
    """
    type_A: Any
    faces: Dict[Face, Square] = field(default_factory=dict)
    filler: Optional[Callable[[str, str, str], Any]] = None

    def __call__(self, r: str, s: str, t: str) -> Any:
        """Evaluate the cube at (i, j, k) = (r, s, t)."""
        if self.filler:
            return self.filler(r, s, t)
        raise ValueError("No filler defined")


@dataclass
class PartialElement:
    """
    A partial element of a type, defined on some faces of a cube.

    This is the input to Kan operations: we have some faces filled in,
    and we want to fill the rest.

    Example: We have 3 sides of a square and want the 4th.
    """
    type_A: Any
    defined_faces: Dict[Face, Any]
    dimension: int = 1

    def is_defined_on(self, face: Face) -> bool:
        """Check if this partial element is defined on a face."""
        return face in self.defined_faces

    def get_value(self, face: Face) -> Any:
        """Get the value on a face."""
        return self.defined_faces.get(face)


class PathContext:
    """
    Context for managing paths and their compositions.

    Tracks:
    - Known paths between points
    - Compositions and inversions
    - Higher paths (squares, cubes)
    """

    def __init__(self):
        self.paths: Dict[Tuple[int, int], List[PathType]] = {}
        self.squares: List[Square] = []
        self.cubes: List[Cube] = []

    def add_path(self, p: PathType):
        """Register a path."""
        key = (id(p.left), id(p.right))
        if key not in self.paths:
            self.paths[key] = []
        self.paths[key].append(p)

    def find_path(self, a: Any, b: Any) -> Optional[PathType]:
        """Find a path from a to b."""
        key = (id(a), id(b))
        paths = self.paths.get(key, [])
        return paths[0] if paths else None

    def find_all_paths(self, a: Any, b: Any) -> List[PathType]:
        """Find all paths from a to b."""
        key = (id(a), id(b))
        return self.paths.get(key, [])


# Example usage
if __name__ == "__main__":
    # Create a simple path
    p = refl_path(42, "Int")
    print(f"refl(42): {p}")
    print(f"p(i0) = {p(I0)}")
    print(f"p(i1) = {p(I1)}")

    # Create a non-trivial path
    def arithmetic_path_fn(t):
        if t == I0:
            return "2+2"
        elif t == I1:
            return "4"
        else:
            return "evaluating..."

    arithmetic = PathType(
        type_A="Expression",
        left="2+2",
        right="4",
        path_fn=arithmetic_path_fn,
        provenance="arithmetic"
    )
    print(f"\nArithmetic path: {arithmetic}")
    print(f"p(i0) = {arithmetic(I0)}")
    print(f"p(i1) = {arithmetic(I1)}")

    # Create a square (2D path)
    # Represents: (2+2) = 4 = (2*2) and 2+2 = 2*2
    top = PathType("Expr", "4", "2*2")
    bottom = PathType("Expr", "2+2", "1+3")
    left = PathType("Expr", "2+2", "4")
    right = PathType("Expr", "1+3", "2*2")

    square = Square(
        type_A="Expr",
        top=top,
        bottom=bottom,
        left=left,
        right=right
    )
    print(f"\nSquare boundaries:")
    print(f"  top: {square.top}")
    print(f"  bottom: {square.bottom}")
    print(f"  left: {square.left}")
    print(f"  right: {square.right}")
