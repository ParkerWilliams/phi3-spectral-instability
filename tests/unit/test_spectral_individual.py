"""Per-primitive correctness tests for the spectral seam.

These are deterministic property tests (rank-1 case, identity case,
isotropic case) that don't require the DCSBM reference. They run on any
machine with numpy installed.

The 1e-7-vs-DCSBM parity tests live in ``test_spectral_parity.py``.
"""

from __future__ import annotations

import numpy as np
import pytest

from phi3geom.geometry.spectral import (
    spectral_entropy,
    stable_rank,
    top_k_grassmannian,
)


# ---------------------------------------------------------------------------
# Float64-only seam (Constitution Principle IV)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fn", [stable_rank, spectral_entropy])
def test_rejects_float32_input(fn) -> None:
    m32 = np.eye(8, dtype=np.float32)
    with pytest.raises(TypeError, match="float64"):
        fn(m32)


def test_top_k_grassmannian_rejects_float32() -> None:
    m32 = np.eye(8, dtype=np.float32)
    with pytest.raises(TypeError, match="float64"):
        top_k_grassmannian(m32, k=4)


def test_rejects_non_ndarray() -> None:
    with pytest.raises(TypeError, match="numpy.ndarray"):
        stable_rank([[1.0, 0.0], [0.0, 1.0]])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# stable_rank
# ---------------------------------------------------------------------------

def test_stable_rank_identity_is_dim() -> None:
    for n in (4, 16, 96):
        m = np.eye(n, dtype=np.float64)
        assert stable_rank(m) == pytest.approx(float(n), abs=1e-9)


def test_stable_rank_rank_one_is_one() -> None:
    v = np.array([3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0], dtype=np.float64)
    m = np.outer(v, v)  # rank-1
    assert stable_rank(m) == pytest.approx(1.0, abs=1e-9)


def test_stable_rank_zero_matrix() -> None:
    m = np.zeros((8, 8), dtype=np.float64)
    assert stable_rank(m) == 0.0


def test_stable_rank_scales_invariant_to_uniform_scaling() -> None:
    rng = np.random.default_rng(0)
    m = rng.standard_normal((16, 16))
    sr1 = stable_rank(m)
    sr2 = stable_rank(10.0 * m)
    assert sr1 == pytest.approx(sr2, rel=1e-12)


def test_stable_rank_bounded_by_min_shape() -> None:
    rng = np.random.default_rng(1)
    for shape in [(4, 4), (8, 16), (16, 8), (96, 96)]:
        m = rng.standard_normal(shape)
        sr = stable_rank(m)
        assert 0.0 < sr <= float(min(shape)) + 1e-9


# ---------------------------------------------------------------------------
# spectral_entropy
# ---------------------------------------------------------------------------

def test_spectral_entropy_rank_one_is_zero() -> None:
    v = np.arange(8.0)
    m = np.outer(v, v)
    assert spectral_entropy(m) == pytest.approx(0.0, abs=1e-9)


def test_spectral_entropy_uniform_singular_values_is_log_n() -> None:
    # Identity has all singular values = 1; entropy = log(n).
    for n in (4, 8, 16):
        m = np.eye(n, dtype=np.float64)
        assert spectral_entropy(m) == pytest.approx(np.log(n), abs=1e-9)


def test_spectral_entropy_non_negative() -> None:
    rng = np.random.default_rng(2)
    for _ in range(10):
        m = rng.standard_normal((12, 12))
        assert spectral_entropy(m) >= 0.0


def test_spectral_entropy_zero_matrix() -> None:
    assert spectral_entropy(np.zeros((4, 4), dtype=np.float64)) == 0.0


# ---------------------------------------------------------------------------
# top_k_grassmannian
# ---------------------------------------------------------------------------

def test_grassmannian_identity_vs_identity_aligned_is_zero() -> None:
    # The identity matrix's top-k left-singular subspace IS the first k
    # canonical basis vectors → distance 0.
    m = np.eye(16, dtype=np.float64)
    for k in (1, 4, 8):
        assert top_k_grassmannian(m, k) == pytest.approx(0.0, abs=1e-10)


def test_grassmannian_same_matrix_against_itself_is_zero() -> None:
    rng = np.random.default_rng(3)
    m = rng.standard_normal((16, 16))
    for k in (1, 4, 8):
        d = top_k_grassmannian(m, k, reference=m)
        assert d == pytest.approx(0.0, abs=1e-10)


def test_grassmannian_symmetric_under_argument_swap() -> None:
    rng = np.random.default_rng(4)
    a = rng.standard_normal((16, 16))
    b = rng.standard_normal((16, 16))
    d_ab = top_k_grassmannian(a, 6, reference=b)
    d_ba = top_k_grassmannian(b, 6, reference=a)
    assert d_ab == pytest.approx(d_ba, rel=1e-10)


def test_grassmannian_rejects_invalid_k() -> None:
    m = np.eye(8, dtype=np.float64)
    with pytest.raises(ValueError, match="k must be"):
        top_k_grassmannian(m, k=0)
    with pytest.raises(ValueError, match="exceeds"):
        top_k_grassmannian(m, k=9)


def test_grassmannian_reference_shape_mismatch_raises() -> None:
    a = np.eye(8, dtype=np.float64)
    b = np.eye(16, dtype=np.float64)
    with pytest.raises(ValueError, match="left-dim"):
        top_k_grassmannian(a, k=4, reference=b)
