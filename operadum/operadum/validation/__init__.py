# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""OPERADUM validation: synthesis-accuracy benchmarks."""

from .benchmark import run_benchmark, BenchmarkResult, random_operad, brute_force_min_cost

__all__ = ["run_benchmark", "BenchmarkResult", "random_operad", "brute_force_min_cost"]
