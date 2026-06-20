# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""Domains: typed, executable primitive sets + goal specs for the generator."""

from .numeric import NUMERIC_PRIMITIVES, NUMERIC_GOALS
from .circuits import CIRCUIT_PRIMITIVES, CIRCUIT_GOALS, NAND

__all__ = [
    "NUMERIC_PRIMITIVES", "NUMERIC_GOALS",
    "CIRCUIT_PRIMITIVES", "CIRCUIT_GOALS", "NAND",
]
