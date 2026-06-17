"""Analytic property tests for the in-pass Marchenko–Pastur reduction (SP-0).

Constitution II/IV: the new spectral-density primitive is verified against
closed-form values in float64 — the MP bulk edge for a known-aspect-ratio
Gaussian, plus a planted-spike detection check.
"""

import numpy as np
import pytest

from phi3geom.geometry.spectral import (
    covariance_eigenvalues,
    marchenko_pastur_edges,
    token_cloud_spectrum,
)


def test_mp_edges_closed_form():
    # gamma = 1/4 -> edges (1 - 1/2)^2 = 0.25, (1 + 1/2)^2 = 2.25
    lo, hi = marchenko_pastur_edges(0.25, sigma_sq=1.0)
    assert lo == pytest.approx(0.25, abs=1e-12)
    assert hi == pytest.approx(2.25, abs=1e-12)
    # gamma = 1 -> [0, 4]; sigma scales linearly
    lo1, hi1 = marchenko_pastur_edges(1.0, sigma_sq=2.0)
    assert lo1 == pytest.approx(0.0, abs=1e-12)
    assert hi1 == pytest.approx(8.0, abs=1e-12)


def test_mp_edges_reject_bad_gamma():
    with pytest.raises(ValueError):
        marchenko_pastur_edges(0.0)
    with pytest.raises(ValueError):
        marchenko_pastur_edges(-0.1)


def test_covariance_eigenvalues_descending_and_padded():
    rng = np.random.default_rng(0)
    x = rng.standard_normal((50, 8)).astype(np.float64)
    ev = covariance_eigenvalues(x)
    assert ev.shape == (8,)
    assert np.all(np.diff(ev) <= 1e-12)  # descending
    # n < p -> rank deficient, padded with zeros
    x2 = rng.standard_normal((5, 12)).astype(np.float64)
    ev2 = covariance_eigenvalues(x2)
    assert ev2.shape == (12,)
    assert np.count_nonzero(ev2 == 0.0) >= 12 - 5


def test_covariance_eigenvalues_rejects_float32():
    with pytest.raises(TypeError):
        covariance_eigenvalues(np.zeros((4, 4), dtype=np.float32))


def test_mp_bulk_edge_matches_gaussian():
    # Pure-noise Gaussian: empirical lambda_max sits at the MP upper edge
    # (up to finite-size Tracy-Widom fluctuations of order n^-2/3).
    rng = np.random.default_rng(42)
    n, p = 2000, 200  # gamma = 0.1
    x = rng.standard_normal((n, p)).astype(np.float64)
    out = token_cloud_spectrum(x, sigma_sq=1.0)  # known noise level
    _, hi = marchenko_pastur_edges(p / n, 1.0)
    assert out["mp_edge_upper"] == pytest.approx(hi, abs=1e-12)
    # empirical top eigenvalue near the predicted edge (loose finite-size band)
    assert out["lambda_max"] == pytest.approx(hi, rel=0.10)
    assert out["gamma"] == pytest.approx(0.1, abs=1e-12)


def test_planted_spike_detected():
    # Noise + one high-variance direction -> exactly one eigenvalue well above
    # the noise-level MP edge.
    rng = np.random.default_rng(7)
    n, p = 1500, 100
    x = rng.standard_normal((n, p)).astype(np.float64)
    x[:, 0] *= np.sqrt(20.0)  # variance-20 spike along feature 0
    out = token_cloud_spectrum(x, sigma_sq=1.0)
    assert out["n_spikes"] >= 1
    assert out["lambda_max"] > 5.0  # the spike, far above the ~1.7 edge


def test_token_cloud_spectrum_topk():
    rng = np.random.default_rng(1)
    x = rng.standard_normal((100, 30)).astype(np.float64)
    out = token_cloud_spectrum(x, k=5)
    assert out["eigenvalues"].shape == (5,)
    assert out["eigenvalues"].dtype == np.float64
