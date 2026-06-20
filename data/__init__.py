"""Minimal data package.

Placeholder so the engines import cleanly. Real persistence/embeddings can be
dropped in later; this just provides the symbols other modules import.
"""
from .store import (
    KomposOSStore,
    StoredObject,
    StoredMorphism,
    HigherMorphism,
    create_store,
)
from .embeddings import EmbeddingsEngine

__all__ = [
    "KomposOSStore",
    "StoredObject",
    "StoredMorphism",
    "HigherMorphism",
    "create_store",
    "EmbeddingsEngine",
]
