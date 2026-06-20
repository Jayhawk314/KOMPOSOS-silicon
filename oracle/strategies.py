"""
Inference strategies for the KOMPOSOS-IV Categorical Oracle.

Each strategy implements a different approach to predicting missing morphisms:
1. KanExtensionStrategy - Uses categorical Kan extensions (colimit computation)
2. SemanticSimilarityStrategy - Uses embedding similarity
3. TemporalReasoningStrategy - Uses temporal metadata (birth/death dates)
4. YonedaPatternStrategy - Uses morphism pattern matching
5. CompositionStrategy - Uses path composition (A->B->C implies A->C)
6. FibrationLiftStrategy - Uses fibration structure for Cartesian lifts
7. StructuralHoleStrategy - Finds triangles that should close
8. GeometricStrategy - Uses Ricci curvature for geometric inference

Additional strategies (imported from separate modules):
9. ToposLogicStrategy - Uses intuitionistic logic for partial-evidence claims
10. NaturalTransformationStrategy - Detects pattern variants via naturality squares
11. OperadicDecompositionStrategy - Decomposes n-ary relations into binary trees

TypeHeuristicStrategy remains available as a legacy strategy, but it is not
part of the default runtime strategy profile.
"""

import sys
from pathlib import Path
from abc import ABC, abstractmethod
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from oracle.prediction import Prediction, PredictionType, PredictionBatch, ConfidenceLevel
from core.category import Category
from data.embeddings import EmbeddingsEngine


REPURPOSING_INTERMEDIATE_TYPES = {
    "Protein",
    "Receptor",
    "Kinase",
    "Enzyme",
    "Transporter",
    "Signaling",
    "Apoptosis",
    "GrowthFactor",
    "Ligand",
    "Marker",
    "TranscriptionFactor",
    "Transcription",
    "TumorSuppressor",
    "Oncogene",
    "DNA_Repair",
    "DNARepair",
    "CellCycle",
    "Regulator",
    "Splicing",
    "Epigenetic",
    "Metabolic",
    "Structural",
    "Chaperone",
}


class InferenceStrategy(ABC):
    """Base class for all inference strategies."""

    name: str = "base_strategy"

    def __init__(self, category: Category):
        self.category = category
        self._morphism_cache = None
        self._object_cache = None

    def _get_morphisms(self) -> list:
        """Cached morphism retrieval."""
        if self._morphism_cache is None:
            self._morphism_cache = self.category.morphisms()
        return self._morphism_cache

    def _get_objects(self) -> list:
        """Cached object retrieval."""
        if self._object_cache is None:
            self._object_cache = self.category.objects()
        return self._object_cache

    def _build_morphism_index(self) -> Tuple[Dict, Dict]:
        """Build outgoing and incoming morphism indices."""
        outgoing = {}  # source -> [morphisms]
        incoming = {}  # target -> [morphisms]

        for mor in self._get_morphisms():
            if mor.source not in outgoing:
                outgoing[mor.source] = []
            outgoing[mor.source].append(mor)

            if mor.target not in incoming:
                incoming[mor.target] = []
            incoming[mor.target].append(mor)

        return outgoing, incoming

    def _existing_morphism_pairs(self) -> Set[Tuple[str, str]]:
        """Get set of existing (source, target) pairs."""
        return {(m.source, m.target) for m in self._get_morphisms()}

    @abstractmethod
    def predict(self, source: str, target: str) -> List[Prediction]:
        """Generate predictions for the source->target relationship."""
        pass


# =============================================================================
# Strategy 1: Kan Extension
# =============================================================================

