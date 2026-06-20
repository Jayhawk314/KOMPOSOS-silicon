"""
Geometric Homotopy - Curvature-Aware Path Equivalence

Extends standard path homotopy with geometric structure from Ricci curvature.

Key insight: Paths are geometrically homotopic if they:
1. Share the same endpoints
2. Pass through the same geometric regions (spherical, hyperbolic, euclidean)
3. Have similar curvature profiles

This connects Thurston geometrization to HoTT:
- Standard homotopy: paths are equivalent if continuously deformable
- Geometric homotopy: paths are equivalent if they traverse same geometry types

Example:
- Path 1: Newton -> Maxwell -> QED (euclidean -> euclidean -> spherical)
- Path 2: Newton -> Faraday -> Maxwell -> QED (euclidean -> euclidean -> euclidean -> spherical)

These have the same geometric signature ["euclidean", "spherical"] when simplified,
so they are geometrically homotopic even though they differ in length.

References:
- Thurston (1982): Three-dimensional manifolds, Kleinian groups, and hyperbolic geometry
- HoTT Book (2013): Chapter 2 on path homotopy
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Any
from enum import Enum

# Import standard homotopy
from .homotopy import HomotopyType, Homotopy, HomotopyResult


class GeometricHomotopyType(Enum):
    """Types of geometric homotopy relationships."""
    IDENTICAL = "identical"                     # Same path
    GEOMETRICALLY_HOMOTOPIC = "geo_homotopic"   # Same geometric signature
    WEAKLY_HOMOTOPIC = "weak_homotopic"         # Similar signatures (edit distance <= 1)
    DISTINCT = "distinct"                       # Different geometric classes


@dataclass
class GeometricSignature:
    """
    The geometric signature of a path.

    A sequence of geometry types the path traverses.
    Example: ("euclidean", "spherical", "euclidean", "hyperbolic")
    """
    raw_signature: Tuple[str, ...]      # Full signature
    simplified: Tuple[str, ...]         # Collapsed consecutive duplicates
    transitions: List[Tuple[str, str]]  # List of (from_geom, to_geom) transitions

    @property
    def num_transitions(self) -> int:
        """Number of geometry type transitions."""
        return len(self.transitions)

    @property
    def dominant_geometry(self) -> str:
        """Most common geometry type in the path."""
        if not self.raw_signature:
            return "unknown"
        counts = {}
        for g in self.raw_signature:
            counts[g] = counts.get(g, 0) + 1
        return max(counts, key=counts.get)

    def __eq__(self, other):
        if not isinstance(other, GeometricSignature):
            return False
        return self.simplified == other.simplified

    def __hash__(self):
        return hash(self.simplified)


@dataclass
class GeometricHomotopy:
    """
    A geometric homotopy between two paths.

    Unlike standard homotopy (continuous deformation), geometric homotopy
    requires paths to traverse the same geometric regions.
    """
    source_path: List[str]
    target_path: List[str]
    source_signature: GeometricSignature
    target_signature: GeometricSignature
    homotopy_type: GeometricHomotopyType
    signature_distance: int  # Edit distance between simplified signatures
    confidence: float = 1.0

    def __repr__(self):
        return f"GeometricHomotopy({self.homotopy_type.value}, dist={self.signature_distance})"


@dataclass
class GeometricHomotopyResult:
    """Result of geometric homotopy analysis."""
    paths: List[List[str]]
    signatures: List[GeometricSignature]
    homotopy_classes: List[Set[int]]  # Sets of path indices
    all_homotopic: bool
    homotopies: List[GeometricHomotopy]
    analysis: str

    @property
    def num_classes(self) -> int:
        return len(self.homotopy_classes)


class GeometricHomotopyChecker:
    """
    Check geometric homotopy between paths using Ricci curvature.

    Two paths are geometrically homotopic if they pass through the
    same sequence of geometric region types (after simplification).

    This is a coarser equivalence than standard homotopy but captures
    the "shape" of the intellectual journey.
    """

    def __init__(self, ricci_curvature=None, store=None):
        """
        Initialize checker.

        Args:
            ricci_curvature: OllivierRicciCurvature instance (or will create one)
            store: KomposOSStore (required if ricci_curvature not provided)
        """
        self.ricci = ricci_curvature
        self.store = store
        self._region_map = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazily initialize geometry computation."""
        if self._initialized:
            return

        if self.ricci is None:
            if self.store is None:
                raise ValueError("Either ricci_curvature or store must be provided")
            try:
                from geometry import OllivierRicciCurvature
                self.ricci = OllivierRicciCurvature(self.store)
            except ImportError:
                # Geometry module not available - use fallback
                self._region_map = {}
                self._initialized = True
                return

        # Compute curvatures and get region map
        self.ricci.compute_all_curvatures()
        self._region_map = self.ricci.get_geometric_regions()
        self._initialized = True

    def get_node_geometry(self, node: str) -> str:
        """Get the geometry type for a node."""
        self._ensure_initialized()
        return self._region_map.get(node, "unknown")

    def compute_signature(self, path: List[str]) -> GeometricSignature:
        """
        Compute the geometric signature of a path.

        Args:
            path: List of node names

        Returns:
            GeometricSignature with raw, simplified, and transition info
        """
        self._ensure_initialized()

        if not path:
            return GeometricSignature(
                raw_signature=(),
                simplified=(),
                transitions=[]
            )

        # Get geometry for each node
        raw = tuple(self.get_node_geometry(node) for node in path)

        # Simplify by collapsing consecutive duplicates
        simplified = []
        for geom in raw:
            if not simplified or simplified[-1] != geom:
                simplified.append(geom)
        simplified = tuple(simplified)

        # Compute transitions
        transitions = []
        for i in range(len(raw) - 1):
            if raw[i] != raw[i + 1]:
                transitions.append((raw[i], raw[i + 1]))

        return GeometricSignature(
            raw_signature=raw,
            simplified=simplified,
            transitions=transitions
        )

    def signature_edit_distance(self, sig1: GeometricSignature, sig2: GeometricSignature) -> int:
        """
        Compute edit distance between two simplified signatures.

        Uses Levenshtein distance on the simplified signature tuples.
        """
        s1 = sig1.simplified
        s2 = sig2.simplified

        # Standard dynamic programming Levenshtein
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])

        return dp[m][n]

    def are_geometrically_homotopic(
        self,
        path1: List[str],
        path2: List[str],
        strict: bool = True
    ) -> Tuple[bool, GeometricHomotopy]:
        """
        Check if two paths are geometrically homotopic.

        Args:
            path1: First path (list of node names)
            path2: Second path (list of node names)
            strict: If True, require identical simplified signatures.
                   If False, allow edit distance <= 1.

        Returns:
            (is_homotopic, GeometricHomotopy witness)
        """
        sig1 = self.compute_signature(path1)
        sig2 = self.compute_signature(path2)

        distance = self.signature_edit_distance(sig1, sig2)

        # Determine homotopy type
        if path1 == path2:
            homotopy_type = GeometricHomotopyType.IDENTICAL
            is_homotopic = True
        elif sig1 == sig2:
            homotopy_type = GeometricHomotopyType.GEOMETRICALLY_HOMOTOPIC
            is_homotopic = True
        elif distance <= 1 and not strict:
            homotopy_type = GeometricHomotopyType.WEAKLY_HOMOTOPIC
            is_homotopic = True
        else:
            homotopy_type = GeometricHomotopyType.DISTINCT
            is_homotopic = False

        homotopy = GeometricHomotopy(
            source_path=path1,
            target_path=path2,
            source_signature=sig1,
            target_signature=sig2,
            homotopy_type=homotopy_type,
            signature_distance=distance,
            confidence=1.0 if is_homotopic else 0.0
        )

        return is_homotopic, homotopy

    def check_paths(
        self,
        paths: List[List[str]],
        strict: bool = True
    ) -> GeometricHomotopyResult:
        """
        Check geometric homotopy for a list of paths.

        Args:
            paths: List of paths to compare
            strict: Whether to require exact signature match

        Returns:
            GeometricHomotopyResult with classes and analysis
        """
        if not paths:
            return GeometricHomotopyResult(
                paths=[],
                signatures=[],
                homotopy_classes=[],
                all_homotopic=True,
                homotopies=[],
                analysis="No paths provided."
            )

        # Compute signatures for all paths
        signatures = [self.compute_signature(p) for p in paths]

        # Group paths by simplified signature
        sig_to_indices: Dict[Tuple[str, ...], Set[int]] = {}
        for i, sig in enumerate(signatures):
            key = sig.simplified
            if key not in sig_to_indices:
                sig_to_indices[key] = set()
            sig_to_indices[key].add(i)

        homotopy_classes = list(sig_to_indices.values())

        # Generate pairwise homotopies for analysis
        homotopies = []
        for i in range(len(paths)):
            for j in range(i + 1, len(paths)):
                _, hom = self.are_geometrically_homotopic(paths[i], paths[j], strict)
                homotopies.append(hom)

        all_homotopic = len(homotopy_classes) == 1

        # Generate analysis
        analysis = self._generate_analysis(paths, signatures, homotopy_classes, homotopies)

        return GeometricHomotopyResult(
            paths=paths,
            signatures=signatures,
            homotopy_classes=homotopy_classes,
            all_homotopic=all_homotopic,
            homotopies=homotopies,
            analysis=analysis
        )

    def _generate_analysis(
        self,
        paths: List[List[str]],
        signatures: List[GeometricSignature],
        homotopy_classes: List[Set[int]],
        homotopies: List[GeometricHomotopy]
    ) -> str:
        """Generate human-readable analysis."""
        lines = []

        lines.append("# Geometric Homotopy Analysis")
        lines.append("")
        lines.append("## Summary")
        lines.append(f"- Paths analyzed: {len(paths)}")
        lines.append(f"- Geometric homotopy classes: {len(homotopy_classes)}")
        lines.append(f"- All paths homotopic: {'Yes' if len(homotopy_classes) == 1 else 'No'}")
        lines.append("")

        # Path signatures
        lines.append("## Path Signatures")
        lines.append("")
        lines.append("| Path | Length | Simplified Signature | Transitions |")
        lines.append("|------|--------|---------------------|-------------|")

        for i, (path, sig) in enumerate(zip(paths, signatures)):
            sig_str = " -> ".join(sig.simplified) if sig.simplified else "(empty)"
            lines.append(f"| {i+1} | {len(path)} | {sig_str} | {sig.num_transitions} |")

        lines.append("")

        # Homotopy classes
        lines.append("## Homotopy Classes")
        lines.append("")

        for i, cls in enumerate(homotopy_classes):
            sig = signatures[list(cls)[0]]
            sig_str = " -> ".join(sig.simplified) if sig.simplified else "(empty)"
            paths_str = ", ".join(f"Path {idx+1}" for idx in sorted(cls))
            lines.append(f"### Class {i+1}: {sig_str}")
            lines.append(f"- Paths: {paths_str}")
            lines.append(f"- Dominant geometry: {sig.dominant_geometry}")
            lines.append("")

        # Interpretation
        lines.append("## Thurston Interpretation")
        lines.append("")

        if len(homotopy_classes) == 1:
            lines.append("All paths traverse the **same geometric regions** in the same order.")
            lines.append("This means they represent the **same type of intellectual journey**,")
            lines.append("even if they differ in specific intermediate steps.")
        else:
            lines.append(f"Paths fall into **{len(homotopy_classes)} distinct geometric classes**.")
            lines.append("This indicates genuinely different types of intellectual journeys:")
            lines.append("")

            # Describe each class
            for i, cls in enumerate(homotopy_classes):
                sig = signatures[list(cls)[0]]
                if "spherical" in sig.simplified and "hyperbolic" in sig.simplified:
                    lines.append(f"- **Class {i+1}**: Crosses between paradigm clusters and hierarchical branches")
                elif "spherical" in sig.simplified:
                    lines.append(f"- **Class {i+1}**: Stays within paradigm clusters (dense interconnection)")
                elif "hyperbolic" in sig.simplified:
                    lines.append(f"- **Class {i+1}**: Follows hierarchical/tree-like development")
                else:
                    lines.append(f"- **Class {i+1}**: Follows linear/timeline development")

        return "\n".join(lines)


