# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Minimal stdlib GDSII reader: top-cell metal shapes per layer.

No third-party GDS library (stays numpy+stdlib). Parses the GDSII record stream and returns
the BOUNDARY/PATH shapes of one structure (the top cell) as bounding boxes, keyed by layer.
For double-patterning conflict analysis we want the routing on a metal layer in the TOP cell
-- standard-cell internals reached via SREF are hierarchical (local coordinates) and are NOT
resolved here (an honest first-cut limitation: top-cell routing only).

GDSII record = 2-byte big-endian length (incl. 4-byte header), 1-byte record type, 1-byte
data type, then payload. Records used: BGNSTR/STRNAME/ENDSTR (0x05/06/07), BOUNDARY/PATH
(0x08/09), LAYER (0x0D), WIDTH (0x0F), XY (0x10), ENDEL (0x11).
"""

from __future__ import annotations

import struct
from typing import Dict, List, Tuple

BBox = Tuple[int, int, int, int]      # (xmin, ymin, xmax, ymax) in GDS db units


def parse_gds_shapes(path: str, cell: str | None = None) -> Dict[int, List[BBox]]:
    """{layer: [bbox, ...]} for one structure (default: the last/top cell)."""
    with open(path, "rb") as fh:
        data = fh.read()
    per_struct: Dict[str, Dict[int, List[BBox]]] = {}
    cur = None
    last = None
    elem = layer = xy = None
    width = 0
    i, n = 0, len(data)
    while i + 4 <= n:
        ln = struct.unpack(">H", data[i:i + 2])[0]
        if ln < 4:
            break
        rt, _dt = data[i + 2], data[i + 3]
        p = data[i + 4:i + ln]
        i += ln
        if rt == 0x06:                                   # STRNAME
            cur = p.split(b"\x00")[0].decode("latin1")
            per_struct.setdefault(cur, {})
            last = cur
        elif rt == 0x07:                                 # ENDSTR
            cur = None
        elif rt in (0x08, 0x09):                          # BOUNDARY / PATH
            elem, layer, xy, width = rt, None, None, 0
        elif rt == 0x0D and len(p) >= 2:                 # LAYER
            layer = struct.unpack(">h", p[:2])[0]
        elif rt == 0x0F and len(p) >= 4:                 # WIDTH
            width = struct.unpack(">i", p[:4])[0]
        elif rt == 0x10:                                 # XY (4-byte ints)
            xy = [struct.unpack(">i", p[k:k + 4])[0] for k in range(0, len(p) - 3, 4)]
        elif rt == 0x11:                                 # ENDEL
            if elem in (0x08, 0x09) and cur and layer is not None and xy:
                xs, ys = xy[0::2], xy[1::2]
                if xs and ys:
                    bb = [min(xs), min(ys), max(xs), max(ys)]
                    if elem == 0x09:                     # path: inflate by half-width
                        h = abs(width) // 2
                        bb = [bb[0] - h, bb[1] - h, bb[2] + h, bb[3] + h]
                    per_struct[cur].setdefault(layer, []).append(tuple(bb))
            elem = None
    target = cell or last
    return per_struct.get(target, {})


def layer_shape_counts(path: str, cell: str | None = None) -> Dict[int, int]:
    return {lyr: len(b) for lyr, b in parse_gds_shapes(path, cell).items()}


def gds_features(path: str, layer: int, cell: str | None = None
                 ) -> List[Tuple[str, float, float, BBox]]:
    """Real metal shapes on `layer` as (id, center_x, center_y, bbox)."""
    shapes = parse_gds_shapes(path, cell).get(layer, [])
    out = []
    for idx, bb in enumerate(shapes):
        out.append((f"L{layer}_{idx}", (bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0, bb))
    return out
