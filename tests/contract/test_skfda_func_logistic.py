"""Functional logistic regression contract test (T064)."""

from __future__ import annotations

import numpy as np
import pytest

from phi3geom.analysis.fda import fit_functional_logistic
from phi3geom.analysis.types import FunctionalLogisticResult


def _signal_curves(n: int, seed: int, signal_strength: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Make 32-point curves where half have a depth-localized bump (label True)
    and the other half don't (label False)."""
    rng = np.random.default_rng(seed)
    depth_grid = np.linspace(0.0, 1.0, 32)
    curves = np.zeros((n, 32), dtype=np.float64)
    labels = np.zeros((n,), dtype=bool)
    for i in range(n):
        labels[i] = i % 2 == 0
        noise = 0.1 * rng.standard_normal(32)
        if labels[i]:
            curves[i] = signal_strength * np.exp(-(depth_grid - 0.5) ** 2 / 0.05) + noise
        else:
            curves[i] = noise
    return curves, labels


def test_functional_logistic_returns_result_dataclass() -> None:
    curves, labels = _signal_curves(200, seed=0)
    result = fit_functional_logistic(
        curves, labels, bin_id="B3", edge_type="qkt_grassmannian",
        random_state=42, n_bootstrap=100,
    )
    assert isinstance(result, FunctionalLogisticResult)
    assert result.bin_id == "B3"
    assert result.edge_type == "qkt_grassmannian"
    assert result.beta_function.shape == (32,)
    assert result.beta_ci_lower.shape == (32,)
    assert result.beta_ci_upper.shape == (32,)


def test_functional_logistic_ci_band_brackets_point_estimate() -> None:
    curves, labels = _signal_curves(200, seed=1)
    result = fit_functional_logistic(
        curves, labels, bin_id="B2", edge_type="avwo_grassmannian",
        random_state=42, n_bootstrap=100,
    )
    assert np.all(result.beta_ci_lower <= result.beta_function + 1e-9)
    assert np.all(result.beta_function <= result.beta_ci_upper + 1e-9)


def test_functional_logistic_rejects_unknown_bin() -> None:
    curves, labels = _signal_curves(150, seed=2)
    with pytest.raises(ValueError, match="bin_id"):
        fit_functional_logistic(
            curves, labels, bin_id="B7", edge_type="qkt_grassmannian",  # type: ignore[arg-type]
            random_state=0, n_bootstrap=10,
        )


def test_functional_logistic_rejects_float32() -> None:
    curves = np.zeros((100, 32), dtype=np.float32)
    labels = np.zeros(100, dtype=bool)
    with pytest.raises(TypeError, match="float64"):
        fit_functional_logistic(
            curves, labels, bin_id="B1", edge_type="qkt_grassmannian",
            random_state=0,
        )


def test_functional_logistic_rejects_wrong_grid_size() -> None:
    curves = np.zeros((100, 16), dtype=np.float64)
    labels = np.zeros(100, dtype=bool)
    with pytest.raises(ValueError, match="32"):
        fit_functional_logistic(
            curves, labels, bin_id="B1", edge_type="qkt_grassmannian",
            random_state=0,
        )


def test_functional_logistic_deterministic_given_seed() -> None:
    curves, labels = _signal_curves(200, seed=3)
    a = fit_functional_logistic(
        curves, labels, bin_id="B3", edge_type="qkt_grassmannian",
        random_state=99, n_bootstrap=50,
    )
    b = fit_functional_logistic(
        curves, labels, bin_id="B3", edge_type="qkt_grassmannian",
        random_state=99, n_bootstrap=50,
    )
    assert np.allclose(a.beta_function, b.beta_function)
    assert np.allclose(a.beta_ci_lower, b.beta_ci_lower)
    assert np.allclose(a.beta_ci_upper, b.beta_ci_upper)
