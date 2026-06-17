"""Redundancy / orthogonality analysis (SP-0 harness interface, T048).

So "no tool untouched" does not collapse into many correlated copies of one
confidence detector (program §5 rigor note). For each feature we report its
*marginal* correlation with the target and its *partial* correlation controlling
for the other features — a feature with high marginal but low partial correlation
is redundant (its signal is already carried by the others).
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LinearRegression


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    denom = float(np.sqrt(np.sum(a * a) * np.sum(b * b)))
    return float(np.sum(a * b) / denom) if denom > 0 else 0.0


def _partial_corr_with_target(X: np.ndarray, y: np.ndarray, j: int) -> float:
    """Partial correlation of feature ``j`` with ``y`` controlling for the rest."""
    others = np.delete(X, j, axis=1)
    if others.shape[1] == 0:
        return _pearson(X[:, j], y)
    rj = X[:, j] - LinearRegression().fit(others, X[:, j]).predict(others)
    ry = y - LinearRegression().fit(others, y).predict(others)
    return _pearson(rj, ry)


def redundancy(
    X: np.ndarray,
    y: np.ndarray,
    *,
    feature_names: list[str] | None = None,
) -> dict:
    """Per-feature marginal vs partial correlation with the target.

    Returns ``{feature_names, marginal_correlations, partial_correlations}``. A
    large gap (high marginal, low partial) marks a redundant feature.
    """
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    d = X.shape[1]
    names = feature_names if feature_names is not None else [f"f{j}" for j in range(d)]
    marginal = [_pearson(X[:, j], y) for j in range(d)]
    partial = [_partial_corr_with_target(X, y, j) for j in range(d)]
    return {
        "feature_names": names,
        "marginal_correlations": marginal,
        "partial_correlations": partial,
    }