class KanExtensionStrategy(InferenceStrategy):
    """
    Use Left Kan Extension for prediction.

    Mathematical basis:
    - Left Kan extension Lan_K(F)(b) = colim_{(K|b)} F
    - For each target b, compute weighted colimit over all paths leading to b
    - Predicts what should exist based on universal properties

    Integrates: categorical/kan_extensions.py
    """

    name = "kan_extension"

    def predict(self, source: str, target: str) -> List[Prediction]:
        predictions = []

        # Build the comma category (K | target)
        # This is all objects with morphisms to target
        outgoing, incoming = self._build_morphism_index()

        # Get objects that connect to target
        objects_to_target = incoming.get(target, [])

        if not objects_to_target:
            return predictions

        # For Kan extension, we look at the "cone" over target
        # If multiple objects point to target with similar patterns to source,
        # source should also point to target

        source_out = set(m.target for m in outgoing.get(source, []))
        source_out_types = set(m.name for m in outgoing.get(source, []))

        # Find objects similar to source that DO have morphism to target
        # Only consider Drug objects as analogs (not proteins, etc.)
        similar_with_connection = []
        for obj in self._get_objects():
            if obj.name == source or obj.type_name != "Drug":
                continue

            obj_out = set(m.target for m in outgoing.get(obj.name, []))
            obj_out_types = set(m.name for m in outgoing.get(obj.name, []))

            # Check if this object has morphism to target
            has_connection = target in obj_out

            if has_connection:
                # Compute structural similarity to source
                target_overlap = len(source_out & obj_out)
                type_overlap = len(source_out_types & obj_out_types)

                if target_overlap >= 1 or type_overlap >= 1:
                    similar_with_connection.append({
                        "object": obj.name,
                        "target_overlap": target_overlap,
                        "type_overlap": type_overlap,
                        "morphism_type": next(
                            (m.name for m in outgoing.get(obj.name, []) if m.target == target),
                            "related_to"
                        )
                    })

        # If similar objects have connections to target, predict source should too
        if similar_with_connection:
            # Compute weighted colimit (Kan extension)
            total_weight = sum(s["target_overlap"] + s["type_overlap"] for s in similar_with_connection)

            if total_weight > 0:
                # Most common morphism type
                type_counts = {}
                for s in similar_with_connection:
                    t = s["morphism_type"]
                    weight = s["target_overlap"] + s["type_overlap"]
                    type_counts[t] = type_counts.get(t, 0) + weight

                best_type = max(type_counts.items(), key=lambda x: x[1])[0]

                # Confidence based on number of contributors and weight
                n_contributors = len(similar_with_connection)
                confidence = min(0.90, 0.4 + 0.1 * n_contributors + 0.05 * total_weight)

                predictions.append(Prediction(
                    source=source,
                    target=target,
                    predicted_relation=best_type,
                    prediction_type=PredictionType.KAN_EXTENSION,
                    strategy_name=self.name,
                    confidence=confidence,
                    reasoning=f"Kan extension via {n_contributors} similar objects that connect to {target}",
                    evidence={
                        "contributors": [s["object"] for s in similar_with_connection],
                        "total_weight": total_weight,
                        "type_distribution": type_counts,
                    }
                ))

        return predictions


# =============================================================================
# Strategy 2: Semantic Similarity
# =============================================================================

class SemanticSimilarityStrategy(InferenceStrategy):
    """
    Predict connections between semantically similar objects.

    If A is similar to B (via embeddings), and B has morphism to C,
    then A might also have morphism to C.

    Requires: EmbeddingsEngine must be initialized
    """

    name = "semantic_similarity"

    def __init__(self, category: Category, embeddings: EmbeddingsEngine):
        super().__init__(category)
        self.embeddings = embeddings
        if embeddings is None or not embeddings.is_available:
            raise ValueError("SemanticSimilarityStrategy requires initialized embeddings")

    def predict(self, source: str, target: str) -> List[Prediction]:
        predictions = []

        # Get similarity between source and target
        direct_similarity = self.embeddings.similarity(source, target)

        # If very similar but no morphism, predict connection
        existing = self._existing_morphism_pairs()
        if (source, target) not in existing and direct_similarity > 0.6:
            confidence = min(0.85, direct_similarity)

            predictions.append(Prediction(
                source=source,
                target=target,
                predicted_relation="related_to",
                prediction_type=PredictionType.SEMANTIC_SIMILARITY,
                strategy_name=self.name,
                confidence=confidence,
                reasoning=f"High semantic similarity ({direct_similarity:.3f}) suggests connection",
                evidence={
                    "similarity_score": direct_similarity,
                }
            ))

        # Find objects similar to source that have morphisms to target
        outgoing, incoming = self._build_morphism_index()

        # Get objects pointing to target
        objects_to_target = [m.source for m in incoming.get(target, [])]

        for obj_name in objects_to_target:
            if obj_name == source:
                continue

            # Check embedding similarity
            similarity = self.embeddings.similarity(source, obj_name)

            if similarity > 0.7:  # High similarity
                # This object is similar to source AND has morphism to target
                # Predict source should also have morphism to target
                mor_to_target = next(
                    (m for m in outgoing.get(obj_name, []) if m.target == target),
                    None
                )
                if mor_to_target and (source, target) not in existing:
                    confidence = min(0.85, similarity * 0.9)

                    predictions.append(Prediction(
                        source=source,
                        target=target,
                        predicted_relation=mor_to_target.name,
                        prediction_type=PredictionType.SEMANTIC_SIMILARITY,
                        strategy_name=self.name,
                        confidence=confidence,
                        reasoning=f"{source} is similar to {obj_name} ({similarity:.3f}) which has '{mor_to_target.name}' to {target}",
                        evidence={
                            "similar_object": obj_name,
                            "similarity_score": similarity,
                            "morphism_type": mor_to_target.name,
                        }
                    ))

        return predictions


# =============================================================================
# Strategy 3: Temporal Reasoning
# =============================================================================

