# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Materials design accuracy on real MOF linker data: a learned predictor,
held-out ground truth, and the cost-vs-prediction tension.
"""

import pytest

from operadum.validation.materials_accuracy import (
    measure_materials_accuracy, MaterialPropertyModel, is_donor_rich, _records,
)


def test_predictor_learns_real_structure_property_signal():
    """A logistic model over cheap descriptors predicts donor-richness on held-out
    linkers well above the majority-class baseline -- real signal, not memorisation."""
    score = measure_materials_accuracy(n_splits=10, seed=0)
    assert score.predictor_accuracy > score.majority_baseline + 0.1
    assert score.predictor_accuracy > 0.7


def test_oracle_design_is_perfect_and_design_is_bounded():
    score = measure_materials_accuracy(n_splits=10, seed=0)
    # Designing with TRUE labels always yields a donor-rich framework.
    assert score.oracle_hit_rate == pytest.approx(1.0)
    assert 0.0 <= score.design_hit_rate <= 1.0


def test_model_fits_and_predicts():
    data = _records()
    model = MaterialPropertyModel().fit(data, is_donor_rich)
    # In-sample accuracy is high (the signal exists in the real features).
    acc = sum(1 for r in data if model.predict(r) == is_donor_rich(r)) / len(data)
    assert acc > 0.75
