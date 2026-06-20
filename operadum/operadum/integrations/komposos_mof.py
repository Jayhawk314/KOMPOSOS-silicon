# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Real KOMPOSOS-MOF tandem integration.

Chemistry is not a second generator inside OPERADUM. KOMPOSOS-IV-CHEM owns the
MOF linker generator, RDKit validation, and CAT/ZFC verdict scoring. OPERADUM
uses those real candidates as typed operations, then adds its part: operadic
assembly, resource accounting, semantic constraints, and round-trip evidence.

This module intentionally has no synthetic fallback. If the local KOMPOSOS
repo, RDKit, or the real linker cache is missing, it raises a clear error.
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ..bridges.round_trip import KomposVerifier, RoundTripResult
from ..core.operad import Operad
from ..core.types import Spec
from ..domains.materials import MaterialsDomain
from ..gate.semantic_gate import SemanticGate, VerifiedDesign


DEFAULT_KOMPOSOS_PATH = r"C:\Users\JAMES\github\KOMPOSOS-IV-CHEM"
VERDICT_NAMES = (
    "synthesizability",
    "toxicity",
    "stability",
    "activity",
    "conductivity",
)


class KompososMOFError(RuntimeError):
    """Raised when the real KOMPOSOS-MOF stack cannot be used."""


@dataclass(frozen=True)
class KompososMOFSpec:
    """Inputs passed through to KOMPOSOS's real linker generator/screener."""

    application_context: str = "custom"
    exact_atoms: int = 22
    num_candidates: int = 50
    require_all_agree: bool = True
    allow_hollow: bool = False
    functional_groups: Optional[List[str]] = None
    exclude_elements: Optional[List[str]] = None
    ranking_mode: str = "morphism_integrity"
    strategy_weights: Optional[Dict[str, float]] = None
    seed_smiles: Optional[str] = None
    required_groups: Optional[List[str]] = None
    top_k: int = 50
    random_seed: Optional[int] = None


@dataclass
class ScreenedLinker:
    """A real KOMPOSOS-scored linker, normalized for OPERADUM."""

    rank: int
    smiles: str
    formula: str
    mw: float
    atoms: int
    n: int
    o: int
    s: int
    verdicts: Dict[str, str]
    verdict_scores: Dict[str, float]
    morphism_integrity: float
    zfc_constraints_passed: int
    reasoning_traces: Dict[str, str]
    overall_viable: bool

    def to_material_record(self) -> Dict[str, Any]:
        """Record shape consumed by MaterialsDomain."""
        return {
            "rank": self.rank,
            "smiles": self.smiles,
            "formula": self.formula,
            "mw": self.mw,
            "atoms": self.atoms,
            "n": self.n,
            "o": self.o,
            "s": self.s,
            "stability": self.verdict_scores.get("stability", 0.0),
            "synth": self.verdict_scores.get("synthesizability", 0.0),
            "viable": self.overall_viable,
            "verdicts": dict(self.verdicts),
            "verdict_scores": dict(self.verdict_scores),
            "morphism_integrity": self.morphism_integrity,
            "zfc_constraints_passed": self.zfc_constraints_passed,
            "reasoning_traces": dict(self.reasoning_traces),
            "source": "komposos_mof",
        }


@dataclass
class KompososMOFScreen:
    """Output from the real KOMPOSOS generation + verdict pass."""

    spec: KompososMOFSpec
    candidates: List[ScreenedLinker]
    num_generated: int
    num_scored: int
    num_passed_all: int
    avg_morphism_integrity: float
    best_morphism_integrity: float
    verdict_statistics: Dict[str, Dict[str, int]]
    komposos_path: str


@dataclass
class TandemMOFDesign:
    """End-to-end result: KOMPOSOS proposes/scores; OPERADUM assembles/verifies."""

    screen: KompososMOFScreen
    operad: Operad
    design: Optional[VerifiedDesign]
    round_trip: Optional[RoundTripResult]

    @property
    def buildable(self) -> bool:
        return self.design is not None

    @property
    def selected_linker(self) -> Optional[Dict[str, Any]]:
        if self.design is None:
            return None
        return self.design.artifact()["linker"]


