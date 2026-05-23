"""Tests for ``phi3geom.lattice.crossbar`` (FR-006)."""

from __future__ import annotations

import numpy as np
import pytest

from phi3geom.lattice.crossbar import (
    N_EDGES_DEFAULT,
    N_HEADS_DEFAULT,
    compute_pairwise_grassmannian,
    edge_index_pairs,
    edges_to_dense,
)


def test_edge_count_32_choose_2_is_496() -> None:
    assert N_EDGES_DEFAULT == 496
    assert len(edge_index_pairs(N_HEADS_DEFAULT)) == 496


def test_edge_index_pairs_lex_order() -> None:
    pairs = edge_index_pairs(4)
    # 4 heads → 6 edges, in lex (i < j) order
    expected = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
    assert pairs == expected


def test_pairwise_grassmannian_self_distances_zero() -> None:
    """Identical heads produce distance 0 on the diagonal of edges_to_dense."""
    rng = np.random.default_rng(0)
    base = rng.standard_normal((8, 8))  # one head's matrix (d_head, d_head), square
    heads = np.stack([base, base, base, base], axis=0)  # 4 identical heads
    distances = compute_pairwise_grassmannian(heads, k_grass=2)
    # All pairwise distances should be ~0
    assert np.allclose(distances, 0.0, atol=1e-10)


def test_pairwise_grassmannian_symmetric_after_densification() -> None:
    rng = np.random.default_rng(1)
    heads = rng.standard_normal((4, 8, 8))
    distances = compute_pairwise_grassmannian(heads, k_grass=2)
    dense = edges_to_dense(distances, n_heads=4)
    assert np.allclose(dense, dense.T)
    assert np.allclose(np.diag(dense), 0.0)


def test_pairwise_grassmannian_rejects_float32() -> None:
    h = np.zeros((4, 8, 8), dtype=np.float32)
    with pytest.raises(TypeError, match="float64"):
        compute_pairwise_grassmannian(h)


def test_pairwise_grassmannian_rejects_wrong_dims() -> None:
    h = np.zeros((4, 8), dtype=np.float64)
    with pytest.raises(ValueError, match="\\(n_heads"):
        compute_pairwise_grassmannian(h)


def test_pairwise_grassmannian_rejects_non_square_heads() -> None:
    h = np.zeros((4, 8, 6), dtype=np.float64)
    with pytest.raises(ValueError, match="square"):
        compute_pairwise_grassmannian(h)


def test_full_32_heads_shape() -> None:
    """A realistic 32-head call returns a 496-vector."""
    rng = np.random.default_rng(2)
    heads = rng.standard_normal((32, 96, 96))  # Phi-3-mini scale
    # Use small k_grass=2 to keep the test fast; the production path uses 8
    distances = compute_pairwise_grassmannian(heads, k_grass=2)
    assert distances.shape == (496,)
    assert distances.dtype == np.float64


def test_cached_projector_path_matches_per_pair_top_k_grassmannian() -> None:
    """The optimized cached-projector path must be bit-identical to the naive
    per-pair ``top_k_grassmannian`` it replaced (same numbers, less work)."""
    from phi3geom.geometry.spectral import top_k_grassmannian

    rng = np.random.default_rng(5)
    n_heads = 6
    heads = rng.standard_normal((n_heads, 12, 12))
    k = 4

    fast = compute_pairwise_grassmannian(heads, k_grass=k)
    naive = np.array([
        top_k_grassmannian(heads[i], k=k, reference=heads[j])
        for (i, j) in edge_index_pairs(n_heads)
    ])
    # Bit-identical: same SVD, same projectors, same Frobenius norm.
    np.testing.assert_array_equal(fast, naive)
