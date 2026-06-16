"""Spectral primitives: stable rank, top-k Grassmannian distance, spectral entropy.

All computations run in float64 (Constitution Principle IV). Float32 inputs
raise ``TypeError`` — the cache-boundary downcast to float32 is the
responsibility of ``phi3geom.storage.cache`` ONLY.

Correctness (Constitution Principle II): verified by analytic property
tests against closed-form values in float64 (rank-1 spectral entropy = 0,
identity stable rank = N, identity-aligned Grassmannian distance = 0, etc.).
Tests live in ``tests/unit/test_spectral_individual.py``.
"""

from __future__ import annotations

import numpy as np

# Tolerance used to clip degenerate singular values when forming the
# normalized squared-singular-value distribution for spectral_entropy.
_EPS = 1e-300


def _check_float64(matrix: np.ndarray, name: str = "matrix") -> None:
    """Reject anything that isn't a float64 numpy array (Principle IV)."""
    if not isinstance(matrix, np.ndarray):
        raise TypeError(
            f"{name} must be a numpy.ndarray; got {type(matrix).__name__}"
        )
    if matrix.dtype != np.float64:
        raise TypeError(
            f"{name} must be float64 (Constitution Principle IV); got {matrix.dtype}. "
            "The cache boundary downcasts to float32; the seam does not accept it."
        )
    if matrix.ndim != 2:
        raise ValueError(f"{name} must be 2D; got shape {matrix.shape}")


def stable_rank(matrix: np.ndarray) -> float:
    """Stable rank: ``‖M‖_F² / ‖M‖_2²``.

    Numerically robust to near-rank-deficient inputs. Always in
    ``[0, min(M.shape)]``.

    Args:
        matrix: 2D float64 array.

    Returns:
        Scalar stable rank, in float64.
    """
    _check_float64(matrix)
    # Frobenius norm squared = sum of squared singular values
    frob_sq = float(np.sum(matrix * matrix))
    # Spectral norm = largest singular value
    sigma_max = float(np.linalg.norm(matrix, ord=2))
    if sigma_max == 0.0:
        # Pathological all-zero matrix: convention 0.0 (no defined direction).
        return 0.0
    return frob_sq / (sigma_max * sigma_max)


def spectral_norm(matrix: np.ndarray) -> float:
    """Spectral norm ``‖M‖_2`` — the largest singular value σ_max.

    The magnitude that the scale-invariant features (stable rank, spectral
    entropy, Grassmannian) discard by construction. Always non-negative;
    ``0.0`` for the all-zero matrix.

    Args:
        matrix: 2D float64 array.

    Returns:
        Scalar σ_max, in float64.
    """
    _check_float64(matrix)
    return float(np.linalg.norm(matrix, ord=2))


def frobenius_norm(matrix: np.ndarray) -> float:
    """Frobenius norm ``‖M‖_F = √Σ σ_i²`` (= √Σ M_ij²).

    Args:
        matrix: 2D float64 array.

    Returns:
        Scalar Frobenius norm, in float64.
    """
    _check_float64(matrix)
    return float(np.linalg.norm(matrix, ord="fro"))


def nuclear_norm(matrix: np.ndarray) -> float:
    """Nuclear (trace) norm ``‖M‖_* = Σ σ_i`` — the sum of singular values.

    Args:
        matrix: 2D float64 array.

    Returns:
        Scalar nuclear norm, in float64.
    """
    _check_float64(matrix)
    return float(np.linalg.norm(matrix, ord="nuc"))


def spectral_entropy(matrix: np.ndarray) -> float:
    """Shannon entropy of the normalized squared-singular-value distribution.

    ``p_i = σ_i² / Σ_j σ_j²``; ``H = -Σ_i p_i log(p_i)``.

    Args:
        matrix: 2D float64 array.

    Returns:
        Non-negative scalar entropy in nats (natural log). Zero for
        rank-1 matrices; ``log(min(M.shape))`` for matrices with uniform
        singular values.
    """
    _check_float64(matrix)
    svals = np.linalg.svd(matrix, compute_uv=False)
    sq = svals * svals
    total = float(sq.sum())
    if total <= _EPS:
        return 0.0
    p = sq / total
    # mask near-zero entries to avoid log(0) NaN
    nonzero = p > _EPS
    return float(-np.sum(p[nonzero] * np.log(p[nonzero])))


