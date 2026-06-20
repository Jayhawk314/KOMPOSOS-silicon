# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 James Ray Hawkins
#
# Categorical module -- compatibility shim + pure math.
#
# In KOMPOSOS-IV, the core types (Object, Morphism, Category) live in core/.
# This module re-exports them for backward compatibility and provides
# the pure math categorical modules (Kan extensions, fibrations, etc.).

from core.types import Object, Morphism
from core.category import Category

__all__ = ["Category", "Object", "Morphism"]