class TemporalReasoningStrategy(InferenceStrategy):
    """
    Use temporal metadata for influence prediction.

    Rules:
    - If birth(source) < birth(target): source may have influenced target
    - If contemporaries (+-20 years): may have collaborated
    - If source died before target born: historical influence only
    """

    name = "temporal_reasoning"

    def predict(self, source: str, target: str) -> List[Prediction]:
        predictions = []

        source_obj = self.category.get(source)
        target_obj = self.category.get(target)

        if not source_obj or not target_obj:
            return predictions

        existing = self._existing_morphism_pairs()
        if (source, target) in existing:
            return predictions

        # Financial domain: use market_cap for influence direction
        source_mc = source_obj.metadata.get("market_cap")
        target_mc = target_obj.metadata.get("market_cap")

        if source_mc is not None and target_mc is not None:
            return self._predict_financial(source, target, source_obj, target_obj, source_mc, target_mc)

        # Physics domain: use birth/death for temporal influence
        source_birth = source_obj.metadata.get("birth")
        target_birth = target_obj.metadata.get("birth")

        if source_birth is None or target_birth is None:
            return predictions

        birth_diff = target_birth - source_birth
        source_death = source_obj.metadata.get("death")

        if birth_diff > 0:
            if source_death and source_death < target_birth:
                confidence = 0.55
                relation = "influenced"
                reasoning = f"{source} (d.{source_death}) predates {target} (b.{target_birth}) - historical influence"
            elif birth_diff <= 50:
                confidence = 0.70
                relation = "influenced"
                reasoning = f"{source} (b.{source_birth}) is {birth_diff} years older than {target} (b.{target_birth})"
            else:
                confidence = 0.50
                relation = "influenced"
                reasoning = f"{source} (b.{source_birth}) predates {target} (b.{target_birth}) by {birth_diff} years"

            predictions.append(Prediction(
                source=source,
                target=target,
                predicted_relation=relation,
                prediction_type=PredictionType.TEMPORAL_INFLUENCE,
                strategy_name=self.name,
                confidence=confidence,
                reasoning=reasoning,
                evidence={
                    "source_birth": source_birth,
                    "source_death": source_death,
                    "target_birth": target_birth,
                    "birth_diff": birth_diff,
                }
            ))

        elif abs(birth_diff) <= 20:
            confidence = 0.55
            predictions.append(Prediction(
                source=source,
                target=target,
                predicted_relation="collaborated",
                prediction_type=PredictionType.TEMPORAL_COLLABORATION,
                strategy_name=self.name,
                confidence=confidence,
                reasoning=f"{source} and {target} are contemporaries (birth diff: {birth_diff} years)",
                evidence={
                    "source_birth": source_birth,
                    "target_birth": target_birth,
                    "birth_diff": birth_diff,
                }
            ))

        return predictions

    def _predict_financial(self, source, target, source_obj, target_obj, source_mc, target_mc):
        """Financial temporal reasoning: larger market cap companies influence smaller ones."""
        predictions = []

        # Same sector check
        source_sector = source_obj.metadata.get("sector", "")
        target_sector = target_obj.metadata.get("sector", "")
        same_sector = source_sector and source_sector == target_sector

        # Market cap ratio determines influence direction
        ratio = source_mc / max(target_mc, 1)

        if ratio > 5:
            # Source much larger -- likely influences target
            confidence = min(0.65, 0.45 + 0.05 * (ratio / 10))
            relation = "correlates_with" if same_sector else "influences"
            reasoning = (f"{source} (mkt_cap={source_mc:.0e}) is {ratio:.1f}x larger than "
                         f"{target} (mkt_cap={target_mc:.0e})")
            if same_sector:
                reasoning += f" -- same sector ({source_sector})"
                confidence = min(0.70, confidence + 0.05)

            predictions.append(Prediction(
                source=source,
                target=target,
                predicted_relation=relation,
                prediction_type=PredictionType.TEMPORAL_INFLUENCE,
                strategy_name=self.name,
                confidence=confidence,
                reasoning=reasoning,
                evidence={
                    "source_market_cap": source_mc,
                    "target_market_cap": target_mc,
                    "cap_ratio": ratio,
                    "same_sector": same_sector,
                }
            ))
        elif same_sector and 0.2 < ratio < 5:
            # Similar size, same sector -- likely correlates
            confidence = 0.55
            predictions.append(Prediction(
                source=source,
                target=target,
                predicted_relation="correlates_with",
                prediction_type=PredictionType.TEMPORAL_COLLABORATION,
                strategy_name=self.name,
                confidence=confidence,
                reasoning=f"{source} and {target} are similar-sized peers in {source_sector}",
                evidence={
                    "source_market_cap": source_mc,
                    "target_market_cap": target_mc,
                    "cap_ratio": ratio,
                    "same_sector": True,
                }
            ))

        return predictions


# =============================================================================
# Strategy 4: Type Heuristics
# =============================================================================

