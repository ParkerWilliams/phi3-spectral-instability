"""Contract test for the sklearn-backed per-regime composite logistic (T043)."""

from __future__ import annotations

import numpy as np
import pytest

from phi3geom.analysis.composite import (
    InsufficientDataError,
    fit_per_regime_composite,
)
from phi3geom.analysis.types import PerRegimeCompositeFit
from phi3geom.geometry import FEATURE_NAMES


def _synthetic_features(
    n: int, n_features: int = len(FEATURE_NAMES), seed: int = 0
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.standard_normal((n, n_features), dtype=np.float64)


def _synthetic_labels(n: int, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 2, size=n).astype(bool)


def test_fit_returns_per_regime_composite_fit() -> None:
    features = _synthetic_features(200)
    labels = _synthetic_labels(200)
    result = fit_per_regime_composite(
        features, labels, bin_id="B3", random_state=42
    )
    assert isinstance(result, PerRegimeCompositeFit)
    assert result.bin_id == "B3"
    assert result.coefficients.shape == (len(FEATURE_NAMES),)
    assert result.coefficients.dtype == np.float64


def test_fit_with_feature_names() -> None:
    features = _synthetic_features(150)
    labels = _synthetic_labels(150)
    result = fit_per_regime_composite(
        features, labels, bin_id="B2",
        feature_names=FEATURE_NAMES, random_state=42,
    )
    assert result.feature_names == FEATURE_NAMES


def test_fit_deterministic_given_seed() -> None:
    features = _synthetic_features(200, seed=7)
    labels = _synthetic_labels(200, seed=7)
    a = fit_per_regime_composite(features, labels, bin_id="B3", random_state=99)
    b = fit_per_regime_composite(features, labels, bin_id="B3", random_state=99)
    assert np.allclose(a.coefficients, b.coefficients)
    assert a.intercept == pytest.approx(b.intercept)
    # AUROC and CI bootstrap also deterministic given the same seed.
    assert a.auroc == pytest.approx(b.auroc)
    assert a.auroc_ci_lower == pytest.approx(b.auroc_ci_lower)
    assert a.auroc_ci_upper == pytest.approx(b.auroc_ci_upper)


def test_fit_handles_nan_in_ricci_column() -> None:
    features = _synthetic_features(200)
    # NaN in the Ricci column (index 6) — should be imputed internally.
    features[::3, 6] = np.nan
    labels = _synthetic_labels(200)
    result = fit_per_regime_composite(
        features, labels, bin_id="B3", random_state=11
    )
    assert np.isfinite(result.coefficients).all()
    assert np.isfinite(result.intercept)


def test_fit_rejects_float32() -> None:
    features = _synthetic_features(150).astype(np.float32)
    labels = _synthetic_labels(150)
    with pytest.raises(TypeError, match="float64"):
        fit_per_regime_composite(features, labels, bin_id="B1", random_state=0)


def test_fit_rejects_too_few_events() -> None:
    features = _synthetic_features(50)
    labels = _synthetic_labels(50)
    with pytest.raises(InsufficientDataError, match="≥100"):
        fit_per_regime_composite(features, labels, bin_id="B1", random_state=0)


def test_auroc_ci_lower_le_upper() -> None:
    features = _synthetic_features(200)
    labels = _synthetic_labels(200)
    result = fit_per_regime_composite(
        features, labels, bin_id="B3", random_state=42, n_bootstrap=200
    )
    assert result.auroc_ci_lower <= result.auroc <= result.auroc_ci_upper


def test_n_train_held_out_sum_equals_total() -> None:
    features = _synthetic_features(200)
    labels = _synthetic_labels(200)
    result = fit_per_regime_composite(
        features, labels, bin_id="B3", random_state=42, n_bootstrap=100
    )
    assert result.n_events_train + result.n_events_held_out == 200
