# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Track 3 Step B (first cut): double-patterning native-conflict localization.

Double patterning is feasible iff the conflict graph is 2-colorable iff no odd cycles (a Z/2
H1 obstruction). We check the combinatorial (BFS) and spectral (signless-Laplacian) views
agree, and that a real layer shows the colorable->native-conflict transition.
"""

import os
import struct

import pytest

from domains.silicon.dp_conflict import (
    analyze, analyze_gds, build_conflict_graph, spectral_frustration, two_color_conflicts,
)
from domains.silicon.gds import parse_gds_shapes


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