def _top_k_left_subspace_projector(matrix: np.ndarray, k: int) -> np.ndarray:
    """Projector onto the top-k LEFT singular subspace of ``matrix``.

    For ``matrix.shape == (m, n)`` and ``k ≤ min(m, n)``, returns an
    ``(m, m)`` projector ``P = U[:, :k] @ U[:, :k].T``.
    """
    u, _, _ = np.linalg.svd(matrix, full_matrices=False)
    u_k = u[:, :k]
    return u_k @ u_k.T


def _identity_aligned_projector(d: int, k: int) -> np.ndarray:
    """Projector onto the first ``k`` canonical basis vectors in ``R^d``."""
    p = np.zeros((d, d), dtype=np.float64)
    for i in range(k):
        p[i, i] = 1.0
    return p


def top_k_grassmannian(
    matrix: np.ndarray,
    k: int,
    *,
    reference: np.ndarray | None = None,
) -> float:
    """Frobenius distance between top-k left-singular subspaces.

    ``||P_k(matrix) - P_k_ref||_F`` where:

    - ``P_k(matrix)`` = projector onto the top-k left-singular subspace
      of ``matrix``.
    - ``P_k_ref`` = if ``reference`` is ``None``, the identity-aligned
      projector onto the first ``k`` canonical basis vectors. If
      ``reference`` is a 2D float64 array, the projector onto the top-k
      left-singular subspace of ``reference``.

    Call sites:

    - Per-atomic-unit feature (``geometry.atomic_unit``): ``reference=None``
      → distance from the canonical axis-aligned subspace.
    - Crossbar pairwise (``lattice.crossbar``): ``reference=other_head``
      → distance between two heads' subspaces.

    Args:
        matrix: 2D float64 array.
        k: Top-k cutoff. Pinned to 8 for v1 study (``k_grass``).
        reference: Optional 2D float64 array with the same number of rows
            (left dimension) as ``matrix``. ``None`` → identity-aligned.

    Returns:
        Non-negative scalar Frobenius distance.
    """
    _check_float64(matrix)
    if k < 1:
        raise ValueError(f"k must be ≥ 1; got {k}")
    if k > min(matrix.shape):
        raise ValueError(
            f"k={k} exceeds min(matrix.shape)={min(matrix.shape)}"
        )

    p_matrix = _top_k_left_subspace_projector(matrix, k)

    if reference is None:
        d = matrix.shape[0]
        p_ref = _identity_aligned_projector(d, k)
    else:
        _check_float64(reference, name="reference")
        if reference.shape[0] != matrix.shape[0]:
            raise ValueError(
                f"reference left-dim {reference.shape[0]} does not match "
                f"matrix left-dim {matrix.shape[0]}"
            )
        if k > min(reference.shape):
            raise ValueError(
                f"k={k} exceeds min(reference.shape)={min(reference.shape)}"
            )
        p_ref = _top_k_left_subspace_projector(reference, k)

    diff = p_matrix - p_ref
    return float(np.linalg.norm(diff, ord="fro"))


def top_k_left_projector(matrix: np.ndarray, k: int) -> np.ndarray:
    """Projector onto the top-k left-singular subspace of ``matrix``.

    Public entry point for callers (e.g. the crossbar) that need to compute
    many pairwise Grassmannian distances among a set of matrices: compute
    each matrix's projector ONCE here, then call ``grassmannian_distance`` on
    pairs of projectors — avoiding the O(n²) re-SVD of ``top_k_grassmannian``.

    Returns an ``(m, m)`` float64 projector for an ``(m, n)`` input.
    """
    _check_float64(matrix)
    if k < 1:
        raise ValueError(f"k must be ≥ 1; got {k}")
    if k > min(matrix.shape):
        raise ValueError(f"k={k} exceeds min(matrix.shape)={min(matrix.shape)}")
    return _top_k_left_subspace_projector(matrix, k)


def grassmannian_distance(p1: np.ndarray, p2: np.ndarray) -> float:
    """Frobenius distance ``||p1 - p2||_F`` between two rank-k projectors.

    Equivalent to ``top_k_grassmannian(a, k, reference=b)`` when
    ``p1 = top_k_left_projector(a, k)`` and ``p2 = top_k_left_projector(b, k)``,
    but computed without re-running the SVDs.
    """
    return float(np.linalg.norm(p1 - p2, ord="fro"))
