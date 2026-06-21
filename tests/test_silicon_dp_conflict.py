# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Track 3 Step B (first cut): double-patterning native-conflict localization.

Double patterning is feasible iff the conflict graph is 2-colorable iff no odd cycles (a Z/2
H1 obstruction). We check the combinatorial (BFS) and spectral (signless-Laplacian) views
agree, and that a real layer shows the colorable->native-conflict transition.
"""

import math
import os
import struct

import numpy as np
import pytest

from domains.silicon.dp_conflict import (
    analyze, analyze_gds, build_conflict_graph, spectral_frustration, two_color_conflicts,
)
from domains.silicon.gds import (
    _gds_real, _xform_bbox, flatten_gds_shapes, gds_features, parse_gds_shapes,
)


def test_path_is_2_colorable_no_native_conflict():
    # 4 features in a line; only consecutive within distance -> a path -> bipartite.
    feats = [("a", 0, 0), ("b", 2, 0), ("c", 4, 0), ("d", 6, 0)]
    names, adj = build_conflict_graph(feats, distance=2.5)
    colorable, _, frustrated = two_color_conflicts(names, adj)
    assert colorable and frustrated == []
    assert spectral_frustration(names, adj) < 1e-6        # spectral agrees: bipartite


def test_triangle_has_localized_native_conflict():
    # 3 mutually-close features -> a triangle (odd cycle) -> NOT 2-colorable.
    feats = [("x", 0, 0), ("y", 0, 1), ("z", 1, 0)]
    names, adj = build_conflict_graph(feats, distance=1.5)
    colorable, _, frustrated = two_color_conflicts(names, adj)
    assert not colorable
    assert len(frustrated) >= 1                            # localized native conflict
    flagged = {n for e in frustrated for n in e}
    assert flagged <= {"x", "y", "z"}
    assert spectral_frustration(names, adj) > 1e-6        # spectral agrees: frustrated


def test_conflict_rule_matches_openmpl_strict_distance():
    # OpenMPL's rule (SimpleMPL update_conflict_relation): euclidean_distance < coloring_distance.
    # A gap EXACTLY equal to the min spacing is legal (no conflict); strictly closer is.
    from domains.silicon.dp_conflict import build_conflict_graph_bbox
    at_spacing = [("a", 0, 0, (0, 0, 10, 10)), ("b", 0, 0, (20, 0, 30, 10))]   # gap == 10
    _, adj = build_conflict_graph_bbox(at_spacing, distance=10.0)
    assert adj["a"] == set()                              # gap == distance -> NOT a conflict
    _, adj = build_conflict_graph_bbox(at_spacing, distance=10.5)
    assert adj["a"] == {"b"}                              # strictly closer than distance -> conflict


def test_even_cycle_is_colorable():
    # 4-cycle (square) is bipartite -> decomposable, no native conflict.
    feats = [("a", 0, 0), ("b", 2, 0), ("c", 2, 2), ("d", 0, 2)]
    names, adj = build_conflict_graph(feats, distance=2.5)
    colorable, _, frustrated = two_color_conflicts(names, adj)
    assert colorable and frustrated == []


def _rec(rt, dt, payload=b""):
    return struct.pack(">HBB", len(payload) + 4, rt, dt) + payload


def test_gds_parser_reads_boundary(tmp_path):
    # Minimal GDS: one structure 'TOP' with one BOUNDARY rectangle on layer 13.
    xy = struct.pack(">10i", 0, 0, 100, 0, 100, 200, 0, 200, 0, 0)
    body = (_rec(0x05, 0x02, b"\x00" * 24) + _rec(0x06, 0x06, b"TOP\x00")
            + _rec(0x08, 0x00) + _rec(0x0D, 0x02, struct.pack(">h", 13))
            + _rec(0x0E, 0x02, struct.pack(">h", 0)) + _rec(0x10, 0x03, xy)
            + _rec(0x11, 0x00) + _rec(0x07, 0x00))
    p = tmp_path / "t.gds"
    p.write_bytes(body)
    shapes = parse_gds_shapes(str(p))
    assert 13 in shapes
    assert shapes[13][0] == (0, 0, 100, 200)         # bbox of the rectangle


_DEF = "domains/silicon/data/orfs_gcd/results/base/6_final.def"
_GDS = "domains/silicon/data/orfs_gcd/results/base/6_final.gds"


@pytest.mark.skipif(not os.path.exists(_DEF),
                    reason="orfs_gcd DEF absent (self-mint via ORFS)")
def test_real_layer_transition_and_method_agreement():
    sparse = analyze(_DEF, 1500.0, design="orfs_gcd")
    dense = analyze(_DEF, 2500.0, design="orfs_gcd")
    # sparse coloring distance -> decomposable; denser -> native conflicts appear
    assert sparse.colorable and sparse.n_native_conflicts == 0
    assert not dense.colorable and dense.n_native_conflicts > 0
    assert dense.native_examples                          # localized
    # the two methods agree on both: colorable iff frustration ~ 0
    for rep in (sparse, dense):
        assert rep.colorable == (rep.frustration < 1e-6)


@pytest.mark.skipif(not os.path.exists(_GDS), reason="orfs_gcd GDS absent")
def test_real_gds_metal_shapes_localize_native_conflicts():
    # REAL routing shapes on the densest metal layer (13) at min-width spacing.
    rep = analyze_gds(_GDS, 13, 700.0, design="orfs_gcd")
    assert rep.n_features > 1000                      # real metal shapes, not placements
    assert rep.n_conflict_edges > 0
    # dense real routing is not 2-colorable at min spacing; conflicts are localized
    assert not rep.colorable and rep.n_native_conflicts > 0
    assert rep.native_examples
    assert rep.colorable == (rep.frustration < 1e-6)  # BFS and spectral agree


# --- GDS hierarchy flattening (SREF/AREF resolution) ----------------------------------------

def _gds_real_bytes(v: float) -> bytes:
    """Encode a Python float as a GDS 8-byte real (inverse of gds._gds_real)."""
    if v == 0.0:
        return b"\x00" * 8
    sign = 0x80 if v < 0 else 0
    v = abs(v)
    exp = 64
    while v >= 1.0:
        v /= 16.0
        exp += 1
    while v < 1.0 / 16.0:
        v *= 16.0
        exp -= 1
    mant = int(v * (1 << 56))
    return bytes([sign | exp]) + mant.to_bytes(7, "big")


def _boundary(layer, x0, y0, x1, y1):
    xy = struct.pack(">10i", x0, y0, x1, y0, x1, y1, x0, y1, x0, y0)
    return (_rec(0x08, 0x00) + _rec(0x0D, 0x02, struct.pack(">h", layer))
            + _rec(0x0E, 0x02, struct.pack(">h", 0)) + _rec(0x10, 0x03, xy) + _rec(0x11, 0x00))


def _sref(sname, x, y, reflect=False, angle=None):
    rec = _rec(0x0A, 0x00) + _rec(0x12, 0x06, sname.encode() + b"\x00")
    if reflect or angle is not None:
        rec += _rec(0x1A, 0x01, struct.pack(">H", 0x8000 if reflect else 0))
    if angle is not None:
        rec += _rec(0x1C, 0x05, _gds_real_bytes(angle))
    rec += _rec(0x10, 0x03, struct.pack(">2i", x, y)) + _rec(0x11, 0x00)
    return rec


def _struct(name, *elems):
    return _rec(0x05, 0x02, b"\x00" * 24) + _rec(0x06, 0x06, name.encode() + b"\x00") \
        + b"".join(elems) + _rec(0x07, 0x00)


def _write_gds(tmp_path, *structs):
    p = tmp_path / "h.gds"
    p.write_bytes(b"".join(structs))
    return str(p)


def test_gds_real_roundtrip():
    for v in (1.0, 90.0, 0.5, -2.0, 1.0 / 16.0):
        assert _gds_real(_gds_real_bytes(v)) == pytest.approx(v, rel=1e-12)
    assert _gds_real(_gds_real_bytes(0.0)) == 0.0


def test_xform_bbox_rotation_and_reflection():
    bb = (0, 0, 10, 20)
    assert _xform_bbox(bb, False, 1.0, 0.0, 100, 200) == (100, 200, 110, 220)   # translate
    assert _xform_bbox(bb, True, 1.0, 0.0, 0, 0) == (0, -20, 10, 0)             # reflect about x
    assert _xform_bbox(bb, False, 1.0, 90.0, 0, 0) == (-20, 0, 0, 10)           # rotate 90 CCW


def test_flatten_resolves_sref_placement(tmp_path):
    # CELL has internal metal; TOP places it via SREF and has its own top-cell shape.
    path = _write_gds(
        tmp_path,
        _struct("CELL", _boundary(13, 0, 0, 10, 20)),
        _struct("TOP", _boundary(13, 0, 0, 5, 5), _sref("CELL", 100, 200)),
    )
    top_only = parse_gds_shapes(path)               # top-cell routing only
    assert len(top_only[13]) == 1 and top_only[13][0] == (0, 0, 5, 5)
    flat = flatten_gds_shapes(path)                 # + the placed cell-internal metal
    assert len(flat[13]) == 2
    assert (100, 200, 110, 220) in flat[13]         # CELL's rect translated into TOP frame
    assert (0, 0, 5, 5) in flat[13]


def test_flatten_applies_sref_transform(tmp_path):
    path = _write_gds(
        tmp_path,
        _struct("CELL", _boundary(13, 0, 0, 10, 20)),
        _struct("TOP", _sref("CELL", 50, 60, reflect=True)),    # y negated then translated
    )
    flat = flatten_gds_shapes(path)
    assert flat[13] == [(50, 40, 60, 60)]           # (0,-20,10,0) + (50,60)


def test_flatten_recurses_nested_sref(tmp_path):
    # TOP -> MID -> LEAF: a two-level hierarchy must fully flatten.
    path = _write_gds(
        tmp_path,
        _struct("LEAF", _boundary(13, 0, 0, 4, 4)),
        _struct("MID", _sref("LEAF", 10, 0)),
        _struct("TOP", _sref("MID", 100, 0)),
    )
    flat = flatten_gds_shapes(path)
    assert flat[13] == [(110, 0, 114, 4)]           # 0 +10 +100 in x


def test_sparse_spectral_scales_to_large_dense_components():
    # The sparse power-iteration path (large components) must agree with BFS by magnitude:
    # bipartite -> ~0 (below the convergence floor), heavily frustrated -> clearly positive.
    rng = np.random.default_rng(1)
    n = 3000
    left = [f"l{i}" for i in range(n)]
    right = [f"r{i}" for i in range(n)]

    def build(extra_intra):
        adj = {x: set() for x in left + right}
        for _ in range(n * 8):
            a, b = left[rng.integers(n)], right[rng.integers(n)]
            adj[a].add(b); adj[b].add(a)
        for _ in range(extra_intra):
            a, b = left[rng.integers(n)], left[rng.integers(n)]
            if a != b:
                adj[a].add(b); adj[b].add(a)
        return left + right, adj

    names, adj = build(0)                            # one giant bipartite component
    colorable, _, _ = two_color_conflicts(names, adj)
    assert colorable and spectral_frustration(names, adj) < 1e-2

    names, adj = build(500)                          # heavily frustrated
    colorable, _, frustrated = two_color_conflicts(names, adj)
    assert not colorable and frustrated
    assert spectral_frustration(names, adj) > 0.1    # spectral confirms by magnitude


@pytest.mark.skipif(not os.path.exists(_GDS), reason="orfs_gcd GDS absent")
def test_real_gds_flatten_includes_cell_internal_metal():
    # Flattening the SREF hierarchy lands cell-internal metal inside the die, far denser
    # than top-cell routing. M1 (layer 11) is nearly empty at top-cell, dense once flattened.
    top = parse_gds_shapes(_GDS)
    flat = flatten_gds_shapes(_GDS)
    assert len(flat.get(11, [])) > 20 * max(1, len(top.get(11, [])))   # 25 -> thousands
    assert len(flat.get(13, [])) > len(top.get(13, []))                # routing + internal
    boxes = [bb for v in flat.values() for bb in v]
    assert all(bb[0] <= bb[2] and bb[1] <= bb[3] for bb in boxes)      # well-formed
    # cell metal lands inside the die area (0..367250 db units for this design), not scattered
    assert min(bb[0] for bb in boxes) >= 0 and max(bb[2] for bb in boxes) <= 400000


@pytest.mark.skipif(not os.path.exists(_GDS), reason="orfs_gcd GDS absent")
def test_real_gds_flatten_localizes_native_conflicts_on_m1():
    # The real, dense M1 with cell-internal metal is not 2-colorable; the exact BFS Z/2
    # localizes thousands of native conflicts and the spectral check confirms by magnitude.
    flat = analyze_gds(_GDS, 11, 700.0, design="orfs_gcd", flatten=True)
    top = analyze_gds(_GDS, 11, 700.0, design="orfs_gcd")             # top-cell M1 ~ empty
    assert flat.n_features > 5000 and flat.n_features > 50 * max(1, top.n_features)
    assert not flat.colorable and flat.n_native_conflicts > 1000
    assert flat.native_examples                                       # localized
    assert flat.frustration > 0.1                                     # spectral confirms
