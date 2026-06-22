# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Track 3 Step C: trust-gate the coherence verdict (proposal -> verification).

A localized obstruction (3A net divergence, 3B native double-patterning conflict) is TRUSTED
only if INDEPENDENT, specificity-weighted views corroborate it -- a non-specific/global view
cannot over-vouch -- and the rationale grounds. The tier stays `structural_only` (never
promoted to foundry-measured EPE).
"""

import math
import os

import pytest

from domains.silicon.coherence_trust import (
    Obstruction, Witness, corroboration, gate_obstruction, summarize,
    trust_dp_conflicts, trust_fidelity_divergences,
)


# ── core gate: specificity-weighted corroboration ───────────────────────────────────────────

def test_specificity_is_idf():
    assert Witness("w", 1.0, 100, 100).specificity == pytest.approx(0.0)        # flags all -> 0
    assert Witness("w", 1.0, 1, 100).specificity == pytest.approx(1.0)          # flags one -> 1
    assert Witness("w", 1.0, 10, 100).specificity == pytest.approx(0.5, abs=0.01)
    assert Witness("w", 1.0, 5, 1).specificity == 1.0                          # degenerate N<=1


def test_corroboration_is_specificity_weighted_noisy_or():
    w = Witness("a", 1.0, 5, 100)          # spec ~ 0.651
    obs = Obstruction("x", [w, Witness("b", 1.0, 5, 100)])
    expect = 1.0 - (1.0 - w.weight) ** 2
    assert corroboration(obs) == pytest.approx(expect)


def test_two_independent_specific_views_are_trusted():
    v = gate_obstruction(Obstruction("x", [Witness("a", 1.0, 5, 100),
                                           Witness("b", 1.0, 5, 100)]))
    assert v.trusted and v.grounded and v.n_specific == 2
    assert v.corroboration > 0.5


def test_single_view_is_uncorroborated():
    v = gate_obstruction(Obstruction("x", [Witness("a", 1.0, 5, 100)]))
    assert v.status == "UNCORROBORATED" and not v.trusted


def test_global_views_cannot_over_vouch():
    # two witnesses that each flag 95/100 items (a global naming mismatch) must NOT pass --
    # IDF drives their weight ~ 0 so even two of them cannot vouch.
    gw = [Witness("a", 1.0, 95, 100), Witness("b", 1.0, 95, 100)]
    assert gw[0].weight < 0.05
    v = gate_obstruction(Obstruction("x", gw))
    assert v.status == "UNCORROBORATED" and v.corroboration < 0.1


def test_tier_is_never_promoted():
    for ws in ([Witness("a", 1.0, 5, 100), Witness("b", 1.0, 5, 100)],
               [Witness("a", 1.0, 95, 100)]):
        assert gate_obstruction(Obstruction("x", ws)).tier == "structural_only"


# ── 3B adapter: native double-patterning conflict regions ───────────────────────────────────

def _triangle(prefix):
    a, b, c = f"{prefix}1", f"{prefix}2", f"{prefix}3"
    return {a: {b, c}, b: {a, c}, c: {a, b}}      # K3 -> odd cycle -> frustrated


def _square(prefix):
    a, b, c, d = f"{prefix}1", f"{prefix}2", f"{prefix}3", f"{prefix}4"
    return {a: {b, d}, b: {a, c}, c: {b, d}, d: {a, c}}    # C4 -> bipartite


def test_3b_trusts_frustrated_components_not_bipartite():
    # two frustrated triangles + one bipartite square, as separate components.
    adj = {}
    adj.update(_triangle("a")); adj.update(_triangle("b")); adj.update(_square("c"))
    names = list(adj)
    verdicts = trust_dp_conflicts(names, adj)
    # exactly the two frustrated components are gated, both trusted by bfs + spectral
    assert len(verdicts) == 2
    assert all(v.trusted and v.n_specific >= 2 for v in verdicts)
    # the bipartite square is never proposed as an obstruction
    assert all("c" not in v.item.lower() or "component" in v.item for v in verdicts)
    # each trusted region localizes its native conflict edges (support)
    assert all(v.support for v in verdicts)
    assert all(v.tier == "structural_only" for v in verdicts)


def test_3b_support_localizes_real_edges():
    adj = _triangle("a")
    [v] = trust_dp_conflicts(list(adj), adj)
    assert v.trusted and len(v.support) >= 1
    flagged = {n for e in v.support for n in e.split("--")}
    assert flagged <= {"a1", "a2", "a3"}            # localized to the triangle's features


@pytest.mark.skipif(
    not os.path.exists("domains/silicon/data/orfs_gcd/results/base/6_final.gds"),
    reason="orfs_gcd GDS absent")
def test_3b_real_m1_region_is_trusted_and_localized():
    from domains.silicon.dp_conflict import build_conflict_graph_bbox
    from domains.silicon.gds import gds_features
    g = "domains/silicon/data/orfs_gcd/results/base/6_final.gds"
    names, adj = build_conflict_graph_bbox(gds_features(g, 11, flatten=True), 700.0)
    verdicts = trust_dp_conflicts(names, adj)
    trusted = [v for v in verdicts if v.trusted]
    assert trusted                                                   # at least one region
    assert sum(len(v.support) for v in trusted) > 1000               # localizes many conflicts
    assert all(v.tier == "structural_only" for v in verdicts)        # never foundry-EPE


# ── 3A adapter: three-view net divergences ──────────────────────────────────────────────────

def test_3a_multi_pair_trusted_single_pair_not():
    disagreements = {
        "verilog~def": ["netX", "netY"],
        "verilog~spef": ["netX"],
        "def~spef": ["netW"],
    }
    verdicts = {v.item: v for v in trust_fidelity_divergences(disagreements, n_total_nets=100)}
    assert verdicts["netX"].trusted                  # flagged by 2 independent pairs
    assert verdicts["netY"].status == "UNCORROBORATED"   # one pair only
    assert verdicts["netW"].status == "UNCORROBORATED"


def test_3a_global_pair_is_downweighted():
    # two pairs that each flag 90/100 nets (a global rename) must not make a net trusted.
    nets = [f"n{i}" for i in range(90)]
    disagreements = {"verilog~def": nets, "verilog~spef": nets}
    verdicts = trust_fidelity_divergences(disagreements, n_total_nets=100)
    assert all(v.status == "UNCORROBORATED" for v in verdicts)
    assert summarize(verdicts)["TRUSTED"] == 0


@pytest.mark.skipif(
    not os.path.exists("domains/silicon/data/orfs_gcd/results/base/6_final.v"),
    reason="orfs_gcd verilog/def/spef absent")
def test_3a_real_divergences_gate_to_structural_trusted():
    from domains.silicon.fidelity_coherence import (
        def_view, fidelity_coherence, spef_view, verilog_view)
    base = "domains/silicon/data/orfs_gcd/results/base"
    lef = "domains/silicon/data/openlane/Nangate45.lef"
    v = verilog_view(f"{base}/6_final.v")
    d, _ = def_view(f"{base}/6_final.def", f"{base}/6_final.spef",
                    lef if os.path.exists(lef) else None)
    s = spef_view(f"{base}/6_final.spef")
    rep = fidelity_coherence(v, d, s)
    # With faithful adapters this is a CLEAN flow: all three views agree on shared connectivity
    # (every pairwise agreement 1.0), so the only residual divergences are view-size deltas
    # (a net present in one view but not another) -- and each such net shows up in exactly two
    # of the three view-pairs, so the gate corroborates them all. The discrimination property
    # (corroborated vs single-view, global-view down-weighting) is proven on synthetic inputs by
    # `test_3a_multi_pair_trusted_single_pair_not` / `test_3a_global_pair_is_downweighted`.
    verdicts = trust_fidelity_divergences(rep.disagreements, rep.n_common_nets)
    counts = summarize(verdicts)
    assert verdicts and counts["TRUSTED"] > 0            # the gate runs on real divergences
    assert all(v.tier == "structural_only" for v in verdicts)   # never promoted to foundry EPE
    assert counts["UNCORROBORATED"] == 0                 # clean flow -> no single-view-only nets
