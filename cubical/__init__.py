"""
KOMPOSOS-III Cubical Engine (Layer C)

Cubical Type Theory foundations:
- Paths as computational objects (not just proofs)
- Kan operations (hcomp, hfill) for gap-filling
- Higher Inductive Types (HITs) for structured data
- Parallel path exploration (the cube structure)
"""

from .paths import Interval, PathType, path_apply
from .kan_ops import hcomp, hfill, comp, inv

__all__ = [
    "Interval",
    "PathType",
    "path_apply",
    "hcomp",
    "hfill",
    "comp",
    "inv",
]
