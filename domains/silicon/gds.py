# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Minimal stdlib GDSII reader: metal shapes per layer, top-cell or hierarchy-flattened.

No third-party GDS library (stays numpy+stdlib). Parses the GDSII record stream and returns
BOUNDARY/PATH shapes as bounding boxes, keyed by layer. Two modes:
  - `parse_gds_shapes` (default): one structure's OWN shapes (the top cell's routing).
  - `flatten_gds_shapes`: resolves the SREF/AREF hierarchy -- places every referenced
    structure's metal (standard-cell internals, fill, vias) into the top frame by applying
    the GDS placement transform (reflection -> magnification -> rotation -> translation), so
    double-patterning conflict analysis sees the REAL dense metal, not just top-cell routing.

GDSII record = 2-byte big-endian length (incl. 4-byte header), 1-byte record type, 1-byte
data type, then payload. Records used: BGNSTR/STRNAME/ENDSTR (0x05/06/07), BOUNDARY/PATH/
SREF/AREF (0x08/09/0A/0B), SNAME (0x12), STRANS (0x1A), MAG (0x1B), ANGLE (0x1C), COLROW
(0x13), LAYER (0x0D), WIDTH (0x0F), XY (0x10), ENDEL (0x11). MAG/ANGLE use the GDS 8-byte
real format (base-16, excess-64 exponent), not IEEE-754.
"""

from __future__ import annotations

import math
import struct
from typing import Dict, List, Optional, Tuple

BBox = Tuple[int, int, int, int]      # (xmin, ymin, xmax, ymax) in GDS db units


def _gds_real(b: bytes) -> float:
    """Decode a GDS 8-byte real (base-16 mantissa, excess-64 exponent, sign bit)."""
    if len(b) < 8:
        return 0.0
    sign = -1.0 if (b[0] & 0x80) else 1.0
    exp = (b[0] & 0x7F) - 64
    mant = int.from_bytes(b[1:8], "big") / float(1 << 56)
    return sign * mant * (16.0 ** exp)


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


# --- hierarchy flattening (SREF/AREF) -------------------------------------------------------

class _Struct:
    __slots__ = ("shapes", "refs")

    def __init__(self) -> None:
        self.shapes: Dict[int, List[BBox]] = {}
        # each ref: (sname, reflect: bool, mag: float, angle_deg: float, placements: [(x,y)])
        self.refs: List[Tuple[str, bool, float, float, List[Tuple[float, float]]]] = []


def parse_gds_structures(path: str) -> Dict[str, _Struct]:
    """Parse every structure's own shapes AND its SREF/AREF placements (one pass)."""
    with open(path, "rb") as fh:
        data = fh.read()
    structs: Dict[str, _Struct] = {}
    cur: Optional[_Struct] = None
    elem = layer = xy = None
    width = 0
    sname = ""
    reflect = False
    mag = 1.0
    angle = 0.0
    colrow = (1, 1)
    i, n = 0, len(data)
    while i + 4 <= n:
        ln = struct.unpack(">H", data[i:i + 2])[0]
        if ln < 4:
            break
        rt = data[i + 2]
        p = data[i + 4:i + ln]
        i += ln
        if rt == 0x06:                                   # STRNAME
            name = p.split(b"\x00")[0].decode("latin1")
            cur = structs.setdefault(name, _Struct())
        elif rt == 0x07:                                 # ENDSTR
            cur = None
        elif rt in (0x08, 0x09, 0x0A, 0x0B):              # BOUNDARY / PATH / SREF / AREF
            elem, layer, xy, width = rt, None, None, 0
            sname, reflect, mag, angle, colrow = "", False, 1.0, 0.0, (1, 1)
        elif rt == 0x0D and len(p) >= 2:                 # LAYER
            layer = struct.unpack(">h", p[:2])[0]
        elif rt == 0x0F and len(p) >= 4:                 # WIDTH
            width = struct.unpack(">i", p[:4])[0]
        elif rt == 0x12:                                 # SNAME
            sname = p.split(b"\x00")[0].decode("latin1")
        elif rt == 0x1A and len(p) >= 2:                 # STRANS (bit 15 = reflect about x)
            reflect = bool(struct.unpack(">H", p[:2])[0] & 0x8000)
        elif rt == 0x1B:                                 # MAG
            mag = _gds_real(p[:8]) or 1.0
        elif rt == 0x1C:                                 # ANGLE
            angle = _gds_real(p[:8])
        elif rt == 0x13 and len(p) >= 4:                 # COLROW
            colrow = (struct.unpack(">h", p[:2])[0], struct.unpack(">h", p[2:4])[0])
        elif rt == 0x10:                                 # XY (4-byte ints)
            xy = [struct.unpack(">i", p[k:k + 4])[0] for k in range(0, len(p) - 3, 4)]
        elif rt == 0x11:                                 # ENDEL
            if cur is not None and elem in (0x08, 0x09) and layer is not None and xy:
                xs, ys = xy[0::2], xy[1::2]
                if xs and ys:
                    bb = [min(xs), min(ys), max(xs), max(ys)]
                    if elem == 0x09:                     # path: inflate by half-width
                        h = abs(width) // 2
                        bb = [bb[0] - h, bb[1] - h, bb[2] + h, bb[3] + h]
                    cur.shapes.setdefault(layer, []).append(tuple(bb))
            elif cur is not None and elem == 0x0A and sname and xy and len(xy) >= 2:
                cur.refs.append((sname, reflect, mag, angle, [(xy[0], xy[1])]))
            elif cur is not None and elem == 0x0B and sname and xy and len(xy) >= 6:
                # AREF: xy = origin, col-ref, row-ref; instances on a col x row lattice.
                cols, rows = colrow
                ox, oy = xy[0], xy[1]
                cvx, cvy = (xy[2] - ox) / max(cols, 1), (xy[3] - oy) / max(cols, 1)
                rvx, rvy = (xy[4] - ox) / max(rows, 1), (xy[5] - oy) / max(rows, 1)
                places = [(ox + c * cvx + r * rvx, oy + c * cvy + r * rvy)
                          for c in range(cols) for r in range(rows)]
                cur.refs.append((sname, reflect, mag, angle, places))
            elem = None
    return structs


