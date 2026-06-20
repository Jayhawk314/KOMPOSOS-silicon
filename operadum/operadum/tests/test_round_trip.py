# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
KOMPOSOS round-trip tests: OPERADUM designs, KOMPOSOS verifies the same structure.

Exit (master spec S16 #5): round-trip soundness -- compile_to_komposos preserves
composition, so the base engine verifies the structure OPERADUM built.
"""

import math
import pytest

from operadum.core.operad import Operad
from operadum.core.types import Spec
from operadum.core.enrichment import MAX_CAPACITY
from operadum.wright.engine import Wright
from operadum.bridges.komposos_bridge import compile_to_komposos, cost_to_confidence
from operadum.bridges.round_trip import KomposVerifier, MiniCategory
from operadum.domains.synthesis_design import SynthesisDesignDomain


def chain_operad():
    op = Operad("chain")
    op.add_op("tok", ["RawText"], "Tokens", cost={"ms": 2}, fn=lambda s: s.split())
    op.add_op("embed", ["Tokens"], "Embedding", cost={"ms": 8}, fn=len)
    return op


def test_minicategory_composes_multiplicatively():
    """MiniCategory mirrors KOMPOSOS: g.f confidence = f.conf * g.conf."""
    cat = MiniCategory()
    cat.connect("A", "B", "f", 0.9)
    cat.connect("B", "C", "g", 0.8)
    assert math.isclose(cat.compose_path("A", "C"), 0.72)
    assert cat.compose_path("C", "A") is None


def test_roundtrip_agrees_on_a_chain():
    op = chain_operad()
    design = Wright(op).synthesize(Spec(inputs=("RawText",), output="Embedding")).construction
    result = KomposVerifier().verify(design.composite, op)
    assert result.verdict == "AGREE"
    assert result.structure_preserved
    assert result.sound


def test_roundtrip_soundness_is_a_homomorphism():
    """composed confidence == cost_to_confidence(total cost): the additive-cost
    -> multiplicative-confidence map is an exact monoid homomorphism."""
    op = chain_operad()
    design = Wright(op).synthesize(Spec(inputs=("RawText",), output="Embedding")).construction
    result = KomposVerifier(lam=0.05).verify(design.composite, op)
    expected = cost_to_confidence({"ms": 10}, lam=0.05)
    assert math.isclose(result.composed_confidence, expected)
    assert math.isclose(result.expected_confidence, expected)


def test_roundtrip_on_domain_route():
    domain = SynthesisDesignDomain()
    op = domain.build_operad()
    design = Wright(op, max_depth=8).optimize(
        Spec(inputs=("Benzene",), output="Paracetamol")).construction
    result = KomposVerifier().verify(design.composite, op)
    assert result.verdict == "AGREE"
    # The compiled graph is a genuine reaction network ending at the target.
    graph = compile_to_komposos(design.composite, op)
    assert graph.root == "Paracetamol"
    assert {"nitrate", "reduce", "acetylate", "hydroxylate"} <= \
           {m["name"] for m in graph.morphisms}


def test_roundtrip_flags_lossy_resource_map():
    """Under a non-additive monoid the cost->confidence map is lossy (spec
    limitation #7): structure is preserved (HOLLOW) but the homomorphism fails."""
    op = Operad("peak", monoid=MAX_CAPACITY)
    op.add_op("a", ["X"], "Y", cost={"mem": 4}, fn=lambda x: x)
    op.add_op("b", ["Y"], "Z", cost={"mem": 9}, fn=lambda x: x)
    design = Wright(op).synthesize(Spec(inputs=("X",), output="Z")).construction
    result = KomposVerifier().verify(design.composite, op)
    assert result.structure_preserved
    # max(4,9)=9 != 4+9 as costs, so product-of-confidences != exp(-lam*peak).
    assert result.verdict == "HOLLOW"
    assert not result.sound
