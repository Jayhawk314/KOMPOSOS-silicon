#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Yoneda Distance Strategy for drug repurposing.

Scores Drug-Disease pairs by structural similarity: if Drug_X has a similar
Yoneda presheaf to a drug known to treat Disease_Y, then Drug_X is a
structural substitute.

Operates on a clean subgraph (MEASURED + ESTABLISHED evidence tiers only)
to avoid noise contamination. Direct Drug->Disease labels are never part of
fingerprints, and known-treatment comparators come only from the category
provided by the caller so holdout protocols stay isolated.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import Dict, List, Set, Tuple

from oracle.prediction import Prediction, PredictionType
from oracle.strategies import InferenceStrategy
from core.category import Category

DB_PATH = "data/drugs/tier1.db"
NON_PROTEIN_TYPES = {"Drug", "Disease", "ExternalCompound"}


class YonedaDistanceStrategy(InferenceStrategy):
    """Score Drug-Disease pairs via Yoneda distance on clean evidence."""

    name = "yoneda_distance"

    def __init__(self, category: Category, db_path: str = DB_PATH):
        super().__init__(category)
        self._db_path = db_path
        self.clean_cat = self._load_clean_subgraph(db_path, category)
        self._fingerprints: Dict[str, Dict[Tuple[str, str], float]] = {
            obj.name: self._weighted_fingerprint(obj.name)
            for obj in self.clean_cat.objects()
        }
        self._known_treatments = self._known_treatments_from_category(category)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    @staticmethod
    def _known_treatments_from_category(category: Category) -> Dict[str, Set[str]]:
        """Collect visible Drug->Disease labels from the caller's graph only."""
        treatments: Dict[str, Set[str]] = defaultdict(set)
        for morphism in category.morphisms():
            source = category.get(morphism.source)
            target = category.get(morphism.target)
            if (
                source and target
                and source.type_name == "Drug"
                and target.type_name == "Disease"
            ):
                treatments[morphism.target].add(morphism.source)
        return treatments

    @staticmethod
    def _load_clean_subgraph(db_path: str, category: Category) -> Category:
        """Load visible, high-tier, non-label edges for structural fingerprints."""
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        visible_edges = {
            (morphism.source, morphism.target, morphism.name)
            for morphism in category.morphisms()
        }

        type_map: Dict[str, str] = {}
        cursor.execute("SELECT name, type_name FROM objects")
        for row in cursor.fetchall():
            type_map[row["name"]] = row["type_name"]

        cursor.execute("PRAGMA table_info(morphisms)")
        morphism_columns = {row["name"] for row in cursor.fetchall()}
        if "source_name" in morphism_columns:
            source_col = "source_name"
        elif "source" in morphism_columns:
            source_col = "source"
        else:
            raise sqlite3.OperationalError(
                "Unsupported morphisms schema: missing source column "
                "(expected source_name or source)"
            )

        if "target_name" in morphism_columns:
            target_col = "target_name"
        elif "target" in morphism_columns:
            target_col = "target"
        else:
            raise sqlite3.OperationalError(
                "Unsupported morphisms schema: missing target column "
                "(expected target_name or target)"
            )

        if "name" in morphism_columns:
            rel_col = "name"
        elif "predicate" in morphism_columns:
            rel_col = "predicate"
        else:
            raise sqlite3.OperationalError(
                "Unsupported morphisms schema: missing relation column "
                "(expected name or predicate)"
            )

        if "evidence_tier" in morphism_columns:
            clean_filter = "m.evidence_tier IN ('MEASURED', 'ESTABLISHED')"
        else:
            # Older checked-in DBs predate evidence_tier. Keep the app usable
            # by approximating the clean subgraph with high-confidence edges.
            clean_filter = "m.confidence >= 0.70"

        cursor.execute(
            "SELECT "
            f"m.{source_col} AS source_name, "
            f"m.{target_col} AS target_name, "
            f"m.{rel_col} AS name, "
            "m.confidence AS confidence, "
            "src.type_name AS source_type, "
            "tgt.type_name AS target_type "
            "FROM morphisms m "
            f"LEFT JOIN objects src ON m.{source_col} = src.name "
            f"LEFT JOIN objects tgt ON m.{target_col} = tgt.name "
            f"WHERE {clean_filter}"
        )
        edges = cursor.fetchall()
        conn.close()

        cat = Category("yoneda_clean", db_path=":memory:")
        seen: Set[str] = set()
        for edge in edges:
            edge_key = (edge["source_name"], edge["target_name"], edge["name"])
            is_direct_label = (
                edge["source_type"] == "Drug"
                and edge["target_type"] == "Disease"
            )
            if edge_key not in visible_edges or is_direct_label:
                continue
            for obj_name in (edge["source_name"], edge["target_name"]):
                if obj_name not in seen:
                    seen.add(obj_name)
                    cat.add(obj_name, type_name=type_map.get(obj_name, "Object"))
            cat.connect(
                edge["source_name"],
                edge["target_name"],
                name=edge["name"],
                confidence=edge["confidence"] or 1.0,
            )
        return cat

    # ------------------------------------------------------------------
    # Fingerprint & distance
    # ------------------------------------------------------------------

    def _weighted_fingerprint(
        self, obj_name: str
    ) -> Dict[Tuple[str, str], float]:
        """Yoneda presheaf as confidence-weighted (neighbor, relation) map.

        Each key is a (neighbor, morphism_name) pair. The value is the max
        confidence across all morphisms with that key, so repeated edges
        contribute only their strongest evidence.
        """
        fp: Dict[Tuple[str, str], float] = {}
        for m in self.clean_cat.morphisms_to(obj_name):
            key = (m.source, m.name)
            fp[key] = max(fp.get(key, 0.0), m.confidence)
        for m in self.clean_cat.morphisms_from(obj_name):
            key = (m.target, m.name)
            fp[key] = max(fp.get(key, 0.0), m.confidence)
        return fp

    def _weighted_jaccard(
        self,
        fp1: Dict[Tuple[str, str], float],
        fp2: Dict[Tuple[str, str], float],
    ) -> float:
        """Weighted Jaccard distance between two fingerprints.

        Uses min/max aggregation: intersection weight = sum of min per key,
        union weight = sum of max per key. Returns 0.0 for identical
        fingerprints, 1.0 for disjoint.
        """
        all_keys = set(fp1) | set(fp2)
        if not all_keys:
            return 1.0
        intersection = sum(min(fp1.get(k, 0.0), fp2.get(k, 0.0)) for k in all_keys)
        union = sum(max(fp1.get(k, 0.0), fp2.get(k, 0.0)) for k in all_keys)
        if union <= 0:
            return 1.0
        return 1.0 - intersection / union

    # ------------------------------------------------------------------
    # Strategy interface
    # ------------------------------------------------------------------

    def predict(self, source: str, target: str) -> List[Prediction]:
        """Score a Drug->Disease pair by Yoneda similarity to known treatments.

        For each drug that is known to treat the target disease, compute
        the weighted Jaccard distance on the clean subgraph. Return the
        best similarity as the prediction confidence.
        """
        src_obj = self.category.get(source)
        tgt_obj = self.category.get(target)
        if not src_obj or not tgt_obj:
            return []
        if src_obj.type_name != "Drug" or tgt_obj.type_name != "Disease":
            return []

        treating_drugs = self._known_treatments.get(target, set())
        if not treating_drugs:
            return []

        fp_source = self._fingerprints.get(source)
        if not fp_source:
            return []

        best_similarity = 0.0
        best_drug = None
        for known_drug in treating_drugs:
            if known_drug == source:
                continue
            fp_known = self._fingerprints.get(known_drug)
            if not fp_known:
                continue
            dist = self._weighted_jaccard(fp_source, fp_known)
            similarity = 1.0 - dist
            if similarity > best_similarity:
                best_similarity = similarity
                best_drug = known_drug

        if best_similarity <= 0.0 or best_drug is None:
            return []

        return [
            Prediction(
                source=source,
                target=target,
                predicted_relation="yoneda_similar",
                prediction_type=PredictionType.YONEDA_DISTANCE,
                strategy_name=self.name,
                confidence=best_similarity,
                reasoning=(
                    f"Yoneda distance {1.0 - best_similarity:.3f} from "
                    f"{best_drug} (known treatment for {target}) on "
                    f"MEASURED+ESTABLISHED subgraph"
                ),
                evidence={
                    "nearest_drug": best_drug,
                    "distance": round(1.0 - best_similarity, 4),
                    "similarity": round(best_similarity, 4),
                    "subgraph": "MEASURED+ESTABLISHED",
                },
            )
        ]
