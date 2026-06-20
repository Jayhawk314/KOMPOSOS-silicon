#!/usr/bin/env python3
"""Bayesian evidence integration for combining heterogeneous data sources."""

import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class Evidence:
    """Single piece of evidence."""
    evidence_type: str
    value: float
    confidence: float
    tier: str

class BayesianEvidenceScorer:
    """
    Bayesian approach to combining evidence from multiple sources.

    P(edge is true | all evidence) ∝ P(all evidence | edge is true) × P(edge is true)
    """

    def __init__(self, prior: float = 0.001):
        """
        Args:
            prior: Base rate of true drug-disease relationships (~0.001)
        """
        self.prior = prior

    def likelihood_ic50(self, ic50_um: float) -> float:
        """Likelihood of seeing this IC50 if edge is true."""
        if ic50_um < 0.01:
            return 0.98
        elif ic50_um < 0.1:
            return 0.95
        elif ic50_um < 1.0:
            return 0.80
        elif ic50_um < 10.0:
            return 0.50
        else:
            return 0.20

    def likelihood_response_rate(self, rr: float, n: int) -> float:
        """Likelihood based on clinical response rate."""
        if rr > 0.50 and n > 100:
            return 0.92
        elif rr > 0.30 and n > 50:
            return 0.75
        elif rr > 0.15:
            return 0.55
        else:
            return 0.30

    def likelihood_mutation_freq(self, freq: float) -> float:
        """Likelihood based on mutation frequency."""
        if freq > 0.30:
            return 0.85
        elif freq > 0.15:
            return 0.70
        elif freq > 0.05:
            return 0.50
        else:
            return 0.25

    def likelihood_graph_coherence(self, coherence: float) -> float:
        """Likelihood from graph topology."""
        return 0.25 + 0.40 * coherence  # 0.25-0.65 range

    def update_posterior(self, prior: float, likelihood: float) -> float:
        """Bayes update: P(H|E) = P(E|H) × P(H) / P(E)."""
        p_not_true = 1 - prior
        p_evidence = likelihood * prior + 0.5 * p_not_true
        return (likelihood * prior) / p_evidence if p_evidence > 0 else prior

    def score(self, evidence_list: List[Evidence]) -> float:
        """
        Compute posterior probability given all evidence.

        Args:
            evidence_list: List of Evidence objects

        Returns:
            Posterior probability (0-1)
        """
        posterior = self.prior

        for ev in evidence_list:
            if ev.tier == "MEASURED":
                if ev.evidence_type == "ic50":
                    likelihood = self.likelihood_ic50(ev.value)
                elif ev.evidence_type == "response_rate":
                    likelihood = self.likelihood_response_rate(ev.value, 100)
                elif ev.evidence_type == "mutation_frequency":
                    likelihood = self.likelihood_mutation_freq(ev.value)
                else:
                    likelihood = 0.60  # Default for measured data

                posterior = self.update_posterior(posterior, likelihood)

            elif ev.tier in ["HYPOTHESIS", "SPECULATIVE"]:
                likelihood = self.likelihood_graph_coherence(ev.confidence)
                posterior = self.update_posterior(posterior, likelihood)

        return posterior
