# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
KOMPOSOS-III Geometry Layer

Implements geometric analysis of knowledge graphs using:
- Ollivier-Ricci curvature for local geometry detection
- Discrete Ricci flow for structure revelation
- Thurston-style geometric decomposition

Key insight: Different regions of a knowledge graph have different
natural geometries (hyperbolic for hierarchies, spherical for clusters,
euclidean for chains). This layer reveals that structure.
"""

from .ricci import (
    OllivierRicciCurvature,
    CurvatureResult,
    GeometryType,
    compute_graph_curvature,
)

from .flow import (
    DiscreteRicciFlow,
    DecompositionResult,
    GeometricRegion,
    FlowStep,
    run_ricci_flow,
)

# Protein structure prediction (if available)
try:
    from .contact_prediction import (
        CompositionalContactPredictor,
        ContactMap,
        MotifPattern,
        PredictionResult
    )
    from .structure_reconstruction import (
        StructureReconstructor,
        Structure3D,
        DistanceConstraint,
        reconstruct_from_contact_map
    )
    from .protein_structure_pipeline import (
        KOMPOSOSStructurePipeline,
        StructurePredictionResult,
        predict_protein_structure
    )
    STRUCTURE_PREDICTION_AVAILABLE = True
except ImportError as e:
    STRUCTURE_PREDICTION_AVAILABLE = False
    # Silently continue - these are optional modules

# Spectral analysis (if available)
try:
    from .spectral import SpectralGraphAnalyzer, analyze_spectrum
    SPECTRAL_AVAILABLE = True
except ImportError:
    SPECTRAL_AVAILABLE = False

__all__ = [
    # Curvature
    "OllivierRicciCurvature",
    "CurvatureResult",
    "GeometryType",
    "compute_graph_curvature",
    # Ricci Flow
    "DiscreteRicciFlow",
    "DecompositionResult",
    "GeometricRegion",
    "FlowStep",
    "run_ricci_flow",
]

# Add structure prediction if available
if STRUCTURE_PREDICTION_AVAILABLE:
    __all__.extend([
        "CompositionalContactPredictor",
        "ContactMap",
        "MotifPattern",
        "PredictionResult",
        "StructureReconstructor",
        "Structure3D",
        "DistanceConstraint",
        "reconstruct_from_contact_map",
        "KOMPOSOSStructurePipeline",
        "StructurePredictionResult",
        "predict_protein_structure",
    ])

# Add spectral if available
if SPECTRAL_AVAILABLE:
    __all__.extend(["SpectralGraphAnalyzer", "analyze_spectrum"])

# ESMFold + ZFC verification pipeline (if available)
try:
    from .zfc_structure_verifier import StructureZFCBridge, StructureVerificationResult
    from .esmfold_zfc_pipeline import ESMFoldZFCPipeline, ESMFoldZFCResult
    ESMFOLD_ZFC_AVAILABLE = True
    __all__.extend([
        "StructureZFCBridge", "StructureVerificationResult",
        "ESMFoldZFCPipeline", "ESMFoldZFCResult",
    ])
except ImportError:
    ESMFOLD_ZFC_AVAILABLE = False

# Categorical fragment assembly (if available)
try:
    from .fragment_category import (
        FragmentAssembler,
        FragmentCategory,
        FragmentAssemblyResult,
        PositionedFragment,
        SpatialMorphism,
    )
    FRAGMENT_ASSEMBLY_AVAILABLE = True
    __all__.extend([
        "FragmentAssembler", "FragmentCategory", "FragmentAssemblyResult",
        "PositionedFragment", "SpatialMorphism",
    ])
except ImportError:
    FRAGMENT_ASSEMBLY_AVAILABLE = False
