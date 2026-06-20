# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
LEF (Library Exchange Format) ingestion — standard-cell library awareness.

The netlist bridge (Rung 2) had to guess net direction ("first listed pin = driver")
and had no notion of cell size. LEF fixes both: each MACRO carries a physical SIZE and
its PINs carry a DIRECTION (INPUT/OUTPUT/INOUT). With LEF we know the *real* driver of
a net (its OUTPUT pin), the real sinks (INPUT pins), and each cell's area — which the
scoreboard showed is where the accuracy is.

Grammar (LEF 5.8):
    MACRO INV_X1
      SIZE 0.38 BY 1.4 ;
      PIN A
        DIRECTION INPUT ;
      PIN ZN
        DIRECTION OUTPUT ;
      ...
    END INV_X1

Pure stdlib. Validated on the real Nangate45 library.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Macro:
    name: str
    width: float = 0.0          # microns
    height: float = 0.0
    pins: Dict[str, str] = field(default_factory=dict)   # pin -> INPUT|OUTPUT|INOUT

    @property
    def area(self) -> float:
        return self.width * self.height

    def output_pins(self) -> List[str]:
        return [p for p, d in self.pins.items() if d == "OUTPUT"]

    def is_signal_pin(self, pin: str) -> bool:
        return self.pins.get(pin, "INOUT") in ("INPUT", "OUTPUT")


def parse_lef(text: str) -> Dict[str, Macro]:
    """Parse all MACRO blocks into {cell_name: Macro}."""
    macros: Dict[str, Macro] = {}
    # each MACRO <name> ... END <name> block (name back-reference handles nesting safely)
    for m in re.finditer(r"\bMACRO\s+(\S+)\b(.*?)\bEND\s+\1\b", text, re.DOTALL):
        name, body = m.group(1), m.group(2)
        size = re.search(r"\bSIZE\s+([\d.]+)\s+BY\s+([\d.]+)", body)
        w, h = (float(size.group(1)), float(size.group(2))) if size else (0.0, 0.0)

        # pin direction: scan each PIN block (DIRECTION may not be the first line)
        pins: Dict[str, str] = {}
        starts = [(pm.start(), pm.group(1))
                  for pm in re.finditer(r"\bPIN\s+(\S+)", body)]
        for i, (pos, pname) in enumerate(starts):
            end = starts[i + 1][0] if i + 1 < len(starts) else len(body)
            dm = re.search(r"\bDIRECTION\s+(\w+)", body[pos:end])
            pins[pname] = dm.group(1).upper() if dm else "INOUT"
        macros[name] = Macro(name, w, h, pins)
    return macros


def driver_pin(macro: Macro) -> str | None:
    """The cell's output pin (its net's driver), if exactly identifiable."""
    outs = macro.output_pins()
    return outs[0] if outs else None