class RealKompososMOFClient:
    """Thin, real adapter over KOMPOSOS-IV-CHEM's MOF generator stack."""

    def __init__(
        self,
        komposos_path: str = DEFAULT_KOMPOSOS_PATH,
        cache_dir: Optional[str] = None,
    ):
        self.komposos_path = str(Path(komposos_path))
        self.cache_dir = str(
            Path(cache_dir)
            if cache_dir is not None
            else Path(self.komposos_path) / "data" / "cache" / "mof_linkers"
        )

    def load_known_linkers(self):
        """Load the real cached linker corpus from KOMPOSOS-IV-CHEM."""
        self._ensure_import_path()
        try:
            from mof_bridge.mp_mof_loader import MOFLinkerCache
        except Exception as exc:  # pragma: no cover - external stack dependent
            raise KompososMOFError(
                f"KOMPOSOS MOF cache loader is not importable from {self.komposos_path}"
            ) from exc

        cache = MOFLinkerCache(cache_dir=self.cache_dir)
        if not cache.is_available():
            raise KompososMOFError(
                "Real KOMPOSOS MOF linker cache is missing: "
                f"{self.cache_dir}. Populate KOMPOSOS-IV-CHEM's cache first."
            )
        return cache.load_linkers()

    def screen_linkers(self, spec: KompososMOFSpec) -> KompososMOFScreen:
        """Generate with KOMPOSOS, score with KOMPOSOS, then normalize results."""
        self._ensure_import_path()
        try:
            from mof_bridge.linker_generator import LinkerGenerator
            from mof_bridge.komposos_verdicts import LinkerVerdictEngine
        except Exception as exc:  # pragma: no cover - external stack dependent
            raise KompososMOFError(
                f"KOMPOSOS MOF generator/verdict stack is not importable from {self.komposos_path}"
            ) from exc

        if spec.random_seed is not None:
            random.seed(spec.random_seed)

        known_linkers = self.load_known_linkers()
        generator = LinkerGenerator(known_linkers)
        generator.min_atoms = spec.exact_atoms
        generator.max_atoms = spec.exact_atoms

        smiles = generator.generate_candidates(
            n_candidates=spec.num_candidates,
            application_context=spec.application_context,
            functional_groups=spec.functional_groups,
            exclude_elements=spec.exclude_elements,
            strategy_weights=spec.strategy_weights,
            seed_smiles=spec.seed_smiles,
            required_groups=spec.required_groups,
        )

        verdict_engine = LinkerVerdictEngine()
        scored: List[ScreenedLinker] = []
        for i, smi in enumerate(smiles, 1):
            result = verdict_engine.score_verdicts(smi, spec.application_context)
            scored.append(screened_linker_from_komposos_result(result, rank=i))

        filtered = [c for c in scored if _passes_screen(c, spec)]
        ranked = _rank_linkers(filtered, spec.ranking_mode)[: spec.top_k]

        return KompososMOFScreen(
            spec=spec,
            candidates=ranked,
            num_generated=len(smiles),
            num_scored=len(scored),
            num_passed_all=sum(1 for c in scored if c.overall_viable),
            avg_morphism_integrity=_avg(c.morphism_integrity for c in scored),
            best_morphism_integrity=max(
                (c.morphism_integrity for c in scored), default=0.0
            ),
            verdict_statistics=_verdict_statistics(scored),
            komposos_path=self.komposos_path,
        )

    def _ensure_import_path(self) -> None:
        path = Path(self.komposos_path)
        if not path.is_dir():
            raise KompososMOFError(f"KOMPOSOS-IV-CHEM path does not exist: {path}")
        if self.komposos_path not in sys.path:
            sys.path.insert(0, self.komposos_path)


def screened_linker_from_komposos_result(result: Any, rank: int) -> ScreenedLinker:
    """Convert KOMPOSOS LinkerVerdictResult into a typed OPERADUM record."""
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors
    except Exception as exc:  # pragma: no cover - external stack dependent
        raise KompososMOFError("RDKit is required for real MOF linker descriptors") from exc

    smiles = result.linker_smiles
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise KompososMOFError(f"KOMPOSOS returned invalid SMILES: {smiles}")

    return ScreenedLinker(
        rank=rank,
        smiles=smiles,
        formula=rdMolDescriptors.CalcMolFormula(mol),
        mw=round(float(Descriptors.MolWt(mol)), 3),
        atoms=int(mol.GetNumHeavyAtoms()),
        n=_count_atoms(mol, "N"),
        o=_count_atoms(mol, "O"),
        s=_count_atoms(mol, "S"),
        verdicts=dict(result.verdicts),
        verdict_scores={k: float(v) for k, v in result.verdict_scores.items()},
        morphism_integrity=float(result.morphism_integrity),
        zfc_constraints_passed=int(result.zfc_constraints_passed),
        reasoning_traces=dict(result.reasoning_traces),
        overall_viable=bool(result.overall_viable),
    )


def build_operad_from_screened_linkers(
    linkers: List[ScreenedLinker],
    db_path: str = ":memory:",
) -> Operad:
    """Build a MaterialsDomain operad from real KOMPOSOS-screened candidates."""
    records = [linker.to_material_record() for linker in linkers]
    return MaterialsDomain(linkers=records).build_operad(db_path=db_path)


