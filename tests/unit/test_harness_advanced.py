"""Tests for incremental-over-baseline + redundancy harness interfaces (SP-0)."""

import numpy as np

from phi3geom.analysis.harness.incremental import incremental_auroc
from phi3geom.analysis.harness.redundancy import redundancy


def test_incremental_detects_added_signal():
    rng = np.random.default_rng(0)
    n = 240
    base = rng.standard_normal((n, 2))  # uninformative baseline
    geom_signal = rng.standard_normal((n, 1))
    y = (geom_signal[:, 0] + 0.25 * rng.standard_normal(n) > 0).astype(int)
    res = incremental_auroc(geom_signal, base, y, n_repeats=3, n_folds=4, n_boot=300, seed=1)
    assert res["auroc_combined"] > res["auroc_baseline"]
    assert res["delta"] > 0
    assert res["delta_ci"][0] > 0  # beats-baselines bar: CI lower bound > 0


def test_incremental_no_gain_from_noise():
    rng = np.random.default_rng(1)
    n = 240
    base_signal = rng.standard_normal((n, 1))
    y = (base_signal[:, 0] + 0.25 * rng.standard_normal(n) > 0).astype(int)
    geom_noise = rng.standard_normal((n, 2))  # adds nothing
    res = incremental_auroc(geom_noise, base_signal, y, n_repeats=3, n_folds=4, n_boot=300, seed=2)
    # noise adds no real gain: the beats-baselines bar (CI lower bound > 0) is NOT
    # met, and the delta is negligible (slightly negative from overfit is fine).
    assert res["delta_ci"][0] <= 0
    assert abs(res["delta"]) < 0.05


def test_redundancy_flags_duplicate_feature():
    rng = np.random.default_rng(3)
    n = 400
    f0 = rng.standard_normal(n)           # unique signal
    f1 = rng.standard_normal(n)           # noise
    f2 = f0 + 0.05 * rng.standard_normal(n)  # near-duplicate of f0 (redundant)
    X = np.column_stack([f0, f1, f2])
    y = (f0 + 0.2 * rng.standard_normal(n) > 0).astype(float)
    res = redundancy(X, y, feature_names=["f0", "f1", "f2"])
    marg = res["marginal_correlations"]
    part = res["partial_correlations"]
    # f0 and its duplicate f2 are both marginally predictive...
    assert abs(marg[0]) > 0.3
    assert abs(marg[2]) > 0.3
    # ...but partial correlation collapses for the redundant pair (shared signal)
    assert abs(part[0]) < abs(marg[0])
    assert abs(part[2]) < abs(marg[2])
    # the noise feature stays ~0 in both
    assert abs(marg[1]) < 0.2
    assert abs(part[1]) < 0.2
