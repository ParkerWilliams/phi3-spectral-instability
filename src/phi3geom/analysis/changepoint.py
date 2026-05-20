"""CUSUM / EWMA change-point detection on FPCA-score trajectories (T067).

Ports the DCSBM primitives for the two-stage FDA → TS pipeline. The long-line
analysis (T071) feeds per-(ℓ, h) over-token FPCA scores through these
detectors to identify when the geometry of one head changes leading up to
the answer-commit point.

Research.md §7: CUSUM as the primary v1 detector (matches DCSBM
precedent); EWMA exposed for sensitivity analysis in the appendix.
"""

from __future__ import annotations

import numpy as np


def cusum_detect(
    series: np.ndarray,
    *,
    threshold: float = 5.0,
    drift: float = 0.0,
) -> dict[str, np.ndarray | int]:
    """Two-sided CUSUM change-point detector.

    Args:
        series: 1D float64 array of observations.
        threshold: Decision boundary on the cumulative sum.
        drift: Reference value (e.g., expected mean under null).

    Returns:
        ``{
            "positive_cusum": (n,) array (one-sided positive accumulator),
            "negative_cusum": (n,) array (one-sided negative accumulator),
            "first_alarm_idx": int (index of first |S| > threshold, or -1),
        }``.
    """
    if series.dtype != np.float64:
        raise TypeError(f"series must be float64; got {series.dtype}")
    if series.ndim != 1:
        raise ValueError(f"series must be 1D; got shape {series.shape}")

    n = series.shape[0]
    s_pos = np.zeros(n, dtype=np.float64)
    s_neg = np.zeros(n, dtype=np.float64)
    first_alarm = -1
    for i in range(n):
        delta = series[i] - drift
        prev_pos = s_pos[i - 1] if i > 0 else 0.0
        prev_neg = s_neg[i - 1] if i > 0 else 0.0
        s_pos[i] = max(0.0, prev_pos + delta)
        s_neg[i] = max(0.0, prev_neg - delta)
        if (s_pos[i] > threshold or s_neg[i] > threshold) and first_alarm == -1:
            first_alarm = i
    return {
        "positive_cusum": s_pos,
        "negative_cusum": s_neg,
        "first_alarm_idx": first_alarm,
    }


def ewma_detect(
    series: np.ndarray,
    *,
    smoothing: float = 0.3,
    threshold: float = 3.0,
    drift: float = 0.0,
) -> dict[str, np.ndarray | int]:
    """Exponentially-weighted moving average change-point detector.

    Used as the sensitivity-check alternative in the writeup appendix
    (research.md §7).

    Args:
        series: 1D float64 array.
        smoothing: λ in [0, 1] — higher = more weight on recent values.
        threshold: Decision boundary on |EWMA - drift|.
        drift: Null-hypothesis mean.

    Returns:
        ``{"ewma": (n,) array, "first_alarm_idx": int}``.
    """
    if series.dtype != np.float64:
        raise TypeError(f"series must be float64; got {series.dtype}")
    if not 0.0 < smoothing <= 1.0:
        raise ValueError(f"smoothing must be in (0, 1]; got {smoothing}")
    if series.ndim != 1:
        raise ValueError(f"series must be 1D; got shape {series.shape}")

    n = series.shape[0]
    ewma = np.zeros(n, dtype=np.float64)
    first_alarm = -1
    prev = drift
    for i in range(n):
        ewma[i] = smoothing * series[i] + (1 - smoothing) * prev
        prev = ewma[i]
        if abs(ewma[i] - drift) > threshold and first_alarm == -1:
            first_alarm = i
    return {
        "ewma": ewma,
        "first_alarm_idx": first_alarm,
    }