def design_mof_with_komposos(
    screen_spec: KompososMOFSpec,
    *,
    komposos_path: str = DEFAULT_KOMPOSOS_PATH,
    min_morphism_integrity: float = 0.0,
    required_verdicts: Optional[Dict[str, str]] = None,
    min_verdict_scores: Optional[Dict[str, float]] = None,
    min_donor_atoms: Optional[Dict[str, int]] = None,
    max_depth: int = 4,
) -> TandemMOFDesign:
    """
    Real tandem workflow.

    1. KOMPOSOS generates and scores linker SMILES.
    2. OPERADUM turns surviving linkers into typed MOF assembly operations.
    3. OPERADUM finds the lightest MOF satisfying the extra semantic constraints.
    4. The selected assembly is compiled back through the KOMPOSOS round-trip.
    """
    client = RealKompososMOFClient(komposos_path=komposos_path)
    screen = client.screen_linkers(screen_spec)
    operad = build_operad_from_screened_linkers(screen.candidates)

    validator = _mof_validator(
        min_morphism_integrity=min_morphism_integrity,
        required_verdicts=required_verdicts,
        min_verdict_scores=min_verdict_scores,
        min_donor_atoms=min_donor_atoms,
    )
    design = SemanticGate(operad, max_depth=max_depth).synthesize(
        Spec((), "MOF"), validator
    )
    round_trip = (
        KomposVerifier(komposos_path=komposos_path).verify(design.composite, operad)
        if design is not None
        else None
    )
    return TandemMOFDesign(
        screen=screen,
        operad=operad,
        design=design,
        round_trip=round_trip,
    )


def _mof_validator(
    *,
    min_morphism_integrity: float,
    required_verdicts: Optional[Dict[str, str]],
    min_verdict_scores: Optional[Dict[str, float]],
    min_donor_atoms: Optional[Dict[str, int]],
):
    verdicts_required = dict(required_verdicts or {})
    scores_required = dict(min_verdict_scores or {})
    donors_required = {k.upper(): v for k, v in dict(min_donor_atoms or {}).items()}

    def validate(artifact, _comp) -> bool:
        linker = artifact()["linker"]
        if linker.get("morphism_integrity", 0.0) < min_morphism_integrity:
            return False
        verdicts = linker.get("verdicts", {})
        for name, expected in verdicts_required.items():
            if verdicts.get(name) != expected:
                return False
        scores = linker.get("verdict_scores", {})
        for name, minimum in scores_required.items():
            if scores.get(name, 0.0) < minimum:
                return False
        counts = {"N": linker.get("n", 0), "O": linker.get("o", 0), "S": linker.get("s", 0)}
        for atom, minimum in donors_required.items():
            if counts.get(atom, 0) < minimum:
                return False
        return True

    return validate


def _passes_screen(candidate: ScreenedLinker, spec: KompososMOFSpec) -> bool:
    verdict_values = set(candidate.verdicts.values())
    if spec.require_all_agree:
        return candidate.overall_viable
    if spec.allow_hollow:
        return "REJECT" not in verdict_values
    return "REJECT" not in verdict_values and "HOLLOW" not in verdict_values


def _rank_linkers(
    candidates: List[ScreenedLinker],
    ranking_mode: str,
) -> List[ScreenedLinker]:
    if ranking_mode == "verdict_count":
        return sorted(
            candidates,
            key=lambda c: (
                sum(1 for v in c.verdicts.values() if v == "AGREE"),
                _composite_score(c),
            ),
            reverse=True,
        )
    return sorted(candidates, key=_composite_score, reverse=True)


def _composite_score(candidate: ScreenedLinker) -> float:
    score = candidate.morphism_integrity
    verdicts = list(candidate.verdicts.values())
    score += 0.05 * sum(1 for v in verdicts if v == "AGREE")
    score -= 0.10 * sum(1 for v in verdicts if v == "HOLLOW")
    score -= 0.20 * sum(1 for v in verdicts if v == "ORPHAN")
    score -= 0.40 * sum(1 for v in verdicts if v == "REJECT")
    return score / (candidate.atoms ** 0.5)


def _verdict_statistics(candidates: List[ScreenedLinker]) -> Dict[str, Dict[str, int]]:
    return {
        name: {
            verdict: sum(1 for c in candidates if c.verdicts.get(name) == verdict)
            for verdict in ("AGREE", "HOLLOW", "ORPHAN", "REJECT")
        }
        for name in VERDICT_NAMES
    }


def _count_atoms(mol: Any, symbol: str) -> int:
    return sum(1 for atom in mol.GetAtoms() if atom.GetSymbol() == symbol)


def _avg(values: Iterable[float]) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0
