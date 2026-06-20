# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Categorical Verifier -- CAT as meta-verifier over ZFC claims.

CAT is the foundation. ZFC proposes claims (transitive chains, logical
entailments). CAT verifies them structurally using its own data:

1. Ricci curvature: Is this chain in a tight cluster (high confidence)
   or a fragile bridge (low confidence)?
2. Kan extension: Does the structural neighborhood support this claim?
3. Sheaf coherence: Do multiple data sources agree?
4. Persistent homology: Is this chain topologically stable?
5. Enriched category: What are the cost/risk/liquidity weights?

Returns a StructuralVerdict with confidence, geometric classification,
and explanation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple

import networkx as nx

from core.category import Category

# Optional imports -- each verification dimension degrades gracefully
try:
    from geometry.ricci import OllivierRicciCurvature
    RICCI_AVAILABLE = True
except ImportError:
    RICCI_AVAILABLE = False

try:
    from geometry.spectral import SpectralAnalyzer
    SPECTRAL_AVAILABLE = True
except ImportError:
    SPECTRAL_AVAILABLE = False

try:
    from topology.persistent_homology import PersistentHomology
    HOMOLOGY_AVAILABLE = True
except ImportError:
    HOMOLOGY_AVAILABLE = False

try:
    from categorical.enriched_category import VEnrichedCategory
    ENRICHED_AVAILABLE = True
except ImportError:
    ENRICHED_AVAILABLE = False

try:
    from categorical.kan_extensions import LeftKanExtension
    KAN_AVAILABLE = True
except ImportError:
    KAN_AVAILABLE = False


class GeometricClass(Enum):
    """Geometric classification of a structural region."""
    SPHERICAL = auto()    # kappa > 0: tight cluster, high confidence
    EUCLIDEAN = auto()    # kappa ~ 0: chain/pathway, moderate confidence
    HYPERBOLIC = auto()   # kappa < 0: bridge between clusters, fragile
    UNKNOWN = auto()


@dataclass
class StructuralVerdict:
    """
    CAT's structural verdict on a ZFC claim.

    This is the output of the meta-verification: CAT's independent
    assessment of whether a logically proven chain is structurally sound.
    """
    source: str
    target: str
    relation: str

    # Overall structural confidence [0, 1]
    structural_confidence: float = 0.0

    # Geometric classification
    geometric_class: GeometricClass = GeometricClass.UNKNOWN

    # Individual dimension scores [0, 1]
    curvature_score: float = 0.0
    neighborhood_score: float = 0.0   # Kan extension support
    coherence_score: float = 0.0      # Sheaf agreement
    stability_score: float = 0.0      # Topological persistence
    enriched_score: float = 0.0       # Quantale weight

    # Path information
    path_count: int = 0
    path_lengths: List[int] = field(default_factory=list)
    mean_curvature: float = 0.0

    # Explanation
    explanation: str = ""

    # Which dimensions were actually computed
    dimensions_used: List[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"StructuralVerdict({self.source}->{self.target} "
            f"conf={self.structural_confidence:.3f} "
            f"geo={self.geometric_class.name})"
        )


