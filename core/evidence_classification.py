# SPDX-License-Identifier: Apache-2.0
"""Evidence source/status classification for audit trails.

This module does not mutate stored evidence tiers. It derives separate fields
from provenance and metadata so UI/reports can distinguish where evidence came
from and how directly it has been validated.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class EvidenceClassification:
    source_type: str
    validation_status: str
    citation_status: str
    quantitative_status: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _metadata_text(metadata: Any) -> str:
    if metadata is None:
        return ""
    if isinstance(metadata, str):
        return metadata
    try:
        return json.dumps(metadata, sort_keys=True)
    except TypeError:
        return str(metadata)


def extract_pmids(*texts: str) -> set[str]:
    pmids: set[str] = set()
    for text in texts:
        pmids.update(re.findall(r"PMID:?\s*(\d+)", text or ""))
        pmids.update(re.findall(r"\bpmid['\"]?\s*[:=]\s*['\"]?(\d+)", text or "", re.IGNORECASE))
    return pmids


def classify_evidence(
    provenance: str | None,
    metadata: Any = None,
    evidence_tier: str | None = None,
    quantitative_value: float | None = None,
) -> EvidenceClassification:
    """Derive source type and validation status without changing the DB tier."""
    provenance = provenance or ""
    meta_text = _metadata_text(metadata)
    text = f"{provenance} {meta_text}"
    lower = text.lower()

    if "fda:" in lower or "fda approved" in lower:
        source_type = "regulatory_label"
        validation_status = "established_source"
    elif "chembl:" in lower:
        source_type = "bioactivity_database"
        validation_status = "database_record"
    elif "kegg:" in lower:
        source_type = "pathway_database"
        validation_status = "database_record"
    elif "abpp" in lower:
        source_type = "experimental_binding"
        validation_status = "assay_curated"
    elif "esm2:" in lower:
        source_type = "protein_similarity_model"
        validation_status = "computational_inference"
    elif "string" in lower or "ppi:" in lower:
        source_type = "protein_interaction_database"
        validation_status = "computational_or_database_inference"
    elif "opentargets" in lower:
        source_type = "target_disease_database"
        validation_status = "database_record"
    elif "tcga" in lower or "depmap" in lower or "cbioportal" in lower:
        source_type = "omics_database"
        validation_status = "database_record"
    elif "cancer_proteins" in lower or "aml_proteins" in lower:
        source_type = "manual_curated_biology"
        validation_status = "curated_assertion"
    elif "pubmed co-mention" in lower:
        source_type = "literature_co_mention"
        validation_status = "unverified_literature"
    elif "pmid" in lower or "literature" in lower:
        source_type = "literature_citation"
        validation_status = "citation_unverified"
    elif "via_drug" in lower or "drug-target-disease" in lower:
        source_type = "label_derived_bridge"
        validation_status = "label_derived_inference"
    else:
        source_type = "unknown_or_internal"
        validation_status = "unclassified"

    pmids = extract_pmids(provenance, meta_text)
    has_context = any(key in lower for key in ("context", "abstract", "snippet"))
    if pmids and has_context:
        citation_status = "pmid_with_context"
    elif pmids:
        citation_status = "pmid_identifier_only"
    elif provenance and provenance != "unknown":
        citation_status = "non_pmid_source"
    else:
        citation_status = "no_source"

    has_nlp = "nlp_extractions" in lower
    if quantitative_value is not None:
        quantitative_status = "structured_quantitative_value"
    elif has_nlp:
        quantitative_status = "nlp_quantitative_candidate"
    else:
        quantitative_status = "no_quantitative_value"

    if evidence_tier == "MEASURED" and validation_status in {
        "computational_inference",
        "unverified_literature",
        "citation_unverified",
        "label_derived_inference",
    }:
        validation_status = f"{validation_status}_tier_mismatch"

    return EvidenceClassification(
        source_type=source_type,
        validation_status=validation_status,
        citation_status=citation_status,
        quantitative_status=quantitative_status,
    )
