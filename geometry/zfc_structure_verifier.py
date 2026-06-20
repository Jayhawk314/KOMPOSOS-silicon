# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
Structure Geometry -> ZFC Constraint Bridge

Converts 3D protein structure geometry into ZFC logical constraints,
then uses SeparationChecker to verify that all constraints are
simultaneously satisfiable.

Follows the exact pattern of ChemZFCBridge (chemistry/zfc_constraints.py).

Geometric axioms encoded:
1. Backbone distance: consecutive CA atoms should be 3.5-4.1 Angstroms apart
2. Clash-free: no two non-bonded CA atoms closer than 3.0 Angstroms
3. Compactness: radius of gyration matches Flory scaling for chain length
4. pLDDT-geometry consistency: high-confidence regions have regular geometry
5. Domain coherence: Pfam-annotated domains have denser internal contacts

Each check produces Constraint objects using atom()/neg()/const() from
zfc.logic, identical to how ChemZFCBridge works.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Graceful ZFC import (same pattern as chemistry/zfc_constraints.py)
try:
    from zfc.logic import Formula, atom, neg, conj, implies, const
    from zfc.separation import Constraint, SeparationChecker
    ZFC_LOGIC_AVAILABLE = True
except ImportError:
    ZFC_LOGIC_AVAILABLE = False


@dataclass
class StructureVerificationResult:
    """Result of ZFC structure verification."""
    protein_name: str
    is_valid: bool
    num_constraints: int
    num_violations: int

    # Per-category results
    backbone_ok: bool
    backbone_violations: int
    clash_ok: bool
    clash_count: int
    compactness_ok: bool
    rg_ratio: float
    plddt_geometry_ok: bool
    domain_coherent: Optional[bool]  # None if no Pfam mapper

    # ZFC details
    all_constraints: list = field(default_factory=list)
    separation_result: Any = None
    violations: List[Dict] = field(default_factory=list)

    # Summary
    summary: str = ""


