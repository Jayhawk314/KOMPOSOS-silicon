# SPDX-License-Identifier: Apache-2.0 OR LicenseRef-KOMPOSOS-V-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""The silicon product boundary: reliability should not import dormant engines."""

import json
import subprocess
import sys
from pathlib import Path


def test_reliability_product_imports_do_not_wake_dormant_math():
    """Import product entry points in a fresh process and inspect loaded packages.

    The repo still contains the substrate engines. This guardrail only protects the
    reliability product path from depending on them by accident.
    """
    repo = Path(__file__).resolve().parents[1]
    script = r"""
import json
import sys

import domains.silicon.reliability
import domains.silicon.hotspot
import domains.silicon.codesign_loop
import domains.silicon.trust_layer
import domains.silicon.ml_hotspot

blocked = {
    "bridges",
    "categorical",
    "cog",
    "cubical",
    "game",
    "geometry",
    "hott",
    "operadum",
    "oracle",
    "topology",
    "zfc",
}
loaded = sorted({name.split(".", 1)[0] for name in sys.modules} & blocked)
print(json.dumps(loaded))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout) == []
