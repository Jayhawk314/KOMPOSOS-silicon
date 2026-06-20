"""
Conjecture Engine for KOMPOSOS-IV.

Flips the Oracle from reactive to proactive:
  - Reactive (existing):  predict(source, target) -> what relation?
  - Proactive (this):     conjecture()            -> what pairs are missing?

Design constraints respected:
  - Every strategy already caches category.morphisms() and category.objects().
    We reuse those exact caches via a shared _GraphCache; no redundant category calls.
  - Candidate enumeration is O(E * k), not O(N^2).  We only consider pairs that
    at least one strategy would score > 0, discovered via graph neighbourhood
    expansion rather than brute-force.
  - The existing pipeline (merge -> coherence -> optimize -> learn) is reused
    end-to-end on whatever candidates we surface.  ConjectureEngine accepts a
    fully-initialised CategoricalOracle and delegates scoring to oracle.predict().

Candidate generation sources (each produces a set of (source, target) pairs):
  1. CompositionCandidates      -- 2-hop transitive closure gaps
  2. StructuralHoleCandidates   -- open triangles (common ancestor / descendant)
  3. FiberCandidates            -- same (type, era) fiber, missing edge
  4. SemanticCandidates         -- top-k nearest neighbours via embeddings
  5. TemporalCandidates         -- type-compatible contemporaries / predecessors
  6. YonedaCandidates           -- objects with high Hom-pattern overlap, no edge
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Dict, List, Set, Tuple
from dataclasses import dataclass, field

if TYPE_CHECKING:  # pragma: no cover
    from core.category import Category
    from data.embeddings import EmbeddingsEngine
    from oracle import CategoricalOracle

from oracle.prediction import Prediction


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class Conjecture:
    """A single conjecture: a missing edge the engine believes should exist."""
    source: str
    target: str
    predictions: List[Prediction]       # full Oracle output for this pair
    top_confidence: float               # max confidence across predictions
    candidate_sources: List[str]        # which generators surfaced this pair

    @property
    def best(self) -> Prediction | None:
        return self.predictions[0] if self.predictions else None

    def __repr__(self) -> str:
        best = self.best
        rel = best.predicted_relation if best else "?"
        return (
            f"Conjecture({self.source} --[{rel}]--> {self.target}, "
            f"conf={self.top_confidence:.2f}, sources={self.candidate_sources})"
        )


@dataclass
class ConjectureResult:
    """Full output of a conjecture run."""
    conjectures: List[Conjecture]
    pairs_evaluated: int                # pairs that went through Oracle.predict()
    pairs_surfaced: int                 # raw candidates before Oracle filtering
    candidate_breakdown: Dict[str, int] # generator name -> how many pairs it contributed
    computation_time_ms: float
    min_confidence: float


# ---------------------------------------------------------------------------
# Shared graph cache
# ---------------------------------------------------------------------------

class _GraphCache:
    """
    Populated once per conjecture run.  All generators and the engine share
    a single instance so we never hit the category more than once per collection.
    """

    def __init__(self, category: Category):
        self.category = category
        self._morphisms: list | None = None
        self._objects: list | None = None
        self._outgoing: Dict[str, list] | None = None
        self._incoming: Dict[str, list] | None = None
        self._existing: Set[Tuple[str, str]] | None = None
        self._object_map: Dict[str, object] | None = None

    # -- accessors ----------------------------------------------------------

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

    # -- internals ----------------------------------------------------------

    def _ensure_indices(self):
        if self._outgoing is not None:
            return
        self._outgoing, self._incoming = {}, {}
        for m in self.morphisms:
            self._outgoing.setdefault(m.source, []).append(m)
            self._incoming.setdefault(m.target, []).append(m)


# ---------------------------------------------------------------------------
# Candidate generators
# ---------------------------------------------------------------------------

class _CandidateGenerator:
    """Base class.  Subclasses implement generate() using the shared cache."""

    name: str = "base"

    def __init__(self, cache: _GraphCache, embeddings: EmbeddingsEngine | None = None):
        self.cache = cache
        self.embeddings = embeddings

    def generate(self) -> Set[Tuple[str, str]]:
        raise NotImplementedError


# --- 1. Composition (transitive closure gaps) ------------------------------

class CompositionCandidates(_CandidateGenerator):
    """
    Every 2-hop path A -> B -> C where A -> C is missing.
    CompositionStrategy will score all of these non-zero.
    """

    name = "composition"

    def generate(self) -> Set[Tuple[str, str]]:
        outgoing = self.cache.outgoing
        existing = self.cache.existing
        candidates: Set[Tuple[str, str]] = set()

        for source, mors in outgoing.items():
            for m1 in mors:
                for m2 in outgoing.get(m1.target, []):
                    target = m2.target
                    if target != source and (source, target) not in existing:
                        candidates.add((source, target))

        return candidates


# --- 2. Structural holes (open triangles) ----------------------------------

class StructuralHoleCandidates(_CandidateGenerator):
    """
    Common-ancestor: X -> A and X -> B exist, A -> B missing.
    Common-descendant: A -> X and B -> X exist, A -> B missing.
    StructuralHoleStrategy scores both patterns.
    """

    name = "structural_hole"

    # Per-node cap on pairwise expansion to keep worst case bounded.
    _MAX_SIBLINGS = 25

    def generate(self) -> Set[Tuple[str, str]]:
        outgoing = self.cache.outgoing
        incoming = self.cache.incoming
        existing = self.cache.existing
        candidates: Set[Tuple[str, str]] = set()

        # -- common ancestor --------------------------------------------------
        for ancestor, mors in outgoing.items():
            targets = [m.target for m in mors]
            if len(targets) > self._MAX_SIBLINGS:
                targets = targets[: self._MAX_SIBLINGS]
            for i, a in enumerate(targets):
                for b in targets[i + 1:]:
                    if (a, b) not in existing:
                        candidates.add((a, b))
                    if (b, a) not in existing:
                        candidates.add((b, a))

        # -- common descendant ------------------------------------------------
        for descendant, mors in incoming.items():
            sources = [m.source for m in mors]
            if len(sources) > self._MAX_SIBLINGS:
                sources = sources[: self._MAX_SIBLINGS]
            for i, a in enumerate(sources):
                for b in sources[i + 1:]:
                    if (a, b) not in existing:
                        candidates.add((a, b))

        return candidates


# --- 3. Fiber candidates (same type + era, missing edge) -------------------

class FiberCandidates(_CandidateGenerator):
    """
    Objects sharing the same (type_name, era) fiber with no direct edge.
    FibrationLiftStrategy scores these.
    """

    name = "fiber"

    _MAX_FIBER_SIZE = 30  # beyond this we truncate to avoid O(n^2) per fiber

    def generate(self) -> Set[Tuple[str, str]]:
        existing = self.cache.existing
        candidates: Set[Tuple[str, str]] = set()

        fibers: Dict[Tuple[str, str], List[str]] = {}
        for obj in self.cache.objects:
            meta = obj.metadata if hasattr(obj, "metadata") and obj.metadata else {}
            era = meta.get("era", "unknown")
            fibers.setdefault((obj.type_name, era), []).append(obj.name)

        for members in fibers.values():
            if len(members) > self._MAX_FIBER_SIZE:
                members = members[: self._MAX_FIBER_SIZE]
            for i, a in enumerate(members):
                for b in members[i + 1:]:
                    if (a, b) not in existing:
                        candidates.add((a, b))
                    if (b, a) not in existing:
                        candidates.add((b, a))

        return candidates


# --- 4. Semantic candidates (embedding nearest neighbours) -----------------

class SemanticCandidates(_CandidateGenerator):
    """
    Top-k nearest neighbours per object by embedding similarity, minus existing
    edges.  SemanticSimilarityStrategy uses a 0.6 threshold; we match it here so
    every candidate will score non-zero.
    """

    name = "semantic"
    _SIMILARITY_THRESHOLD = 0.6

    def __init__(self, cache: _GraphCache, embeddings: EmbeddingsEngine | None = None, top_k: int = 10):
        super().__init__(cache, embeddings)
        self.top_k = top_k

    def generate(self) -> Set[Tuple[str, str]]:
        if self.embeddings is None or not self.embeddings.is_available:
            return set()

        existing = self.cache.existing
        names = [obj.name for obj in self.cache.objects]
        candidates: Set[Tuple[str, str]] = set()

        for name in names:
            for neighbour in self._top_k_neighbours(name, names):
                if (name, neighbour) not in existing:
                    candidates.add((name, neighbour))

        return candidates

    def _top_k_neighbours(self, target: str, all_names: List[str]) -> List[str]:
        # Fast path: vectorised top-k if the engine exposes it
        if hasattr(self.embeddings, "top_neighbours"):
            try:
                return self.embeddings.top_neighbours(target, k=self.top_k)
            except (TypeError, NotImplementedError):
                pass

        # Slow path: pairwise, threshold-filtered
        scored: List[Tuple[float, str]] = []
        for name in all_names:
            if name == target:
                continue
            sim = self.embeddings.similarity(target, name)
            if sim >= self._SIMILARITY_THRESHOLD:
                scored.append((sim, name))

        scored.sort(reverse=True)
        return [n for _, n in scored[: self.top_k]]


# --- 5. Temporal candidates (type-compatible predecessors/contemporaries) --

class TemporalCandidates(_CandidateGenerator):
    """
    Pairs where both objects have birth metadata AND the type pair is one
    TemporalReasoningStrategy + TypeHeuristicStrategy would both score.

    We only emit pairs where the birth-difference actually triggers one of
    TemporalReasoningStrategy's rules (>0 for influence, <=20 for collaboration),
    so we don't flood the pipeline with noise.
    """

    name = "temporal"

    # Type pairs that TypeHeuristicStrategy.TYPE_RULES recognises
    _VALID_TYPE_PAIRS = {
        ("Physicist", "Physicist"),
        ("Physicist", "Theory"),
        ("Physicist", "Mathematician"),
        ("Mathematician", "Physicist"),
        ("Mathematician", "Mathematician"),
        ("Mathematician", "Theory"),
        ("Philosopher", "Physicist"),
        ("Philosopher", "Theory"),
        ("Theory", "Theory"),
    }

    # TemporalReasoningStrategy treats birth_diff <= 20 as "contemporary"
    _CONTEMPORARY_WINDOW = 20

    def generate(self) -> Set[Tuple[str, str]]:
        existing = self.cache.existing
        candidates: Set[Tuple[str, str]] = set()

        # Collect objects that have birth metadata
        temporal_objects: List = []
        for obj in self.cache.objects:
            meta = obj.metadata if hasattr(obj, "metadata") and obj.metadata else {}
            if "birth" in meta:
                temporal_objects.append(obj)

        # Group by type for efficient pairing
        by_type: Dict[str, List] = {}
        for obj in temporal_objects:
            by_type.setdefault(obj.type_name, []).append(obj)

        # Iterate over valid type pairs
        for (src_type, tgt_type) in self._VALID_TYPE_PAIRS:
            src_group = by_type.get(src_type, [])
            tgt_group = by_type.get(tgt_type, [])

            # Same-type pairs: avoid double work
            if src_type == tgt_type:
                for i, a in enumerate(src_group):
                    for b in src_group[i + 1:]:
                        self._maybe_emit(a, b, src_type, tgt_type, existing, candidates)
            else:
                for a in src_group:
                    for b in tgt_group:
                        self._maybe_emit(a, b, src_type, tgt_type, existing, candidates)

        return candidates

    def _maybe_emit(
        self, a, b,
        src_type: str, tgt_type: str,
        existing: Set[Tuple[str, str]],
        candidates: Set[Tuple[str, str]],
    ):
        """
        Emit (a, b) and/or (b, a) only if:
          1. Temporal rules would fire for that direction, AND
          2. The resulting (source_type, target_type) is in _VALID_TYPE_PAIRS.

        We received this pair because (src_type, tgt_type) is valid and
        a is in src_type's group.  If we flip the direction (b older -> emit
        (b, a)), the effective type pair becomes (tgt_type, src_type), which
        must be independently valid.
        """
        a_birth = a.metadata.get("birth")
        b_birth = b.metadata.get("birth")
        if a_birth is None or b_birth is None:
            return

        diff = b_birth - a_birth  # positive means a is older

        # -- contemporary window checked FIRST: it's the tightest condition
        #    and includes cases where diff > 0 or diff < 0 but small.
        if abs(diff) <= self._CONTEMPORARY_WINDOW:
            # Forward direction: (a -> b), type pair is (src_type, tgt_type) -- already valid
            if (a.name, b.name) not in existing:
                candidates.add((a.name, b.name))
            # Reverse direction: (b -> a), type pair is (tgt_type, src_type) -- must check
            if (tgt_type, src_type) in self._VALID_TYPE_PAIRS and (b.name, a.name) not in existing:
                candidates.add((b.name, a.name))

        elif diff > 0:
            # a is older -> influence flows a -> b.  Type pair (src_type, tgt_type) already valid.
            if (a.name, b.name) not in existing:
                candidates.add((a.name, b.name))

        elif diff < 0:
            # b is older -> influence flows b -> a.  Effective type pair is (tgt_type, src_type).
            if (tgt_type, src_type) in self._VALID_TYPE_PAIRS and (b.name, a.name) not in existing:
                candidates.add((b.name, a.name))


# --- 6. Yoneda candidates (shared Hom-pattern, no edge) --------------------

class YonedaCandidates(_CandidateGenerator):
    """
    Two objects whose outgoing morphism-type sets overlap significantly but
    that have no direct edge.  YonedaPatternStrategy scores based on exactly
    this overlap (threshold 0.3), so candidates here get non-trivial scores.

    We only compare objects that share at least one common *target* (not just
    morphism type) to keep the set small -- that's the fast filter before we
    compute the actual Jaccard overlap.
    """

    name = "yoneda"
    _SIMILARITY_THRESHOLD = 0.3

    def generate(self) -> Set[Tuple[str, str]]:
        outgoing = self.cache.outgoing
        existing = self.cache.existing
        candidates: Set[Tuple[str, str]] = set()

        # Build: target -> list of sources that point to it
        target_to_sources: Dict[str, List[str]] = {}
        for src, mors in outgoing.items():
            for m in mors:
                target_to_sources.setdefault(m.target, []).append(src)

        # For each shared target, compare all pairs of sources.
        # Objects that share no target can't have meaningful Hom-pattern overlap
        # in the sense YonedaPatternStrategy uses, so this is our fast filter.
        already_compared: Set[Tuple[str, str]] = set()

        for shared_target, sources in target_to_sources.items():
            if len(sources) > 40:
                sources = sources[:40]  # cap to avoid blowup on hub targets
            for i, a in enumerate(sources):
                for b in sources[i + 1:]:
                    pair = (a, b) if a < b else (b, a)
                    if pair in already_compared:
                        continue
                    already_compared.add(pair)

                    # Compute Yoneda similarity (same formula as YonedaPatternStrategy)
                    a_out_types = {m.name for m in outgoing.get(a, [])}
                    b_out_types = {m.name for m in outgoing.get(b, [])}
                    a_out_targets = {m.target for m in outgoing.get(a, [])}
                    b_out_targets = {m.target for m in outgoing.get(b, [])}

                    type_sim = len(a_out_types & b_out_types) / max(len(a_out_types | b_out_types), 1)
                    target_sim = len(a_out_targets & b_out_targets) / max(len(a_out_targets | b_out_targets), 1)
                    yoneda_sim = (type_sim + target_sim) / 2

                    if yoneda_sim >= self._SIMILARITY_THRESHOLD:
                        if (a, b) not in existing:
                            candidates.add((a, b))
                        if (b, a) not in existing:
                            candidates.add((b, a))

        return candidates


# ---------------------------------------------------------------------------
# Conjecture Engine -- the orchestrator
# ---------------------------------------------------------------------------

class ConjectureEngine:
    """
    Produces conjectures by:
      1. Running all candidate generators to surface missing-edge pairs.
      2. Deduplicating and stripping already-existing edges.
      3. Scoring every surviving pair through the full Oracle.predict() pipeline.
      4. Returning results sorted by confidence.

    Usage:
        engine = ConjectureEngine(oracle)          # oracle is a CategoricalOracle
        result = engine.conjecture(top_k=50)       # top 50 conjectures
        for c in result.conjectures:
            print(c)
    """

    def __init__(
        self,
        oracle: CategoricalOracle | None = None,
        semantic_top_k: int = 10,
        *,
        category: Category | None = None,
        embeddings: EmbeddingsEngine | None = None,
    ):
        """
        Args:
            oracle: Fully initialised CategoricalOracle (embeddings required).
                Needed for the scored `conjecture()` path.
            semantic_top_k: How many embedding neighbours to consider per object.
            category / embeddings: oracle-free construction for the proactive
                candidate-surfacing path (`surface_candidates()`), which needs no
                scoring oracle. Used by the self-improvement loop, which runs
                embedding-free. `embeddings=None` simply skips the semantic
                generator; all five structural generators still fire.
        """
        if oracle is not None:
            self.oracle = oracle
            self._category = oracle.category
            self._embeddings = oracle.embeddings
        elif category is not None:
            self.oracle = None
            self._category = category
            self._embeddings = embeddings
        else:
            raise ValueError(
                "ConjectureEngine requires either an `oracle` (for scored "
                "conjecture()) or a `category` (for surface_candidates())."
            )
        self.semantic_top_k = semantic_top_k

    @classmethod
    def from_category(
        cls,
        category: Category,
        embeddings: EmbeddingsEngine | None = None,
        semantic_top_k: int = 10,
    ) -> "ConjectureEngine":
        """Build an oracle-free engine for proactive candidate surfacing."""
        return cls(category=category, embeddings=embeddings, semantic_top_k=semantic_top_k)

    # -- public API ---------------------------------------------------------

    def surface_candidates(
        self,
        generators: List[str] | None = None,
    ) -> Dict[Tuple[str, str], List[str]]:
        """
        Run only the candidate generators (no scoring oracle required).

        This is the proactive core of the engine: it surfaces missing-edge pairs
        the graph's own structure says *should* exist. Returns a mapping from each
        candidate ``(source, target)`` pair to the list of generator names that
        surfaced it (provenance / breadth of support).

        Args:
            generators: Whitelist of generator names. None = all.
                Valid: composition, structural_hole, fiber, semantic, temporal, yoneda.
        """
        cache = _GraphCache(self._category)
        gens = self._build_generators(cache)
        if generators is not None:
            allowed = set(generators)
            gens = [g for g in gens if g.name in allowed]

        pair_sources: Dict[Tuple[str, str], List[str]] = {}
        for gen in gens:
            for pair in gen.generate():
                pair_sources.setdefault(pair, []).append(gen.name)
        return pair_sources

    def conjecture(
        self,
        top_k: int = 50,
        min_confidence: float | None = None,
        generators: List[str] | None = None,
    ) -> ConjectureResult:
        """
        Run the full conjecture pipeline.

        Args:
            top_k: Maximum conjectures to return (sorted by confidence).
            min_confidence: Override the Oracle's min_confidence for this run.
                If None, uses whatever the Oracle was initialised with.
            generators: Whitelist of generator names to run.  None = all.
                Valid names: composition, structural_hole, fiber, semantic,
                             temporal, yoneda

        Returns:
            ConjectureResult with ranked conjectures and diagnostics.
        """
        if self.oracle is None:
            raise ValueError(
                "conjecture() needs a scoring oracle. Construct with an oracle, "
                "or use surface_candidates() for oracle-free candidate generation."
            )

        start = time.time()
        effective_min_conf = min_confidence if min_confidence is not None else self.oracle.min_confidence

        # -- steps 1-3: surface candidates (shared with surface_candidates) --
        pair_sources = self.surface_candidates(generators)
        all_candidates: Set[Tuple[str, str]] = set(pair_sources)

        pairs_surfaced = len(all_candidates)
        breakdown: Dict[str, int] = {}
        for srcs in pair_sources.values():
            for name in srcs:
                breakdown[name] = breakdown.get(name, 0) + 1

        # -- step 4: score through Oracle ------------------------------------
        conjectures: List[Conjecture] = []

        for source, target in all_candidates:
            result = self.oracle.predict(source, target)
            preds = result.predictions

            if not preds:
                continue

            top_conf = preds[0].confidence  # already sorted desc by optimizer
            if top_conf < effective_min_conf:
                continue

            conjectures.append(Conjecture(
                source=source,
                target=target,
                predictions=preds,
                top_confidence=top_conf,
                candidate_sources=pair_sources.get((source, target), []),
            ))

        # -- step 5: sort and truncate --------------------------------------
        conjectures.sort(key=lambda c: c.top_confidence, reverse=True)
        conjectures = conjectures[:top_k]

        elapsed_ms = (time.time() - start) * 1000

        return ConjectureResult(
            conjectures=conjectures,
            pairs_evaluated=pairs_surfaced,
            pairs_surfaced=pairs_surfaced,
            candidate_breakdown=breakdown,
            computation_time_ms=elapsed_ms,
            min_confidence=effective_min_conf,
        )

    # -- internals ----------------------------------------------------------

    def _build_generators(self, cache: _GraphCache) -> List[_CandidateGenerator]:
        emb = self._embeddings
        return [
            CompositionCandidates(cache),
            StructuralHoleCandidates(cache),
            FiberCandidates(cache),
            SemanticCandidates(cache, emb, top_k=self.semantic_top_k),
            TemporalCandidates(cache),
            YonedaCandidates(cache),
        ]


# ---------------------------------------------------------------------------
# Convenience: standalone conjecture call (no pre-built Oracle needed)
# ---------------------------------------------------------------------------

def find_conjectures(
    category: Category,
    embeddings: EmbeddingsEngine,
    top_k: int = 50,
    min_confidence: float = 0.4,
    max_predictions: int = 20,
) -> ConjectureResult:
    """
    One-shot conjecture generation.  Builds an Oracle internally.

    Args:
        category: Populated Category.
        embeddings: Initialised EmbeddingsEngine.
        top_k: Number of conjectures to return.
        min_confidence: Minimum confidence threshold.
        max_predictions: Max predictions per pair (passed to Oracle).

    Returns:
        ConjectureResult sorted by confidence.
    """
    from oracle import CategoricalOracle  # local import avoids circular

    oracle = CategoricalOracle(
        category,
        embeddings,
        min_confidence=min_confidence,
        max_predictions=max_predictions,
    )
    engine = ConjectureEngine(oracle)
    return engine.conjecture(top_k=top_k, min_confidence=min_confidence)
