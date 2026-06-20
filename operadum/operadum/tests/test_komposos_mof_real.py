# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Real KOMPOSOS-MOF tandem tests."""

from pathlib import Path

import pytest

from operadum.bridges.round_trip import KomposVerifier
from operadum.core.types import Spec
from operadum.integrations.komposos_mof import (
    DEFAULT_KOMPOSOS_PATH,
    KompososMOFSpec,
    RealKompososMOFClient,
    build_operad_from_screened_linkers,
    design_mof_with_komposos,
    screened_linker_from_komposos_result,
)
from operadum.wright.engine import Wright
from operadum.wright.schema import Verdict


pytestmark = pytest.mark.skipif(
    not Path(DEFAULT_KOMPOSOS_PATH).is_dir(),
    reason="real KOMPOSOS-IV-CHEM checkout is not present",
)


def test_real_komposos_mof_cache_loads():
    client = RealKompososMOFClient()
    linkers = client.load_known_linkers()

    assert len(linkers) >= 100
    exact_22 = [linker for linker in linkers if linker.heavy_atom_count == 22]
    assert len(exact_22) >= 20
    assert all(linker.smiles for linker in exact_22[:20])


def test_real_scored_linker_becomes_operadum_mof_design():
    client = RealKompososMOFClient()
    known = client.load_known_linkers()

    from mof_bridge.komposos_verdicts import LinkerVerdictEngine

    scored = LinkerVerdictEngine().score_verdicts(known[0].smiles, "custom")
    candidate = screened_linker_from_komposos_result(scored, rank=1)

    op = build_operad_from_screened_linkers([candidate])
    result = Wright(op, max_depth=4).optimize(Spec((), "MOF"))

    assert result.verdict == Verdict.BUILDABLE
    linker = result.construction.artifact()["linker"]
    assert linker["smiles"] == candidate.smiles
    assert linker["verdicts"] == candidate.verdicts
    assert linker["morphism_integrity"] == candidate.morphism_integrity

    audit = KomposVerifier(komposos_path=DEFAULT_KOMPOSOS_PATH).verify(
        result.construction.composite, op
    )
    assert audit.verdict == "AGREE"


def test_real_komposos_generation_feeds_operadum_tandem():
    spec = KompososMOFSpec(
        application_context="custom",
        exact_atoms=22,
        num_candidates=2,
        require_all_agree=False,
        allow_hollow=True,
        strategy_weights={"template": 1.0, "substitution": 0.0, "modification": 0.0},
        random_seed=1,
    )

    result = design_mof_with_komposos(
        spec,
        min_morphism_integrity=0.0,
        komposos_path=DEFAULT_KOMPOSOS_PATH,
    )

    assert result.screen.num_generated == 2
    assert result.screen.num_scored == 2
    assert result.screen.candidates
    assert result.buildable
    assert result.selected_linker is not None
    assert result.round_trip is not None
    assert result.round_trip.verdict == "AGREE"
