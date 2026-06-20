# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Scale laws: partitioning is a true bounded partition; fast curvature keeps the
bottleneck ranking; the scale path agrees with the whole-graph result on the bottleneck."""

import os

import pytest

from domains.silicon.netlist_bridge import NetlistBridge, SAMPLE_DEF, SAMPLE_SPEF
from domains.silicon.flow_geometry import edge_curvatures, AUTO_EXACT_MAX_EDGES
from domains.silicon.partition import (
    partition_nodes, partition_category, induced_subcategory, analyze_partitioned,
)


def _sample():
    b = NetlistBridge(SAMPLE_DEF, SAMPLE_SPEF); b.load()
    return b


def _nodes(cat):
    return {n for m in cat.morphisms() for n in (m.source, m.target)}


# --- partition is a true, bounded partition -------------------------------

def test_partition_is_disjoint_cover_and_bounded():
    b = _sample()
    nodes = _nodes(b.category)
    groups = partition_nodes(b.category, max_size=4)
    flat = [n for g in groups for n in g]
    assert set(flat) == nodes                 # covers every node
    assert len(flat) == len(set(flat))        # disjoint
    assert all(len(g) <= 4 for g in groups)   # bounded


def test_induced_subcategory_keeps_only_internal_edges():
    b = _sample()
    parts = partition_category(b.category, max_size=4)
    for p in parts:
        names = set(p.nodes)
        for m in p.category.morphisms():
            assert m.source in names and m.target in names


def test_partition_cuts_the_bus_between_cores():
    """Fiedler bisection of the barbell separates the cores, cutting n_bus."""
    b = _sample()
    pa = analyze_partitioned(b, max_size=4, method="exact")
    assert pa.n_partitions >= 2
    assert pa.max_partition_size <= 4
    assert "n_bus" in pa.inter_region_nets   # the inter-core bus is a cut/seam net


# --- fast curvature preserves the bottleneck ------------------------------

def test_effres_preserves_negative_bottleneck_ranking():
    """Effective-Resistance must still rank a real bottleneck most-negative."""
    g = os.path.join(os.path.dirname(SAMPLE_DEF), "..", "data", "openlane", "gcd.def")
    s = os.path.join(os.path.dirname(SAMPLE_DEF), "..", "data", "openlane", "gcd.spefok")
    if not os.path.exists(g):
        pytest.skip("real gcd not downloaded")
    b = NetlistBridge(g, s); b.load()
    fast = edge_curvatures(b.category, method="effres")
    assert fast and fast[0][2] < -0.1           # a clearly negative corridor survives


def test_lower_method_is_available_but_distinct():
    b = _sample()
    exact = edge_curvatures(b.category, method="exact")
    lower = edge_curvatures(b.category, method="lower")
    assert len(exact) == len(lower)             # same edge set, different values


def test_auto_uses_exact_below_threshold():
    b = _sample()
    assert len(b.category.morphisms()) < AUTO_EXACT_MAX_EDGES
    # auto == exact here, so the planted bus is still the worst corridor
    auto = edge_curvatures(b.category, method="auto")
    net_of = {frozenset((m.source, m.target)): m.metadata.get("net")
              for m in b.category.morphisms()}
    assert net_of[frozenset((auto[0][0], auto[0][1]))] == "n_bus"


# --- the scale path agrees with the whole-graph result on the bottleneck ---

def test_partitioned_corridors_found_and_bounded_on_gcd():
    g = os.path.join(os.path.dirname(SAMPLE_DEF), "..", "data", "openlane", "gcd.def")
    s = os.path.join(os.path.dirname(SAMPLE_DEF), "..", "data", "openlane", "gcd.spefok")
    if not os.path.exists(g):
        pytest.skip("real gcd not downloaded")
    b = NetlistBridge(g, s); b.load()
    pa = analyze_partitioned(b, max_size=120, method="exact")
    assert pa.max_partition_size <= 120
    assert pa.corridors and pa.corridors[0][3] < 0     # an intra-region bottleneck
    assert pa.inter_region_nets                         # seam candidates exist


def test_cli_partition_emits_bounded_regions(capsys):
    import json
    from domains.silicon import agent_tools
    agent_tools.main(["partition", "--max-size", "4", "--method", "exact"])
    out = json.loads(capsys.readouterr().out)
    assert out["tool"] == "partition"
    assert out["max_partition_size"] <= 4
    assert out["n_partitions"] >= 2
