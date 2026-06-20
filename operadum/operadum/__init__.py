# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
OPERADUM -- a categorical *design* engine.

The constructive mirror of KOMPOSOS-IV's interpretive engine. KOMPOSOS
interprets (stores relations, verifies claims, factors structure); OPERADUM
constructs (stores operations, generates valid assemblies, synthesizes
artifacts that satisfy a specification).

  KOMPOSOS primitive: the morphism   A -> B          (relate)
  OPERADUM primitive: the operation  (A1..An) -> B   (build)

Both are symmetric-monoidal at the bottom, so an OPERADUM design compiles
into a KOMPOSOS morphism graph: synthesize, then verify.

Formerly named TEKTON / SYNTHESIS-I.
"""

from .core.operad import Operad
from .core.types import Colour, Operation, Composite, Interface, Spec
from .core.enrichment import (
    ResourceMonoid,
    Figure,
    FigureProfile,
    GENERAL_FIGURE_PROFILE,
    ADDITIVE_COST,
    MAX_CAPACITY,
    MULTISET_MATERIALS,
    TROPICAL,
    LINEAR_TOKENS,
    GENERAL_FIGURES,
    SAFETY_FIRST,
    COMPLIANCE_FIRST,
    FASTEST_RECOVERY,
    LEAST_DISRUPTIVE,
    EVIDENCE_FIRST,
    SUSTAINABILITY_FIRST,
    DRUG_PORTFOLIO,
    get_resource_algebra,
)
from .core.linear import (
    LinearChecker, LinearJudgement, Atom, Tensor, Lolli, OfCourse,
    operation_signature, composite_signature,
)
from .core.polytope import Polytope
from .core.prop import PROP, CopyError
from .core.formal_coherence import CoherenceProver, Proof, catalan
from .gate.pattern_miner import PatternMiner, Pattern
from .gate.self_observer import SelfObserver, SelfReport
from .gate.semantic_gate import SemanticGate, VerifiedDesign, enumerate_designs
from .gate.diagram_synth import synthesize_diagram, VerifiedDiagram, truth_table_validator
from .core.diagram import Diagram, Source
from .core.plugin_generator import PluginGenerator
from .core.serialization import to_wiring_dsl, parse_wiring, design_to_json
from .forge.core import Forge, CapabilityError
from .forge.plugin import Plugin
from .forge.plugins import (
    ComponentStorePlugin, WrightPlugin, DaedalusPlugin, PolytopePlugin,
)
from .agent import Agent
from .domains.base import DomainPlugin, GroundTruthCase
from .domains import (
    DOMAINS, SynthesisDesignDomain, ComputePipelineDomain,
    ProgramSynthesisDomain, QuantumCircuitDomain, ManufacturingDomain,
    LogicCircuitDomain, TopologicalNetworkDomain, MaterialsDomain,
)
from .bridges.komposos_bridge import compile_to_komposos, MorphismGraph
from .bridges.round_trip import KomposVerifier, RoundTripResult
from .wright.engine import Wright
from .wright.schema import BuildResult, Construction, Verdict, Certificate
from .wright.solver import Solver
from .daedalus_core import Daedalus, SearchResult
from .world_model import (
    WorldState,
    WorldPrediction,
    WorldAction,
    ActionChoice,
    RuleWorldModel,
)
from .integrations.komposos_drug_world import (
    DEFAULT_KOMPOSOS_CHEM_TB_PATH,
    ScoreResult,
    KompososDrugEvidenceClient,
    initial_drug_state,
    build_drug_world_model,
)
from .integrations.komposos_pharm_evidence import (
    DEFAULT_KOMPOSOS_PHARM_PATH,
    KompososPharmEvidenceProvider,
    PharmPair,
    pair_from_candidate,
    pharm_candidate,
)
from .integrations.pronoia_pharm_loop import (
    PharmScoreConfig,
    PharmPredictionLoop,
    PharmPredictionSlate,
    pharm_evidence_strength,
    rank_pharm_candidates_with_pronoia,
    score_pharm_report_v2,
)

__version__ = "0.3.0"

__all__ = [
    "Operad",
    "Colour", "Operation", "Composite", "Interface", "Spec",
    "ResourceMonoid", "Figure", "FigureProfile", "GENERAL_FIGURE_PROFILE",
    "ADDITIVE_COST", "MAX_CAPACITY", "MULTISET_MATERIALS",
    "TROPICAL", "LINEAR_TOKENS", "GENERAL_FIGURES", "SAFETY_FIRST",
    "COMPLIANCE_FIRST", "FASTEST_RECOVERY", "LEAST_DISRUPTIVE",
    "EVIDENCE_FIRST", "SUSTAINABILITY_FIRST", "DRUG_PORTFOLIO",
    "get_resource_algebra",
    # Phase 2: linear logic + generative search
    "LinearChecker", "LinearJudgement", "Atom", "Tensor", "Lolli", "OfCourse",
    "operation_signature", "composite_signature",
    "Daedalus", "SearchResult", "Solver",
    # Phase 3: higher structure, coherence, patterns
    "Polytope", "PROP", "CopyError", "CoherenceProver", "Proof", "catalan",
    "PatternMiner", "Pattern", "Certificate",
    # Domains + semantic gate + KOMPOSOS round-trip
    "DomainPlugin", "GroundTruthCase", "DOMAINS",
    "SynthesisDesignDomain", "ComputePipelineDomain", "ProgramSynthesisDomain",
    "QuantumCircuitDomain", "ManufacturingDomain", "LogicCircuitDomain",
    "TopologicalNetworkDomain", "MaterialsDomain",
    "SemanticGate", "VerifiedDesign", "enumerate_designs",
    "Diagram", "Source", "synthesize_diagram", "VerifiedDiagram", "truth_table_validator",
    "compile_to_komposos", "MorphismGraph", "KomposVerifier", "RoundTripResult",
    # Phase 4: self-construction & learning
    "SelfObserver", "SelfReport", "PluginGenerator",
    # Layer 1 (Forge) + unified Agent + Phase 5 (DSL / serialization)
    "Forge", "CapabilityError", "Plugin", "Agent",
    "ComponentStorePlugin", "WrightPlugin", "DaedalusPlugin", "PolytopePlugin",
    "to_wiring_dsl", "parse_wiring", "design_to_json",
    "Wright", "BuildResult", "Construction", "Verdict",
    # Lightweight world model shell
    "WorldState", "WorldPrediction", "WorldAction", "ActionChoice",
    "RuleWorldModel",
    # Drug world-model integration
    "DEFAULT_KOMPOSOS_CHEM_TB_PATH", "ScoreResult",
    "KompososDrugEvidenceClient", "initial_drug_state", "build_drug_world_model",
    "DEFAULT_KOMPOSOS_PHARM_PATH", "KompososPharmEvidenceProvider",
    "PharmPair", "pair_from_candidate", "pharm_candidate",
    "PharmScoreConfig", "PharmPredictionLoop", "PharmPredictionSlate",
    "pharm_evidence_strength", "rank_pharm_candidates_with_pronoia",
    "score_pharm_report_v2",
]
