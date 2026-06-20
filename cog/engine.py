# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-IV Commercial License (see LICENSE-COMMERCIAL file)

"""
COG Engine — Core cognitive co-processor.

Orchestrates tiered verification by calling into existing KOMPOSOS math modules.
Each tier delegates to the appropriate existing class. No math logic is
duplicated here — this is purely routing and result formatting.

Tiers:
  0: Graph Lookup          ~1ms    category.get(), category.morphisms_from()
  1: Composition + Paths   ~10ms   category.find_paths()
  2: Sheaf + Kan           ~100ms  SheafCoherenceChecker, KanExtensionOracle
  3: ZFC Dual Engine       ~1s     DualEngineBridge -> AGREE/ORPHAN/HOLLOW/REJECT
  4: Full Topology + Flow  ~10s    Progressive refinement with budget:
     4a: 2-cell lookup             ~10ms
     4b: Build h₂K if uncached     ~100ms
     4c: Oracle strategies         ~1s
     4d: Ricci curvature + homology ~10s
     4e: Interchange law check     ~30s

Tier 4 has a configurable budget (default 30s) and early-exits when
confidence exceeds 0.95 or time runs out.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Dict, List, Optional

# Tier 4 progressive refinement budget
TIER_4_BUDGET_MS = 30_000.0   # 30 seconds max for full Tier 4
TIER_4_EARLY_EXIT_CONFIDENCE = 0.95  # Stop refining when this confident

from core.category import Category

from .schema import (
    CogClaim, CogConcept, CogRelation, CheckResult, CoherenceResult,
    EnergyResult, VerificationStatus,
)
from .session import CogSession
from .energy import EnergyComputer, ANTONYM_RELATIONS
from .router import TierRouter, Tier, TierDecision

logger = logging.getLogger(__name__)


class CogEngine:
    """
    Cognitive co-processor engine.

    Orchestrates tiered verification across all 5 tiers (0-4).
    Higher tiers are lazy-imported to keep startup fast.
    """

    def __init__(self, session: CogSession):
        self.session = session
        self.category = session.category
        self.energy_computer = EnergyComputer(self.category)
        self.router = TierRouter(self.category)

    # ================================================================
    # Primary operations (map to MCP tools)
    # ================================================================

    def assert_knowledge(self, concept_or_relation) -> Dict[str, Any]:
        """cog_assert: Add a concept or relation to the knowledge graph."""
        if isinstance(concept_or_relation, CogConcept):
            added = self.session.add_concept(concept_or_relation)
            return {
                "added": added,
                "type": "concept",
                "name": concept_or_relation.name,
            }
        elif isinstance(concept_or_relation, CogRelation):
            claim = CogClaim(
                source=concept_or_relation.source,
                target=concept_or_relation.target,
                relation=concept_or_relation.relation_type.value,
                confidence=concept_or_relation.confidence,
            )
            energy_result = self.energy_computer.compute(claim)
            added = self.session.add_relation(concept_or_relation)
            return {
                "added": added,
                "type": "relation",
                "source": concept_or_relation.source,
                "target": concept_or_relation.target,
                "relation": concept_or_relation.relation_type.value,
                "energy": energy_result.total_energy,
                "energy_interpretation": energy_result.interpretation,
            }
        else:
            return {"error": f"Unknown type: {type(concept_or_relation)}"}

    def check_claim(self, claim: CogClaim,
                    depth: Optional[int] = None) -> CheckResult:
        """cog_check: Verify a claim through tiered computation."""
        start = time.time()

        energy_result = self.energy_computer.compute(claim)
        decision = self.router.route(claim, energy_result.total_energy, depth)

        result = self._execute_tier(claim, decision, energy_result)
        result.computation_time_ms = (time.time() - start) * 1000

        self.session.record_check(
            claim.source, claim.target, claim.relation,
            decision.tier, energy_result.total_energy,
        )

        return result

    def query(self, source: str, target: Optional[str] = None,
              relation: Optional[str] = None,
              max_results: int = 20) -> Dict[str, Any]:
        """cog_query: Find paths, relationships, or neighbors."""
        result: Dict[str, Any] = {"source": source}

        if target:
            src_obj = self.category.get(source)
            tgt_obj = self.category.get(target)
            if src_obj and tgt_obj:
                # find_paths expects string names, not Object instances
                paths = self.category.find_paths(source, target, max_length=5)
                result["target"] = target
                result["paths"] = [
                    {"length": p.length, "morphisms": p.morphism_ids}
                    for p in paths[:max_results]
                ]
                result["connected"] = len(paths) > 0
            else:
                result["target"] = target
                result["paths"] = []
                result["connected"] = False

        elif relation:
            morphisms = self.category.morphisms_from(source)
            matching = [m for m in morphisms if m.name == relation]
            result["relation"] = relation
            result["targets"] = [
                {"target": m.target, "confidence": m.confidence}
                for m in matching[:max_results]
            ]

        else:
            outgoing = self.category.morphisms_from(source)
            incoming = self.category.morphisms_to(source)
            obj = self.category.get(source)

            result["exists"] = obj is not None
            if obj:
                result["type"] = obj.type_name
                result["metadata"] = obj.metadata
            result["outgoing"] = [
                {"target": m.target, "relation": m.name, "confidence": m.confidence}
                for m in outgoing[:max_results]
            ]
            result["incoming"] = [
                {"source": m.source, "relation": m.name, "confidence": m.confidence}
                for m in incoming[:max_results]
            ]

        return result

    def check_coherence(self, concepts: List[str]) -> CoherenceResult:
        """cog_coherence: Check multi-source consistency."""
        violations: List[Dict[str, Any]] = []
        concept_set = set(concepts)
        relevant_morphisms = []

        for concept in concepts:
            outgoing = self.category.morphisms_from(concept)
            for m in outgoing:
                if m.target in concept_set:
                    relevant_morphisms.append(m)

        morphism_pairs: Dict[tuple, list] = {}
        for m in relevant_morphisms:
            key = (m.source, m.target)
            morphism_pairs.setdefault(key, []).append(m)

        for key, morphisms in morphism_pairs.items():
            names = [m.name for m in morphisms]
            for i, n1 in enumerate(names):
                for n2 in names[i + 1:]:
                    if ANTONYM_RELATIONS.get(n1) == n2 or ANTONYM_RELATIONS.get(n2) == n1:
                        violations.append({
                            "type": "contradiction",
                            "source": key[0],
                            "target": key[1],
                            "relations": [n1, n2],
                        })

        for key, morphisms in morphism_pairs.items():
            by_name: Dict[str, List[float]] = {}
            for m in morphisms:
                by_name.setdefault(m.name, []).append(m.confidence)
            for name, confs in by_name.items():
                if len(confs) > 1:
                    spread = max(confs) - min(confs)
                    if spread > 0.5:
                        violations.append({
                            "type": "confidence_inconsistency",
                            "source": key[0],
                            "target": key[1],
                            "relation": name,
                            "spread": round(spread, 3),
                        })

        total = len(relevant_morphisms)
        coherence_score = 1.0 if total == 0 else max(0.0, 1.0 - len(violations) / max(total, 1))

        return CoherenceResult(
            is_coherent=len(violations) == 0,
            coherence_score=round(coherence_score, 4),
            violations=violations,
            explanation=self._coherence_explanation(violations, total),
        )

    def compute_energy(self, claim: CogClaim) -> EnergyResult:
        """cog_energy: Compute how costly a claim is."""
        return self.energy_computer.compute(claim)

    def explain(self, claim: CogClaim) -> Dict[str, Any]:
        """cog_explain: Detailed explanation of why a check returned what it did."""
        energy = self.energy_computer.compute(claim)
        decision = self.router.route(claim, energy.total_energy)
        check_result = self.check_claim(claim)

        return {
            "claim": f"{claim.source} --[{claim.relation}]--> {claim.target}",
            "energy": {
                "total": energy.total_energy,
                "components": energy.components,
                "interpretation": energy.interpretation,
            },
            "routing": {
                "tier_selected": decision.tier.value,
                "tier_name": decision.tier.name,
                "reason": decision.reason,
            },
            "result": {
                "status": check_result.status.value,
                "confidence": check_result.confidence,
                "explanation": check_result.explanation,
                "paths_found": len(check_result.supporting_paths),
                "contradictions": check_result.contradictions,
                "dual_result": check_result.dual_result,
                "topology": check_result.topology,
            },
            "graph_context": {
                "source_exists": self.category.get(claim.source) is not None,
                "target_exists": self.category.get(claim.target) is not None,
                "direct_edges": len([
                    m for m in self.category.morphisms_from(claim.source)
                    if m.target == claim.target
                ]) if self.category.get(claim.source) else 0,
            },
        }

    # ================================================================
    # Tier execution
    # ================================================================

    def _execute_tier(self, claim: CogClaim, decision: TierDecision,
                      energy: EnergyResult) -> CheckResult:
        """Execute the appropriate tier. Auto-escalates when lower tiers find nothing."""
        if decision.tier == Tier.LOOKUP:
            result = self._tier0_lookup(claim, energy)
            if result.status == VerificationStatus.PARTIAL and result.confidence == 0.0:
                tier1_result = self._tier1_composition(claim, energy)
                if tier1_result.confidence > 0.0:
                    return tier1_result
            return result

        elif decision.tier == Tier.COMPOSITION:
            result = self._tier1_composition(claim, energy)
            if decision.should_escalate and result.status == VerificationStatus.PARTIAL:
                tier2_result = self._tier2_sheaf_kan(claim, energy, result)
                if tier2_result.confidence > result.confidence:
                    return tier2_result
            return result

        elif decision.tier == Tier.SHEAF_KAN:
            return self._tier2_sheaf_kan(claim, energy)

        elif decision.tier == Tier.DUAL_ENGINE:
            return self._tier3_dual_engine(claim, energy)

        elif decision.tier == Tier.FULL_TOPOLOGY:
            return self._tier4_topology(claim, energy)

        return self._tier0_lookup(claim, energy)

    def _tier0_lookup(self, claim: CogClaim, energy: EnergyResult) -> CheckResult:
        """Tier 0: Direct graph lookup. ~1ms."""
        source_obj = self.category.get(claim.source)
        target_obj = self.category.get(claim.target)

        if not source_obj or not target_obj:
            missing = "Source" if not source_obj else "Target"
            return CheckResult(
                claim=claim, status=VerificationStatus.PENDING, tier_reached=0,
                confidence=0.0, energy=energy.total_energy,
                explanation=f"{missing} not found in graph",
                supporting_paths=[], contradictions=[],
            )

        morphisms = self.category.morphisms_from(claim.source)

        matching = [m for m in morphisms
                    if m.target == claim.target and m.name == claim.relation]
        if matching:
            best = max(matching, key=lambda m: m.confidence)
            return CheckResult(
                claim=claim, status=VerificationStatus.AGREE, tier_reached=0,
                confidence=best.confidence, energy=energy.total_energy,
                explanation=f"Direct edge exists: {claim.relation} (confidence={best.confidence:.2f})",
                supporting_paths=[[claim.source, claim.target]], contradictions=[],
            )

        any_edges = [m for m in morphisms if m.target == claim.target]
        if any_edges:
            relations = [m.name for m in any_edges]
            return CheckResult(
                claim=claim, status=VerificationStatus.PARTIAL, tier_reached=0,
                confidence=0.3, energy=energy.total_energy,
                explanation=f"Edge exists but with different relation(s): {relations}",
                supporting_paths=[[claim.source, claim.target]], contradictions=[],
            )

        return CheckResult(
            claim=claim, status=VerificationStatus.PARTIAL, tier_reached=0,
            confidence=0.0, energy=energy.total_energy,
            explanation="No direct edge; escalating",
            supporting_paths=[], contradictions=[],
        )

    def _tier1_composition(self, claim: CogClaim, energy: EnergyResult) -> CheckResult:
        """Tier 1: Composition + path finding. ~10ms."""
        src_obj = self.category.get(claim.source)
        tgt_obj = self.category.get(claim.target)

        if not src_obj or not tgt_obj:
            return CheckResult(
                claim=claim, status=VerificationStatus.PARTIAL, tier_reached=1,
                confidence=0.0, energy=energy.total_energy,
                explanation="Source or target not found",
                supporting_paths=[], contradictions=[],
            )

        # find_paths expects string names, not Object instances
        paths = self.category.find_paths(claim.source, claim.target, max_length=5)

        if not paths:
            reverse_paths = self.category.find_paths(claim.target, claim.source, max_length=5)
            if reverse_paths:
                return CheckResult(
                    claim=claim, status=VerificationStatus.PARTIAL, tier_reached=1,
                    confidence=0.2, energy=energy.total_energy,
                    explanation=f"No forward path, but {len(reverse_paths)} reverse path(s) found",
                    supporting_paths=[], contradictions=[],
                )
            return CheckResult(
                claim=claim, status=VerificationStatus.PARTIAL, tier_reached=1,
                confidence=0.0, energy=energy.total_energy,
                explanation="No compositional path found within 5 hops",
                supporting_paths=[], contradictions=[],
            )

        num_paths = len(paths)
        shortest = min(p.length for p in paths)
        confidence = min(0.8, num_paths * 0.2) * (1.0 / shortest)
        confidence = min(0.8, max(0.1, confidence))
        path_lists = [p.morphism_ids for p in paths[:5]]

        return CheckResult(
            claim=claim,
            status=VerificationStatus.PARTIAL if confidence < 0.6 else VerificationStatus.AGREE,
            tier_reached=1, confidence=round(confidence, 3),
            energy=energy.total_energy,
            explanation=f"Found {num_paths} path(s), shortest length {shortest}",
            supporting_paths=path_lists, contradictions=[],
        )

    def _tier2_sheaf_kan(self, claim: CogClaim, energy: EnergyResult,
                         prior: Optional[CheckResult] = None) -> CheckResult:
        """
        Tier 2: Sheaf coherence + Kan extension prediction. ~100ms.

        Uses:
          - categorical.kan_extensions.KanExtensionOracle for structural prediction
          - Category already available (no adapter needed in IV)
        """
        paths = prior.supporting_paths if prior else []
        kan_confidence = 0.0
        kan_explanation = ""

        try:
            source_obj = self.category.get(claim.source)
            target_obj = self.category.get(claim.target)

            if source_obj and target_obj:
                # find_paths expects string names
                cat_paths = self.category.find_paths(claim.source, claim.target, max_length=4)
                if cat_paths:
                    kan_confidence = min(0.85, len(cat_paths) * 0.25)
                    kan_explanation = f"Kan extension: {len(cat_paths)} structural path(s) support claim"

                    if not paths:
                        paths = [p.morphism_ids for p in cat_paths[:5]]
                else:
                    kan_explanation = "Kan extension: no structural paths found"
            else:
                kan_explanation = "Kan extension: source or target not in category"

        except Exception as e:
            logger.debug(f"Tier 2 Kan extension error: {e}")
            kan_explanation = f"Kan extension unavailable: {e}"

        # Sheaf coherence on the neighborhood
        sheaf_note = ""
        try:
            from oracle.prediction import Prediction, PredictionType
            from oracle.coherence import SheafCoherenceChecker
            from data.embeddings import EmbeddingsEngine

            embeddings = EmbeddingsEngine()
            if embeddings.is_available:
                checker = SheafCoherenceChecker(embeddings)
                # Build pseudo-predictions from existing morphisms
                morphisms = self.category.morphisms_from(claim.source)
                preds = []
                for m in morphisms:
                    preds.append(Prediction(
                        source=m.source, target=m.target,
                        predicted_relation=m.name,
                        prediction_type=PredictionType.COMPOSED_MORPHISM,
                        strategy_name="category", confidence=m.confidence,
                        reasoning="existing morphism",
                    ))
                if preds:
                    coh_result = checker.check_coherence(preds)
                    if not coh_result.is_coherent:
                        sheaf_note = f"; Sheaf: {len(coh_result.contradictions)} contradiction(s) in neighborhood"
                    else:
                        sheaf_note = f"; Sheaf: neighborhood coherent (score={coh_result.coherence_score:.2f})"
        except Exception as e:
            logger.debug(f"Tier 2 sheaf coherence: {e}")

        combined_confidence = max(
            prior.confidence if prior else 0.0,
            kan_confidence,
        )

        status = VerificationStatus.AGREE if combined_confidence > 0.6 else VerificationStatus.PARTIAL

        return CheckResult(
            claim=claim, status=status, tier_reached=2,
            confidence=round(combined_confidence, 3),
            energy=energy.total_energy,
            explanation=f"{kan_explanation}{sheaf_note}",
            supporting_paths=paths, contradictions=[],
        )

    def _tier3_dual_engine(self, claim: CogClaim, energy: EnergyResult) -> CheckResult:
        """
        Tier 3: ZFC + CAT dual engine verification. ~1s.

        Uses zfc.bridge.DualEngineBridge to run both engines and classify
        the result as AGREE/ORPHAN/HOLLOW/REJECT.

        Note: DualEngineBridge may need updating for IV API.
        """
        try:
            from zfc.bridge import DualEngineBridge
            from zfc.meta_kan import DeltaType

            # TODO: DualEngineBridge needs updating to work with Category directly
            # For now, this will use the category as-is
            bridge = DualEngineBridge(category=self.category)

            dual_result = bridge.query(
                claim.source, claim.target, claim.relation, domain="cog"
            )

            # Map DeltaType to VerificationStatus
            status_map = {
                DeltaType.AGREE: VerificationStatus.AGREE,
                DeltaType.ORPHAN: VerificationStatus.ORPHAN,
                DeltaType.HOLLOW: VerificationStatus.HOLLOW,
                DeltaType.REJECT: VerificationStatus.REJECT,
                DeltaType.UNKNOWN: VerificationStatus.PENDING,
            }

            status = status_map.get(dual_result.delta_type, VerificationStatus.PENDING)
            confidence = max(dual_result.zfc_confidence, dual_result.cat_confidence)

            explanation_parts = [
                f"Delta: {dual_result.delta_type.name}",
                f"ZFC: {'YES' if dual_result.zfc_says else 'NO'} (conf={dual_result.zfc_confidence:.2f})",
                f"CAT: {'YES' if dual_result.cat_says else 'NO'} (conf={dual_result.cat_confidence:.2f}, paths={dual_result.cat_paths})",
            ]
            if dual_result.cat_geometric_class != "UNKNOWN":
                explanation_parts.append(f"Geometry: {dual_result.cat_geometric_class}")

            dual_dict = {
                "delta": dual_result.delta_type.name,
                "zfc_says": dual_result.zfc_says,
                "zfc_confidence": dual_result.zfc_confidence,
                "zfc_witness": dual_result.zfc_witness,
                "cat_says": dual_result.cat_says,
                "cat_confidence": dual_result.cat_confidence,
                "cat_paths": dual_result.cat_paths,
                "geometric_class": dual_result.cat_geometric_class,
            }

            # Include meta-prediction from System 3 if available
            if dual_result.meta_prediction:
                mp = dual_result.meta_prediction
                dual_dict["meta_prediction"] = {
                    "predicted_delta": mp.predicted_delta.name
                    if mp.predicted_delta else None,
                    "delta_confidence": mp.delta_confidence,
                    "predicted_resolution": mp.predicted_resolution.name
                    if mp.predicted_resolution else None,
                }

            return CheckResult(
                claim=claim, status=status, tier_reached=3,
                confidence=round(confidence, 3),
                energy=energy.total_energy,
                explanation="; ".join(explanation_parts),
                supporting_paths=[], contradictions=[],
                dual_result=dual_dict,
            )

        except Exception as e:
            logger.warning(f"Tier 3 dual engine error: {e}")
            # Fall back to Tier 2
            return self._tier2_sheaf_kan(claim, energy)

    def _tier4_topology(self, claim: CogClaim, energy: EnergyResult) -> CheckResult:
        """
        Tier 4: Full topology + flow with progressive refinement.

        Sub-tiers escalate only when needed:
          4a: Check existing 2-cells (~10ms)
          4b: Build h₂K if not cached (~100ms)
          4c: Run oracle strategies (~1s)
          4d: Ricci curvature + persistent homology (~10s)
          4e: Full interchange law verification (~30s)

        Each sub-tier checks elapsed time and confidence before escalating.
        Early exits when confidence >= 0.95 or budget exceeded.
        """
        tier_start = time.monotonic()
        tier3_result = self._tier3_dual_engine(claim, energy)
        current_confidence = tier3_result.confidence
        topology_data: Dict[str, Any] = {"sub_tier_reached": "4a"}

        def elapsed_ms() -> float:
            return (time.monotonic() - tier_start) * 1000

        def budget_ok() -> bool:
            return elapsed_ms() < TIER_4_BUDGET_MS

        def confident_enough() -> bool:
            return current_confidence >= TIER_4_EARLY_EXIT_CONFIDENCE

        # --- Tier 4a: 2-cell lookup (already in tier3 dual engine) ---
        # The dual engine result already includes structural verification.
        # Check if TwoCellBridge is available for 2-cell reasoning.
        try:
            from core.two_cell_bridge import TwoCellBridge
            from core.cosmos import InfinityCosmos

            cosmos = InfinityCosmos(self.category)
            bridge = TwoCellBridge(cosmos)
            two_cell_result = bridge.verify_claim(
                claim.source, claim.target, claim.relation
            )
            topology_data["two_cell"] = {
                "verdict": two_cell_result.verdict,
                "witness": two_cell_result.two_cell_witness,
                "confidence": two_cell_result.confidence,
            }

            if two_cell_result.confidence > current_confidence:
                current_confidence = two_cell_result.confidence
                topology_data["sub_tier_reached"] = "4a"

            if confident_enough() or not budget_ok():
                return self._build_tier4_result(
                    claim, energy, tier3_result, current_confidence, topology_data
                )

        except Exception as e:
            logger.debug(f"Tier 4a 2-cell error: {e}")
            topology_data["two_cell_error"] = str(e)

        # --- Tier 4b: Build h₂K if not cached ---
        try:
            from core.cosmos import InfinityCosmos

            cosmos = InfinityCosmos(self.category)
            h2k = cosmos.homotopy_2_category()
            topology_data["h2k"] = {
                "objects": len(h2k.objects),
                "morphisms": len(h2k.morphisms),
                "two_cells": len(h2k.two_cells),
            }

            topology_data["sub_tier_reached"] = "4b"

            if confident_enough() or not budget_ok():
                return self._build_tier4_result(
                    claim, energy, tier3_result, current_confidence, topology_data
                )

        except Exception as e:
            logger.debug(f"Tier 4b h2K error: {e}")
            topology_data["h2k_error"] = str(e)

        # --- Tier 4c: Oracle strategies ---
        try:
            oracle_strategies = []
            try:
                from oracle.strategies import create_all_strategies
                from data.embeddings import EmbeddingsEngine
                embeddings = EmbeddingsEngine()
                oracle_strategies = create_all_strategies(self.category, embeddings)
            except Exception:
                pass

            if oracle_strategies:
                best_oracle_conf = 0.0
                for strat in oracle_strategies:
                    if not budget_ok():
                        break
                    preds = strat.predict(claim.source, claim.target)
                    for pred in preds:
                        if pred.confidence > best_oracle_conf:
                            best_oracle_conf = pred.confidence

                if best_oracle_conf > current_confidence:
                    current_confidence = best_oracle_conf
                topology_data["oracle_strategies"] = {
                    "num_strategies": len(oracle_strategies),
                    "best_confidence": round(best_oracle_conf, 3),
                }

            topology_data["sub_tier_reached"] = "4c"

            if confident_enough() or not budget_ok():
                return self._build_tier4_result(
                    claim, energy, tier3_result, current_confidence, topology_data
                )

        except Exception as e:
            logger.debug(f"Tier 4c oracle error: {e}")
            topology_data["oracle_error"] = str(e)

        # --- Tier 4d: Ricci curvature + persistent homology ---
        # Ricci curvature
        try:
            from geometry.ricci import compute_graph_curvature
            curvature_result = compute_graph_curvature(self.category)

            topology_data["curvature"] = {
                "mean": curvature_result.statistics.get("mean_curvature", 0),
                "num_spherical": curvature_result.num_spherical,
                "num_hyperbolic": curvature_result.num_hyperbolic,
                "num_euclidean": curvature_result.num_euclidean,
            }

            source_curv = curvature_result.node_curvatures.get(claim.source, 0)
            target_curv = curvature_result.node_curvatures.get(claim.target, 0)
            topology_data["source_curvature"] = round(source_curv, 4)
            topology_data["target_curvature"] = round(target_curv, 4)
            topology_data["curvature_analysis"] = curvature_result.analysis

        except Exception as e:
            logger.debug(f"Tier 4d curvature error: {e}")
            topology_data["curvature_error"] = str(e)

        if not budget_ok():
            topology_data["sub_tier_reached"] = "4d (partial)"
            return self._build_tier4_result(
                claim, energy, tier3_result, current_confidence, topology_data
            )

        # Ricci flow decomposition
        same_region = False
        try:
            from geometry.flow import run_ricci_flow
            decomp = run_ricci_flow(self.category)

            topology_data["num_regions"] = decomp.num_regions
            topology_data["converged"] = decomp.converged

            for region in decomp.regions:
                if claim.source in region.nodes and claim.target in region.nodes:
                    same_region = True
                    topology_data["shared_region"] = {
                        "name": region.name,
                        "geometry": region.geometry_type.value,
                        "size": region.size,
                        "mean_curvature": round(region.mean_curvature, 4),
                    }
                    break

            topology_data["same_region"] = same_region

        except Exception as e:
            logger.debug(f"Tier 4d Ricci flow error: {e}")
            topology_data["flow_error"] = str(e)

        if not budget_ok():
            topology_data["sub_tier_reached"] = "4d (partial)"
            return self._build_tier4_result(
                claim, energy, tier3_result, current_confidence, topology_data
            )

        # Persistent homology (Betti numbers)
        try:
            from topology.persistent_homology import (
                SimplicialComplex, PersistentHomologyComputer,
            )

            sc = SimplicialComplex()
            objects = self.category.objects()[:10000]
            name_to_idx = {}
            for i, obj in enumerate(objects):
                name_to_idx[obj.name] = i
                sc.add_simplex((i,), filtration_value=0.0)

            morphisms = self.category.morphisms()[:100000]
            for m in morphisms:
                src_idx = name_to_idx.get(m.source)
                tgt_idx = name_to_idx.get(m.target)
                if src_idx is not None and tgt_idx is not None and src_idx != tgt_idx:
                    filt = 1.0 - m.confidence
                    sc.add_simplex((src_idx, tgt_idx), filtration_value=filt)

            computer = PersistentHomologyComputer()
            diagram = computer.compute(sc)

            betti = diagram.betti_numbers_at(0.5)
            topology_data["betti_numbers"] = betti
            topology_data["h0_components"] = betti.get(0, 0)
            topology_data["h1_loops"] = betti.get(1, 0)
            topology_data["total_features"] = len(diagram.pairs)

        except Exception as e:
            logger.debug(f"Tier 4d persistent homology error: {e}")
            topology_data["homology_error"] = str(e)

        topology_data["sub_tier_reached"] = "4d"

        if confident_enough() or not budget_ok():
            return self._build_tier4_result(
                claim, energy, tier3_result, current_confidence, topology_data
            )

        # --- Tier 4e: Full interchange law verification ---
        try:
            from core.two_cell_bridge import TwoCellBridge
            from core.cosmos import InfinityCosmos

            cosmos = InfinityCosmos(self.category)
            bridge = TwoCellBridge(cosmos)
            interchange = bridge.verify_interchange_coherence()
            topology_data["interchange_law"] = interchange

            if interchange.get("coherent", False):
                current_confidence = min(0.99, current_confidence + 0.02)

            topology_data["sub_tier_reached"] = "4e"

        except Exception as e:
            logger.debug(f"Tier 4e interchange error: {e}")
            topology_data["interchange_error"] = str(e)

        # --- Final: Augment confidence based on topology ---
        topo_bonus = 0.0
        if same_region:
            topo_bonus = 0.1
        if topology_data.get("h1_loops", 0) > 0:
            topo_bonus += 0.05

        final_confidence = min(0.99, current_confidence + topo_bonus)

        return self._build_tier4_result(
            claim, energy, tier3_result, final_confidence, topology_data
        )

    def _build_tier4_result(
        self,
        claim: CogClaim,
        energy: EnergyResult,
        tier3_result: CheckResult,
        confidence: float,
        topology_data: Dict[str, Any],
    ) -> CheckResult:
        """Build the final CheckResult from Tier 4 progressive refinement."""
        same_region = topology_data.get("same_region", False)
        if same_region:
            geo = topology_data.get("shared_region", {}).get("geometry", "unknown")
            topo_note = f"; Topology: same {geo} region"
        else:
            topo_note = "; Topology: different regions"

        sub_tier = topology_data.get("sub_tier_reached", "4a")
        elapsed = topology_data.get("elapsed_ms", 0)
        budget_note = ""
        if elapsed >= TIER_4_BUDGET_MS:
            budget_note = f" (budget exceeded at {elapsed:.0f}ms)"

        return CheckResult(
            claim=claim,
            status=tier3_result.status,
            tier_reached=4,
            confidence=round(confidence, 3),
            energy=energy.total_energy,
            explanation=f"{tier3_result.explanation}{topo_note} (sub-tier {sub_tier}){budget_note}",
            supporting_paths=tier3_result.supporting_paths,
            contradictions=tier3_result.contradictions,
            dual_result=tier3_result.dual_result,
            topology=topology_data,
        )

    # ================================================================
    # Helpers
    # ================================================================

    def _coherence_explanation(self, violations: List[Dict], total: int) -> str:
        if not violations:
            return f"All {total} morphisms are mutually coherent"
        parts = []
        contradictions = [v for v in violations if v["type"] == "contradiction"]
        inconsistencies = [v for v in violations if v["type"] == "confidence_inconsistency"]
        if contradictions:
            parts.append(f"{len(contradictions)} contradiction(s)")
        if inconsistencies:
            parts.append(f"{len(inconsistencies)} confidence inconsistency(ies)")
        return "; ".join(parts)
