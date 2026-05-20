"""Tests for ``phi3geom.analysis.changepoint`` (T066)."""

from __future__ import annotations

import numpy as np
import pytest

from phi3geom.analysis.changepoint import cusum_detect, ewma_detect


def test_cusum_no_alarm_on_null_series() -> None:
    """A constant-zero series with threshold=5 produces no alarm."""
    series = np.zeros(100, dtype=np.float64)
    result = cusum_detect(series, threshold=5.0)
    assert result["first_alarm_idx"] == -1


def test_cusum_alarm_on_positive_step_change() -> None:
    """A step change at index 20 → alarm raised."""
    series = np.zeros(100, dtype=np.float64)
    series[20:] = 1.0  # step change
    result = cusum_detect(series, threshold=5.0)
    assert result["first_alarm_idx"] >= 20


def test_cusum_alarm_on_negative_step() -> None:
    series = np.zeros(100, dtype=np.float64)
    series[30:] = -1.0
    result = cusum_detect(series, threshold=5.0)
    assert result["first_alarm_idx"] >= 30


def test_cusum_accumulators_non_negative() -> None:
    series = np.random.default_rng(0).standard_normal(50)
    result = cusum_detect(series.astype(np.float64), threshold=5.0)
    assert np.all(result["positive_cusum"] >= 0)
    assert np.all(result["negative_cusum"] >= 0)


def test_cusum_rejects_float32() -> None:
    s = np.zeros(10, dtype=np.float32)
    with pytest.raises(TypeError, match="float64"):
        cusum_detect(s)


def test_ewma_smoothing_in_bounds() -> None:
    series = np.ones(100, dtype=np.float64) * 5.0
    result = ewma_detect(series, smoothing=0.3, threshold=10.0)
    # EWMA approaches 5; doesn't alarm because |5 - 0| ≤ 10.
    assert result["first_alarm_idx"] == -1


def test_ewma_alarm_on_large_drift() -> None:
    series = np.ones(50, dtype=np.float64) * 10.0
    result = ewma_detect(series, smoothing=0.5, threshold=3.0)
    assert result["first_alarm_idx"] != -1


def test_ewma_rejects_invalid_smoothing() -> None:
    s = np.zeros(10, dtype=np.float64)
    with pytest.raises(ValueError, match="smoothing"):
        ewma_detect(s, smoothing=0.0)
    with pytest.raises(ValueError, match="smoothing"):
        ewma_detect(s, smoothing=1.5)


def test_ewma_qualitatively_smoother_than_raw() -> None:
    """EWMA produces smoother output than the raw series."""
    series = np.random.default_rng(0).standard_normal(100).astype(np.float64)
    result = ewma_detect(series, smoothing=0.1, threshold=10.0)
    # Variance of EWMA < variance of raw input
    assert result["ewma"].var() < series.var()
