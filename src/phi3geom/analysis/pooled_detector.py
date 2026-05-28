"""The headline pooled, distance-blind failure detector.

Constitution v2.0.0, Principle III: the PRIMARY analysis is a single
classifier fit over all events POOLED across evidence-distance bins, fed
ONLY attention-geometry features and BLIND to evidence distance. This module
intentionally takes no ``bin_id`` parameter — distance cannot enter the model.

The per-bin ``composite`` module is the SECONDARY diagnostic and lives apart.
"""

from __future__ import annotations

import numpy as np

from phi3geom.analysis.types import PooledDetectorFit

DEFAULT_N_BOOTSTRAP = 1000


def fit_pooled_detector(
    features: np.ndarray,
    labels: np.ndarray,
    *,
    feature_names: tuple[str, ...] | None = None,
    l2_penalty: float = 1.0,
    random_state: int,
    held_out_fraction: float = 0.2,
    n_bootstrap: int = DEFAULT_N_BOOTSTRAP,
) -> PooledDetectorFit:
    """Fit an L2-regularized logistic on events POOLED across all bins.

    Args:
        features: ``(n_events, n_features)`` float64. Geometry features only.
        labels: ``(n_events,)`` bool (True = failure).
        feature_names: Names for reporting (default ``f_0..f_{n-1}``).
        l2_penalty: L2 strength; ``C = 1/l2_penalty``.
        random_state: From ``seed_for_analysis("pooled_detector")``.
        held_out_fraction: Test split (default 0.2).
        n_bootstrap: Percentile-bootstrap resamples for the AUROC CI.
    """
    if features.ndim != 2:
        raise ValueError(f"features must be 2D; got shape {features.shape}")
    if features.dtype != np.float64:
        raise TypeError(
            f"features must be float64 (Principle IV); got {features.dtype}"
        )
    if labels.ndim != 1 or labels.shape[0] != features.shape[0]:
        raise ValueError(
            f"labels shape mismatch: {features.shape[0]} events vs {labels.shape}"
        )

    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split

    n_features = features.shape[1]
    if feature_names is None:
        feature_names = tuple(f"f_{i}" for i in range(n_features))

    # Median-impute NaN columns (Ricci column may be NaN on the baseline path).
    arr = features.copy()
    for col in range(n_features):
        column = arr[:, col]
        nan_mask = np.isnan(column)
        if nan_mask.any():
            median = float(np.nanmedian(column))
            column[nan_mask] = median if np.isfinite(median) else 0.0

    x_train, x_test, y_train, y_test = train_test_split(
        arr, labels.astype(int),
        test_size=held_out_fraction, random_state=random_state, stratify=labels,
    )
    model = LogisticRegression(
        C=1.0 / l2_penalty, solver="lbfgs", max_iter=1000, random_state=random_state,
    )
    model.fit(x_train, y_train)
    y_scores = model.predict_proba(x_test)[:, 1]
    auroc = float(roc_auc_score(y_test, y_scores))

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

    return PooledDetectorFit(
        feature_names=feature_names,
        coefficients=model.coef_.ravel().astype(np.float64),
        intercept=float(model.intercept_[0]),
        auroc=auroc,
        auroc_ci_lower=lo,
        auroc_ci_upper=hi,
        n_events_train=len(x_train),
        n_events_held_out=len(x_test),
    )
