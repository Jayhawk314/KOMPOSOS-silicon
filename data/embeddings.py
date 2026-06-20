"""Embeddings engine — a soft Yoneda prior over the category.

Role in the system (read this before "improving" it)
-----------------------------------------------------
This is the *continuous* layer. Category theory + ZFC give exact, structural,
symbolic reasoning; embeddings give the one thing they cannot: a metric notion
of "these two objects are alike even though no morphism connects them yet."

The Yoneda lemma says an object is determined by its profile of morphisms (its
functor of points). An embedding is that profile approximated in a vector space.
So this engine is a *soft Yoneda embedding*: it is a relaxation of structure we
already believe in, not a competing paradigm.

Discipline: embeddings live strictly on the **proposal** side. They surface
candidate edges (SemanticSimilarityStrategy, SemanticCandidates); the symbolic
layer (composition / horns / COG / ZFC) verifies them. Never let a similarity
score stand in for a verdict.

Backend
-------
Default: a dependency-light, deterministic encoder — signed feature-hashing over
character 3-grams + word tokens, L2-normalised, cosine similarity. Works offline,
needs only numpy, and is stable across processes (hashlib, not the salted builtin
`hash`). `is_available` is therefore always True.

Two refinements layer on top of the lexical vector:
  - `fit(category)` computes a *structural* vector per object from its morphism
    neighbourhood (relation names + neighbours, in and out) — the actual soft
    Yoneda embedding — and blends it with the lexical one. Call it once after the
    graph is populated to make similarity reflect structure, not just spelling.
  - If constructed with `model=<sentence-transformers name>` and that library is
    importable, real semantic embeddings are used for free-text. Optional; the
    lexical encoder is the always-available fallback.
"""
from __future__ import annotations

import hashlib
import math
from typing import Dict, List, Optional, Sequence

import numpy as np

# Token weighting when blending the structural (Yoneda) signal with the lexical
# one in fit(): structure dominates, spelling is a tiebreaker.
_STRUCTURAL_WEIGHT = 1.0
_LEXICAL_WEIGHT = 0.35


def _char_ngrams(text: str, n: int = 3) -> List[str]:
    t = f"^{text.lower().strip()}$"
    if len(t) <= n:
        return [t]
    return [t[i:i + n] for i in range(len(t) - n + 1)]


def _word_tokens(text: str) -> List[str]:
    return [w for w in text.lower().replace("_", " ").replace(":", " ").split() if w]


def _stable_hash(token: str) -> int:
    """Process-stable hash (builtin hash() is salted per run)."""
    return int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big")


class EmbeddingsEngine:
    """Deterministic vector embeddings with cosine similarity.

    API consumed elsewhere: ``is_available``, ``similarity(a, b)``,
    ``embed(text)``, ``embed_batch(texts)``. ``fit(category)`` and the optional
    transformer model are additive.
    """

    def __init__(self, model: Optional[str] = None, dim: int = 256):
        self.model = model
        self.dim = max(8, int(dim))
        self._cache: Dict[str, np.ndarray] = {}
        self._fitted: Dict[str, np.ndarray] = {}
        self._st_model = None  # lazily-loaded sentence-transformers model, if any
        if model:
            self._try_load_transformer(model)

    # -- availability -------------------------------------------------------

    @property
    def is_available(self) -> bool:
        # The lexical fallback always works, so the engine is always available.
        return True

    # -- transformer (optional) --------------------------------------------

    def _try_load_transformer(self, model: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._st_model = SentenceTransformer(model)
            self.dim = int(self._st_model.get_sentence_embedding_dimension())
        except Exception:
            # No network / lib / model -> stay on the lexical encoder.
            self._st_model = None

    # -- core encoding ------------------------------------------------------

    def _hash_vector(self, tokens: Sequence[str]) -> np.ndarray:
        """Signed feature hashing of tokens into a dim-vector."""
        vec = np.zeros(self.dim, dtype=np.float64)
        for tok in tokens:
            h = _stable_hash(tok)
            idx = h % self.dim
            sign = 1.0 if (h >> 1) & 1 else -1.0
            vec[idx] += sign
        return vec

    def _lexical_vector(self, text: str) -> np.ndarray:
        if self._st_model is not None:
            try:
                v = np.asarray(self._st_model.encode(text), dtype=np.float64)
                return _l2_normalise(v)
            except Exception:
                pass
        tokens = _char_ngrams(text, 3) + [f"w:{w}" for w in _word_tokens(text)]
        return _l2_normalise(self._hash_vector(tokens))

    def _vector(self, name: str) -> np.ndarray:
        """Fitted structural vector if available, else lexical (cached)."""
        if name in self._fitted:
            return self._fitted[name]
        if name not in self._cache:
            self._cache[name] = self._lexical_vector(name)
        return self._cache[name]

    # -- structural (Yoneda) fit -------------------------------------------

    def fit(self, category) -> "EmbeddingsEngine":
        """Compute a soft Yoneda embedding per object from its morphism profile.

        An object's vector becomes the hash of (its name) + (its outgoing and
        incoming morphisms: relation names, neighbours, and relation->neighbour
        pairs), blended with its lexical vector. Objects with similar roles in the
        graph land near each other even with dissimilar names.
        """
        try:
            objects = list(category.objects())
        except Exception:
            return self
        self._fitted = {}
        for obj in objects:
            name = getattr(obj, "name", None)
            if name is None:
                continue
            tokens: List[str] = [f"self:{name}", f"type:{getattr(obj, 'type_name', '')}"]
            for m in _safe(category.morphisms_from, name):
                tokens += [f"out:{m.name}", f"out_to:{m.target}", f"out_pair:{m.name}->{m.target}"]
            for m in _safe(category.morphisms_to, name):
                tokens += [f"in:{m.name}", f"in_from:{m.source}"]
            structural = self._hash_vector(tokens)
            lexical = self._lexical_vector(name)
            blended = _STRUCTURAL_WEIGHT * _l2_normalise(structural) + _LEXICAL_WEIGHT * lexical
            self._fitted[name] = _l2_normalise(blended)
        return self

    # -- public API ---------------------------------------------------------

    def similarity(self, a: str, b: str) -> float:
        """Cosine similarity in [0, 1] between two names/strings."""
        if a == b:
            return 1.0
        va, vb = self._vector(a), self._vector(b)
        cos = float(np.dot(va, vb))  # both L2-normalised
        if math.isnan(cos):
            return 0.0
        # Negative cosine means "unrelated"; clamp to the [0,1] range callers expect.
        return max(0.0, min(1.0, cos))

    def embed(self, text: str) -> List[float]:
        return self._vector(text).tolist()

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


def _l2_normalise(v: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(v))
    if norm == 0.0:
        return v
    return v / norm


def _safe(fn, arg):
    try:
        return list(fn(arg))
    except Exception:
        return []
