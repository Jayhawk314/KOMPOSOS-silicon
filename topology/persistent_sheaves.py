# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Persistent Sheaves: Sheaf Cohomology over Filtered Simplicial Complexes

Combines persistent homology (tracking features across filtration scales)
with sheaf theory (checking coherence across overlaps). This tracks not
just "a feature appeared/disappeared" but "a COHERENT structure
appeared/disappeared."

A cellular sheaf F on a simplicial complex K assigns:
  - A value space F(σ) to each simplex σ
  - A restriction map F(σ←τ): F(σ) → F(τ) for each face relation τ ⊂ σ

The restriction maps must satisfy:
  - F(σ←σ) = identity (restricting to yourself changes nothing)
  - F(τ←ρ) ∘ F(σ←τ) = F(σ←ρ) for ρ ⊂ τ ⊂ σ (transitivity)

Sheaf cohomology measures:
  - H⁰: global sections (data that's consistent everywhere)
  - H¹: obstructions to gluing (where local data can't be stitched together)

Persistent sheaf = run this across a filtration:
  - At each scale t, compute sheaf cohomology of the active subcomplex
  - Track which coherent features persist and which break down
  - Weight persistence by coherence: long-lived + coherent = important

Mathematical basis:
  - Curry, "Sheaves, Cosheaves, and Applications" (2014)
  - Robinson, "Topological Signal Processing" (2014)
  - Ghrist & Hansen, "Toward a spectral theory of cellular sheaves" (2019)
  - Kashiwara & Schapira, "Sheaves on Manifolds" (1990)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional, Any, Callable
from collections import defaultdict
import math


@dataclass
class SheafSection:
    """
    A section of a sheaf over a simplex.

    In sheaf theory, a section s ∈ F(σ) is a "local datum" assigned
    to simplex σ. Sections on neighboring simplices must agree when
    restricted to their shared faces (the gluing condition).
    """
    simplex: Tuple[int, ...]     # the simplex this section lives over
    value: float                  # the section value
    filtration: float             # when this simplex enters the complex
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash((self.simplex, self.filtration))

    def __repr__(self):
        return f"Section({self.simplex}, v={self.value:.3f}, f={self.filtration:.2f})"


@dataclass
class RestrictionMap:
    """
    A restriction map F(σ←τ): F(σ) → F(τ) for face relation τ ⊂ σ.

    In the scalar case (F(σ) = ℝ), this is just multiplication by a scalar.
    The restriction "forgets" information when going from a larger simplex
    to a smaller face.
    """
    source: Tuple[int, ...]    # σ (larger simplex)
    target: Tuple[int, ...]    # τ (face of σ)
    weight: float = 1.0        # scalar restriction factor

    def apply(self, value: float) -> float:
        """Restrict a section value from source to target."""
        return value * self.weight


@dataclass
class FiberedPersistencePair:
    """
    A persistence pair enriched with sheaf coherence data.

    Standard persistent homology gives (birth, death, dimension).
    We add coherence tracking: at each filtration value, how well
    do the sections over this feature agree on overlaps?
    """
    birth: float
    death: float
    dimension: int

    # Sheaf enrichment
    coherence_at_birth: float = 1.0     # sheaf coherence when feature appears
    coherence_at_death: float = 0.0     # sheaf coherence when feature disappears
    coherence_history: List[Tuple[float, float]] = field(default_factory=list)

    # Cycle data
    representative_cycle: List[Tuple[int, ...]] = field(default_factory=list)
    section_values: Dict[Tuple[int, ...], float] = field(default_factory=dict)

    @property
    def persistence(self) -> float:
        """Lifespan: death - birth."""
        if self.death == float('inf'):
            return float('inf')
        return self.death - self.birth

    @property
    def weighted_persistence(self) -> float:
        """
        Persistence weighted by average coherence.

        A feature that persists long AND stays coherent is more important
        than one that persists long but loses coherence.
        """
        if not self.coherence_history:
            return self.persistence if self.persistence != float('inf') else 0.0

        avg_coh = sum(c for _, c in self.coherence_history) / len(self.coherence_history)

        if self.persistence == float('inf'):
            return avg_coh * 1000.0  # large but finite proxy
        return self.persistence * avg_coh

    @property
    def average_coherence(self) -> float:
        """Mean coherence across the feature's lifetime."""
        if not self.coherence_history:
            return self.coherence_at_birth
        return sum(c for _, c in self.coherence_history) / len(self.coherence_history)

    def __repr__(self):
        death_str = "inf" if self.death == float('inf') else f"{self.death:.2f}"
        return (f"FiberedH{self.dimension}({self.birth:.2f}, {death_str}, "
                f"coh={self.average_coherence:.2f})")


class PersistentSheafDiagram:
    """
    Persistence diagram enriched with sheaf coherence.

    Like a standard PersistenceDiagram but each pair carries
    coherence data: how well the sheaf sections agree across
    the feature's lifetime.
    """

    def __init__(self, pairs: List[FiberedPersistencePair] = None):
        self.pairs: List[FiberedPersistencePair] = pairs or []

    def betti_numbers_at(self, t: float) -> Dict[int, int]:
        """Standard Betti numbers at filtration value t."""
        betti = defaultdict(int)
        for pair in self.pairs:
            if pair.birth <= t and (pair.death == float('inf') or t < pair.death):
                betti[pair.dimension] += 1
        return dict(betti)

    def coherent_betti_at(self, t: float,
                          min_coherence: float = 0.5) -> Dict[int, int]:
        """
        Betti numbers counting only coherent features.

        A feature counts only if its coherence at time t exceeds
        the threshold. This filters out topological features that
        are "technically alive" but have lost their coherent structure.
        """
        betti = defaultdict(int)
        for pair in self.pairs:
            if pair.birth <= t and (pair.death == float('inf') or t < pair.death):
                # Find coherence at time t
                coh = self._coherence_at(pair, t)
                if coh >= min_coherence:
                    betti[pair.dimension] += 1
        return dict(betti)

    def _coherence_at(self, pair: FiberedPersistencePair,
                      t: float) -> float:
        """Interpolate coherence at a specific filtration value."""
        if not pair.coherence_history:
            return pair.coherence_at_birth

        # Find bracketing entries
        prev_t, prev_c = pair.coherence_history[0]
        for hist_t, hist_c in pair.coherence_history:
            if hist_t > t:
                # Linear interpolation
                if hist_t == prev_t:
                    return hist_c
                frac = (t - prev_t) / (hist_t - prev_t)
                return prev_c + frac * (hist_c - prev_c)
            prev_t, prev_c = hist_t, hist_c

        return prev_c

    def coherence_loss_events(self) -> List[Dict[str, Any]]:
        """
        Points where a persistent feature loses coherence.

        These are significant: a topological feature still exists
        but its structure is breaking down. Often signals a
        qualitative change in the data.
        """
        events = []
        for pair in self.pairs:
            if len(pair.coherence_history) < 2:
                continue

            for i in range(1, len(pair.coherence_history)):
                prev_t, prev_c = pair.coherence_history[i - 1]
                curr_t, curr_c = pair.coherence_history[i]

                # Significant drop: > 0.3 drop
                if prev_c - curr_c > 0.3:
                    events.append({
                        "pair": pair,
                        "filtration": curr_t,
                        "coherence_before": prev_c,
                        "coherence_after": curr_c,
                        "drop": prev_c - curr_c,
                        "dimension": pair.dimension,
                    })

        return sorted(events, key=lambda e: -e["drop"])

    def total_weighted_persistence(self) -> float:
        """Sum of persistence * coherence for all pairs."""
        return sum(p.weighted_persistence for p in self.pairs
                   if p.persistence != float('inf'))

    def __repr__(self):
        return f"PersistentSheafDiagram({len(self.pairs)} pairs)"


class CellularSheaf:
    """
    A cellular sheaf on a simplicial complex.

    Assigns scalar values to simplices and defines restriction maps
    between simplices and their faces. This is the data structure
    that PersistentSheafComputer uses to track coherence.

    For a simplex σ with face τ:
      restriction(σ, τ): F(σ) → F(τ)
      coherence at σ = how well restriction(σ, τ_i) agrees for all faces τ_i
    """

    def __init__(self):
        self.sections: Dict[Tuple[int, ...], float] = {}
        self.restrictions: Dict[Tuple[Tuple[int, ...], Tuple[int, ...]], float] = {}

    def set_section(self, simplex: Tuple[int, ...], value: float):
        """Assign a section value to a simplex."""
        self.sections[tuple(sorted(simplex))] = value

    def set_restriction(self, source: Tuple[int, ...],
                        target: Tuple[int, ...], weight: float = 1.0):
        """Set restriction map weight from source to face target."""
        key = (tuple(sorted(source)), tuple(sorted(target)))
        self.restrictions[key] = weight

    def restrict(self, source: Tuple[int, ...],
                 target: Tuple[int, ...]) -> float:
        """Apply restriction map: F(σ) → F(τ)."""
        s = tuple(sorted(source))
        t = tuple(sorted(target))
        key = (s, t)
        weight = self.restrictions.get(key, 1.0)
        value = self.sections.get(s, 0.0)
        return value * weight

    def local_coherence(self, simplex: Tuple[int, ...]) -> float:
        """
        Compute local coherence at a simplex.

        Measures how well the section on σ agrees with sections on
        its faces after restriction. Perfect coherence = 1.0.

        For each face τ_i of σ:
          disagreement(σ, τ_i) = |F_{σ←τ_i}(section(σ)) - section(τ_i)|
        Coherence = 1 - avg(relative disagreement)

        This is the per-simplex version of the sheaf total variation
        E(x) = Σ_e ||F_{u→e}x_u - F_{v→e}x_v||² from Hansen & Ghrist.
        """
        simplex = tuple(sorted(simplex))

        if len(simplex) <= 1:
            return 1.0  # Vertices are always coherent

        section_val = self.sections.get(simplex, 0.0)
        faces = self._faces(simplex)

        if not faces:
            return 1.0

        total_error = 0.0
        num_faces = 0

        for face in faces:
            face = tuple(sorted(face))
            restricted = self.restrict(simplex, face)
            face_val = self.sections.get(face, 0.0)

            if abs(restricted) + abs(face_val) > 0:
                error = abs(restricted - face_val) / max(abs(restricted), abs(face_val), 1e-10)
            else:
                error = 0.0

            total_error += error
            num_faces += 1

        if num_faces == 0:
            return 1.0

        avg_error = total_error / num_faces
        return max(0.0, 1.0 - avg_error)

    def global_coherence(self) -> float:
        """
        Average local coherence across all simplices.

        This is the sheaf's overall consistency score.
        """
        if not self.sections:
            return 1.0

        coherences = []
        for simplex in self.sections:
            if len(simplex) > 1:  # Skip vertices
                coherences.append(self.local_coherence(simplex))

        if not coherences:
            return 1.0

        return sum(coherences) / len(coherences)

    def coboundary(self, dim: int = 0) -> Dict[Tuple[int, ...], float]:
        """
        Compute the coboundary map δ^dim : C^dim -> C^{dim+1}.

        For dim=0 (edges from vertices):
          (δx)_e = F_{v0→e} x_{v0} - F_{v1→e} x_{v1}
          with signed incidence: (-1)^i where i is the position of
          the omitted vertex in the face.

        For dim=1 (triangles from edges):
          (δx)_{(v0,v1,v2)} = F_{e01} x_{e01} - F_{e02} x_{e02} + F_{e12} x_{e12}
          (alternating signs from the boundary operator)

        The coboundary measures "disagreement." Kernel of δ^0 = global
        sections (H^0). Image of δ^0 / kernel of δ^1 gives H^1.

        Hansen & Ghrist, "Toward a spectral theory of cellular sheaves" (2019).
        """
        result = {}

        target_dim = dim + 1
        for simplex in self.sections:
            if len(simplex) != target_dim + 1:
                continue

            # Sum over faces with alternating signs
            coboundary_val = 0.0
            faces = self._faces(simplex)
            for i, face in enumerate(faces):
                face = tuple(sorted(face))
                sign = (-1) ** i
                face_val = self.sections.get(face, 0.0)
                r = self.restrictions.get((simplex, face), 1.0)
                coboundary_val += sign * r * face_val

            result[simplex] = coboundary_val

        return result

    def total_variation(self) -> float:
        """
        Sheaf total variation: E(x) = ||δ⁰x||² = Σ_e ||F_{u→e}x_u - F_{v→e}x_v||².

        This is x^T L_F x where L_F is the sheaf Laplacian.
        Equals zero iff x is a global section (perfect coherence).

        Hansen & Ghrist, "Toward a spectral theory of cellular sheaves" (2019).
        """
        delta = self.coboundary(dim=0)
        return sum(v ** 2 for v in delta.values())

    def sheaf_betti_0(self) -> int:
        """
        Sheaf Betti number β₀ = dim ker(δ⁰) = number of independent
        global sections.

        For scalar sheaves, this counts connected components where
        sections agree on all edges. β₀ = 0 means no global section
        exists (total disagreement).

        Computed by counting edges with zero coboundary.
        """
        delta = self.coboundary(dim=0)
        if not delta:
            # No edges: every vertex is its own global section
            return sum(1 for s in self.sections if len(s) == 1)

        # Count edges with near-zero coboundary
        zero_edges = sum(1 for v in delta.values() if abs(v) < 1e-9)
        total_edges = len(delta)

        # For scalar sheaves: if all edges have zero coboundary,
        # one global section exists per connected component
        vertices = [s for s in self.sections if len(s) == 1]
        if total_edges == 0:
            return len(vertices)
        if zero_edges == total_edges:
            # All consistent — count connected components
            return self._count_components()
        return 0

    def _count_components(self) -> int:
        """Count connected components using edges in the sheaf."""
        vertices = {s[0] for s in self.sections if len(s) == 1}
        if not vertices:
            return 0

        parent = {v: v for v in vertices}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for simplex in self.sections:
            if len(simplex) == 2:
                v0, v1 = simplex
                if v0 in parent and v1 in parent:
                    r0, r1 = find(v0), find(v1)
                    if r0 != r1:
                        parent[r0] = r1

        return len({find(v) for v in vertices})

    def _faces(self, simplex: Tuple[int, ...]) -> List[Tuple[int, ...]]:
        """Get all codimension-1 faces of a simplex."""
        if len(simplex) <= 1:
            return []
        faces = []
        for i in range(len(simplex)):
            face = simplex[:i] + simplex[i+1:]
            faces.append(face)
        return faces


class PersistentSheafComputer:
    """
    Computes persistent sheaves from a simplicial complex + section data.

    Algorithm:
    1. Run standard persistent homology to get birth/death pairs
    2. At each filtration value, build a cellular sheaf on the active subcomplex
    3. Compute sheaf coherence (do sections agree on overlaps?)
    4. Track coherence alongside persistence
    5. Return enriched persistence diagram
    """

    def __init__(self, monoidal=None):
        """
        Args:
            monoidal: A MonoidalStructure for composing section values.
                      If None, uses multiplication (MULTIPLICATIVE_QUANTALE).
        """
        self.monoidal = monoidal

    def compute(self, simplicial_complex,
                section_fn: Callable = None,
                num_samples: int = 10) -> PersistentSheafDiagram:
        """
        Compute persistent sheaf diagram.

        Args:
            simplicial_complex: A SimplicialComplex from persistent_homology.py
            section_fn: Function(simplex_vertices, filtration) -> float
                        Assigns section values. Default: edge weight or 1.0.
            num_samples: How many filtration values to sample for coherence.

        Returns:
            PersistentSheafDiagram with coherence-enriched pairs.
        """
        from .persistent_homology import PersistentHomologyComputer

        # Step 1: Standard persistent homology
        ph_computer = PersistentHomologyComputer()
        standard_diagram = ph_computer.compute(simplicial_complex)

        if section_fn is None:
            section_fn = self._default_section_fn

        # Step 2: Get filtration range
        filt_values = sorted(set(
            s.filtration_value for s in simplicial_complex.simplices
        ))
        if not filt_values:
            return PersistentSheafDiagram([])

        # Sample filtration values for coherence tracking
        if len(filt_values) > num_samples:
            step = max(1, len(filt_values) // num_samples)
            sample_values = filt_values[::step]
        else:
            sample_values = filt_values

        # Step 3: Compute sheaf coherence at each sample
        coherence_at_t: Dict[float, float] = {}
        sheaf_at_t: Dict[float, CellularSheaf] = {}

        for t in sample_values:
            sheaf = self._build_sheaf_at(simplicial_complex, t, section_fn)
            sheaf_at_t[t] = sheaf
            coherence_at_t[t] = sheaf.global_coherence()

        # Step 4: Enrich persistence pairs with coherence
        enriched_pairs = []
        for pair in standard_diagram.pairs:
            coherence_history = []

            for t in sample_values:
                if pair.birth <= t and (pair.death == float('inf') or t < pair.death):
                    coherence_history.append((t, coherence_at_t.get(t, 1.0)))

            # Coherence at birth/death
            coh_birth = coherence_at_t.get(pair.birth, 1.0)
            if not coh_birth and coherence_history:
                coh_birth = coherence_history[0][1] if coherence_history else 1.0

            coh_death = 0.0
            if pair.death != float('inf') and coherence_history:
                coh_death = coherence_history[-1][1] if coherence_history else 0.0

            enriched = FiberedPersistencePair(
                birth=pair.birth,
                death=pair.death,
                dimension=pair.dimension,
                coherence_at_birth=coh_birth,
                coherence_at_death=coh_death,
                coherence_history=coherence_history,
            )
            enriched_pairs.append(enriched)

        return PersistentSheafDiagram(enriched_pairs)

    def _build_sheaf_at(self, simplicial_complex, t: float,
                        section_fn: Callable) -> CellularSheaf:
        """Build a cellular sheaf on the subcomplex alive at filtration t."""
        sheaf = CellularSheaf()

        for simplex in simplicial_complex.simplices:
            if simplex.filtration_value <= t:
                v = tuple(sorted(simplex.vertices))
                value = section_fn(v, t)
                sheaf.set_section(v, value)

                # Set restriction maps for faces
                if len(v) > 1:
                    for i in range(len(v)):
                        face = v[:i] + v[i+1:]
                        sheaf.set_restriction(v, face, 1.0)

        return sheaf

    def _default_section_fn(self, simplex: Tuple[int, ...],
                            filtration: float) -> float:
        """Default section function: 1.0 for vertices, 1/dim for higher."""
        dim = len(simplex) - 1
        if dim == 0:
            return 1.0
        return 1.0 / (dim + 1)


class TemporalPersistentSheaf:
    """
    Bridge: temporal event streams -> persistent sheaf analysis.

    Combines temporal_sheaves.py (event stream coherence) with
    persistent sheaf computation. Answers: which temporal patterns
    persist AND stay coherent across scales?
    """

    def __init__(self, window_size: float = 300,
                 proximity_threshold: float = 60.0):
        """
        Args:
            window_size: Time window size for temporal sheaf (seconds).
            proximity_threshold: Max time difference to create an edge
                                 between events (seconds).
        """
        self.window_size = window_size
        self.proximity_threshold = proximity_threshold

    def analyze(self, events) -> Dict[str, Any]:
        """
        Full analysis: temporal coherence + persistence.

        1. Build simplicial complex from events:
           - Entities = vertices
           - Co-occurring events = edges (threshold by time proximity)
        2. Use timestamps as filtration values
        3. Compute persistent sheaf
        4. Return: which patterns persist AND stay coherent?

        Args:
            events: List of Event objects from temporal_sheaves.py

        Returns:
            {
                "persistent_sheaf": PersistentSheafDiagram,
                "temporal_coherence": dict (from TemporalSheafChecker),
                "coherent_features": int,
                "total_features": int,
                "weighted_persistence": float,
            }
        """
        from .temporal_sheaves import TemporalSheafChecker
        from .persistent_homology import SimplicialComplex

        if not events:
            return {
                "persistent_sheaf": PersistentSheafDiagram([]),
                "temporal_coherence": {"is_coherent": True, "violations": []},
                "coherent_features": 0,
                "total_features": 0,
                "weighted_persistence": 0.0,
            }

        # Step 1: Temporal coherence check
        checker = TemporalSheafChecker(self.window_size)
        temporal_result = checker.check_coherence(events)

        # Step 2: Build simplicial complex from events
        sc = SimplicialComplex()
        entity_to_vertex = {}
        vertex_counter = 0

        # Assign vertices to entities
        for event in events:
            entity = event.metadata.get("entity", event.source)
            if entity and entity not in entity_to_vertex:
                entity_to_vertex[entity] = vertex_counter
                sc.add_simplex((vertex_counter,), event.timestamp)
                vertex_counter += 1

        # Add edges for co-occurring events
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        for i in range(len(sorted_events)):
            for j in range(i + 1, len(sorted_events)):
                ei, ej = sorted_events[i], sorted_events[j]
                time_diff = abs(ej.timestamp - ei.timestamp)

                if time_diff > self.proximity_threshold:
                    break  # Events too far apart

                entity_i = ei.metadata.get("entity", ei.source)
                entity_j = ej.metadata.get("entity", ej.source)

                if (entity_i and entity_j and
                        entity_i != entity_j and
                        entity_i in entity_to_vertex and
                        entity_j in entity_to_vertex):
                    vi = entity_to_vertex[entity_i]
                    vj = entity_to_vertex[entity_j]
                    filt = max(ei.timestamp, ej.timestamp)
                    sc.add_simplex((vi, vj), filt)

        # Step 3: Compute persistent sheaf
        def event_section_fn(simplex, t):
            """Section = number of events involving this simplex's entities at time t."""
            count = 0
            for event in events:
                entity = event.metadata.get("entity", event.source)
                if entity in entity_to_vertex:
                    vid = entity_to_vertex[entity]
                    if vid in simplex and event.timestamp <= t:
                        count += 1
            return float(count) if count > 0 else 1.0

        computer = PersistentSheafComputer()
        sheaf_diagram = computer.compute(sc, event_section_fn)

        # Step 4: Summarize
        coherent_count = sum(
            1 for p in sheaf_diagram.pairs
            if p.average_coherence >= 0.5
        )

        return {
            "persistent_sheaf": sheaf_diagram,
            "temporal_coherence": temporal_result,
            "coherent_features": coherent_count,
            "total_features": len(sheaf_diagram.pairs),
            "weighted_persistence": sheaf_diagram.total_weighted_persistence(),
            "num_entities": len(entity_to_vertex),
            "num_events": len(events),
        }
