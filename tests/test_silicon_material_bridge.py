# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Rung 1 laws: the material proposal is gated by physics + COG + HonestyGate.

Falsifiable targets from docs/SILICON_PLAN.md §5: a known-good heterostructure
passes (AGREE, would persist); a known-bad one is rejected (REJECT, never persists).
"""

import pytest

from domains.silicon.material_bridge import (
    validate_interface, analyze_stack, verdict_for_interface, MaterialBridge,
    GAN_ALGAN_POWER, GAAS_ALGAAS_HEMT, MOS2_WS2_2D, SIC_GAN_POWER,
    PROBLEMATIC_GAN_GAAS, PROBLEMATIC_GAAS_SI, PROBLEMATIC_INSB_SI,
)


# --- the headline falsifiable target --------------------------------------

def test_good_stack_passes_bad_stack_rejected():
    assert analyze_stack(GAN_ALGAN_POWER).viable is True
    assert analyze_stack(PROBLEMATIC_GAN_GAAS).viable is False


def test_verdict_agrees_on_gan_algan():
    v = verdict_for_interface("GaN", "AlGaN", context=["GaAs", "Si"])
    assert v.status == "AGREE"
    assert v.persisted is True
    assert v.viable is True
    assert v.cog_status != "reject"


def test_verdict_rejects_gan_gaas():
    v = verdict_for_interface("GaN", "GaAs", context=["AlGaN", "Si"])
    assert v.status == "REJECT"
    assert v.persisted is False
    assert v.viable is False


# --- the scorers/physics behave ------------------------------------------

@pytest.mark.parametrize("stack", [GAAS_ALGAAS_HEMT, MOS2_WS2_2D, SIC_GAN_POWER])
def test_known_good_stacks_viable(stack):
    assert analyze_stack(stack).viable is True


@pytest.mark.parametrize("stack", [PROBLEMATIC_GAAS_SI, PROBLEMATIC_INSB_SI])
def test_known_bad_stacks_unviable(stack):
    assert analyze_stack(stack).viable is False


def test_lattice_veto_blocks_huge_mismatch():
    """GaN/GaAs: wurtzite vs zincblende, ~56% a-mismatch -> lattice veto."""
    s = validate_interface("GaN", "GaAs")
    assert s.lattice_match < 0.25
    assert s.viable is False
    assert "veto" in s.details


def test_weakest_interface_is_the_bottleneck():
    """In a 3-layer stack, analysis flags the lowest-scoring interface."""
    a = analyze_stack(SIC_GAN_POWER)
    assert a.weakest is not None
    assert a.weakest.total == min(s.total for s in a.interfaces)


# --- the bridge only admits viable interfaces -----------------------------

def test_bridge_loads_only_viable_interfaces():
    bridge = MaterialBridge(["GaN", "AlGaN", "GaAs"])
    bridge.load()
    cat = bridge.category
    assert cat.get("GaN") is not None
    edges = {(m.source, m.target) for m in cat.morphisms()}
    # GaN/AlGaN is viable; GaN/GaAs and GaAs(z.b.)/AlGaN(wurtzite) are not
    assert ("GaN", "AlGaN") in edges or ("AlGaN", "GaN") in edges
    assert ("GaN", "GaAs") not in edges and ("GaAs", "GaN") not in edges
