"""Tests for ``phi3geom.lattice.spine`` (FR-007)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from phi3geom.lattice.spine import (
    AGGREGATE_NAMES,
    N_AGGREGATES,
    compute_spine_curve,
)


def test_aggregate_count_and_order() -> None:
    assert N_AGGREGATES == 4
    assert AGGREGATE_NAMES == (
        "mean_grassmannian",
        "spectral_gap",
        "mean_forman_ricci",
        "modularity",
    )


def test_compute_spine_curve_shape() -> None:
    rng = np.random.default_rng(0)
    edges = np.abs(rng.standard_normal((32, 496)))  # (n_layers, n_edges)
    atomics = rng.standard_normal((32, 32, 7))
    atomics[:, :, 6] = np.nan  # US1 baseline: Ricci all NaN
    spine = compute_spine_curve(
        edges.astype(np.float64), atomics.astype(np.float64)
    )
    assert spine.shape == (32, 4)
    assert spine.dtype == np.float64


def test_spine_mean_ricci_is_nan_when_all_nan() -> None:
    rng = np.random.default_rng(1)
    edges = np.abs(rng.standard_normal((4, 6)))
    atomics = np.zeros((4, 4, 7), dtype=np.float64)
    atomics[:, :, 6] = np.nan
    spine = compute_spine_curve(edges.astype(np.float64), atomics, n_heads=4)
    assert all(math.isnan(spine[ell, 2]) for ell in range(4))


def test_spine_mean_ricci_finite_when_some_valid() -> None:
    edges = np.abs(np.random.default_rng(2).standard_normal((1, 6))).astype(np.float64)
    atomics = np.zeros((1, 4, 7), dtype=np.float64)
    atomics[0, :, 6] = [1.0, 2.0, np.nan, 4.0]
    spine = compute_spine_curve(edges, atomics, n_heads=4)
    assert spine[0, 2] == pytest.approx((1.0 + 2.0 + 4.0) / 3.0, rel=1e-9)


def test_spine_uses_32_raw_layers_not_phase_buckets() -> None:
    """Spec FR-007: 32-point curve over all 32 raw layers without phase
    bucketing (Principle III on the layer axis stays no-pooling for v1)."""
    edges = np.abs(np.random.default_rng(3).standard_normal((32, 496))).astype(np.float64)
    atomics = np.random.default_rng(3).standard_normal((32, 32, 7)).astype(np.float64)
    spine = compute_spine_curve(edges, atomics)
    # 32 rows, not 3 (early/mid/late) or any other coarsening
    assert spine.shape[0] == 32


def test_spine_rejects_float32_inputs() -> None:
    edges = np.zeros((4, 6), dtype=np.float32)
    atomics = np.zeros((4, 4, 7), dtype=np.float64)
    with pytest.raises(TypeError, match="float64"):
        compute_spine_curve(edges, atomics, n_heads=4)

    edges = np.zeros((4, 6), dtype=np.float64)
    atomics_32 = np.zeros((4, 4, 7), dtype=np.float32)
    with pytest.raises(TypeError, match="float64"):
        compute_spine_curve(edges, atomics_32, n_heads=4)


def test_spine_layer_axis_disagreement_raises() -> None:
    edges = np.zeros((4, 6), dtype=np.float64)
    atomics = np.zeros((5, 4, 7), dtype=np.float64)
    with pytest.raises(ValueError, match="layer-axis"):
        compute_spine_curve(edges, atomics, n_heads=4)
