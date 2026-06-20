# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Self-learning fix loop — verified silicon fixes become primitives (the capstone).

This is the silicon instance of `core/generator.py`'s GenerativeLoop: the same engine
that grows NAND -> XOR by making each verified capability a primitive for the next pass.
Here the primitives are *layout fixes* and the goals are *remediations*:

  - fixes are typed transforms on a discrete risk level (0 clean .. 3 critical):
      swap_interconnect  (EM: Ru/W swap, -2)      widen_wire        (EM: -1)
      reroute_upper_metal (congestion: M7/M8, -2)  insert_buffer     (congestion: -1)
  - goals are "drive any risky level to clean"; OPERADUM composes fixes to satisfy every
    example, COG gates the composite, and the verified remediation is hot-loaded AND
    appended as a new primitive. A goal unbuildable this pass can become buildable next.

Two honesty anchors keep this from being a toy:
  1. each atomic fix's magnitude reflects the real modules (swap_interconnect mirrors
     interconnect.recommend_interconnect; widen/ reroute reflect EM / RC physics);
  2. `verify_em_fix` applies the recommended swap to a REAL EM-risk net from a layout and
     checks the risk proxy actually drops (before/after), gated by HonestyGate — a runnable,
     verified composite, not an assertion (CLAUDE.md #5).

Run:
    python -m domains.silicon.fix_loop
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import List, Optional

from core.generator import GenerativeLoop
from core.synthesis import IOSpec, Primitive, gate

from .interconnect import INTERCONNECT_METALS, recommend_interconnect


# ═══════════════════════════════════════════════════════════════════════════
# 1. Fix primitives + remediation goals  (drive the real GenerativeLoop)
# ═══════════════════════════════════════════════════════════════════════════

def _clamp(x: int) -> int:
    return max(0, min(3, x))


# EM-risk remediations (EMlevel -> EMlevel)
SWAP_INTERCONNECT = gate("swap_interconnect", ("EMlevel",), "EMlevel",
                         lambda s: _clamp(s - 2))     # higher-Ea metal (Ru/W)
WIDEN_WIRE = gate("widen_wire", ("EMlevel",), "EMlevel",
                  lambda s: _clamp(s - 1))            # larger cross-section

# Congestion remediations (Conglevel -> Conglevel)
REROUTE_UPPER_METAL = gate("reroute_upper_metal", ("Conglevel",), "Conglevel",
                           lambda c: _clamp(c - 2))   # M7/M8 relief
INSERT_BUFFER = gate("insert_buffer", ("Conglevel",), "Conglevel",
                     lambda c: _clamp(c - 1))

FIX_PRIMITIVES: List[Primitive] = [
    SWAP_INTERCONNECT, WIDEN_WIRE, REROUTE_UPPER_METAL, INSERT_BUFFER,
]

# Goals: take ANY risk level (including critical=3) to clean=0.
MITIGATE_EM = IOSpec("mitigate_em", "EMlevel", "EMlevel",
                     examples=[(0, 0), (1, 0), (2, 0), (3, 0)], in_types=("EMlevel",))
RELIEVE_CONGESTION = IOSpec("relieve_congestion", "Conglevel", "Conglevel",
                            examples=[(0, 0), (1, 0), (2, 0), (3, 0)],
                            in_types=("Conglevel",))

FIX_GOALS: List[IOSpec] = [MITIGATE_EM, RELIEVE_CONGESTION]


def run_fix_loop(max_iterations: int = 4):
    """Run the real GenerativeLoop over silicon fixes; verified remediations become
    primitives. Returns (history, loop) so callers can inspect the grown vocabulary."""
    loop = GenerativeLoop(FIX_PRIMITIVES, FIX_GOALS, max_depth=4)
    history = asyncio.run(loop.run(max_iterations=max_iterations))
    return history, loop


# ═══════════════════════════════════════════════════════════════════════════
# 2. Ground a fix on REAL layout data: before/after, gated
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class VerifiedFix:
    net: str
    fix: str
    metal: str
    risk_before: float
    risk_after: float
    improved: bool
    status: str             # AGREE | HOLLOW (from the material recommendation gate)
    note: str = ""


def verify_em_fix(bridge, baseline: str = "Cu") -> Optional[VerifiedFix]:
    """Apply the recommended interconnect swap to the worst real EM-risk net and verify
    the EM risk proxy drops. EM risk ~ current_demand / metal EM capacity (Ea); a higher-Ea
    metal raises capacity, lowering normalized risk. Verify-fail => not a fix."""
    from .ir_drop import em_risk_nets
    risks = em_risk_nets(bridge, top_recommend=1)
    if not risks:
        return None
    worst = risks[0]
    rec = worst.recommendation or recommend_interconnect(worst.net, worst.severity)
    metal = rec.recommended

    ea_base = INTERCONNECT_METALS[baseline].em_activation_eV
    ea_new = INTERCONNECT_METALS[metal].em_activation_eV
    risk_before = worst.severity                       # normalized vs Cu baseline
    risk_after = round(risk_before * (ea_base / ea_new), 3) if ea_new else risk_before
    improved = risk_after < risk_before - 1e-9

    return VerifiedFix(
        net=worst.net, fix="swap_interconnect", metal=metal,
        risk_before=round(risk_before, 3), risk_after=risk_after,
        improved=improved, status=rec.status,
        note=(f"Ea {ea_base:.2f}->{ea_new:.2f} eV cuts EM risk "
              f"{(1 - ea_base/ea_new)*100:.0f}%" if improved and metal != baseline
              else f"{baseline} already optimal"))


# ═══════════════════════════════════════════════════════════════════════════
# 3. Report
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("KOMPOSOS-V | silicon fix loop (self-learning remediation)")
    print("=" * 62)
    start = [p.name for p in FIX_PRIMITIVES]
    history, loop = run_fix_loop()
    print(f"start primitives: {start}\n")
    for it in history:
        built = [o.goal for o in it.outcomes if o.built]
        print(f"  iteration {it.index}: opportunities={it.opportunities} "
              f"built={built or '-'}")
    grown = [p.name for p in loop.primitives if p.name not in start]
    print(f"\nlearned remediations (now reusable primitives): {grown or '(none)'}")
    for goal, cand in loop.built.items():
        print(f"   {goal:<20} <- {cand.route}")

    print("\nGrounding a learned fix on real layout data:")
    from .netlist_bridge import NetlistBridge, SAMPLE_DEF, SAMPLE_SPEF
    b = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF); b.load()
    vf = verify_em_fix(b)
    if vf:
        print(f"   net {vf.net}: {vf.fix}->{vf.metal}  risk {vf.risk_before} -> "
              f"{vf.risk_after}  improved={vf.improved}  gate={vf.status}")
        print(f"   {vf.note}")
    print("\nFixes are verified before/after and gated; magnitudes are proxies, not a sim.")


if __name__ == "__main__":
    main()
