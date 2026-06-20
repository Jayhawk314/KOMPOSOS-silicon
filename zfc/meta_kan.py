# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
Meta Kan Extension — System 3

Three levels of prediction in KOMPOSOS:

Level 1 — CAT's Kan extension:
    "Given this knowledge graph, predict this unknown relationship."
    Extends over objects and morphisms.
    Lives in: categorical/kan_extensions.py

Level 2 — ZFC's entailment:
    "Given these axioms, what must be true?"
    Checks satisfiability and finds witnesses.
    Lives in: zfc/logic.py

Level 3 — Meta Kan extension on the DELTA:
    "Given the history of disagreements between Level 1 and Level 2,
     predict what kind of disagreement a new query will produce,
     and what resolution is likely."
    Extends over reasoning episodes.
    Lives HERE.

Level 3 is David Bessis's System 3 formalized:
    System 1 (fast/constructive) = ZFC — does this exist?
    System 2 (slow/structural)  = CAT — does this compose?
    System 3 (meta/intuitive)   = THIS — what pattern of agreement/disagreement
                                   should I expect, and what does it mean?

The delta history is itself a category:
    Objects:   (query, delta_type, resolution) triples
    Morphisms: structural similarity between episodes
    Functor:   known episodes → their resolutions

The Meta Kan Extension extends this functor to new queries:
    "Every time I've seen this shape of disagreement, the answer was X."

This is the system learning about its own reasoning.

Components:
1. Episode          — one reasoning event (query + both judgments + resolution)
2. EpisodeCategory  — the category of all episodes
3. Similarity       — morphisms between episodes (structural likeness)
4. MetaKan          — the Kan extension on the episode category
5. System3Oracle    — the prediction interface
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    Any, Callable, Dict, List, Optional,
    Set as PySet, Tuple,
)
from collections import defaultdict
import math


# ═══════════════════════════════════════════════════════════════════
# Delta Types (from proof_engine.py, repeated for independence)
# ═══════════════════════════════════════════════════════════════════

class DeltaType(Enum):
    """How CAT and ZFC relate on a given query."""
    AGREE = auto()      # both yes — high confidence
    ORPHAN = auto()     # ZFC yes, CAT no — exists but doesn't compose
    HOLLOW = auto()     # CAT yes, ZFC no — composes but doesn't exist
    REJECT = auto()     # both no — broken
    UNKNOWN = auto()    # not yet classified


class Resolution(Enum):
    """What turned out to be true after investigation."""
    CONFIRMED = auto()       # the prediction was correct
    REFUTED = auto()         # the prediction was wrong
    PARTIALLY_TRUE = auto()  # correct in some contexts
    REFRAMED = auto()        # question itself was wrong
    UNRESOLVED = auto()      # we don't know yet


