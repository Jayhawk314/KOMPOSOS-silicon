# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""Tests for core/harness.py — the live harness exchange on a real domain."""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.harness import GeneratorService
from domains import NUMERIC_PRIMITIVES, NUMERIC_GOALS


def run(coro):
    return asyncio.run(coro)


IS_PRIME = (
    "def solve(n):\n"
    "    n = int(n)\n"
    "    if n < 2:\n"
    "        return False\n"
    "    i = 2\n"
    "    while i * i <= n:\n"
    "        if n % i == 0:\n"
    "            return False\n"
    "        i += 1\n"
    "    return True\n"
)
IS_PRIME_WRONG = "def solve(n):\n    return True\n"


def service():
    return GeneratorService(NUMERIC_PRIMITIVES, NUMERIC_GOALS)


class TestLiveHarnessExchange(unittest.TestCase):
    def test_two_phase_run_implement_run(self):
        svc = service()

        # Phase 1: OPERADUM composes digit_sum; novel goals are pending.
        r1 = run(svc.run())
        self.assertIn("digit_sum", r1["built"])
        self.assertIn("is_prime", r1["pending"])
        self.assertIn("digit_sum_is_prime", r1["pending"])

        # Phase 2: the open requests are surfaced for the harness.
        pend = {p["goal"] for p in svc.pending()}
        self.assertIn("is_prime", pend)

        # Phase 3: harness submits is_prime -> gated -> accepted.
        res = run(svc.implement("is_prime", IS_PRIME))
        self.assertTrue(res["accepted"], msg=res)

        # Phase 4: the composite goal can now build.
        r2 = run(svc.run())
        self.assertEqual(r2["pending"], [])
        self.assertIn("digit_sum_is_prime", r2["built"])

        # Phase 5: capabilities are real on fresh inputs.
        self.assertEqual(run(svc.call("digit_sum", 778))["output"], 22)
        self.assertTrue(run(svc.call("is_prime", 97))["output"])
        self.assertTrue(run(svc.call("digit_sum_is_prime", 41))["output"])   # 4+1=5 prime
        self.assertFalse(run(svc.call("digit_sum_is_prime", 123))["output"]) # 1+2+3=6

    def test_wrong_implementation_is_rejected_by_gates(self):
        svc = service()
        run(svc.run())
        res = run(svc.implement("is_prime", IS_PRIME_WRONG))  # returns True always
        self.assertFalse(res["accepted"])
        self.assertNotIn("is_prime", svc.status()["built"])

    def test_pending_shrinks_after_accepted_implementation(self):
        svc = service()
        run(svc.run())
        before = len(svc.pending())
        run(svc.implement("is_prime", IS_PRIME))
        run(svc.run())
        self.assertLess(len(svc.pending()), before)


if __name__ == "__main__":
    unittest.main()
