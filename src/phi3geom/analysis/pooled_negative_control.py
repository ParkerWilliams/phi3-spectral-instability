"""Pooled-across-bin logistic for the SC-003 negative-control demonstration.

This module is the **only** place in the analysis layer that fits a logistic
on events from multiple bins. ``phi3geom.analysis.composite`` MUST NOT
import from this module (Constitution Principle III at the file-system
level).

Its output is labeled ``PooledNegativeControl`` (a distinct dataclass from
``PerRegimeCompositeFit``) so it is type-distinguishable downstream in
``reporting/writeup.py``.

T069 (this version, US4) replaces the T029 ``NotImplementedError``
skeleton with the sklearn-backed fit.
"""

from __future__ import annotations

import numpy as np

from phi3geom.analysis.types import PooledNegativeControl
from phi3geom.geometry import FEATURE_NAMES


def fit(
    features: np.ndarray,
    labels: np.ndarray,
    *,
    feature_names: tuple[str, ...] | None = None,
    l2_penalty: float = 1.0,
    random_state: int,
    held_out_fraction: float = 0.2,
    n_bootstrap: int = 1000,
) -> PooledNegativeControl:
    """Fit an L2-regularized logistic on events POOLED across all 6 bins.

    Args:
        features: ``(n_events, n_features)`` float64 — POOLED data.
        labels: ``(n_events,)`` bool.
        feature_names: Names for reporting (default: canonical FEATURE_NAMES).
        l2_penalty: L2 regularization strength.
        random_state: From ``seed_for_analysis("pooled_negative_control")``.
        held_out_fraction: Default 0.2.
        n_bootstrap: AUROC CI resamples.

    Returns:
        ``PooledNegativeControl`` (distinct from ``PerRegimeCompositeFit``).
    """
    if features.ndim != 2:
        raise ValueError(f"features must be 2D; got shape {features.shape}")
    if features.dtype != np.float64:
        raise TypeError(
            f"features must be float64 (Principle IV); got {features.dtype}"
        )
    if labels.ndim != 1 or labels.shape[0] != features.shape[0]:
        raise ValueError(
            f"labels shape mismatch: features {features.shape[0]} events, "
            f"labels {labels.shape}"
        )

    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split

    n_features = features.shape[1]
    if feature_names is None:
        feature_names = FEATURE_NAMES if n_features == len(FEATURE_NAMES) else tuple(
            f"f_{i}" for i in range(n_features)
        )

    # NaN imputation by column median (Ricci column at index 6 may carry NaN).
    arr = features.copy()
    for col in range(n_features):
        column = arr[:, col]
        nan_mask = np.isnan(column)
        if not nan_mask.any():
            continue
        median = float(np.nanmedian(column))
        column[nan_mask] = median if np.isfinite(median) else 0.0

    x_train, x_test, y_train, y_test = train_test_split(
        arr, labels.astype(int),
        test_size=held_out_fraction,
        random_state=random_state,
        stratify=labels,
    )
    model = LogisticRegression(
        penalty="l2", C=1.0 / l2_penalty,
        solver="lbfgs", max_iter=1000, random_state=random_state,
    )
    model.fit(x_train, y_train)
    y_scores = model.predict_proba(x_test)[:, 1]
    auroc = float(roc_auc_score(y_test, y_scores))

    # Bootstrap CI.
    rng = np.random.default_rng(random_state)
    aurocs: list[float] = []
    n = len(y_test)
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        ys = y_test[idx]
        if len(np.unique(ys)) < 2:
            continue
        aurocs.append(float(roc_auc_score(ys, y_scores[idx])))
    aurocs.sort()
    lo = aurocs[int(0.025 * len(aurocs))] if aurocs else float("nan")
    hi = aurocs[int(0.975 * len(aurocs)) - 1] if aurocs else float("nan")

    return PooledNegativeControl(
        feature_names=feature_names,
        coefficients=model.coef_.ravel().astype(np.float64),
        intercept=float(model.intercept_[0]),
        auroc=auroc,
        auroc_ci_lower=lo,
        auroc_ci_upper=hi,
        n_events_train=len(x_train),
        n_events_held_out=len(x_test),
    )
