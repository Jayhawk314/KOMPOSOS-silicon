# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-IV-Commercial
# Copyright (c) 2024-2026 James Ray Hawkins

"""Tests for the logic-circuit domain — n-ary DAG synthesis (XOR from NAND)."""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.synthesis import CapabilityForge, OperadumProposer, IOSpec, Primitive
from core.generator import GenerativeLoop
from domains import CIRCUIT_PRIMITIVES, CIRCUIT_GOALS, NAND


def run(coro):
    return asyncio.run(coro)


XOR = IOSpec("xor", "Bit", "Bit",
             [((0, 0), 0), ((0, 1), 1), ((1, 0), 1), ((1, 1), 0)],
             in_types=("Bit", "Bit"))


class TestDiagramSynthesis(unittest.TestCase):
    def test_xor_from_nand_alone(self):
        forge = CapabilityForge([NAND], proposers=[OperadumProposer(diagram_nodes=6)])
        res = run(forge.synthesize(XOR))

        self.assertTrue(res.ok, msg=res.note)
        self.assertEqual(res.candidate.source, "operadum")
        self.assertIn("diagram", res.candidate.route)  # a DAG, not a chain

        # The realized circuit is a real, correct XOR.
        fn = run(forge.host.get_capability("xor"))
        self.assertEqual([fn(a, b) for a in (0, 1) for b in (0, 1)], [0, 1, 1, 0])

    def test_not_needs_fanout(self):
        # NOT is unary but cannot be a single-input chain over a 2-input NAND;
        # it requires fan-out NAND(a, a), which only the diagram path can build.
        not_goal = IOSpec("not_g", "Bit", "Bit", [(0, 1), (1, 0)])
        res = run(CapabilityForge([NAND],
                                  proposers=[OperadumProposer()]).synthesize(not_goal))
        self.assertTrue(res.ok, msg=res.note)
        self.assertIn("diagram", res.candidate.route)


class TestCircuitGenerativeLoop(unittest.TestCase):
    def test_designs_full_gate_family_from_nand(self):
        prims = [Primitive(p.name, p.in_type, p.out_type, p.fn, in_types=p.in_types)
                 for p in CIRCUIT_PRIMITIVES]
        loop = GenerativeLoop(prims, CIRCUIT_GOALS, max_depth=4)
        run(loop.run())

        for gate_name in ("not_gate", "and_gate", "or_gate", "xor_gate"):
            self.assertIn(gate_name, loop.built, msg=f"{gate_name} not designed")
            self.assertIn(gate_name, [p.name for p in loop.primitives])

        # Verify every truth table on the hot-loaded circuits.
        and_fn = run(loop.host.get_capability("and_gate"))
        or_fn = run(loop.host.get_capability("or_gate"))
        xor_fn = run(loop.host.get_capability("xor_gate"))
        not_fn = run(loop.host.get_capability("not_gate"))
        self.assertEqual([and_fn(a, b) for a in (0, 1) for b in (0, 1)], [0, 0, 0, 1])
        self.assertEqual([or_fn(a, b) for a in (0, 1) for b in (0, 1)], [0, 1, 1, 1])
        self.assertEqual([xor_fn(a, b) for a in (0, 1) for b in (0, 1)], [0, 1, 1, 0])
        self.assertEqual([not_fn(a) for a in (0, 1)], [1, 0])


class TestBackwardCompatNumeric(unittest.TestCase):
    def test_single_input_domain_still_works(self):
        # The n-ary generalization must not regress unary synthesis.
        from domains import NUMERIC_PRIMITIVES
        prims = [Primitive(p.name, p.in_type, p.out_type, p.fn) for p in NUMERIC_PRIMITIVES]
        spec = IOSpec("digit_sum", "Int", "Int", [(123, 6), (99, 18), (5, 5)])
        forge = CapabilityForge(prims, proposers=[OperadumProposer()])
        res = run(forge.synthesize(spec))
        self.assertTrue(res.ok, msg=res.note)
        self.assertEqual(res.candidate.fn(2025), 9)  # unary chain still composes
        self.assertEqual(run(forge.host.get_capability("digit_sum"))(2025), 9)


if __name__ == "__main__":
    unittest.main()
