# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
PRONOIA benchmark on the KOMPOSOS-IV-PHARM drug-repurposing universe.

This is the Phase 1 measurement harness:

    Candidate -> KOMPOSOS PHARM EvidencePacket -> PRONOIA PredictionReport

It compares PRONOIA's bits/grounding score against the existing KOMPOSOS
repurposing label universe. KOMPOSOS remains external and read-only.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Optional, Sequence

from domain_core import Candidate
from pronoia.domain_adapter import PronoiaPredictor

from ..integrations.komposos_pharm_evidence import (
    DEFAULT_KOMPOSOS_PHARM_PATH,
    KompososPharmEvidenceProvider,
    pharm_candidate,
)
from ..integrations.pronoia_pharm_loop import (
    PharmScoreConfig,
    score_pharm_report_v2,
)


@dataclass(frozen=True)
class PairScore:
    drug: str
    disease: str
    label: int
    pronoia_score: float
    pronoia_gain_bits: float
    grounding: float
    fabricated_bits: float
    abstained: bool
    evidence_items: int
    evidence_chars: int
    evidence_sum: float
    evidence_max: float
    edge_max: float
    path_max: float
    mechanism_max: float
    komposos_score: float = 0.0


@dataclass(frozen=True)
class MetricBlock:
    auroc: float
    auprc: float
    hits_at_5: float
    hits_at_10: float
    hits_at_20: float
    mrr: float


@dataclass(frozen=True)
class PronoiaPharmBenchmarkResult:
    protocol: str
    quality_tier: str
    n_drugs: int
    n_diseases: int
    n_pairs: int
    n_positives: int
    n_abstained: int
    abstention_rate: float
    mean_grounding: float
    pronoia: MetricBlock
    pronoia_raw_gain: MetricBlock
    pronoia_gain_per_item: MetricBlock
    pronoia_gain_per_kchar: MetricBlock
    grounding: MetricBlock
    evidence_sum: MetricBlock
    evidence_max: MetricBlock
    edge_max: MetricBlock
    path_max: MetricBlock
    mechanism_max: MetricBlock
    komposos: MetricBlock | None
    top_pronoia: tuple[PairScore, ...] = field(default_factory=tuple)
    top_false_positives: tuple[PairScore, ...] = field(default_factory=tuple)
    missed_positives: tuple[PairScore, ...] = field(default_factory=tuple)


