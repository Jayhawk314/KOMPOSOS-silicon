# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""OPERADUM core runtime: the fused operadic engine (Layer 2)."""

from .operad import Operad
from .types import Colour, Operation, Composite, Interface, Spec, ResourceValue
from .enrichment import (
    ResourceMonoid, ResourceError, Figure, FigureProfile, GENERAL_FIGURE_PROFILE,
    ADDITIVE_COST, MAX_CAPACITY, MULTISET_MATERIALS, TROPICAL, LINEAR_TOKENS,
    GENERAL_FIGURES, SAFETY_FIRST, COMPLIANCE_FIRST, FASTEST_RECOVERY,
    LEAST_DISRUPTIVE, EVIDENCE_FIRST, SUSTAINABILITY_FIRST,
    get_resource_algebra,
)
from .hooks import HookRegistry, EVENTS
from .linear import (
    LinearChecker, LinearJudgement, Atom, Tensor, Lolli, OfCourse,
    operation_signature, composite_signature, tensor,
)
from .polytope import Polytope
from .prop import PROP, CopyError
from .formal_coherence import CoherenceProver, Proof, catalan
from .plugin_generator import PluginGenerator
from .diagram import Diagram, Source

__all__ = [
    "Operad",
    "Colour", "Operation", "Composite", "Interface", "Spec", "ResourceValue",
    "ResourceMonoid", "ResourceError", "Figure", "FigureProfile",
    "GENERAL_FIGURE_PROFILE",
    "ADDITIVE_COST", "MAX_CAPACITY", "MULTISET_MATERIALS", "TROPICAL",
    "LINEAR_TOKENS", "GENERAL_FIGURES", "SAFETY_FIRST", "COMPLIANCE_FIRST",
    "FASTEST_RECOVERY", "LEAST_DISRUPTIVE", "EVIDENCE_FIRST",
    "SUSTAINABILITY_FIRST", "get_resource_algebra",
    "HookRegistry", "EVENTS",
    "LinearChecker", "LinearJudgement", "Atom", "Tensor", "Lolli", "OfCourse",
    "operation_signature", "composite_signature", "tensor",
    "Polytope", "PROP", "CopyError", "CoherenceProver", "Proof", "catalan",
    "PluginGenerator", "Diagram", "Source",
]
