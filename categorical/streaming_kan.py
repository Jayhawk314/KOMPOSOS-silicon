# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>
"""
Streaming Kan Extensions via Comma Categories

The left Kan extension: Lan_K(F)(e) = colim_{(K downarrow e)} F

Key insight for streaming: When a new event arrives (new object in the comma
category), we don't recompute the entire colimit. We compute the pushout
of the existing colimit with the new contribution -- O(1) per event.

Mathematical basis:
  - Milewski, "Pointwise Kan Extensions"
  - Perrone & Tholen, "Kan Extensions are Partial Colimits" (2022)
  - Shiebler, "Kan Extensions in Data Science" (2022)
"""

import math
import time
from typing import List, Dict, Tuple, Optional, Set, TYPE_CHECKING
from dataclasses import dataclass, field
from collections import defaultdict

if TYPE_CHECKING:
    pass  # Domain-specific databases injected at runtime


@dataclass
class CommaObject:
    """Object in comma category (K downarrow e): pair (c, f: K(c) -> e)"""
    source_object: str       # c in C (observed technique)
    morphism_to_target: str  # f: K(c) -> e (the composition path)
    target: str              # e (prediction target)
    timestamp: float         # When observed
    weight: float            # Stealth weight from enriched category


class StreamingCommaCategory:
    """
    Incrementally maintained comma category for real-time Kan extensions.

    As new events arrive:
    1. Map event to MITRE technique
    2. Find morphisms to prediction targets (composable successors)
    3. Add to comma category
    4. Incrementally update colimit (O(1) per event)

    The colimit is the prediction: weighted sum of contributions.
    Temporal decay ensures older observations contribute less.
    """

    def __init__(self, decay_rate: float = 0.001):
        self.objects: List[CommaObject] = []
        self.colimit_cache: Dict[str, float] = {}  # target -> prediction score
        self.decay_rate = decay_rate
        self.observation_count: int = 0
        # Index: target -> list of indices into self.objects
        self._target_index: Dict[str, List[int]] = defaultdict(list)

    def add_observation(self, technique_id: str, timestamp: float,
                        composable_targets: List[Tuple[str, float]]) -> Dict[str, float]:
        """
        New event observed. Update comma category incrementally.

        For each composable target, creates a CommaObject representing the
        morphism from the observed technique to the prediction target in the
        comma category (K downarrow e). Then updates the colimit cache
        incrementally.

        Args:
            technique_id: The observed MITRE technique ID.
            timestamp: Event timestamp (seconds since epoch).
            composable_targets: List of (target_technique_id, stealth_weight)
                tuples from MITREDatabase.get_composable_successors().

        Returns:
            Dictionary of updated prediction scores (only changed targets).
        """
        new_objects: List[CommaObject] = []

        for target_id, weight in composable_targets:
            # Skip self-loops: predicting what already happened is not useful
            if target_id == technique_id:
                continue

            morphism_label = f"{technique_id}->{target_id}"
            obj = CommaObject(
                source_object=technique_id,
                morphism_to_target=morphism_label,
                target=target_id,
                timestamp=timestamp,
                weight=weight,
            )
            idx = len(self.objects)
            self.objects.append(obj)
            self._target_index[target_id].append(idx)
            new_objects.append(obj)

        self.observation_count += 1

        # Incremental colimit update: O(len(new_objects)) not O(len(all objects))
        updated = self._update_colimit_incremental(new_objects, timestamp)
        return updated

    def _update_colimit_incremental(self, new_objects: List[CommaObject],
                                    current_time: float) -> Dict[str, float]:
        """
        Update colimit without full recomputation.

        For each new comma object, the contribution to the colimit for its
        target is:
            contribution = weight * exp(-decay_rate * age)

        Since the object was just created, age is approximately 0, so the
        contribution is approximately equal to weight. We add this directly
        to the cached colimit value.

        Returns:
            Dictionary mapping target -> updated total score.
        """
        updated: Dict[str, float] = {}

        for obj in new_objects:
            age = max(0.0, current_time - obj.timestamp)
            contribution = obj.weight * math.exp(-self.decay_rate * age)

            if obj.target in self.colimit_cache:
                self.colimit_cache[obj.target] += contribution
            else:
                self.colimit_cache[obj.target] = contribution

            updated[obj.target] = self.colimit_cache[obj.target]

        return updated

    def get_predictions(self, top_k: int = 5,
                        current_time: float = None) -> List[Tuple[str, float]]:
        """
        Get current top-k predictions with temporal decay applied.

        Uses the incrementally maintained colimit_cache for O(|targets|)
        performance instead of O(|all objects|). Full recomputation is
        triggered periodically (every 100 observations) to correct for
        accumulated decay drift.

        Args:
            top_k: Number of top predictions to return.
            current_time: Reference time for decay. Defaults to now.

        Returns:
            List of (target_technique_id, score) sorted by score descending.
        """
        if current_time is None:
            current_time = time.time()

        # Full recomputation every 100 observations to correct decay drift
        if self.observation_count % 100 == 0 and self.objects:
            scores: Dict[str, float] = defaultdict(float)
            for obj in self.objects:
                age = max(0.0, current_time - obj.timestamp)
                decayed_weight = obj.weight * math.exp(-self.decay_rate * age)
                scores[obj.target] += decayed_weight
            self.colimit_cache = dict(scores)

        # Sort cached scores — O(|unique targets|) not O(|all objects|)
        sorted_predictions = sorted(
            self.colimit_cache.items(), key=lambda x: x[1], reverse=True
        )
        return sorted_predictions[:top_k]

    def get_confidence(self, target: str) -> float:
        """
        Confidence for a specific prediction target.

        Confidence is based on the number of independent source observations
        that support this target. It saturates via an exponential curve so
        that many independent sources converge toward confidence = 1.0.

        Formula: confidence = 1 - exp(-0.5 * n_contributors)

        This means:
            1 source  -> ~0.39
            2 sources -> ~0.63
            3 sources -> ~0.78
            5 sources -> ~0.92
            10 sources -> ~0.99

        Args:
            target: The technique ID to check confidence for.

        Returns:
            Confidence score in [0, 1].
        """
        if target not in self._target_index:
            return 0.0

        # Count distinct source techniques that contribute to this target
        source_techniques: Set[str] = set()
        for idx in self._target_index[target]:
            if idx < len(self.objects):
                source_techniques.add(self.objects[idx].source_object)

        n_contributors = len(source_techniques)
        if n_contributors == 0:
            return 0.0

        confidence = 1.0 - math.exp(-0.5 * n_contributors)
        return confidence

    def prune_old(self, max_age_seconds: float = 3600):
        """
        Remove observations older than max_age to save memory.

        Rebuilds the object list and target index, discarding any
        CommaObject whose timestamp is older than the cutoff.

        Args:
            max_age_seconds: Maximum age in seconds. Objects older than
                this are removed. Defaults to 3600 (1 hour).
        """
        cutoff = time.time() - max_age_seconds
        surviving: List[CommaObject] = []
        new_target_index: Dict[str, List[int]] = defaultdict(list)

        for obj in self.objects:
            if obj.timestamp >= cutoff:
                idx = len(surviving)
                surviving.append(obj)
                new_target_index[obj.target].append(idx)

        self.objects = surviving
        self._target_index = new_target_index

        # Rebuild colimit cache from surviving objects
        current_time = time.time()
        self.colimit_cache.clear()
        for obj in self.objects:
            age = max(0.0, current_time - obj.timestamp)
            contribution = obj.weight * math.exp(-self.decay_rate * age)
            if obj.target in self.colimit_cache:
                self.colimit_cache[obj.target] += contribution
            else:
                self.colimit_cache[obj.target] = contribution

    def get_contributor_count(self, target: str) -> int:
        """
        Get the number of distinct source techniques contributing to a target.

        Args:
            target: The prediction target technique ID.

        Returns:
            Number of distinct contributing source techniques.
        """
        if target not in self._target_index:
            return 0
        source_techniques: Set[str] = set()
        for idx in self._target_index[target]:
            if idx < len(self.objects):
                source_techniques.add(self.objects[idx].source_object)
        return len(source_techniques)

    def get_supporting_evidence(self, target: str) -> List[str]:
        """
        Get the list of source techniques that support a prediction target.

        Args:
            target: The prediction target technique ID.

        Returns:
            Sorted list of distinct source technique IDs.
        """
        if target not in self._target_index:
            return []
        source_techniques: Set[str] = set()
        for idx in self._target_index[target]:
            if idx < len(self.objects):
                source_techniques.add(self.objects[idx].source_object)
        return sorted(source_techniques)


