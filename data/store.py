"""Minimal data store stubs.

Placeholder so the rest of the repo imports cleanly. Real persistence can be
dropped in later; these provide the symbols the engines import.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class StoredObject:
    name: str
    type_name: str = "object"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StoredMorphism:
    source: str
    target: str
    name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HigherMorphism:
    source: str
    target: str
    name: str = ""
    level: int = 2
    metadata: Dict[str, Any] = field(default_factory=dict)


class KomposOSStore:
    """In-memory key/value store standing in for the real KOMPOSOS store."""

    def __init__(self, path: Optional[str] = None):
        self.path = path
        self._objects: Dict[str, StoredObject] = {}
        self._morphisms: Dict[str, StoredMorphism] = {}

    def add_object(self, obj: StoredObject) -> None:
        self._objects[obj.name] = obj

    def add_morphism(self, mor: StoredMorphism) -> None:
        self._morphisms[mor.name or f"{mor.source}->{mor.target}"] = mor

    def get_object(self, name: str) -> Optional[StoredObject]:
        return self._objects.get(name)

    def objects(self):
        return list(self._objects.values())

    def morphisms(self):
        return list(self._morphisms.values())


def create_store(path: Optional[str] = None) -> KomposOSStore:
    return KomposOSStore(path)
