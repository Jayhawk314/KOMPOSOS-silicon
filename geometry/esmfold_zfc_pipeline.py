# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
ESMFold + ZFC Verification + Pfam Validation + Category Theory Interpretation

Complete pipeline:
  Sequence -> ESMFold -> ZFC verify -> Pfam check -> Category Theory interpret

Usage:
    from geometry.esmfold_zfc_pipeline import ESMFoldZFCPipeline

    pipeline = ESMFoldZFCPipeline()
    result = pipeline.predict_and_verify("MKTA...", protein_name="TP53")
    print(result.confidence_class)
    print(result.verification.summary)
"""

from __future__ import annotations

import time
import numpy as np
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# ESMFold
try:
    from .esmfold_structure_module import ESMFoldStructureModule, ESMFOLD_AVAILABLE
except ImportError:
    try:
        from geometry.esmfold_structure_module import ESMFoldStructureModule, ESMFOLD_AVAILABLE
    except ImportError:
        ESMFOLD_AVAILABLE = False

# ZFC structure verifier
try:
    from .zfc_structure_verifier import StructureZFCBridge, StructureVerificationResult
    ZFC_VERIFIER_AVAILABLE = True
except ImportError:
    try:
        from geometry.zfc_structure_verifier import StructureZFCBridge, StructureVerificationResult
        ZFC_VERIFIER_AVAILABLE = True
    except ImportError:
        ZFC_VERIFIER_AVAILABLE = False

# Pfam
try:
    from chemistry.pfam_domain_mapper import PfamDomainMapper
    PFAM_AVAILABLE = True
except ImportError:
    PFAM_AVAILABLE = False

try:
    from validation.pfam_validator import PfamDomainValidator
    PFAM_VALIDATOR_AVAILABLE = True
except ImportError:
    PFAM_VALIDATOR_AVAILABLE = False

# Category theory modules (all optional, each in try/except)
try:
    from data.store import KomposOSStore, StoredObject, StoredMorphism
    STORE_AVAILABLE = True
except ImportError:
    STORE_AVAILABLE = False

try:
    from geometry.ricci import OllivierRicciCurvature
    RICCI_AVAILABLE = True
except ImportError:
    try:
        from .ricci import OllivierRicciCurvature
        RICCI_AVAILABLE = True
    except ImportError:
        RICCI_AVAILABLE = False

try:
    from geometry.flow import DiscreteRicciFlow
    FLOW_AVAILABLE = True
except ImportError:
    try:
        from .flow import DiscreteRicciFlow
        FLOW_AVAILABLE = True
    except ImportError:
        FLOW_AVAILABLE = False

try:
    from topology.persistence import PersistentHomologyAnalyzer
    TDA_AVAILABLE = True
except ImportError:
    TDA_AVAILABLE = False

# TM-score comparison
try:
    from scripts.compare_to_pdb import compute_tm_score_simple, read_pdb_coords
    COMPARE_AVAILABLE = True
except ImportError:
    COMPARE_AVAILABLE = False


def _coords_to_contacts(coords, threshold=8.0):
    """Convert CA coordinates to contact map."""
    N = len(coords)
    contacts = np.zeros((N, N), dtype=int)
    for i in range(N):
        for j in range(i + 5, N):
            dist = np.linalg.norm(coords[i] - coords[j])
            if dist < threshold:
                contacts[i, j] = 1
                contacts[j, i] = 1
    return contacts


def _load_structure_into_store(store, sequence, confidence, contacts):
    """Load protein structure into KomposOSStore as categorical objects/morphisms."""
    N = len(sequence)
    for i in range(N):
        residue_name = f"R{i}_{sequence[i]}"
        obj = StoredObject(
            name=residue_name,
            type_name="residue",
            metadata={'position': i, 'aa': sequence[i], 'plddt': float(confidence[i])},
            provenance="esmfold_prediction",
        )
        store.add_object(obj)

    num_contacts = 0
    for i in range(N):
        for j in range(i + 5, N):
            if contacts[i, j] == 1:
                source = f"R{i}_{sequence[i]}"
                target = f"R{j}_{sequence[j]}"
                mor = StoredMorphism(
                    name="contact",
                    source_name=source,
                    target_name=target,
                    confidence=0.9,
                    provenance="esmfold_prediction",
                )
                store.add_morphism(mor)
                num_contacts += 1
    return num_contacts


@dataclass
class ESMFoldZFCResult:
    """Complete result of ESMFold + ZFC + Pfam + Category Theory pipeline."""
    # ESMFold output
    pdb_string: str = ""
    coordinates: Any = None  # np.ndarray (N, 3)
    plddt_scores: Any = None  # np.ndarray
    mean_plddt: float = 0.0

    # ZFC verification
    verification: Any = None  # StructureVerificationResult
    confidence_class: str = "UNKNOWN"

    # Pfam domain analysis
    pfam_domains: list = field(default_factory=list)
    pfam_issues: list = field(default_factory=list)

    # Category theory interpretation
    cat_interpretation: Dict = field(default_factory=dict)

    # Benchmark (if native PDB provided)
    tm_score: Optional[float] = None
    rmsd: Optional[float] = None

    # Timing
    total_time_s: float = 0.0
    esmfold_time_s: float = 0.0
    zfc_time_s: float = 0.0
    pfam_time_s: float = 0.0
    cat_time_s: float = 0.0

    # Pipeline status
    stages_completed: List[str] = field(default_factory=list)
    stages_skipped: List[str] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)


class ESMFoldZFCPipeline:
    """
    Complete pipeline: ESMFold -> ZFC -> Pfam -> Category Theory

    Each stage is independent and degrades gracefully if unavailable.
    """

    def __init__(
        self,
        use_category_theory: bool = True,
        use_pfam: bool = True,
        pfam_cache_dir: Optional[Path] = None,
        verbose: bool = True,
    ):
        self.use_cat = use_category_theory
        self.use_pfam = use_pfam
        self.verbose = verbose

        # ESMFold
        self.esmfold = None  # Lazy load (large model)

        # ZFC verifier
        self.zfc_verifier = StructureZFCBridge() if ZFC_VERIFIER_AVAILABLE else None

        # Pfam
        self.pfam_mapper = None
        self.pfam_validator = None
        if use_pfam and PFAM_AVAILABLE:
            try:
                kwargs = {}
                if pfam_cache_dir:
                    kwargs['cache_dir'] = str(pfam_cache_dir)
                self.pfam_mapper = PfamDomainMapper(**kwargs)
            except Exception:
                pass
        if self.pfam_mapper and PFAM_VALIDATOR_AVAILABLE:
            try:
                self.pfam_validator = PfamDomainValidator(pfam_mapper=self.pfam_mapper)
            except Exception:
                pass

    def _log(self, msg):
        if self.verbose:
            print(msg)

    def _ensure_esmfold(self):
        """Lazy-load ESMFold model on first use."""
        if self.esmfold is not None:
            return True
        if not ESMFOLD_AVAILABLE:
            return False
        try:
            self.esmfold = ESMFoldStructureModule(use_category_theory=False)
            return True
        except Exception as e:
            self._log(f"  [FAIL] ESMFold load failed: {e}")
            return False

    def predict_and_verify(
        self,
        sequence: str,
        protein_name: str = "unknown",
        native_pdb_path: Optional[Path] = None,
        output_pdb: Optional[Path] = None,
    ) -> ESMFoldZFCResult:
        """
        Full pipeline: predict structure, verify with ZFC, annotate with Pfam,
        interpret with category theory.
        """
        total_start = time.time()
        result = ESMFoldZFCResult()

        self._log("=" * 70)
        self._log(f"ESMFold + ZFC Pipeline: {protein_name} ({len(sequence)}aa)")
        self._log("=" * 70)
        self._log("")

        # ── Stage 1: ESMFold Prediction ──────────────────────────────
        self._log("[1/4] ESMFold Structure Prediction...")
        t0 = time.time()

        if not self._ensure_esmfold():
            result.errors['esmfold'] = "ESMFold not available"
            result.stages_skipped.append('esmfold')
            self._log("  SKIPPED: ESMFold not available")
            result.total_time_s = time.time() - total_start
            return result

        try:
            esmfold_result = self.esmfold.predict_structure(sequence, num_recycles=4)
            result.pdb_string = esmfold_result['pdb_string']
            result.coordinates = esmfold_result['coordinates']
            result.plddt_scores = esmfold_result['confidence']
            result.mean_plddt = float(esmfold_result['mean_confidence'])
            result.esmfold_time_s = time.time() - t0
            result.stages_completed.append('esmfold')
            self._log(f"  Mean pLDDT: {result.mean_plddt:.1f}")
            self._log(f"  CA atoms: {len(result.coordinates)}")
            self._log(f"  Time: {result.esmfold_time_s:.1f}s")
        except Exception as e:
            result.errors['esmfold'] = str(e)
            result.stages_skipped.append('esmfold')
            self._log(f"  [FAIL] ESMFold prediction failed: {e}")
            result.total_time_s = time.time() - total_start
            return result

        # Save PDB if requested
        if output_pdb and result.pdb_string:
            output_pdb = Path(output_pdb)
            output_pdb.parent.mkdir(parents=True, exist_ok=True)
            with open(output_pdb, 'w') as f:
                f.write(result.pdb_string)
            self._log(f"  Saved: {output_pdb}")

        self._log("")

        # ── Stage 2: Pfam Domain Annotation ──────────────────────────
        self._log("[2/4] Pfam Domain Annotation...")
        t0 = time.time()

        if self.pfam_mapper:
            try:
                result.pfam_domains = self.pfam_mapper.lookup_domains(sequence)
                self._log(f"  Domains found: {len(result.pfam_domains)}")
                for d in result.pfam_domains:
                    self._log(f"    {d.name} ({d.accession}): {d.start}-{d.end}")

                # Pfam validation on predicted contacts
                if self.pfam_validator and result.coordinates is not None:
                    contacts = _coords_to_contacts(result.coordinates)
                    N = len(sequence)
                    conf_map = np.zeros((N, N), dtype=float)
                    for i in range(N):
                        for j in range(N):
                            if contacts[i, j]:
                                conf_map[i, j] = (
                                    result.plddt_scores[i] + result.plddt_scores[j]
                                ) / 200.0
                    result.pfam_issues = self.pfam_validator.validate_domain_contact_agreement(
                        sequence, contacts, conf_map
                    )
                    self._log(f"  Validation issues: {len(result.pfam_issues)}")

                result.stages_completed.append('pfam')
            except Exception as e:
                result.errors['pfam'] = str(e)
                result.stages_skipped.append('pfam')
                self._log(f"  [FAIL] Pfam annotation failed: {e}")
        else:
            result.stages_skipped.append('pfam')
            self._log("  SKIPPED: Pfam not available")

        result.pfam_time_s = time.time() - t0
        self._log("")

        # ── Stage 3: ZFC Structure Verification ──────────────────────
        self._log("[3/4] ZFC Structure Verification...")
        t0 = time.time()

        if self.zfc_verifier and self.zfc_verifier.is_available and result.coordinates is not None:
            try:
                result.verification = self.zfc_verifier.verify_structure(
                    protein_name=protein_name,
                    coordinates=result.coordinates,
                    sequence=sequence,
                    plddt_scores=result.plddt_scores,
                    pfam_mapper=self.pfam_mapper,
                )
                result.stages_completed.append('zfc')
                self._log(f"  Valid: {result.verification.is_valid}")
                self._log(f"  Constraints: {result.verification.num_constraints}")
                self._log(f"  Violations: {result.verification.num_violations}")

                # Classify confidence
                result.confidence_class = _classify_confidence(
                    result.verification, result.mean_plddt
                )
                self._log(f"  Confidence class: {result.confidence_class}")
            except Exception as e:
                result.errors['zfc'] = str(e)
                result.stages_skipped.append('zfc')
                self._log(f"  [FAIL] ZFC verification failed: {e}")
        else:
            result.stages_skipped.append('zfc')
            reason = "ZFC not available" if not ZFC_VERIFIER_AVAILABLE else "no coordinates"
            self._log(f"  SKIPPED: {reason}")
            # Classify without ZFC
            result.confidence_class = _classify_confidence(None, result.mean_plddt)

        result.zfc_time_s = time.time() - t0
        self._log("")

        # ── Stage 4: Category Theory Interpretation ──────────────────
        self._log("[4/4] Category Theory Interpretation...")
        t0 = time.time()

        if self.use_cat and STORE_AVAILABLE and result.coordinates is not None:
            try:
                result.cat_interpretation = _run_cat_interpretation(
                    result.coordinates, sequence, result.plddt_scores, self._log
                )
                result.stages_completed.append('category_theory')
            except Exception as e:
                result.errors['category_theory'] = str(e)
                result.stages_skipped.append('category_theory')
                self._log(f"  [FAIL] Category theory failed: {e}")
        else:
            result.stages_skipped.append('category_theory')
            self._log("  SKIPPED: Category theory not available or no coordinates")

        result.cat_time_s = time.time() - t0
        self._log("")

        # ── Optional: TM-score comparison ────────────────────────────
        if native_pdb_path and COMPARE_AVAILABLE and result.coordinates is not None:
            native_path = Path(native_pdb_path)
            if native_path.exists():
                try:
                    native_coords = read_pdb_coords(str(native_path))
                    min_len = min(len(native_coords), len(result.coordinates))
                    if min_len >= 10:
                        result.tm_score = compute_tm_score_simple(
                            native_coords[:min_len],
                            result.coordinates[:min_len],
                            min_len,
                        )
                        from scripts.compare_to_pdb import align_structures, compute_rmsd
                        aligned, _ = align_structures(
                            native_coords[:min_len], result.coordinates[:min_len]
                        )
                        result.rmsd = float(compute_rmsd(
                            native_coords[:min_len], aligned
                        ))
                        self._log(f"Comparison to native ({native_path.name}):")
                        self._log(f"  TM-score: {result.tm_score:.3f}")
                        self._log(f"  RMSD: {result.rmsd:.2f}A")
                except Exception as e:
                    self._log(f"  [FAIL] TM-score comparison failed: {e}")

        # ── Summary ──────────────────────────────────────────────────
        result.total_time_s = time.time() - total_start

        self._log("=" * 70)
        self._log("PIPELINE SUMMARY")
        self._log("=" * 70)
        self._log(f"  Protein: {protein_name} ({len(sequence)}aa)")
        self._log(f"  Mean pLDDT: {result.mean_plddt:.1f}")
        self._log(f"  Confidence: {result.confidence_class}")
        self._log(f"  Stages completed: {result.stages_completed}")
        self._log(f"  Stages skipped: {result.stages_skipped}")
        if result.tm_score is not None:
            self._log(f"  TM-score: {result.tm_score:.3f}")
        self._log(f"  Total time: {result.total_time_s:.1f}s")
        self._log("=" * 70)

        return result

    def batch_predict(
        self,
        proteins: Dict[str, str],
    ) -> Dict[str, ESMFoldZFCResult]:
        """Run pipeline on multiple proteins."""
        results = {}
        for name, sequence in proteins.items():
            results[name] = self.predict_and_verify(sequence, protein_name=name)
        return results


def _classify_confidence(
    verification: Optional[Any],
    mean_plddt: float,
) -> str:
    """
    Classify prediction confidence based on ZFC verification and pLDDT.

    Returns: HIGH_CONFIDENCE, MODERATE_CONFIDENCE, LOW_CONFIDENCE, or UNRELIABLE
    """
    if verification is not None:
        zfc_valid = verification.is_valid
        n_violations = verification.num_violations
    else:
        zfc_valid = None
        n_violations = 0

    if zfc_valid and mean_plddt >= 70:
        return "HIGH_CONFIDENCE"
    elif zfc_valid and mean_plddt >= 50:
        return "MODERATE_CONFIDENCE"
    elif zfc_valid is None and mean_plddt >= 70:
        return "MODERATE_CONFIDENCE"
    elif n_violations <= 3 and mean_plddt >= 50:
        return "MODERATE_CONFIDENCE"
    elif mean_plddt >= 50:
        return "LOW_CONFIDENCE"
    else:
        return "UNRELIABLE"


def _run_cat_interpretation(coordinates, sequence, plddt_scores, log_fn):
    """Run category theory interpretation frameworks on predicted structure."""
    N = len(sequence)
    contacts = _coords_to_contacts(coordinates)
    cat = {}

    # Load into store
    store = KomposOSStore()
    confidence = plddt_scores
    num_contacts = _load_structure_into_store(store, sequence, confidence, contacts)
    cat['contacts'] = {'num_contacts': num_contacts}
    log_fn(f"  Contacts: {num_contacts}")

    # Ricci curvature
    if RICCI_AVAILABLE:
        try:
            ricci = OllivierRicciCurvature(store, alpha=0.5)
            result = ricci.compute_all_curvatures()
            cat['ricci'] = {
                'mean_curvature': result.statistics['mean'],
                'spherical': result.num_spherical,
                'hyperbolic': result.num_hyperbolic,
                'euclidean': result.num_euclidean,
            }
            log_fn(f"  Ricci: mean={result.statistics['mean']:.4f}, "
                   f"S={result.num_spherical} H={result.num_hyperbolic} E={result.num_euclidean}")
        except Exception as e:
            cat['ricci'] = {'error': str(e)}

    # Ricci flow
    if FLOW_AVAILABLE:
        try:
            flow = DiscreteRicciFlow(store, alpha=0.5)
            flow_result = flow.flow(max_steps=5, dt=0.1)
            cat['flow'] = {
                'converged': flow_result.converged,
                'steps': flow_result.num_steps,
                'regions': flow_result.num_regions,
            }
            log_fn(f"  Flow: {flow_result.num_regions} regions, converged={flow_result.converged}")
        except Exception as e:
            cat['flow'] = {'error': str(e)}

    # Spectral analysis (direct, no import needed)
    try:
        A = contacts.astype(float)
        degrees = A.sum(axis=1)
        D = np.diag(degrees)
        L = D - A
        eigenvalues = np.linalg.eigvalsh(L)
        alg_conn = float(eigenvalues[1]) if len(eigenvalues) > 1 else 0.0
        cat['spectral'] = {
            'algebraic_connectivity': alg_conn,
            'coupling': "STRONG" if alg_conn > 0.5 else ("MODERATE" if alg_conn > 0.1 else "WEAK"),
        }
        log_fn(f"  Spectral: algebraic_connectivity={alg_conn:.4f}")
    except Exception as e:
        cat['spectral'] = {'error': str(e)}

    # TDA
    if TDA_AVAILABLE:
        try:
            tda = PersistentHomologyAnalyzer(point_cloud=coordinates)
            diagrams = tda.compute_persistence(maxdim=2)
            h0 = len(diagrams[0]) if len(diagrams) > 0 else 0
            h1 = len(diagrams[1]) if len(diagrams) > 1 else 0
            h2 = len(diagrams[2]) if len(diagrams) > 2 else 0
            cat['tda'] = {'h0': h0, 'h1': h1, 'h2': h2}
            log_fn(f"  TDA: H0={h0} H1={h1} H2={h2}")
        except Exception as e:
            cat['tda'] = {'error': str(e)}

    # Geometric homotopy classification (from Ricci data)
    if 'ricci' in cat and 'mean_curvature' in cat['ricci']:
        sph = cat['ricci'].get('spherical', 0)
        hyp = cat['ricci'].get('hyperbolic', 0)
        euc = cat['ricci'].get('euclidean', 0)
        total = sph + hyp + euc
        if total > 0:
            if hyp / total > 0.6:
                mechanism = "HIERARCHICAL_COLLAPSE"
            elif sph / total > 0.6:
                mechanism = "COOPERATIVE_NUCLEATION"
            else:
                mechanism = "MIXED_MECHANISM"
        else:
            mechanism = "UNKNOWN"
        cat['mechanism'] = {
            'type': mechanism,
            'signature': f"S{sph}:H{hyp}:E{euc}",
        }
        log_fn(f"  Mechanism: {mechanism}")

    return cat
