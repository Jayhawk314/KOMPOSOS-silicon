# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
KOMPOSOS-IV-PHARM evidence adapter for the shared domain_core contracts.

This module is intentionally an adapter, not a copied KOMPOSOS subsystem. It reads
an external KOMPOSOS-IV-PHARM checkout when available and converts graph paths,
mechanistic edges, direct labels, and benchmark scores into EvidencePacket items
that PRONOIA can rank and certify.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence

from domain_core import Candidate, EvidenceItem, EvidencePacket

DEFAULT_KOMPOSOS_PHARM_PATH = r"C:\Users\JAMES\github\KOMPOSOS-IV-PHARM"


@dataclass(frozen=True)
class PharmPair:
    """Drug/disease pair with an optional mechanistic target."""

    drug: str
    disease: str
    target: Optional[str] = None


class KompososPharmEvidenceProvider:
    """Build EvidencePacket objects from a KOMPOSOS-IV-PHARM graph.

    Tests can pass a preloaded/fake `category`; production use points the adapter
    at a real KOMPOSOS-IV-PHARM checkout. The adapter never mutates KOMPOSOS data.
    """

    def __init__(
        self,
        komposos_path: str = DEFAULT_KOMPOSOS_PHARM_PATH,
        *,
        quality_tier: str = "all",
        max_paths: int = 8,
        max_mechanisms: int = 12,
        include_benchmark_score: bool = True,
        use_komposos: bool = True,
        category: Any = None,
    ) -> None:
        self.komposos_path = komposos_path
        self.quality_tier = quality_tier
        self.max_paths = int(max_paths)
        self.max_mechanisms = int(max_mechanisms)
        self.include_benchmark_score = bool(include_benchmark_score)
        self.use_komposos = bool(use_komposos)
        self._category = category
        self._category_override = category is not None
        self._morphism_record_cache: dict[str, Mapping[str, Any] | None] = {}

    def evidence_for(self, candidate: Candidate, task: str) -> EvidencePacket:
        pair = pair_from_candidate(candidate)
        context: dict[str, Any] = {
            "adapter": "komposos_pharm",
            "komposos_path": self.komposos_path,
            "quality_tier": self.quality_tier,
            "drug": pair.drug,
            "disease": pair.disease,
        }
        if pair.target:
            context["target"] = pair.target

        items: list[EvidenceItem] = []
        if not self.use_komposos:
            items.append(_unavailable_item(pair, "KOMPOSOS use disabled"))
            return EvidencePacket(candidate, task, tuple(items), context)

        try:
            category = self._load_category()
        except Exception as exc:
            items.append(_unavailable_item(pair, str(exc)))
            context["error"] = str(exc)
            return EvidencePacket(candidate, task, tuple(items), context)

        items.extend(self._direct_edge_items(category, pair))
        items.extend(self._mechanism_items(category, pair))
        items.extend(self._path_items(category, pair))
        if self.include_benchmark_score:
            score_item = self._benchmark_score_item(category, pair)
            if score_item is not None:
                items.append(score_item)

        if not items:
            items.append(EvidenceItem(
                "komposos_pharm",
                f"no graph evidence found for {pair.drug} -> {pair.disease}",
                score=0.0,
                weight=0.0,
                provenance="adapter",
            ))
        return EvidencePacket(candidate, task, tuple(items), context)

    def _load_category(self) -> Any:
        if self._category is not None:
            return self._category
        if not os.path.isdir(self.komposos_path):
            raise FileNotFoundError(
                f"KOMPOSOS-IV-PHARM checkout not found at {self.komposos_path}"
            )
        self._ensure_path()
        from validation.repurposing_benchmark import load_full_typed_view

        db_path = os.path.join(self.komposos_path, "data", "drugs", "tier1.db")
        self._category, _missing = load_full_typed_view(
            db_path=db_path,
            quality_tier=self.quality_tier,
        )
        return self._category

    def _direct_edge_items(self, category: Any, pair: PharmPair) -> list[EvidenceItem]:
        wanted = {(pair.drug, pair.disease)}
        if pair.target:
            wanted.add((pair.drug, pair.target))
            wanted.add((pair.target, pair.disease))
        out: list[EvidenceItem] = []
        for morphism in _morphisms(category):
            if (_source(morphism), _target(morphism)) not in wanted:
                continue
            out.append(self._edge_item("komposos_edge", morphism))
        return out

    def _mechanism_items(self, category: Any, pair: PharmPair) -> list[EvidenceItem]:
        if pair.target:
            return []

        by_source: dict[str, list[Any]] = defaultdict(list)
        into_disease: dict[str, list[Any]] = defaultdict(list)
        for morphism in _morphisms(category):
            by_source[_source(morphism)].append(morphism)
            if _target(morphism) == pair.disease:
                into_disease[_source(morphism)].append(morphism)

        out: list[EvidenceItem] = []
        for first in by_source.get(pair.drug, []):
            mid = _target(first)
            if mid == pair.disease:
                continue
            for second in into_disease.get(mid, []):
                score = _clip((_confidence(first) * _confidence(second)) ** 0.5)
                claim = (
                    f"mechanistic chain {pair.drug} -[{_name(first)}]-> {mid}; "
                    f"{mid} -[{_name(second)}]-> {pair.disease}"
                )
                out.append(EvidenceItem(
                    "komposos_mechanism",
                    claim,
                    score=score,
                    weight=score,
                    provenance=_combined_provenance(
                        self._morphism_metadata(first),
                        self._morphism_metadata(second),
                    ),
                    metadata={
                        "first": self._morphism_metadata(first),
                        "second": self._morphism_metadata(second),
                    },
                ))
        out.sort(key=lambda item: item.score, reverse=True)
        return out[: self.max_mechanisms]

    def _path_items(self, category: Any, pair: PharmPair) -> list[EvidenceItem]:
        try:
            paths = category.find_paths(pair.drug, pair.disease, max_length=4)
        except Exception:
            return []
        out: list[EvidenceItem] = []
        for path in list(paths)[: self.max_paths]:
            ids = list(getattr(path, "morphism_ids", ()) or ())
            score = _clip(float(getattr(path, "weight", 0.0) or 0.0))
            label = "; ".join(str(part) for part in ids) if ids else f"{pair.drug}->{pair.disease}"
            morphism_records = [
                record for record in (self._morphism_record_by_id(str(morphism_id)) for morphism_id in ids)
                if record is not None
            ]
            out.append(EvidenceItem(
                "komposos_path",
                f"evidence path {pair.drug} -> {pair.disease}: {label}",
                score=score,
                weight=score,
                provenance="path_search",
                metadata={
                    "morphism_ids": ids,
                    "length": getattr(path, "length", None),
                    "morphisms": morphism_records,
                    "provenance": _unique_nonempty(
                        str(record.get("provenance", "")) for record in morphism_records
                    ),
                    "pmids": _unique_nonempty(
                        pmid
                        for record in morphism_records
                        for pmid in _pmids(str(record.get("provenance", "")))
                    ),
                    "evidence_tiers": _unique_nonempty(
                        str(record.get("evidence_tier", "")) for record in morphism_records
                    ),
                },
            ))
        return out

    def _benchmark_score_item(self, category: Any, pair: PharmPair) -> EvidenceItem | None:
        if self._category_override:
            return None
        cwd = os.getcwd()
        try:
            self._ensure_path()
            os.chdir(self.komposos_path)
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                from validation.repurposing_benchmark import make_strategies, score_pair_detailed

                details = score_pair_detailed(make_strategies(category), pair.drug, pair.disease)
        except Exception as exc:
            return EvidenceItem(
                "komposos_benchmark_error",
                f"current KOMPOSOS scorer unavailable for {pair.drug} -> {pair.disease}: {exc}",
                score=0.0,
                weight=0.0,
                provenance="adapter",
            )
        finally:
            os.chdir(cwd)

        score = _clip(float(details.get("score", 0.0) or 0.0))
        votes = details.get("votes", ()) or ()
        vote_text = ", ".join(f"{name}={value:.3f}" for name, value in votes)
        return EvidenceItem(
            "komposos_benchmark",
            f"current KOMPOSOS repurposing score {pair.drug} -> {pair.disease}: {score:.3f}; {vote_text}",
            score=score,
            weight=score,
            provenance="repurposing_benchmark",
            metadata=details,
        )

    def _ensure_path(self) -> None:
        if self.komposos_path and self.komposos_path not in sys.path:
            sys.path.insert(0, self.komposos_path)

    def _edge_item(self, source: str, morphism: Any) -> EvidenceItem:
        score = _confidence(morphism)
        metadata = self._morphism_metadata(morphism)
        claim = f"{_source(morphism)} -[{_name(morphism)}]-> {_target(morphism)}"
        return EvidenceItem(
            source,
            claim,
            score=score,
            weight=score,
            provenance=str(metadata.get("provenance") or _provenance(morphism)),
            metadata=metadata,
        )

    def _morphism_metadata(self, morphism: Any) -> Mapping[str, Any]:
        base_metadata = getattr(morphism, "metadata", {}) or {}
        if isinstance(base_metadata, str):
            base_metadata = _parse_json_mapping(base_metadata)
        record = self._morphism_record_for(morphism)
        metadata: dict[str, Any] = {
            "id": _morphism_id(morphism),
            "name": _name(morphism),
            "source": _source(morphism),
            "target": _target(morphism),
            "confidence": _confidence(morphism),
            "provenance": _provenance(morphism),
            "metadata": base_metadata,
        }
        if record:
            metadata.update({
                "id": record.get("id") or metadata["id"],
                "name": record.get("name") or metadata["name"],
                "source": record.get("source") or metadata["source"],
                "target": record.get("target") or metadata["target"],
                "confidence": record.get("confidence", metadata["confidence"]),
                "provenance": record.get("provenance", metadata["provenance"]),
                "evidence_tier": record.get("evidence_tier"),
                "quantitative_value": record.get("quantitative_value"),
                "value_unit": record.get("value_unit"),
                "sample_size": record.get("sample_size"),
                "confidence_lower": record.get("confidence_lower"),
                "confidence_upper": record.get("confidence_upper"),
                "metadata": record.get("metadata", base_metadata),
                "pmids": record.get("pmids", ()),
                "raw_morphism": record,
            })
        return metadata

    def _morphism_record_for(self, morphism: Any) -> Mapping[str, Any] | None:
        morphism_id = _morphism_id(morphism)
        if morphism_id:
            return self._morphism_record_by_id(morphism_id)
        return None

    def _morphism_record_by_id(self, morphism_id: str) -> Mapping[str, Any] | None:
        if not morphism_id:
            return None
        if morphism_id in self._morphism_record_cache:
            return self._morphism_record_cache[morphism_id]

        db_path = os.path.join(self.komposos_path, "data", "drugs", "tier1.db")
        if not os.path.isfile(db_path):
            self._morphism_record_cache[morphism_id] = None
            return None

        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    """
                    SELECT
                        id, name, source_name, target_name, metadata, confidence,
                        provenance, evidence_tier, quantitative_value, value_unit,
                        sample_size, confidence_lower, confidence_upper
                    FROM morphisms
                    WHERE id = ?
                    """,
                    (morphism_id,),
                ).fetchone()
        except sqlite3.Error:
            row = None

        record = _morphism_record_from_row(row) if row is not None else None
        self._morphism_record_cache[morphism_id] = record
        return record