class StreamingKanExtension:
    """
    Left Kan extension computed incrementally from streaming events.

    Lan_K(F)(e) = colim_{(K downarrow e)} F

    Where:
    - K: ObservedEvents -> MITRECategory (maps events to techniques)
    - F: ObservedEvents -> StealthScores (maps events to stealth values)
    - e: candidate prediction target

    The colimit over the comma category (K downarrow e) aggregates all
    observations that have morphisms pointing toward e, weighted by stealth
    and decayed over time. This provides a real-time, mathematically grounded
    prediction of likely next attack steps.
    """

    def __init__(self, decay_rate: float = 0.001):
        self.comma_cat = StreamingCommaCategory(decay_rate=decay_rate)
        self.event_history: List[Tuple[str, float]] = []  # (technique, timestamp)

    def observe(self, technique_id: str, timestamp: float,
                composable_targets: List[Tuple[str, float]]) -> Dict[str, float]:
        """
        Process new observation. Returns updated prediction map.

        This is the core streaming operation. When a new event arrives:
        1. Record in event history
        2. Add to comma category (creates CommaObjects for each target)
        3. Incrementally update colimit predictions

        Performance target: < 10ms per event.

        Args:
            technique_id: The observed MITRE technique ID.
            timestamp: Event timestamp (seconds since epoch).
            composable_targets: List of (target_id, weight) from
                MITREDatabase.get_composable_successors().

        Returns:
            Dictionary of updated prediction scores (changed targets only).
        """
        self.event_history.append((technique_id, timestamp))
        updated = self.comma_cat.add_observation(
            technique_id, timestamp, composable_targets
        )
        return updated

    def predict(self, top_k: int = 5) -> List[Dict]:
        """
        Get current top predictions with confidence and stealth metadata.

        Returns a list of prediction dictionaries containing:
        - technique: the predicted technique ID
        - score: the Kan extension colimit score (higher = more likely)
        - confidence: saturation confidence from independent sources
        - n_contributors: number of distinct source observations
        - supporting_evidence: list of source technique IDs

        Args:
            top_k: Number of top predictions to return.

        Returns:
            List of prediction dictionaries sorted by score descending.
        """
        current_time = time.time()
        if self.event_history:
            # Use the latest event timestamp if it is ahead of wall clock
            # (can happen when replaying historical events)
            current_time = max(current_time, self.event_history[-1][1])

        raw_predictions = self.comma_cat.get_predictions(top_k, current_time)

        results = []
        for target, score in raw_predictions:
            confidence = self.comma_cat.get_confidence(target)
            n_contributors = self.comma_cat.get_contributor_count(target)
            evidence = self.comma_cat.get_supporting_evidence(target)

            results.append({
                "technique": target,
                "score": round(score, 6),
                "confidence": round(confidence, 4),
                "n_contributors": n_contributors,
                "supporting_evidence": evidence,
            })

        return results

    def multi_step_forecast(self, steps: int = 3,
                            composable_fn=None) -> List[List[Dict]]:
        """
        Multi-step forecast using iterated Kan extension.

        Predict step N+1 from current observations. Then, treat the top
        prediction as a hypothetical observation and predict step N+2.
        Repeat for the requested number of steps.

        Confidence decreases geometrically at each forecast step because
        each subsequent prediction is conditioned on the previous one
        being correct.

        Args:
            steps: Number of forecast steps (default 3).
            composable_fn: A callable that takes a technique_id and returns
                List[Tuple[str, float]] of composable successors. If None,
                the forecast uses only the current comma category state for
                the first step and cannot extend further.

        Returns:
            List of lists, where forecast[i] is the list of prediction dicts
            for step i+1. Each prediction dict includes a 'step' field and
            adjusted confidence.
        """
        forecast: List[List[Dict]] = []
        confidence_decay = 0.7  # Each step reduces confidence by this factor

        # Track hypothetical additions so we can roll them back afterward
        hypothetical_markers: List[Tuple[str, float]] = []

        for step in range(steps):
            step_num = step + 1

            if step == 0:
                # First step: use real predictions from current observations
                preds = self.predict(top_k=5)
            else:
                # Subsequent steps: use top prediction from previous step as
                # a hypothetical observation, then predict from the extended
                # comma category
                if not forecast[step - 1]:
                    break  # No predictions available to extend from

                top_prev = forecast[step - 1][0]
                top_technique = top_prev["technique"]

                if composable_fn is not None:
                    # Get composable targets for the hypothetical technique
                    targets = composable_fn(top_technique)
                    # Use a future timestamp to distinguish hypothetical
                    # observations from real ones during rollback
                    hypothetical_time = time.time() + 1000000.0 + step
                    hypothetical_markers.append(
                        (top_technique, hypothetical_time)
                    )
                    # Temporarily inject into the comma category
                    self.comma_cat.add_observation(
                        top_technique, hypothetical_time, targets
                    )
                    self.event_history.append(
                        (top_technique, hypothetical_time)
                    )
                    preds = self.predict(top_k=5)
                else:
                    # Without composable_fn, we cannot extend predictions
                    # beyond the first step
                    break

            # Apply geometric confidence decay for forecast horizon
            step_preds = []
            for pred in preds:
                adjusted = dict(pred)
                adjusted["step"] = step_num
                adjusted["confidence"] = round(
                    pred["confidence"] * (confidence_decay ** step), 4
                )
                step_preds.append(adjusted)

            forecast.append(step_preds)

        # Roll back all hypothetical observations to restore original state
        if hypothetical_markers:
            hypo_set = set(hypothetical_markers)
            surviving: List[CommaObject] = []
            new_index: Dict[str, List[int]] = defaultdict(list)
            for obj in self.comma_cat.objects:
                if (obj.source_object, obj.timestamp) in hypo_set:
                    continue  # Discard hypothetical objects
                idx = len(surviving)
                surviving.append(obj)
                new_index[obj.target].append(idx)
            self.comma_cat.objects = surviving
            self.comma_cat._target_index = new_index

            # Rebuild the colimit cache from surviving (real) objects
            current_time = time.time()
            self.comma_cat.colimit_cache.clear()
            for obj in self.comma_cat.objects:
                age = max(0.0, current_time - obj.timestamp)
                contribution = obj.weight * math.exp(
                    -self.comma_cat.decay_rate * age
                )
                if obj.target in self.comma_cat.colimit_cache:
                    self.comma_cat.colimit_cache[obj.target] += contribution
                else:
                    self.comma_cat.colimit_cache[obj.target] = contribution

            # Remove hypothetical entries from event_history
            self.event_history = [
                (t, ts) for t, ts in self.event_history
                if (t, ts) not in hypo_set
            ]

        return forecast

    def get_event_count(self) -> int:
        """Return the number of events observed so far."""
        return len(self.event_history)

    def get_comma_category_size(self) -> int:
        """Return the number of objects in the comma category."""
        return len(self.comma_cat.objects)

    def prune(self, max_age_seconds: float = 3600):
        """
        Prune old observations from the comma category.

        Also removes corresponding entries from event_history.

        Args:
            max_age_seconds: Maximum age before pruning. Defaults to 1 hour.
        """
        cutoff = time.time() - max_age_seconds
        self.event_history = [
            (t, ts) for t, ts in self.event_history if ts >= cutoff
        ]
        self.comma_cat.prune_old(max_age_seconds)


