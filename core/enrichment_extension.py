# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Enrichment Extension: Additional quantale types for KOMPOSOS-IV

Adds quantales from categorical/quantales.py to the core enrichment module.

This activates previously dead code: categorical/quantales.py
"""

from __future__ import annotations

from core.enrichment import MonoidalStructure

# Import additional quantales from categorical/quantales.py
try:
    from categorical.quantales import (
        MULTIPLICATIVE_QUANTALE as CAT_MULTIPLICATIVE,
        ADDITIVE_QUANTALE as CAT_ADDITIVE,
        PROBABILISTIC_QUANTALE as CAT_PROBABILISTIC,
        MAX_QUANTALE as CAT_MAX,
        MIN_QUANTALE as CAT_MIN,
        QUANTALE_REGISTRY,
        get_quantale,
    )

    # Make additional quantales available for import
    __all__ = [
        "CAT_MULTIPLICATIVE",
        "CAT_ADDITIVE",
        "CAT_PROBABILISTIC",
        "CAT_MAX",
        "CAT_MIN",
        "QUANTALE_REGISTRY",
        "get_quantale",
    ]

except ImportError:
    # categorical/quantales.py not available
    __all__ = []
