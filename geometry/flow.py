"""
Discrete Ricci Flow for Knowledge Graph Decomposition

Ricci flow evolves edge weights based on curvature:
- Positive curvature edges shrink (clusters tighten)
- Negative curvature edges expand (bridges widen)
- At equilibrium: natural community structure emerges

This is the discrete analog of Perelman's proof of the Poincare conjecture,
applied to knowledge graphs. Just as Ricci flow decomposes 3-manifolds into
Thurston geometries, discrete Ricci flow decomposes graphs into communities.

References:
- Hamilton (1982): Ricci flow on manifolds
- Perelman (2003): Proof of geometrization via Ricci flow with surgery
- Ni et al. (2019): Community detection on networks with Ricci flow
- Ollivier (2009): Discrete Ricci curvature
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional, Any
from enum import Enum
import numpy as np
from collections import defaultdict

try:
    from .ricci import OllivierRicciCurvature, GeometryType
except ImportError:
    from ricci import OllivierRicciCurvature, GeometryType


@dataclass
class FlowStep:
    """Record of a single Ricci flow step."""
    step: int
    weights: Dict[Tuple[str, str], float]
    curvatures: Dict[Tuple[str, str], float]
    mean_curvature: float
    max_change: float


@dataclass
class GeometricRegion:
    """A region of the graph with uniform geometry."""
    name: str
    nodes: Set[str]
    geometry_type: GeometryType
    mean_curvature: float
    internal_edges: int
    boundary_edges: int

    @property
    def size(self) -> int:
        return len(self.nodes)


@dataclass
class DecompositionResult:
    """Result of geometric decomposition via Ricci flow."""
    regions: List[GeometricRegion]
    boundary_edges: List[Tuple[str, str, float]]  # (source, target, final_weight)
    num_steps: int
    converged: bool
    flow_history: List[FlowStep]
    analysis: str

    @property
    def num_regions(self) -> int:
        return len(self.regions)


class DiscreteRicciFlow:
    """
    Apply discrete Ricci flow to reveal geometric structure.

    The flow evolves edge weights according to:
        w^{t+1}(u,v) = w^t(u,v) * (1 - kappa(u,v) * dt)

    Where:
    - w is edge weight
    - kappa is Ollivier-Ricci curvature
    - dt is time step

    Effect:
    - Positive curvature (clusters): weights decrease, cluster tightens
    - Negative curvature (bridges): weights increase, bridge weakens
    - At equilibrium: community boundaries emerge as high-weight edges

    This is analogous to how Perelman's Ricci flow with surgery
    decomposes 3-manifolds into Thurston geometries.
    """

    def __init__(self, category, alpha: float = 0.5):
        """
        Initialize Ricci flow.

        Args:
            category: Category with objects and morphisms
            alpha: Laziness parameter for curvature computation
        """
        self.category = category
        self.alpha = alpha
        self.curvature_computer = OllivierRicciCurvature(category, alpha=alpha)
        self._initialize_weights()
        self.flow_history = []

    def _initialize_weights(self):
        """Initialize edge weights from morphism confidences."""
        self.weights = {}
        self.edges = set()

        morphisms = self.category.morphisms()
        for mor in morphisms:
            edge = (mor.source, mor.target)
            reverse_edge = (mor.target, mor.source)

            # Use confidence as initial weight, default 1.0
            weight = mor.confidence if mor.confidence else 1.0

            self.weights[edge] = weight
            self.weights[reverse_edge] = weight
            self.edges.add(tuple(sorted([mor.source, mor.target])))

        # Get all nodes
        self.nodes = set()
        for s, t in self.edges:
            self.nodes.add(s)
            self.nodes.add(t)

    def step(self, dt: float = 0.1) -> FlowStep:
        """
        Perform one step of Ricci flow.

        The flow equation is:
            w^{t+1}(u,v) = w^t(u,v) * (1 - kappa(u,v) * dt)

        Normalized to prevent collapse:
            w_normalized = w * (total_initial / total_current)
        """
        # Compute current curvatures
        curvatures = {}
        for edge in self.edges:
            s, t = edge
            kappa = self.curvature_computer.compute_edge_curvature(s, t)
            curvatures[edge] = kappa

        # Update weights
        new_weights = {}
        total_old = sum(self.weights.values())

        for edge, w in self.weights.items():
            canonical_edge = tuple(sorted(edge))
            kappa = curvatures.get(canonical_edge, 0)

            # Ricci flow update
            new_w = w * (1 - kappa * dt)

            # Prevent negative or zero weights
            new_w = max(new_w, 0.01)

            new_weights[edge] = new_w

        # Normalize to prevent total collapse
        total_new = sum(new_weights.values())
        if total_new > 0:
            scale = total_old / total_new
            for edge in new_weights:
                new_weights[edge] *= scale

        # Compute max change for convergence check
        max_change = max(
            abs(new_weights[e] - self.weights[e])
            for e in self.weights
        )

        # Update state
        self.weights = new_weights

        # Update curvature computer's weights
        self.curvature_computer._weights = self.weights

        # Record step
        step_record = FlowStep(
            step=len(self.flow_history),
            weights=dict(self.weights),
            curvatures=curvatures,
            mean_curvature=np.mean(list(curvatures.values())),
            max_change=max_change
        )
        self.flow_history.append(step_record)

        return step_record

    def flow(self, max_steps: int = 50, dt: float = 0.1, tolerance: float = 0.001) -> DecompositionResult:
        """
        Run Ricci flow until convergence or max steps.

        Args:
            max_steps: Maximum number of flow steps
            dt: Time step size
            tolerance: Convergence threshold for max weight change

        Returns:
            DecompositionResult with geometric regions and analysis
        """
        print(f"Running discrete Ricci flow (max_steps={max_steps}, dt={dt})...")

        converged = False
        for i in range(max_steps):
            step_result = self.step(dt)

            # Progress update every 10 steps
            if (i + 1) % 10 == 0:
                print(f"  Step {i+1}: mean_kappa={step_result.mean_curvature:.4f}, max_change={step_result.max_change:.4f}")

            # Check convergence
            if step_result.max_change < tolerance:
                print(f"  Converged at step {i+1}")
                converged = True
                break

        if not converged:
            print(f"  Reached max steps ({max_steps})")

        # Detect community structure from final weights
        regions, boundary_edges = self._detect_communities()

        # Generate analysis
        analysis = self._generate_analysis(regions, boundary_edges, converged)

        return DecompositionResult(
            regions=regions,
            boundary_edges=boundary_edges,
            num_steps=len(self.flow_history),
            converged=converged,
            flow_history=self.flow_history,
            analysis=analysis
        )

    def _detect_communities(self, threshold_percentile: float = 75) -> Tuple[List[GeometricRegion], List[Tuple[str, str, float]]]:
        """
        Detect communities by finding edge weight cuts.

        After Ricci flow:
        - Low weight edges are within communities (positive curvature shrank them)
        - High weight edges are between communities (negative curvature expanded them)

        We cut at high-weight edges to find communities.
        """
        # Get weight threshold for cutting
        edge_weights = []
        for edge in self.edges:
            w = self.weights.get(edge, 1.0)
            edge_weights.append((edge, w))

        weights_only = [w for _, w in edge_weights]
        threshold = np.percentile(weights_only, threshold_percentile)

        # Build graph with only low-weight (intra-community) edges
        adjacency = defaultdict(set)
        boundary_edges = []

        for edge, w in edge_weights:
            s, t = edge
            if w < threshold:
                # Internal edge
                adjacency[s].add(t)
                adjacency[t].add(s)
            else:
                # Boundary edge
                boundary_edges.append((s, t, w))

        # Find connected components (communities)
        visited = set()
        communities = []

        def dfs(node, community):
            if node in visited:
                return
            visited.add(node)
            community.add(node)
            for neighbor in adjacency[node]:
                dfs(neighbor, community)

        for node in self.nodes:
            if node not in visited:
                community = set()
                dfs(node, community)
                if community:
                    communities.append(community)

        # Create GeometricRegion objects
        regions = []
        for i, community in enumerate(sorted(communities, key=len, reverse=True)):
            # Compute mean curvature for this region
            region_curvatures = []
            internal_edges = 0
            region_boundary = 0

            for edge in self.edges:
                s, t = edge
                if s in community and t in community:
                    # Internal edge
                    kappa = self.curvature_computer.compute_edge_curvature(s, t)
                    region_curvatures.append(kappa)
                    internal_edges += 1
                elif s in community or t in community:
                    # Boundary edge
                    region_boundary += 1

            mean_kappa = np.mean(region_curvatures) if region_curvatures else 0.0

            # Classify geometry type
            if mean_kappa > 0.2:
                geom_type = GeometryType.SPHERICAL
            elif mean_kappa < -0.2:
                geom_type = GeometryType.HYPERBOLIC
            else:
                geom_type = GeometryType.EUCLIDEAN

            regions.append(GeometricRegion(
                name=f"Region_{i+1}",
                nodes=community,
                geometry_type=geom_type,
                mean_curvature=mean_kappa,
                internal_edges=internal_edges // 2,  # Counted twice
                boundary_edges=region_boundary // 2
            ))

        return regions, boundary_edges

    def _generate_analysis(
        self,
        regions: List[GeometricRegion],
        boundary_edges: List[Tuple[str, str, float]],
        converged: bool
    ) -> str:
        """Generate human-readable analysis of decomposition."""
        lines = []

        lines.append("# Geometric Decomposition via Ricci Flow")
        lines.append("")
        lines.append("## Summary")
        lines.append(f"- Flow steps: {len(self.flow_history)}")
        lines.append(f"- Converged: {'Yes' if converged else 'No'}")
        lines.append(f"- Regions found: {len(regions)}")
        lines.append(f"- Boundary edges: {len(boundary_edges)}")
        lines.append("")

        # Region details
        lines.append("## Geometric Regions")
        lines.append("")
        lines.append("| Region | Size | Geometry | Mean Curvature | Internal Edges | Boundary |")
        lines.append("|--------|------|----------|----------------|----------------|----------|")

        for region in regions:
            lines.append(
                f"| {region.name} | {region.size} | {region.geometry_type.value} | "
                f"{region.mean_curvature:.4f} | {region.internal_edges} | {region.boundary_edges} |"
            )

        lines.append("")

        # List nodes in each region
        lines.append("## Region Contents")
        lines.append("")

        for region in regions:
            lines.append(f"### {region.name} ({region.geometry_type.value})")
            lines.append("")

            # Sample nodes
            sample_nodes = sorted(region.nodes)[:10]
            lines.append(f"**Nodes ({region.size} total):** {', '.join(sample_nodes)}")
            if region.size > 10:
                lines.append(f"  ... and {region.size - 10} more")
            lines.append("")

            # Interpretation
            if region.geometry_type == GeometryType.SPHERICAL:
                lines.append(f"*Interpretation*: This is a **dense cluster** of closely related concepts.")
                lines.append(f"Neighbors are highly similar - moving within this region is 'easy'.")
            elif region.geometry_type == GeometryType.HYPERBOLIC:
                lines.append(f"*Interpretation*: This is a **hierarchical/tree-like** structure.")
                lines.append(f"Concepts branch out - moving in this region involves paradigm shifts.")
            else:
                lines.append(f"*Interpretation*: This is a **linear/chain-like** structure.")
                lines.append(f"Concepts follow sequential development - historical timeline.")
            lines.append("")

        # Boundary edges (inter-region connections)
        lines.append("## Inter-Region Bridges")
        lines.append("")
        lines.append("These edges connect different geometric regions:")
        lines.append("")

        # Sort by weight (highest = strongest boundary)
        sorted_boundaries = sorted(boundary_edges, key=lambda x: -x[2])[:10]

        lines.append("| Source | Target | Weight | Interpretation |")
        lines.append("|--------|--------|--------|----------------|")

        for s, t, w in sorted_boundaries:
            interp = "Strong boundary" if w > 1.5 else "Moderate boundary" if w > 1.0 else "Weak boundary"
            lines.append(f"| {s} | {t} | {w:.4f} | {interp} |")

        lines.append("")

        # Thurston interpretation
        lines.append("## Thurston Geometrization Interpretation")
        lines.append("")
        lines.append("Just as Thurston's theorem decomposes 3-manifolds into pieces with")
        lines.append("uniform geometry, Ricci flow decomposes this knowledge graph into")
        lines.append("regions with uniform curvature:")
        lines.append("")

        spherical_count = sum(1 for r in regions if r.geometry_type == GeometryType.SPHERICAL)
        hyperbolic_count = sum(1 for r in regions if r.geometry_type == GeometryType.HYPERBOLIC)
        euclidean_count = sum(1 for r in regions if r.geometry_type == GeometryType.EUCLIDEAN)

        lines.append(f"- **Spherical pieces (S³-like):** {spherical_count} regions")
        lines.append(f"- **Hyperbolic pieces (H³-like):** {hyperbolic_count} regions")
        lines.append(f"- **Euclidean pieces (E³-like):** {euclidean_count} regions")
        lines.append("")

        if spherical_count > 0:
            lines.append("The spherical regions represent **schools of thought** or **paradigms**")
            lines.append("where concepts are densely interconnected.")
            lines.append("")

        if hyperbolic_count > 0:
            lines.append("The hyperbolic regions represent **branching structures** where")
            lines.append("concepts diverge into multiple research programs.")
            lines.append("")

        if len(boundary_edges) > 0:
            lines.append(f"The {len(boundary_edges)} boundary edges represent **paradigm bridges**")
            lines.append("where conceptual frameworks connect across geometric regions.")

        return "\n".join(lines)


def run_ricci_flow(category, max_steps: int = 50, dt: float = 0.1) -> DecompositionResult:
    """
    Convenience function to run Ricci flow on a category.

    Args:
        category: Category with objects and morphisms
        max_steps: Maximum flow steps
        dt: Time step size

    Returns:
        DecompositionResult with geometric regions
    """
    flow = DiscreteRicciFlow(category)
    return flow.flow(max_steps=max_steps, dt=dt)


# Example usage
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from evaluation.physics_dataset import create_physics_dataset

    print("=" * 70)
    print("Discrete Ricci Flow: Physics Dataset")
    print("=" * 70)
    print()

    # Create physics dataset
    store = create_physics_dataset()

    # Run Ricci flow
    result = run_ricci_flow(store, max_steps=30, dt=0.2)

    # Print analysis
    print()
    print(result.analysis)

    print()
    print("=" * 70)
    print(f"Found {result.num_regions} geometric regions")
    print(f"Converged: {result.converged}")
    print(f"Steps: {result.num_steps}")
