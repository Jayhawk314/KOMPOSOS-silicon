# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""Tests for core/synthesis.py — real executable capabilities behind the gates."""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.synthesis import (
    CapabilityForge, IOSpec, OperadumProposer, HarnessProposer,
    ImplementationRequest, TEXT_PRIMITIVES,
)


def run(coro):
    return asyncio.run(coro)


WORD_COUNT = IOSpec("word_count", "Text", "Int",
                    [("a b c", 3), ("hello world there", 3), ("x", 1)])
VOWEL_COUNT = IOSpec("vowel_count", "Text", "Int",
                     [("hello", 2), ("sky", 0), ("aeiou", 5)])


def good_solver(req: ImplementationRequest) -> str:
    if req.spec.name == "vowel_count":
        return "def solve(s):\n    return sum(1 for c in s.lower() if c in 'aeiou')\n"
    return ""


def wrong_solver(req: ImplementationRequest) -> str:
    # A plausible-but-wrong implementation the LLM might emit.
    return "def solve(s):\n    return len(s)\n"


class TestOperadumSynthesis(unittest.TestCase):
    def test_composes_correct_program_from_examples(self):
        forge = CapabilityForge(TEXT_PRIMITIVES, proposers=[OperadumProposer()])
        res = run(forge.synthesize(WORD_COUNT))

        self.assertTrue(res.ok, msg=res.note)
        self.assertEqual(res.candidate.source, "operadum")
        # It chose the word route (via Tokens), NOT the type-correct-but-wrong char_count.
        self.assertIn("Tokens", res.candidate.route)

        # The hot-loaded capability is real and correct on a fresh input.
        fn = run(forge.host.get_capability("word_count"))
        self.assertEqual(fn("the quick brown fox"), 4)

    def test_returns_none_when_uncomposable(self):
        # No primitive computes vowels, so OPERADUM alone cannot solve it.
        res = run(CapabilityForge(TEXT_PRIMITIVES,
                                  proposers=[OperadumProposer()]).synthesize(VOWEL_COUNT))
        self.assertFalse(res.ok)


class TestHarnessImplementer(unittest.TestCase):
    def test_harness_solves_what_operadum_cannot(self):
        forge = CapabilityForge(
            TEXT_PRIMITIVES,
            proposers=[OperadumProposer(), HarnessProposer(solver=good_solver)],
        )
        res = run(forge.synthesize(VOWEL_COUNT))

        self.assertTrue(res.ok, msg=res.note)
        self.assertEqual(res.candidate.source, "harness")
        fn = run(forge.host.get_capability("vowel_count"))
        self.assertEqual(fn("education"), 5)

    def test_gate_rejects_wrong_llm_code(self):
        """The safety property: behaviorally-wrong LLM code never gets loaded."""
        forge = CapabilityForge(
            TEXT_PRIMITIVES,
            proposers=[HarnessProposer(solver=wrong_solver)],
        )
        res = run(forge.synthesize(VOWEL_COUNT))

        self.assertFalse(res.ok)
        self.assertFalse(forge.host.has_capability("vowel_count"))


if __name__ == "__main__":
    unittest.main()
