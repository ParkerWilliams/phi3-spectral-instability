"""Analytic property tests for the inter-head configuration primitives (SP-0, §5.6)."""

import numpy as np
import pytest

from phi3geom.geometry.interhead import (
    CELL_FEATURES,
    cell_summary,
    effective_rank,
    evidence_coverage,
    fiedler_value,
    overlap_matrix,
    pairwise_dispersion,
    top_eigenvalue,
)


def _dist(T, idx):
    """One-hot distribution over T tokens at index idx."""
    v = np.zeros(T, dtype=np.float64)
    v[idx] = 1.0
    return v


def test_identical_heads_zero_dispersion_rank_one():
    rng = np.random.default_rng(0)
    p = rng.random(20)
    p /= p.sum()
    A = np.tile(p, (8, 1))  # 8 identical heads
    assert pairwise_dispersion(A, metric="js") == pytest.approx(0.0, abs=1e-9)
    assert pairwise_dispersion(A, metric="hellinger") == pytest.approx(0.0, abs=1e-9)
    M = overlap_matrix(A)
    assert effective_rank(M) == pytest.approx(1.0, abs=1e-6)  # all-ones -> rank 1
    assert top_eigenvalue(M) == pytest.approx(8.0, abs=1e-6)  # largest eig of J_H = H


def test_disjoint_support_heads_max_dispersion_identity_overlap():
    H, T = 6, 6
    A = np.stack([_dist(T, i) for i in range(H)])  # each head on a distinct token
    assert pairwise_dispersion(A, metric="js") == pytest.approx(1.0, abs=1e-9)
    assert pairwise_dispersion(A, metric="hellinger") == pytest.approx(1.0, abs=1e-9)
    M = overlap_matrix(A)
    assert np.allclose(M, np.eye(H))
    assert effective_rank(M) == pytest.approx(H, abs=1e-6)  # identity -> rank H
    assert fiedler_value(M) == pytest.approx(0.0, abs=1e-9)  # disconnected graph
    assert top_eigenvalue(M) == pytest.approx(1.0, abs=1e-6)


def test_two_groups_effective_rank_two():
    T = 10
    p = _dist(T, 0)
    q = _dist(T, 5)  # disjoint from p
    A = np.stack([p, p, q, q])  # two groups of identical heads
    M = overlap_matrix(A)
    assert effective_rank(M) == pytest.approx(2.0, abs=1e-6)
    # mean pairwise JS: within-group 0 (x2 pairs), between-group 1 (x4 pairs) -> 4/6
    assert pairwise_dispersion(A, metric="js") == pytest.approx(4.0 / 6.0, abs=1e-9)


def test_evidence_coverage():
    H, T = 4, 10
    on = np.stack([_dist(T, 3) for _ in range(H)])  # all mass on token 3
    assert evidence_coverage(on, (3, 3)) == pytest.approx(1.0)
    assert evidence_coverage(on, (5, 7)) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        evidence_coverage(on, (8, 12))  # out of range


def test_cell_summary_shape_and_order():
    rng = np.random.default_rng(1)
    A = rng.random((5, 12))
    A /= A.sum(axis=1, keepdims=True)
    s = cell_summary(A, evidence_span=(2, 4))
    assert tuple(k for k in s if k in CELL_FEATURES) == CELL_FEATURES
    assert "evidence_coverage" in s
    assert cell_summary(A).keys() == set(CELL_FEATURES)  # no span -> agnostic only


def test_single_head_is_degenerate_not_a_crash():
    A = np.ones((1, 8), dtype=np.float64) / 8.0
    assert pairwise_dispersion(A) == 0.0
    assert fiedler_value(overlap_matrix(A)) == 0.0


def test_rejects_float32():
    with pytest.raises(TypeError):
        pairwise_dispersion(np.ones((3, 4), dtype=np.float32) / 4.0)
