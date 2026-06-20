# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""OPERADUM bridges: glue to KOMPOSOS and (later) the Forge event bus."""

from .komposos_bridge import (
    compile_to_komposos, cost_to_confidence, MorphismGraph,
)
from .round_trip import KomposVerifier, RoundTripResult, MiniCategory

__all__ = [
    "compile_to_komposos", "cost_to_confidence", "MorphismGraph",
    "KomposVerifier", "RoundTripResult", "MiniCategory",
]