def evaluate_pronoia_pharm(
    *,
    komposos_path: str = DEFAULT_KOMPOSOS_PHARM_PATH,
    protocol: str = "remove_direct_labels",
    quality_tier: str = "all",
    min_grounding: float = 0.2,
    max_pairs: Optional[int] = None,
    include_komposos_baseline: bool = True,
    top_k: int = 12,
) -> PronoiaPharmBenchmarkResult:
    """Run PRONOIA over the PHARM drug/disease label universe.

    Protocols:
    - `as_loaded`: direct Drug->Disease labels remain visible in evidence.
      This is a sanity check.
    - `remove_direct_labels`: direct labels and label-derived bridges are hidden
      from evidence, but positives are taken from the full graph. This is the
      useful prediction protocol.
    """
    if protocol not in {"as_loaded", "remove_direct_labels"}:
        raise ValueError("protocol must be 'as_loaded' or 'remove_direct_labels'")

    bench = _load_pharm_benchmark_module(komposos_path)
    db_path = os.path.join(komposos_path, "data", "drugs", "tier1.db")
    remove_direct = protocol == "remove_direct_labels"

    with _quiet_external_imports():
        category, _missing = bench.load_full_typed_view(
            db_path=db_path,
            remove_direct_labels=remove_direct,
            quality_tier=quality_tier,
        )
        base_category, _ = bench.load_full_typed_view(
            db_path=db_path,
            quality_tier=quality_tier,
        )
    drugs, diseases, _visible_positives = bench.drug_disease_pairs(category)
    _base_drugs, _base_diseases, positives = bench.drug_disease_pairs(base_category)

    pairs = [(drug, disease) for drug in drugs for disease in diseases]
    if max_pairs is not None:
        pairs = pairs[: int(max_pairs)]

    provider = KompososPharmEvidenceProvider(
        komposos_path=komposos_path,
        quality_tier=quality_tier,
        include_benchmark_score=False,
        category=category,
    )
    predictor = PronoiaPredictor(min_grounding=min_grounding)

    baseline_scores: dict[tuple[str, str], float] = {}
    if include_komposos_baseline:
        baseline_scores = _score_komposos_baseline(bench, category, pairs, komposos_path)

    rows: list[PairScore] = []
    for drug, disease in pairs:
        candidate = pharm_candidate(drug, disease)
        packet = provider.evidence_for(candidate, "PHARM drug repurposing benchmark")
        report = score_pharm_report_v2(
            predictor.predict(packet),
            PharmScoreConfig(min_grounding=min_grounding),
        )
        evidence_stats = _evidence_stats(packet)
        gain = float(report.metrics.get("raw_mdl_gain_bits", report.metrics.get("gain_bits", report.score)))
        grounding = float(report.metrics.get("grounding", 0.0))
        fabricated = float(report.metrics.get("fabricated_bits", 0.0))
        gated_score = 0.0 if report.abstained else float(report.score)
        rows.append(PairScore(
            drug=drug,
            disease=disease,
            label=1 if (drug, disease) in positives else 0,
            pronoia_score=gated_score,
            pronoia_gain_bits=gain,
            grounding=grounding,
            fabricated_bits=fabricated,
            abstained=bool(report.abstained),
            evidence_items=int(evidence_stats["items"]),
            evidence_chars=int(evidence_stats["chars"]),
            evidence_sum=evidence_stats["sum"],
            evidence_max=evidence_stats["max"],
            edge_max=evidence_stats["edge_max"],
            path_max=evidence_stats["path_max"],
            mechanism_max=evidence_stats["mechanism_max"],
            komposos_score=baseline_scores.get((drug, disease), 0.0),
        ))

    labels = [row.label for row in rows]
    pronoia_scores = [row.pronoia_score for row in rows]
    raw_scores = [row.pronoia_gain_bits for row in rows]
    per_item_scores = [row.pronoia_gain_bits / max(1, row.evidence_items) for row in rows]
    per_kchar_scores = [1000.0 * row.pronoia_gain_bits / max(1, row.evidence_chars) for row in rows]
    grounding_scores = [row.grounding for row in rows]
    evidence_sum_scores = [row.evidence_sum for row in rows]
    evidence_max_scores = [row.evidence_max for row in rows]
    edge_max_scores = [row.edge_max for row in rows]
    path_max_scores = [row.path_max for row in rows]
    mechanism_max_scores = [row.mechanism_max for row in rows]
    komposos_scores = [row.komposos_score for row in rows]
    n_abstained = sum(1 for row in rows if row.abstained)
    mean_grounding = _mean(row.grounding for row in rows)

    top_pronoia = tuple(sorted(rows, key=lambda r: r.pronoia_score, reverse=True)[:top_k])
    top_false = tuple(
        row for row in sorted(rows, key=lambda r: r.pronoia_score, reverse=True)
        if row.label == 0
    )[:top_k]
    missed = tuple(
        row for row in sorted(rows, key=lambda r: r.pronoia_score)
        if row.label == 1
    )[:top_k]

    return PronoiaPharmBenchmarkResult(
        protocol=protocol,
        quality_tier=quality_tier,
        n_drugs=len(drugs),
        n_diseases=len(diseases),
        n_pairs=len(rows),
        n_positives=sum(labels),
        n_abstained=n_abstained,
        abstention_rate=n_abstained / len(rows) if rows else 0.0,
        mean_grounding=mean_grounding,
        pronoia=_metrics(pronoia_scores, labels),
        pronoia_raw_gain=_metrics(raw_scores, labels),
        pronoia_gain_per_item=_metrics(per_item_scores, labels),
        pronoia_gain_per_kchar=_metrics(per_kchar_scores, labels),
        grounding=_metrics(grounding_scores, labels),
        evidence_sum=_metrics(evidence_sum_scores, labels),
        evidence_max=_metrics(evidence_max_scores, labels),
        edge_max=_metrics(edge_max_scores, labels),
        path_max=_metrics(path_max_scores, labels),
        mechanism_max=_metrics(mechanism_max_scores, labels),
        komposos=_metrics(komposos_scores, labels) if include_komposos_baseline else None,
        top_pronoia=top_pronoia,
        top_false_positives=top_false,
        missed_positives=missed,
    )


