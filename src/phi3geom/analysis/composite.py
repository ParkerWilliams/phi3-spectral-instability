"""Per-regime composite logistic regression (FR-008, contracts/composite.md).

Constitution Principle III is enforced at the function-signature level: the
``bin_id`` parameter is required, must be a single bin, and the function
refuses to fit on cross-bin pooled data. The pooled negative control lives
in ``phi3geom.analysis.pooled_negative_control`` and is NOT re-exported
from this module — by design, a future ``from phi3geom.analysis.composite
import pooled_fit`` MUST fail.

T044 (this version, US1) replaces the NotImplementedError skeleton from T029
with the sklearn-backed fit logic.
"""

from __future__ import annotations

import numpy as np

from phi3geom.dataset.types import BIN_IDS, BinId

# Minimum per-bin event count for a stable fit.
MIN_EVENTS_FOR_FIT = 100

# Default bootstrap parameters for AUROC CI.
DEFAULT_N_BOOTSTRAP = 1000


class InsufficientDataError(ValueError):
    """Per-bin event count below ``MIN_EVENTS_FOR_FIT``."""


def fit_per_regime_composite(
    features: np.ndarray,
    labels: np.ndarray,
    bin_id: BinId,
    *,
    feature_names: tuple[str, ...] | None = None,
    l2_penalty: float = 1.0,
    random_state: int,
    held_out_fraction: float = 0.2,
    n_bootstrap: int = DEFAULT_N_BOOTSTRAP,
) -> "PerRegimeCompositeFit":  # noqa: F821 - forward reference
    """Fit an L2-regularized logistic regression on events from ONE bin.

    See ``contracts/composite.md`` for the full I/O contract.
    """
    _validate_bin_id(bin_id)
    _validate_inputs(features, labels)

    # Lazy imports keep test_principle_iii_segregation.py's import-time check
    # cheap and avoid pulling sklearn until the fit actually runs.
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split

    from phi3geom.analysis.types import PerRegimeCompositeFit

    n_features = features.shape[1]
    if feature_names is None:
        feature_names = tuple(f"f_{i}" for i in range(n_features))
    elif len(feature_names) != n_features:
        raise ValueError(
            f"feature_names length {len(feature_names)} != n_features {n_features}"
        )

    # NaN handling: median impute the Forman-Ricci column (index 6 in
    # canonical FEATURE_NAMES order) per research.md §10. We impute generally
    # by column to be robust if the caller passed a different feature layout.
    features_imputed = _impute_nan_columns_inplace_copy(features)

    # Stratified split. With small bin sizes the held-out set can be tiny
    # (e.g., 100 events → 20 held out), so we keep the split at 80/20 by
    # default.
    rng = np.random.default_rng(random_state)
    x_train, x_test, y_train, y_test = train_test_split(
        features_imputed,
        labels.astype(int),
        test_size=held_out_fraction,
        random_state=random_state,
        stratify=labels,
    )

    # ``LogisticRegression`` uses ``C = 1 / l2_penalty`` as the inverse-reg
    # parameter.
    # L2 is the default penalty; we set it via C only (passing penalty="l2"
    # explicitly is deprecated in sklearn ≥1.8 and removed in 1.10).
    model = LogisticRegression(
        C=1.0 / l2_penalty,
        solver="lbfgs",
        max_iter=1000,
        random_state=random_state,
    )
    model.fit(x_train, y_train)

    # Compute AUROC on the held-out set.
    y_scores = model.predict_proba(x_test)[:, 1]
    auroc = float(roc_auc_score(y_test, y_scores))

    # Percentile bootstrap CI on AUROC.
    auroc_lo, auroc_hi = _bootstrap_auroc_ci(
        y_test=y_test,
        y_scores=y_scores,
        n_bootstrap=n_bootstrap,
        rng=rng,
    )

    return PerRegimeCompositeFit(
        bin_id=bin_id,
        feature_names=feature_names,
        coefficients=model.coef_.ravel().astype(np.float64),
        intercept=float(model.intercept_[0]),
        auroc=auroc,
        auroc_ci_lower=auroc_lo,
        auroc_ci_upper=auroc_hi,
        n_events_train=len(x_train),
        n_events_held_out=len(x_test),
    )


# ---------------------------------------------------------------------------
# Validation helpers (shared with T029 skeleton)
# ---------------------------------------------------------------------------

def _validate_bin_id(bin_id: object) -> None:
    """Enforce Constitution Principle III at the function boundary."""
    if bin_id is None:
        raise ValueError(
            "bin_id must be a single bin enum (B1..B6); got None. "
            "Use phi3geom.analysis.pooled_negative_control.fit for cross-bin "
            "analyses (SC-003 only)."
        )
    if bin_id == "ALL":
        raise ValueError(
            "bin_id='ALL' is forbidden by Constitution Principle III. "
            "Use phi3geom.analysis.pooled_negative_control.fit for SC-003."
        )
    if bin_id not in BIN_IDS:
        raise ValueError(
            f"bin_id must be one of {BIN_IDS}; got {bin_id!r}."
        )


def _validate_inputs(features: np.ndarray, labels: np.ndarray) -> None:
    if features.ndim != 2:
        raise ValueError(f"features must be 2D; got shape {features.shape}")
    if labels.ndim != 1:
        raise ValueError(f"labels must be 1D; got shape {labels.shape}")
    if features.shape[0] != labels.shape[0]:
        raise ValueError(
            f"features and labels disagree on n_events: {features.shape[0]} vs "
            f"{labels.shape[0]}"
        )
    if features.dtype != np.float64:
        raise TypeError(
            f"features must be float64 (Constitution Principle IV); got {features.dtype}."
        )
    if features.shape[0] < MIN_EVENTS_FOR_FIT:
        raise InsufficientDataError(
            f"Need ≥{MIN_EVENTS_FOR_FIT} events for a stable per-bin fit; "
            f"got {features.shape[0]}."
        )


def _impute_nan_columns_inplace_copy(features: np.ndarray) -> np.ndarray:
    """Median-impute NaN entries column-by-column. Returns a copy."""
    arr = features.copy()
    for col in range(arr.shape[1]):
        column = arr[:, col]
        nan_mask = np.isnan(column)
        if not nan_mask.any():
            continue
        median = float(np.nanmedian(column))
        if not np.isfinite(median):
            median = 0.0
        column[nan_mask] = median
    return arr


def _bootstrap_auroc_ci(
    *,
    y_test: np.ndarray,
    y_scores: np.ndarray,
    n_bootstrap: int,
    rng: np.random.Generator,
    ci_level: float = 0.95,
) -> tuple[float, float]:
    """Percentile bootstrap CI on AUROC."""
    from sklearn.metrics import roc_auc_score

    n = len(y_test)
    aurocs: list[float] = []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        ys = y_test[idx]
        if len(np.unique(ys)) < 2:
            continue  # degenerate resample
        aurocs.append(float(roc_auc_score(ys, y_scores[idx])))
    if not aurocs:
        return float("nan"), float("nan")
    aurocs.sort()
    alpha = (1 - ci_level) / 2
    lo_idx = int(alpha * len(aurocs))
    hi_idx = int((1 - alpha) * len(aurocs)) - 1
    return aurocs[lo_idx], aurocs[hi_idx]
