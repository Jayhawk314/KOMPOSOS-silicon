# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Phase 3 tests: Polytope coherence + formal proofs.

Exit criterion (master spec, Phase 3): unique normal-form designs.
"""

import pytest

from operadum.core.operad import Operad
from operadum.core.polytope import Polytope
from operadum.core.formal_coherence import CoherenceProver, catalan


def assoc_operad():
    op = Operad("assoc")
    # An associative binary merge on colour V, plus a leaf maker.
    op.add_op("mk", ["Raw"], "V", cost={"u": 1}, fn=lambda x: x)
    op.add_op("merge", ["V", "V"], "V", cost={"u": 1}, fn=lambda a, b: a + b)
    return op


def leaf(op):
    return op.get_op("mk").as_composite()


# ---------------------------------------------------------------- normal form

def test_rebracketings_share_normal_form():
    op = assoc_operad()
    poly = Polytope(op).declare_associative("merge")
    a, b, c = leaf(op), leaf(op), leaf(op)
    # ((a b) c) and (a (b c)) are different trees...
    left = op.compose(op.compose("merge", 0, a), 1, c)   # builds merge(merge(a,_),c)-ish
    # Build explicitly to be unambiguous:
    from operadum.core.types import Composite
    merge = op.get_op("merge")
    left_assoc = Composite(merge, [("sub", Composite(merge, [("sub", a), ("sub", b)])),
                                   ("sub", c)])
    right_assoc = Composite(merge, [("sub", a),
                                    ("sub", Composite(merge, [("sub", b), ("sub", c)]))])
    assert left_assoc.to_wiring() != right_assoc.to_wiring()      # different designs
    assert poly.equivalent(left_assoc, right_assoc)              # ...same normal form
    assert poly.normalize(left_assoc).to_wiring() == \
           poly.normalize(right_assoc).to_wiring()


def test_unit_elimination():
    op = assoc_operad()
    poly = Polytope(op)
    idV = op.identity("V")
    design = op.compose("merge", 0, idV)   # merge(id_V(V), V)
    nf = poly.normalize(design)
    assert "id_V" not in nf.to_wiring()    # the unit is gone
    assert nf.open_inputs() == design.open_inputs()


# ---------------------------------------------------------------- Mac Lane

def test_maclane_coherence_all_bracketings_collapse():
    op = assoc_operad()
    poly = Polytope(op).declare_associative("merge")
    prover = CoherenceProver(op, poly)
    operands = [leaf(op) for _ in range(4)]      # K_4 = pentagon
    proof = prover.prove_coherence(op.get_op("merge"), operands)
    assert proof.holds
    assert proof.data["vertices"] == catalan(3)  # 5 bracketings
    assert proof.data["normal_forms"] == 1


def test_catalan_numbers():
    assert [catalan(n) for n in range(5)] == [1, 1, 2, 5, 14]


# ---------------------------------------------------------------- confluence

def test_confluence_of_rewrites():
    op = assoc_operad()
    poly = Polytope(op).declare_associative("merge")
    prover = CoherenceProver(op, poly)
    from operadum.core.types import Composite
    merge = op.get_op("merge")
    a, b, c, d = (leaf(op) for _ in range(4))
    # A deeply left-nested term has several rewrite paths to the normal form.
    term = Composite(merge, [
        ("sub", Composite(merge, [
            ("sub", Composite(merge, [("sub", a), ("sub", b)])), ("sub", c)])),
        ("sub", d)])
    proof = prover.prove_confluence(term)
    assert proof.holds


# ---------------------------------------------------------------- conservation

def test_resource_conservation_is_proven():
    op = assoc_operad()
    poly = Polytope(op).declare_associative("merge")
    prover = CoherenceProver(op, poly)
    from operadum.core.types import Composite
    merge = op.get_op("merge")
    a, b, c = (leaf(op) for _ in range(3))
    term = Composite(merge, [("sub", Composite(merge, [("sub", a), ("sub", b)])),
                             ("sub", c)])
    proof = prover.prove_conservation(term)
    assert proof.holds
    assert proof.data["cost_before"] == proof.data["cost_after"]
    assert proof.data["multiset_invariant"]


def test_certify_returns_certificate():
    from operadum.core.types import Spec
    from operadum.wright.engine import Wright
    op = Operad("pipe")
    op.add_op("tok", ["RawText"], "Tokens", cost={"ms": 2}, fn=lambda s: s.split())
    op.add_op("embed", ["Tokens"], "Embedding", cost={"ms": 8}, fn=len)
    cert = Wright(op).certify(Spec(inputs=("RawText",), output="Embedding"))
    assert cert is not None
    assert cert.certified
    assert cert.unique
    assert cert.conservation.holds
    assert cert.linear.ok
