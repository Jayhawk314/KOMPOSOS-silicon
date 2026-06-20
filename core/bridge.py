# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Domain Bridge ABC

Thin adapter for loading domain data into a Category.
Much simpler than KOMPOSOS-III's KompososBridge because Category IS
the runtime -- no separate store, enriched category, or store adapter.

A domain bridge implements three methods:
  - get_objects(): Domain entities as categorical Objects.
  - get_morphisms(): Domain interactions as categorical Morphisms.
  - score_pair(): Domain-specific compatibility score.

Then calls bridge.load() to wire everything into the Category.
Analysis (curvature, homology, path finding) lives on Category
or in standalone modules -- not on the bridge.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from .types import Object, Morphism
from .enrichment import MonoidalStructure
from .category import Category


class Bridge(ABC):
    """
    Domain bridge for KOMPOSOS-IV.

    Subclass this and implement the three abstract methods.
    The bridge creates a Category (or uses one you provide)
    and loads domain data into it.

    Usage:
        class MyBridge(Bridge):
            def get_objects(self):
                return [Object(name="A"), Object(name="B")]
            def get_morphisms(self):
                return [Morphism(name="r", source="A", target="B", confidence=0.9)]
            def score_pair(self, source, target):
                return {"strength": 0.9}

        bridge = MyBridge("my_domain")
        bridge.load()
        path = bridge.category.optimal_path("A", "B")
    """

    def __init__(
        self,
        name: str,
        category: Category = None,
        quantale: MonoidalStructure = None,
        db_path: str = ":memory:",
    ):
        self.name = name
        self.category = category or Category(
            name=name, db_path=db_path, quantale=quantale
        )
        self._loaded = False

    @abstractmethod
    def get_objects(self) -> List[Object]:
        """Return domain entities as categorical Objects."""
        ...

    @abstractmethod
    def get_morphisms(self) -> List[Morphism]:
        """Return domain interactions as categorical Morphisms."""
        ...

    @abstractmethod
    def score_pair(self, source: str, target: str) -> Dict[str, float]:
        """Return domain-specific compatibility scores for a pair."""
        ...

    def load(self) -> Dict[str, int]:
        """
        Load domain data into the Category.

        Returns dict with counts: {"objects": N, "morphisms": M}
        """
        result = self.category.bulk_add(
            self.get_objects(), self.get_morphisms()
        )
        self._loaded = True
        return result

    @property
    def is_loaded(self) -> bool:
        """Whether domain data has been loaded."""
        return self._loaded

    def as_functor(self):
        """
        Capture the bridge's load mapping as a verified Functor.

        The bridge defines a mapping from domain objects/morphisms into
        the category. This method reifies that mapping as a Functor from
        a "domain" category (containing just the loaded objects/morphisms)
        to self.category.

        Must be called after load().

        Returns:
            A Functor from a domain category to self.category.
        """
        from .functor import Functor

        if not self._loaded:
            raise RuntimeError("Bridge must be loaded before calling as_functor()")

        # Build a domain category with the raw objects/morphisms
        domain = Category(
            name=f"{self.name}_domain",
            db_path=":memory:",
            quantale=self.category.quantale,
        )

        objects = self.get_objects()
        morphisms = self.get_morphisms()

        obj_map = {}
        for obj in objects:
            domain.add_object(Object(
                name=obj.name,
                type_name=obj.type_name,
                metadata=dict(obj.metadata),
            ))
            # Domain object maps to same-named object in category
            obj_map[obj.name] = obj.name

        mor_map = {}
        for mor in morphisms:
            domain.add_morphism(Morphism(
                name=mor.name,
                source=mor.source,
                target=mor.target,
                confidence=mor.confidence,
                metadata=dict(mor.metadata),
            ))
            mor_map[mor.id] = mor.id

        return Functor(
            name=f"{self.name}_bridge",
            source=domain,
            target=self.category,
            _object_map=obj_map,
            _morphism_map=mor_map,
        )
