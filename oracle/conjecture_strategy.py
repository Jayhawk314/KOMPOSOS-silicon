# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Conjecture Gap Strategy
=======================

Scores Drug->Disease pairs by how many independent graph-theoretic reasons
suggest the relationship *should* exist but doesn't.

Existing strategies score evidence that paths exist; this strategy scores
structural reasons a path should exist but is missing. It wraps the gap-detection
logic from oracle/conjecture.py as a lightweight per-pair scorer.

Three checks fire for Drug->Disease pairs:
  1. Composition gap   -- count Drug->Protein->Disease 2-hop paths
  2. Structural hole   -- count shared proteins (common ancestors/descendants)
  3. Yoneda overlap    -- Jaccard overlap of outgoing target/type sets

Three additional checks are included for generality but return None for
Drug->Disease pairs (fiber membership, semantic similarity, temporal compatibility).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from oracle.prediction import Prediction, PredictionType, ConfidenceLevel
from oracle.strategies import InferenceStrategy
from core.category import Category


class _PairGraphCache:
    """
    Lazy graph cache for ConjectureStrategy. Mirrors the _GraphCache in
    conjecture.py but is owned by the strategy instance (populated once
    per benchmark run, shared across all pair evaluations).
    """

    def __init__(self, category: Category):
        self.category = category
        self._morphisms: list | None = None
        self._objects: list | None = None
        self._outgoing: Dict[str, list] | None = None
        self._incoming: Dict[str, list] | None = None
        self._existing: Set[Tuple[str, str]] | None = None
        self._object_map: Dict[str, object] | None = None

    @property
    def morphisms(self) -> list:
        if self._morphisms is None:
            self._morphisms = self.category.morphisms()
        return self._morphisms

    @property
    def objects(self) -> list:
        if self._objects is None:
            self._objects = self.category.objects()
        return self._objects

    @property
    def outgoing(self) -> Dict[str, list]:
        self._ensure_indices()
        return self._outgoing  # type: ignore[return-value]

    @property
    def incoming(self) -> Dict[str, list]:
        self._ensure_indices()
        return self._incoming  # type: ignore[return-value]

    @property
    def existing(self) -> Set[Tuple[str, str]]:
        if self._existing is None:
            self._existing = {(m.source, m.target) for m in self.morphisms}
        return self._existing

    @property
    def object_map(self) -> Dict[str, object]:
        if self._object_map is None:
            self._object_map = {obj.name: obj for obj in self.objects}
        return self._object_map

    def _ensure_indices(self):
        if self._outgoing is not None:
            return
        self._outgoing, self._incoming = {}, {}
        for m in self.morphisms:
            self._outgoing.setdefault(m.source, []).append(m)
            self._incoming.setdefault(m.target, []).append(m)


