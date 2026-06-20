# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Fix-loop laws: verified remediations are composed, become primitives, and a real fix
improves the metric before/after (the self-learning capstone)."""

import pytest

from domains.silicon.fix_loop import (
    run_fix_loop, verify_em_fix, FIX_PRIMITIVES,
    SWAP_INTERCONNECT, WIDEN_WIRE, REROUTE_UPPER_METAL,
)
from domains.silicon.interconnect import INTERCONNECT_METALS
from domains.silicon.netlist_bridge import NetlistBridge, SAMPLE_DEF, SAMPLE_SPEF


@pytest.fixture(scope="module")
def loop_run():
    return run_fix_loop()


# --- atomic fixes ---------------------------------------------------------

def test_atomic_fixes_clamp_in_range():
    assert SWAP_INTERCONNECT.fn(3) == 1 and SWAP_INTERCONNECT.fn(1) == 0
    assert WIDEN_WIRE.fn(3) == 2 and WIDEN_WIRE.fn(0) == 0
    assert REROUTE_UPPER_METAL.fn(3) == 1


# --- the GenerativeLoop self-learning mechanic ----------------------------

def test_loop_learns_remediations_as_primitives(loop_run):
    history, loop = loop_run
    start = {p.name for p in FIX_PRIMITIVES}
    assert "mitigate_em" in loop.built and "relieve_congestion" in loop.built
    grown = {p.name for p in loop.primitives} - start
    assert "mitigate_em" in grown        # verified capability became a primitive


def test_learned_remediation_drives_any_risk_to_clean(loop_run):
    _, loop = loop_run
    fn = loop.built["mitigate_em"].fn
    assert all(fn(s) == 0 for s in (0, 1, 2, 3))   # composed fix satisfies every example


def test_loop_converges(loop_run):
    history, _ = loop_run
    assert history[-1].newly_built == 0            # nothing new to add -> converged


# --- grounding a learned fix on real data ---------------------------------

def test_verify_em_fix_improves_and_is_gated():
    b = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF); b.load()
    vf = verify_em_fix(b)
    assert vf is not None
    assert vf.improved and vf.risk_after < vf.risk_before
    assert vf.status == "AGREE"
    assert INTERCONNECT_METALS[vf.metal].em_activation_eV > \
        INTERCONNECT_METALS["Cu"].em_activation_eV     # swapped to a higher-Ea metal


def test_cli_fixloop_emits_learned_and_verified(capsys):
    import json
    from domains.silicon import agent_tools
    agent_tools.main(["fixloop"])
    out = json.loads(capsys.readouterr().out)
    assert out["tool"] == "fixloop"
    assert "mitigate_em" in out["learned"]
    assert out["verified_fix"]["improved"] is True
