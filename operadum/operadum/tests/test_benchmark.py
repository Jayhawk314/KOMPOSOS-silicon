# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Phase 3 tests: synthesis-accuracy benchmark.

This is the measurable answer to "can we test the accuracy yet?" -- yes, for
the engine: over random operads with a brute-forced known optimum, optimize()
must recover the true minimum cost (or correctly report impossibility).
"""

import pytest

from operadum.validation.benchmark import run_benchmark


def test_optimum_recall_is_perfect_on_random_operads():
    result = run_benchmark(n_trials=40, seed=1, max_depth=5)
    # DAEDALUS is exhaustive within the depth bound, so it must match the
    # brute-force optimum on every trial.
    assert result.optimum_recall == 1.0, result.failures[:5]
    assert result.buildable_recall == 1.0, result.failures[:5]


def test_benchmark_is_deterministic():
    a = run_benchmark(n_trials=20, seed=7)
    b = run_benchmark(n_trials=20, seed=7)
    assert a.optimum_recall == b.optimum_recall
    assert a.trials == b.trials == 20
