# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Phase 5: the productized reliability co-design report ties the pipeline together."""

import os
import pytest

from domains.silicon.reliability import (
    assess_reliability, EVIDENCE_LADDER, ReliabilityReport,
)


def test_evidence_ladder_is_ordered_strongest_first():
    keys = list(EVIDENCE_LADDER)
    assert keys[0] == "measured"
    assert "measured_proxy" in keys and "validated_hypothesis" in keys
    assert "literature_value" in keys


_AES = "domains/silicon/data/orfs_aes/results/nangate45/aes/base"


@pytest.mark.skipif(not os.path.exists(f"{_AES}/6_final.def"),
                    reason="real ORFS layout absent (gitignored)")
def test_full_report_on_real_aes():
    rep = assess_reliability(f"{_AES}/6_final.def", f"{_AES}/6_final.spef",
                             "domains/silicon/data/openlane/Nangate45.lef",
                             design="aes", top=5)
    assert isinstance(rep, ReliabilityReport)
    # WHERE: validated hotspots present
    assert len(rep.hotspots.tiles) == 5
    # WHAT: a proven action per hotspot net, each with cited receipts
    assert len(rep.actions.fixes) == 5
    assert all(f.citations and f.reasons for f in rep.actions.fixes)
    # WHY: the report exposes its evidence ladder, and every tier it uses is defined
    d = rep.to_dict()
    assert set(d["evidence_ladder"]) == set(rep.tiers_used)
    assert all(t in EVIDENCE_LADDER for t in rep.tiers_used)
