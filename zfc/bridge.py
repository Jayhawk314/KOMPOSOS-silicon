# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
Dual Engine Bridge -- CAT-over-ZFC Architecture.

ZFC proposes claims (logical entailments, transitive chains).
CAT verifies them structurally (curvature, topology, neighborhoods).

Architecture:

    StoreAdapter
      /        \
    ZFC        CAT (CategoricalVerifier)
  (proposes)   (verifies structurally)
      \        /
    DualEngineBridge
         |
      System 3
     (Meta Kan)

Delta classification:
    AGREE  -- ZFC proves it, CAT confirms structurally
    ORPHAN -- ZFC proves it, CAT says structure doesn't support it
             (logically forced but geometrically unsound)
    HOLLOW -- ZFC can't prove it, but CAT sees structural pattern
             (novel discoveries -- geometrically real, logically baseless)
    REJECT -- neither engine supports it

Domain-agnostic: no hardcoded relation names.
Uses list() when iterating dict keys to avoid RuntimeError on dict mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .meta_kan import (
    DeltaType,
    Resolution,
    Episode,
    MetaPrediction,
    System3Oracle,
)
from .store_adapter import StoreAdapter
from .logic import LogicOracle
from .well_ordering import OrdinalOracle
from core.category import Category

# Optional: CategoricalVerifier for structural verification
try:
    from oracle.categorical_verifier import CategoricalVerifier, StructuralVerdict
    CAT_VERIFIER_AVAILABLE = True
except ImportError:
    CAT_VERIFIER_AVAILABLE = False


# ================================================================
# DualResult -- the outcome of running both engines
# ================================================================

@dataclass
class DualResult:
    """
    Result of running both engines on the same query.

    Contains ZFC's logical judgment, CAT's structural verdict,
    the delta classification, and System 3 meta-prediction.
    """
    source: str
    target: str
    relation: str

    # ZFC judgment (runs first -- proposes)
    zfc_says: bool = False
    zfc_confidence: float = 0.0
    zfc_witness: Optional[str] = None
    zfc_rank_gap: int = 0

    # CAT judgment (runs second -- verifies structurally)
    cat_says: bool = False
    cat_confidence: float = 0.0
    cat_paths: int = 0
    cat_path_lengths: List[int] = field(default_factory=list)
    cat_geometric_class: str = "UNKNOWN"
    cat_explanation: str = ""

    # Delta
    delta_type: DeltaType = DeltaType.UNKNOWN

    # System 3 meta-prediction (if any)
    meta_prediction: Optional[MetaPrediction] = None

    # Evidence from evolved axioms (if any)
    evidence: Optional[Dict[str, Any]] = field(default=None)

    @property
    def agreement(self) -> bool:
        """Do the two engines agree?"""
        return self.cat_says == self.zfc_says

    def __repr__(self) -> str:
        return (
            f"DualResult({self.source}->{self.target} [{self.relation}] "
            f"delta={self.delta_type.name} "
            f"zfc={self.zfc_confidence:.2f} cat={self.cat_confidence:.2f} "
            f"geo={self.cat_geometric_class})"
        )


# ================================================================
# DualEngineBridge
# ================================================================

