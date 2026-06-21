# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Track 3 Step B (first cut): double-patterning native-conflict localization.

Double patterning is feasible iff the conflict graph is 2-colorable iff no odd cycles (a Z/2
H1 obstruction). We check the combinatorial (BFS) and spectral (signless-Laplacian) views
agree, and that a real layer shows the colorable->native-conflict transition.
"""

import os

import pytest

from domains.silicon.dp_conflict import (
    analyze, build_conflict_graph, spectral_frustration, two_color_conflicts,
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


def test_even_cycle_is_colorable():
    # 4-cycle (square) is bipartite -> decomposable, no native conflict.
    feats = [("a", 0, 0), ("b", 2, 0), ("c", 2, 2), ("d", 0, 2)]
    names, adj = build_conflict_graph(feats, distance=2.5)
    colorable, _, frustrated = two_color_conflicts(names, adj)
    assert colorable and frustrated == []


_DEF = "domains/silicon/data/orfs_gcd/results/base/6_final.def"


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
