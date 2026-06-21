# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Per-net INTERCONNECT (wire) delay from a real STA `report_checks` path report.

This is the `measured`-tier upgrade for the tau interconnect-delay test
(`tau_scoreboard.py`, which uses an extracted Elmore R*C proxy). When `report_checks`
is run with `-fields {input_pins ...}` and loaded parasitics, each path table alternates
rows: a driver OUTPUT pin (whose incremental Delay is the cell arc) and a load INPUT pin
(whose incremental Delay is the WIRE delay on the net feeding it). We attribute each
load-pin row's delay to its net using the layout bridge's own pin->net map -- so this does
NOT depend on any fragile `(net ...)` text annotation, only on pin names we already parse
reliably against real OpenSTA/OpenROAD output.

Per net we keep the MAX wire delay seen across all reported paths (worst-case interconnect
delay). The `measured` tier and provenance/hash come from `sta.load_sta` (the report must be
attested `tool` with hashed netlist/liberty/constraints context, exactly like the rest of
the STA path).

Format (verified against real OpenROAD 26Q2 output, `-fields {input_pins net capacitance
slew fanout} -digits 5`): rows carry a VARIABLE number of leading columns --
`Fanout Cap Slew Delay Time` for driver output pins, `Slew Delay Time` for load input pins.
The incremental Delay is therefore the SECOND-to-last number and the cumulative Time is the
LAST, regardless of how many fields are enabled. Net-name rows (`<net> (net)`) and clock
rows carry no edge char (`^`/`v`) and are skipped. The synthetic fixture in
`tests/test_silicon_net_delay.py` mirrors this real layout; adjust `_ROW` and the fixture
together if a tool version changes it.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

# A data row: >=2 leading numbers (... Delay Time), an edge char, then inst/pin (cell).
_ROW = re.compile(
    r"^\s*((?:[-+]?\d*\.?\d+\s+){2,})[\^v]\s+([\w$\\./\[\]]+)/([\w$\\.\[\]]+)\s+\(",
    re.MULTILINE)


def parse_pin_delays(text: str) -> List[Tuple[str, str, float]]:
    """Every path-table row as (instance, pin, incremental_delay).

    Incremental Delay is the second-to-last column; Time is the last. This is stable
    whether the row is a driver output (Fanout Cap Slew Delay Time) or a load input
    (Slew Delay Time).
    """
    out: List[Tuple[str, str, float]] = []
    for m in _ROW.finditer(text):
        nums = m.group(1).split()
        try:
            out.append((m.group(2), m.group(3), float(nums[-2])))
        except (ValueError, IndexError):
            continue
    return out


def build_load_pin_map(bridge) -> Dict[Tuple[str, str], str]:
    """{(instance, pin): net} for LOAD pins of signal nets (driver pin excluded).

    The driver row's delay is a cell arc, not a wire arc, so it must not be attributed
    to the net's interconnect delay.
    """
    lpm: Dict[Tuple[str, str], str] = {}
    for net in bridge.nets:
        if not bridge._is_signal(net):
            continue
        di = bridge._driver_index(net)
        for i, conn in enumerate(net.conns):
            if i != di:
                lpm[conn] = net.name
    return lpm


def net_wire_delays(text: str, bridge) -> Dict[str, float]:
    """Per-net worst-case interconnect (wire) delay from the report and the bridge map."""
    lpm = build_load_pin_map(bridge)
    out: Dict[str, float] = {}
    for inst, pin, delay in parse_pin_delays(text):
        net = lpm.get((inst, pin))
        if net is not None:
            out[net] = max(out.get(net, 0.0), delay)
    return out
