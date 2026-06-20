# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-IV Commercial License (see LICENSE-COMMERCIAL file)

"""
COG Schema — Cognitive domain types for KOMPOSOS-IV-COG.

Defines the objects, morphisms, and result types for the cognitive
knowledge layer. These are thin wrappers that map to the underlying
Object/Morphism types in core/types.py.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


class ConceptType(Enum):
    """Types of cognitive objects."""
    CONCEPT = "concept"
    CLAIM = "claim"
    EVIDENCE = "evidence"
    RULE = "rule"
    CONTEXT = "context"
    GOAL = "goal"
    # Security-specific
    DATA_SOURCE = "data_source"       # untrusted input, API param, file upload
    SINK = "sink"                     # SQL query, shell exec, HTML render, file write
    SANITIZER = "sanitizer"           # input validator, escaper, parameterizer
    AUTH_CHECK = "auth_check"         # authentication/authorization gate
    TRUST_BOUNDARY = "trust_boundary" # network boundary, process boundary
    COMPONENT = "component"           # module, service, endpoint, function


class RelationType(Enum):
    """Types of cognitive morphisms."""
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    ENTAILS = "entails"
    REQUIRES = "requires"
    SIMILAR_TO = "similar_to"
    PART_OF = "part_of"
    CAUSES = "causes"
    PRECEDES = "precedes"
    INSTANTIATES = "instantiates"
    REFINES = "refines"
    # Security-specific
    FLOWS_TO = "flows_to"       # data flow edge (A's output reaches B)
    SANITIZES = "sanitizes"     # sanitizer cleans data for a sink type
    GUARDS = "guards"           # auth check protects a resource
    TRUSTS = "trusts"           # A trusts B's output (no validation)
    EXPOSES = "exposes"         # A makes B reachable from outside
    MITIGATES = "mitigates"     # control reduces a risk
    # Supply chain
    DEPENDS_ON = "depends_on"   # package A depends on package B


class VerificationStatus(Enum):
    """Result of verifying a claim through the dual engine."""
    AGREE = "agree"
    ORPHAN = "orphan"
    HOLLOW = "hollow"
    REJECT = "reject"
    PENDING = "pending"
    PARTIAL = "partial"


@dataclass
class CogConcept:
    """A concept in the cognitive graph. Maps to StoredObject."""
    name: str
    concept_type: ConceptType = ConceptType.CONCEPT
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: str = "agent"


@dataclass
class CogRelation:
    """A relation in the cognitive graph. Maps to StoredMorphism."""
    source: str
    target: str
    relation_type: RelationType
    confidence: float = 0.7
    evidence: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: str = "agent"


@dataclass
class CogClaim:
    """A claim to be verified by the cognitive engine."""
    source: str
    target: str
    relation: str
    confidence: float = 0.5
    context: str = ""
    evidence: List[str] = field(default_factory=list)


@dataclass
class CheckResult:
    """Result of checking a claim through tiered verification."""
    claim: CogClaim
    status: VerificationStatus
    tier_reached: int
    confidence: float
    energy: float
    explanation: str
    supporting_paths: List[List[str]]
    contradictions: List[str]
    dual_result: Optional[Dict] = None
    topology: Optional[Dict] = None
    computation_time_ms: float = 0.0


@dataclass
class CoherenceResult:
    """Result of multi-source coherence check."""
    is_coherent: bool
    coherence_score: float
    violations: List[Dict[str, Any]]
    explanation: str


@dataclass
class EnergyResult:
    """Result of energy computation for a claim."""
    total_energy: float
    components: Dict[str, float]
    interpretation: str
