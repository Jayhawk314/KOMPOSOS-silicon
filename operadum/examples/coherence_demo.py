# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
OPERADUM Phase 3 demo: coherence, certification, patterns, accuracy.

Run:  python -m examples.coherence_demo

Shows:
  1. The associahedron K_4: 5 bracketings of an associative op -> 1 normal form.
  2. Formal proofs: Mac Lane coherence, confluence, resource conservation.
  3. WRIGHT Tier 4: a certified construction (unique up to coherence, sound).
  4. PatternMiner: a recurring sub-design lifted into a reusable component.
  5. The synthesis-accuracy benchmark (optimum recall).
"""

from operadum import Operad, Spec, Wright, Polytope, CoherenceProver, catalan
from operadum.core.types import Composite
from operadum.gate.pattern_miner import PatternMiner
from operadum.validation.benchmark import run_benchmark


def coherence():
    op = Operad("assoc")
    op.add_op("mk", ["Raw"], "V", cost={"u": 1}, fn=lambda x: x)
    op.add_op("merge", ["V", "V"], "V", cost={"u": 1}, fn=lambda a, b: a + b)
    poly = Polytope(op).declare_associative("merge")
    prover = CoherenceProver(op, poly)

    operands = [op.get_op("mk").as_composite() for _ in range(4)]
    print("1) Associahedron K_4 (4 operands):")
    print("   ", prover.prove_coherence(op.get_op("merge"), operands))

    merge = op.get_op("merge")
    a, b, c, d = (op.get_op("mk").as_composite() for _ in range(4))
    term = Composite(merge, [("sub", Composite(merge, [
        ("sub", Composite(merge, [("sub", a), ("sub", b)])), ("sub", c)])), ("sub", d)])
    print("2) Formal proofs on a left-nested term:")
    print("   ", prover.prove_confluence(term))
    print("   ", prover.prove_conservation(term))
    print()


def certification():
    op = Operad("pipe")
    op.add_op("tok", ["RawText"], "Tokens", cost={"ms": 2}, fn=lambda s: s.split())
    op.add_op("embed", ["Tokens"], "Embedding", cost={"ms": 8}, fn=len)
    cert = Wright(op).certify(Spec(inputs=("RawText",), output="Embedding"))
    print("3) WRIGHT Tier 4 certificate:")
    print("   ", cert)
    print("    conservation:", cert.conservation)
    print("    linear      :", cert.linear)
    print()


def patterns():
    op = Operad("patterns")
    op.add_op("tok", ["RawText"], "Tokens", cost={"ms": 2}, fn=lambda s: s.split())
    op.add_op("embed", ["Tokens"], "Embedding", cost={"ms": 8}, fn=len)
    op.add_op("classify", ["Embedding"], "Label", cost={"ms": 3}, fn=lambda e: e > 2)
    op.add_op("cluster", ["Embedding"], "Cluster", cost={"ms": 4}, fn=lambda e: e)
    w = Wright(op)
    miner = PatternMiner(op, min_support=2, min_size=2)
    for output in ("Label", "Cluster"):
        miner.record_result(w.synthesize(Spec(inputs=("RawText",), output=output)))

    pattern = next(p for p in miner.mine() if p.wiring == "embed(tok(RawText))")
    print("4) Mined pattern:", pattern)
    miner.lift(pattern, name="text_to_embedding")
    again = w.synthesize(Spec(inputs=("RawText",), output="Embedding"))
    print("   reapplied ->", again.construction.wiring, "at tier", again.tier)
    print()


def accuracy():
    print("5) Synthesis-accuracy benchmark (random operads vs brute-force optimum):")
    print("   ", run_benchmark(n_trials=50, seed=0))


if __name__ == "__main__":
    coherence()
    certification()
    patterns()
    accuracy()