class DualEngineBridge:
    """
    CAT-over-ZFC dual engine bridge.

    ZFC runs first: proves logical entailments from the store.
    CAT runs second: verifies each claim structurally using its own
    data (curvature, topology, neighborhoods, enriched weights).

    System 3 (Meta Kan) learns from past query episodes to predict
    which delta types to expect.

    Domain-agnostic: reads whatever relations are in the store.
    """

    def __init__(
        self,
        adapter: StoreAdapter,
        category=None,
        system3_name: str = "System3",
    ):
        self.adapter = adapter
        self.logic: LogicOracle = adapter.to_logic_oracle()
        self.category: Category = adapter.to_category()
        self.system3 = System3Oracle(system3_name)
        self._episode_counter = 0

        # Build CategoricalVerifier if category provided and available
        self._verifier: Optional[Any] = None
        if category is not None and CAT_VERIFIER_AVAILABLE:
            self._verifier = CategoricalVerifier(category)
        elif CAT_VERIFIER_AVAILABLE:
            # Try to get category from adapter
            try:
                self._verifier = CategoricalVerifier(adapter.category)
            except (AttributeError, Exception):
                pass

    # ----------------------------------------------------------------
    # Core: ZFC proposes, CAT verifies
    # ----------------------------------------------------------------

    def query(
        self,
        source: str,
        target: str,
        relation: str,
        domain: str = "",
        record: bool = True,
    ) -> DualResult:
        """
        Run the dual engine on a (source, target, relation) query.

        1. ZFC proposes: check if relation(source, target) is logically entailed.
        2. CAT verifies: structurally verify the claim using curvature,
           neighborhood overlap, topological stability, enriched weights.
        3. Classify the delta.
        4. Optionally record the episode in System 3.

        Returns:
            DualResult with both judgments and delta classification.
        """
        # -- Step 1: ZFC proposes ------------------------------------
        zfc_says, zfc_conf, zfc_witness = self.logic.predict_relation(
            relation, source, target
        )
        zfc_rank_gap = self._rank_gap(source, target)

        # -- Step 2: CAT verifies structurally -----------------------
        if self._verifier is not None:
            verdict = self._verifier.verify(source, target, relation)
            cat_says = verdict.structural_confidence > 0.3
            cat_conf = verdict.structural_confidence
            cat_paths = verdict.path_count
            cat_path_lengths = verdict.path_lengths
            cat_geometric_class = verdict.geometric_class.name
            cat_explanation = verdict.explanation
        else:
            # Fallback: simple path check
            paths, path_lengths = self._cat_check(source, target)
            cat_says = len(paths) > 0
            cat_conf = min(1.0, len(paths) * 0.3) if cat_says else 0.0
            cat_paths = len(paths)
            cat_path_lengths = path_lengths
            cat_geometric_class = "UNKNOWN"
            cat_explanation = ""

        # -- Step 3: Delta classification ----------------------------
        if zfc_says and cat_says:
            delta = DeltaType.AGREE
        elif zfc_says and not cat_says:
            delta = DeltaType.ORPHAN
        elif not zfc_says and cat_says:
            delta = DeltaType.HOLLOW
        else:
            delta = DeltaType.REJECT

        result = DualResult(
            source=source,
            target=target,
            relation=relation,
            zfc_says=zfc_says,
            zfc_confidence=zfc_conf,
            zfc_witness=str(zfc_witness) if zfc_witness else None,
            zfc_rank_gap=zfc_rank_gap,
            cat_says=cat_says,
            cat_confidence=cat_conf,
            cat_paths=cat_paths,
            cat_path_lengths=cat_path_lengths,
            cat_geometric_class=cat_geometric_class,
            cat_explanation=cat_explanation,
            delta_type=delta,
        )

        # -- Step 4: System 3 record ---------------------------------
        if record:
            ep = self._make_episode(result, domain)
            self.system3.record(ep)
            result.meta_prediction = self.system3.predict(
                source, target, relation, domain,
                cat_conf=cat_conf, zfc_conf=zfc_conf,
            )

        return result

    # ----------------------------------------------------------------
    # System 3 wiring
    # ----------------------------------------------------------------

    def predict(
        self,
        source: str,
        target: str,
        relation: str,
        domain: str = "",
    ) -> MetaPrediction:
        """Ask System 3 what delta to expect before running engines."""
        return self.system3.predict(source, target, relation, domain)

    def should_run_both(
        self,
        source: str,
        target: str,
        relation: str,
        domain: str = "",
    ) -> Tuple[bool, str]:
        """Ask System 3 whether running both engines is worthwhile."""
        return self.system3.should_run_both(source, target, relation, domain)

    def resolve(
        self,
        episode_id: str,
        resolution: Resolution,
        notes: str = "",
    ) -> None:
        """Record ground truth for a past episode."""
        self.system3.resolve(episode_id, resolution, notes)

    def system3_report(self) -> str:
        """Generate a System 3 performance report."""
        return self.system3.report()

    # ----------------------------------------------------------------
    # Batch operations
    # ----------------------------------------------------------------

    def query_all_relations(
        self,
        source: str,
        target: str,
        domain: str = "",
    ) -> List[DualResult]:
        """
        Run query for every relation in the universe.

        Domain-agnostic: iterates all relation keys using list()
        to avoid RuntimeError from dict mutation.
        """
        universe = self.adapter.to_universe()
        results = []
        for rel_name in list(universe.relations.keys()):
            result = self.query(source, target, rel_name, domain=domain)
            results.append(result)
        return results

    def scan_universe(
        self,
        domain: str = "",
        max_pairs: int = 1000,
    ) -> List[DualResult]:
        """
        Scan all existing relation pairs in the universe.

        For each relation and each existing pair (a, b), runs the
        dual engine and records the episode.

        Uses list() on dict keys to avoid RuntimeError.
        """
        universe = self.adapter.to_universe()
        results = []
        count = 0

        for rel_name in list(universe.relations.keys()):
            rel = universe.relations[rel_name]
            for (a, b) in list(rel.pairs):
                if count >= max_pairs:
                    return results
                result = self.query(a, b, rel_name, domain=domain)
                results.append(result)
                count += 1

        return results

    # ----------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------

    def _cat_check(
        self,
        source: str,
        target: str,
    ) -> Tuple[List, List[int]]:
        """
        Fallback path check when CategoricalVerifier is not available.

        In KOMPOSOS-IV, Category.find_paths takes strings directly.
        """
        paths = self.category.find_paths(source, target, max_length=5)
        lengths = [p.length for p in paths]
        return paths, lengths

    def _rank_gap(self, source: str, target: str) -> int:
        """Compute rank gap between source and target in the universe."""
        try:
            universe = self.adapter.to_universe()
            from .well_ordering import rank_all
            ranks = rank_all(universe)
            rs = ranks.get(source, 0)
            rt = ranks.get(target, 0)
            return abs(rt - rs)
        except Exception:
            return 0

    def _make_episode(self, result: DualResult, domain: str) -> Episode:
        """Create an Episode from a DualResult."""
        self._episode_counter += 1
        eid = f"ep_{self._episode_counter:04d}"
        return Episode(
            id=eid,
            source=result.source,
            target=result.target,
            relation=result.relation,
            domain=domain,
            cat_says=result.cat_says,
            cat_confidence=result.cat_confidence,
            cat_path_count=result.cat_paths,
            cat_path_lengths=result.cat_path_lengths,
            zfc_says=result.zfc_says,
            zfc_confidence=result.zfc_confidence,
            zfc_witness=result.zfc_witness,
            zfc_rank_gap=result.zfc_rank_gap,
            delta_type=result.delta_type,
        )