def _top_cell(structs: Dict[str, _Struct], cell: str | None) -> Optional[str]:
    if cell and cell in structs:
        return cell
    referenced = {r[0] for s in structs.values() for r in s.refs}
    roots = [name for name in structs if name not in referenced]
    if len(roots) == 1:
        return roots[0]
    # ambiguous (or none): fall back to the last-defined structure
    return roots[-1] if roots else (list(structs)[-1] if structs else None)


def _xform_bbox(bb: BBox, reflect: bool, mag: float, angle: float,
                tx: float, ty: float) -> BBox:
    """Transform a child bbox into the parent frame: reflect -> mag -> rotate -> translate.

    Rotates all four corners and re-bounds (exact for Manhattan rectangles at 0/90/180/270,
    a correct conservative bound otherwise)."""
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    xs: List[float] = []
    ys: List[float] = []
    for cx, cy in ((bb[0], bb[1]), (bb[2], bb[1]), (bb[2], bb[3]), (bb[0], bb[3])):
        y = -cy if reflect else cy
        x = cx * mag
        y = y * mag
        xr = x * ca - y * sa + tx
        yr = x * sa + y * ca + ty
        xs.append(xr)
        ys.append(yr)
    return (int(round(min(xs))), int(round(min(ys))),
            int(round(max(xs))), int(round(max(ys))))


def flatten_gds_shapes(path: str, cell: str | None = None,
                       max_depth: int = 20) -> Dict[int, List[BBox]]:
    """{layer: [bbox]} for the top cell with the full SREF/AREF hierarchy flattened in."""
    structs = parse_gds_structures(path)
    top = _top_cell(structs, cell)
    out: Dict[int, List[BBox]] = {}

    def walk(name: str, reflect: bool, mag: float, angle: float,
             tx: float, ty: float, depth: int) -> None:
        st = structs.get(name)
        if st is None or depth > max_depth:
            return
        for lyr, boxes in st.shapes.items():
            dst = out.setdefault(lyr, [])
            for bb in boxes:
                dst.append(_xform_bbox(bb, reflect, mag, angle, tx, ty))
        ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        for sname, c_ref, c_mag, c_ang, places in st.refs:
            for (px, py) in places:
                # compose this ref's origin through the parent transform
                ry = -py if reflect else py
                ax, ay = px * mag, ry * mag
                ntx = ax * ca - ay * sa + tx
                nty = ax * sa + ay * ca + ty
                walk(sname, reflect ^ c_ref, mag * c_mag, angle + c_ang,
                     ntx, nty, depth + 1)

    if top is not None:
        walk(top, False, 1.0, 0.0, 0.0, 0.0, 0)
    return out


def gds_features(path: str, layer: int, cell: str | None = None,
                 flatten: bool = False) -> List[Tuple[str, float, float, BBox]]:
    """Real metal shapes on `layer` as (id, center_x, center_y, bbox).

    flatten=False: top-cell routing only (fast). flatten=True: include the full SREF/AREF
    hierarchy (standard-cell internal metal) placed into the top frame."""
    src = flatten_gds_shapes(path, cell) if flatten else parse_gds_shapes(path, cell)
    shapes = src.get(layer, [])
    out = []
    for idx, bb in enumerate(shapes):
        out.append((f"L{layer}_{idx}", (bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0, bb))
    return out
