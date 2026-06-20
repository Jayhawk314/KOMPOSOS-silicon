# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Lightweight drug-design world model backed by KOMPOSOS-CHEM-TB when present.

This module keeps OPERADUM out of the business of pretending to be a drug model.
It only asks specialized evidence sources for scores, converts those scores into
figures, and lets OPERADUM choose the next action under a figure profile.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from ..world_model import RuleWorldModel, WorldPrediction, WorldState


DEFAULT_KOMPOSOS_CHEM_TB_PATH = r"C:\Users\JAMES\github\KOMPOSOS-IV-CHEM-TB"


@dataclass
class ScoreResult:
    score: float
    source: str
    detail: str = ""


class KompososDrugEvidenceClient:
    """Small adapter over KOMPOSOS-CHEM-TB with deterministic fallback scores."""

    def __init__(
        self,
        komposos_path: str = DEFAULT_KOMPOSOS_CHEM_TB_PATH,
        *,
        use_komposos: bool = True,
    ):
        self.komposos_path = komposos_path
        self.use_komposos = use_komposos
        self._category = None
        self._abpp = None

    def graph_evidence(self, drug: str, disease: str) -> ScoreResult:
        """Score existing Drug -> Disease evidence paths in the KOMPOSOS graph."""
        if self.use_komposos:
            try:
                category = self._load_category()
                paths = category.find_paths(drug, disease, max_length=4)
                if paths:
                    best = max(float(getattr(path, "weight", 0.0) or 0.0) for path in paths)
                    score = min(0.98, best + min(0.15, 0.03 * len(paths)))
                    return ScoreResult(
                        score=score,
                        source="komposos_graph",
                        detail=f"{len(paths)} evidence path(s), best weight {best:.3f}",
                    )
            except Exception as exc:
                return self._fallback("graph_evidence", drug, disease, detail=str(exc))
        return self._fallback("graph_evidence", drug, disease)

    def target_engagement(self, drug: str, target: str, prior: float = 0.5) -> ScoreResult:
        """Use ABPP target-engagement data when available."""
        if self.use_komposos:
            try:
                abpp = self._load_abpp()
                enhanced, result, status = abpp.enhance_with_abpp(drug, target, prior)
                detail = status
                if result is not None:
                    ic50 = "n/a" if result.ic50_um is None else f"{result.ic50_um:g} uM"
                    detail = f"{status}; IC50={ic50}; {result.publication or 'no publication id'}"
                return ScoreResult(float(enhanced), "abpp", detail)
            except Exception as exc:
                return self._fallback("target_engagement", drug, target, detail=str(exc))
        return self._fallback("target_engagement", drug, target)

    def structure_binding(self, drug: str, target: str) -> ScoreResult:
        """Use the Boltz2 bridge if importable; otherwise deterministic fallback."""
        if self.use_komposos:
            try:
                self._ensure_path()
                from boltz2_bridge import Boltz2Bridge

                output_dir = os.path.join(self.komposos_path, "boltz2_structures")
                pred = Boltz2Bridge(output_dir=output_dir).predict_binding(drug, target)
                score = 0.6 * float(pred.binding_score) + 0.4 * float(pred.confidence)
                return ScoreResult(
                    score=max(0.0, min(1.0, score)),
                    source="boltz2_bridge",
                    detail=f"binding={pred.binding_score:.3f}, confidence={pred.confidence:.3f}",
                )
            except Exception as exc:
                return self._fallback("structure_binding", drug, target, detail=str(exc))
        return self._fallback("structure_binding", drug, target)

    def drug_likeness(self, drug: str) -> ScoreResult:
        """Use KOMPOSOS drug properties if available."""
        if self.use_komposos:
            try:
                self._ensure_path()
                from data.drugs.drug_properties import get_drug_likeness

                score = get_drug_likeness(drug)
                if score is not None:
                    return ScoreResult(float(score), "drug_properties", "Lipinski-style score")
            except Exception as exc:
                return self._fallback("drug_likeness", drug, detail=str(exc))
        return self._fallback("drug_likeness", drug)

    def _load_category(self):
        if self._category is not None:
            return self._category
        self._ensure_path()
        from validation.repurposing_benchmark import load_full_typed_view

        db_path = os.path.join(self.komposos_path, "data", "drugs", "tier1.db")
        self._category, _missing = load_full_typed_view(db_path=db_path)
        return self._category

    def _load_abpp(self):
        if self._abpp is not None:
            return self._abpp
        self._ensure_path()
        from abpp_bridge import ABPPBridge

        db_path = os.path.join(self.komposos_path, "data", "abpp_results.json")
        self._abpp = ABPPBridge(abpp_db_path=db_path)
        return self._abpp

    def _ensure_path(self) -> None:
        if self.komposos_path and self.komposos_path not in sys.path:
            sys.path.insert(0, self.komposos_path)

    def _fallback(self, kind: str, *parts: str, detail: str = "") -> ScoreResult:
        score = _stable_score(kind, *parts)
        suffix = f"; {detail}" if detail else ""
        return ScoreResult(score, "deterministic_fallback", f"{kind}{suffix}")


def initial_drug_state(
    *,
    drug: str,
    disease: str,
    target: Optional[str] = None,
    label: str = "drug-candidate",
) -> WorldState:
    facts: Dict[str, Any] = {"drug": drug, "disease": disease, "phase": "candidate"}
    if target:
        facts["target"] = target
    return WorldState(label=label, facts=facts, evidence=("initial_candidate",))


