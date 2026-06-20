"""
Path Homotopy - Are Multiple Paths Equivalent?

In HoTT, two paths p, q : a = b are homotopic if there exists
a 2-path (homotopy) α : p = q. This is a "path between paths".

For KOMPOSOS-III, this answers:
"Are the 4 paths from Planck to Feynman 'the same proof' or different?"

Key concepts:
1. Path Homotopy: Two paths with the same endpoints are homotopic
   if there's a continuous deformation from one to the other
2. Free Homotopy: Paths with possibly different endpoints can be
   compared if their images are "close"
3. Spine Detection: Multiple paths are homotopic if they share a
   "common spine" - essential intermediate points

In category theory terms:
- Paths are 1-morphisms
- Homotopies are 2-morphisms (natural transformations)
- Homotopy equivalence means the paths represent the same "proof"
"""

from dataclasses import dataclass, field
from typing import Any, List, Dict, Set, Optional, Tuple
from enum import Enum


class HomotopyType(Enum):
    """Types of homotopy relationships between paths."""
    IDENTICAL = "identical"           # Same path (p = q judgmentally)
    HOMOTOPIC = "homotopic"           # Different paths, same homotopy class
    FREE_HOMOTOPIC = "free_homotopic" # Homotopic with endpoint adjustment
    DISTINCT = "distinct"             # Different homotopy classes


@dataclass
class Homotopy:
    """
    A homotopy (2-path) between two paths.

    If p, q : a = b, then a homotopy α : p ~ q is a witness
    that p and q are "the same path up to deformation".

    In KOMPOSOS-III, this represents:
    - Different historical narratives that are essentially equivalent
    - Multiple proofs of the same theorem
    - Parallel intellectual lineages that converge
    """
    source_path: List[str]  # The first path (list of node names)
    target_path: List[str]  # The second path (list of node names)
    homotopy_type: HomotopyType
    witness: str = "direct"  # How we know they're homotopic
    confidence: float = 1.0
    shared_spine: Optional[List[str]] = None  # Common essential nodes

    def __repr__(self):
        return f"Homotopy({self.homotopy_type.value}: {len(self.source_path)} ~ {len(self.target_path)} nodes)"


@dataclass
class HomotopyResult:
    """Result of checking homotopy between paths."""
    paths: List[List[str]]
    homotopy_classes: List[Set[int]]  # Sets of path indices that are homotopic
    shared_spine: Optional[List[str]]
    all_homotopic: bool
    homotopies: List[Homotopy]
    analysis: str

    @property
    def num_classes(self) -> int:
        """Number of distinct homotopy classes."""
        return len(self.homotopy_classes)


