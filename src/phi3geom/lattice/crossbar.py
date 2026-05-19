"""Pairwise head-head Grassmannian distances at fixed (token, layer) (FR-006).

For 32 heads, this is ``(32 choose 2) = 496`` edges. Two parallel
head-graphs exist per (token, layer): one with QKᵀ-Grassmannian edge
weights, one with AVWO-Grassmannian edge weights. They are analyzed
independently per Spec FR-006 and Constitution Principle III's spirit.

Edge ordering: lex ``(i, j)`` with ``i < j`` — i.e., ``(0,1), (0,2), …,
(0,31), (1,2), …, (30,31)``. This is data-model.md's canonical order.
"""

from __future__ import annotations

import numpy as np

from phi3geom.geometry.spectral import top_k_grassmannian

N_HEADS_DEFAULT = 32
N_EDGES_DEFAULT = (N_HEADS_DEFAULT * (N_HEADS_DEFAULT - 1)) // 2  # 496


def edge_index_pairs(n_heads: int = N_HEADS_DEFAULT) -> list[tuple[int, int]]:
    """Return the canonical edge ordering: lex ``(i, j)`` for ``i < j``."""
    return [(i, j) for i in range(n_heads) for j in range(i + 1, n_heads)]


def compute_pairwise_grassmannian(
    head_matrices: np.ndarray,
    *,
    k_grass: int = 8,
) -> np.ndarray:
    """Compute pairwise Grassmannian distances among ``n_heads`` head
    matrices at fixed (token, layer).

    Args:
        head_matrices: ``(n_heads, d_head, d_head)`` float64 array. Each
            ``head_matrices[h]`` is one head's QKᵀ or AVWO matrix.
        k_grass: Subspace dimension. Pinned to 8 for v1.

    Returns:
        ``(n_edges,)`` float64 array, where ``n_edges = n_heads * (n_heads - 1) // 2``.
        Entry ``e`` corresponds to the edge pair ``edge_index_pairs()[e]``.

    The same primitive is called for both QKᵀ and AVWO head matrices to
    produce the two parallel head-graphs.
    """
    if head_matrices.dtype != np.float64:
        raise TypeError(
            f"head_matrices must be float64 (Principle IV); got {head_matrices.dtype}"
        )
    if head_matrices.ndim != 3:
        raise ValueError(
            f"head_matrices must be (n_heads, d_head, d_head); got shape {head_matrices.shape}"
        )
    n_heads, d_head, d_head_2 = head_matrices.shape
    if d_head != d_head_2:
        raise ValueError(
            f"head matrices must be square; got d_head={d_head}, d_head_2={d_head_2}"
        )

    pairs = edge_index_pairs(n_heads)
    distances = np.empty(len(pairs), dtype=np.float64)
    for e, (i, j) in enumerate(pairs):
        distances[e] = top_k_grassmannian(
            head_matrices[i], k=k_grass, reference=head_matrices[j]
        )
    return distances


def edges_to_dense(
    distances: np.ndarray, n_heads: int = N_HEADS_DEFAULT
) -> np.ndarray:
    """Convert a flat ``(n_edges,)`` edges array to a dense
    ``(n_heads, n_heads)`` symmetric distance matrix with zero diagonal.
    """
    dense = np.zeros((n_heads, n_heads), dtype=distances.dtype)
    for e, (i, j) in enumerate(edge_index_pairs(n_heads)):
        dense[i, j] = distances[e]
        dense[j, i] = distances[e]
    return dense
