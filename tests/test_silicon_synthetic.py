# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Rung 0 laws: the synthetic chip's planted structure must be recovered.

These are falsifiable — they assert the geometry/coherence find the *specific*
structure we planted (the bus bottleneck, the A|B seam, the ghost CONTRADICT),
not merely that something ran.
"""

from domains.silicon.synthetic import (
    build_synthetic_chip, congestion_corridors, chiplet_seam, coherence_check,
    CORE_A, CORE_B,
)


def test_bus_is_the_worst_congestion_corridor():
    """The single inter-core bus is the most negative-curvature wire."""
    chip = build_synthetic_chip()
    corridors = congestion_corridors(chip)
    assert corridors[0].net == "n_bus_AB"
    assert corridors[0].curvature < 0          # bottleneck is hyperbolic
    # intra-core wires are meshed => non-negative
    assert all(c.curvature >= 0 for c in corridors if c.net != "n_bus_AB")


def test_fiedler_seam_separates_the_two_cores():
    """The Fiedler partition recovers core A vs core B; the cut is the bus."""
    chip = build_synthetic_chip()
    seam = chiplet_seam(chip)
    sides = [set(seam.partition_a), set(seam.partition_b)]
    assert set(CORE_A) in sides
    assert set(CORE_B) in sides
    assert seam.cut_nets == ["n_bus_AB"]


def test_ghost_net_is_the_only_contradiction():
    """The unrouted logical net is CONTRADICT; the bus is TENSION; rest GLUE."""
    chip = build_synthetic_chip()
    verdicts = {v.net: v.verdict for v in coherence_check(chip)}
    assert verdicts["n_ghost_fetch"] == "CONTRADICT"
    assert verdicts["n_bus_AB"] == "TENSION"
    contradictions = [n for n, v in verdicts.items() if v == "CONTRADICT"]
    assert contradictions == ["n_ghost_fetch"]


def test_removing_the_contradiction_makes_the_chip_coherent():
    """Falsifiability: route the ghost net and the CONTRADICT disappears."""
    chip = build_synthetic_chip()
    chip.routes["n_ghost_fetch"] = 0.25        # now physically realized, matches spec
    verdicts = {v.net: v.verdict for v in coherence_check(chip)}
    assert "CONTRADICT" not in verdicts.values()
