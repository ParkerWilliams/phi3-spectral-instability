"""Per-regime composite logistic regression (FR-008, contracts/composite.md).

Constitution Principle III is enforced at the function-signature level: the
``bin_id`` parameter is required, must be a single bin, and the function
refuses to fit on cross-bin pooled data. The pooled negative control lives
in ``phi3geom.analysis.pooled_negative_control`` and is NOT re-exported
from this module — by design, ``from phi3geom.analysis.composite import
fit`` of a pooled function MUST fail.

This module is a SKELETON at T029: ``fit_per_regime_composite`` validates
inputs and raises ``NotImplementedError`` for the actual sklearn-backed
fit. T044 (US1) replaces the NotImplementedError with the real fit logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from phi3geom.dataset.types import BIN_IDS, BinId

if TYPE_CHECKING:
    import numpy as np

    from phi3geom.analysis.types import PerRegimeCompositeFit

# Minimum per-bin event count for a stable fit (≥10× the candidate-feature
# parameter count of ~10–15 atomic-unit + aggregate features).
MIN_EVENTS_FOR_FIT = 100


class InsufficientDataError(ValueError):
    """Per-bin event count below ``MIN_EVENTS_FOR_FIT``."""


def fit_per_regime_composite(
    features: "np.ndarray",
    labels: "np.ndarray",
    bin_id: BinId,
    *,
    l2_penalty: float = 1.0,
    random_state: int,
) -> "PerRegimeCompositeFit":
    """Fit an L2-regularized logistic regression on events from ONE bin.

    Args:
        features: ``(n_events, n_features)`` float64 array. NaNs permitted
            in the Forman-Ricci column only; median imputation is applied
            internally (research.md §10).
        labels: ``(n_events,)`` bool array. True = fail event.
        bin_id: One of ``"B1".."B6"``. NOT ``None``, NOT ``"ALL"`` — the
            single-bin invariant is enforced here. Cross-bin pooling is
            forbidden by Constitution Principle III; use
            ``phi3geom.analysis.pooled_negative_control.fit`` for SC-003.
        l2_penalty: Strength of L2 regularization (sklearn ``C = 1 / l2_penalty``).
        random_state: Derived from
            ``seeds.seed_for_analysis("per_regime_composite:" + bin_id)``.

    Returns:
        ``PerRegimeCompositeFit`` with fitted coefficients, AUROC, and CI.

    Raises:
        ValueError: If ``bin_id`` is ``None`` or ``"ALL"`` or otherwise not
            one of the 6 bin enums.
        InsufficientDataError: If ``len(features) < MIN_EVENTS_FOR_FIT``.
        TypeError: If ``features.dtype`` is not float64.

    Note:
        T029 (this skeleton) raises ``NotImplementedError`` for the actual
        sklearn-backed fit. T044 fills in the body.
    """
    _validate_bin_id(bin_id)
    _validate_inputs(features, labels)

    raise NotImplementedError(
        "fit_per_regime_composite body is filled by T044 (US1). "
        "Skeleton at T029 validates inputs only."
    )


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


def _validate_inputs(features: "np.ndarray", labels: "np.ndarray") -> None:
    """Shape + dtype + NaN policy checks shared by skeleton and impl."""
    import numpy as np  # local: numpy is a runtime dep

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
