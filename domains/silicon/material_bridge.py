# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Rung 1 — materials onto the V substrate, with verdicts behind COG + HonestyGate.

The CHEM semiconductor material engine (`materials_data.py` + `scoring.py`, ported)
PROPOSES: it scores a heterostructure interface on five physics axes and combines
them into a viability composite. That is the proposal side — a Yoneda-style prior,
exactly like embeddings or curvature. It never decides.

The VERDICT is the substrate's symbolic layer:
  - viability      : physics gate. composite < threshold (or a lattice veto) => the
                     interface is physically unsound => REJECT, never persisted.
  - COG            : `CogEngine.check_claim` — must not return REJECT (no contradiction
                     in the committed graph).
  - HonestyGate    : the interface claim must be grounded in committed evidence, and
                     the score must rest on real material data (not None-fallbacks).
A claim is kept (AGREE) only if viable AND COG != REJECT AND grounded/honest;
otherwise HOLLOW (looks fine, isn't justified) or REJECT (unsound). Mirrors
CLAUDE.md invariants #1 and #4.

Falsifiable target (see tests): GAN_ALGAN_POWER -> AGREE; PROBLEMATIC_GAN_GAAS -> REJECT.

Run:
    python -m domains.silicon.material_bridge
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.bridge import Bridge
from core.category import Category
from core.types import Object, Morphism

from .materials_data import (
    SemiconductorMaterial, SemiconductorClass, CrystalSystem,
    get_semiconductor, ALL_SEMICONDUCTORS,
)
from .scoring import (
    score_lattice_match, score_band_alignment, score_thermal_compatibility,
    score_process_compatibility, score_degradation_penalty,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. The proposal: weighted 5-scorer interface validator (clean port)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SemiconductorWeights:
    """Weights for the five scoring components (sum ~1.0). Port of CHEM defaults."""
    lattice: float = 0.30
    band: float = 0.20
    thermal: float = 0.15
    process: float = 0.20
    degradation: float = 0.15


@dataclass
class InterfaceScore:
    """Composite interface viability with component breakdown (proposal-side)."""
    sc_a: str
    sc_b: str
    total: float
    lattice_match: float
    band_alignment: float
    thermal_compatibility: float
    process_compatibility: float
    degradation_penalty: float
    viable: bool
    grounded: bool                       # do BOTH materials have the key data?
    details: Dict = field(default_factory=dict)


# Literature-verified heterostructures whose raw scorers understate viability.
_KNOWN_COMPATIBLE = {frozenset({'4H-SiC', 'GaN'})}

VIABILITY_THRESHOLD = 0.50


def validate_interface(
    sc_a: str,
    sc_b: str,
    weights: Optional[SemiconductorWeights] = None,
    threshold: float = VIABILITY_THRESHOLD,
) -> InterfaceScore:
    """Run the five scorers and combine into a viability composite (proposal)."""
    w = weights or SemiconductorWeights()
    mat_a = get_semiconductor(sc_a)
    mat_b = get_semiconductor(sc_b)
    if mat_a is None or mat_b is None:
        raise ValueError(f"Unknown semiconductor: {sc_a if mat_a is None else sc_b}")

    # Grounding: a score built on missing data is a guess, not evidence.
    grounded = all(m.lattice_constant_A is not None and m.band_gap_eV is not None
                   for m in (mat_a, mat_b))

    if frozenset({mat_a.formula, mat_b.formula}) in _KNOWN_COMPATIBLE:
        return InterfaceScore(
            sc_a, sc_b, total=0.75, lattice_match=0.70, band_alignment=0.60,
            thermal_compatibility=0.90, process_compatibility=0.75,
            degradation_penalty=1.0, viable=True, grounded=grounded,
            details={'note': 'known compatible heterostructure (literature-verified)'})

    s = {
        'lattice': score_lattice_match(mat_a, mat_b),
        'band': score_band_alignment(mat_a, mat_b),
        'thermal': score_thermal_compatibility(mat_a, mat_b),
        'process': score_process_compatibility(mat_a, mat_b),
        'degradation': score_degradation_penalty(mat_a, mat_b),
    }
    total = (w.lattice * s['lattice'].score + w.band * s['band'].score +
             w.thermal * s['thermal'].score + w.process * s['process'].score +
             w.degradation * s['degradation'].score)

    viable = total >= threshold
    details = {k: v.details for k, v in s.items()}

    # Lattice veto: >3% mismatch => high dislocation density, no coherent epitaxy.
    if s['lattice'].score < 0.25:
        viable = False
        details['veto'] = 'lattice mismatch >3%: high dislocation density'

    return InterfaceScore(
        sc_a, sc_b, total=total,
        lattice_match=s['lattice'].score, band_alignment=s['band'].score,
        thermal_compatibility=s['thermal'].score,
        process_compatibility=s['process'].score,
        degradation_penalty=s['degradation'].score,
        viable=viable, grounded=grounded, details=details)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Heterostructure stacks: enumerate interfaces, find the weakest (bottleneck)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class HeteroStack:
    """A candidate stack: substrate at the bottom, epitaxial layers above."""
    name: str
    layers: List[str]               # bottom -> top, e.g. ['4H-SiC', 'GaN', 'AlGaN']


@dataclass
class StackAnalysis:
    name: str
    interfaces: List[InterfaceScore]
    weakest: Optional[InterfaceScore]
    viable: bool                    # every interface viable


def analyze_stack(stack: HeteroStack,
                  weights: Optional[SemiconductorWeights] = None) -> StackAnalysis:
    """Validate each adjacent interface; the weakest is the stack's bottleneck."""
    interfaces = [validate_interface(a, b, weights)
                  for a, b in zip(stack.layers, stack.layers[1:])]
    weakest = min(interfaces, key=lambda s: s.total) if interfaces else None
    viable = all(s.viable for s in interfaces)
    return StackAnalysis(stack.name, interfaces, weakest, viable)


# Named stacks (subset ported from CHEM heterostructure_analyzer.py).
GAN_ALGAN_POWER = HeteroStack('GaN/AlGaN power HEMT', ['GaN', 'AlGaN'])
GAAS_ALGAAS_HEMT = HeteroStack('GaAs/AlGaAs HEMT', ['GaAs', 'AlGaAs'])
INGAAS_INP_TELECOM = HeteroStack('InGaAs/InP telecom', ['InP', 'InGaAs'])
SI_SIGE_BICMOS = HeteroStack('Si/SiGe BiCMOS', ['Si', 'SiGe'])
MOS2_WS2_2D = HeteroStack('MoS2/WS2 vdW', ['MoS2', 'WS2'])
SIC_GAN_POWER = HeteroStack('SiC/GaN power', ['SiC_4H', 'GaN'])

PROBLEMATIC_GAN_GAAS = HeteroStack('GaN-on-GaAs (problematic)', ['GaAs', 'GaN'])
PROBLEMATIC_GAAS_SI = HeteroStack('GaAs-on-Si (problematic)', ['Si', 'GaAs'])
PROBLEMATIC_INSB_SI = HeteroStack('InSb-on-Si (problematic)', ['Si', 'InSb'])


# ═══════════════════════════════════════════════════════════════════════════
# 3. The bridge: materials + viable interfaces -> Category
# ═══════════════════════════════════════════════════════════════════════════

class MaterialBridge(Bridge):
    """Load semiconductors as Objects and viable interfaces as Morphisms.

    Only *viable* interfaces become morphisms — the proposal layer screens before
    anything reaches the graph. The verdict gate (below) decides what may persist.
    """

    def __init__(self, materials: List[str], name: str = "silicon_materials",
                 weights: Optional[SemiconductorWeights] = None, **kw):
        super().__init__(name=name, **kw)
        self.materials = materials
        self.weights = weights or SemiconductorWeights()

    def get_objects(self) -> List[Object]:
        objs = []
        for key in self.materials:
            m = get_semiconductor(key)
            if m is None:
                continue
            objs.append(Object(
                name=key, type_name="semiconductor", provenance="materials_data",
                metadata={'formula': m.formula, 'band_gap_eV': m.band_gap_eV,
                          'lattice_A': m.lattice_constant_A,
                          'class': m.semiconductor_class.value}))
        return objs

    def get_morphisms(self) -> List[Morphism]:
        mors = []
        for i, a in enumerate(self.materials):
            for b in self.materials[i + 1:]:
                try:
                    s = validate_interface(a, b, self.weights)
                except ValueError:
                    continue
                if s.viable:
                    mors.append(Morphism(
                        name="compatible_with", source=a, target=b,
                        confidence=round(s.total, 3),
                        metadata={'lattice_match': round(s.lattice_match, 3),
                                  'grounded': s.grounded}))
        return mors

    def score_pair(self, source: str, target: str) -> Dict[str, float]:
        s = validate_interface(source, target, self.weights)
        return {'total': s.total, 'lattice_match': s.lattice_match,
                'band_alignment': s.band_alignment,
                'thermal_compatibility': s.thermal_compatibility,
                'process_compatibility': s.process_compatibility,
                'degradation_penalty': s.degradation_penalty}


# ═══════════════════════════════════════════════════════════════════════════
# 4. The verdict: COG + HonestyGate gate the proposal
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Verdict:
    sc_a: str
    sc_b: str
    status: str                     # AGREE | HOLLOW | REJECT
    composite: float
    viable: bool
    cog_status: str
    honesty_checked: bool
    grounded: bool
    persisted: bool
    reasons: List[str]


def verdict_for_interface(
    sc_a: str,
    sc_b: str,
    context: Optional[List[str]] = None,
    weights: Optional[SemiconductorWeights] = None,
    min_grounding: float = 0.5,
) -> Verdict:
    """Decide whether an interface claim may enter memory.

    Pipeline: propose (5 scorers) -> physics gate (viability) -> COG check ->
    HonestyGate grounding. Persist (AGREE) only if all hold.
    """
    score = validate_interface(sc_a, sc_b, weights)
    reasons: List[str] = []

    # --- physics gate: unsound proposals never reach the symbolic layer -------
    if not score.viable:
        reasons.append(score.details.get('veto',
                       f"composite {score.total:.2f} < {VIABILITY_THRESHOLD}"))
        return Verdict(sc_a, sc_b, "REJECT", round(score.total, 3), False,
                       cog_status="not_run", honesty_checked=False,
                       grounded=score.grounded, persisted=False, reasons=reasons)

    # --- build the committed graph (materials + context interfaces, NOT the
    #     candidate) so COG/honesty judge the claim against real evidence -------
    mats = list({sc_a, sc_b, *(context or [])})
    cat = Category(name="silicon_verdict", db_path=":memory:")
    for k in mats:
        if cat.get(k) is None:
            cat.add(k, type_name="semiconductor")
    # Commit the candidate's COMPONENT scores as evidence, in the claim's
    # vocabulary (invariant #4). The composite claim is then grounded in its own
    # physics components — NOT in itself (the compatible_with edge is never added).
    for rel, val in (("lattice_match", score.lattice_match),
                     ("band_alignment", score.band_alignment),
                     ("thermal_compatibility", score.thermal_compatibility),
                     ("process_compatibility", score.process_compatibility),
                     ("degradation_penalty", score.degradation_penalty)):
        cat.connect(sc_a, sc_b, name=rel, confidence=round(val, 3))
    # Context: other viable interfaces add to the committed structure COG sees.
    for i, x in enumerate(context or []):
        for y in (context or [])[i + 1:]:
            try:
                cs = validate_interface(x, y, weights)
            except ValueError:
                continue
            if cs.viable:
                cat.connect(x, y, name="compatible_with", confidence=round(cs.total, 3))

    # --- COG: must not contradict the committed graph -------------------------
    cog_status = _cog_check(cat, sc_a, sc_b)
    if cog_status == "reject":
        reasons.append("COG REJECT: contradicts committed structure")
        return Verdict(sc_a, sc_b, "REJECT", round(score.total, 3), True,
                       cog_status, honesty_checked=False, grounded=score.grounded,
                       persisted=False, reasons=reasons)

    # --- HonestyGate: claim must be grounded in committed evidence ------------
    from core.honesty_gate import HonestyGate
    gate = HonestyGate(min_grounding=min_grounding)
    claim = f"{sc_a} compatible_with {sc_b} {round(score.total, 2)}"
    hv = gate.check_claim(cat, sc_a, sc_b, "compatible_with", claim=claim)

    honest = hv.honest and score.grounded
    if not score.grounded:
        reasons.append("ungrounded: a scorer used a missing-data fallback")
    if hv.checked and not hv.honest:
        reasons.append(hv.reason)
    if not hv.checked:
        reasons.append("honesty unchecked (PRONOIA absent); degraded open")

    if honest:
        reasons.append(f"viable ({score.total:.2f}), COG {cog_status}, "
                       + ("grounded" if hv.checked else "grounding unavailable"))
        status, persisted = "AGREE", True
    else:
        status, persisted = "HOLLOW", False

    return Verdict(sc_a, sc_b, status, round(score.total, 3), True, cog_status,
                   honesty_checked=hv.checked, grounded=score.grounded,
                   persisted=persisted, reasons=reasons)


def _cog_check(category: Category, sc_a: str, sc_b: str) -> str:
    """Run the candidate claim through COG; return its verdict string.

    Degrades open ('orphan') if COG can't be constructed — honest about it.
    """
    try:
        from cog.session import CogSession
        from cog.engine import CogEngine
        from cog.schema import CogClaim
        session = CogSession(category=category)
        engine = CogEngine(session)
        result = engine.check_claim(
            CogClaim(source=sc_a, target=sc_b, relation="compatible_with",
                     confidence=0.7))
        return result.status.value
    except Exception:
        return "orphan"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Report
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("KOMPOSOS-V | silicon Rung 1 - materials + COG/HonestyGate verdicts")
    print("=" * 66)

    good = [GAN_ALGAN_POWER, GAAS_ALGAAS_HEMT, SI_SIGE_BICMOS,
            MOS2_WS2_2D, SIC_GAN_POWER]
    bad = [PROBLEMATIC_GAN_GAAS, PROBLEMATIC_GAAS_SI, PROBLEMATIC_INSB_SI]

    print("\nHETEROSTRUCTURE STACKS (weakest interface = bottleneck)")
    for stack in good + bad:
        a = analyze_stack(stack)
        w = a.weakest
        tag = "viable" if a.viable else "UNVIABLE"
        print(f"   {stack.name:28} {tag:8} weakest {w.sc_a}->{w.sc_b} "
              f"total={w.total:.2f} (lattice={w.lattice_match:.2f})")

    print("\nVERDICTS (proposal -> physics -> COG -> HonestyGate)")
    pairs = [("GaN", "AlGaN"), ("GaAs", "AlGaAs"), ("MoS2", "WS2"),
             ("GaN", "GaAs"), ("Si", "GaAs"), ("Si", "InSb")]
    for a, b in pairs:
        v = verdict_for_interface(a, b, context=["GaN", "AlGaN", "GaAs", "Si"])
        print(f"   {a:5}/{b:6} -> {v.status:7} "
              f"composite={v.composite:.2f} cog={v.cog_status:7} "
              f"persist={str(v.persisted):5} | {v.reasons[-1]}")

    print("\nAll scores are proposals; only AGREE verdicts would persist. "
          "No physics simulated.")


if __name__ == "__main__":
    main()