class TypeHeuristicStrategy(InferenceStrategy):
    """
    Use object types to constrain and predict relationships.

    TYPE_RULES defines valid morphism types between object types.
    """

    name = "type_heuristic"

    TYPE_RULES = {
        # Physics domain (legacy)
        ("Physicist", "Physicist"): ["influenced", "collaborated", "trained"],
        ("Physicist", "Theory"): ["created", "contributed", "developed", "extended"],
        ("Physicist", "Mathematician"): ["influenced", "collaborated"],
        ("Theory", "Theory"): ["extends", "supersedes", "reformulates", "generalizes"],
        ("Theory", "Physicist"): [],
        ("Mathematician", "Physicist"): ["influenced", "provided_tools"],
        ("Mathematician", "Mathematician"): ["influenced", "collaborated"],
        ("Mathematician", "Theory"): ["axiomatized", "proved", "formalized", "developed"],
        ("Philosopher", "Physicist"): ["influenced"],
        ("Philosopher", "Theory"): ["influenced", "conceptualized"],
        # Financial domain
        ("Asset:equity", "Sector"): ["in_sector"],
        ("Asset:equity", "Asset:equity"): ["correlates_with", "competes_with", "supplies", "hedges", "leads"],
        ("Asset:equity", "MacroFactor"): ["exposed_to", "responds_to"],
        ("Asset:equity", "Index"): ["component_of"],
        ("Asset:equity", "RiskFactor"): ["has_risk"],
        ("Sector", "MacroFactor"): ["sensitive_to"],
        ("Sector", "Sector"): ["correlates_with"],
        ("MacroFactor", "MacroFactor"): ["influences"],
        ("MacroFactor", "Sector"): ["influences"],
        ("Index", "Asset:equity"): [],  # Indices don't influence assets directly
        ("Portfolio", "Asset:equity"): ["holds"],
    }

    def predict(self, source: str, target: str) -> List[Prediction]:
        predictions = []

        source_obj = self.category.get(source)
        target_obj = self.category.get(target)

        if not source_obj or not target_obj:
            return predictions

        type_pair = (source_obj.type_name, target_obj.type_name)
        valid_relations = self.TYPE_RULES.get(type_pair, [])

        if not valid_relations:
            return predictions

        existing = self._existing_morphism_pairs()
        if (source, target) in existing:
            return predictions

        # Check if similar typed objects have this relationship
        outgoing, incoming = self._build_morphism_index()

        # Count how often each valid relation appears between these types
        relation_counts = {r: 0 for r in valid_relations}
        for mor in self._get_morphisms():
            src = self.category.get(mor.source)
            tgt = self.category.get(mor.target)
            if src and tgt:
                if (src.type_name, tgt.type_name) == type_pair:
                    if mor.name in relation_counts:
                        relation_counts[mor.name] += 1

        # Predict most common valid relation
        if any(relation_counts.values()):
            best_relation = max(relation_counts.items(), key=lambda x: x[1])
            if best_relation[1] > 0:
                total = sum(relation_counts.values())
                confidence = min(0.70, 0.4 + 0.3 * (best_relation[1] / total))

                predictions.append(Prediction(
                    source=source,
                    target=target,
                    predicted_relation=best_relation[0],
                    prediction_type=PredictionType.TYPE_CONSTRAINED,
                    strategy_name=self.name,
                    confidence=confidence,
                    reasoning=f"Type pattern: {type_pair[0]}->{type_pair[1]} typically use '{best_relation[0]}' ({best_relation[1]}/{total})",
                    evidence={
                        "source_type": source_obj.type_name,
                        "target_type": target_obj.type_name,
                        "relation_distribution": relation_counts,
                    }
                ))

        return predictions


# =============================================================================
# Strategy 5: Yoneda Pattern
# =============================================================================

class YonedaPatternStrategy(InferenceStrategy):
    """
    Objects with same morphism patterns are structurally similar.

    Yoneda lemma: Hom(A, -) determines A up to isomorphism.
    If Hom(A, -) ~ Hom(B, -), then A and B play the same structural role.
    """

    name = "yoneda_pattern"

    def predict(self, source: str, target: str) -> List[Prediction]:
        predictions = []

        outgoing, incoming = self._build_morphism_index()
        existing = self._existing_morphism_pairs()
        source_obj = self.category.get(source)

        if not source_obj or (source, target) in existing:
            return predictions

        # Build Hom(source, -) - outgoing morphism types
        source_hom_out = {m.name for m in outgoing.get(source, [])}
        source_hom_out_targets = {m.target for m in outgoing.get(source, [])}

        # Build Hom(-, source) - incoming morphism types
        source_hom_in = {m.name for m in incoming.get(source, [])}
        source_hom_in_sources = {m.source for m in incoming.get(source, [])}

        # Find objects with similar Hom patterns that connect to target
        for obj in self._get_objects():
            if (
                obj.name == source
                or obj.name == target
                or obj.type_name != source_obj.type_name
            ):
                continue

            obj_hom_out = {m.name for m in outgoing.get(obj.name, [])}
            obj_hom_out_targets = {m.target for m in outgoing.get(obj.name, [])}

            # Check if obj has morphism to target
            if target not in obj_hom_out_targets:
                continue

            # Compute Yoneda similarity (morphism type overlap)
            out_type_sim = len(source_hom_out & obj_hom_out) / max(len(source_hom_out | obj_hom_out), 1)
            out_target_sim = len(source_hom_out_targets & obj_hom_out_targets) / max(len(source_hom_out_targets | obj_hom_out_targets), 1)

            yoneda_similarity = (out_type_sim + out_target_sim) / 2

            if yoneda_similarity > 0.3:
                # Objects have similar Hom patterns
                mor_to_target = next(
                    (m for m in outgoing.get(obj.name, []) if m.target == target),
                    None
                )
                if mor_to_target:
                    confidence = min(0.80, 0.5 + yoneda_similarity * 0.4)

                    predictions.append(Prediction(
                        source=source,
                        target=target,
                        predicted_relation=mor_to_target.name,
                        prediction_type=PredictionType.YONEDA_ANALOGY,
                        strategy_name=self.name,
                        confidence=confidence,
                        reasoning=f"Yoneda similarity: {source} ~ {obj.name} ({yoneda_similarity:.2f}), and {obj.name} has '{mor_to_target.name}' to {target}",
                        evidence={
                            "similar_object": obj.name,
                            "yoneda_similarity": yoneda_similarity,
                            "out_type_similarity": out_type_sim,
                            "out_target_similarity": out_target_sim,
                        }
                    ))

        return predictions


