# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
Binding Evidence Strategy
=========================

Scores Drug->Disease pairs by aggregating binding/chemistry evidence
from multiple molecular bridges:

1. ABPP Bridge - experimental IC50/engagement data
2. Boltz2 Bridge - heuristic binding prediction (fallback mode)
3. Pfam Domain Mapper - domain-family matching (kinase inhibitor -> kinase domain)
4. Drug Properties - Lipinski drug-likeness and drug-target molecular compatibility
5. Molecular Bridge Scorers - solubility/steric/reactivity scoring

For each Drug->Disease pair, the strategy finds disease-connected
intermediate proteins (Drug->Protein->Disease paths) and scores binding
evidence for each Drug->Protein link. The best relevant binding score
becomes the strategy confidence.

This wires existing chemistry/molecular code from KOMPOSOS-III into the
drug repurposing scoring pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from oracle.prediction import Prediction, PredictionType, ConfidenceLevel
from oracle.strategies import InferenceStrategy, REPURPOSING_INTERMEDIATE_TYPES
from core.category import Category


class BindingEvidenceStrategy(InferenceStrategy):
    """
    Score drug-disease pairs using molecular/chemistry binding evidence.

    Aggregates signals from ABPP experimental data, Boltz2 heuristic
    binding, Pfam domain matching, drug-likeness, and drug-target
    molecular compatibility.
    """

    name = "binding_evidence"

    def __init__(self, category: Category):
        super().__init__(category)
        self._abpp = None
        self._boltz2 = None
        self._outgoing = None
        self._incoming = None
        self._drug_props_loaded = False
        self._drug_props_module = None

    # ----- lazy initialisation (avoid import cost if never called) -----

    def _get_abpp(self):
        if self._abpp is None:
            try:
                from abpp_bridge import ABPPBridge
                self._abpp = ABPPBridge()
            except Exception:
                self._abpp = False  # sentinel: tried and failed
        return self._abpp if self._abpp is not False else None

    def _get_boltz2(self):
        if self._boltz2 is None:
            try:
                from boltz2_bridge import Boltz2Bridge
                self._boltz2 = Boltz2Bridge()
            except Exception:
                self._boltz2 = False
        return self._boltz2 if self._boltz2 is not False else None

    def _get_drug_props(self):
        if not self._drug_props_loaded:
            try:
                import data.drugs.drug_properties as dp
                self._drug_props_module = dp
            except Exception:
                self._drug_props_module = None
            self._drug_props_loaded = True
        return self._drug_props_module

    def _get_mol_scorers(self):
        """Lazy import of molecular_bridge interaction scorers."""
        if not hasattr(self, '_mol_scorers'):
            try:
                from molecular_bridge.interaction_scoring import (
                    score_solubility_compatibility,
                    score_steric_compatibility,
                    score_reactivity_risk,
                )
                self._mol_scorers = {
                    'solubility': score_solubility_compatibility,
                    'steric': score_steric_compatibility,
                    'reactivity': score_reactivity_risk,
                }
            except Exception:
                self._mol_scorers = None
        return self._mol_scorers

    def _get_pfam_mapper(self):
        """Lazy import of PfamDomainMapper for domain classification."""
        if not hasattr(self, '_pfam_mapper'):
            try:
                from chemistry.pfam_domain_mapper import PfamDomain
                self._pfam_domain_cls = PfamDomain
                self._pfam_mapper = True  # Available
            except Exception:
                self._pfam_mapper = None
                self._pfam_domain_cls = None
        return self._pfam_mapper

    def _ensure_indices(self):
        if self._outgoing is None:
            self._outgoing, self._incoming = self._build_morphism_index()

    # ----- core predict method -----

    def predict(self, source: str, target: str) -> List[Prediction]:
        """
        Predict Drug->Disease relationship via binding evidence.

        Only produces predictions for Drug->Disease pairs (object types
        checked). For each intermediate protein P on an observed
        Drug->P->Disease path, aggregates binding evidence and returns the
        best. Binding to an unrelated target is not disease evidence.
        """
        source_obj = self.category.get(source)
        target_obj = self.category.get(target)
        if not source_obj or not target_obj:
            return []
        if source_obj.type_name != "Drug" or target_obj.type_name != "Disease":
            return []

        self._ensure_indices()

        # Restrict molecular support to proteins connected to this disease.
        drug_morphisms = self._outgoing.get(source, [])
        protein_targets = []
        for mor in drug_morphisms:
            tgt = self.category.get(mor.target)
            if tgt and tgt.type_name in REPURPOSING_INTERMEDIATE_TYPES:
                disease_links = [
                    link for link in self._outgoing.get(mor.target, [])
                    if link.target == target
                ]
                if disease_links:
                    protein_targets.append(
                        (mor.target, mor.confidence, disease_links)
                    )

        if not protein_targets:
            return []

        # Score binding evidence for each Drug->Protein link
        best_score = 0.0
        best_protein = None
        best_evidence: Dict = {}
        all_scores: List[Tuple[str, float, Dict]] = []

        for protein_name, edge_confidence, disease_links in protein_targets:
            score, evidence = self._score_drug_protein(
                source, protein_name, edge_confidence
            )
            evidence["disease_links"] = [
                {
                    "relation": link.name,
                    "confidence": link.confidence,
                }
                for link in disease_links
            ]
            all_scores.append((protein_name, score, evidence))
            if score > best_score:
                best_score = score
                best_protein = protein_name
                best_evidence = evidence

        if best_score <= 0.0:
            return []

        # Build prediction
        evidence_summary = {
            "best_target": best_protein,
            "best_score": round(best_score, 4),
            "binding_details": best_evidence,
            "targets_scored": len(all_scores),
            "all_target_scores": {
                p: round(s, 4) for p, s, _ in all_scores if s > 0
            },
        }

        confidence_level = ConfidenceLevel.HIGH if best_score > 0.7 else (
            ConfidenceLevel.MEDIUM if best_score > 0.4 else ConfidenceLevel.LOW
        )

        return [Prediction(
            source=source,
            target=target,
            predicted_relation="binding_supported",
            prediction_type=PredictionType.BINDING_EVIDENCE,
            strategy_name=self.name,
            confidence=best_score,
            reasoning=(
                f"Binding evidence for {source}->{best_protein}: "
                f"{', '.join(k for k, v in best_evidence.items() if v)}"
            ),
            evidence=evidence_summary,
        )]

    # ----- per-target scoring -----

    def _score_drug_protein(
        self, drug: str, protein: str, edge_confidence: float
    ) -> Tuple[float, Dict]:
        """
        Score binding evidence for a single Drug->Protein pair.

        Combines signals from all available bridges.  Each signal
        contributes to the overall score with diminishing returns.
        """
        evidence: Dict = {}
        component_scores: List[float] = []

        # 1. ABPP experimental data (highest priority -- real IC50)
        abpp_score = self._score_abpp(drug, protein)
        evidence["abpp"] = abpp_score
        if abpp_score is not None:
            component_scores.append(("abpp", abpp_score, 0.30))

        # 2. Boltz2 heuristic binding prediction
        boltz_score = self._score_boltz2(drug, protein)
        evidence["boltz2"] = boltz_score
        if boltz_score is not None:
            component_scores.append(("boltz2", boltz_score, 0.10))

        # 3. Drug-likeness (Lipinski)
        druglike_score = self._score_drug_likeness(drug)
        evidence["drug_likeness"] = druglike_score
        if druglike_score is not None:
            component_scores.append(("drug_likeness", druglike_score, 0.10))

        # 4. Drug-target molecular compatibility (logP, H-bond)
        compat_score = self._score_molecular_compatibility(drug, protein)
        evidence["molecular_compatibility"] = compat_score
        if compat_score is not None:
            component_scores.append(("compatibility", compat_score, 0.10))

        # 5. Molecular bridge scorers (solubility, steric, reactivity)
        molbridge_score = self._score_molecular_bridge(drug, protein)
        evidence["molecular_bridge"] = molbridge_score
        if molbridge_score is not None:
            component_scores.append(("molecular_bridge", molbridge_score, 0.10))

        # 6. Pfam domain matching (kinase inhibitor -> kinase domain)
        pfam_score = self._score_pfam_domain_match(drug, protein)
        evidence["pfam_domain"] = pfam_score
        if pfam_score is not None:
            component_scores.append(("pfam_domain", pfam_score, 0.10))

        # 7. Graph edge confidence (from the Category morphism)
        evidence["edge_confidence"] = edge_confidence
        component_scores.append(("edge", edge_confidence, 0.20))

        if not component_scores:
            return 0.0, evidence

        # Weighted average of available components, renormalised
        total_weight = sum(w for _, _, w in component_scores)
        if total_weight <= 0:
            return 0.0, evidence

        weighted_sum = sum(s * w for _, s, w in component_scores)
        final = weighted_sum / total_weight
        return min(1.0, max(0.0, final)), evidence

    # ----- bridge-specific scorers -----

    def _score_abpp(self, drug: str, protein: str) -> Optional[float]:
        """Check ABPP for experimental IC50/engagement data."""
        abpp = self._get_abpp()
        if abpp is None:
            return None
        result = abpp.check_abpp(drug, protein)
        if result is None:
            return None
        return result.get_engagement_score()

    def _score_boltz2(self, drug: str, protein: str) -> Optional[float]:
        """Get Boltz2 heuristic binding prediction."""
        boltz = self._get_boltz2()
        if boltz is None:
            return None
        try:
            pred = boltz.predict_binding(drug, protein)
            return pred.binding_score if pred else None
        except Exception:
            return None

    def _score_drug_likeness(self, drug: str) -> Optional[float]:
        """Compute Lipinski drug-likeness from drug properties."""
        dp = self._get_drug_props()
        if dp is None:
            return None
        return dp.get_drug_likeness(drug)

    def _score_molecular_compatibility(
        self, drug: str, protein: str
    ) -> Optional[float]:
        """Compute drug-target molecular compatibility."""
        dp = self._get_drug_props()
        if dp is None:
            return None
        return dp.compute_drug_target_compatibility(drug, protein)

    def _score_molecular_bridge(
        self, drug: str, protein: str
    ) -> Optional[float]:
        """
        Run molecular_bridge scorers (solubility, steric, reactivity).

        Creates a synthetic Molecule for the protein target from pocket
        properties, then calls the actual molecular_bridge scoring
        functions on the drug-target pair.
        """
        scorers = self._get_mol_scorers()
        if scorers is None:
            return None
        dp = self._get_drug_props()
        if dp is None:
            return None

        drug_mol = dp.get_drug(drug)
        if drug_mol is None or dp.is_antibody(drug):
            return None

        target_props = dp.get_target_properties(protein)
        if target_props is None:
            return None

        # Build a synthetic Molecule for the target pocket
        from molecular_bridge.molecule_properties import Molecule, MoleculeClass
        target_mol = Molecule(
            name=f"{protein}_pocket",
            formula="",
            pubchem_cid=0,
            cas_number="",
            smiles="",
            molecular_weight=300.0,  # Approximate pocket fragment MW
            functional_groups=["amine", "carbonyl", "hydroxyl"],
            logP=target_props.get("logP_pocket", 2.0),
            hbond_donors=target_props.get("hbd_pocket", 3),
            hbond_acceptors=target_props.get("hba_pocket", 4),
            molecule_class=MoleculeClass.OTHER,
        )

        # Run the 3 relevant scorers
        results = []
        try:
            sol = scorers['solubility'](drug_mol, target_mol)
            results.append(sol.score)
        except Exception:
            pass
        try:
            ster = scorers['steric'](drug_mol, target_mol)
            results.append(ster.score)
        except Exception:
            pass
        try:
            react = scorers['reactivity'](drug_mol, target_mol)
            results.append(react.score)
        except Exception:
            pass

        if not results:
            return None
        return sum(results) / len(results)

    def _score_pfam_domain_match(
        self, drug: str, protein: str
    ) -> Optional[float]:
        """
        Score drug-target domain compatibility using Pfam domain knowledge.

        Uses the PfamDomain dataclass from chemistry/pfam_domain_mapper.py
        and known domain-drug class associations (kinase inhibitor -> kinase
        domain, protease inhibitor -> protease domain, etc.).
        """
        if self._get_pfam_mapper() is None:
            return None
        dp = self._get_drug_props()
        if dp is None:
            return None

        drug_mol = dp.get_drug(drug)
        if drug_mol is None or dp.is_antibody(drug):
            return None

        target_props = dp.get_target_properties(protein)
        if target_props is None:
            return None

        domain = target_props.get("domain", "")
        drug_fg = set(g.lower() for g in drug_mol.functional_groups)

        # Build a PfamDomain object for the match record
        domain_to_pfam = {
            "kinase": ("PF00069", "Pkinase", "Protein kinase domain"),
            "protease": ("PF00089", "Trypsin", "Trypsin-like serine protease"),
            "cyclooxygenase": ("PF00124", "COX", "Cyclooxygenase domain"),
            "reductase": ("PF00106", "Reductase", "Short-chain dehydrogenase/reductase"),
            "deacetylase": ("PF00850", "HDAC", "Histone deacetylase domain"),
            "ubiquitin_ligase": ("PF03145", "CRBN", "Cereblon domain"),
            "bcl2_family": ("PF00452", "Bcl-2", "Bcl-2 family"),
            "gpcr": ("PF00001", "GPCR", "G-protein coupled receptor"),
            "gtpase": ("PF00071", "Ras", "Ras GTPase domain"),
            "immunophilin": ("PF00254", "FKBP", "FK506-binding protein"),
        }

        pfam_info = domain_to_pfam.get(domain)
        if pfam_info:
            # Record the domain match using the PfamDomain dataclass
            _domain_obj = self._pfam_domain_cls(
                accession=pfam_info[0],
                name=pfam_info[1],
                description=pfam_info[2],
                start=0,
                end=300,
            )

        # Score: does the drug's functional group profile match the
        # target's domain family?  Kinase inhibitors have amine/amide
        # for hinge binding, protease inhibitors have hydroxyl for
        # catalytic triad, etc.
        score = 0.5  # baseline

        if domain == "kinase":
            # Kinase inhibitors typically have amine + heterocyclic scaffolds
            kinase_signals = {"amine", "amide", "pyrimidine", "pyridine",
                              "quinazoline", "pyrazole", "indole"}
            overlap = drug_fg & kinase_signals
            score += min(0.4, len(overlap) * 0.1)

        elif domain == "protease":
            protease_signals = {"hydroxyl", "amide", "carboxyl", "tetracycline"}
            overlap = drug_fg & protease_signals
            score += min(0.3, len(overlap) * 0.1)

        elif domain == "cyclooxygenase":
            cox_signals = {"carboxyl", "sulfonamide", "aromatic"}
            overlap = drug_fg & cox_signals
            score += min(0.3, len(overlap) * 0.1)

        elif domain == "gtpase":
            # Covalent KRAS inhibitors need electrophilic warhead
            gtpase_signals = {"acrylamide", "fluoride", "piperazine"}
            overlap = drug_fg & gtpase_signals
            score += min(0.3, len(overlap) * 0.1)

        elif domain == "bcl2_family":
            # BH3 mimetics are large hydrophobic molecules
            bcl2_signals = {"sulfonamide", "chloride", "aromatic", "ether"}
            overlap = drug_fg & bcl2_signals
            score += min(0.3, len(overlap) * 0.1)

        elif domain == "ubiquitin_ligase":
            # IMiDs bind CRBN via glutarimide ring
            crbn_signals = {"glutarimide", "phthalimide", "amide"}
            overlap = drug_fg & crbn_signals
            score += min(0.4, len(overlap) * 0.15)

        elif domain:
            # Generic: reward any functional group overlap with common
            # binding motifs
            generic_signals = {"amine", "amide", "hydroxyl", "carbonyl"}
            overlap = drug_fg & generic_signals
            score += min(0.2, len(overlap) * 0.05)

        return min(1.0, score)
