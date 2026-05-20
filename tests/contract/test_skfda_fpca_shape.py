"""FPCA contract test (T062).

The implementation uses an SVD-based FPCA wrapper (research.md §3 noted
``skfda`` as the chosen backend but the v1 wrapper implements the math
directly to avoid version churn). The shape contract is the same.
"""

from __future__ import annotations

import numpy as np
import pytest

from phi3geom.analysis.fda import FPCAFit, fit_fpca


def test_fpca_shapes(synthetic_spine_curves) -> None:
    curves = synthetic_spine_curves(n_curves=200, intrinsic_dim=4)
    fit = fit_fpca(curves, variance_threshold=0.95)
    assert isinstance(fit, FPCAFit)
    n_grid = curves.shape[1]
    assert fit.components.shape[1] == n_grid
    assert fit.scores.shape[0] == curves.shape[0]
    assert fit.scores.shape[1] == fit.n_fpcs
    assert fit.variance_explained.shape == (fit.n_fpcs,)


def test_fpca_variance_explained_decreasing(synthetic_spine_curves) -> None:
    curves = synthetic_spine_curves(n_curves=200, intrinsic_dim=5)
    fit = fit_fpca(curves)
    assert np.all(np.diff(fit.variance_explained) <= 1e-12)  # monotone decreasing


def test_fpca_threshold_returns_reasonable_n_fpcs(synthetic_spine_curves) -> None:
    """Intrinsic dimension 4 + small noise should give 4–6 FPCs at 0.95."""
    curves = synthetic_spine_curves(n_curves=200, intrinsic_dim=4)
    fit = fit_fpca(curves, variance_threshold=0.95)
    assert 2 <= fit.n_fpcs <= 8


def test_fpca_higher_threshold_more_fpcs(synthetic_spine_curves) -> None:
    curves = synthetic_spine_curves(n_curves=200, intrinsic_dim=6)
    f_90 = fit_fpca(curves, variance_threshold=0.90)
    f_99 = fit_fpca(curves, variance_threshold=0.99)
    assert f_99.n_fpcs >= f_90.n_fpcs


def test_fpca_rejects_float32() -> None:
    curves = np.zeros((100, 32), dtype=np.float32)
    with pytest.raises(TypeError, match="float64"):
        fit_fpca(curves)


def test_fpca_rejects_wrong_dims() -> None:
    curves = np.zeros((100,), dtype=np.float64)
    with pytest.raises(ValueError, match="2D"):
        fit_fpca(curves)
