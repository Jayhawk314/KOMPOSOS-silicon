"""PRONOIA: interpretable, non-LLM prediction stack."""

from .honesty_mdl import (
    ReasoningStep,
    SincerityReport,
    description_bits,
    most_sincere,
    sincerity,
)
from .honest_rank import HonestlyRanked, grounding_of, honest_rank
from .mdl_ranker import Hypothesis, RankedHypothesis, compression_gain, rank
from .scm import SCM
from .sheaf_probe import ContradictionReport, Sheaf, SheafEdge
from .tsetlin import Clause, TsetlinMachine
from .vsa import HDComputing

try:
    from .domain_adapter import PronoiaPredictor
except ImportError:  # Keep the original standalone PRONOIA package usable.
    PronoiaPredictor = None  # type: ignore[assignment]

__all__ = [
    "Clause",
    "ContradictionReport",
    "HDComputing",
    "HonestlyRanked",
    "Hypothesis",
    "PronoiaPredictor",
    "RankedHypothesis",
    "ReasoningStep",
    "SCM",
    "Sheaf",
    "SheafEdge",
    "SincerityReport",
    "TsetlinMachine",
    "compression_gain",
    "description_bits",
    "grounding_of",
    "honest_rank",
    "most_sincere",
    "rank",
    "sincerity",
]