# ═══════════════════════════════════════════════════════════════════
# Episode — one reasoning event
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Episode:
    """
    A single reasoning episode — one pass of the dual engine.

    Records what was asked, what each engine said, what the
    delta was, and (eventually) what the resolution was.

    This is an OBJECT in the episode category.
    """
    id: str

    # The query
    source: str
    target: str
    relation: str
    domain: str = ""  # e.g., "drug_repurposing", "physics", "protein_signaling"

    # Level 1: CAT judgment
    cat_says: bool = False
    cat_confidence: float = 0.0
    cat_strategy: str = ""        # which strategy produced this
    cat_path_count: int = 0       # how many paths CAT found
    cat_path_lengths: List[int] = field(default_factory=list)

    # Level 2: ZFC judgment
    zfc_says: bool = False
    zfc_confidence: float = 0.0
    zfc_method: str = ""          # entailment, composition, induction
    zfc_witness: Optional[str] = None
    zfc_rank_gap: int = 0         # well-ordering distance

    # The delta
    delta_type: DeltaType = DeltaType.UNKNOWN
    confidence_gap: float = 0.0   # |cat_conf - zfc_conf|

    # The resolution (filled in later, after human review or validation)
    resolution: Resolution = Resolution.UNRESOLVED
    resolution_notes: str = ""

    # Feature vector for similarity computation
    _features: Optional[List[float]] = field(default=None, repr=False)

    def __post_init__(self):
        # Classify delta
        if self.delta_type == DeltaType.UNKNOWN:
            if self.cat_says and self.zfc_says:
                self.delta_type = DeltaType.AGREE
            elif not self.cat_says and self.zfc_says:
                self.delta_type = DeltaType.ORPHAN
            elif self.cat_says and not self.zfc_says:
                self.delta_type = DeltaType.HOLLOW
            else:
                self.delta_type = DeltaType.REJECT

        self.confidence_gap = abs(self.cat_confidence - self.zfc_confidence)

    def features(self) -> List[float]:
        """
        Extract a numerical feature vector for this episode.

        Used for computing similarity between episodes.
        This is how we define morphisms in the episode category.
        """
        if self._features is not None:
            return self._features

        self._features = [
            # CAT features
            1.0 if self.cat_says else 0.0,
            self.cat_confidence,
            min(self.cat_path_count / 10.0, 1.0),
            min(min(self.cat_path_lengths) / 10.0, 1.0) if self.cat_path_lengths else 0.0,
            min(max(self.cat_path_lengths) / 10.0, 1.0) if self.cat_path_lengths else 0.0,

            # ZFC features
            1.0 if self.zfc_says else 0.0,
            self.zfc_confidence,
            min(self.zfc_rank_gap / 20.0, 1.0),

            # Delta features
            float(self.delta_type.value) / 4.0,
            self.confidence_gap,

            # Domain encoding (simple hash to [0,1])
            (hash(self.domain) % 1000) / 1000.0 if self.domain else 0.0,
        ]
        return self._features

    def __repr__(self):
        res = f" → {self.resolution.name}" if self.resolution != Resolution.UNRESOLVED else ""
        return f"Episode({self.id}: {self.source}→{self.target} [{self.delta_type.name}]{res})"


# ═══════════════════════════════════════════════════════════════════
# Similarity — morphisms between episodes
# ═══════════════════════════════════════════════════════════════════

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two feature vectors."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def episode_similarity(a: Episode, b: Episode) -> float:
    """
    Compute similarity between two episodes.

    This defines the MORPHISMS in the episode category.
    Two episodes are "close" if they have similar:
    - Delta types
    - Confidence profiles
    - Path structure
    - Domain

    Returns: similarity in [0, 1]. Higher = more similar.
    """
    fa = a.features()
    fb = b.features()

    # Base similarity from features
    sim = cosine_similarity(fa, fb)

    # Bonus for same delta type (the most important structural feature)
    if a.delta_type == b.delta_type:
        sim = min(1.0, sim + 0.2)

    # Bonus for same domain
    if a.domain and a.domain == b.domain:
        sim = min(1.0, sim + 0.1)

    return sim


# ═══════════════════════════════════════════════════════════════════
# EpisodeCategory — the category of reasoning episodes
# ═══════════════════════════════════════════════════════════════════

