# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
ZFC Verification Adapter for Oracle Predictions

Sits between oracle/__init__.py and zfc/bridge.py.
Wraps AROUND an existing CategoricalOracle, verifying its output
against the ZFC engine (LogicOracle + OrdinalOracle).

Each prediction is classified as:
    AGREE  -- both engines say yes (high confidence)
    ORPHAN -- ZFC yes, CAT no (logically forced but structurally missing)
    HOLLOW -- CAT yes, ZFC no (structurally plausible but logically unsound)
    REJECT -- both say no

Graceful degradation: if ZFC import fails, returns unmodified predictions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Graceful ZFC import
try:
    from zfc.store_adapter import store_to_logic_oracle, store_to_ordinal_oracle
    from zfc.bridge import DualPrediction, DualResult, _CAT_THRESHOLD
    from zfc.meta_kan import (
        DeltaType, Resolution, Episode, System3Oracle, MetaPrediction,
    )
    from zfc.separation import SeparationChecker, SeparationResult
    ZFC_AVAILABLE = True
except ImportError:
    ZFC_AVAILABLE = False


def _wrap_cat_only_result(source: str, target: str, cat_result) -> Any:
    """
    Wrap a CAT-only OracleResult into a DualResult-like object
    when ZFC is unavailable.

    Returns a simple namespace with the same interface as DualResult
    so callers can use it without checking availability.
    """
    if not ZFC_AVAILABLE:
        # Return a minimal dict-like object
        return _CatOnlyDualResult(
            source=source,
            target=target,
            cat_result=cat_result,
            predictions=cat_result.predictions if cat_result else [],
        )

    # ZFC is available but we still want a CAT-only wrapper
    from zfc.meta_kan import DeltaType, Episode

    dual_preds = []
    preds = cat_result.predictions if cat_result else []
    for pred in preds:
        dp = DualPrediction(
            source=pred.source,
            target=pred.target,
            relation=pred.predicted_relation,
            cat_confidence=pred.confidence,
            cat_strategy=pred.strategy_name,
            zfc_says=False,
            zfc_confidence=0.0,
            delta_type=DeltaType.UNKNOWN,
        )
        dual_preds.append(dp)

    episode = Episode(
        id=f"cat_only_{source}_{target}_{int(time.time() * 1000)}",
        source=source,
        target=target,
        relation=dual_preds[0].relation if dual_preds else "",
        domain="cat_only",
        cat_says=bool(preds),
        cat_confidence=preds[0].confidence if preds else 0.0,
        cat_strategy=preds[0].strategy_name if preds else "",
        cat_path_count=len(preds),
        cat_path_lengths=[1],
        zfc_says=False,
        zfc_confidence=0.0,
    )

    return DualResult(
        predictions=dual_preds,
        cat_result=cat_result,
        episode=episode,
        computation_time_ms=0.0,
        analysis=f"CAT-only result (ZFC not run): {len(preds)} predictions",
    )


@dataclass
class _CatOnlyDualResult:
    """Minimal fallback when ZFC module is not importable."""
    source: str
    target: str
    cat_result: Any
    predictions: list = field(default_factory=list)
    computation_time_ms: float = 0.0
    analysis: str = "ZFC module not available"
    episode: Any = None
    meta_prediction: Any = None

    @property
    def agrees(self) -> list:
        return []

    @property
    def orphans(self) -> list:
        return []

    @property
    def hollows(self) -> list:
        return []

    @property
    def rejects(self) -> list:
        return []