class RightKanExtension:
    """
    Right Kan extension: Ran_K(F)(e) = lim_{(e downarrow K)} F

    While the left Kan extension (StreamingKanExtension) computes colimits
    over OBSERVED events — reactive, needs data — the right Kan extension
    computes limits over the STRUCTURE of the category — proactive, needs
    no observations.

    For each object e, the right Kan asks: "How many composition paths
    in the enriched category converge toward e?" This is the structural
    score — a prior probability that e will appear, computed purely from
    the graph topology.

    The left and right Kan together solve the first-move problem:
      - Right Kan provides non-zero structural priors (before any event)
      - Left Kan updates with evidence as real observations arrive
      - Priors ensure the system never starts from zero

    Mathematical basis:
      - Mac Lane, "Categories for the Working Mathematician", Ch. X
      - Loregian, "(Co)end Calculus" (2021)
      - Riehl, "Category Theory in Context", §6.2
    """

    def __init__(self,
                 objects: List[str],
                 compositions: List[Tuple[str, str]],
                 entry_objects: Optional[Set[str]] = None,
                 weight_fn: Optional[object] = None,
                 successor_fn: Optional[object] = None):
        """
        Initialize with graph structure.

        Args:
            objects: List of object IDs in the category.
            compositions: List of (source, target) valid composition pairs.
            entry_objects: Set of objects that are natural entry points
                          (get a prior bonus). If None, no bonus applied.
            weight_fn: Callable(src, tgt) -> float returning composition
                       weight. If None, uses uniform weight of 0.5.
            successor_fn: Callable(obj) -> List[(successor_id, weight)]
                          returning composable successors with weights.
                          Used by get_priors_for_seeding. If None, seeding
                          uses structural scores directly.
        """
        self._objects = set(objects)
        self._weight_fn = weight_fn
        self._successor_fn = successor_fn
        self._entry_objects: Set[str] = entry_objects or set()

        self._structural_scores: Dict[str, float] = {}
        self._predecessor_map: Dict[str, Set[str]] = defaultdict(set)

        # Build predecessor map from compositions
        for (src, tgt) in compositions:
            self._predecessor_map[tgt].add(src)

        self._compute_structural_priors()

    def _compute_structural_priors(self):
        """
        Compute structural score for every object.

        For each object t:
          score(t) = (sum_{predecessors p} weight(p -> t)) / sqrt(N)

        where N = total objects. The sqrt normalization ensures scores
        stay in [0, 1] while differentiating high-connectivity objects.

        Entry objects get a bonus because they are natural first moves.
        """
        n_objects = len(self._objects)
        norm = max(1.0, math.sqrt(n_objects))

        for obj_id in self._objects:
            predecessors = self._predecessor_map.get(obj_id, set())
            if not predecessors:
                self._structural_scores[obj_id] = 0.0
                continue

            total = 0.0
            for pred in predecessors:
                if self._weight_fn is not None:
                    w = self._weight_fn(pred, obj_id)
                else:
                    w = 0.5
                total += w

            score = min(1.0, total / norm)

            if obj_id in self._entry_objects:
                score = min(1.0, score + 0.1)

            self._structural_scores[obj_id] = score

    def predict(self, top_k: int = 10) -> List[Dict]:
        """
        Structural predictions — no observations needed.

        Returns objects ranked by structural score: how many
        weighted composition paths converge on each object.
        """
        sorted_objs = sorted(
            self._structural_scores.items(),
            key=lambda x: x[1], reverse=True
        )[:top_k]

        results = []
        for obj_id, score in sorted_objs:
            results.append({
                "object": obj_id,
                "structural_score": round(score, 6),
                "n_predecessors": len(self._predecessor_map.get(obj_id, set())),
                "is_entry": obj_id in self._entry_objects,
            })
        return results

    def get_priors_for_seeding(self, entry_points: List[str] = None,
                               prior_weight: float = 0.15) -> List[Tuple[str, float]]:
        """
        Get weighted priors for seeding a StreamingKanExtension.

        These are injected into the left Kan's comma category as synthetic
        "structural observations" so the system never starts from zero.
        The prior_weight is kept low (0.15) so real observations quickly
        dominate, but the priors ensure non-zero predictions from step 0.

        Args:
            entry_points: Specific entry point objects to seed from.
                          If None, uses all entry objects.
            prior_weight: Base weight for structural priors. Default 0.15.

        Returns:
            List of (object_id, weight) tuples for comma category seeding.
        """
        entries = entry_points or list(self._entry_objects)

        if self._successor_fn is not None:
            prior_dict: Dict[str, float] = {}
            for entry in entries:
                successors = self._successor_fn(entry)
                for succ_id, succ_weight in successors:
                    structural = self._structural_scores.get(succ_id, 0.1)
                    weight = prior_weight * succ_weight * structural
                    if weight > 0.001:
                        if succ_id not in prior_dict or weight > prior_dict[succ_id]:
                            prior_dict[succ_id] = weight
            return sorted(prior_dict.items(), key=lambda x: x[1], reverse=True)
        else:
            # No successor function: use structural scores directly
            prior_dict = {}
            for obj_id, score in self._structural_scores.items():
                weight = prior_weight * score
                if weight > 0.001:
                    prior_dict[obj_id] = weight
            return sorted(prior_dict.items(), key=lambda x: x[1], reverse=True)

    def get_structural_score(self, object_id: str) -> float:
        """Get the structural score for a specific object."""
        return self._structural_scores.get(object_id, 0.0)

    def is_entry(self, object_id: str) -> bool:
        """Check if an object is an entry point."""
        return object_id in self._entry_objects
