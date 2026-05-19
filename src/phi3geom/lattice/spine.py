"""32-point spine curves over the depth axis (FR-007).

For each token, produce a 32-point curve indexed by raw layer index
(NO phase bucketing). Each point is a 4-aggregate of the head-graph at
that depth: ``[mean_grassmannian, spectral_gap, mean_forman_ricci,
modularity]``. The unit of functional data analysis downstream.
"""

from __future__ import annotations

import math

import numpy as np

from phi3geom.lattice.crossbar import edges_to_dense

N_AGGREGATES = 4
AGGREGATE_NAMES: tuple[str, ...] = (
    "mean_grassmannian",
    "spectral_gap",
    "mean_forman_ricci",
    "modularity",
)


def _mean_grassmannian(edges: np.ndarray) -> float:
    """Arithmetic mean over the 496 edge weights (Grassmannian distances)."""
    return float(edges.mean())


def _spectral_gap(edges: np.ndarray, n_heads: int) -> float:
    """Spectral gap of the head-graph treated as a weighted Laplacian.

    Specifically: the second-smallest eigenvalue of the (normalized)
    Laplacian of the dense ``(n_heads, n_heads)`` distance matrix,
    interpreted as edge weights. A larger gap → better head-cluster
    separation.
    """
    dense = edges_to_dense(edges, n_heads=n_heads)
    # Symmetric Laplacian: L = D - W, where D is the degree matrix of W.
    # Use W = 1 / (1 + dense) so that small Grassmannian distance → strong
    # connection (heads are similar). This avoids zero-weight edges making L
    # degenerate.
    w = 1.0 / (1.0 + dense)
    np.fill_diagonal(w, 0.0)
    deg = w.sum(axis=1)
    laplacian = np.diag(deg) - w
    eigvals = np.linalg.eigvalsh(laplacian)
    eigvals.sort()
    # Smallest is 0 (constant eigenvector); spectral gap = next-smallest.
    return float(eigvals[1]) if len(eigvals) > 1 else 0.0


def _mean_forman_ricci(per_head_atomic_features: np.ndarray) -> float:
    """Mean Forman-Ricci across the 32 atomic units at this depth.

    Uses NaN-aware averaging (per research.md §10): NaN entries are
    excluded, the count of valid entries is implicit in the divisor.

    Args:
        per_head_atomic_features: ``(n_heads, 7)`` array of per-head atomic
            features. The Forman-Ricci slot is index 6.

    Returns:
        Mean of finite Ricci values; ``NaN`` if all are NaN.
    """
    ricci_values = per_head_atomic_features[:, 6]
    valid = ~np.isnan(ricci_values)
    if not valid.any():
        return math.nan
    return float(ricci_values[valid].mean())


def _modularity(edges: np.ndarray, n_heads: int) -> float:
    """A simple modularity proxy: the std-dev of edge weights normalized by
    the mean.

    Higher modularity → more cluster structure (some pairs much closer than
    others). We use std/mean rather than a community-detection-based
    modularity to keep the computation cheap and deterministic at the
    spine-aggregate granularity.
    """
    _ = n_heads
    if edges.size == 0:
        return 0.0
    mu = float(edges.mean())
    if mu == 0.0:
        return 0.0
    sigma = float(edges.std())
    return sigma / mu


def compute_spine_curve(
    head_graph_edges_per_layer: np.ndarray,
    atomic_features_per_layer: np.ndarray,
    *,
    n_heads: int = 32,
) -> np.ndarray:
    """Build the 32-point spine curve at one token.

    Args:
        head_graph_edges_per_layer: ``(n_layers, n_edges)`` float64 array.
            Each row is the 496-edge head-graph for one layer.
        atomic_features_per_layer: ``(n_layers, n_heads, 7)`` float64 array.
            Per-(layer, head) atomic features at this token; index 6 is
            Forman-Ricci.
        n_heads: 32 for Phi-3-mini.

    Returns:
        ``(n_layers, 4) float64`` array. Aggregate order matches
        ``AGGREGATE_NAMES``.
    """
    if head_graph_edges_per_layer.dtype != np.float64:
        raise TypeError(
            "head_graph_edges_per_layer must be float64 (Principle IV); "
            f"got {head_graph_edges_per_layer.dtype}"
        )
    if atomic_features_per_layer.dtype != np.float64:
        raise TypeError(
            "atomic_features_per_layer must be float64 (Principle IV); "
            f"got {atomic_features_per_layer.dtype}"
        )

    n_layers = head_graph_edges_per_layer.shape[0]
    if atomic_features_per_layer.shape[0] != n_layers:
        raise ValueError(
            f"layer-axis disagreement: edges {n_layers} vs "
            f"atomic {atomic_features_per_layer.shape[0]}"
        )

    spine = np.empty((n_layers, N_AGGREGATES), dtype=np.float64)
    for ell in range(n_layers):
        edges = head_graph_edges_per_layer[ell]
        atomics = atomic_features_per_layer[ell]
        spine[ell, 0] = _mean_grassmannian(edges)
        spine[ell, 1] = _spectral_gap(edges, n_heads=n_heads)
        spine[ell, 2] = _mean_forman_ricci(atomics)
        spine[ell, 3] = _modularity(edges, n_heads=n_heads)
    return spine
