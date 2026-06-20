# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
OPERADUM end-to-end demo: design, then verify.

Run:  python -m examples.pipeline_demo   (from the repo root)

Shows the whole loop on a tiny text-pipeline domain:
  1. Declare colours + operations (the domain content).
  2. Hand WRIGHT a Spec (target interface + budget).
  3. Get a BUILDABLE construction -- a typed composite + a runnable artifact.
  4. Run the artifact.
  5. Compile the design into a KOMPOSOS morphism graph for auditing.
"""

from operadum import Operad, Spec, Wright, ADDITIVE_COST
from operadum.bridges.komposos_bridge import compile_to_komposos


def main():
    # 1. The domain: colours (interface types) and operations (components).
    op = Operad("text-pipeline", monoid=ADDITIVE_COST)
    op.add_op("tokenize", ["RawText"], "Tokens", cost={"ms": 2}, fn=lambda s: s.split())
    op.add_op("embed", ["Tokens"], "Embedding", cost={"ms": 8}, fn=lambda t: len(t))
    op.add_op("merge", ["Embedding", "Embedding"], "Embedding", cost={"ms": 1},
              fn=lambda a, b: a + b)

    print(op)
    print()

    # 2-3. Ask WRIGHT to build RawText -> Embedding within 20ms.
    wright = Wright(op)
    spec = Spec(inputs=("RawText",), output="Embedding", budget={"ms": 20})
    result = wright.synthesize(spec)
    print("SYNTHESIZE", spec.interface)
    print(" ", result)
    print()

    # 4. Run the synthesized artifact.
    run = result.construction.artifact
    print("RUN artifact('the quick brown fox') =", run("the quick brown fox"))
    print()

    # 5. Compile the design to a KOMPOSOS morphism graph for verification.
    graph = compile_to_komposos(result.construction.composite, op)
    print("COMPILE -> KOMPOSOS morphism graph")
    print("  objects:", graph.objects)
    for m in graph.morphisms:
        print(f"  {m['source']} --{m['name']}--> {m['target']}"
              f"  (confidence={m['confidence']:.3f})")


if __name__ == "__main__":
    main()
