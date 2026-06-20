# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
Semiconductor Interaction Scoring
====================================

PORTED into KOMPOSOS-V from KOMPOSOS-IV-CHEM/semiconductor_bridge/interaction_scoring.py
(Rung 1, 2026-06-19). Only the import paths changed (now relative to domains.silicon);
the five scorers and their physics are unchanged. See docs/SILICON_PLAN.md.

Five compatibility scorers for semiconductor heterostructure assessment,
analogous to ceramic_bridge/interaction_scoring.py.

Each scorer takes two SemiconductorMaterial objects and returns a float in [0, 1].

Scorer Mapping (ceramic bridge -> semiconductor bridge):
-----------------------------------------------------------
Sintering compat.   -> Lattice match (lattice mismatch -> dislocations)
CTE match            -> Band alignment (band offset and gap compatibility)
Mechanical compat.   -> Thermal compatibility (CTE + thermal conductivity)
Chemical compat.     -> Process compatibility (growth temp, crystal structure)
Degradation penalty  -> Degradation penalty (known failures, environment)

References:
-----------
- Vurgaftman et al., J. Appl. Phys. 89, 5815 (2001) — III-V parameters
- People & Bean, Appl. Phys. Lett. 47, 322 (1985) — critical thickness
- Matthews & Blakeslee, J. Cryst. Growth 27, 118 (1974) — misfit dislocations
- Kroemer, Rev. Mod. Phys. 73, 783 (2001) — heterostructure physics (Nobel)
"""

from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple

from .materials_data import (
    SemiconductorMaterial, SemiconductorClass, SemiconductorFailureMode,
    CrystalSystem, BandGapType, get_semiconductor,
)


@dataclass
class ScorerResult:
    """Result from a single interaction scorer."""
    score: float         # 0-1 (1 = excellent compatibility)
    label: str           # Human-readable label
    details: Dict        # Breakdown / reasoning


# =============================================================================
# 1. LATTICE MATCH SCORE
# =============================================================================
# Most critical parameter for semiconductor heterostructures.
# Lattice mismatch = |a1 - a2| / a_avg * 100%
# Misfit dislocations nucleate above ~0.1% unless strained below critical thickness.

def score_lattice_match(
    material_a: SemiconductorMaterial,
    material_b: SemiconductorMaterial,
) -> ScorerResult:
    """
    Score lattice matching between two semiconductors.

    Lattice mismatch is THE dominant factor for epitaxial semiconductor
    heterostructures. Even 1% mismatch generates ~10^8 cm^-2 dislocations.

    Mismatch thresholds (for a-lattice):
        < 0.1%:  excellent (pseudomorphic growth, e.g. GaAs/AlGaAs)
        0.1-0.5%: very good (thin strained layers, e.g. InGaAs/InP)
        0.5-2%:  moderate (strained, limited thickness)
        2-4%:    poor (high dislocation density, buffer layers needed)
        4-8%:    very poor (metamorphic growth required)
        > 8%:    incompatible (no coherent epitaxy possible)

    Args:
        material_a: First semiconductor
        material_b: Second semiconductor

    Returns:
        ScorerResult with score in [0, 1]
    """
    details = {}

    a_a = material_a.lattice_constant_A
    a_b = material_b.lattice_constant_A

    if a_a is None or a_b is None:
        details['note'] = 'Lattice constant not available'
        return ScorerResult(score=0.5, label='lattice_match', details=details)

    # Calculate mismatch percentage
    a_avg = (a_a + a_b) / 2.0
    mismatch_pct = abs(a_a - a_b) / a_avg * 100.0

    details['lattice_a_A'] = a_a
    details['lattice_b_A'] = a_b
    details['mismatch_pct'] = round(mismatch_pct, 3)

    # Crystal structure compatibility
    cs_a = material_a.crystal_system
    cs_b = material_b.crystal_system
    details['crystal_a'] = cs_a.value
    details['crystal_b'] = cs_b.value

    # Different crystal structures is a severe penalty
    structure_penalty = 1.0
    if cs_a != cs_b:
        # Some combinations are worse than others
        compatible_pairs = {
            frozenset({CrystalSystem.ZINCBLENDE, CrystalSystem.DIAMOND_CUBIC}),
            frozenset({CrystalSystem.HEXAGONAL, CrystalSystem.WURTZITE}),  # SiC/GaN standard heterostructure
        }
        if frozenset({cs_a, cs_b}) in compatible_pairs:
            structure_penalty = 0.85
            details['structure_note'] = 'hexagonal/wurtzite compatible (SiC/GaN standard heterostructure) or zincblende/diamond (similar FCC sublattice)'
        elif CrystalSystem.AMORPHOUS in {cs_a, cs_b}:
            structure_penalty = 0.7
            details['structure_note'] = 'amorphous material (no epitaxial growth)'
        else:
            structure_penalty = 0.5
            details['structure_note'] = 'incompatible crystal structures'

    # 2D material special handling: van der Waals heterostructures relax
    # lattice matching requirements
    is_2d = (material_a.semiconductor_class == SemiconductorClass.TWO_D or
             material_b.semiconductor_class == SemiconductorClass.TWO_D)

    if is_2d:
        # vdW heterostructures can tolerate large mismatch
        if mismatch_pct < 1.0:
            score = 0.95
            details['assessment'] = 'excellent vdW heterostructure match'
        elif mismatch_pct < 5.0:
            score = 0.85
            details['assessment'] = 'good vdW heterostructure (relaxed matching)'
        else:
            score = 0.70
            details['assessment'] = 'vdW stacking tolerates mismatch'
        details['vdw_note'] = 'van der Waals gap relaxes lattice matching requirement'
    else:
        # Standard epitaxial lattice matching
        if mismatch_pct < 0.1:
            score = 0.98
            details['assessment'] = 'nearly lattice-matched (pseudomorphic)'
        elif mismatch_pct < 0.5:
            score = 0.90
            details['assessment'] = 'excellent match (thin strained layers OK)'
        elif mismatch_pct < 1.0:
            score = 0.80
            details['assessment'] = 'good match (strained, limited thickness)'
        elif mismatch_pct < 2.0:
            score = 0.65
            details['assessment'] = 'moderate mismatch (buffer layers recommended)'
        elif mismatch_pct < 3.0:
            score = 0.40
            details['assessment'] = 'poor match (high dislocation density)'
        elif mismatch_pct < 4.5:
            score = 0.20
            details['assessment'] = 'very poor match (metamorphic growth required)'
        else:
            score = 0.05
            details['assessment'] = 'incompatible (no coherent epitaxy possible)'

    score *= structure_penalty
    score = max(0.0, min(1.0, score))
    return ScorerResult(score=score, label='lattice_match', details=details)


# =============================================================================
# 2. BAND ALIGNMENT SCORE
# =============================================================================
# Band offset determines carrier confinement and device function.

def score_band_alignment(
    material_a: SemiconductorMaterial,
    material_b: SemiconductorMaterial,
) -> ScorerResult:
    """
    Score band alignment compatibility between two semiconductors.

    Uses electron affinity (chi) and band gap to determine band offsets.
    For general heterostructure compatibility:
    - Moderate band offset (0.1-1.0 eV) is ideal for most devices
    - Very small offset (<0.1 eV) provides no useful confinement
    - Very large offset (>2 eV) can cause interface charges

    Band alignment types:
        Type I (straddling): both carriers confined in narrow-gap layer
        Type II (staggered): carriers separated spatially
        Type III (broken gap): extreme misalignment

    Args:
        material_a: First semiconductor
        material_b: Second semiconductor

    Returns:
        ScorerResult with score in [0, 1]
    """
    details = {}

    eg_a = material_a.band_gap_eV
    eg_b = material_b.band_gap_eV
    chi_a = material_a.electron_affinity_eV
    chi_b = material_b.electron_affinity_eV

    if eg_a is None or eg_b is None:
        details['note'] = 'Band gap not available'
        return ScorerResult(score=0.5, label='band_alignment', details=details)

    details['band_gap_a_eV'] = eg_a
    details['band_gap_b_eV'] = eg_b
    details['gap_difference_eV'] = round(abs(eg_a - eg_b), 3)

    # Determine band alignment type if electron affinities are available
    if chi_a is not None and chi_b is not None:
        # Anderson's rule (approximate)
        delta_Ec = chi_b - chi_a  # conduction band offset
        delta_Ev = (chi_a + eg_a) - (chi_b + eg_b)  # valence band offset

        details['electron_affinity_a_eV'] = chi_a
        details['electron_affinity_b_eV'] = chi_b
        details['delta_Ec_eV'] = round(delta_Ec, 3)
        details['delta_Ev_eV'] = round(delta_Ev, 3)

        # Classify alignment type
        if delta_Ec * delta_Ev > 0:
            # Both offsets same sign (or one zero) -> Type I (straddling)
            details['alignment_type'] = 'Type I (straddling)'
            alignment_score = 0.9
        elif abs(delta_Ec) + abs(delta_Ev) > abs(eg_a - eg_b) + 0.5:
            details['alignment_type'] = 'Type III (broken gap)'
            alignment_score = 0.4
        else:
            details['alignment_type'] = 'Type II (staggered)'
            alignment_score = 0.7

        # Penalize extreme offsets
        max_offset = max(abs(delta_Ec), abs(delta_Ev))
        if max_offset > 3.0:
            alignment_score *= 0.5
            details['offset_note'] = f'extreme offset {max_offset:.1f} eV'
        elif max_offset > 2.0:
            alignment_score *= 0.7
            details['offset_note'] = f'large offset {max_offset:.1f} eV'
    else:
        # Fallback: use band gap difference only
        gap_diff = abs(eg_a - eg_b)
        if gap_diff < 0.3:
            alignment_score = 0.85
            details['alignment_type'] = 'similar bandgaps (small offset likely)'
        elif gap_diff < 1.0:
            alignment_score = 0.80
            details['alignment_type'] = 'moderate gap difference'
        elif gap_diff < 2.0:
            alignment_score = 0.65
            details['alignment_type'] = 'large gap difference'
        elif gap_diff < 3.5:
            alignment_score = 0.50
            details['alignment_type'] = 'very large gap difference'
        else:
            alignment_score = 0.35
            details['alignment_type'] = 'extreme gap difference'

    # Bonus: same band gap type (direct-direct or indirect-indirect)
    bg_type_a = material_a.band_gap_type
    bg_type_b = material_b.band_gap_type
    if bg_type_a is not None and bg_type_b is not None:
        if bg_type_a == bg_type_b:
            details['gap_type_match'] = True
        else:
            alignment_score *= 0.9
            details['gap_type_match'] = False
            details['gap_type_note'] = 'direct/indirect mismatch (momentum mismatch)'

    score = max(0.0, min(1.0, alignment_score))
    return ScorerResult(score=score, label='band_alignment', details=details)


# =============================================================================
# 3. THERMAL COMPATIBILITY SCORE
# =============================================================================

def score_thermal_compatibility(
    material_a: SemiconductorMaterial,
    material_b: SemiconductorMaterial,
) -> ScorerResult:
    """
    Score thermal compatibility between two semiconductors.

    Factors:
    - CTE mismatch: strain during cooling from growth temperature
    - Thermal conductivity mismatch: heat dissipation bottleneck
    - Operating temperature headroom

    CTE mismatch in semiconductor heterostructures:
        < 0.5 x10^-6/K: negligible
        0.5-1.5: manageable
        1.5-3.0: significant (wafer bow, cracking in thick layers)
        > 3.0: severe (likely delamination)

    Args:
        material_a: First semiconductor
        material_b: Second semiconductor

    Returns:
        ScorerResult with score in [0, 1]
    """
    score = 1.0
    details = {}

    # --- CTE mismatch ---
    cte_a = material_a.cte_per_K
    cte_b = material_b.cte_per_K

    if cte_a is not None and cte_b is not None:
        cte_diff = abs(cte_a - cte_b)
        details['cte_a'] = cte_a
        details['cte_b'] = cte_b
        details['cte_difference'] = round(cte_diff, 2)

        if cte_diff < 0.5:
            details['cte_assessment'] = 'negligible CTE mismatch'
        elif cte_diff < 1.5:
            score *= 0.90
            details['cte_assessment'] = 'manageable CTE mismatch'
        elif cte_diff < 3.0:
            score *= 0.70
            details['cte_assessment'] = 'significant CTE mismatch (wafer bow likely)'
        elif cte_diff < 5.0:
            score *= 0.50
            details['cte_assessment'] = 'severe CTE mismatch'
        else:
            score *= 0.30
            details['cte_assessment'] = 'extreme CTE mismatch (delamination likely)'

    # --- Thermal conductivity mismatch ---
    tc_a = material_a.thermal_conductivity_W_mK
    tc_b = material_b.thermal_conductivity_W_mK

    if tc_a is not None and tc_b is not None and tc_a > 0 and tc_b > 0:
        tc_ratio = max(tc_a, tc_b) / min(tc_a, tc_b)
        details['thermal_cond_a_W_mK'] = tc_a
        details['thermal_cond_b_W_mK'] = tc_b
        details['thermal_cond_ratio'] = round(tc_ratio, 1)

        if tc_ratio > 100:
            score *= 0.6
            details['tc_assessment'] = 'extreme thermal conductivity mismatch'
        elif tc_ratio > 30:
            score *= 0.75
            details['tc_assessment'] = 'large thermal conductivity mismatch'
        elif tc_ratio > 10:
            score *= 0.85
            details['tc_assessment'] = 'moderate thermal conductivity mismatch'

    # --- Operating temperature compatibility ---
    max_t_a = material_a.max_operating_temp_C
    max_t_b = material_b.max_operating_temp_C

    if max_t_a is not None and max_t_b is not None:
        min_max_t = min(max_t_a, max_t_b)
        details['min_max_operating_temp_C'] = min_max_t
        if min_max_t < 100:
            score *= 0.8
            details['temp_note'] = 'low operating temperature limit'

    score = max(0.0, min(1.0, score))
    return ScorerResult(score=score, label='thermal_compatibility', details=details)


# =============================================================================
# 4. PROCESS COMPATIBILITY SCORE
# =============================================================================
# Can these materials be grown/fabricated together?

# Known compatible pairs (lattice-matched systems with standard growth processes)
_COMPATIBLE_PAIRS: Set[Tuple[str, str]] = {
    ('GaAs', 'AlGaAs'), ('AlGaAs', 'GaAs'),
    ('GaAs', 'AlAs'), ('AlAs', 'GaAs'),
    ('InGaAs', 'InP'), ('InP', 'InGaAs'),
    ('GaN', 'AlGaN'), ('AlGaN', 'GaN'),
    ('GaN', 'AlN'), ('AlN', 'GaN'),
    ('Si', 'SiGe'), ('SiGe', 'Si'),
    ('MoS2', 'WS2'), ('WS2', 'MoS2'),
    ('SiC_4H', 'SiC_6H'), ('SiC_6H', 'SiC_4H'),
    ('SiC_4H', 'GaN'), ('GaN', 'SiC_4H'),
}

# Known difficult growth combinations
_DIFFICULT_PAIRS: Dict[Tuple[str, str], Tuple[float, str]] = {
    ('GaAs', 'Si'): (0.4, 'Anti-phase domains from polar-on-nonpolar growth; 4% mismatch'),
    ('Si', 'GaAs'): (0.4, 'Anti-phase domains from polar-on-nonpolar growth; 4% mismatch'),
    ('GaN', 'GaAs'): (0.5, 'Wurtzite on zincblende; extreme mismatch; no standard process'),
    ('GaAs', 'GaN'): (0.5, 'Zincblende on wurtzite; extreme mismatch'),
    ('InSb', 'Si'): (0.5, 'Extreme lattice and thermal mismatch; no viable epitaxy'),
    ('Si', 'InSb'): (0.5, 'Extreme lattice and thermal mismatch'),
    ('InAs', 'GaP'): (0.5, '11% lattice mismatch; no buffer layer scheme works'),
    ('GaP', 'InAs'): (0.5, '11% lattice mismatch'),
}


def score_process_compatibility(
    material_a: SemiconductorMaterial,
    material_b: SemiconductorMaterial,
) -> ScorerResult:
    """
    Score process (growth/fabrication) compatibility between two semiconductors.

    Factors:
    - Growth temperature overlap (can layers be grown sequentially?)
    - Crystal structure compatibility for epitaxy
    - Same material family bonus (III-V on III-V, etc.)
    - Known compatible/difficult pair lookup

    Args:
        material_a: First semiconductor
        material_b: Second semiconductor

    Returns:
        ScorerResult with score in [0, 1]
    """
    score = 0.7  # default: moderate compatibility
    details = {}

    key_a = _get_material_key(material_a)
    key_b = _get_material_key(material_b)
    details['key_a'] = key_a
    details['key_b'] = key_b

    # --- Same semiconductor class = bonus ---
    if material_a.semiconductor_class == material_b.semiconductor_class:
        score = 0.85
        details['class_match'] = True
    else:
        details['class_match'] = False

    # --- Crystal structure compatibility ---
    cs_a = material_a.crystal_system
    cs_b = material_b.crystal_system
    details['crystal_a'] = cs_a.value
    details['crystal_b'] = cs_b.value

    if cs_a == cs_b:
        score = min(1.0, score + 0.05)
        details['crystal_match'] = 'same crystal structure (favorable for epitaxy)'
    elif frozenset({cs_a, cs_b}) == frozenset({CrystalSystem.ZINCBLENDE, CrystalSystem.DIAMOND_CUBIC}):
        score = min(1.0, score + 0.02)
        details['crystal_match'] = 'zincblende/diamond compatible'
    elif CrystalSystem.AMORPHOUS in {cs_a, cs_b}:
        score *= 0.8
        details['crystal_match'] = 'amorphous (no epitaxial compatibility)'
    else:
        score *= 0.6
        details['crystal_match'] = 'incompatible crystal structures for epitaxy'

    # --- Growth temperature overlap ---
    gt_a = material_a.growth_temp_C
    gt_b = material_b.growth_temp_C

    if gt_a is not None and gt_b is not None:
        gt_diff = abs(gt_a - gt_b)
        details['growth_temp_a_C'] = gt_a
        details['growth_temp_b_C'] = gt_b
        details['growth_temp_diff_C'] = gt_diff

        # Check if one material's growth temp exceeds other's melting point
        mp_a = material_a.melting_point_C
        mp_b = material_b.melting_point_C

        growth_conflict = False
        if mp_a is not None and gt_b > mp_a:
            growth_conflict = True
            details['growth_conflict'] = (f'{material_b.formula} grows at {gt_b}C > '
                                          f'{material_a.formula} melts at {mp_a}C')
        if mp_b is not None and gt_a > mp_b:
            growth_conflict = True
            details['growth_conflict'] = (f'{material_a.formula} grows at {gt_a}C > '
                                          f'{material_b.formula} melts at {mp_b}C')

        if growth_conflict:
            score *= 0.3
            details['growth_assessment'] = 'growth temperature exceeds partner melting point'
        elif gt_diff < 50:
            details['growth_assessment'] = 'excellent growth temp overlap'
        elif gt_diff < 150:
            score *= 0.95
            details['growth_assessment'] = 'good growth temp overlap'
        elif gt_diff < 400:
            score *= 0.85
            details['growth_assessment'] = 'moderate growth temp gap'
        elif gt_diff < 700:
            score *= 0.70
            details['growth_assessment'] = 'large growth temp gap'
        else:
            score *= 0.55
            details['growth_assessment'] = 'extreme growth temp gap'

    # --- Known compatible pairs (BONUS) ---
    pair = (key_a, key_b)
    if pair in _COMPATIBLE_PAIRS:
        score = min(1.0, score + 0.10)
        details['compatible_pair'] = f'{key_a} + {key_b} standard heterostructure process'

    # --- Known difficult pairs (PENALTY) ---
    if pair in _DIFFICULT_PAIRS:
        penalty, reason = _DIFFICULT_PAIRS[pair]
        score *= (1.0 - penalty)
        details['difficult_pair'] = reason

    score = max(0.0, min(1.0, score))
    return ScorerResult(score=score, label='process_compatibility', details=details)


def _get_material_key(material: SemiconductorMaterial) -> str:
    """Extract simplified key for pair lookups."""
    for name, mat in _all_semiconductors_cache().items():
        if mat is material:
            return name
    return material.formula


def _all_semiconductors_cache():
    """Lazy import to avoid circular dependency."""
    from .materials_data import ALL_SEMICONDUCTORS
    return ALL_SEMICONDUCTORS


# =============================================================================
# 5. DEGRADATION PENALTY
# =============================================================================

# Known problematic pairings
_KNOWN_BAD_PAIRS: Dict[Tuple[str, str], Tuple[float, str]] = {
    ('GaAs', 'Si'): (0.3, 'Anti-phase boundaries + 4% mismatch threading dislocations'),
    ('Si', 'GaAs'): (0.3, 'Anti-phase boundaries + mismatch dislocations'),
    ('InAs', 'GaP'): (0.5, 'Extreme mismatch; misfit dislocations propagate to surface'),
    ('GaP', 'InAs'): (0.5, 'Extreme mismatch; misfit dislocations'),
    ('GaN', 'GaAs'): (0.4, 'Crystal structure mismatch + lattice mismatch -> high defect density'),
    ('GaAs', 'GaN'): (0.4, 'Crystal structure mismatch'),
    ('InSb', 'Si'): (0.5, 'Extreme mismatch in lattice, CTE, and growth temp'),
    ('Si', 'InSb'): (0.5, 'Extreme mismatch'),
    ('AlAs', 'Si'): (0.3, 'AlAs oxidizes rapidly in moisture; polar-on-nonpolar'),
    ('Si', 'AlAs'): (0.3, 'AlAs moisture sensitivity + polar-nonpolar'),
}


def score_degradation_penalty(
    material_a: SemiconductorMaterial,
    material_b: SemiconductorMaterial,
) -> ScorerResult:
    """
    Apply degradation penalty for known problematic semiconductor pairings.

    Factors:
    - Known bad pairing lookup
    - Shared failure mode vulnerabilities
    - Moisture sensitivity penalty
    - Thermal stability mismatch

    Args:
        material_a: First semiconductor
        material_b: Second semiconductor

    Returns:
        ScorerResult with score in [0, 1] (1 = no degradation concerns)
    """
    penalty = 0.0
    reasons = []

    key_a = _get_material_key(material_a)
    key_b = _get_material_key(material_b)

    # --- Known bad pairings lookup ---
    for key in [(key_a, key_b), (key_b, key_a)]:
        if key in _KNOWN_BAD_PAIRS:
            p, reason = _KNOWN_BAD_PAIRS[key]
            penalty = max(penalty, p)
            reasons.append(reason)
            break

    # --- Shared critical failure modes ---
    shared_failures = set(material_a.failure_modes) & set(material_b.failure_modes)
    critical_shared = shared_failures & {
        SemiconductorFailureMode.THERMAL_RUNAWAY,
        SemiconductorFailureMode.LATTICE_MISMATCH_DISLOCATIONS,
        SemiconductorFailureMode.DARK_LINE_DEFECTS,
    }
    if critical_shared:
        penalty = max(penalty, 0.1 * len(critical_shared))
        reasons.append(f'Shared vulnerabilities: {[f.value for f in critical_shared]}')

    # --- Moisture sensitivity ---
    for mat in [material_a, material_b]:
        if SemiconductorFailureMode.MOISTURE_SENSITIVITY in mat.failure_modes:
            penalty = max(penalty, 0.15)
            reasons.append(f'{mat.formula}: moisture-sensitive (encapsulation required)')

    # --- Thermal stability mismatch ---
    mp_a = material_a.melting_point_C
    mp_b = material_b.melting_point_C
    if mp_a is not None and mp_b is not None:
        mp_ratio = max(mp_a, mp_b) / max(min(mp_a, mp_b), 100)
        if mp_ratio > 4.0:
            penalty = max(penalty, 0.2)
            reasons.append(f'Extreme melting point ratio ({mp_ratio:.1f}x)')
        elif mp_ratio > 2.5:
            penalty = max(penalty, 0.1)
            reasons.append(f'Large melting point ratio ({mp_ratio:.1f}x)')

    # --- Thermal oxidation risk ---
    oxidation_risk = sum(
        1 for mat in [material_a, material_b]
        if SemiconductorFailureMode.THERMAL_OXIDATION in mat.failure_modes
    )
    if oxidation_risk >= 1:
        penalty = max(penalty, 0.1)
        reasons.append('Thermal oxidation risk at heterointerface')

    score = max(0.0, 1.0 - penalty)
    details = {
        'penalty': round(penalty, 2),
        'reasons': reasons if reasons else ['No known degradation concerns'],
    }

    return ScorerResult(score=score, label='degradation_penalty', details=details)


# =============================================================================
# COMPOSITE SCORER
# =============================================================================

def score_all(
    material_a: SemiconductorMaterial,
    material_b: SemiconductorMaterial,
) -> Dict[str, ScorerResult]:
    """
    Run all five scorers on a semiconductor pair.

    Args:
        material_a: First semiconductor
        material_b: Second semiconductor

    Returns:
        Dict mapping scorer name to ScorerResult
    """
    return {
        'lattice_match': score_lattice_match(material_a, material_b),
        'band_alignment': score_band_alignment(material_a, material_b),
        'thermal_compatibility': score_thermal_compatibility(material_a, material_b),
        'process_compatibility': score_process_compatibility(material_a, material_b),
        'degradation_penalty': score_degradation_penalty(material_a, material_b),
    }


if __name__ == "__main__":
    print("=" * 70)
    print("Semiconductor Interaction Scoring - Demo")
    print("=" * 70)
    print()

    # Good pair: GaAs + AlGaAs
    a = get_semiconductor('GaAs')
    b = get_semiconductor('AlGaAs')
    print(f"Pair: {a.formula} <-> {b.formula} (known good heterostructure)")
    results = score_all(a, b)
    for name, result in results.items():
        print(f"  {name:30s}: {result.score:.2f}")
    print()

    # Bad pair: GaAs + Si
    a = get_semiconductor('GaAs')
    b = get_semiconductor('Si')
    print(f"Pair: {a.formula} <-> {b.formula} (problematic)")
    results = score_all(a, b)
    for name, result in results.items():
        print(f"  {name:30s}: {result.score:.2f}")