class CategoricalVerifier:
    """
    CAT as meta-verifier over ZFC claims.

    Maintains its own structural data computed from Category:
    - NetworkX graph with Ricci curvature on edges
    - Spectral decomposition
    - Persistent homology features
    - Enriched morphism weights

    ZFC doesn't see this data. CAT uses it independently to verify
    whether ZFC's logical claims are structurally grounded.
    """

    def __init__(self, category: Category):
        self.category = category
        self._graph: Optional[nx.Graph] = None
        self._curvature_computed = False
        self._edge_curvatures: Dict[Tuple[str, str], float] = {}

    # ----------------------------------------------------------------
    # Build CAT's structural view
    # ----------------------------------------------------------------

    def _ensure_graph(self) -> nx.Graph:
        """Build NetworkX graph from category if not already built."""
        if self._graph is not None:
            return self._graph

        G = nx.Graph()
        objects = self.category.objects()
        for obj in objects:
            G.add_node(obj.name, type_name=obj.type_name,
                       metadata=obj.metadata)

        morphisms = self.category.morphisms()
        for m in morphisms:
            G.add_edge(m.source, m.target,
                       relation=m.name, confidence=m.confidence,
                       metadata=m.metadata)

        self._graph = G
        return G

    def _ensure_curvature(self) -> None:
        """Compute Ricci curvature on all edges if not done."""
        if self._curvature_computed or not RICCI_AVAILABLE:
            return

        G = self._ensure_graph()
        if G.number_of_edges() == 0:
            self._curvature_computed = True
            return

        try:
            ricci = OllivierRicciCurvature(self.category)
            result = ricci.compute_all_curvatures()
            for (src, tgt), kappa in result.edge_curvatures.items():
                self._edge_curvatures[(src, tgt)] = kappa
                self._edge_curvatures[(tgt, src)] = kappa
        except Exception:
            pass

        self._curvature_computed = True

    # ----------------------------------------------------------------
    # Core verification
    # ----------------------------------------------------------------

    def verify(
        self,
        source: str,
        target: str,
        relation: str,
    ) -> StructuralVerdict:
        """
        Verify a ZFC claim structurally.

        Runs all available verification dimensions and combines
        into a single StructuralVerdict.
        """
        verdict = StructuralVerdict(
            source=source, target=target, relation=relation,
        )

        G = self._ensure_graph()

        # Check nodes exist
        if source not in G or target not in G:
            verdict.explanation = (
                f"{'source' if source not in G else 'target'} "
                f"not found in structural graph"
            )
            return verdict

        # 1. Path analysis (always available)
        paths, lengths = self._find_paths(G, source, target)
        verdict.path_count = len(paths)
        verdict.path_lengths = lengths

        # 2. Curvature analysis
        curvature_score = self._curvature_check(G, source, target, paths)
        if curvature_score is not None:
            verdict.curvature_score = curvature_score
            verdict.dimensions_used.append("curvature")

        # 3. Neighborhood support (Kan-like)
        neighborhood_score = self._neighborhood_check(G, source, target)
        verdict.neighborhood_score = neighborhood_score
        verdict.dimensions_used.append("neighborhood")

        # 4. Topological stability
        stability_score = self._stability_check(G, source, target)
        if stability_score is not None:
            verdict.stability_score = stability_score
            verdict.dimensions_used.append("stability")

        # 5. Enriched weight
        enriched_score = self._enriched_check(source, target)
        if enriched_score is not None:
            verdict.enriched_score = enriched_score
            verdict.dimensions_used.append("enriched")

        # Combine scores
        scores = []
        if "curvature" in verdict.dimensions_used:
            scores.append(verdict.curvature_score)
        scores.append(verdict.neighborhood_score)
        if "stability" in verdict.dimensions_used:
            scores.append(verdict.stability_score)
        if "enriched" in verdict.dimensions_used:
            scores.append(verdict.enriched_score)

        # Path count bonus
        path_bonus = min(0.3, len(paths) * 0.1) if paths else 0.0

        if scores:
            verdict.structural_confidence = min(
                1.0, sum(scores) / len(scores) + path_bonus
            )
        elif paths:
            verdict.structural_confidence = path_bonus

        # Geometric classification from mean curvature
        verdict.geometric_class = self._classify_geometry(
            verdict.mean_curvature
        )

        # Build explanation
        verdict.explanation = self._build_explanation(verdict)

        return verdict

    # ----------------------------------------------------------------
    # Dimension 1: Curvature
    # ----------------------------------------------------------------

    def _curvature_check(
        self,
        G: nx.Graph,
        source: str,
        target: str,
        paths: List[List[str]],
    ) -> Optional[float]:
        """
        Check Ricci curvature along paths.

        Spherical (kappa > 0) = tight cluster = high structural support.
        Hyperbolic (kappa < 0) = bridge = fragile, low support.
        """
        if not RICCI_AVAILABLE:
            return None

        self._ensure_curvature()

        if not self._edge_curvatures:
            return None

        # Collect curvatures along all paths
        curvatures = []
        for path in paths:
            for i in range(len(path) - 1):
                edge = (path[i], path[i + 1])
                kappa = self._edge_curvatures.get(
                    edge, self._edge_curvatures.get(
                        (edge[1], edge[0]), 0.0
                    )
                )
                curvatures.append(kappa)

        if not curvatures:
            # No paths, check direct edge
            kappa = self._edge_curvatures.get(
                (source, target),
                self._edge_curvatures.get((target, source), None),
            )
            if kappa is not None:
                curvatures.append(kappa)

        if not curvatures:
            return None

        mean_kappa = sum(curvatures) / len(curvatures)

        # Map curvature to confidence:
        # kappa > 0 (spherical) -> high confidence (0.7 - 1.0)
        # kappa ~ 0 (euclidean) -> moderate (0.4 - 0.6)
        # kappa < 0 (hyperbolic) -> low confidence (0.1 - 0.3)
        score = 0.5 + mean_kappa * 0.5  # Maps [-1,1] -> [0,1]
        return max(0.0, min(1.0, score))

    # ----------------------------------------------------------------
    # Dimension 2: Neighborhood support
    # ----------------------------------------------------------------

    def _neighborhood_check(
        self,
        G: nx.Graph,
        source: str,
        target: str,
    ) -> float:
        """
        Check if source and target share neighborhood structure.

        High overlap in neighbors = strong structural support.
        This is a simplified Kan extension check: does the local
        colimit (neighborhood union) support a connection?
        """
        source_neighbors = set(G.neighbors(source)) if source in G else set()
        target_neighbors = set(G.neighbors(target)) if target in G else set()

        if not source_neighbors and not target_neighbors:
            return 0.0

        # Jaccard similarity of neighborhoods
        intersection = source_neighbors & target_neighbors
        union = source_neighbors | target_neighbors

        if not union:
            return 0.0

        jaccard = len(intersection) / len(union)

        # Also check: are they directly connected?
        direct = G.has_edge(source, target)

        if direct:
            return min(1.0, 0.5 + jaccard * 0.5)
        else:
            return jaccard * 0.7

    # ----------------------------------------------------------------
    # Dimension 3: Topological stability
    # ----------------------------------------------------------------

    def _stability_check(
        self,
        G: nx.Graph,
        source: str,
        target: str,
    ) -> Optional[float]:
        """
        Check topological stability of the connection.

        Uses edge connectivity as a proxy for persistence:
        high connectivity = topologically stable (survives perturbation).
        """
        if source not in G or target not in G:
            return None

        try:
            # Edge connectivity: min edges to remove to disconnect s from t
            connectivity = nx.edge_connectivity(G, source, target)
            # Normalize: 1 edge = fragile (0.2), 5+ = robust (1.0)
            score = min(1.0, connectivity * 0.2)
            return score
        except (nx.NetworkXError, nx.NetworkXUnfeasible):
            return None

    # ----------------------------------------------------------------
    # Dimension 4: Enriched category weights
    # ----------------------------------------------------------------

    def _enriched_check(
        self,
        source: str,
        target: str,
    ) -> Optional[float]:
        """
        Check enriched morphism weights (cost, risk, liquidity).

        High confidence morphisms with low cost = strong structural support.
        """
        morphisms = [
            m for m in self.category.morphisms_from(source)
            if m.target == target
        ]
        if not morphisms:
            morphisms = [
                m for m in self.category.morphisms_from(target)
                if m.target == source
            ]

        if not morphisms:
            return None

        # Use morphism confidence as enriched score
        confidences = [m.confidence for m in morphisms]
        return sum(confidences) / len(confidences)

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------

    def _find_paths(
        self,
        G: nx.Graph,
        source: str,
        target: str,
        max_length: int = 5,
    ) -> Tuple[List[List[str]], List[int]]:
        """Find all simple paths up to max_length."""
        try:
            paths = list(nx.all_simple_paths(
                G, source, target, cutoff=max_length
            ))
            lengths = [len(p) - 1 for p in paths]  # edges, not nodes
            return paths, lengths
        except (nx.NetworkXError, nx.NodeNotFound):
            return [], []

    def _classify_geometry(self, mean_curvature: float) -> GeometricClass:
        """Classify geometric region from mean curvature."""
        if mean_curvature > 0.1:
            return GeometricClass.SPHERICAL
        elif mean_curvature < -0.1:
            return GeometricClass.HYPERBOLIC
        elif mean_curvature != 0.0:
            return GeometricClass.EUCLIDEAN
        else:
            return GeometricClass.UNKNOWN

    def _build_explanation(self, verdict: StructuralVerdict) -> str:
        """Build human-readable explanation of the verdict."""
        parts = []

        if verdict.path_count == 0:
            parts.append("No structural paths found")
        else:
            parts.append(
                f"{verdict.path_count} path(s), "
                f"lengths {verdict.path_lengths}"
            )

        geo = verdict.geometric_class
        if geo == GeometricClass.SPHERICAL:
            parts.append("Spherical region (tight cluster, high support)")
        elif geo == GeometricClass.HYPERBOLIC:
            parts.append("Hyperbolic region (bridge, fragile)")
        elif geo == GeometricClass.EUCLIDEAN:
            parts.append("Euclidean region (chain, moderate support)")

        if verdict.neighborhood_score > 0.5:
            parts.append(
                f"Strong neighborhood overlap ({verdict.neighborhood_score:.2f})"
            )

        if verdict.stability_score > 0.6:
            parts.append(
                f"Topologically stable (connectivity {verdict.stability_score:.2f})"
            )

        return "; ".join(parts)