class OracleZFCBridge:
    """
    Lightweight adapter that adds ZFC verification to CategoricalOracle.

    Unlike DualEngineBridge (which owns a CategoricalOracle internally),
    this class wraps AROUND an existing oracle, verifying its output.
    This avoids double-prediction and works as a post-processing step.

    Usage:
        oracle = CategoricalOracle(category, embeddings)
        zfc_bridge = OracleZFCBridge(category, domain="drug_repurposing")

        result = oracle.predict(source, target)
        dual = zfc_bridge.verify_predictions(
            source, target, result.predictions, cat_result=result
        )
    """

    def __init__(self, category, domain: str = "", min_confidence: float = 0.4):
        """
        Args:
            category: Category instance
            domain: tag for System 3 episodes
            min_confidence: CAT threshold for AGREE/HOLLOW classification
        """
        self._available = False
        self.domain = domain
        self.min_confidence = min_confidence

        if not ZFC_AVAILABLE:
            return

        try:
            self.logic_oracle = store_to_logic_oracle(category)
            self.ordinal_oracle = store_to_ordinal_oracle(category)
            self.system3 = System3Oracle(
                f"OracleZFC_{domain}" if domain else "OracleZFC"
            )
            self.separation = SeparationChecker(
                self.logic_oracle.model.universe
            )
            self._available = True
        except Exception:
            pass

    @property
    def is_available(self) -> bool:
        """Whether ZFC engine loaded successfully."""
        return self._available

    def verify_predictions(
        self,
        source: str,
        target: str,
        predictions: list,
        cat_result: Any = None,
    ):
        """
        Verify a list of CAT Predictions against ZFC.

        For each Prediction:
          1. Check LogicOracle.predict_relation(rel, source, target)
          2. Check OrdinalOracle.predict_by_rank(source, target)
          3. Classify delta type
          4. Build DualPrediction

        Then:
          5. Record Episode in System 3
          6. Get MetaPrediction from System 3
          7. Return DualResult

        Returns:
            DualResult with dual-verified predictions.
            If ZFC unavailable, returns fallback wrapping original predictions.
        """
        if not self._available:
            return _wrap_cat_only_result(source, target, cat_result)

        start = time.time()
        dual_preds = []

        best_cat_conf = 0.0
        best_cat_strategy = ""
        best_zfc_conf = 0.0
        best_zfc_says = False
        zfc_witness = None

        threshold = self.min_confidence

        for pred in predictions:
            # ZFC entailment check
            zfc_says, zfc_conf, witness = self.logic_oracle.predict_relation(
                pred.predicted_relation, pred.source, pred.target
            )

            # Ordinal rank gap
            rank_gap = 0
            rank_dir = ""
            if self.ordinal_oracle is not None:
                try:
                    _, _, evidence = self.ordinal_oracle.predict_by_rank(
                        pred.source, pred.target
                    )
                    rank_gap = evidence.get("rank_gap", 0)
                    rank_dir = evidence.get("direction", "")
                except Exception:
                    pass

            # Classify delta
            cat_says = pred.confidence >= threshold
            if cat_says and zfc_says:
                delta = DeltaType.AGREE
            elif not cat_says and zfc_says:
                delta = DeltaType.ORPHAN
            elif cat_says and not zfc_says:
                delta = DeltaType.HOLLOW
            else:
                delta = DeltaType.REJECT

            dp = DualPrediction(
                source=pred.source,
                target=pred.target,
                relation=pred.predicted_relation,
                cat_confidence=pred.confidence,
                cat_strategy=pred.strategy_name,
                zfc_says=zfc_says,
                zfc_confidence=zfc_conf,
                zfc_witness=witness,
                rank_gap=rank_gap,
                rank_direction=rank_dir,
                delta_type=delta,
            )
            dual_preds.append(dp)

            # Track best for episode
            if pred.confidence > best_cat_conf:
                best_cat_conf = pred.confidence
                best_cat_strategy = pred.strategy_name
            if zfc_conf > best_zfc_conf:
                best_zfc_conf = zfc_conf
                best_zfc_says = zfc_says
                zfc_witness = witness

        # Build Episode
        ep_id = f"verify_{source}_{target}_{int(time.time() * 1000)}"
        episode = Episode(
            id=ep_id,
            source=source,
            target=target,
            relation=dual_preds[0].relation if dual_preds else "",
            domain=self.domain,
            cat_says=best_cat_conf >= threshold,
            cat_confidence=best_cat_conf,
            cat_strategy=best_cat_strategy,
            cat_path_count=len(predictions),
            cat_path_lengths=[1],
            zfc_says=best_zfc_says,
            zfc_confidence=best_zfc_conf,
            zfc_witness=str(zfc_witness) if zfc_witness else None,
            zfc_rank_gap=dual_preds[0].rank_gap if dual_preds else 0,
        )
        self.system3.record(episode)

        # System 3 meta-prediction
        meta_pred = None
        try:
            meta_pred = self.system3.predict(
                source, target,
                dual_preds[0].relation if dual_preds else "",
                self.domain,
                best_cat_conf, best_zfc_conf,
            )
        except Exception:
            pass

        elapsed = (time.time() - start) * 1000

        # Build analysis
        analysis = self._build_analysis(
            source, target, dual_preds, episode, meta_pred, elapsed
        )

        return DualResult(
            predictions=dual_preds,
            cat_result=cat_result,
            episode=episode,
            meta_prediction=meta_pred,
            computation_time_ms=elapsed,
            analysis=analysis,
        )

    def verify_batch(
        self,
        pairs_and_predictions: List[Tuple[str, str, list]],
    ) -> list:
        """Verify multiple (source, target, predictions) tuples."""
        return [
            self.verify_predictions(src, tgt, preds)
            for src, tgt, preds in pairs_and_predictions
        ]

    def coherence_check(self, predictions: list):
        """
        Run ZFC separation checker on oracle predictions.

        Converts Prediction objects to constraint dicts and delegates
        to SeparationChecker. Returns None if ZFC unavailable.
        """
        if not self._available:
            return None

        pred_dicts = []
        for p in predictions:
            pred_dicts.append({
                "source": p.source,
                "target": p.target,
                "relation": p.predicted_relation,
                "confidence": p.confidence,
                "strategy": p.strategy_name,
            })

        return self.separation.check(pred_dicts)

    def resolve(self, episode_id: str, resolution, notes: str = ""):
        """Record actual outcome for System 3 learning."""
        if self._available:
            self.system3.resolve(episode_id, resolution, notes)

    def report(self) -> str:
        """System 3 performance report."""
        if self._available:
            return self.system3.report()
        return "ZFC not available"

    def _build_analysis(self, source, target, dual_preds, episode,
                        meta_pred, elapsed_ms) -> str:
        lines = []
        lines.append(f"ZFC Verification: {source} -> {target}")
        lines.append("-" * 50)
        lines.append(f"Domain: {self.domain or '(unspecified)'}")
        lines.append(f"Time: {elapsed_ms:.0f}ms")

        counts = {dt: 0 for dt in DeltaType}
        for dp in dual_preds:
            counts[dp.delta_type] += 1

        lines.append(f"Predictions: {len(dual_preds)}")
        if counts[DeltaType.AGREE]:
            lines.append(f"  AGREE:  {counts[DeltaType.AGREE]}")
        if counts[DeltaType.ORPHAN]:
            lines.append(f"  ORPHAN: {counts[DeltaType.ORPHAN]}")
        if counts[DeltaType.HOLLOW]:
            lines.append(f"  HOLLOW: {counts[DeltaType.HOLLOW]}")
        if counts[DeltaType.REJECT]:
            lines.append(f"  REJECT: {counts[DeltaType.REJECT]}")

        if meta_pred:
            lines.append(f"System 3: predicted={meta_pred.predicted_delta.name} "
                        f"({meta_pred.delta_confidence:.0%})")

        return "\n".join(lines)
