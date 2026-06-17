"""Incremental-AUROC-over-baseline (SP-0 harness interface, T046).

The beats-baselines bar (constitution Principle III v3.0.0): does adding the
geometry features improve AUROC *beyond* the cheap-confidence baseline? Reported as
the paired CV delta with a bootstrap CI; the bar is ``delta_ci`` lower bound > 0.
Metrics only — SP-1 supplies the baseline columns, SP-2 the geometry columns.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def _auroc_on_split(X, y, tr, te) -> float | None:
    if len(np.unique(y[tr])) < 2 or len(np.unique(y[te])) < 2:
        return None
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    clf.fit(X[tr], y[tr])
    return float(roc_auc_score(y[te], clf.predict_proba(X[te])[:, 1]))


def incremental_auroc(
    X_geom: np.ndarray,
    X_baseline: np.ndarray,
    y: np.ndarray,
    *,
    n_repeats: int = 5,
    n_folds: int = 5,
    n_boot: int = 1000,
    seed: int = 0,
) -> dict:
    """Paired CV AUROC of ``baseline`` vs ``baseline ⊕ geom`` + bootstrap CI.

    Returns ``{auroc_baseline, auroc_combined, delta, delta_ci}`` where
    ``delta_ci`` is the 95% bootstrap interval of the paired per-fold deltas.
    """
    Xb = np.asarray(X_baseline, dtype=np.float64)
    Xg = np.asarray(X_geom, dtype=np.float64)
    y = np.asarray(y, dtype=int)
    Xc = np.hstack([Xb, Xg])
    rng = np.random.default_rng(seed)

    base, comb = [], []
    for r in range(n_repeats):
        skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed + r)
        for tr, te in skf.split(Xb, y):
            ab = _auroc_on_split(Xb, y, tr, te)
            ac = _auroc_on_split(Xc, y, tr, te)
            if ab is not None and ac is not None:
                base.append(ab)
                comb.append(ac)

    base = np.array(base)
    comb = np.array(comb)
    deltas = comb - base
    boot = np.array(
        [np.mean(rng.choice(deltas, size=len(deltas), replace=True)) for _ in range(n_boot)]
    )
    return {
        "auroc_baseline": float(np.mean(base)),
        "auroc_combined": float(np.mean(comb)),
        "delta": float(np.mean(deltas)),
        "delta_ci": (float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))),
    }
