# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
OPERADUM Phase 4 demo: self-construction & learning.

Run:  python -m examples.self_construction_demo

The system improves its own component set from its build history:
  1. Synthesize several designs; the PatternMiner records the episodes and
     learns which interface shapes tend to be realizable.
  2. It PROPOSES recurring sub-designs and auto-lifts them into new components.
  3. A previously multi-step target is now a one-step (Tier-0) build.
  4. The SelfObserver flags a redundant (dominated) operation.
  5. The PluginGenerator packages the self-extended operad as a fresh,
     shippable DomainPlugin -- mine -> lift -> package -> reload.
"""

from operadum.core.operad import Operad
from operadum.core.types import Spec
from operadum.core.plugin_generator import PluginGenerator
from operadum.wright.engine import Wright
from operadum.gate.pattern_miner import PatternMiner
from operadum.gate.self_observer import SelfObserver


def main():
    op = Operad("nlp")
    op.add_op("tok", ["RawText"], "Tokens", cost={"ms": 2}, fn=lambda s: s.split())
    op.add_op("embed", ["Tokens"], "Embedding", cost={"ms": 8}, fn=len)
    op.add_op("embed_slow", ["Tokens"], "Embedding", cost={"ms": 40}, fn=len)  # redundant
    op.add_op("classify", ["Embedding"], "Label", cost={"ms": 3}, fn=lambda e: e > 2)
    op.add_op("cluster", ["Embedding"], "Cluster", cost={"ms": 4}, fn=lambda e: e)

    w = Wright(op)
    miner = PatternMiner(op, min_support=2, min_size=2)

    print("1) Build history (the system synthesizes a few designs):")
    for output in ("Label", "Cluster"):
        r = w.synthesize(Spec(inputs=("RawText",), output=output))
        miner.record_result(r)
        print(f"     {output:9s} <- {r.construction.wiring}")
    miner.record_result(w.synthesize(Spec(inputs=("RawText",), output="Protein")))  # fails
    print(f"   learned realizability rate: {miner.realizability_rate():.2f} overall, "
          f"{miner.realizability_rate('Embedding'):.2f} for Embedding")
    print()

    print("2) Proposed reusable components (mined from history):")
    for p in miner.propose():
        print(f"     {p}")
    lifted = miner.auto_lift()
    print(f"   auto-lifted: {[o.name for o in lifted]}")
    print()

    print("3) Reapply: RawText -> Embedding is now a one-step build:")
    again = w.synthesize(Spec(inputs=("RawText",), output="Embedding"))
    print(f"     {again.construction.wiring}  (tier {again.tier})")
    print()

    print("4) Self-observation:")
    report = SelfObserver(op).observe()
    print(f"     sources={report.source_colours}  sinks={report.sink_colours}")
    for proposal in report.proposals:
        print(f"     - {proposal}")
    print()

    print("5) Package the self-extended operad as a fresh DomainPlugin:")
    plugin = PluginGenerator().materialize(op, name="nlp-learned")
    print(f"     plugin '{plugin.name}' with {len(plugin.operations())} operations "
          f"(incl. the lifted ones)")
    src = PluginGenerator().generate_source(op, class_name="NlpLearnedDomain")
    print(f"     generated {len(src.splitlines())} lines of importable plugin source")


if __name__ == "__main__":
    main()