# =============================================================================
# Strategy 6: Composition
# =============================================================================

class CompositionStrategy(InferenceStrategy):
    """
    If A->B->C exists, predict A->C should exist (transitive closure).

    In category theory, morphism composition is fundamental.
    """

    name = "composition"

    def predict(self, source: str, target: str) -> List[Prediction]:
        predictions = []

        existing = self._existing_morphism_pairs()
        if (source, target) in existing:
            return predictions

        # Type filtering for drug repurposing
        source_obj = self.category.get(source)
        target_obj = self.category.get(target)

        # Only predict Drug -> Disease for repurposing
        if not (source_obj and target_obj):
            return predictions

        is_drug_disease = (source_obj.type_name == "Drug" and target_obj.type_name == "Disease")

        outgoing, incoming = self._build_morphism_index()

        # Find 2-hop paths: source -> intermediate -> target
        source_targets = {m.target: m for m in outgoing.get(source, [])}

        for intermediate, mor1 in source_targets.items():
            # Check if intermediate -> target exists
            intermediate_targets = {m.target: m for m in outgoing.get(intermediate, [])}

            if target in intermediate_targets:
                mor2 = intermediate_targets[target]

                # Type filtering: for Drug->Disease, require protein intermediate
                if is_drug_disease:
                    intermediate_obj = self.category.get(intermediate)
                    if not intermediate_obj:
                        continue

                    if intermediate_obj.type_name not in REPURPOSING_INTERMEDIATE_TYPES:
                        continue

                    # Confidence follows the multiplicative enriched-category rule.
                    composed_confidence = mor1.confidence * mor2.confidence
                else:
                    # For other types, apply penalty
                    composed_confidence = mor1.confidence * mor2.confidence * 0.85

                # Determine composed relation type
                if mor1.name == mor2.name:
                    composed_type = mor1.name
                else:
                    composed_type = f"composed_{mor1.name}_{mor2.name}"
                    # Simplify common patterns
                    if "influenced" in composed_type:
                        composed_type = "influenced"

                predictions.append(Prediction(
                    source=source,
                    target=target,
                    predicted_relation=composed_type,
                    prediction_type=PredictionType.COMPOSED_MORPHISM,
                    strategy_name=self.name,
                    confidence=composed_confidence,
                    reasoning=f"Composition: {source} --[{mor1.name}]--> {intermediate} --[{mor2.name}]--> {target}",
                    evidence={
                        "intermediate": intermediate,
                        "morphism1": mor1.name,
                        "morphism2": mor2.name,
                        "confidence1": mor1.confidence,
                        "confidence2": mor2.confidence,
                    }
                ))

        return predictions


# =============================================================================
# Strategy 7: Fibration Lift
# =============================================================================

class FibrationLiftStrategy(InferenceStrategy):
    """
    Use fibration structure for Cartesian lift predictions.

    If fiber(A) has object X and morphism f: A->B exists,
    predict F(X) should exist in fiber(B).

    In our context:
    - Fibers are grouped by object type or era
    - Cartesian lifts preserve relationships across fibers
    """

    name = "fibration_lift"

    def predict(self, source: str, target: str) -> List[Prediction]:
        predictions = []

        source_obj = self.category.get(source)
        target_obj = self.category.get(target)

        if not source_obj or not target_obj:
            return predictions

        existing = self._existing_morphism_pairs()
        if (source, target) in existing:
            return predictions

        outgoing, incoming = self._build_morphism_index()

        # Define fibers by type and era
        source_fiber = (source_obj.type_name, source_obj.metadata.get("era", "unknown"))
        target_fiber = (target_obj.type_name, target_obj.metadata.get("era", "unknown"))

        # Find objects in same fiber as source with morphisms to objects in target's fiber
        for obj in self._get_objects():
            if obj.name == source:
                continue

            obj_fiber = (obj.type_name, obj.metadata.get("era", "unknown"))

            if obj_fiber == source_fiber:
                # Same fiber as source - check Cartesian lift pattern
                obj_out = outgoing.get(obj.name, [])

                for mor in obj_out:
                    mor_target = self.category.get(mor.target)
                    if mor_target:
                        mor_target_fiber = (mor_target.type_name, mor_target.metadata.get("era", "unknown"))

                        if mor_target_fiber == target_fiber and mor.target == target:
                            # Found lift pattern: obj (same fiber as source) -> target
                            # Predict source should also -> target

                            confidence = min(0.70, mor.confidence * 0.8)

                            predictions.append(Prediction(
                                source=source,
                                target=target,
                                predicted_relation=mor.name,
                                prediction_type=PredictionType.CARTESIAN_LIFT,
                                strategy_name=self.name,
                                confidence=confidence,
                                reasoning=f"Fibration lift: {obj.name} (fiber: {obj_fiber}) has '{mor.name}' to {target}, lift to {source}",
                                evidence={
                                    "lift_source": obj.name,
                                    "source_fiber": source_fiber,
                                    "target_fiber": target_fiber,
                                    "morphism_type": mor.name,
                                }
                            ))

        return predictions


