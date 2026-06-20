"""
Demo: Vector Symbolic Architecture (hyperdimensional computing).

Part 1 — Holographic associative memory: store FOUR drug->target associations in
ONE 10,000-d hypervector, then recover each target by unbinding the drug.

Part 2 — One-shot classification: build a class prototype from a SINGLE example
each, then classify new drugs by shared property hypervectors. No training loop.

    python -m examples.vsa_demo
"""

from __future__ import annotations

from pronoia.vsa import HDComputing


def associative_memory() -> None:
    hd = HDComputing(dim=10000, seed=0)
    pairs = [("Erlotinib", "EGFR"), ("Sotorasib", "KRAS"),
             ("Dabrafenib", "BRAF"), ("Imatinib", "ABL1")]
    for d, t in pairs:
        hd.symbol(d); hd.symbol(t)

    # One vector holding every drug->target association.
    mapping = hd.bundle(*[hd.bind(hd.symbol(d), hd.symbol(t)) for d, t in pairs])
    targets = [t for _, t in pairs]

    print("Holographic associative memory (4 associations in ONE vector):")
    for d, t in pairs:
        recovered = hd.cleanup(hd.bind(mapping, hd.symbol(d)), among=targets)
        ok = "OK" if recovered == t else "MISS"
        print(f"  target_of({d:<11}) -> {recovered:<5} (true {t:<5})  {ok}")


def one_shot_classification() -> None:
    hd = HDComputing(dim=10000, seed=1)

    # Each drug is the bundle of its property symbols (shared within a class).
    drugs = {
        "Erlotinib":     ["ATP_competitive", "kinase_domain", "small_molecule"],
        "Imatinib":      ["ATP_competitive", "kinase_domain", "small_molecule"],
        "Atezolizumab":  ["checkpoint", "antibody", "PD_L1"],
        "Pembrolizumab": ["checkpoint", "antibody", "PD_1"],
    }
    hv = {name: hd.encode_set(props) for name, props in drugs.items()}

    # One-shot prototypes: a SINGLE labelled example per class.
    prototypes = {"kinase_inhibitor": hv["Erlotinib"],
                  "immunotherapy": hv["Atezolizumab"]}

    print("\nOne-shot classification (one labelled example per class):")
    for name in ["Imatinib", "Pembrolizumab"]:
        scored = {cls: hd.similarity(hv[name], proto)
                  for cls, proto in prototypes.items()}
        best = max(scored, key=scored.get)
        sims = ", ".join(f"{c}={s:+.2f}" for c, s in scored.items())
        print(f"  {name:<14} -> {best:<17} ({sims})")


def main() -> None:
    associative_memory()
    one_shot_classification()


if __name__ == "__main__":
    main()
