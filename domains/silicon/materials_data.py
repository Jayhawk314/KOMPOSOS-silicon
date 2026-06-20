# SPDX-License-Identifier: Apache-2.0 OR KOMPOSOS-III-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins
#
# This file is dual-licensed. You may use it under either:
# 1. Apache License 2.0 (see LICENSE file), OR
# 2. KOMPOSOS-III Commercial License (see LICENSE-COMMERCIAL file)

"""
Semiconductor Material Properties
====================================

PORTED verbatim into KOMPOSOS-V from
KOMPOSOS-IV-CHEM/semiconductor_bridge/material_properties.py (Rung 1, 2026-06-19).
Pure stdlib; every value carries a source citation. See docs/SILICON_PLAN.md.

Validated property tables for semiconductor materials, analogous to
metal_bridge/material_properties.py and ceramic_bridge/material_properties.py.

Each material entry uses real published values with source citations.

Property Sources:
-----------------
- Ioffe Institute, "New Semiconductor Materials" (www.ioffe.ru/SVA/NSM/)
- Vurgaftman et al., J. Appl. Phys. 89, 5815 (2001) — III-V band parameters
- Levinshtein et al., "Properties of Advanced Semiconductor Materials", 2001
- Sze & Ng, "Physics of Semiconductor Devices", 3rd ed., 2007
- Adachi, "Properties of Semiconductor Alloys", 2009
- Madelung (ed.), "Semiconductors: Data Handbook", 3rd ed., 2004
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class SemiconductorClass(Enum):
    """Classification of semiconductor materials."""
    ELEMENTAL = "elemental"
    III_V = "iii_v"
    II_VI = "ii_vi"
    IV_IV = "iv_iv"
    OXIDE = "oxide_semiconductor"
    NITRIDE = "nitride_semiconductor"
    WIDE_BANDGAP = "wide_bandgap"
    THERMOELECTRIC = "thermoelectric"
    ORGANIC = "organic_semiconductor"
    TWO_D = "2d_material"


class CrystalSystem(Enum):
    """Crystal structure."""
    DIAMOND_CUBIC = "diamond_cubic"
    ZINCBLENDE = "zincblende"
    WURTZITE = "wurtzite"
    ROCKSALT = "rocksalt"
    HEXAGONAL = "hexagonal"
    MONOCLINIC = "monoclinic"
    AMORPHOUS = "amorphous"
    MIXED = "mixed"


class BandGapType(Enum):
    """Direct vs indirect band gap."""
    DIRECT = "direct"
    INDIRECT = "indirect"


class SemiconductorFailureMode(Enum):
    """Known failure modes for semiconductors."""
    THERMAL_RUNAWAY = "thermal_runaway"
    ELECTROMIGRATION = "electromigration"
    HOT_CARRIER_DEGRADATION = "hot_carrier_degradation"
    GATE_OXIDE_BREAKDOWN = "gate_oxide_breakdown"
    LATTICE_MISMATCH_DISLOCATIONS = "lattice_mismatch_dislocations"
    SURFACE_RECOMBINATION = "surface_recombination"
    INTERFACE_TRAPS = "interface_traps"
    DARK_LINE_DEFECTS = "dark_line_defects"
    THERMAL_OXIDATION = "thermal_oxidation"
    MOISTURE_SENSITIVITY = "moisture_sensitivity"
    RADIATION_DAMAGE = "radiation_damage"
    DOPANT_DIFFUSION = "dopant_diffusion"


@dataclass
class SemiconductorMaterial:
    """
    A semiconductor material with validated physical properties.

    Analogous to MetalMaterial / CeramicMaterial in other bridges.
    Every numerical value has a source citation.
    """
    name: str
    formula: str
    semiconductor_class: SemiconductorClass
    crystal_system: CrystalSystem

    # Band structure
    band_gap_eV: Optional[float] = None
    band_gap_type: Optional[BandGapType] = None
    electron_affinity_eV: Optional[float] = None

    # Transport
    electron_mobility_cm2_Vs: Optional[float] = None
    hole_mobility_cm2_Vs: Optional[float] = None
    saturation_velocity_cm_s: Optional[float] = None     # x10^7 cm/s

    # Lattice
    lattice_constant_A: Optional[float] = None           # Angstroms
    lattice_constant_c_A: Optional[float] = None         # c-axis for wurtzite

    # Thermal
    melting_point_C: Optional[float] = None
    thermal_conductivity_W_mK: Optional[float] = None
    cte_per_K: Optional[float] = None                    # x10^-6 /K
    max_operating_temp_C: Optional[float] = None

    # Mechanical
    elastic_modulus_GPa: Optional[float] = None
    density_g_cm3: Optional[float] = None

    # Electrical
    dielectric_constant: Optional[float] = None
    breakdown_field_MV_cm: Optional[float] = None

    # Processing
    growth_temp_C: Optional[float] = None                # Typical epitaxial growth temp

    # Failure modes
    failure_modes: List[SemiconductorFailureMode] = field(default_factory=list)

    # Source citations
    sources: Dict[str, str] = field(default_factory=dict)

    # Additional metadata
    metadata: Dict[str, any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        result = {
            'name': self.name,
            'formula': self.formula,
            'semiconductor_class': self.semiconductor_class.value,
            'crystal_system': self.crystal_system.value,
        }
        if self.band_gap_eV is not None:
            result['band_gap_eV'] = self.band_gap_eV
        if self.band_gap_type is not None:
            result['band_gap_type'] = self.band_gap_type.value
        if self.lattice_constant_A is not None:
            result['lattice_constant_A'] = self.lattice_constant_A
        if self.electron_mobility_cm2_Vs is not None:
            result['electron_mobility_cm2_Vs'] = self.electron_mobility_cm2_Vs
        if self.thermal_conductivity_W_mK is not None:
            result['thermal_conductivity_W_mK'] = self.thermal_conductivity_W_mK
        if self.cte_per_K is not None:
            result['cte_per_K'] = self.cte_per_K
        if self.density_g_cm3 is not None:
            result['density_g_cm3'] = self.density_g_cm3
        if self.failure_modes:
            result['failure_modes'] = [fm.value for fm in self.failure_modes]
        return result


# =============================================================================
# ELEMENTAL SEMICONDUCTORS
# =============================================================================

ELEMENTAL_SEMICONDUCTORS: Dict[str, SemiconductorMaterial] = {}

ELEMENTAL_SEMICONDUCTORS['Si'] = SemiconductorMaterial(
    name='Silicon',
    formula='Si',
    semiconductor_class=SemiconductorClass.ELEMENTAL,
    crystal_system=CrystalSystem.DIAMOND_CUBIC,
    band_gap_eV=1.12,
    band_gap_type=BandGapType.INDIRECT,
    electron_affinity_eV=4.05,
    electron_mobility_cm2_Vs=1400,
    hole_mobility_cm2_Vs=450,
    saturation_velocity_cm_s=1.0,
    lattice_constant_A=5.431,
    melting_point_C=1414.0,
    thermal_conductivity_W_mK=148.0,
    cte_per_K=2.6,
    max_operating_temp_C=300.0,
    elastic_modulus_GPa=130.0,
    density_g_cm3=2.33,
    dielectric_constant=11.7,
    breakdown_field_MV_cm=0.3,
    growth_temp_C=1000.0,
    failure_modes=[
        SemiconductorFailureMode.THERMAL_RUNAWAY,
        SemiconductorFailureMode.HOT_CARRIER_DEGRADATION,
        SemiconductorFailureMode.GATE_OXIDE_BREAKDOWN,
    ],
    sources={
        'band': 'Sze & Ng, Physics of Semiconductor Devices, 2007',
        'transport': 'Ioffe Institute NSM Archive',
        'lattice': 'Madelung, Semiconductors Data Handbook, 2004',
        'thermal': 'Glassbrenner & Slack, Phys. Rev. 134, A1058, 1964',
    },
    metadata={'note': 'Dominant semiconductor; >95% of all IC production'},
)

ELEMENTAL_SEMICONDUCTORS['Ge'] = SemiconductorMaterial(
    name='Germanium',
    formula='Ge',
    semiconductor_class=SemiconductorClass.ELEMENTAL,
    crystal_system=CrystalSystem.DIAMOND_CUBIC,
    band_gap_eV=0.66,
    band_gap_type=BandGapType.INDIRECT,
    electron_affinity_eV=4.00,
    electron_mobility_cm2_Vs=3900,
    hole_mobility_cm2_Vs=1900,
    saturation_velocity_cm_s=0.7,
    lattice_constant_A=5.658,
    melting_point_C=938.0,
    thermal_conductivity_W_mK=60.0,
    cte_per_K=5.9,
    max_operating_temp_C=100.0,
    elastic_modulus_GPa=103.0,
    density_g_cm3=5.32,
    dielectric_constant=16.0,
    breakdown_field_MV_cm=0.1,
    growth_temp_C=700.0,
    failure_modes=[
        SemiconductorFailureMode.THERMAL_RUNAWAY,
        SemiconductorFailureMode.SURFACE_RECOMBINATION,
    ],
    sources={
        'band': 'Sze & Ng, 2007',
        'transport': 'Ioffe Institute NSM',
        'lattice': 'Madelung, 2004',
    },
    metadata={'note': 'High mobility; used in SiGe BiCMOS and photodetectors'},
)

ELEMENTAL_SEMICONDUCTORS['C_diamond'] = SemiconductorMaterial(
    name='Diamond (semiconducting)',
    formula='C',
    semiconductor_class=SemiconductorClass.WIDE_BANDGAP,
    crystal_system=CrystalSystem.DIAMOND_CUBIC,
    band_gap_eV=5.47,
    band_gap_type=BandGapType.INDIRECT,
    electron_affinity_eV=0.0,
    electron_mobility_cm2_Vs=2200,
    hole_mobility_cm2_Vs=1600,
    saturation_velocity_cm_s=2.7,
    lattice_constant_A=3.567,
    melting_point_C=3550.0,
    thermal_conductivity_W_mK=2200.0,
    cte_per_K=1.0,
    max_operating_temp_C=700.0,
    elastic_modulus_GPa=1050.0,
    density_g_cm3=3.52,
    dielectric_constant=5.7,
    breakdown_field_MV_cm=10.0,
    growth_temp_C=900.0,
    failure_modes=[],
    sources={
        'band': 'Isberg et al., Science 297, 1670, 2002',
        'thermal': 'Berman, Physical Properties of Diamond, 1965',
    },
    metadata={'note': 'Ultimate semiconductor; highest thermal conductivity, breakdown field'},
)


# =============================================================================
# GROUP IV-IV SEMICONDUCTORS
# =============================================================================

IV_IV_SEMICONDUCTORS: Dict[str, SemiconductorMaterial] = {}

IV_IV_SEMICONDUCTORS['SiGe'] = SemiconductorMaterial(
    name='Silicon-Germanium (Si0.7Ge0.3)',
    formula='Si0.7Ge0.3',
    semiconductor_class=SemiconductorClass.IV_IV,
    crystal_system=CrystalSystem.DIAMOND_CUBIC,
    band_gap_eV=0.96,
    band_gap_type=BandGapType.INDIRECT,
    electron_affinity_eV=4.03,
    electron_mobility_cm2_Vs=2000,
    hole_mobility_cm2_Vs=800,
    lattice_constant_A=5.499,
    melting_point_C=1270.0,
    thermal_conductivity_W_mK=15.0,
    cte_per_K=3.5,
    max_operating_temp_C=200.0,
    elastic_modulus_GPa=120.0,
    density_g_cm3=3.22,
    dielectric_constant=13.0,
    growth_temp_C=650.0,
    failure_modes=[
        SemiconductorFailureMode.LATTICE_MISMATCH_DISLOCATIONS,
        SemiconductorFailureMode.DOPANT_DIFFUSION,
    ],
    sources={
        'band': 'Adachi, Properties of Semiconductor Alloys, 2009',
        'transport': 'Schaffler, Semicond. Sci. Technol. 12, 1515, 1997',
    },
    metadata={'note': 'Strained on Si; used in BiCMOS HBTs for RF'},
)

IV_IV_SEMICONDUCTORS['SiC_4H'] = SemiconductorMaterial(
    name='4H Silicon Carbide',
    formula='4H-SiC',
    semiconductor_class=SemiconductorClass.WIDE_BANDGAP,
    crystal_system=CrystalSystem.HEXAGONAL,
    band_gap_eV=3.26,
    band_gap_type=BandGapType.INDIRECT,
    electron_affinity_eV=3.17,
    electron_mobility_cm2_Vs=900,
    hole_mobility_cm2_Vs=120,
    saturation_velocity_cm_s=2.0,
    lattice_constant_A=3.073,
    lattice_constant_c_A=10.053,
    melting_point_C=2730.0,
    thermal_conductivity_W_mK=370.0,
    cte_per_K=4.3,
    max_operating_temp_C=600.0,
    elastic_modulus_GPa=410.0,
    density_g_cm3=3.21,
    dielectric_constant=9.7,
    breakdown_field_MV_cm=2.2,
    growth_temp_C=1600.0,
    failure_modes=[
        SemiconductorFailureMode.INTERFACE_TRAPS,
    ],
    sources={
        'band': 'Levinshtein et al., 2001',
        'transport': 'Ioffe Institute NSM',
        'thermal': 'Slack, J. Phys. Chem. Solids 34, 321, 1973',
    },
    metadata={'note': 'Power electronics standard; EV inverters, grid power'},
)

IV_IV_SEMICONDUCTORS['SiC_6H'] = SemiconductorMaterial(
    name='6H Silicon Carbide',
    formula='6H-SiC',
    semiconductor_class=SemiconductorClass.WIDE_BANDGAP,
    crystal_system=CrystalSystem.HEXAGONAL,
    band_gap_eV=3.02,
    band_gap_type=BandGapType.INDIRECT,
    electron_affinity_eV=3.45,
    electron_mobility_cm2_Vs=400,
    hole_mobility_cm2_Vs=90,
    saturation_velocity_cm_s=2.0,
    lattice_constant_A=3.081,
    lattice_constant_c_A=15.117,
    melting_point_C=2730.0,
    thermal_conductivity_W_mK=490.0,
    cte_per_K=4.3,
    max_operating_temp_C=600.0,
    elastic_modulus_GPa=410.0,
    density_g_cm3=3.21,
    dielectric_constant=9.66,
    breakdown_field_MV_cm=2.5,
    growth_temp_C=1600.0,
    failure_modes=[
        SemiconductorFailureMode.INTERFACE_TRAPS,
    ],
    sources={
        'band': 'Levinshtein et al., 2001',
        'thermal': 'Slack, 1973',
    },
    metadata={'note': 'Substrate for GaN epitaxy; LED applications'},
)


# =============================================================================
# III-V SEMICONDUCTORS
# =============================================================================

III_V_SEMICONDUCTORS: Dict[str, SemiconductorMaterial] = {}

III_V_SEMICONDUCTORS['GaAs'] = SemiconductorMaterial(
    name='Gallium Arsenide',
    formula='GaAs',
    semiconductor_class=SemiconductorClass.III_V,
    crystal_system=CrystalSystem.ZINCBLENDE,
    band_gap_eV=1.42,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=4.07,
    electron_mobility_cm2_Vs=8500,
    hole_mobility_cm2_Vs=400,
    saturation_velocity_cm_s=1.2,
    lattice_constant_A=5.653,
    melting_point_C=1238.0,
    thermal_conductivity_W_mK=46.0,
    cte_per_K=5.73,
    max_operating_temp_C=350.0,
    elastic_modulus_GPa=85.5,
    density_g_cm3=5.32,
    dielectric_constant=12.9,
    breakdown_field_MV_cm=0.4,
    growth_temp_C=630.0,
    failure_modes=[
        SemiconductorFailureMode.SURFACE_RECOMBINATION,
        SemiconductorFailureMode.DARK_LINE_DEFECTS,
    ],
    sources={
        'band': 'Vurgaftman et al., J. Appl. Phys. 89, 5815, 2001',
        'transport': 'Ioffe Institute NSM',
        'lattice': 'Madelung, 2004',
    },
    metadata={'note': 'Standard III-V; RF, optoelectronics, solar cells'},
)

III_V_SEMICONDUCTORS['AlAs'] = SemiconductorMaterial(
    name='Aluminum Arsenide',
    formula='AlAs',
    semiconductor_class=SemiconductorClass.III_V,
    crystal_system=CrystalSystem.ZINCBLENDE,
    band_gap_eV=2.17,
    band_gap_type=BandGapType.INDIRECT,
    electron_affinity_eV=3.50,
    electron_mobility_cm2_Vs=200,
    hole_mobility_cm2_Vs=100,
    lattice_constant_A=5.661,
    melting_point_C=1740.0,
    thermal_conductivity_W_mK=91.0,
    cte_per_K=5.20,
    elastic_modulus_GPa=83.5,
    density_g_cm3=3.73,
    dielectric_constant=10.1,
    growth_temp_C=630.0,
    failure_modes=[
        SemiconductorFailureMode.THERMAL_OXIDATION,
        SemiconductorFailureMode.MOISTURE_SENSITIVITY,
    ],
    sources={
        'band': 'Vurgaftman et al., 2001',
        'lattice': 'Madelung, 2004',
    },
    metadata={'note': 'Lattice-matched to GaAs; barrier/cladding layer'},
)

III_V_SEMICONDUCTORS['AlGaAs'] = SemiconductorMaterial(
    name='Aluminum Gallium Arsenide (Al0.3Ga0.7As)',
    formula='Al0.3Ga0.7As',
    semiconductor_class=SemiconductorClass.III_V,
    crystal_system=CrystalSystem.ZINCBLENDE,
    band_gap_eV=1.80,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=3.74,
    electron_mobility_cm2_Vs=3000,
    hole_mobility_cm2_Vs=200,
    lattice_constant_A=5.655,
    melting_point_C=1400.0,
    thermal_conductivity_W_mK=12.0,
    cte_per_K=5.50,
    elastic_modulus_GPa=84.5,
    density_g_cm3=4.71,
    dielectric_constant=12.0,
    growth_temp_C=630.0,
    failure_modes=[
        SemiconductorFailureMode.DARK_LINE_DEFECTS,
    ],
    sources={
        'band': 'Vurgaftman et al., 2001; Adachi, 2009',
        'lattice': 'Vegard interpolation from GaAs/AlAs',
    },
    metadata={'note': 'Nearly lattice-matched to GaAs; HEMT barrier, laser cladding'},
)

III_V_SEMICONDUCTORS['InP'] = SemiconductorMaterial(
    name='Indium Phosphide',
    formula='InP',
    semiconductor_class=SemiconductorClass.III_V,
    crystal_system=CrystalSystem.ZINCBLENDE,
    band_gap_eV=1.35,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=4.38,
    electron_mobility_cm2_Vs=5400,
    hole_mobility_cm2_Vs=200,
    saturation_velocity_cm_s=1.0,
    lattice_constant_A=5.869,
    melting_point_C=1062.0,
    thermal_conductivity_W_mK=68.0,
    cte_per_K=4.60,
    max_operating_temp_C=350.0,
    elastic_modulus_GPa=61.1,
    density_g_cm3=4.81,
    dielectric_constant=12.5,
    breakdown_field_MV_cm=0.5,
    growth_temp_C=630.0,
    failure_modes=[
        SemiconductorFailureMode.SURFACE_RECOMBINATION,
    ],
    sources={
        'band': 'Vurgaftman et al., 2001',
        'transport': 'Ioffe Institute NSM',
        'lattice': 'Madelung, 2004',
    },
    metadata={'note': 'Telecom wavelengths; InGaAs/InP HBTs for >100 GHz'},
)

III_V_SEMICONDUCTORS['InAs'] = SemiconductorMaterial(
    name='Indium Arsenide',
    formula='InAs',
    semiconductor_class=SemiconductorClass.III_V,
    crystal_system=CrystalSystem.ZINCBLENDE,
    band_gap_eV=0.36,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=4.90,
    electron_mobility_cm2_Vs=40000,
    hole_mobility_cm2_Vs=500,
    saturation_velocity_cm_s=0.8,
    lattice_constant_A=6.058,
    melting_point_C=942.0,
    thermal_conductivity_W_mK=27.0,
    cte_per_K=5.19,
    elastic_modulus_GPa=51.4,
    density_g_cm3=5.68,
    dielectric_constant=15.1,
    growth_temp_C=500.0,
    failure_modes=[
        SemiconductorFailureMode.SURFACE_RECOMBINATION,
    ],
    sources={
        'band': 'Vurgaftman et al., 2001',
        'transport': 'Ioffe Institute NSM',
    },
    metadata={'note': 'Very high electron mobility; IR detectors'},
)

III_V_SEMICONDUCTORS['InGaAs'] = SemiconductorMaterial(
    name='Indium Gallium Arsenide (In0.53Ga0.47As)',
    formula='In0.53Ga0.47As',
    semiconductor_class=SemiconductorClass.III_V,
    crystal_system=CrystalSystem.ZINCBLENDE,
    band_gap_eV=0.74,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=4.50,
    electron_mobility_cm2_Vs=12000,
    hole_mobility_cm2_Vs=300,
    lattice_constant_A=5.869,
    melting_point_C=1100.0,
    thermal_conductivity_W_mK=5.0,
    cte_per_K=5.00,
    elastic_modulus_GPa=60.0,
    density_g_cm3=5.49,
    dielectric_constant=13.9,
    growth_temp_C=600.0,
    failure_modes=[
        SemiconductorFailureMode.SURFACE_RECOMBINATION,
    ],
    sources={
        'band': 'Vurgaftman et al., 2001; Adachi, 2009',
        'lattice': 'Lattice-matched to InP at In=0.53',
    },
    metadata={'note': 'Lattice-matched to InP; 1.55um telecom photodetectors, HBTs'},
)

III_V_SEMICONDUCTORS['GaP'] = SemiconductorMaterial(
    name='Gallium Phosphide',
    formula='GaP',
    semiconductor_class=SemiconductorClass.III_V,
    crystal_system=CrystalSystem.ZINCBLENDE,
    band_gap_eV=2.26,
    band_gap_type=BandGapType.INDIRECT,
    electron_affinity_eV=3.80,
    electron_mobility_cm2_Vs=110,
    hole_mobility_cm2_Vs=75,
    lattice_constant_A=5.451,
    melting_point_C=1457.0,
    thermal_conductivity_W_mK=110.0,
    cte_per_K=4.65,
    elastic_modulus_GPa=103.0,
    density_g_cm3=4.14,
    dielectric_constant=11.1,
    growth_temp_C=700.0,
    failure_modes=[
        SemiconductorFailureMode.INTERFACE_TRAPS,
    ],
    sources={
        'band': 'Vurgaftman et al., 2001',
        'lattice': 'Madelung, 2004',
    },
    metadata={'note': 'Green/yellow LEDs; nearly lattice-matched to Si'},
)

III_V_SEMICONDUCTORS['InSb'] = SemiconductorMaterial(
    name='Indium Antimonide',
    formula='InSb',
    semiconductor_class=SemiconductorClass.III_V,
    crystal_system=CrystalSystem.ZINCBLENDE,
    band_gap_eV=0.17,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=4.59,
    electron_mobility_cm2_Vs=78000,
    hole_mobility_cm2_Vs=750,
    saturation_velocity_cm_s=0.5,
    lattice_constant_A=6.479,
    melting_point_C=527.0,
    thermal_conductivity_W_mK=18.0,
    cte_per_K=5.37,
    elastic_modulus_GPa=40.3,
    density_g_cm3=5.78,
    dielectric_constant=17.7,
    growth_temp_C=450.0,
    failure_modes=[
        SemiconductorFailureMode.THERMAL_RUNAWAY,
    ],
    sources={
        'band': 'Vurgaftman et al., 2001',
        'transport': 'Ioffe Institute NSM',
    },
    metadata={'note': 'Highest electron mobility of III-V; mid-wave IR detectors'},
)


# =============================================================================
# NITRIDE SEMICONDUCTORS
# =============================================================================

NITRIDE_SEMICONDUCTORS: Dict[str, SemiconductorMaterial] = {}

NITRIDE_SEMICONDUCTORS['GaN'] = SemiconductorMaterial(
    name='Gallium Nitride',
    formula='GaN',
    semiconductor_class=SemiconductorClass.NITRIDE,
    crystal_system=CrystalSystem.WURTZITE,
    band_gap_eV=3.44,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=4.10,
    electron_mobility_cm2_Vs=1000,
    hole_mobility_cm2_Vs=30,
    saturation_velocity_cm_s=2.5,
    lattice_constant_A=3.189,
    lattice_constant_c_A=5.185,
    melting_point_C=2500.0,
    thermal_conductivity_W_mK=130.0,
    cte_per_K=5.59,
    max_operating_temp_C=600.0,
    elastic_modulus_GPa=295.0,
    density_g_cm3=6.15,
    dielectric_constant=9.0,
    breakdown_field_MV_cm=3.3,
    growth_temp_C=1050.0,
    failure_modes=[
        SemiconductorFailureMode.HOT_CARRIER_DEGRADATION,
        SemiconductorFailureMode.INTERFACE_TRAPS,
    ],
    sources={
        'band': 'Vurgaftman & Meyer, J. Appl. Phys. 94, 3675, 2003',
        'transport': 'Ioffe Institute NSM',
        'thermal': 'Slack et al., J. Phys. Chem. Solids 48, 641, 1977',
    },
    metadata={'note': 'Power electronics and RF; blue LEDs (Nobel Prize 2014)'},
)

NITRIDE_SEMICONDUCTORS['AlN'] = SemiconductorMaterial(
    name='Aluminum Nitride (semiconductor)',
    formula='AlN',
    semiconductor_class=SemiconductorClass.NITRIDE,
    crystal_system=CrystalSystem.WURTZITE,
    band_gap_eV=6.02,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=0.60,
    electron_mobility_cm2_Vs=300,
    hole_mobility_cm2_Vs=14,
    lattice_constant_A=3.112,
    lattice_constant_c_A=4.982,
    melting_point_C=2200.0,
    thermal_conductivity_W_mK=285.0,
    cte_per_K=4.15,
    max_operating_temp_C=700.0,
    elastic_modulus_GPa=344.0,
    density_g_cm3=3.26,
    dielectric_constant=8.5,
    breakdown_field_MV_cm=12.0,
    growth_temp_C=1100.0,
    failure_modes=[
        SemiconductorFailureMode.MOISTURE_SENSITIVITY,
    ],
    sources={
        'band': 'Vurgaftman & Meyer, 2003',
        'thermal': 'Slack et al., 1987',
    },
    metadata={'note': 'Widest direct-gap III-nitride; deep UV LEDs, HEMT barrier'},
)

NITRIDE_SEMICONDUCTORS['AlGaN'] = SemiconductorMaterial(
    name='Aluminum Gallium Nitride (Al0.25Ga0.75N)',
    formula='Al0.25Ga0.75N',
    semiconductor_class=SemiconductorClass.NITRIDE,
    crystal_system=CrystalSystem.WURTZITE,
    band_gap_eV=4.08,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=3.22,
    electron_mobility_cm2_Vs=600,
    hole_mobility_cm2_Vs=20,
    lattice_constant_A=3.170,
    lattice_constant_c_A=5.134,
    melting_point_C=2400.0,
    thermal_conductivity_W_mK=40.0,
    cte_per_K=5.23,
    elastic_modulus_GPa=307.0,
    density_g_cm3=5.43,
    dielectric_constant=9.1,
    breakdown_field_MV_cm=5.0,
    growth_temp_C=1050.0,
    failure_modes=[
        SemiconductorFailureMode.INTERFACE_TRAPS,
    ],
    sources={
        'band': 'Vurgaftman & Meyer, 2003; Vegard interpolation',
        'lattice': 'Vegard interpolation from GaN/AlN',
    },
    metadata={'note': 'GaN/AlGaN HEMT barrier layer; power and RF devices'},
)

NITRIDE_SEMICONDUCTORS['InN'] = SemiconductorMaterial(
    name='Indium Nitride',
    formula='InN',
    semiconductor_class=SemiconductorClass.NITRIDE,
    crystal_system=CrystalSystem.WURTZITE,
    band_gap_eV=0.70,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=5.80,
    electron_mobility_cm2_Vs=3200,
    hole_mobility_cm2_Vs=30,
    lattice_constant_A=3.545,
    lattice_constant_c_A=5.703,
    melting_point_C=1100.0,
    thermal_conductivity_W_mK=45.0,
    cte_per_K=3.80,
    elastic_modulus_GPa=165.0,
    density_g_cm3=6.81,
    dielectric_constant=15.3,
    growth_temp_C=550.0,
    failure_modes=[
        SemiconductorFailureMode.LATTICE_MISMATCH_DISLOCATIONS,
        SemiconductorFailureMode.SURFACE_RECOMBINATION,
    ],
    sources={
        'band': 'Wu et al., Appl. Phys. Lett. 80, 3967, 2002 (revised to 0.7 eV)',
        'lattice': 'Madelung, 2004',
    },
    metadata={'note': 'Narrowest-gap nitride; InGaN alloys span visible spectrum'},
)


# =============================================================================
# II-VI SEMICONDUCTORS
# =============================================================================

II_VI_SEMICONDUCTORS: Dict[str, SemiconductorMaterial] = {}

II_VI_SEMICONDUCTORS['ZnO'] = SemiconductorMaterial(
    name='Zinc Oxide',
    formula='ZnO',
    semiconductor_class=SemiconductorClass.II_VI,
    crystal_system=CrystalSystem.WURTZITE,
    band_gap_eV=3.37,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=4.35,
    electron_mobility_cm2_Vs=200,
    hole_mobility_cm2_Vs=5,
    lattice_constant_A=3.250,
    lattice_constant_c_A=5.207,
    melting_point_C=1975.0,
    thermal_conductivity_W_mK=54.0,
    cte_per_K=4.75,
    elastic_modulus_GPa=140.0,
    density_g_cm3=5.61,
    dielectric_constant=8.7,
    growth_temp_C=400.0,
    failure_modes=[
        SemiconductorFailureMode.MOISTURE_SENSITIVITY,
        SemiconductorFailureMode.SURFACE_RECOMBINATION,
    ],
    sources={
        'band': 'Ozgur et al., J. Appl. Phys. 98, 041301, 2005',
        'lattice': 'Madelung, 2004',
    },
    metadata={'note': 'Transparent conductor; piezoelectric; p-type doping difficult'},
)

II_VI_SEMICONDUCTORS['CdTe'] = SemiconductorMaterial(
    name='Cadmium Telluride',
    formula='CdTe',
    semiconductor_class=SemiconductorClass.II_VI,
    crystal_system=CrystalSystem.ZINCBLENDE,
    band_gap_eV=1.50,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=4.28,
    electron_mobility_cm2_Vs=1050,
    hole_mobility_cm2_Vs=100,
    lattice_constant_A=6.481,
    melting_point_C=1092.0,
    thermal_conductivity_W_mK=6.2,
    cte_per_K=5.90,
    elastic_modulus_GPa=38.0,
    density_g_cm3=5.85,
    dielectric_constant=10.2,
    growth_temp_C=300.0,
    failure_modes=[
        SemiconductorFailureMode.INTERFACE_TRAPS,
        SemiconductorFailureMode.DOPANT_DIFFUSION,
    ],
    sources={
        'band': 'Madelung, 2004',
        'transport': 'Ioffe Institute NSM',
    },
    metadata={'note': 'Thin-film solar cells (First Solar); X-ray/gamma detectors'},
)

II_VI_SEMICONDUCTORS['ZnSe'] = SemiconductorMaterial(
    name='Zinc Selenide',
    formula='ZnSe',
    semiconductor_class=SemiconductorClass.II_VI,
    crystal_system=CrystalSystem.ZINCBLENDE,
    band_gap_eV=2.70,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=4.09,
    electron_mobility_cm2_Vs=530,
    hole_mobility_cm2_Vs=30,
    lattice_constant_A=5.668,
    melting_point_C=1526.0,
    thermal_conductivity_W_mK=19.0,
    cte_per_K=7.10,
    elastic_modulus_GPa=67.2,
    density_g_cm3=5.27,
    dielectric_constant=9.1,
    growth_temp_C=350.0,
    failure_modes=[
        SemiconductorFailureMode.DARK_LINE_DEFECTS,
        SemiconductorFailureMode.LATTICE_MISMATCH_DISLOCATIONS,
    ],
    sources={
        'band': 'Madelung, 2004',
        'lattice': 'Madelung, 2004',
    },
    metadata={'note': 'Blue-green optoelectronics; lattice-matched to GaAs'},
)

II_VI_SEMICONDUCTORS['HgCdTe'] = SemiconductorMaterial(
    name='Mercury Cadmium Telluride (Hg0.7Cd0.3Te)',
    formula='Hg0.7Cd0.3Te',
    semiconductor_class=SemiconductorClass.II_VI,
    crystal_system=CrystalSystem.ZINCBLENDE,
    band_gap_eV=0.25,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=4.60,
    electron_mobility_cm2_Vs=20000,
    hole_mobility_cm2_Vs=500,
    lattice_constant_A=6.464,
    melting_point_C=700.0,
    thermal_conductivity_W_mK=2.0,
    cte_per_K=5.60,
    elastic_modulus_GPa=35.0,
    density_g_cm3=7.63,
    dielectric_constant=16.0,
    growth_temp_C=200.0,
    failure_modes=[
        SemiconductorFailureMode.DOPANT_DIFFUSION,
        SemiconductorFailureMode.SURFACE_RECOMBINATION,
    ],
    sources={
        'band': 'Hansen et al., J. Appl. Phys. 53, 7099, 1982',
        'transport': 'Rogalski, IR Phys. & Tech. 43, 187, 2002',
    },
    metadata={'note': 'Gold standard IR detector; tunable bandgap with composition'},
)


# =============================================================================
# OXIDE SEMICONDUCTORS
# =============================================================================

OXIDE_SEMICONDUCTORS: Dict[str, SemiconductorMaterial] = {}

OXIDE_SEMICONDUCTORS['Ga2O3'] = SemiconductorMaterial(
    name='Beta Gallium Oxide',
    formula='beta-Ga2O3',
    semiconductor_class=SemiconductorClass.OXIDE,
    crystal_system=CrystalSystem.MONOCLINIC,
    band_gap_eV=4.80,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=4.00,
    electron_mobility_cm2_Vs=200,
    hole_mobility_cm2_Vs=None,
    lattice_constant_A=12.214,
    melting_point_C=1795.0,
    thermal_conductivity_W_mK=21.0,
    cte_per_K=5.00,
    elastic_modulus_GPa=261.0,
    density_g_cm3=5.95,
    dielectric_constant=10.0,
    breakdown_field_MV_cm=8.0,
    growth_temp_C=800.0,
    failure_modes=[
        SemiconductorFailureMode.THERMAL_RUNAWAY,
    ],
    sources={
        'band': 'Higashiwaki et al., Appl. Phys. Lett. 100, 013504, 2012',
        'thermal': 'Guo et al., Appl. Phys. Lett. 106, 111909, 2015',
    },
    metadata={'note': 'Ultra-wide bandgap; melt-grown substrates available; poor thermal conductivity'},
)

OXIDE_SEMICONDUCTORS['IGZO'] = SemiconductorMaterial(
    name='Indium Gallium Zinc Oxide',
    formula='InGaZnO4',
    semiconductor_class=SemiconductorClass.OXIDE,
    crystal_system=CrystalSystem.AMORPHOUS,
    band_gap_eV=3.50,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=4.16,
    electron_mobility_cm2_Vs=15,
    hole_mobility_cm2_Vs=None,
    lattice_constant_A=None,
    melting_point_C=None,
    thermal_conductivity_W_mK=1.0,
    cte_per_K=7.00,
    elastic_modulus_GPa=120.0,
    density_g_cm3=6.10,
    dielectric_constant=12.0,
    growth_temp_C=300.0,
    failure_modes=[
        SemiconductorFailureMode.MOISTURE_SENSITIVITY,
        SemiconductorFailureMode.INTERFACE_TRAPS,
    ],
    sources={
        'band': 'Nomura et al., Science 300, 1269, 2003',
    },
    metadata={'note': 'TFT backplane for displays; room-temp sputtering; amorphous'},
)


# =============================================================================
# 2D MATERIALS
# =============================================================================

TWO_D_SEMICONDUCTORS: Dict[str, SemiconductorMaterial] = {}

TWO_D_SEMICONDUCTORS['MoS2'] = SemiconductorMaterial(
    name='Molybdenum Disulfide (monolayer)',
    formula='MoS2',
    semiconductor_class=SemiconductorClass.TWO_D,
    crystal_system=CrystalSystem.HEXAGONAL,
    band_gap_eV=1.90,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=4.20,
    electron_mobility_cm2_Vs=200,
    hole_mobility_cm2_Vs=50,
    lattice_constant_A=3.160,
    melting_point_C=1185.0,
    thermal_conductivity_W_mK=34.0,
    cte_per_K=5.00,
    elastic_modulus_GPa=270.0,
    density_g_cm3=5.06,
    dielectric_constant=4.0,
    growth_temp_C=750.0,
    failure_modes=[
        SemiconductorFailureMode.INTERFACE_TRAPS,
        SemiconductorFailureMode.SURFACE_RECOMBINATION,
    ],
    sources={
        'band': 'Mak et al., Phys. Rev. Lett. 105, 136805, 2010',
        'transport': 'Radisavljevic et al., Nat. Nanotechnol. 6, 147, 2011',
    },
    metadata={'note': 'Monolayer: direct gap; bulk: indirect 1.3 eV'},
)

TWO_D_SEMICONDUCTORS['WS2'] = SemiconductorMaterial(
    name='Tungsten Disulfide (monolayer)',
    formula='WS2',
    semiconductor_class=SemiconductorClass.TWO_D,
    crystal_system=CrystalSystem.HEXAGONAL,
    band_gap_eV=2.10,
    band_gap_type=BandGapType.DIRECT,
    electron_affinity_eV=3.90,
    electron_mobility_cm2_Vs=100,
    hole_mobility_cm2_Vs=60,
    lattice_constant_A=3.153,
    melting_point_C=1250.0,
    thermal_conductivity_W_mK=32.0,
    cte_per_K=5.00,
    elastic_modulus_GPa=272.0,
    density_g_cm3=7.50,
    dielectric_constant=4.2,
    growth_temp_C=800.0,
    failure_modes=[
        SemiconductorFailureMode.INTERFACE_TRAPS,
    ],
    sources={
        'band': 'Gutiérrez et al., Nano Lett. 13, 3447, 2013',
    },
    metadata={'note': 'Large spin-orbit coupling; valleytronics'},
)


# =============================================================================
# THERMOELECTRIC SEMICONDUCTORS
# =============================================================================

THERMOELECTRIC_SEMICONDUCTORS: Dict[str, SemiconductorMaterial] = {}

THERMOELECTRIC_SEMICONDUCTORS['Bi2Te3'] = SemiconductorMaterial(
    name='Bismuth Telluride',
    formula='Bi2Te3',
    semiconductor_class=SemiconductorClass.THERMOELECTRIC,
    crystal_system=CrystalSystem.HEXAGONAL,
    band_gap_eV=0.15,
    band_gap_type=BandGapType.INDIRECT,
    electron_affinity_eV=None,
    electron_mobility_cm2_Vs=1200,
    hole_mobility_cm2_Vs=510,
    lattice_constant_A=4.384,
    lattice_constant_c_A=30.487,
    melting_point_C=585.0,
    thermal_conductivity_W_mK=1.5,
    cte_per_K=16.80,
    elastic_modulus_GPa=47.0,
    density_g_cm3=7.86,
    dielectric_constant=50.0,
    growth_temp_C=400.0,
    failure_modes=[
        SemiconductorFailureMode.THERMAL_RUNAWAY,
        SemiconductorFailureMode.ELECTROMIGRATION,
    ],
    sources={
        'band': 'Madelung, 2004',
        'thermoelectric': 'Goldsmid, Thermoelectric Refrigeration, 1964',
    },
    metadata={'note': 'Best room-temperature thermoelectric (ZT~1); Peltier coolers'},
)


# =============================================================================
# CONVENIENCE LOOKUPS
# =============================================================================

ALL_SEMICONDUCTORS: Dict[str, SemiconductorMaterial] = {}
ALL_SEMICONDUCTORS.update(ELEMENTAL_SEMICONDUCTORS)
ALL_SEMICONDUCTORS.update(IV_IV_SEMICONDUCTORS)
ALL_SEMICONDUCTORS.update(III_V_SEMICONDUCTORS)
ALL_SEMICONDUCTORS.update(NITRIDE_SEMICONDUCTORS)
ALL_SEMICONDUCTORS.update(II_VI_SEMICONDUCTORS)
ALL_SEMICONDUCTORS.update(OXIDE_SEMICONDUCTORS)
ALL_SEMICONDUCTORS.update(TWO_D_SEMICONDUCTORS)
ALL_SEMICONDUCTORS.update(THERMOELECTRIC_SEMICONDUCTORS)


def get_semiconductor(name: str) -> Optional[SemiconductorMaterial]:
    """Look up a semiconductor by name or abbreviation."""
    return ALL_SEMICONDUCTORS.get(name)


def get_semiconductors_by_class(
    sc_class: SemiconductorClass,
) -> Dict[str, SemiconductorMaterial]:
    """Get all semiconductors of a given class."""
    return {k: v for k, v in ALL_SEMICONDUCTORS.items()
            if v.semiconductor_class == sc_class}


def list_elemental() -> List[str]:
    return list(ELEMENTAL_SEMICONDUCTORS.keys())


def list_iii_v() -> List[str]:
    return list(III_V_SEMICONDUCTORS.keys())


def list_nitrides() -> List[str]:
    return list(NITRIDE_SEMICONDUCTORS.keys())


def list_ii_vi() -> List[str]:
    return list(II_VI_SEMICONDUCTORS.keys())


def list_2d() -> List[str]:
    return list(TWO_D_SEMICONDUCTORS.keys())


# =============================================================================
# KNOWN GOOD/BAD JUNCTIONS (for test validation)
# =============================================================================

KNOWN_GOOD_JUNCTIONS = [
    {
        'name': 'GaAs + AlGaAs',
        'sc_a': 'GaAs',
        'sc_b': 'AlGaAs',
        'notes': 'Nearly lattice-matched (0.04%); standard HEMT and laser heterostructure',
    },
    {
        'name': 'InGaAs + InP',
        'sc_a': 'InGaAs',
        'sc_b': 'InP',
        'notes': 'Lattice-matched at In=0.53; telecom photodetectors and HBTs',
    },
    {
        'name': 'GaN + AlGaN',
        'sc_a': 'GaN',
        'sc_b': 'AlGaN',
        'notes': 'Small lattice mismatch (~0.6%); GaN HEMT barrier layer',
    },
    {
        'name': 'Si + SiGe',
        'sc_a': 'Si',
        'sc_b': 'SiGe',
        'notes': 'Strained SiGe on Si; standard BiCMOS process; ~1.2% mismatch',
    },
    {
        'name': 'MoS2 + WS2',
        'sc_a': 'MoS2',
        'sc_b': 'WS2',
        'notes': 'Nearly lattice-matched 2D TMDs; van der Waals heterostructure',
    },
]

KNOWN_BAD_JUNCTIONS = [
    {
        'name': 'GaAs + Si',
        'sc_a': 'GaAs',
        'sc_b': 'Si',
        'issue': '4.1% lattice mismatch; high dislocation density at interface',
    },
    {
        'name': 'InAs + GaP',
        'sc_a': 'InAs',
        'sc_b': 'GaP',
        'issue': '11.1% lattice mismatch; extreme dislocation density',
    },
    {
        'name': 'GaN + GaAs',
        'sc_a': 'GaN',
        'sc_b': 'GaAs',
        'issue': 'Different crystal structures (wurtzite vs zincblende); ~20% a-lattice mismatch',
    },
    {
        'name': 'InSb + Si',
        'sc_a': 'InSb',
        'sc_b': 'Si',
        'issue': '19.3% lattice mismatch; incompatible growth temps',
    },
]


if __name__ == "__main__":
    print("=" * 70)
    print("Semiconductor Material Properties - Summary")
    print("=" * 70)
    print()

    categories = [
        ("Elemental", ELEMENTAL_SEMICONDUCTORS),
        ("IV-IV", IV_IV_SEMICONDUCTORS),
        ("III-V", III_V_SEMICONDUCTORS),
        ("Nitrides", NITRIDE_SEMICONDUCTORS),
        ("II-VI", II_VI_SEMICONDUCTORS),
        ("Oxide", OXIDE_SEMICONDUCTORS),
        ("2D Materials", TWO_D_SEMICONDUCTORS),
        ("Thermoelectric", THERMOELECTRIC_SEMICONDUCTORS),
    ]

    for cat_name, cat_dict in categories:
        print(f"{cat_name}: {len(cat_dict)}")
        for name, mat in cat_dict.items():
            bg = f"Eg={mat.band_gap_eV}eV" if mat.band_gap_eV is not None else ""
            lc = f"a={mat.lattice_constant_A}A" if mat.lattice_constant_A is not None else ""
            print(f"  {name:16s} ({mat.name:42s}) {bg:12s} {lc}")
        print()

    print(f"Total materials: {len(ALL_SEMICONDUCTORS)}")
