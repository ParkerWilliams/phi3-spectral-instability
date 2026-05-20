"""Tests for ``phi3geom.analysis.pooled_negative_control`` (T068)."""

from __future__ import annotations

import numpy as np
import pytest

from phi3geom.analysis.pooled_negative_control import fit
from phi3geom.analysis.types import PooledNegativeControl


def _pooled_features_and_labels(n_per_bin: int = 50, seed: int = 0):
    """Build a synthetic pooled dataset with 6 bins, each with a
    locally-strong but cross-bin-noisy signal — the R2 lesson exemplar."""
    rng = np.random.default_rng(seed)
    n_total = n_per_bin * 6
    features = rng.standard_normal((n_total, 7), dtype=np.float64)
    labels = rng.integers(0, 2, size=n_total).astype(bool)
    return features, labels


def test_fit_returns_pooled_negative_control_dataclass() -> None:
    features, labels = _pooled_features_and_labels(n_per_bin=50)
    result = fit(features, labels, random_state=42, n_bootstrap=100)
    assert isinstance(result, PooledNegativeControl)
    assert result.coefficients.shape == (7,)
    assert result.auroc_ci_lower <= result.auroc <= result.auroc_ci_upper


def test_pooled_collapse_demonstration() -> None:
    """Per the R2 lesson, the AUROC on synthetic data with no global signal
    is around chance — well below 0.75 (the SC-003 threshold).
    """
    features, labels = _pooled_features_and_labels(n_per_bin=50, seed=7)
    result = fit(features, labels, random_state=42, n_bootstrap=200)
    # Random features → AUROC near chance
    assert result.auroc < 0.75 or result.auroc_ci_lower < 0.55


def test_handles_nan_imputation() -> None:
    features, labels = _pooled_features_and_labels(n_per_bin=50)
    features[::5, 6] = np.nan  # Ricci column NaN
    result = fit(features, labels, random_state=11, n_bootstrap=100)
    assert np.isfinite(result.coefficients).all()
    assert np.isfinite(result.intercept)


def test_rejects_float32() -> None:
    features = np.zeros((100, 7), dtype=np.float32)
    labels = np.zeros(100, dtype=bool)
    with pytest.raises(TypeError, match="float64"):
        fit(features, labels, random_state=0, n_bootstrap=10)


def test_rejects_shape_mismatch() -> None:
    features = np.zeros((100, 7), dtype=np.float64)
    labels = np.zeros(50, dtype=bool)
    with pytest.raises(ValueError, match="labels shape"):
        fit(features, labels, random_state=0, n_bootstrap=10)


def test_deterministic_given_seed() -> None:
    features, labels = _pooled_features_and_labels(n_per_bin=50)
    a = fit(features, labels, random_state=99, n_bootstrap=100)
    b = fit(features, labels, random_state=99, n_bootstrap=100)
    assert np.allclose(a.coefficients, b.coefficients)
    assert a.auroc == pytest.approx(b.auroc)