class EpisodeCategory:
    """
    The category of reasoning episodes.

    Objects: Episodes (past reasoning events)
    Morphisms: Similarity scores between episodes
    Composition: Transitive similarity (if A~B and B~C, then A~C)

    This is an ENRICHED category — morphisms carry a real-valued
    weight (similarity score) rather than just existing or not.

    Mirror of: categorical/category.py
    But at the meta-level — objects are reasoning events,
    not domain concepts.
    """

    def __init__(self, name: str = "EpisodeHistory"):
        self.name = name
        self.episodes: Dict[str, Episode] = {}
        self._resolved: Dict[str, Episode] = {}  # episodes with known resolutions

        # Indexes for fast lookup
        self._by_delta: Dict[DeltaType, List[str]] = defaultdict(list)
        self._by_domain: Dict[str, List[str]] = defaultdict(list)
        self._by_resolution: Dict[Resolution, List[str]] = defaultdict(list)

    def add(self, episode: Episode):
        """Add an episode to the category."""
        self.episodes[episode.id] = episode
        self._by_delta[episode.delta_type].append(episode.id)
        if episode.domain:
            self._by_domain[episode.domain].append(episode.id)
        if episode.resolution != Resolution.UNRESOLVED:
            self._resolved[episode.id] = episode
            self._by_resolution[episode.resolution].append(episode.id)

    def resolve(self, episode_id: str, resolution: Resolution,
                notes: str = ""):
        """Record the resolution of an episode."""
        ep = self.episodes.get(episode_id)
        if ep is None:
            return
        ep.resolution = resolution
        ep.resolution_notes = notes
        self._resolved[episode_id] = ep
        self._by_resolution[resolution].append(episode_id)

    def neighbors(self, episode: Episode, k: int = 5,
                  threshold: float = 0.5,
                  resolved_only: bool = True) -> List[Tuple[Episode, float]]:
        """
        Find the k most similar episodes.

        This is the comma category construction for the meta Kan extension:
        for a new episode e, find all known episodes that are "close" to e.

        Args:
            episode: the query episode
            k: max number of neighbors
            threshold: minimum similarity to include
            resolved_only: if True, only return episodes with known resolutions

        Returns:
            List of (episode, similarity) pairs, sorted by similarity descending
        """
        pool = self._resolved if resolved_only else self.episodes
        scored = []

        for eid, ep in pool.items():
            if ep.id == episode.id:
                continue
            sim = episode_similarity(episode, ep)
            if sim >= threshold:
                scored.append((ep, sim))

        scored.sort(key=lambda x: -x[1])
        return scored[:k]

    def delta_distribution(self) -> Dict[DeltaType, int]:
        """Count episodes by delta type."""
        return {dt: len(ids) for dt, ids in self._by_delta.items()}

    def resolution_distribution(self) -> Dict[Resolution, int]:
        """Count resolved episodes by resolution type."""
        return {r: len(ids) for r, ids in self._by_resolution.items()}

    def __repr__(self):
        return (f"EpisodeCategory({self.name}, "
                f"|episodes|={len(self.episodes)}, "
                f"|resolved|={len(self._resolved)})")


# ═══════════════════════════════════════════════════════════════════
# MetaKan — Kan extension on the episode category
# ═══════════════════════════════════════════════════════════════════

@dataclass
class MetaPrediction:
    """
    Prediction from the meta Kan extension.

    For a new query, predicts:
    - What delta type to expect
    - What resolution is likely
    - Confidence in the prediction
    - Which past episodes informed it
    """
    predicted_delta: DeltaType
    delta_confidence: float
    predicted_resolution: Resolution
    resolution_confidence: float
    contributing_episodes: List[Tuple[str, float]]  # (episode_id, similarity)
    explanation: str
    should_run_both: bool  # whether to bother running both engines