def print_result(result: PronoiaPharmBenchmarkResult) -> None:
    print(f"PRONOIA PHARM benchmark ({result.protocol}, quality={result.quality_tier})")
    print(f"Pairs: {result.n_pairs}  positives: {result.n_positives}  "
          f"abstained: {result.n_abstained} ({result.abstention_rate:.3f})")
    print(f"Mean grounding: {result.mean_grounding:.3f}")
    _print_metrics("PRONOIA v2", result.pronoia)
    _print_metrics("PRONOIA raw gain", result.pronoia_raw_gain)
    _print_metrics("gain / item", result.pronoia_gain_per_item)
    _print_metrics("gain / kchar", result.pronoia_gain_per_kchar)
    _print_metrics("grounding", result.grounding)
    _print_metrics("evidence sum", result.evidence_sum)
    _print_metrics("evidence max", result.evidence_max)
    _print_metrics("edge max", result.edge_max)
    _print_metrics("path max", result.path_max)
    _print_metrics("mechanism max", result.mechanism_max)
    if result.komposos is not None:
        _print_metrics("KOMPOSOS baseline", result.komposos)
    print("\nTop PRONOIA v2 pairs:")
    for row in result.top_pronoia:
        tag = "POS" if row.label else "NEG"
        abstain = " abstain" if row.abstained else ""
        print(f"  {tag} {row.drug:<14} -> {row.disease:<20} "
              f"score={row.pronoia_score:>7.1f} gain={row.pronoia_gain_bits:>7.1f} "
              f"ground={row.grounding:.3f}{abstain}")
    print("\nTop false positives:")
    for row in result.top_false_positives:
        print(f"  {row.drug:<14} -> {row.disease:<20} "
              f"score={row.pronoia_score:>7.1f} ground={row.grounding:.3f}")
    print("\nLowest-scored positives:")
    for row in result.missed_positives:
        abstain = " abstain" if row.abstained else ""
        print(f"  {row.drug:<14} -> {row.disease:<20} "
              f"score={row.pronoia_score:>7.1f} gain={row.pronoia_gain_bits:>7.1f} "
              f"ground={row.grounding:.3f}{abstain}")


def _print_metrics(label: str, metrics: MetricBlock) -> None:
    print(f"{label:<18} AUROC={metrics.auroc:.3f}  AUPRC={metrics.auprc:.3f}  "
          f"H@5={metrics.hits_at_5:.3f}  H@10={metrics.hits_at_10:.3f}  "
          f"H@20={metrics.hits_at_20:.3f}  MRR={metrics.mrr:.3f}")


def _load_pharm_benchmark_module(komposos_path: str):
    if not os.path.isdir(komposos_path):
        raise FileNotFoundError(f"KOMPOSOS-IV-PHARM not found at {komposos_path}")
    if komposos_path not in sys.path:
        sys.path.insert(0, komposos_path)
    cwd = os.getcwd()
    try:
        os.chdir(komposos_path)
        with _quiet_external_imports():
            from validation import repurposing_benchmark
    finally:
        os.chdir(cwd)
    return repurposing_benchmark


def _score_komposos_baseline(
    bench: Any,
    category: Any,
    pairs: Sequence[tuple[str, str]],
    komposos_path: str,
) -> dict[tuple[str, str], float]:
    cwd = os.getcwd()
    try:
        os.chdir(komposos_path)
        with _quiet_external_imports():
            strategies = bench.make_strategies(category)
            return {
                pair: bench.score_pair(strategies, pair[0], pair[1], fail_on_error=False)[0]
                for pair in pairs
            }
    finally:
        os.chdir(cwd)


