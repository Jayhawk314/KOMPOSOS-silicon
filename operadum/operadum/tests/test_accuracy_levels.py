# SPDX-License-Identifier: LicenseRef-Proprietary-Commercial
# SPDX-FileCopyrightText: 2026 James Hawkins <jhawk314@gmail.com>

"""
Accuracy-level harnesses: the tests where OPERADUM can be measurably WRONG.

These probe genuine accuracy (a number in [0,1] that varies), unlike the
correctness-by-construction harnesses that always score 1.0:
  * generalization   -- program-by-example held out on unseen inputs
  * concept learning -- PAC Boolean generalization from a partial truth table
"""

import pytest

from operadum.validation.generalization import measure_generalization
from operadum.validation.concept_learning import measure_concept_learning


def test_generalization_curve_improves_with_examples():
    curve = measure_generalization(n_train_values=(1, 3), n_test=20, trials=8, seed=0)
    one, three = curve[0], curve[1]
    # A consistent program is always found...
    assert one.solve_rate == 1.0 and three.solve_rate == 1.0
    # ...but one example under-determines the spec, so held-out accuracy is
    # below perfect, and rises with more examples (the measurable accuracy level).
    assert one.holdout_accuracy < 1.0
    assert three.holdout_accuracy >= one.holdout_accuracy
    assert three.holdout_accuracy >= 0.9      # more examples -> near-perfect


def test_realizable_concept_learning_reaches_exact():
    curve = measure_concept_learning(realizable=True, m_values=(2, 8), trials=8,
                                     max_nodes=3, target_gates=2, limit=4000, seed=1)
    few, full = curve[0], curve[1]
    # Seeing the whole truth table yields exact generalization...
    assert full.holdout_accuracy == pytest.approx(1.0)
    # ...and accuracy is a real number in [0,1] that is no better with fewer rows.
    assert 0.0 <= few.holdout_accuracy <= 1.0
    assert full.holdout_accuracy >= few.holdout_accuracy


def test_agnostic_concept_learning_shows_no_free_lunch():
    """Structureless random concepts cannot be generalized from partial data:
    held-out accuracy stays near chance until the table is complete."""
    curve = measure_concept_learning(realizable=False, m_values=(2, 8), trials=8,
                                     max_nodes=3, limit=4000, seed=2)
    few = curve[0]
    # Near chance (0.5) on held-out rows with only a quarter of the table seen.
    assert few.holdout_accuracy < 0.75