class PathHomotopyChecker:
    """
    Checks whether multiple paths are homotopic.

    Two paths are considered homotopic if:
    1. They have the same endpoints (source and target)
    2. They share a "common spine" of essential intermediaries
    3. The non-spine portions can be "contracted" to the spine

    Algorithm:
    1. Extract the essential spine (nodes that appear in all paths)
    2. Check if non-spine nodes are "locally equivalent" to spine
    3. Build 2-cells (squares) showing deformations between paths
    """

    def __init__(self, store=None):
        self.store = store

    def check_homotopy(self, paths: List[List[str]]) -> HomotopyResult:
        """
        Check if multiple paths are homotopic.

        Args:
            paths: List of paths, where each path is a list of node names
                   e.g., [["Planck", "Bohr", "Heisenberg", "Dirac", "Feynman"], ...]

        Returns:
            HomotopyResult with analysis of homotopy classes
        """
        if not paths:
            return HomotopyResult(
                paths=[],
                homotopy_classes=[],
                shared_spine=None,
                all_homotopic=True,
                homotopies=[],
                analysis="No paths provided"
            )

        if len(paths) == 1:
            return HomotopyResult(
                paths=paths,
                homotopy_classes=[{0}],
                shared_spine=paths[0],
                all_homotopic=True,
                homotopies=[],
                analysis="Single path is trivially homotopic to itself"
            )

        # Step 1: Find shared spine (nodes in ALL paths)
        spine = self._find_shared_spine(paths)

        # Step 2: Check if all paths contract to spine
        contractible = self._check_contractibility(paths, spine)

        # Step 3: Build homotopy classes
        homotopy_classes, homotopies = self._build_homotopy_classes(paths, spine)

        all_homotopic = len(homotopy_classes) == 1 and len(homotopy_classes[0]) == len(paths)

        # Generate analysis text
        analysis = self._generate_analysis(paths, spine, homotopy_classes, all_homotopic)

        return HomotopyResult(
            paths=paths,
            homotopy_classes=homotopy_classes,
            shared_spine=spine,
            all_homotopic=all_homotopic,
            homotopies=homotopies,
            analysis=analysis
        )

    def _find_shared_spine(self, paths: List[List[str]]) -> List[str]:
        """
        Find the shared spine - nodes that appear in ALL paths.

        The spine represents the "essential" intermediaries that
        every evolutionary pathway must pass through.
        """
        if not paths:
            return []

        # Start with first path
        spine_set = set(paths[0])

        # Intersect with all other paths
        for path in paths[1:]:
            spine_set &= set(path)

        # Maintain order from first path
        spine = [node for node in paths[0] if node in spine_set]

        return spine

    def _check_contractibility(self, paths: List[List[str]], spine: List[str]) -> Dict[int, bool]:
        """
        Check if each path can be contracted to the spine.

        A path is contractible to the spine if:
        1. Removing non-spine nodes doesn't break connectivity
        2. Non-spine nodes are "locally equivalent" - meaning they
           represent variations that don't change the essential structure

        Returns dict mapping path index to contractibility
        """
        contractible = {}

        for idx, path in enumerate(paths):
            # Get non-spine nodes
            non_spine = [n for n in path if n not in spine]

            # A path is contractible if:
            # 1. Non-spine nodes are "bridges" between spine nodes
            # 2. The spine subsequence is preserved in order

            # Check spine order preservation
            spine_positions = []
            for s in spine:
                if s in path:
                    spine_positions.append(path.index(s))

            order_preserved = spine_positions == sorted(spine_positions)

            # A path contracts if removing non-spine doesn't disconnect spine
            contractible[idx] = order_preserved

        return contractible

    def _build_homotopy_classes(
        self,
        paths: List[List[str]],
        spine: List[str]
    ) -> Tuple[List[Set[int]], List[Homotopy]]:
        """
        Build equivalence classes of homotopic paths.

        Two paths are in the same homotopy class if:
        1. They share the same spine
        2. Their non-spine portions can be "deformed" to each other
        """
        n = len(paths)
        homotopies = []

        # Initially, each path is its own class
        parent = list(range(n))

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # Check pairwise homotopy
        for i in range(n):
            for j in range(i+1, n):
                homotopy_type, witness = self._check_pairwise_homotopy(
                    paths[i], paths[j], spine
                )

                if homotopy_type in [HomotopyType.IDENTICAL, HomotopyType.HOMOTOPIC]:
                    union(i, j)
                    homotopies.append(Homotopy(
                        source_path=paths[i],
                        target_path=paths[j],
                        homotopy_type=homotopy_type,
                        witness=witness,
                        shared_spine=spine
                    ))

        # Build equivalence classes
        classes = {}
        for i in range(n):
            root = find(i)
            if root not in classes:
                classes[root] = set()
            classes[root].add(i)

        return list(classes.values()), homotopies

    def _check_pairwise_homotopy(
        self,
        path1: List[str],
        path2: List[str],
        spine: List[str]
    ) -> Tuple[HomotopyType, str]:
        """
        Check if two specific paths are homotopic.

        Homotopy detection:
        1. Identical: paths are exactly the same
        2. Homotopic: paths differ only by "contracting" detours
        3. Distinct: paths represent genuinely different routes
        """
        # Check identical
        if path1 == path2:
            return HomotopyType.IDENTICAL, "identical_paths"

        # Get non-spine nodes for each path
        non_spine1 = [n for n in path1 if n not in spine]
        non_spine2 = [n for n in path2 if n not in spine]

        # Paths are homotopic if non-spine nodes are "equivalent detours"
        # Key insight: in the physics dataset, detours like:
        #   Planck -> Einstein -> Bohr vs Planck -> Bohr
        # are NOT homotopic because Einstein adds genuine content
        # But:
        #   Bohr -> Heisenberg vs Bohr -> Sommerfeld -> Heisenberg
        # COULD be homotopic if Sommerfeld is a "local detour"

        # Heuristic: paths are homotopic if:
        # 1. Same spine
        # 2. Non-spine insertions are between consecutive spine elements
        # 3. Non-spine nodes don't create genuinely different "routes"

        # Check if the paths have the same "branching structure"
        # by comparing where non-spine nodes are inserted

        def get_insertion_positions(path, spine):
            """Get where non-spine nodes are inserted relative to spine."""
            positions = {}
            spine_indices = {s: path.index(s) for s in spine if s in path}

            for node in path:
                if node not in spine:
                    idx = path.index(node)
                    # Find surrounding spine nodes
                    before = [s for s in spine if s in spine_indices and spine_indices[s] < idx]
                    after = [s for s in spine if s in spine_indices and spine_indices[s] > idx]
                    before_node = before[-1] if before else None
                    after_node = after[0] if after else None
                    positions[node] = (before_node, after_node)

            return positions

        pos1 = get_insertion_positions(path1, spine)
        pos2 = get_insertion_positions(path2, spine)

        # Paths are homotopic if their non-spine nodes are inserted
        # at "compatible" positions (between same spine elements)

        # Check overlap: if a non-spine node appears in both, must be same position
        common_non_spine = set(non_spine1) & set(non_spine2)
        for node in common_non_spine:
            if pos1.get(node) != pos2.get(node):
                return HomotopyType.DISTINCT, "incompatible_positions"

        # Check if unique non-spine nodes are insertable between same spine pairs
        # This is the key homotopy condition
        unique1 = set(non_spine1) - set(non_spine2)
        unique2 = set(non_spine2) - set(non_spine1)

        # Get the set of (before, after) pairs for each path's unique nodes
        pairs1 = set(pos1[n] for n in unique1 if n in pos1)
        pairs2 = set(pos2[n] for n in unique2 if n in pos2)

        # If unique nodes are in different spine intervals, paths are distinct
        # If they're in the same interval, they might be homotopic "detours"
        if pairs1 == pairs2:
            # Same intervals - could be homotopic detours
            return HomotopyType.HOMOTOPIC, "parallel_detours"

        # Check for "Einstein case" - fundamentally different intermediate
        # Einstein is not just a detour, he's a distinct intellectual lineage
        if non_spine1 != non_spine2:
            # Different non-spine content means different proofs
            # In HoTT terms: not homotopic because they carry different information
            return HomotopyType.DISTINCT, "different_intellectual_lineages"

        return HomotopyType.HOMOTOPIC, "spine_equivalent"

    def _generate_analysis(
        self,
        paths: List[List[str]],
        spine: List[str],
        homotopy_classes: List[Set[int]],
        all_homotopic: bool
    ) -> str:
        """Generate human-readable analysis of homotopy structure."""
        lines = []

        lines.append(f"Analyzed {len(paths)} paths for homotopy equivalence.")
        lines.append("")

        # Spine analysis
        if spine:
            lines.append(f"**Shared Spine** (nodes in ALL paths): {' -> '.join(spine)}")
            lines.append(f"Spine length: {len(spine)} nodes")
            lines.append("")
        else:
            lines.append("**No shared spine found** - paths are fundamentally different")
            lines.append("")

        # Homotopy class analysis
        lines.append(f"**Homotopy Classes**: {len(homotopy_classes)}")
        for i, cls in enumerate(homotopy_classes, 1):
            path_nums = sorted(cls)
            lines.append(f"  Class {i}: Paths {[n+1 for n in path_nums]}")
        lines.append("")

        # Interpretation
        if all_homotopic:
            lines.append("**Interpretation**: All paths are **homotopic** (equivalent as proofs).")
            lines.append("")
            lines.append("In HoTT terms: These paths represent the 'same proof' that the source")
            lines.append("concept evolved into the target concept. The variations (different")
            lines.append("intermediaries) are 'contractible detours' that don't change the")
            lines.append("essential structure of the evolutionary relationship.")
            lines.append("")
            lines.append("Categorically: There exists a 2-morphism (natural transformation)")
            lines.append("between any pair of paths, making them 'essentially the same'")
            lines.append("in the 2-categorical structure.")
        else:
            lines.append(f"**Interpretation**: Paths fall into **{len(homotopy_classes)} distinct** homotopy classes.")
            lines.append("")
            lines.append("In HoTT terms: These paths represent genuinely different 'proofs'")
            lines.append("of the evolutionary relationship. The differences are NOT mere")
            lines.append("'detours' but represent distinct intellectual lineages that")
            lines.append("cannot be continuously deformed into each other.")
            lines.append("")
            lines.append("Categorically: There is NO 2-morphism between paths in different")
            lines.append("classes. They represent independent pieces of evidence for the")
            lines.append("source-to-target evolution.")

        return "\n".join(lines)