class MetaKanExtension:
    """
    The Meta Kan Extension — System 3.

    Given:
    - F: EpisodeCategory → Resolutions (known episode → resolution mapping)
    - K: EpisodeCategory → FeatureSpace (episode → feature vector embedding)

    For a new episode e, compute:
    Lan_K(F)(e) = colimit over {similar resolved episodes}

    The colimit is a weighted vote: each similar past episode
    votes for its resolution, weighted by similarity.

    This IS trained intuition:
    "Every time I've seen this pattern of disagreement, the answer was X."

    Mirror of: categorical/kan_extensions.py:LeftKanExtension
    But at the meta-level — extending over reasoning history,
    not over knowledge graphs.
    """

    def __init__(self, history: EpisodeCategory):
        self.history = history
        self._cache: Dict[str, MetaPrediction] = {}

    def predict(self, episode: Episode,
                k: int = 10,
                threshold: float = 0.3) -> MetaPrediction:
        """
        Predict delta type and resolution for a new episode.

        This is Lan_K(F)(e):
        1. Build the comma category: find similar resolved episodes
        2. Collect their resolutions (the F values)
        3. Compute the colimit: weighted vote

        Args:
            episode: the new episode to predict for
            k: number of neighbors to consider
            threshold: minimum similarity

        Returns:
            MetaPrediction with predicted delta, resolution, and confidence
        """
        if episode.id in self._cache:
            return self._cache[episode.id]

        # Step 1: Comma category — find similar resolved episodes
        neighbors = self.history.neighbors(
            episode, k=k, threshold=threshold, resolved_only=True
        )

        if not neighbors:
            # No similar resolved episodes — we're in unknown territory
            prediction = MetaPrediction(
                predicted_delta=DeltaType.UNKNOWN,
                delta_confidence=0.0,
                predicted_resolution=Resolution.UNRESOLVED,
                resolution_confidence=0.0,
                contributing_episodes=[],
                explanation="No similar resolved episodes found. Novel territory.",
                should_run_both=True,  # definitely need both engines
            )
            self._cache[episode.id] = prediction
            return prediction

        # Step 2: Collect F values (resolutions) with weights
        delta_votes: Dict[DeltaType, float] = defaultdict(float)
        resolution_votes: Dict[Resolution, float] = defaultdict(float)
        contributors = []

        for ep, sim in neighbors:
            delta_votes[ep.delta_type] += sim
            resolution_votes[ep.resolution] += sim
            contributors.append((ep.id, sim))

        # Step 3: Colimit — weighted majority vote
        total_delta_weight = sum(delta_votes.values())
        total_res_weight = sum(resolution_votes.values())

        predicted_delta = max(delta_votes, key=delta_votes.get)
        delta_conf = delta_votes[predicted_delta] / total_delta_weight if total_delta_weight > 0 else 0.0

        predicted_resolution = max(resolution_votes, key=resolution_votes.get)
        res_conf = resolution_votes[predicted_resolution] / total_res_weight if total_res_weight > 0 else 0.0

        # Should we bother running both engines?
        # If we're very confident about the delta type, and it's AGREE or REJECT,
        # we might not need the second engine.
        should_run_both = True
        if delta_conf > 0.8:
            if predicted_delta == DeltaType.AGREE:
                should_run_both = False  # CAT alone is probably enough
            elif predicted_delta == DeltaType.REJECT:
                should_run_both = False  # don't waste compute

        # Explanation
        explanation = self._explain(
            predicted_delta, delta_conf,
            predicted_resolution, res_conf,
            neighbors, delta_votes, resolution_votes,
        )

        prediction = MetaPrediction(
            predicted_delta=predicted_delta,
            delta_confidence=delta_conf,
            predicted_resolution=predicted_resolution,
            resolution_confidence=res_conf,
            contributing_episodes=contributors,
            explanation=explanation,
            should_run_both=should_run_both,
        )

        self._cache[episode.id] = prediction
        return prediction

    def predict_from_query(self, source: str, target: str,
                           relation: str, domain: str = "",
                           cat_conf: float = 0.0,
                           zfc_conf: float = 0.0) -> MetaPrediction:
        """
        Convenience: predict from raw query parameters.

        Can be called BEFORE running the engines (with conf=0)
        to decide whether to run both, or AFTER running one engine
        to decide whether to run the other.
        """
        ep = Episode(
            id=f"query_{source}_{target}_{relation}",
            source=source,
            target=target,
            relation=relation,
            domain=domain,
            cat_says=cat_conf >= 0.4,
            cat_confidence=cat_conf,
            zfc_says=zfc_conf >= 0.4,
            zfc_confidence=zfc_conf,
        )
        return self.predict(ep)

    def _explain(self, predicted_delta, delta_conf,
                 predicted_resolution, res_conf,
                 neighbors, delta_votes, resolution_votes) -> str:
        """Generate human-readable explanation."""
        lines = []
        lines.append(f"Meta Kan Extension (System 3)")
        lines.append(f"  Based on {len(neighbors)} similar resolved episodes")
        lines.append(f"")
        lines.append(f"  Predicted delta: {predicted_delta.name} "
                     f"(confidence: {delta_conf:.2f})")

        # Show vote distribution
        total = sum(delta_votes.values())
        if total > 0:
            for dt, weight in sorted(delta_votes.items(),
                                     key=lambda x: -x[1]):
                pct = weight / total * 100
                lines.append(f"    {dt.name}: {pct:.0f}%")

        lines.append(f"")
        lines.append(f"  Predicted resolution: {predicted_resolution.name} "
                     f"(confidence: {res_conf:.2f})")

        total_r = sum(resolution_votes.values())
        if total_r > 0:
            for r, weight in sorted(resolution_votes.items(),
                                    key=lambda x: -x[1]):
                pct = weight / total_r * 100
                lines.append(f"    {r.name}: {pct:.0f}%")

        lines.append(f"")
        lines.append(f"  Top similar episodes:")
        for ep, sim in neighbors[:5]:
            lines.append(f"    {ep.id}: {ep.delta_type.name} → "
                        f"{ep.resolution.name} (sim={sim:.2f})")

        return "\n".join(lines)

    def accuracy(self) -> Dict[str, float]:
        """
        Compute accuracy of the meta-predictor using leave-one-out.

        For each resolved episode, predict using all OTHERS,
        check if prediction matches actual.
        """
        resolved = list(self.history._resolved.values())
        if len(resolved) < 3:
            return {"delta_accuracy": 0.0, "resolution_accuracy": 0.0,
                    "sample_size": len(resolved)}

        delta_correct = 0
        res_correct = 0

        for ep in resolved:
            # Temporarily remove this episode
            temp_history = EpisodeCategory("temp")
            for other in resolved:
                if other.id != ep.id:
                    temp_history.add(other)

            temp_kan = MetaKanExtension(temp_history)
            pred = temp_kan.predict(ep)

            if pred.predicted_delta == ep.delta_type:
                delta_correct += 1
            if pred.predicted_resolution == ep.resolution:
                res_correct += 1

        n = len(resolved)
        return {
            "delta_accuracy": delta_correct / n,
            "resolution_accuracy": res_correct / n,
            "sample_size": n,
        }