# =============================================================================
# Strategy 8: Structural Holes
# =============================================================================

class StructuralHoleStrategy(InferenceStrategy):
    """
    Find triangles that should close.

    If A->B and A->C exist, but B->C or C->B is missing,
    and types are compatible, predict the missing edge.
    """

    name = "structural_hole"

    def predict(self, source: str, target: str) -> List[Prediction]:
        predictions = []

        existing = self._existing_morphism_pairs()
        if (source, target) in existing:
            return predictions

        outgoing, incoming = self._build_morphism_index()

        # Find common ancestors: objects that point to both source and target
        source_ancestors = {m.source for m in incoming.get(source, [])}
        target_ancestors = {m.source for m in incoming.get(target, [])}

        common_ancestors = source_ancestors & target_ancestors

        if common_ancestors:
            # Triangle: ancestor -> source, ancestor -> target
            # Missing: source -> target or target -> source

            for ancestor in common_ancestors:
                mor_to_source = next((m for m in outgoing.get(ancestor, []) if m.target == source), None)
                mor_to_target = next((m for m in outgoing.get(ancestor, []) if m.target == target), None)

                if mor_to_source and mor_to_target:
                    # Check type compatibility
                    source_obj = self.category.get(source)
                    target_obj = self.category.get(target)

                    if source_obj and target_obj:
                        type_pair = (source_obj.type_name, target_obj.type_name)
                        valid_relations = TypeHeuristicStrategy.TYPE_RULES.get(type_pair, [])

                        if valid_relations:
                            # Predict closure with most common relation for this type pair
                            confidence = min(0.65, (mor_to_source.confidence + mor_to_target.confidence) / 2 * 0.7)

                            predictions.append(Prediction(
                                source=source,
                                target=target,
                                predicted_relation=valid_relations[0] if valid_relations else "related_to",
                                prediction_type=PredictionType.TRIANGLE_CLOSURE,
                                strategy_name=self.name,
                                confidence=confidence,
                                reasoning=f"Triangle closure: {ancestor} -> both {source} and {target}, missing edge between them",
                                evidence={
                                    "common_ancestor": ancestor,
                                    "mor_to_source": mor_to_source.name,
                                    "mor_to_target": mor_to_target.name,
                                }
                            ))

        # Also check: source -> X, target -> X (common descendants)
        source_descendants = {m.target for m in outgoing.get(source, [])}
        target_descendants = {m.target for m in outgoing.get(target, [])}

        common_descendants = source_descendants & target_descendants

        if common_descendants and (target, source) not in existing:
            # Both point to same thing - might be related
            for descendant in list(common_descendants)[:3]:  # Limit
                mor_from_source = next((m for m in outgoing.get(source, []) if m.target == descendant), None)
                mor_from_target = next((m for m in outgoing.get(target, []) if m.target == descendant), None)

                if mor_from_source and mor_from_target:
                    confidence = 0.50  # Lower confidence for this pattern

                    predictions.append(Prediction(
                        source=source,
                        target=target,
                        predicted_relation="related_to",
                        prediction_type=PredictionType.STRUCTURAL_HOLE,
                        strategy_name=self.name,
                        confidence=confidence,
                        reasoning=f"Common descendant: both {source} and {target} connect to {descendant}",
                        evidence={
                            "common_descendant": descendant,
                            "source_relation": mor_from_source.name,
                            "target_relation": mor_from_target.name,
                        }
                    ))

        return predictions


# =============================================================================
# Strategy 9: Geometric (Ricci Curvature)
# =============================================================================

