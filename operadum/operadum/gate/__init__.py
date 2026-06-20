# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""OPERADUM Dual Gate: TYPE (realizability) + RES (resource soundness)."""

from .type_engine import TypeEngine
from .res_engine import ResEngine
from .pattern_miner import PatternMiner, Pattern
from .self_observer import SelfObserver, SelfReport
from .semantic_gate import SemanticGate, VerifiedDesign, enumerate_designs
from .diagram_synth import synthesize_diagram, VerifiedDiagram, truth_table_validator

__all__ = [
    "TypeEngine", "ResEngine", "PatternMiner", "Pattern",
    "SelfObserver", "SelfReport",
    "SemanticGate", "VerifiedDesign", "enumerate_designs",
    "synthesize_diagram", "VerifiedDiagram", "truth_table_validator",
]
