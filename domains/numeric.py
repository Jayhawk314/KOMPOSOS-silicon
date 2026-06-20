# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""
A real (non-toy) numeric domain for the generator.

Primitives are genuine computations; goals are defined by ground-truth examples
computed from actual math, so the EXAMPLE gate really discriminates correct from
type-correct-but-wrong. The domain is deliberately *incomplete*: `is_prime` is
novel logic no composition of the primitives can produce — that goal can only be
filled by the harness (the LLM), behind the gates. And `digit_sum_is_prime` is a
*composite* that becomes buildable only after both `digit_sum` and `is_prime`
exist — the compositional self-improvement case.
"""

from __future__ import annotations

from core.synthesis import IOSpec, Primitive

# ---- primitives: real, executable, single-input ----

NUMERIC_PRIMITIVES = [
    Primitive("to_digits", "Int", "Digits", lambda n: [int(c) for c in str(abs(int(n)))]),
    Primitive("dsum", "Digits", "Int", sum),
]

# ---- goals: defined by ground-truth examples ----

NUMERIC_GOALS = [
    # Composite goal listed FIRST, before its dependencies exist, so the loop
    # must defer it to a later pass (proves compositional self-improvement).
    IOSpec("digit_sum_is_prime", "Int", "Bool",
           [(25, True), (2, True), (41, True), (123, False), (10, False)]),
    # OPERADUM composes this: to_digits -> dsum.
    IOSpec("digit_sum", "Int", "Int",
           [(123, 6), (99, 18), (5, 5), (2025, 9)]),
    # Novel logic — only the harness/LLM can supply it.
    IOSpec("is_prime", "Int", "Bool",
           [(2, True), (3, True), (4, False), (17, True), (1, False), (9, False)]),
]
