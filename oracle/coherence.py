"""
Sheaf Coherence Validation for KOMPOSOS-IV Oracle.

Implements sheaf-theoretic coherence checking:
- Validates that predictions "agree on overlaps"
- Detects semantic contradictions
- Filters incoherent predictions

Sheaf condition: Local data must glue consistently to global data.
"""

import sys
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from oracle.prediction import Prediction, PredictionBatch
from data.embeddings import EmbeddingsEngine


# Antonym pairs for contradiction detection
ANTONYM_PAIRS = [
    ("increase", "decrease"),
    ("positive", "negative"),
    ("create", "destroy"),
    ("extend", "reduce"),
    ("support", "oppose"),
    ("precede", "follow"),
    ("influenced", "opposed"),
    ("unified", "divided"),
    ("proved", "disproved"),
    ("accept", "reject"),
]


@dataclass
class CoherenceResult:
    """Result of coherence checking."""
    is_coherent: bool
    coherence_score: float  # 0.0 to 1.0
    min_similarity: float
    contradictions: List[Tuple[Prediction, Prediction, str]]  # (pred1, pred2, reason)
    filtered_predictions: List[Prediction]


class SheafCoherenceChecker:
    """
    Validate predictions using sheaf-theoretic coherence.

    The sheaf condition requires that data "agrees on overlaps":
    - If two predictions concern the same source-target pair, they should agree
    - If predictions are semantically contradictory, flag them
    - Filter predictions that violate coherence
    """

    def __init__(self, embeddings: EmbeddingsEngine,
                 similarity_threshold: float = 0.5,
                 contradiction_threshold: float = 0.3):
        """
        Initialize coherence checker.

        Args:
            embeddings: Embeddings engine for semantic comparison
            similarity_threshold: Minimum average similarity for coherence
            contradiction_threshold: Maximum similarity for contradiction
        """
        self.embeddings = embeddings
        self.similarity_threshold = similarity_threshold
        self.contradiction_threshold = contradiction_threshold

    def check_coherence(self, predictions: List[Prediction]) -> CoherenceResult:
        """
        Check coherence of a set of predictions.

        Sheaf condition: For predictions to be coherent:
        1. No semantic contradictions
        2. Average similarity >= threshold
        3. Minimum similarity >= contradiction_threshold
        """
        if len(predictions) <= 1:
            return CoherenceResult(
                is_coherent=True,
                coherence_score=1.0,
                min_similarity=1.0,
                contradictions=[],
                filtered_predictions=predictions,
            )

        # Group predictions by (source, target) pair
        by_pair: Dict[Tuple[str, str], List[Prediction]] = {}
        for pred in predictions:
            key = (pred.source, pred.target)
            if key not in by_pair:
                by_pair[key] = []
            by_pair[key].append(pred)

        all_contradictions = []
        similarities = []
        incoherent_predictions = set()

        # Check pairwise coherence
        for (source, target), preds in by_pair.items():
            if len(preds) <= 1:
                continue

            for i, pred1 in enumerate(preds):
                for pred2 in preds[i+1:]:
                    # Check for semantic contradiction
                    contradiction = self._detect_contradiction(pred1, pred2)
                    if contradiction:
                        all_contradictions.append((pred1, pred2, contradiction))
                        # Mark lower confidence prediction as incoherent
                        if pred1.confidence < pred2.confidence:
                            incoherent_predictions.add(id(pred1))
                        else:
                            incoherent_predictions.add(id(pred2))
                    else:
                        # Compute similarity of predictions
                        sim = self._compute_prediction_similarity(pred1, pred2)
                        similarities.append(sim)

        # Also check across pairs for related contradictions
        pairs = list(by_pair.keys())
        for i, pair1 in enumerate(pairs):
            for pair2 in pairs[i+1:]:
                # Check if pair1 and pair2 are related (share source or target)
                if pair1[0] == pair2[0] or pair1[1] == pair2[1]:
                    for pred1 in by_pair[pair1]:
                        for pred2 in by_pair[pair2]:
                            contradiction = self._detect_cross_pair_contradiction(pred1, pred2)
                            if contradiction:
                                all_contradictions.append((pred1, pred2, contradiction))

        # Compute coherence metrics
        if similarities:
            avg_similarity = sum(similarities) / len(similarities)
            min_similarity = min(similarities)
        else:
            avg_similarity = 1.0
            min_similarity = 1.0

        has_contradictions = len(all_contradictions) > 0

        is_coherent = (
            not has_contradictions and
            avg_similarity >= self.similarity_threshold and
            min_similarity >= self.contradiction_threshold
        )

        # Filter out incoherent predictions
        filtered = [p for p in predictions if id(p) not in incoherent_predictions]

        return CoherenceResult(
            is_coherent=is_coherent,
            coherence_score=avg_similarity,
            min_similarity=min_similarity,
            contradictions=all_contradictions,
            filtered_predictions=filtered,
        )

    def _detect_contradiction(self, pred1: Prediction, pred2: Prediction) -> Optional[str]:
        """
        Detect if two predictions are semantically contradictory.

        Checks for:
        - Antonym pairs in relation types
        - Negation patterns
        - Incompatible relation types
        """
        rel1 = pred1.predicted_relation.lower()
        rel2 = pred2.predicted_relation.lower()

        # Check antonym pairs
        for ant1, ant2 in ANTONYM_PAIRS:
            if (ant1 in rel1 and ant2 in rel2) or (ant2 in rel1 and ant1 in rel2):
                return f"Antonym contradiction: '{pred1.predicted_relation}' vs '{pred2.predicted_relation}'"

        # Check for negation
        if ("not_" in rel1 or "non_" in rel1) != ("not_" in rel2 or "non_" in rel2):
            if rel1.replace("not_", "").replace("non_", "") == rel2.replace("not_", "").replace("non_", ""):
                return f"Negation contradiction: '{rel1}' vs '{rel2}'"

        # Check incompatible relation types
        incompatible_pairs = [
            ("created", "extended"),  # Can't both create and extend same thing
            ("supersedes", "extends"),  # Different directions
            ("unified", "separated"),
        ]
        for inc1, inc2 in incompatible_pairs:
            if (inc1 in rel1 and inc2 in rel2) or (inc2 in rel1 and inc1 in rel2):
                return f"Incompatible relations: '{rel1}' vs '{rel2}'"

        return None

    def _detect_cross_pair_contradiction(self, pred1: Prediction, pred2: Prediction) -> Optional[str]:
        """
        Detect contradictions across different source-target pairs.

        For example:
        - A influences B and B influences A (cycle without evidence)
        - A created X and B created X (exclusive creation)
        """
        # Check for suspicious cycles
        if (pred1.source == pred2.target and
            pred1.target == pred2.source and
            pred1.predicted_relation == pred2.predicted_relation):
            # Same relation in both directions - suspicious
            if pred1.predicted_relation in ["created", "preceded", "superseded"]:
                return f"Cycle contradiction: {pred1.source} <--> {pred1.target} with '{pred1.predicted_relation}'"

        # Check for exclusive creation
        if (pred1.target == pred2.target and
            pred1.predicted_relation == "created" and
            pred2.predicted_relation == "created"):
            # Multiple creators might be OK (collaboration), but lower confidence
            return None  # Not a hard contradiction

        return None

    def _compute_prediction_similarity(self, pred1: Prediction, pred2: Prediction) -> float:
        """
        Compute semantic similarity between two predictions.

        Uses embeddings if available, otherwise falls back to string matching.
        """
        # Compare relation types
        rel1 = pred1.predicted_relation
        rel2 = pred2.predicted_relation

        if rel1 == rel2:
            return 1.0

        # Use embeddings for semantic similarity
        if self.embeddings and self.embeddings.is_available:
            return self.embeddings.similarity(rel1, rel2)

        # Fallback: simple word overlap
        words1 = set(rel1.lower().replace("_", " ").split())
        words2 = set(rel2.lower().replace("_", " ").split())

        if not words1 or not words2:
            return 0.0

        return len(words1 & words2) / len(words1 | words2)

    def adjust_confidences(self, predictions: List[Prediction]) -> List[Prediction]:
        """
        Adjust prediction confidences based on coherence with other predictions.

        Predictions confirmed by multiple sources get boosted.
        Predictions with low coherence get penalized.
        """
        if not predictions:
            return predictions

        # Group by key
        by_key: Dict[tuple, List[Prediction]] = {}
        for pred in predictions:
            if pred.key not in by_key:
                by_key[pred.key] = []
            by_key[pred.key].append(pred)

        adjusted = []
        for key, preds in by_key.items():
            if len(preds) == 1:
                adjusted.append(preds[0])
            else:
                # Multiple predictions for same key - check agreement
                relations = [p.predicted_relation for p in preds]
                most_common = max(set(relations), key=relations.count)

                for pred in preds:
                    if pred.predicted_relation == most_common:
                        # Boost confidence for agreement
                        agreement_count = relations.count(most_common)
                        boost = min(0.15, 0.05 * agreement_count)
                        new_conf = min(0.98, pred.confidence + boost)
                        adjusted.append(pred.with_adjusted_confidence(new_conf))
                    else:
                        # Penalize disagreement
                        new_conf = pred.confidence * 0.8
                        adjusted.append(pred.with_adjusted_confidence(new_conf))

        return adjusted
