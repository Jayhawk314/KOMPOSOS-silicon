#!/usr/bin/env python3
"""
Hybrid evidence-aware scoring strategy.

Prioritizes: MEASURED > ESTABLISHED > INFERRED > HYPOTHESIS
Uses Bayesian integration when multiple evidence types available.
"""

import sqlite3
import json
from typing import List
from core.types import Prediction
from oracle.strategies import InferenceStrategy
from oracle.bayesian_scorer import BayesianEvidenceScorer, Evidence

DB_PATH = "data/drugs/tier1.db"


class HybridEvidenceStrategy(InferenceStrategy):
    """
    Evidence-aware strategy that combines:
    1. Quantitative measurements (IC50, clinical outcomes)
    2. Established knowledge (FDA, KEGG)
    3. Computational inferences (ESM2, STRING)
    4. Graph coherence (categorical verification)

    Uses Bayesian integration to combine heterogeneous evidence.
    """

    name = "hybrid_evidence"

    def __init__(self, category):
        super().__init__(category)
        self.bayesian = BayesianEvidenceScorer(prior=0.001)
        self._evidence_cache = {}
        self._load_evidence_from_db()

    def _load_evidence_from_db(self):
        """Load evidence tiers and quantitative values from database."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT source_name, target_name, evidence_tier, quantitative_value,
                   value_unit, confidence, metadata
            FROM morphisms
        """)

        for source, target, tier, quant_val, unit, conf, meta_str in cursor.fetchall():
            key = (source, target)

            metadata = json.loads(meta_str) if meta_str else {}

            evidence_list = []

            # Add main evidence
            if quant_val is not None and tier == "MEASURED":
                evidence_list.append(Evidence(
                    evidence_type=unit or "unknown",
                    value=quant_val,
                    confidence=conf,
                    tier=tier
                ))

            # Add NLP extractions if present
            nlp_extractions = metadata.get("nlp_extractions", [])
            for extraction in nlp_extractions:
                evidence_list.append(Evidence(
                    evidence_type=extraction.get("evidence_type", "unknown"),
                    value=extraction.get("value", 0.0),
                    confidence=extraction.get("confidence", 0.5),
                    tier="MEASURED" if extraction.get("confidence", 0) >= 0.7 else "HYPOTHESIS"
                ))

            # Add clinical outcomes
            clinical = metadata.get("clinical_outcomes", {})
            if clinical.get("response_rate"):
                evidence_list.append(Evidence(
                    evidence_type="response_rate",
                    value=clinical["response_rate"],
                    confidence=0.95,
                    tier="MEASURED"
                ))

            # Add genomic data
            genomic = metadata.get("genomic_data", {})
            if genomic.get("mutation_frequency"):
                evidence_list.append(Evidence(
                    evidence_type="mutation_frequency",
                    value=genomic["mutation_frequency"],
                    confidence=0.80,
                    tier="MEASURED"
                ))

            if evidence_list:
                self._evidence_cache[key] = evidence_list

        conn.close()

        print(f"[HybridEvidence] Loaded evidence for {len(self._evidence_cache)} edges")

    def predict(self, source: str, target: str) -> List[Prediction]:
        """
        Score based on best available evidence.

        Priority:
        1. Direct MEASURED evidence (IC50, clinical, genomic)
        2. ESTABLISHED (FDA, KEGG)
        3. INFERRED (ESM2, STRING)
        4. Path-based (composition through intermediates)
        5. HYPOTHESIS (graph coherence only)
        """

        # Check for direct evidence
        direct_evidence = self._evidence_cache.get((source, target), [])

        if direct_evidence:
            # Use Bayesian integration for multiple evidence types
            if len(direct_evidence) > 1:
                posterior = self.bayesian.score(direct_evidence)
                return [Prediction(source, target, posterior, "hybrid_bayesian")]

            # Single high-quality evidence
            ev = direct_evidence[0]
            if ev.tier == "MEASURED":
                # Use confidence based on value
                if ev.evidence_type == "ic50":
                    conf = self.bayesian.likelihood_ic50(ev.value)
                elif ev.evidence_type == "response_rate":
                    conf = self.bayesian.likelihood_response_rate(ev.value, 100)
                elif ev.evidence_type == "mutation_frequency":
                    conf = self.bayesian.likelihood_mutation_freq(ev.value)
                else:
                    conf = ev.confidence

                return [Prediction(source, target, conf, f"measured_{ev.evidence_type}")]

        # Check for path through intermediates
        outgoing, incoming = self._build_morphism_index()

        # For drug-disease: look for Drug -> Protein -> Disease paths
        drug_targets = outgoing.get(source, [])
        disease_proteins = incoming.get(target, [])

        path_evidence = []
        for drug_mor in drug_targets:
            protein = drug_mor.target
            for prot_mor in disease_proteins:
                if prot_mor.source == protein:
                    # Found path!
                    drug_prot_evidence = self._evidence_cache.get((source, protein), [])
                    prot_disease_evidence = self._evidence_cache.get((protein, target), [])

                    combined = drug_prot_evidence + prot_disease_evidence

                    if combined:
                        path_conf = self.bayesian.score(combined)
                        path_evidence.append(path_conf)

        if path_evidence:
            # Return best path
            best_path_conf = max(path_evidence)
            return [Prediction(source, target, best_path_conf, "hybrid_path")]

        # Fallback to graph coherence (low confidence)
        return [Prediction(source, target, 0.10, "hybrid_fallback")]
