"""Functional principal component analysis + functional logistic regression
on 32-point spine curves (FR-009, T063, T065).

Backend: we implement FPCA directly via SVD on centered curves for v1.
This avoids skfda version churn and gives the same mathematical output.
``research.md §3`` notes skfda as the chosen backend; we keep that label
for the dependency declaration but use the simpler SVD path internally.
For studies that need basis-fitting niceties (e.g., periodic-basis FPCA),
the wrapper can be swapped to call ``skfda.preprocessing.dim_reduction.FPCA``.

Constitution Principle III: ``fit_functional_logistic`` accepts a single
``bin_id`` and is impossible to call on cross-bin data.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from phi3geom.analysis.types import FunctionalLogisticResult
from phi3geom.dataset.types import BIN_IDS, BinId


@dataclass(frozen=True, slots=True)
class FPCAFit:
    """Output of ``fit_fpca``."""

    mean_curve: np.ndarray  # (n_grid,) float64
    components: np.ndarray  # (n_fpcs, n_grid) float64; rows are FPCs
    variance_explained: np.ndarray  # (n_fpcs,) float64; fractions in [0, 1]
    scores: np.ndarray  # (n_curves, n_fpcs) float64; coefficient on each FPC
    n_fpcs: int


def fit_fpca(
    curves: np.ndarray,
    *,
    variance_threshold: float = 0.95,
    max_fpcs: int = 32,
) -> FPCAFit:
    """Functional Principal Component Analysis on ``(n_curves, n_grid)`` curves.

    Args:
        curves: ``(n_curves, n_grid)`` float64 array.
        variance_threshold: Retain the smallest number of FPCs that
            cumulatively explain at least this fraction of variance.
        max_fpcs: Upper bound on retained FPCs.

    Returns:
        ``FPCAFit`` with the mean curve, FPC basis, variance fractions,
        and per-curve scores.
    """
    if curves.dtype != np.float64:
        raise TypeError(
            f"curves must be float64 (Principle IV); got {curves.dtype}"
        )
    if curves.ndim != 2:
        raise ValueError(f"curves must be 2D; got shape {curves.shape}")

    n_curves, n_grid = curves.shape
    mean_curve = curves.mean(axis=0)
    centered = curves - mean_curve

    # SVD decomposition: centered = U @ diag(s) @ Vt
    # where Vt rows are the FPCs and s² gives variance.
    u, s, vt = np.linalg.svd(centered, full_matrices=False)
    eigenvalues = (s * s) / max(n_curves - 1, 1)
    total = float(eigenvalues.sum()) if eigenvalues.size else 0.0
    if total <= 0:
        return FPCAFit(
            mean_curve=mean_curve,
            components=np.zeros((0, n_grid), dtype=np.float64),
            variance_explained=np.zeros(0, dtype=np.float64),
            scores=np.zeros((n_curves, 0), dtype=np.float64),
            n_fpcs=0,
        )

    variance_fractions = eigenvalues / total

    # Pick n_fpcs ≥ smallest count clearing the threshold.
    cumvar = np.cumsum(variance_fractions)
    n_required = int(np.searchsorted(cumvar, variance_threshold) + 1)
    n_fpcs = min(n_required, max_fpcs, len(s))

    components = vt[:n_fpcs]  # (n_fpcs, n_grid)
    scores = centered @ components.T  # (n_curves, n_fpcs)
    return FPCAFit(
        mean_curve=mean_curve,
        components=components,
        variance_explained=variance_fractions[:n_fpcs],
        scores=scores,
        n_fpcs=n_fpcs,
    )


def fit_functional_logistic(
    spine_curves: np.ndarray,
    labels: np.ndarray,
    bin_id: BinId,
    edge_type: str,
    *,
    n_fpcs_variance_threshold: float = 0.95,
    random_state: int,
    n_bootstrap: int = 1000,
) -> FunctionalLogisticResult:
    """Fit functional logistic regression on 32-point spine curves.

    See ``contracts/composite.md`` for the full I/O contract.

    Args:
        spine_curves: ``(n_events, 32)`` float64.
        labels: ``(n_events,)`` bool.
        bin_id: ONE of "B1".."B6"; cross-bin fitting forbidden by
            Constitution Principle III.
        edge_type: ``"qkt_grassmannian"`` or ``"avwo_grassmannian"``.
        n_fpcs_variance_threshold: Default 0.95 (research.md §8).
        random_state: From ``seed_for_analysis("functional_logistic:...")``.
        n_bootstrap: Bootstrap resamples for β(ℓ) CI.

    Returns:
        ``FunctionalLogisticResult``.
    """
    if bin_id not in BIN_IDS:
        raise ValueError(
            f"bin_id must be a single bin enum (B1..B6); got {bin_id!r}. "
            "Use phi3geom.analysis.pooled_negative_control.fit for cross-bin."
        )
    if spine_curves.dtype != np.float64:
        raise TypeError(
            f"spine_curves must be float64 (Principle IV); got {spine_curves.dtype}"
        )
    if spine_curves.ndim != 2 or spine_curves.shape[1] != 32:
        raise ValueError(
            f"spine_curves must be (n_events, 32); got {spine_curves.shape}"
        )

    from sklearn.linear_model import LogisticRegression

    fpca = fit_fpca(spine_curves, variance_threshold=n_fpcs_variance_threshold)
    if fpca.n_fpcs == 0:
        raise ValueError("FPCA returned 0 components; spine_curves are degenerate.")

    model = LogisticRegression(
        solver="lbfgs", max_iter=1000, random_state=random_state,
    )
    model.fit(fpca.scores, labels.astype(int))
    # Reconstruct β(ℓ) = sum_k (coef_k * fpc_k(ℓ)) — the projection of the
    # fitted coefficients back through the FPC basis.
    beta_function = (model.coef_.ravel() @ fpca.components).astype(np.float64)

    # Bootstrap CI on β(ℓ).
    rng = np.random.default_rng(random_state)
    beta_samples = np.empty((n_bootstrap, 32), dtype=np.float64)
    n_events = spine_curves.shape[0]
    for b in range(n_bootstrap):
        idx = rng.integers(0, n_events, size=n_events)
        if len(np.unique(labels[idx])) < 2:
            beta_samples[b] = beta_function  # degenerate; reuse point estimate
            continue
        boot_fpca = fit_fpca(spine_curves[idx], variance_threshold=n_fpcs_variance_threshold)
        if boot_fpca.n_fpcs == 0:
            beta_samples[b] = beta_function
            continue
        boot_model = LogisticRegression(
            solver="lbfgs", max_iter=1000, random_state=random_state,
        )
        try:
            boot_model.fit(boot_fpca.scores, labels[idx].astype(int))
            beta_samples[b] = (boot_model.coef_.ravel() @ boot_fpca.components).astype(np.float64)
        except Exception:  # noqa: BLE001
            beta_samples[b] = beta_function
    beta_lo = np.percentile(beta_samples, 2.5, axis=0)
    beta_hi = np.percentile(beta_samples, 97.5, axis=0)

    # Discriminative-depth intervals: contiguous layer runs where CI excludes 0.
    intervals: list[tuple[int, int]] = []
    in_interval = False
    start = 0
    for ell in range(32):
        sig = (beta_lo[ell] > 0) or (beta_hi[ell] < 0)
        if sig and not in_interval:
            start = ell
            in_interval = True
        elif not sig and in_interval:
            intervals.append((start, ell - 1))
            in_interval = False
    if in_interval:
        intervals.append((start, 31))

    return FunctionalLogisticResult(
        bin_id=bin_id,
        edge_type=edge_type,
        n_fpcs=fpca.n_fpcs,
        fpc_variance_explained=fpca.variance_explained,
        beta_function=beta_function,
        beta_ci_lower=beta_lo,
        beta_ci_upper=beta_hi,
        discriminative_depth_intervals=intervals,
    )