def _metrics(scores: Sequence[float], labels: Sequence[int]) -> MetricBlock:
    return MetricBlock(
        auroc=pairwise_auroc(scores, labels)[0],
        auprc=compute_auprc(scores, labels),
        hits_at_5=compute_hits_at_k(scores, labels, 5),
        hits_at_10=compute_hits_at_k(scores, labels, 10),
        hits_at_20=compute_hits_at_k(scores, labels, 20),
        mrr=compute_mrr(scores, labels),
    )


def _evidence_stats(packet: Any) -> dict[str, float | int]:
    items = tuple(getattr(packet, "items", ()) or ())
    chars = len("\n".join(item.as_text() for item in items))
    scores = [float(getattr(item, "score", 0.0) or 0.0) for item in items]
    by_source: dict[str, list[float]] = {}
    for item, score in zip(items, scores):
        by_source.setdefault(str(getattr(item, "source", "")), []).append(score)
    return {
        "items": len(items),
        "chars": chars,
        "sum": sum(scores),
        "max": max(scores) if scores else 0.0,
        "edge_max": max(by_source.get("komposos_edge", [0.0])),
        "path_max": max(by_source.get("komposos_path", [0.0])),
        "mechanism_max": max(by_source.get("komposos_mechanism", [0.0])),
    }


def compute_auprc(scores: Sequence[float], labels: Sequence[int]) -> float:
    paired = sorted(zip(scores, labels), key=lambda item: -item[0])
    total_positives = sum(labels)
    if total_positives == 0:
        return 0.0
    tp = 0
    fp = 0
    prev_recall = 0.0
    area = 0.0
    for _score, label in paired:
        if label:
            tp += 1
        else:
            fp += 1
        precision = tp / (tp + fp)
        recall = tp / total_positives
        if recall > prev_recall:
            area += precision * (recall - prev_recall)
            prev_recall = recall
    return area


def compute_hits_at_k(scores: Sequence[float], labels: Sequence[int], k: int) -> float:
    paired = sorted(zip(scores, labels), key=lambda item: -item[0])[:k]
    total_positives = sum(labels)
    return sum(label for _score, label in paired) / min(total_positives, k) if total_positives else 0.0


def compute_mrr(scores: Sequence[float], labels: Sequence[int]) -> float:
    paired = sorted(zip(scores, labels), key=lambda item: -item[0])
    reciprocals = [
        1.0 / rank
        for rank, (_score, label) in enumerate(paired, 1)
        if label
    ]
    return sum(reciprocals) / len(reciprocals) if reciprocals else 0.0


def pairwise_auroc(
    scores: Iterable[float],
    labels: Iterable[int],
) -> tuple[float, int, int, int]:
    true_scores = [score for score, label in zip(scores, labels) if label == 1]
    false_scores = [score for score, label in zip(scores, labels) if label == 0]
    concordant = discordant = tied = 0
    for true_score in true_scores:
        for false_score in false_scores:
            if true_score > false_score:
                concordant += 1
            elif true_score < false_score:
                discordant += 1
            else:
                tied += 1
    total = concordant + discordant + tied
    auroc = (concordant + 0.5 * tied) / total if total else 0.5
    return auroc, concordant, discordant, tied


def _mean(values: Iterable[float]) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


@contextlib.contextmanager
def _quiet_external_imports():
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        yield


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark PRONOIA on KOMPOSOS-IV-PHARM.")
    parser.add_argument("--komposos-path", default=DEFAULT_KOMPOSOS_PHARM_PATH)
    parser.add_argument("--protocol", choices=["as_loaded", "remove_direct_labels"], default="remove_direct_labels")
    parser.add_argument("--quality", default="all")
    parser.add_argument("--min-grounding", type=float, default=0.2)
    parser.add_argument("--max-pairs", type=int, default=None)
    parser.add_argument("--no-komposos-baseline", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = evaluate_pronoia_pharm(
        komposos_path=args.komposos_path,
        protocol=args.protocol,
        quality_tier=args.quality,
        min_grounding=args.min_grounding,
        max_pairs=args.max_pairs,
        include_komposos_baseline=not args.no_komposos_baseline,
    )
    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