def pharm_candidate(
    drug: str,
    disease: str,
    *,
    target: str | None = None,
    claim: str | None = None,
    identifier: str | None = None,
) -> Candidate:
    """Create a domain_core Candidate for a drug repurposing hypothesis."""
    if claim is None:
        if target:
            claim = f"{drug} treats {disease} through {target}-linked mechanism"
        else:
            claim = f"{drug} treats {disease}"
    return Candidate(
        identifier=identifier or f"drug:{drug}|disease:{disease}",
        name=drug,
        kind="drug_repurposing",
        target=disease,
        claim=claim,
        metadata={"drug": drug, "disease": disease, "target": target or ""},
    )


def pair_from_candidate(candidate: Candidate) -> PharmPair:
    metadata = dict(candidate.metadata or {})
    drug = str(metadata.get("drug") or candidate.name)
    disease = str(metadata.get("disease") or candidate.target)
    target = metadata.get("target") or metadata.get("target_protein") or None
    target_text = None if target in (None, "") else str(target)
    if not disease:
        raise ValueError(f"Candidate {candidate.name!r} does not specify a disease target")
    return PharmPair(drug=drug, disease=disease, target=target_text)


def _morphisms(category: Any) -> Sequence[Any]:
    morphisms = category.morphisms
    return tuple(morphisms() if callable(morphisms) else morphisms)


