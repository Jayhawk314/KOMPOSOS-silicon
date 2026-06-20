# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Fused Categorical Types

In KOMPOSOS-III, data lived in three places:
  1. StoredObject / StoredMorphism (SQLite data layer)
  2. Object / Morphism (categorical math layer)
  3. Enriched hom-values as (str, str) -> float (metric layer)

KOMPOSOS-IV fuses all three. An Object IS storable, IS categorical,
and carries enrichment natively. A Morphism IS a relationship, IS a
database row, IS an enriched hom-value, and optionally IS executable.

One representation. Zero translation seams.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .category import Category


@dataclass
class Object:
    """
    A categorical object that persists itself.

    Replaces: StoredObject (III data layer) + categorical.Object (III math layer)

    Fields:
        name: Unique identifier.
        type_name: Categorization (e.g., "concept", "component").
        metadata: Arbitrary key-value data.
        embedding: Optional 768d vector for semantic operations.
        created_at: Timestamp (auto-set if None).
        provenance: Where this object came from.
    """
    name: str
    type_name: str = "Object"
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[np.ndarray] = field(default=None, repr=False)
    created_at: Optional[datetime] = None
    provenance: str = "unknown"
    _category: Optional[Category] = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, Object):
            return self.name == other.name
        return NotImplemented


@dataclass
class Morphism:
    """
    A categorical morphism that persists itself, carries enrichment,
    and optionally executes.

    Replaces:
      - StoredMorphism (III data layer)
      - categorical.Morphism (III math layer)
      - Enriched hom-values (III metric layer)

    The confidence field IS the enriched hom-value. When two morphisms
    compose, the quantale's tensor product combines their confidences.

    Fields:
        name: Identifier for the morphism type.
        source: Source object name.
        target: Target object name.
        confidence: Enriched hom-value in [0,1] (or domain of quantale).
        metadata: Arbitrary key-value data.
        created_at: Timestamp (auto-set if None).
        provenance: Where this morphism came from.
        _fn: Optional callable -- makes this morphism executable.
        _category: Back-reference to owning Category.
    """
    name: str
    source: str
    target: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    provenance: str = "unknown"
    _fn: Optional[Callable] = field(default=None, repr=False, compare=False)
    _category: Optional[Category] = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    @property
    def id(self) -> str:
        """Unique identifier for this morphism instance."""
        return f"{self.name}:{self.source}->{self.target}"

    def __call__(self, *args, **kwargs):
        """If this morphism has a callable, execute it."""
        if self._fn is None:
            raise TypeError(f"Morphism '{self.name}' is structural, not callable")
        return self._fn(*args, **kwargs)

    @property
    def is_callable(self) -> bool:
        """Whether this morphism can be executed."""
        return self._fn is not None

    def compose(self, other: Morphism) -> Morphism:
        """
        Compose self after other: self . other (other runs first).

        Delegates to Category if attached (for persistence + enrichment).
        Falls back to pure composition if detached.
        """
        if self._category:
            return self._category.compose(other, self)
        # Fallback: pure composition without persistence
        composed_fn = None
        if other._fn and self._fn:
            other_fn, self_fn = other._fn, self._fn
            composed_fn = lambda *a, **k: self_fn(other_fn(*a, **k))
        return Morphism(
            name=f"{self.name}.{other.name}",
            source=other.source,
            target=self.target,
            confidence=self.confidence * other.confidence,
            metadata={"composed_from": [other.name, self.name]},
            _fn=composed_fn,
        )

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, Morphism):
            return self.id == other.id
        return NotImplemented


@dataclass
class Path:
    """
    A composed sequence of morphisms representing evolution.

    Fields:
        morphism_ids: Ordered list of morphism IDs along the path.
        source: Starting object name.
        target: Ending object name.
        weight: Total enriched weight of the path.
    """
    morphism_ids: List[str]
    source: str
    target: str
    weight: float = 1.0

    @property
    def length(self) -> int:
        """Number of morphisms in the path."""
        return len(self.morphism_ids)


@dataclass
class HigherMorphism:
    """
    A 2-cell: morphism between morphisms (path between paths).

    Captures HOW two paths are equivalent -- not just that they are,
    but the specific transformation between them.
    """
    name: str
    source_path: str
    target_path: str
    transformation_type: str = "homotopy"
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EquivalenceClass:
    """
    HoTT equivalence: objects identified by paths.

    Via univalence: equivalent things ARE equal.
    """
    name: str
    members: List[str]
    witness: str = ""


@dataclass
class Cone:
    """
    A cone over a diagram: an apex object with leg morphisms to each
    diagram object.

    Used for limits (products, pullbacks, equalizers, terminal objects).

    Fields:
        apex: Name of the apex object.
        legs: Map from diagram object name to morphism ID (apex → object).
    """
    apex: str
    legs: Dict[str, str] = field(default_factory=dict)


@dataclass
class Cocone:
    """
    A cocone over a diagram: an apex object with leg morphisms from each
    diagram object.

    Used for colimits (coproducts, pushouts, coequalizers, initial objects).

    Fields:
        apex: Name of the apex object.
        legs: Map from diagram object name to morphism ID (object → apex).
    """
    apex: str
    legs: Dict[str, str] = field(default_factory=dict)