def build_drug_world_model(
    client: Optional[KompososDrugEvidenceClient] = None,
) -> RuleWorldModel:
    """Build the cheap pharma world model.

    The actions are one-step decisions/evidence-gathering moves. They can be
    selected with any OPERADUM figure profile, e.g. EVIDENCE_FIRST for the most
    substantiated next step or FASTEST_RECOVERY for the quickest next step.
    """
    evidence = client or KompososDrugEvidenceClient()
    model = RuleWorldModel("drug-world")

    @model.action("score_graph_evidence", description="Query existing KOMPOSOS drug-disease paths.")
    def score_graph(state: WorldState) -> WorldPrediction:
        drug, disease = _drug_disease(state)
        score = evidence.graph_evidence(drug, disease)
        figures = _figures(
            score.score,
            evidence_strength=score.score,
            time_hours=0.25,
            money_usd=0.0,
            assay_uncertainty=1.0 - score.score,
        )
        after = state.with_updates(
            facts={"graph_evidence_score": score.score, "phase": "evidence_scored"},
            figures=figures,
            evidence=(f"{score.source}:{score.detail}",),
        )
        return WorldPrediction(
            "score_graph_evidence", state, after, figures,
            confidence=score.score, evidence=after.evidence,
            explanation="Score existing categorical evidence before spending lab or compute budget.",
        )

    @model.action(
        "check_abpp_target_engagement",
        precondition=lambda s: bool(s.facts.get("target")),
        description="Use ABPP target-engagement evidence if available.",
    )
    def check_abpp(state: WorldState) -> WorldPrediction:
        drug = str(state.facts["drug"])
        target = str(state.facts["target"])
        prior = float(state.figures.get("confidence", 0.5))
        score = evidence.target_engagement(drug, target, prior)
        figures = _figures(
            score.score,
            evidence_strength=score.score,
            time_hours=48.0,
            money_usd=5000.0,
            assay_uncertainty=max(0.02, 1.0 - score.score),
            toxicity_risk=0.03,
        )
        after = state.with_updates(
            facts={"target_engagement_score": score.score, "phase": "target_engagement_checked"},
            figures=figures,
            evidence=(f"{score.source}:{score.detail}",),
        )
        return WorldPrediction(
            "check_abpp_target_engagement", state, after, figures,
            confidence=score.score, evidence=after.evidence,
            explanation="Ground the candidate in target-engagement evidence.",
        )

    @model.action(
        "run_structure_binding",
        precondition=lambda s: bool(s.facts.get("target")),
        description="Run or approximate structure-based binding assessment.",
    )
    def run_structure(state: WorldState) -> WorldPrediction:
        drug = str(state.facts["drug"])
        target = str(state.facts["target"])
        score = evidence.structure_binding(drug, target)
        figures = _figures(
            score.score,
            evidence_strength=min(0.75, score.score),
            time_hours=8.0,
            money_usd=150.0,
            assay_uncertainty=max(0.15, 1.0 - score.score),
            off_target_risk=max(0.05, 0.5 * (1.0 - score.score)),
        )
        after = state.with_updates(
            facts={"structure_binding_score": score.score, "phase": "structure_checked"},
            figures=figures,
            evidence=(f"{score.source}:{score.detail}",),
        )
        return WorldPrediction(
            "run_structure_binding", state, after, figures,
            confidence=score.score, evidence=after.evidence,
            explanation="Estimate structure-based binding before committing to experiments.",
        )

    @model.action("check_drug_likeness", description="Check cheap drug-likeness constraints.")
    def check_likeness(state: WorldState) -> WorldPrediction:
        drug = str(state.facts["drug"])
        score = evidence.drug_likeness(drug)
        risk = max(0.02, 1.0 - score.score)
        figures = _figures(
            score.score,
            evidence_strength=0.45,
            time_hours=0.1,
            money_usd=0.0,
            assay_uncertainty=0.65,
            toxicity_risk=risk,
            drug_likeness=score.score,
        )
        after = state.with_updates(
            facts={"drug_likeness": score.score, "phase": "developability_checked"},
            figures=figures,
            evidence=(f"{score.source}:{score.detail}",),
        )
        return WorldPrediction(
            "check_drug_likeness", state, after, figures,
            confidence=score.score, evidence=after.evidence,
            explanation="Cheap developability screen using known molecular properties.",
        )

    return model


def _drug_disease(state: WorldState) -> Tuple[str, str]:
    return str(state.facts["drug"]), str(state.facts["disease"])


def _figures(
    confidence: float,
    *,
    evidence_strength: float,
    time_hours: float,
    money_usd: float,
    assay_uncertainty: float,
    toxicity_risk: float = 0.02,
    off_target_risk: float = 0.02,
    hERG_risk: float = 0.02,
    drug_likeness: Optional[float] = None,
) -> Dict[str, float]:
    out = {
        "confidence": _clip(confidence),
        "evidence_strength": _clip(evidence_strength),
        "time_hours": float(time_hours),
        "money_usd": float(money_usd),
        "assay_uncertainty": _clip(assay_uncertainty),
        "toxicity_risk": _clip(toxicity_risk),
        "off_target_risk": _clip(off_target_risk),
        "hERG_risk": _clip(hERG_risk),
    }
    if drug_likeness is not None:
        out["drug_likeness"] = _clip(drug_likeness)
    return out


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _stable_score(*parts: str) -> float:
    raw = sum((i + 1) * ord(ch) for i, text in enumerate(parts) for ch in text)
    return round(0.35 + 0.5 * ((raw % 1000) / 1000.0), 4)