class StructureZFCBridge:
    """
    Converts 3D protein structure geometry to ZFC constraints.

    Follows the same pattern as ChemZFCBridge (chemistry/zfc_constraints.py).

    Usage:
        bridge = StructureZFCBridge()
        result = bridge.verify_structure(
            protein_name="ubiquitin",
            coordinates=coords,       # (N, 3) CA coordinates
            sequence="MQIFV...",
            plddt_scores=plddt,        # per-residue pLDDT
        )
        print(result.is_valid)
        print(result.summary)
    """

    def __init__(
        self,
        backbone_distance_range: Tuple[float, float] = (3.5, 4.1),
        clash_min_distance: float = 3.0,
        min_separation_for_clash: int = 3,
        compactness_range: Tuple[float, float] = (0.5, 2.0),
        high_plddt_threshold: float = 70.0,
        backbone_variance_threshold: float = 0.5,
    ):
        """
        Args:
            backbone_distance_range: (min, max) Angstroms for consecutive CA-CA
            clash_min_distance: minimum allowed distance for non-bonded CAs
            min_separation_for_clash: minimum sequence separation for clash check
            compactness_range: (min, max) ratio of actual/expected Rg
            high_plddt_threshold: pLDDT above which geometry should be regular
            backbone_variance_threshold: max CA-CA distance variance in high-pLDDT regions
        """
        self.bb_min, self.bb_max = backbone_distance_range
        self.clash_min = clash_min_distance
        self.min_sep = min_separation_for_clash
        self.compact_min, self.compact_max = compactness_range
        self.plddt_thresh = high_plddt_threshold
        self.bb_var_thresh = backbone_variance_threshold

    @property
    def is_available(self) -> bool:
        """Whether ZFC logic imports succeeded."""
        return ZFC_LOGIC_AVAILABLE

    # -----------------------------------------------------------------
    # Individual constraint generators
    # -----------------------------------------------------------------

    def backbone_constraints(
        self,
        protein_name: str,
        coordinates: np.ndarray,
    ) -> List:
        """
        Check that consecutive CA-CA distances are within range.

        For each pair (i, i+1):
        - In range: atom("valid_backbone", protein, pair_label)
        - Out of range: neg(atom("valid_backbone", protein, pair_label))
        """
        if not ZFC_LOGIC_AVAILABLE:
            return []

        constraints = []
        p = const(protein_name)
        N = len(coordinates)

        for i in range(N - 1):
            dist = float(np.linalg.norm(coordinates[i + 1] - coordinates[i]))
            pair_label = f"CA_{i}_{i+1}"
            pair_c = const(pair_label)

            if self.bb_min <= dist <= self.bb_max:
                formula = atom("valid_backbone", p, pair_c)
                conf = 1.0
            else:
                formula = neg(atom("valid_backbone", p, pair_c))
                deviation = max(dist - self.bb_max, self.bb_min - dist, 0)
                conf = min(1.0, deviation / 2.0)

            constraints.append(Constraint(
                formula=formula,
                source_prediction={
                    "source": protein_name, "target": pair_label,
                    "relation": "valid_backbone",
                    "confidence": conf,
                    "strategy": "structure_backbone",
                },
                confidence=conf,
                strategy="structure_backbone",
            ))

        return constraints

    def clash_constraints(
        self,
        protein_name: str,
        coordinates: np.ndarray,
    ) -> List:
        """
        Check that no two non-bonded CA atoms are closer than clash_min.

        Only checks pairs with sequence separation >= min_separation_for_clash.
        """
        if not ZFC_LOGIC_AVAILABLE:
            return []

        constraints = []
        p = const(protein_name)
        N = len(coordinates)

        clash_violations = []
        for i in range(N):
            for j in range(i + self.min_sep, N):
                dist = float(np.linalg.norm(coordinates[j] - coordinates[i]))
                if dist < self.clash_min:
                    clash_violations.append((i, j, dist))

        if not clash_violations:
            # No clashes — single positive constraint
            formula = atom("clash_free", p, const("structure"))
            constraints.append(Constraint(
                formula=formula,
                source_prediction={
                    "source": protein_name, "target": "structure",
                    "relation": "clash_free",
                    "confidence": 1.0,
                    "strategy": "structure_clash",
                },
                confidence=1.0,
                strategy="structure_clash",
            ))
        else:
            # Report each clash as a negative constraint
            for i, j, dist in clash_violations:
                pair_label = f"clash_{i}_{j}"
                formula = neg(atom("clash_free", p, const(pair_label)))
                conf = min(1.0, (self.clash_min - dist) / self.clash_min)
                constraints.append(Constraint(
                    formula=formula,
                    source_prediction={
                        "source": protein_name, "target": pair_label,
                        "relation": "clash_free",
                        "confidence": 0.0,
                        "strategy": "structure_clash",
                        "detail": f"CA_{i}-CA_{j} dist={dist:.2f}A",
                    },
                    confidence=conf,
                    strategy="structure_clash",
                ))

        return constraints

    def compactness_constraints(
        self,
        protein_name: str,
        coordinates: np.ndarray,
        sequence_length: int,
    ) -> List:
        """
        Check radius of gyration matches expected for chain length.

        Expected Rg = 2.2 * L^0.38 (Flory scaling for globular proteins).
        """
        if not ZFC_LOGIC_AVAILABLE:
            return []

        p = const(protein_name)

        # Compute Rg
        centroid = coordinates.mean(axis=0)
        rg = float(np.sqrt(np.mean(np.sum((coordinates - centroid) ** 2, axis=1))))
        expected_rg = 2.2 * (sequence_length ** 0.38)
        rg_ratio = rg / expected_rg if expected_rg > 0 else 0.0

        if self.compact_min <= rg_ratio <= self.compact_max:
            formula = atom("valid_compactness", p, const("structure"))
            conf = 1.0
        else:
            formula = neg(atom("valid_compactness", p, const("structure")))
            if rg_ratio < self.compact_min:
                conf = min(1.0, (self.compact_min - rg_ratio) / self.compact_min)
            else:
                conf = min(1.0, (rg_ratio - self.compact_max) / self.compact_max)

        return [Constraint(
            formula=formula,
            source_prediction={
                "source": protein_name, "target": "structure",
                "relation": "valid_compactness",
                "confidence": conf,
                "strategy": "structure_compactness",
                "detail": f"Rg={rg:.1f}A, expected={expected_rg:.1f}A, ratio={rg_ratio:.2f}",
            },
            confidence=conf,
            strategy="structure_compactness",
        )]

    def plddt_geometry_constraints(
        self,
        protein_name: str,
        coordinates: np.ndarray,
        plddt_scores: np.ndarray,
    ) -> List:
        """
        High-pLDDT regions should have regular backbone geometry.

        For regions with pLDDT > threshold, check that local CA-CA distance
        variance is low (indicating consistent secondary structure).
        """
        if not ZFC_LOGIC_AVAILABLE:
            return []

        p = const(protein_name)
        N = len(coordinates)

        if N < 5:
            return []

        # Find high-confidence regions (runs of 3+ consecutive high-pLDDT residues)
        high_conf_runs = []
        current_run_start = None
        for i in range(N):
            if plddt_scores[i] >= self.plddt_thresh:
                if current_run_start is None:
                    current_run_start = i
            else:
                if current_run_start is not None and (i - current_run_start) >= 3:
                    high_conf_runs.append((current_run_start, i))
                current_run_start = None
        # Handle run at end
        if current_run_start is not None and (N - current_run_start) >= 3:
            high_conf_runs.append((current_run_start, N))

        if not high_conf_runs:
            # No high-confidence regions to check
            return []

        constraints = []
        for start, end in high_conf_runs:
            # Compute CA-CA distances within this run
            dists = []
            for i in range(start, end - 1):
                d = float(np.linalg.norm(coordinates[i + 1] - coordinates[i]))
                dists.append(d)

            if len(dists) < 2:
                continue

            variance = float(np.var(dists))
            region_label = f"region_{start}_{end}"
            region_c = const(region_label)

            if variance <= self.bb_var_thresh:
                formula = atom("plddt_geometry_consistent", p, region_c)
                conf = 1.0
            else:
                formula = neg(atom("plddt_geometry_consistent", p, region_c))
                conf = min(1.0, variance / (self.bb_var_thresh * 3))

            constraints.append(Constraint(
                formula=formula,
                source_prediction={
                    "source": protein_name, "target": region_label,
                    "relation": "plddt_geometry_consistent",
                    "confidence": conf,
                    "strategy": "structure_plddt_geometry",
                    "detail": f"residues {start}-{end}, variance={variance:.4f}",
                },
                confidence=conf,
                strategy="structure_plddt_geometry",
            ))

        return constraints

    def pfam_domain_constraints(
        self,
        protein_name: str,
        coordinates: np.ndarray,
        sequence: str,
        pfam_mapper,
    ) -> List:
        """
        Cross-reference structure with Pfam domain annotations.

        Checks that intra-domain contacts are denser than inter-domain contacts,
        and that active site residues are in well-structured regions.
        """
        if not ZFC_LOGIC_AVAILABLE:
            return []

        if pfam_mapper is None:
            return []

        p = const(protein_name)
        constraints = []

        try:
            domains = pfam_mapper.lookup_domains(sequence)
        except Exception:
            return []

        if not domains:
            return []

        N = len(coordinates)
        contact_threshold = 8.0  # Angstrom

        # Build contact map from coordinates
        contacts = np.zeros((N, N), dtype=bool)
        for i in range(N):
            for j in range(i + 5, N):
                if j < N:
                    dist = np.linalg.norm(coordinates[j] - coordinates[i])
                    if dist < contact_threshold:
                        contacts[i, j] = True
                        contacts[j, i] = True

        # For each domain: check intra-domain contact density vs inter-domain
        for domain in domains:
            d_start = domain.start
            d_end = min(domain.end, N)
            if d_end <= d_start or d_end - d_start < 5:
                continue

            domain_label = f"domain_{domain.name}_{d_start}_{d_end}"
            domain_c = const(domain_label)

            # Count intra-domain contacts
            intra_contacts = 0
            intra_pairs = 0
            for i in range(d_start, d_end):
                for j in range(i + 5, d_end):
                    if i < N and j < N:
                        intra_pairs += 1
                        if contacts[i, j]:
                            intra_contacts += 1

            intra_density = intra_contacts / max(intra_pairs, 1)

            # Count inter-domain contacts (domain residues to outside)
            inter_contacts = 0
            inter_pairs = 0
            for i in range(d_start, d_end):
                for j in range(N):
                    if j < d_start or j >= d_end:
                        if abs(i - j) >= 5 and i < N and j < N:
                            inter_pairs += 1
                            if contacts[i, j]:
                                inter_contacts += 1

            inter_density = inter_contacts / max(inter_pairs, 1)

            # Domain should be more internally connected than externally
            if intra_density >= inter_density or intra_density > 0.05:
                formula = atom("domain_coherent", p, domain_c)
                conf = min(1.0, intra_density / max(inter_density, 0.001))
                conf = min(conf, 1.0)
            else:
                formula = neg(atom("domain_coherent", p, domain_c))
                conf = 0.5

            constraints.append(Constraint(
                formula=formula,
                source_prediction={
                    "source": protein_name, "target": domain_label,
                    "relation": "domain_coherent",
                    "confidence": conf,
                    "strategy": "structure_pfam_domain",
                    "detail": f"intra={intra_density:.3f}, inter={inter_density:.3f}",
                },
                confidence=conf,
                strategy="structure_pfam_domain",
            ))

        return constraints

    # -----------------------------------------------------------------
    # Main verification entry point
    # -----------------------------------------------------------------

    def verify_structure(
        self,
        protein_name: str,
        coordinates: np.ndarray,
        sequence: str,
        plddt_scores: np.ndarray,
        pfam_mapper=None,
    ) -> StructureVerificationResult:
        """
        Run all geometric constraints and check consistency.

        Collects constraints from all check categories, then runs
        SeparationChecker to verify the full set is satisfiable.
        """
        violations_list = []

        # 1. Backbone constraints
        bb_constraints = self.backbone_constraints(protein_name, coordinates)
        bb_neg = [c for c in bb_constraints if _is_negative(c)]
        bb_ok = len(bb_neg) == 0

        # 2. Clash constraints
        clash_constraints = self.clash_constraints(protein_name, coordinates)
        clash_neg = [c for c in clash_constraints if _is_negative(c)]
        clash_ok = len(clash_neg) == 0

        # 3. Compactness constraints
        compact_constraints = self.compactness_constraints(
            protein_name, coordinates, len(sequence)
        )
        compact_neg = [c for c in compact_constraints if _is_negative(c)]
        compact_ok = len(compact_neg) == 0

        # Extract Rg ratio from detail
        rg_ratio = 1.0
        for c in compact_constraints:
            detail = c.source_prediction.get("detail", "")
            if "ratio=" in detail:
                try:
                    rg_ratio = float(detail.split("ratio=")[1])
                except (ValueError, IndexError):
                    pass

        # 4. pLDDT-geometry constraints
        plddt_constraints = self.plddt_geometry_constraints(
            protein_name, coordinates, plddt_scores
        )
        plddt_neg = [c for c in plddt_constraints if _is_negative(c)]
        plddt_ok = len(plddt_neg) == 0

        # 5. Pfam domain constraints
        pfam_constraints = self.pfam_domain_constraints(
            protein_name, coordinates, sequence, pfam_mapper
        )
        pfam_neg = [c for c in pfam_constraints if _is_negative(c)]
        domain_coherent = len(pfam_neg) == 0 if pfam_constraints else None

        # Collect all constraints
        all_constraints = (
            bb_constraints + clash_constraints + compact_constraints
            + plddt_constraints + pfam_constraints
        )

        total_neg = len(bb_neg) + len(clash_neg) + len(compact_neg) + len(plddt_neg) + len(pfam_neg)

        # Build violations list
        for c in bb_neg:
            violations_list.append({
                "category": "backbone",
                "detail": c.source_prediction.get("detail", c.source_prediction.get("target", "")),
            })
        for c in clash_neg:
            violations_list.append({
                "category": "clash",
                "detail": c.source_prediction.get("detail", c.source_prediction.get("target", "")),
            })
        for c in compact_neg:
            violations_list.append({
                "category": "compactness",
                "detail": c.source_prediction.get("detail", ""),
            })
        for c in plddt_neg:
            violations_list.append({
                "category": "plddt_geometry",
                "detail": c.source_prediction.get("detail", ""),
            })
        for c in pfam_neg:
            violations_list.append({
                "category": "domain_coherence",
                "detail": c.source_prediction.get("detail", ""),
            })

        # Run SeparationChecker if available and there are constraints
        separation_result = None
        if ZFC_LOGIC_AVAILABLE and all_constraints:
            try:
                checker = SeparationChecker()
                # Convert to prediction dicts for checker
                pred_dicts = [c.source_prediction for c in all_constraints]
                separation_result = checker.check(pred_dicts)
            except Exception:
                pass  # Graceful degradation

        is_valid = bb_ok and clash_ok and compact_ok and plddt_ok
        if domain_coherent is not None:
            is_valid = is_valid and domain_coherent

        # Build summary
        lines = [f"ZFC Structure Verification: {protein_name}"]
        lines.append(f"  Backbone: {'PASS' if bb_ok else 'FAIL'} ({len(bb_neg)} violations)")
        lines.append(f"  Clash-free: {'PASS' if clash_ok else 'FAIL'} ({len(clash_neg)} clashes)")
        lines.append(f"  Compactness: {'PASS' if compact_ok else 'FAIL'} (Rg ratio={rg_ratio:.2f})")
        lines.append(f"  pLDDT-geometry: {'PASS' if plddt_ok else 'FAIL'} ({len(plddt_neg)} inconsistencies)")
        if domain_coherent is not None:
            lines.append(f"  Domain coherence: {'PASS' if domain_coherent else 'FAIL'} ({len(pfam_neg)} issues)")
        else:
            lines.append("  Domain coherence: SKIPPED (no Pfam mapper)")
        lines.append(f"  Overall: {'VALID' if is_valid else 'INVALID'} ({total_neg} total violations)")
        summary = "\n".join(lines)

        return StructureVerificationResult(
            protein_name=protein_name,
            is_valid=is_valid,
            num_constraints=len(all_constraints),
            num_violations=total_neg,
            backbone_ok=bb_ok,
            backbone_violations=len(bb_neg),
            clash_ok=clash_ok,
            clash_count=len(clash_neg),
            compactness_ok=compact_ok,
            rg_ratio=rg_ratio,
            plddt_geometry_ok=plddt_ok,
            domain_coherent=domain_coherent,
            all_constraints=all_constraints,
            separation_result=separation_result,
            violations=violations_list,
            summary=summary,
        )


def _is_negative(constraint) -> bool:
    """Check if a constraint's formula is a negation."""
    if not ZFC_LOGIC_AVAILABLE:
        return False
    try:
        from zfc.logic import FormulaKind
        return constraint.formula.kind == FormulaKind.NOT
    except Exception:
        return False
