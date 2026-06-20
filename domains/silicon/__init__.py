# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
KOMPOSOS-V silicon co-design domain.

A semiconductor co-design vertical on the shared `Category` substrate. It takes a
chip's *materials* (from the CHEM semiconductor bridge) and its *layout/netlist*
(via the new netlist bridge) and runs categorical + sheaf + flow-geometry analysis,
emitting an honest, receipt-backed waste ledger and action portfolio.

Mostly an integration of existing engines:
  - materials + 5 scorers  <- KOMPOSOS-IV-CHEM/semiconductor_bridge
  - coherence pattern, Ricci/Fiedler flow geometry, waste ledger, agent CLI
                            <- KOMPOSOS-GRID/domains/grid
  - the one new piece: netlist_bridge (layout/netlist -> Category)

Invariant: scores/curvature only PROPOSE; the verdict is COG != REJECT + HonestyGate.
Structural results are `structural_only`; SPEF is `measured_proxy`. STA is `measured`
only with an attested report and hashed netlist/Liberty/SDC context. No silicon physics
is simulated here.

Master plan: docs/SILICON_PLAN.md   Status: docs/SILICON_STATUS.md
Work log: docs/SESSIONS.md
Status: Rungs 0-4 and 6-8 built; Rung 5 real STA evidence remains pending.
"""
