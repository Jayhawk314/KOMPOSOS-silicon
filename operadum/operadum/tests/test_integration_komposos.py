# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Integration test: OPERADUM search over KOMPOSOS-CHEM's REAL predictor.

Heavy + environment-dependent (loads KOMPOSOS-IV-CHEM + numpy, ~10s), so it is
skipped unless OPERADUM_RUN_INTEGRATION is set. Run it explicitly with:

    OPERADUM_RUN_INTEGRATION=1 python -m pytest operadum/tests/test_integration_komposos.py
"""

import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("OPERADUM_RUN_INTEGRATION"),
    reason="set OPERADUM_RUN_INTEGRATION=1 (needs KOMPOSOS-IV-CHEM + numpy)",
)


def _predictor():
    from operadum.integrations.komposos_chem import load_predictor
    try:
        return load_predictor()
    except Exception as exc:  # pragma: no cover - env dependent
        pytest.skip(f"KOMPOSOS-CHEM not importable: {exc}")


def test_real_predictor_scores_a_cathode():
    from operadum.integrations.komposos_chem import design_cathode
    r = design_cathode(_predictor())
    assert r.best_unconstrained is not None
    assert r.best_unconstrained.capacity > 100        # real mAh/g
    assert r.round_trip == "AGREE"


def test_conductivity_constraint_binds_and_changes_optimum():
    from operadum.integrations.komposos_chem import design_cathode
    r = design_cathode(_predictor(), max_band_gap=1.0)
    assert r.constraint_binds                          # LiMnO2 (gap 1.09) excluded
    assert r.best_constrained.band_gap <= 1.0
    assert r.round_trip == "AGREE"
    # The predictor is called once per distinct composition (dedup).
    assert r.predictor_calls == r.candidates
