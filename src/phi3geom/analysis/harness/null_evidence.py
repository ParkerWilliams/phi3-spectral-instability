"""Feature-width-generic null-evidence pack (SP-0 harness interface).

Generalizes the v1 hard-coded 7-feature evaluation into a width-agnostic pack:
repeated cross-validated AUROC, a label-permutation p-value, per-feature Cohen's d,
and the single-split "split-luck" distribution. This is the pre-registered
existence bar (CI lower bound > 0.5 AND permutation p < 0.05). Metrics only — the
geometry/baseline features are supplied by SP-1/SP-2.

The v1 lesson encoded here: a single-split point estimate lies (0.645 → 0.513), so
the headline is the repeated-CV mean plus the permutation test, never one split.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def _clf() -> object:
    return make_pipeline(
        StandardScaler(), LogisticRegression(max_iter=1000, solver="lbfgs")
    )


def _cv_auroc(X: np.ndarray, y: np.ndarray, *, n_folds: int, seed: int) -> float:
    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    scores: list[float] = []
    for tr, te in skf.split(X, y):
        if len(np.unique(y[tr])) < 2 or len(np.unique(y[te])) < 2:
            continue
        clf = _clf()
        clf.fit(X[tr], y[tr])
        p = clf.predict_proba(X[te])[:, 1]
        scores.append(roc_auc_score(y[te], p))
    return float(np.mean(scores)) if scores else float("nan")


def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2 or len(b) < 2:
        return 0.0
    na, nb = len(a), len(b)
    sp2 = ((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2)
    sp = float(np.sqrt(sp2))
    return float((a.mean() - b.mean()) / sp) if sp > 0 else 0.0


def null_evidence(
    X: np.ndarray,
    y: np.ndarray,
    *,
    n_repeats: int = 5,
    n_folds: int = 5,
    n_perm: int = 200,
    seed: int = 0,
) -> dict:
    """Repeated-CV AUROC + permutation p + Cohen's d + split-luck.

    Args:
        X: ``(N, d)`` feature matrix, any width.
        y: ``(N,)`` binary labels.
        n_repeats, n_folds, n_perm: evaluation budget.
        seed: RNG seed (reproducibility).

    Returns:
        Dict with ``cv_auroc_mean``, ``cv_auroc_std``, ``permutation_p``,
        ``null_mean``, ``cohens_d`` (per feature), ``split_luck_p975``.
    """
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=int)
    if X.ndim != 2:
        raise ValueError(f"X must be 2D; got shape {X.shape}")
    rng = np.random.default_rng(seed)

    cv = np.array(
        [_cv_auroc(X, y, n_folds=n_folds, seed=int(rng.integers(1_000_000_000)))
         for _ in range(n_repeats)]
    )
    cv_mean = float(np.nanmean(cv))
    cv_std = float(np.nanstd(cv))

    null = np.array(
        [_cv_auroc(X, rng.permutation(y), n_folds=n_folds,
                   seed=int(rng.integers(1_000_000_000)))
         for _ in range(n_perm)]
    )
    # +1 smoothing; one-sided (real >= null)
    perm_p = float((np.sum(null >= cv_mean) + 1) / (n_perm + 1))

    cohens_d = [_cohens_d(X[y == 1, j], X[y == 0, j]) for j in range(X.shape[1])]

    luck = np.array(
        [_cv_auroc(X, y, n_folds=2, seed=int(rng.integers(1_000_000_000)))
         for _ in range(n_perm)]
    )

    return {
        "cv_auroc_mean": cv_mean,
        "cv_auroc_std": cv_std,
        "permutation_p": perm_p,
        "null_mean": float(np.nanmean(null)),
        "cohens_d": cohens_d,
        "split_luck_p975": float(np.nanpercentile(luck, 97.5)),
    }