def check_geometric_homotopy(
    paths: List[List[str]],
    store=None,
    ricci=None,
    strict: bool = True
) -> GeometricHomotopyResult:
    """
    Convenience function to check geometric homotopy.

    Args:
        paths: List of paths (each path is a list of node names)
        store: KomposOSStore (optional if ricci provided)
        ricci: OllivierRicciCurvature instance (optional if store provided)
        strict: Whether to require exact signature match

    Returns:
        GeometricHomotopyResult
    """
    checker = GeometricHomotopyChecker(ricci_curvature=ricci, store=store)
    return checker.check_paths(paths, strict=strict)


# Example usage
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from evaluation.physics_dataset import create_physics_dataset
    from geometry import OllivierRicciCurvature

    print("=" * 70)
    print("Geometric Homotopy Analysis: Physics Dataset")
    print("=" * 70)
    print()

    # Create dataset and compute curvature
    store = create_physics_dataset()
    ricci = OllivierRicciCurvature(store)

    # Create checker
    checker = GeometricHomotopyChecker(ricci_curvature=ricci)

    # Example paths (you would get these from path finding)
    example_paths = [
        ["Newton", "Maxwell", "Einstein"],
        ["Newton", "Faraday", "Maxwell", "Einstein"],
        ["Newton", "Lagrange", "Hamilton", "Schrodinger"],
    ]

    # Check homotopy
    result = checker.check_paths(example_paths)

    print(result.analysis)
    print()
    print(f"Number of geometric homotopy classes: {result.num_classes}")