def check_path_homotopy(paths: List[List[str]], store=None) -> HomotopyResult:
    """
    Convenience function to check path homotopy.

    Args:
        paths: List of paths (each path is list of node names)
        store: Optional store for additional metadata

    Returns:
        HomotopyResult with analysis
    """
    checker = PathHomotopyChecker(store)
    return checker.check_homotopy(paths)


# Example usage
if __name__ == "__main__":
    # The 4 paths from Planck to Feynman
    paths = [
        # Pathway 1: Length 4
        ["Planck", "Bohr", "Heisenberg", "Dirac", "Feynman"],

        # Pathway 2: Length 5 (via Einstein)
        ["Planck", "Einstein", "Bohr", "Heisenberg", "Dirac", "Feynman"],

        # Pathway 3: Length 5 (via Sommerfeld)
        ["Planck", "Bohr", "Sommerfeld", "Heisenberg", "Dirac", "Feynman"],

        # Pathway 4: Length 6 (via both Einstein and Sommerfeld)
        ["Planck", "Einstein", "Bohr", "Sommerfeld", "Heisenberg", "Dirac", "Feynman"],
    ]

    print("=" * 70)
    print("Path Homotopy Analysis: Planck → Feynman")
    print("=" * 70)
    print()

    result = check_path_homotopy(paths)

    print(result.analysis)
    print()
    print("=" * 70)
    print(f"Shared Spine: {result.shared_spine}")
    print(f"Number of Homotopy Classes: {result.num_classes}")
    print(f"All Paths Homotopic: {result.all_homotopic}")
