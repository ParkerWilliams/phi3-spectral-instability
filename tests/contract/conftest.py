"""Fixtures specific to contract tests (library-wrapper boundaries)."""

from __future__ import annotations

import pytest


@pytest.fixture
def synthetic_spine_curves():
    """Factory returning `(n_curves, 32)` synthetic spine curves with known
    intrinsic dimensionality, for FPCA contract tests.
    """
    import numpy as np

    def _make(n_curves: int = 100, intrinsic_dim: int = 4, seed: int = 7) -> "np.ndarray":
        rng = np.random.default_rng(seed)
        depth_grid = np.linspace(0.0, 1.0, 32)
        # Build basis from sinusoids of low order to fix intrinsic_dim.
        basis = np.stack(
            [np.sin((k + 1) * np.pi * depth_grid) for k in range(intrinsic_dim)],
            axis=1,
        )  # shape (32, intrinsic_dim)
        coeffs = rng.standard_normal((n_curves, intrinsic_dim))
        noise = 0.05 * rng.standard_normal((n_curves, 32))
        return coeffs @ basis.T + noise

    return _make