class GeometricStrategy(InferenceStrategy):
    """
    Use Ollivier-Ricci curvature for geometry-aware predictions.

    Key insight: Objects in the same geometric region (as revealed by
    curvature analysis) are more likely to be connected than objects
    in different regions.

    - Spherical regions: dense clusters, high connection probability
    - Hyperbolic regions: tree-like, lower connection probability
    - Bridge edges: connect different geometric regions

    Integrates: geometry/ricci.py
    """

    name = "geometric"

    def __init__(self, category: Category, curvature_computer=None):
        super().__init__(category)
        self.curvature_computer = curvature_computer
        self._curvature_result = None
        self._region_map = None

    def _ensure_curvature(self):
        """Compute curvature if not already done."""
        if self._curvature_result is not None:
            return

        try:
            if self.curvature_computer is None:
                from geometry import OllivierRicciCurvature
                self.curvature_computer = OllivierRicciCurvature(self.category)

            self._curvature_result = self.curvature_computer.compute_all_curvatures()
            self._region_map = self.curvature_computer.get_geometric_regions()
        except ImportError:
            self._curvature_result = None
            self._region_map = {}

    def predict(self, source: str, target: str) -> List[Prediction]:
        predictions = []

        self._ensure_curvature()

        if self._curvature_result is None:
            return predictions  # Geometry module not available

        existing = self._existing_morphism_pairs()
        if (source, target) in existing:
            return predictions

        # Get geometric regions for source and target
        source_region = self._region_map.get(source, "unknown")
        target_region = self._region_map.get(target, "unknown")

        # Get node curvatures
        source_curvature = self._curvature_result.node_curvatures.get(source, 0.0)
        target_curvature = self._curvature_result.node_curvatures.get(target, 0.0)

        # Same region prediction: higher confidence if same geometry
        if source_region == target_region and source_region != "unknown":
            # Same geometric region - likely connected

            # Base confidence depends on region type
            if source_region == "spherical":
                base_confidence = 0.75  # Dense clusters have high connectivity
            elif source_region == "euclidean":
                base_confidence = 0.55  # Chains have moderate connectivity
            else:  # hyperbolic
                base_confidence = 0.45  # Tree-like has lower connectivity

            # Adjust by curvature similarity
            curvature_diff = abs(source_curvature - target_curvature)
            curvature_bonus = max(0, 0.15 - curvature_diff * 0.3)

            confidence = min(0.85, base_confidence + curvature_bonus)

            predictions.append(Prediction(
                source=source,
                target=target,
                predicted_relation="related_to",
                prediction_type=PredictionType.GEOMETRIC,
                strategy_name=self.name,
                confidence=confidence,
                reasoning=f"Same geometric region ({source_region}): both nodes are in a {source_region} structure with similar curvature",
                evidence={
                    "source_region": source_region,
                    "target_region": target_region,
                    "source_curvature": source_curvature,
                    "target_curvature": target_curvature,
                    "region_match": True,
                }
            ))

        # Cross-region prediction: could be a bridge edge
        elif source_region != target_region and source_region != "unknown" and target_region != "unknown":
            # Different regions - could be a paradigm bridge

            # Bridge edges are less common but significant
            # High curvature difference suggests true bridge
            curvature_diff = abs(source_curvature - target_curvature)

            if curvature_diff > 0.2:
                # Significant curvature jump - might be a bridge
                confidence = min(0.50, 0.35 + curvature_diff * 0.3)

                predictions.append(Prediction(
                    source=source,
                    target=target,
                    predicted_relation="bridges_to",
                    prediction_type=PredictionType.GEOMETRIC,
                    strategy_name=self.name,
                    confidence=confidence,
                    reasoning=f"Potential paradigm bridge: {source} ({source_region}) to {target} ({target_region}), curvature gap {curvature_diff:.3f}",
                    evidence={
                        "source_region": source_region,
                        "target_region": target_region,
                        "source_curvature": source_curvature,
                        "target_curvature": target_curvature,
                        "curvature_gap": curvature_diff,
                        "region_match": False,
                    }
                ))

        # Hub-based prediction: high-curvature nodes are hubs
        if source_curvature > 0.3:
            # Source is a hub - more likely to have connections
            hub_bonus = min(0.15, source_curvature * 0.2)

            if (source, target) not in existing and len(predictions) == 0:
                predictions.append(Prediction(
                    source=source,
                    target=target,
                    predicted_relation="connected_to",
                    prediction_type=PredictionType.GEOMETRIC,
                    strategy_name=self.name,
                    confidence=0.40 + hub_bonus,
                    reasoning=f"Hub node: {source} has high curvature ({source_curvature:.3f}), indicating high connectivity",
                    evidence={
                        "source_curvature": source_curvature,
                        "hub_indicator": True,
                    }
                ))

        return predictions


# =============================================================================
# Strategy Registry
# =============================================================================

def _has_object_types(category: Category, *type_names: str) -> bool:
    """Return True when the category has all requested object types."""
    try:
        present = {obj.type_name for obj in category.objects()}
    except Exception:
        return False
    return set(type_names).issubset(present)


def _has_visible_drug_disease_labels(category: Category) -> bool:
    """Return True when Yoneda distance has treatment comparators."""
    try:
        morphisms = category.morphisms()
    except Exception:
        return False
    for morphism in morphisms:
        source = category.get(morphism.source)
        target = category.get(morphism.target)
        if (
            source and target
            and source.type_name == "Drug"
            and target.type_name == "Disease"
        ):
            return True
    return False


