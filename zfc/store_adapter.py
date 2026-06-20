# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
Store Adapter -- Reads Category, populates both engines.

Category is the single source of truth (KOMPOSOS-IV fused runtime).
StoreAdapter reads it and builds:
    - ZFC side: Universe, Model, Theory, LogicOracle, OrdinalOracle
    - CAT side: Category (already IS the Category -- returned directly)

Domain-agnostic: reads whatever objects and morphisms are in the category.
No hardcoded relation names.

Architecture:

    Category (any domain)
           |
       StoreAdapter
        /        \
      CAT        ZFC
    (System 2)  (System 1)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.category import Category, Object, Morphism

from .universe import Universe, ZFSet, Relation, zfset, relation
from .logic import (
    Model, Theory, LogicOracle,
    atom, conj, implies, forall,
    var, const,
)
from .well_ordering import OrdinalOracle, well_order_by_rank


class StoreAdapter:
    """
    Reads Category and populates both ZFC and CAT engines.

    Usage:
        category = Category(db_path=":memory:")
        # ... add objects and morphisms to category ...
        adapter = StoreAdapter(category)
        universe = adapter.to_universe()
        model    = adapter.to_model()
        theory   = adapter.to_theory()
        logic    = adapter.to_logic_oracle()
        ordinal  = adapter.to_ordinal_oracle()
        category = adapter.to_category()
    """

    def __init__(self, category: Category):
        self.category = category
        self._universe: Optional[Universe] = None
        self._model: Optional[Model] = None
        self._category: Optional[Category] = None

    # ================================================================
    # ZFC side
    # ================================================================

    def to_universe(self, name: str = "V") -> Universe:
        """
        Build a ZFC Universe from the category.

        Each Object becomes a ZFSet.
        Each Morphism becomes a Relation pair.
        Objects are grouped into type-sets based on type_name.
        """
        if self._universe is not None:
            return self._universe

        V = Universe(name)

        # Load all objects
        objects = self.category.objects()
        type_sets: Dict[str, ZFSet] = {}

        for obj in objects:
            # Filter out keys that conflict with zfset() positional args
            safe_meta = {k: v for k, v in obj.metadata.items()
                         if k not in ("name", "elements")}
            s = zfset(obj.name, **safe_meta)
            V.add_set(s)

            # Group by type
            tname = obj.type_name or "Object"
            if tname not in type_sets:
                ts = zfset(tname)
                V.add_set(ts)
                type_sets[tname] = ts
            V.add_element(s, type_sets[tname])

        # Load all morphisms -> Relations
        morphisms = self.category.morphisms()
        rel_buckets: Dict[str, List] = {}

        for m in morphisms:
            rel_buckets.setdefault(m.name, []).append((m.source, m.target))

        for rel_name, pairs in rel_buckets.items():
            r = relation(rel_name, pairs)
            V.add_relation(r)

        self._universe = V
        return V

    def to_model(self) -> Model:
        """
        Build a ZFC Model from the category.

        The model interprets every object name as itself
        (constants map to set names in the universe).
        """
        if self._model is not None:
            return self._model

        V = self.to_universe()
        constants: Dict[str, str] = {}
        for name in V.sets:
            constants[name] = name

        self._model = Model(universe=V, constants=constants)
        return self._model

    def to_theory(self, name: str = "StoreTheory") -> Theory:
        """
        Build a Theory from the category.

        For each relation R with pairs (a, b), assert R(a, b) as axioms.
        This makes the theory a faithful mirror of the stored data.
        """
        V = self.to_universe()
        T = Theory(name)

        for rel_name in list(V.relations.keys()):
            rel = V.relations[rel_name]
            for (a, b) in rel.pairs:
                axiom_formula = atom(rel_name, const(a), const(b))
                T.add_axiom(axiom_formula)

        return T

    def to_logic_oracle(self) -> LogicOracle:
        """Build a LogicOracle (ZFC prediction interface)."""
        T = self.to_theory()
        M = self.to_model()
        return LogicOracle(T, M)

    def to_ordinal_oracle(self, relation_name: Optional[str] = None) -> OrdinalOracle:
        """
        Build an OrdinalOracle (well-ordering prediction).

        If relation_name is given, builds the oracle from that relation.
        Otherwise, picks the first relation in the universe, or uses
        a rank-based ordering if no relations exist.
        """
        V = self.to_universe()

        if relation_name is not None:
            rel = V.get_relation(relation_name)
            if rel is None:
                raise ValueError(f"Relation '{relation_name}' not found in universe")
            return OrdinalOracle(V, rel)

        # Pick first relation
        rel_keys = list(V.relations.keys())
        if rel_keys:
            return OrdinalOracle(V, V.relations[rel_keys[0]])

        # No relations -- create an empty one
        empty_rel = relation("_empty")
        V.add_relation(empty_rel)
        return OrdinalOracle(V, empty_rel)

    # ================================================================
    # CAT side
    # ================================================================

    def to_category(self, name: str = "C") -> Category:
        """
        Return the Category.

        In KOMPOSOS-IV, the Category IS the fused runtime.
        No conversion needed -- just return it directly.
        """
        if self._category is not None:
            return self._category
        self._category = self.category
        return self._category


# ================================================================
# Convenience functions
# ================================================================

def store_to_logic_oracle(category: Category) -> LogicOracle:
    """Convenience: build a LogicOracle directly from a Category."""
    return StoreAdapter(category).to_logic_oracle()


def store_to_ordinal_oracle(category: Category) -> OrdinalOracle:
    """Convenience: build an OrdinalOracle directly from a Category."""
    return StoreAdapter(category).to_ordinal_oracle()
