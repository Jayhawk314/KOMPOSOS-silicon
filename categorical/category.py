# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 James Ray Hawkins
#
# Compatibility shim: re-exports from KOMPOSOS-IV core.
# In IV, Category IS the fused runtime (core/category.py).
# This module exists so that `from categorical.category import Category`
# still works in ported math modules.

from core.types import Object, Morphism
from core.category import Category

__all__ = ["Category", "Object", "Morphism"]
