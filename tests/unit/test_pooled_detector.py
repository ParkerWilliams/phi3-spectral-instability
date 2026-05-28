# tests/unit/test_pooled_detector.py
"""Pooled distance-blind detector (constitution v2.0.0, Principle III)."""
from __future__ import annotations

import numpy as np
import pytest

from phi3geom.analysis.pooled_detector import fit_pooled_detector
from phi3geom.analysis.types import PooledDetectorFit


def _separable(n=240, n_features=7, seed=0):
    rng = np.random.default_rng(seed)
    labels = np.zeros(n, dtype=bool)
    labels[::2] = True
    feats = rng.standard_normal((n, n_features)).astype(np.float64)
    feats[labels, 0] += 3.0  # feature 0 carries signal
    return feats, labels


def test_returns_pooled_detector_fit():
    feats, labels = _separable()
    fit = fit_pooled_detector(feats, labels, random_state=0, n_bootstrap=50)
    assert isinstance(fit, PooledDetectorFit)
    assert fit.coefficients.shape == (7,)
    assert fit.coefficients.dtype == np.float64


def test_recovers_signal_auroc():
    feats, labels = _separable()
    fit = fit_pooled_detector(feats, labels, random_state=0, n_bootstrap=200)
    assert fit.auroc > 0.9
    assert fit.beats_chance  # CI lower > 0.5


def test_rejects_non_float64():
    feats, labels = _separable()
    with pytest.raises(TypeError, match="float64"):
        fit_pooled_detector(feats.astype(np.float32), labels, random_state=0)


def test_takes_no_bin_id():
    # Distance-blind by construction: passing bin_id is a TypeError.
    feats, labels = _separable()
    with pytest.raises(TypeError):
        fit_pooled_detector(feats, labels, bin_id="B1", random_state=0)  # type: ignore[call-arg]


def test_imputes_nan_ricci_column():
    feats, labels = _separable()
    feats[:5, 6] = np.nan  # Ricci column may carry NaN on the baseline path
    fit = fit_pooled_detector(feats, labels, random_state=0, n_bootstrap=50)
    assert np.isfinite(fit.auroc)
