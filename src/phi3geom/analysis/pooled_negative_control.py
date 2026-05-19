"""Pooled-across-bin logistic for the SC-003 negative-control demonstration.

This module is the **only** place in the analysis layer that fits a logistic
on events from multiple bins. ``phi3geom.analysis.composite`` MUST NOT
import from this module (Constitution Principle III at the file-system
level).

Its output is labeled ``PooledNegativeControl`` (a distinct dataclass from
``PerRegimeCompositeFit``) so it is type-distinguishable downstream in
``reporting/writeup.py``.

T029 (this skeleton) raises ``NotImplementedError`` for the actual fit;
T069 (US4) fills in the body.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

    from phi3geom.analysis.types import PooledNegativeControl


def fit(
    features: "np.ndarray",
    labels: "np.ndarray",
    *,
    l2_penalty: float = 1.0,
    random_state: int,
) -> "PooledNegativeControl":
    """Fit an L2-regularized logistic on events POOLED across all 6 bins.

    Args:
        features: ``(n_events, n_features)`` float64 array, pooled across
            bins. Caller is responsible for providing pooled data.
        labels: ``(n_events,)`` bool array.
        l2_penalty: L2 strength.
        random_state: Derived from
            ``seeds.seed_for_analysis("pooled_negative_control")``.

    Returns:
        ``PooledNegativeControl`` (distinct dataclass from
        ``PerRegimeCompositeFit``).

    Raises:
        ValueError: On shape mismatches.
        TypeError: If ``features.dtype`` is not float64.

    Note:
        T029 raises NotImplementedError. T069 (US4) fills in the body.
    """
    import numpy as np  # local: runtime dep

    if features.ndim != 2:
        raise ValueError(f"features must be 2D; got shape {features.shape}")
    if features.dtype != np.float64:
        raise TypeError(
            f"features must be float64 (Constitution Principle IV); got {features.dtype}."
        )
    if labels.ndim != 1 or labels.shape[0] != features.shape[0]:
        raise ValueError(
            f"labels shape mismatch: features {features.shape[0]} events, "
            f"labels {labels.shape}"
        )

    raise NotImplementedError(
        "pooled_negative_control.fit body is filled by T069 (US4). "
        "Skeleton at T029 validates inputs only."
    )
