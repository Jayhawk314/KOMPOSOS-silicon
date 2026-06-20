# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""Measured-EM scoreboard: structure should predict real measured EM current."""

import os
import pytest

from domains.silicon.em_scoreboard import parse_em_current, em_scoreboard, EMScoreReport


def test_parse_em_current_skips_header_and_bad_rows():
    import tempfile
    txt = ("Node0 Layer,Node0 X,Node0 Y,Node1 Layer,Node1 X,Node1 Y,Current\n"
           "metal1,1.0,2.0,metal1,1.1,2.0,1.5e-03\n"
           "garbage,line\n")
    with tempfile.NamedTemporaryFile("w", suffix=".rpt", delete=False) as fh:
        fh.write(txt); path = fh.name
    segs = parse_em_current(path)
    os.unlink(path)
    assert segs == [(1.0, 2.0, 0.0015)]


_AES = "domains/silicon/data/orfs_aes/results/nangate45/aes/base"
_EM = "domains/silicon/data/ir_aes/em_current.rpt"


@pytest.mark.skipif(not (os.path.exists(f"{_AES}/6_final.def") and os.path.exists(_EM)),
                    reason="real OpenROAD EM artifacts absent (gitignored)")
def test_structure_predicts_real_em_current_aes():
    rep = em_scoreboard(f"{_AES}/6_final.def", f"{_AES}/6_final.spef",
                        "domains/silicon/data/openlane/Nangate45.lef", _EM, design="aes")
    assert isinstance(rep, EMScoreReport)
    # The EM hotspot detection must be measured-validated, with a clean control.
    assert rep.passed, rep.render()
    name, rho = rep.best
    assert rho >= 0.30 and abs(rep.control[name]) < 0.20
