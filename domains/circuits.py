# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
A logic-circuit domain — designing real circuits from a single NAND gate.

NAND is functionally complete: every Boolean function is some wiring of NANDs,
and some of those (XOR) are DAGs with fan-out that no tree can express. This is
the n-ary case: gates take two inputs, goals are defined by truth tables, and
OPERADUM's `synthesize_diagram` searches typed DAGs to realize each one.

`is_long` had to come from the harness because it was *novel*; here OPERADUM can
design everything from NAND alone — and each synthesized gate becomes a primitive,
so later gates are built from a richer library (compositional self-improvement).
"""

from __future__ import annotations

from core.synthesis import IOSpec, gate

# The one primitive: a NAND gate over bits (0/1).
NAND = gate("nand", ("Bit", "Bit"), "Bit", lambda a, b: int(not (a and b)))
CIRCUIT_PRIMITIVES = [NAND]

# Goals as truth tables. NOT is unary (needs fan-out: NAND(a, a)); the rest are
# 2-input gates. Ordered simplest-first so each builds on the last.
CIRCUIT_GOALS = [
    IOSpec("not_gate", "Bit", "Bit",
           [(0, 1), (1, 0)]),
    IOSpec("and_gate", "Bit", "Bit",
           [((0, 0), 0), ((0, 1), 0), ((1, 0), 0), ((1, 1), 1)],
           in_types=("Bit", "Bit")),
    IOSpec("or_gate", "Bit", "Bit",
           [((0, 0), 0), ((0, 1), 1), ((1, 0), 1), ((1, 1), 1)],
           in_types=("Bit", "Bit")),
    IOSpec("xor_gate", "Bit", "Bit",
           [((0, 0), 0), ((0, 1), 1), ((1, 0), 1), ((1, 1), 0)],
           in_types=("Bit", "Bit")),
]


def _demo() -> None:
    """Design the whole gate family from NAND alone. Run: python -m domains.circuits"""
    import asyncio
    from core.generator import GenerativeLoop

    loop = GenerativeLoop(CIRCUIT_PRIMITIVES, CIRCUIT_GOALS, max_depth=4)
    print(f"start vocabulary: {[p.name for p in loop.primitives]}\n")
    history = asyncio.run(loop.run())

    for it in history:
        for o in it.outcomes:
            if o.built:
                print(f"   [BUILT] {o.goal:<9} {o.route}")
    print(f"\nfinal vocabulary: {[p.name for p in loop.primitives]}")
    print("verifying truth tables on fresh inputs:")
    for g in ("not_gate", "and_gate", "or_gate", "xor_gate"):
        fn = asyncio.run(loop.host.get_capability(g))
        if g == "not_gate":
            print(f"   {g:<9}", [(a, fn(a)) for a in (0, 1)])
        else:
            print(f"   {g:<9}", [((a, b), fn(a, b)) for a in (0, 1) for b in (0, 1)])


if __name__ == "__main__":
    _demo()