# ═══════════════════════════════════════════════════════════════════
# System3Oracle — the full interface
# ═══════════════════════════════════════════════════════════════════

class System3Oracle:
    """
    The System 3 Oracle — trained mathematical intuition.

    Wraps the meta Kan extension with:
    - Episode recording (learning from experience)
    - Prediction (what delta to expect)
    - Routing (should we run one engine or both?)
    - Self-assessment (how accurate is our intuition?)

    This is Bessis's System 3:
    "A process of consciously training mathematical intuition
     so that it works more effectively."

    The oracle gets better as you use it. Each resolved episode
    improves future predictions. The system learns about its
    own reasoning patterns.
    """

    def __init__(self, name: str = "System3"):
        self.name = name
        self.history = EpisodeCategory(name)
        self.kan = MetaKanExtension(self.history)

    def record(self, episode: Episode):
        """Record a new episode (from running the dual engine)."""
        self.history.add(episode)
        # Invalidate cache since history changed
        self.kan._cache.clear()

    def resolve(self, episode_id: str, resolution: Resolution,
                notes: str = ""):
        """Record what actually happened."""
        self.history.resolve(episode_id, resolution, notes)
        self.kan._cache.clear()

    def predict(self, source: str, target: str, relation: str,
                domain: str = "",
                cat_conf: float = 0.0,
                zfc_conf: float = 0.0) -> MetaPrediction:
        """
        Before running the engines: what should we expect?

        Can be called with no confidence values (before either engine runs)
        to decide whether to run both, or with one engine's results
        to decide whether to run the other.
        """
        return self.kan.predict_from_query(
            source, target, relation, domain, cat_conf, zfc_conf
        )

    def should_run_both(self, source: str, target: str, relation: str,
                        domain: str = "") -> Tuple[bool, str]:
        """
        Quick check: should we bother running both engines?

        Returns (should_run_both, reason).

        If System 3 is confident about the delta type:
        - AGREE with high confidence → CAT alone is enough
        - REJECT with high confidence → don't waste compute
        - ORPHAN or HOLLOW → definitely run both (that's the interesting case)
        """
        pred = self.predict(source, target, relation, domain)

        if pred.delta_confidence < 0.5:
            return (True, "Low confidence — need both engines")

        if pred.predicted_delta == DeltaType.AGREE and pred.delta_confidence > 0.8:
            return (False, f"System 3 predicts AGREE ({pred.delta_confidence:.0%}). "
                          f"CAT alone is likely sufficient.")

        if pred.predicted_delta == DeltaType.REJECT and pred.delta_confidence > 0.8:
            return (False, f"System 3 predicts REJECT ({pred.delta_confidence:.0%}). "
                          f"Save compute.")

        if pred.predicted_delta in (DeltaType.ORPHAN, DeltaType.HOLLOW):
            return (True, f"System 3 predicts {pred.predicted_delta.name} "
                         f"({pred.delta_confidence:.0%}). "
                         f"This is the interesting case — run both.")

        return (True, "Uncertain — run both to be safe")

    def report(self) -> str:
        """Generate a report on System 3's performance."""
        lines = []
        lines.append(f"System 3 Report: {self.name}")
        lines.append(f"═" * 50)

        lines.append(f"")
        lines.append(f"Episodes: {len(self.history.episodes)}")
        lines.append(f"Resolved: {len(self.history._resolved)}")

        lines.append(f"")
        lines.append(f"Delta distribution:")
        for dt, count in sorted(self.history.delta_distribution().items(),
                                key=lambda x: -x[1]):
            pct = count / max(len(self.history.episodes), 1) * 100
            lines.append(f"  {dt.name}: {count} ({pct:.0f}%)")

        lines.append(f"")
        lines.append(f"Resolution distribution:")
        for r, count in sorted(self.history.resolution_distribution().items(),
                               key=lambda x: -x[1]):
            pct = count / max(len(self.history._resolved), 1) * 100
            lines.append(f"  {r.name}: {count} ({pct:.0f}%)")

        # Accuracy
        if len(self.history._resolved) >= 3:
            acc = self.kan.accuracy()
            lines.append(f"")
            lines.append(f"Leave-one-out accuracy (n={acc['sample_size']}):")
            lines.append(f"  Delta prediction:      {acc['delta_accuracy']:.0%}")
            lines.append(f"  Resolution prediction: {acc['resolution_accuracy']:.0%}")

        # Pattern insights
        lines.append(f"")
        lines.append(self._pattern_insights())

        return "\n".join(lines)

    def _pattern_insights(self) -> str:
        """Discover patterns in the episode history."""
        lines = ["Pattern insights:"]

        # Resolution rates by delta type
        delta_to_res: Dict[DeltaType, Dict[Resolution, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        for ep in self.history._resolved.values():
            delta_to_res[ep.delta_type][ep.resolution] += 1

        for dt in [DeltaType.AGREE, DeltaType.ORPHAN,
                   DeltaType.HOLLOW, DeltaType.REJECT]:
            if dt in delta_to_res:
                total = sum(delta_to_res[dt].values())
                lines.append(f"")
                lines.append(f"  {dt.name} episodes ({total} total):")
                for r, count in sorted(delta_to_res[dt].items(),
                                       key=lambda x: -x[1]):
                    pct = count / total * 100
                    lines.append(f"    → {r.name}: {count} ({pct:.0f}%)")

                # Key insight for each delta type
                if dt == DeltaType.ORPHAN:
                    confirmed = delta_to_res[dt].get(Resolution.CONFIRMED, 0)
                    if total > 0:
                        rate = confirmed / total
                        lines.append(f"    Insight: {rate:.0%} of ORPHANs turn out to be real")
                        lines.append(f"    (ZFC was right, CAT missed the connection)")

                elif dt == DeltaType.HOLLOW:
                    confirmed = delta_to_res[dt].get(Resolution.CONFIRMED, 0)
                    if total > 0:
                        rate = confirmed / total
                        lines.append(f"    Insight: {rate:.0%} of HOLLOWs turn out to be real")
                        lines.append(f"    (CAT was right, ZFC missed the construction)")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Example: drug repurposing scenario
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    oracle = System3Oracle("DrugRepurposing")

    # Simulate a history of past reasoning episodes
    past_episodes = [
        # AGREE cases — both engines said yes, most were confirmed
        Episode("ep01", "Aspirin", "COX2", "inhibits", "pharma",
                cat_says=True, cat_confidence=0.9, cat_path_count=3,
                zfc_says=True, zfc_confidence=0.85, zfc_rank_gap=1),
        Episode("ep02", "Ibuprofen", "COX2", "inhibits", "pharma",
                cat_says=True, cat_confidence=0.85, cat_path_count=2,
                zfc_says=True, zfc_confidence=0.8, zfc_rank_gap=1),
        Episode("ep03", "Metformin", "AMPK", "activates", "pharma",
                cat_says=True, cat_confidence=0.8, cat_path_count=2,
                zfc_says=True, zfc_confidence=0.75, zfc_rank_gap=2),

        # ORPHAN cases — ZFC said yes, CAT said no
        Episode("ep04", "Celecoxib", "Inflammation", "treats", "pharma",
                cat_says=False, cat_confidence=0.3, cat_path_count=0,
                zfc_says=True, zfc_confidence=0.7, zfc_rank_gap=3),
        Episode("ep05", "Metformin", "Cancer", "treats", "pharma",
                cat_says=False, cat_confidence=0.2, cat_path_count=0,
                zfc_says=True, zfc_confidence=0.6, zfc_rank_gap=5),

        # HOLLOW cases — CAT said yes, ZFC said no
        Episode("ep06", "DrugX", "ProteinY", "inhibits", "pharma",
                cat_says=True, cat_confidence=0.7, cat_path_count=2,
                cat_path_lengths=[2, 3],
                zfc_says=False, zfc_confidence=0.1, zfc_rank_gap=8),
        Episode("ep07", "DrugY", "DiseaseZ", "treats", "pharma",
                cat_says=True, cat_confidence=0.6, cat_path_count=1,
                cat_path_lengths=[4],
                zfc_says=False, zfc_confidence=0.15, zfc_rank_gap=7),

        # REJECT cases — both said no
        Episode("ep08", "Water", "Cancer", "treats", "pharma",
                cat_says=False, cat_confidence=0.05,
                zfc_says=False, zfc_confidence=0.02, zfc_rank_gap=15),
    ]

    # Add episodes and resolve them
    for ep in past_episodes:
        oracle.record(ep)

    # Resolve with outcomes
    oracle.resolve("ep01", Resolution.CONFIRMED, "Known inhibitor")
    oracle.resolve("ep02", Resolution.CONFIRMED, "Known inhibitor")
    oracle.resolve("ep03", Resolution.CONFIRMED, "Known activator")
    oracle.resolve("ep04", Resolution.CONFIRMED, "Validated in trial — COX2 pathway")
    oracle.resolve("ep05", Resolution.PARTIALLY_TRUE, "Some evidence for anti-cancer effect")
    oracle.resolve("ep06", Resolution.REFUTED, "No binding affinity found")
    oracle.resolve("ep07", Resolution.REFRAMED, "Mechanism was indirect, not direct")
    oracle.resolve("ep08", Resolution.REFUTED, "No mechanism")

    # Print report
    print(oracle.report())
    print()

    # Now predict for a new query
    print("=" * 50)
    print("NEW QUERY: Thalidomide → TNF-alpha (inhibits)?")
    print("=" * 50)

    # Before running engines — should we bother with both?
    should, reason = oracle.should_run_both(
        "Thalidomide", "TNF_alpha", "inhibits", "pharma"
    )
    print(f"Run both engines? {should}")
    print(f"Reason: {reason}")
    print()

    # After running CAT (which says yes with moderate confidence)
    pred = oracle.predict(
        "Thalidomide", "TNF_alpha", "inhibits", "pharma",
        cat_conf=0.65, zfc_conf=0.0,
    )
    print("After CAT only (conf=0.65):")
    print(pred.explanation)
    print()

    # After running ZFC too (which says no)
    pred2 = oracle.predict(
        "Thalidomide", "TNF_alpha", "inhibits", "pharma",
        cat_conf=0.65, zfc_conf=0.15,
    )
    print("After both engines (CAT=0.65, ZFC=0.15):")
    print(pred2.explanation)
    print(f"\nPredicted delta: {pred2.predicted_delta.name}")
    print(f"Predicted resolution: {pred2.predicted_resolution.name}")
    print(f"Should run both: {pred2.should_run_both}")
