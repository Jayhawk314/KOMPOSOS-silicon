#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Evidence tier system for KOMPOSOS-IV-PHARM.

Distinguishes measured biological data from graph-inferred relationships.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class EvidenceTier(Enum):
    """Evidence quality tiers from highest to lowest."""
    MEASURED = "MEASURED"           # IC50, clinical outcomes, mutation frequencies
    ESTABLISHED = "ESTABLISHED"     # FDA approvals, KEGG canonical pathways
    INFERRED = "INFERRED"          # ESM2, STRING PPI, computed similarities
    HYPOTHESIS = "HYPOTHESIS"       # PubMed citations (AGREE/PARTIAL)
    SPECULATIVE = "SPECULATIVE"     # PubMed ORPHAN (isolated edges)
    NOISE = "NOISE"                # PubMed REJECT (contradictory)


@dataclass
class EvidenceAnnotation:
    """
    Structured evidence annotation for a morphism.

    Separates quantitative measurements from graph-derived confidence.
    """
    tier: EvidenceTier
    source: str                    # "ChEMBL IC50", "FDA approval", "PMID:12345"
    quantitative_value: Optional[float] = None  # IC50 in μM, mutation freq, etc.
    unit: Optional[str] = None     # "μM", "percentage", "hazard_ratio"
    sample_size: Optional[int] = None
    p_value: Optional[float] = None
    confidence_lower: Optional[float] = None  # CI lower bound
    confidence_upper: Optional[float] = None  # CI upper bound

    def display_string(self) -> str:
        """Human-readable evidence string for UI display."""
        if self.tier == EvidenceTier.MEASURED and self.quantitative_value is not None:
            value_str = f"{self.quantitative_value:.3g} {self.unit or ''}"
            if self.confidence_lower is not None and self.confidence_upper is not None:
                value_str += f" (95% CI: {self.confidence_lower:.3g}-{self.confidence_upper:.3g})"
            return f"{self.tier.value}: {self.source} = {value_str}"

        elif self.tier == EvidenceTier.HYPOTHESIS:
            return f"{self.tier.value}: {self.source} (not quantified - graph coherence only)"

        else:
            return f"{self.tier.value}: {self.source}"

    def to_dict(self) -> dict:
        """Serialize to dictionary for database storage."""
        return {
            "tier": self.tier.value,
            "source": self.source,
            "quantitative_value": self.quantitative_value,
            "unit": self.unit,
            "sample_size": self.sample_size,
            "p_value": self.p_value,
            "confidence_lower": self.confidence_lower,
            "confidence_upper": self.confidence_upper,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvidenceAnnotation":
        """Deserialize from dictionary."""
        return cls(
            tier=EvidenceTier(data["tier"]),
            source=data["source"],
            quantitative_value=data.get("quantitative_value"),
            unit=data.get("unit"),
            sample_size=data.get("sample_size"),
            p_value=data.get("p_value"),
            confidence_lower=data.get("confidence_lower"),
            confidence_upper=data.get("confidence_upper"),
        )


def classify_tier_from_provenance(provenance: str, metadata: dict, confidence: float) -> EvidenceTier:
    """
    Classify a morphism into an evidence tier based on its provenance.

    Args:
        provenance: Provenance string (e.g., "ChEMBL IC50", "PMID:12345")
        metadata: Morphism metadata dict (may contain categorical_delta)
        confidence: Edge confidence (0-1)

    Returns:
        EvidenceTier enum value
    """
    prov_upper = provenance.upper()

    # MEASURED: Direct experimental measurements
    if any(keyword in prov_upper for keyword in ["CHEMBL", "IC50", "KI", "KD", "ABPP"]):
        return EvidenceTier.MEASURED

    # ESTABLISHED: Regulatory/canonical databases
    if any(keyword in prov_upper for keyword in ["FDA", "KEGG PATHWAY", "NDA", "BLA"]):
        return EvidenceTier.ESTABLISHED

    # INFERRED: Computational/similarity-based
    if any(keyword in prov_upper for keyword in ["ESM2", "ESM-2", "STRING PPI", "SIMILARITY"]):
        return EvidenceTier.INFERRED

    # Check categorical verification metadata for PubMed edges
    categorical_delta = metadata.get("categorical_delta", "")

    if categorical_delta == "REJECT":
        return EvidenceTier.NOISE

    elif categorical_delta == "ORPHAN":
        return EvidenceTier.SPECULATIVE

    elif categorical_delta in ["AGREE", "PARTIAL"]:
        return EvidenceTier.HYPOTHESIS

    # Fallback based on confidence
    if confidence >= 0.70:
        return EvidenceTier.ESTABLISHED
    elif confidence >= 0.40:
        return EvidenceTier.INFERRED
    else:
        return EvidenceTier.HYPOTHESIS


def tier_priority(tier: EvidenceTier) -> int:
    """
    Get numeric priority for a tier (lower = higher priority).

    Used for sorting/ranking evidence.
    """
    priority_map = {
        EvidenceTier.MEASURED: 1,
        EvidenceTier.ESTABLISHED: 2,
        EvidenceTier.INFERRED: 3,
        EvidenceTier.HYPOTHESIS: 4,
        EvidenceTier.SPECULATIVE: 5,
        EvidenceTier.NOISE: 6,
    }
    return priority_map[tier]