class ConjectureStrategy(InferenceStrategy):
    """
    Score drug-disease pairs by structural gap signals from the graph.

    For each pair, runs up to 6 checks (3 active for Drug->Disease) and
    produces a weighted-average confidence from the active signals.
    """

    name = "conjecture_gap"

    # Per-check weights (sum to 1.0)
    _WEIGHTS = {
        "composition_gap": 0.30,
        "structural_hole": 0.25,
        "yoneda_overlap": 0.20,
        "semantic": 0.10,
        "fiber": 0.10,
        "temporal": 0.05,
    }

    def __init__(
        self,
        category: Category,
        source_type: Optional[str] = None,
        target_type: Optional[str] = None,
        relation: str = "related_to",
    ):
        """
        Args:
            category: the category to score over.
            source_type / target_type: when set, only pairs whose endpoints have
                these ``type_name``s are scored. Leave both ``None`` (the default)
                for a fully generic scorer over any pair. The pharma profile uses
                ``source_type="Drug", target_type="Disease", relation="treats"``.
            relation: the morphism label attached to the conjectured edge.
        """
        super().__init__(category)
        self.source_type = source_type
        self.target_type = target_type
        self.relation = relation
        self._cache: _PairGraphCache | None = None

    def _get_cache(self) -> _PairGraphCache:
        if self._cache is None:
            self._cache = _PairGraphCache(self.category)
        return self._cache

    # ----- public interface -----

    def predict(self, source: str, target: str) -> List[Prediction]:
        """Score a single (source, target) pair for structural-gap signals."""
        cache = self._get_cache()

        src_obj = cache.object_map.get(source)
        tgt_obj = cache.object_map.get(target)
        if not src_obj or not tgt_obj:
            return []
        # Optional endpoint-type restriction (None => generic, any types).
        if self.source_type is not None and getattr(src_obj, "type_name", None) != self.source_type:
            return []
        if self.target_type is not None and getattr(tgt_obj, "type_name", None) != self.target_type:
            return []

        # Run all checks
        signals: Dict[str, Optional[float]] = {
            "composition_gap": self._check_composition_gap(source, target, cache),
            "structural_hole": self._check_structural_hole(source, target, cache),
            "yoneda_overlap": self._check_yoneda_overlap(source, target, cache),
            "semantic": self._check_semantic_similarity(source, target, cache),
            "fiber": self._check_fiber_membership(source, target, cache),
            "temporal": self._check_temporal_compatibility(source, target, cache),
        }

        # Filter to active (non-None) signals
        active = {k: v for k, v in signals.items() if v is not None}
        if not active:
            return []

        # Weighted average over active signals, renormalized
        total_weight = sum(self._WEIGHTS[k] for k in active)
        if total_weight <= 0:
            return []

        weighted_sum = sum(self._WEIGHTS[k] * v for k, v in active.items())
        score = weighted_sum / total_weight

        # Breadth bonus: reward multiple independent signals
        n_active = len(active)
        breadth_bonus = min(0.15, 0.05 * (n_active - 1))
        score = score + breadth_bonus

        # Scale down to tiebreaker range: this strategy fires broadly so must
        # not dominate the average. Cap at 0.45 to stay below primary strategies.
        score = min(0.45, score * 0.50)

        if score < 0.1:
            return []

        # Build reasoning string
        active_names = [f"{k}={v:.2f}" for k, v in active.items()]
        reasoning = (
            f"Structural gap: {n_active} signals active "
            f"({', '.join(active_names)}), breadth_bonus={breadth_bonus:.2f}"
        )

        return [Prediction(
            source=source,
            target=target,
            predicted_relation=self.relation,
            prediction_type=PredictionType.CONJECTURE_GAP,
            strategy_name=self.name,
            confidence=score,
            reasoning=reasoning,
            evidence={
                "signals": {k: round(v, 4) for k, v in active.items()},
                "n_active": n_active,
                "breadth_bonus": round(breadth_bonus, 4),
            },
        )]

    # ----- individual checks -----

    def _check_composition_gap(
        self, source: str, target: str, cache: _PairGraphCache
    ) -> Optional[float]:
        """
        Count Drug->Protein->Disease 2-hop paths where Drug->Disease is missing.
        Only fires when path_count >= 2 (single path is already captured by
        composition strategy). Returns 0.2 + 0.1 * (path_count - 1), capped at 1.0.
        """
        outgoing = cache.outgoing
        path_count = 0

        for m1 in outgoing.get(source, []):
            intermediate = m1.target
            # Check if intermediate connects to target
            for m2 in outgoing.get(intermediate, []):
                if m2.target == target:
                    path_count += 1

        # Only fire for multi-path support (single paths already scored by composition)
        if path_count < 2:
            return None

        return min(1.0, 0.2 + 0.1 * (path_count - 1))

    def _check_structural_hole(
        self, source: str, target: str, cache: _PairGraphCache
    ) -> Optional[float]:
        """
        Count shared proteins: common ancestors (X->source, X->target) and
        common descendants (source->X, target->X).
        Only fires when total >= 2 (single shared node is weak signal).
        Returns 0.2 + 0.1 * (total - 1), capped at 1.0.
        """
        outgoing = cache.outgoing
        incoming = cache.incoming

        # Common ancestors: nodes that point to both source and target
        source_ancestors = {m.source for m in incoming.get(source, [])}
        target_ancestors = {m.source for m in incoming.get(target, [])}
        common_ancestors = source_ancestors & target_ancestors

        # Common descendants: nodes that both source and target point to
        source_descendants = {m.target for m in outgoing.get(source, [])}
        target_descendants = {m.target for m in outgoing.get(target, [])}
        common_descendants = source_descendants & target_descendants

        total = len(common_ancestors) + len(common_descendants)
        if total < 2:
            return None

        return min(1.0, 0.2 + 0.1 * (total - 1))

    def _check_yoneda_overlap(
        self, source: str, target: str, cache: _PairGraphCache
    ) -> Optional[float]:
        """
        Jaccard overlap of outgoing target/type sets between source and target.
        Returns the Yoneda similarity if >= 0.3, else None.
        """
        outgoing = cache.outgoing

        src_mors = outgoing.get(source, [])
        tgt_mors = outgoing.get(target, [])

        if not src_mors or not tgt_mors:
            return None

        # Type overlap (morphism names/types)
        src_types = {m.name for m in src_mors}
        tgt_types = {m.name for m in tgt_mors}

        # Target overlap (where they point)
        src_targets = {m.target for m in src_mors}
        tgt_targets = {m.target for m in tgt_mors}

        type_union = src_types | tgt_types
        target_union = src_targets | tgt_targets

        type_sim = len(src_types & tgt_types) / max(len(type_union), 1)
        target_sim = len(src_targets & tgt_targets) / max(len(target_union), 1)
        yoneda_sim = (type_sim + target_sim) / 2

        if yoneda_sim < 0.4:
            return None

        return yoneda_sim

    def _check_fiber_membership(
        self, source: str, target: str, cache: _PairGraphCache
    ) -> Optional[float]:
        """
        Same (type, era) fiber -> signal. Always None for Drug->Disease pairs
        since they have different types by definition.
        """
        src_obj = cache.object_map.get(source)
        tgt_obj = cache.object_map.get(target)
        if not src_obj or not tgt_obj:
            return None

        # Different types can't share a fiber
        if getattr(src_obj, "type_name", None) != getattr(tgt_obj, "type_name", None):
            return None

        # Check era metadata
        src_meta = getattr(src_obj, "metadata", None) or {}
        tgt_meta = getattr(tgt_obj, "metadata", None) or {}
        src_era = src_meta.get("era")
        tgt_era = tgt_meta.get("era")

        if src_era and tgt_era and src_era == tgt_era:
            return 0.5

        return None

    def _check_semantic_similarity(
        self, source: str, target: str, cache: _PairGraphCache
    ) -> Optional[float]:
        """
        Embedding cosine similarity. Returns None if no embeddings available.
        """
        # No embeddings in the pharma pipeline
        return None

    def _check_temporal_compatibility(
        self, source: str, target: str, cache: _PairGraphCache
    ) -> Optional[float]:
        """
        Birth metadata compatibility. Returns None for pharma objects
        (drugs/diseases don't have birth metadata).
        """
        src_obj = cache.object_map.get(source)
        tgt_obj = cache.object_map.get(target)
        if not src_obj or not tgt_obj:
            return None

        src_meta = getattr(src_obj, "metadata", None) or {}
        tgt_meta = getattr(tgt_obj, "metadata", None) or {}

        if "birth" not in src_meta or "birth" not in tgt_meta:
            return None

        # Contemporary objects get a mild signal
        diff = abs(src_meta["birth"] - tgt_meta["birth"])
        if diff <= 20:
            return 0.4
        return None