def create_all_strategies(
    category: Category,
    embeddings: EmbeddingsEngine,
    include_type_heuristic: bool = False,
    include_yoneda_distance: bool = True,
) -> List[InferenceStrategy]:
    """Create all inference strategies (built-in + imported)."""
    strategies = [
        KanExtensionStrategy(category),
        TemporalReasoningStrategy(category),
        YonedaPatternStrategy(category),
        CompositionStrategy(category),
        FibrationLiftStrategy(category),
        StructuralHoleStrategy(category),
    ]
    if include_type_heuristic:
        strategies.insert(2, TypeHeuristicStrategy(category))

    # Add SemanticSimilarityStrategy only if embeddings available
    try:
        if embeddings and embeddings.is_available:
            strategies.append(SemanticSimilarityStrategy(category, embeddings))
    except Exception:
        pass  # Embeddings not available, skip this strategy

    # Add Geometric strategy if available
    try:
        from geometry import OllivierRicciCurvature
        strategies.append(GeometricStrategy(category))
    except ImportError:
        pass  # Geometry module not available

    # Add imported strategies (from separate modules)
    # These activate previously dead code in categorical/

    # ToposLogicStrategy: intuitionistic reasoning (activates topos_logic.py)
    try:
        from oracle.topos_strategy import ToposLogicStrategy
        strategies.append(ToposLogicStrategy(category))
    except ImportError:
        pass

    # YonedaDistanceStrategy: STT-derived structural drug similarity on the
    # clean MEASURED+ESTABLISHED evidence subgraph.
    if (
        include_yoneda_distance
        and _has_object_types(category, "Drug", "Disease")
        and _has_visible_drug_disease_labels(category)
    ):
        try:
            from oracle.yoneda_strategy import YonedaDistanceStrategy
            strategies.append(YonedaDistanceStrategy(category))
        except Exception:
            pass

    # NaturalTransformationStrategy: pattern variant detection (activates natural_transformations.py)
    try:
        from oracle.natural_transformation import NaturalTransformationStrategy
        strategies.append(NaturalTransformationStrategy(category))
    except ImportError:
        pass

    # OperadicDecompositionStrategy: n-ary composition analysis (activates operads.py)
    try:
        from oracle.operadic_decomposition import OperadicDecompositionStrategy
        strategies.append(OperadicDecompositionStrategy(category))
    except ImportError:
        pass

    # EvidenceCombinationStrategy: Dempster-Shafer uncertainty (activates dempster_shafer.py)
    try:
        from oracle.evidence_combination import EvidenceCombinationStrategy
        strategies.append(EvidenceCombinationStrategy(category))
    except ImportError:
        pass

    # StreamingForecastStrategy: temporal predictions (activates streaming_kan.py)
    try:
        from oracle.streaming_forecast import StreamingForecastStrategy
        strategies.append(StreamingForecastStrategy(category))
    except ImportError:
        pass

    # TopologicalAnomalyStrategy: persistent homology anomalies (activates persistent_homology.py)
    try:
        from oracle.topological_anomaly import TopologicalAnomalyStrategy
        strategies.append(TopologicalAnomalyStrategy(category))
    except ImportError:
        pass

    # GameStrategy: Nash equilibrium analysis (activates game/nash.py)
    try:
        from oracle.game_strategy import GameStrategy
        strategies.append(GameStrategy(category))
    except ImportError:
        pass

    # ActivityAnalysisStrategy: Engeström Activity Theory
    try:
        from oracle.activity_analysis import ActivityAnalysisStrategy
        strategies.append(ActivityAnalysisStrategy(category))
    except ImportError:
        pass

    # BoundaryDetectionStrategy: Cross-domain boundary objects
    try:
        from oracle.boundary_detection import BoundaryDetectionStrategy
        strategies.append(BoundaryDetectionStrategy(category))
    except ImportError:
        pass

    # CellularDynamicsStrategy: SIR epidemic modeling
    try:
        from oracle.cellular_dynamics import CellularDynamicsStrategy
        strategies.append(CellularDynamicsStrategy(category))
    except ImportError:
        pass

    # CubicalGapFillingStrategy: Cubical type theory gap filling
    try:
        from oracle.cubical_gap_filling_strategy import CubicalGapFillingStrategy
        strategies.append(CubicalGapFillingStrategy(category))
    except ImportError:
        pass

    # GeometricHomotopyStrategy: Homotopy-based inference
    try:
        from oracle.geometric_homotopy_strategy import GeometricHomotopyStrategy
        strategies.append(GeometricHomotopyStrategy(category))
    except ImportError:
        pass

    # HornFillingStrategy: simplicial inner-horn filling (generic promotion of
    # the oracle/horns.py nerve diagnostic). Adds cross-intermediate coherence
    # on top of plain composition.
    try:
        from oracle.horn_filling_strategy import HornFillingStrategy
        strategies.append(HornFillingStrategy(category))
    except ImportError:
        pass

    # ConjectureStrategy: structural-gap scorer (generic profile -- no endpoint
    # type restriction). Scores reasons an edge *should* exist but doesn't.
    try:
        from oracle.conjecture_strategy import ConjectureStrategy
        strategies.append(ConjectureStrategy(category))
    except ImportError:
        pass

    return strategies
