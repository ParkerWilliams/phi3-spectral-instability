"""Dataclass schemas for analysis outputs (per data-model.md).

These dataclasses are returned by ``composite.fit_per_regime_composite``,
``fda.fit_functional_logistic``, and ``pooled_negative_control.fit``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from phi3geom.dataset.types import BinId


@dataclass(frozen=True, slots=True)
class PerRegimeCompositeFit:
    """A logistic regression model fit independently within one bin (FR-008)."""

    bin_id: BinId
    feature_names: tuple[str, ...]
    coefficients: np.ndarray  # float64, shape (n_features,)
    intercept: float
    auroc: float
    auroc_ci_lower: float
    auroc_ci_upper: float
    n_events_train: int
    n_events_held_out: int


@dataclass(frozen=True, slots=True)
class FunctionalLogisticResult:
    """A functional logistic regression on 32-point spine curves (FR-009)."""

    bin_id: BinId
    edge_type: str  # "qkt_grassmannian" | "avwo_grassmannian"
    n_fpcs: int
    fpc_variance_explained: np.ndarray  # shape (n_fpcs,)
    beta_function: np.ndarray  # float64, shape (32,)
    beta_ci_lower: np.ndarray  # shape (32,)
    beta_ci_upper: np.ndarray  # shape (32,)
    discriminative_depth_intervals: list[tuple[int, int]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PooledNegativeControl:
    """Pooled-across-bin logistic for the SC-003 negative-control demonstration.

    Constructed ONLY by ``analysis.pooled_negative_control.fit``. Never
    returned by ``analysis.composite.fit_per_regime_composite``.
    """

    feature_names: tuple[str, ...]
    coefficients: np.ndarray  # float64, shape (n_features,)
    intercept: float
    auroc: float
    auroc_ci_lower: float
    auroc_ci_upper: float
    n_events_train: int
    n_events_held_out: int