def _source(morphism: Any) -> str:
    return str(getattr(morphism, "source", getattr(morphism, "source_name", "")))


def _target(morphism: Any) -> str:
    return str(getattr(morphism, "target", getattr(morphism, "target_name", "")))


def _name(morphism: Any) -> str:
    return str(getattr(morphism, "name", getattr(morphism, "predicate", "related_to")))


def _confidence(morphism: Any) -> float:
    return _clip(float(getattr(morphism, "confidence", 1.0) or 1.0))


def _provenance(morphism: Any) -> str:
    return str(getattr(morphism, "provenance", "") or "")


def _morphism_id(morphism: Any) -> str:
    explicit_id = getattr(morphism, "id", None)
    if explicit_id:
        return str(explicit_id)
    name = _name(morphism)
    source = _source(morphism)
    target = _target(morphism)
    if name and source and target:
        return f"{name}:{source}->{target}"
    return ""


def _morphism_record_from_row(row: sqlite3.Row) -> Mapping[str, Any]:
    provenance = str(row["provenance"] or "")
    return {
        "id": row["id"],
        "name": row["name"],
        "source": row["source_name"],
        "target": row["target_name"],
        "metadata": _parse_json_mapping(row["metadata"]),
        "confidence": _clip(float(row["confidence"] or 0.0)),
        "provenance": provenance,
        "evidence_tier": row["evidence_tier"],
        "quantitative_value": row["quantitative_value"],
        "value_unit": row["value_unit"],
        "sample_size": row["sample_size"],
        "confidence_lower": row["confidence_lower"],
        "confidence_upper": row["confidence_upper"],
        "pmids": _pmids(provenance),
    }


def _parse_json_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}
    return parsed if isinstance(parsed, Mapping) else {"raw": parsed}


def _pmids(provenance: str) -> tuple[str, ...]:
    out: list[str] = []
    for part in str(provenance).replace(",", ";").split(";"):
        item = part.strip()
        if item.upper().startswith("PMID:"):
            pmid = item.split(":", 1)[1].strip()
            if pmid:
                out.append(pmid)
    return tuple(out)


def _combined_provenance(*metadata_items: Mapping[str, Any]) -> str:
    return "; ".join(_unique_nonempty(str(item.get("provenance", "")) for item in metadata_items))


def _unique_nonempty(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return tuple(out)


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _unavailable_item(pair: PharmPair, reason: str) -> EvidenceItem:
    return EvidenceItem(
        "komposos_pharm_unavailable",
        f"no KOMPOSOS PHARM evidence loaded for {pair.drug} -> {pair.disease}: {reason}",
        score=0.0,
        weight=0.0,
        provenance="adapter",
    )


__all__ = [
    "DEFAULT_KOMPOSOS_PHARM_PATH",
    "KompososPharmEvidenceProvider",
    "PharmPair",
    "pair_from_candidate",
    "pharm_candidate",
]
