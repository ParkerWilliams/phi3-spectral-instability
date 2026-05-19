"""Forman-Ricci curvature on the per-(t, ℓ, h) attention graph.

Forman-Ricci is the **graph-defined** scalar feature in the atomic-unit
vector. The attention graph is derived from ``softmax(QKᵀ/√d_head + mask)``
sparsified to the top-``k_attn`` outgoing edges per node (research.md §5,
§10). For nodes that end up isolated after sparsification the convention
is ``NaN`` (research.md §10) — the cache layer applies median imputation
with an indicator feature downstream.

Parity oracle: ``GraphRicciCurvature.FormanRicci``. Tests verify
``max_abs_diff ≤ 1e-10`` on 3 explicit reference graphs (K₃, C₄, K₁,₄) and
on 100 random 16-node graphs with edge density in [0.1, 0.8].
"""

from __future__ import annotations

import math

import networkx as nx


def build_attention_graph(
    attention: "np.ndarray",  # noqa: F821 - forward ref to numpy
    *,
    k_attn: int,
) -> nx.Graph:
    """Construct the per-(t, ℓ, h) attention graph from a square attention
    matrix, sparsified to the top-``k_attn`` outgoing edges per node.

    Args:
        attention: ``(T, T)`` float64 attention matrix (post-softmax + mask).
            Row i is the distribution of attention FROM token i.
        k_attn: Top-``k`` cutoff per node.

    Returns:
        An undirected ``networkx.Graph`` with ``T`` nodes and edges
        weighted by the symmetric average attention weight
        ``(A[i, j] + A[j, i]) / 2`` for each retained edge.
    """
    import numpy as np

    if attention.dtype != np.float64:
        raise TypeError(
            f"attention must be float64 (Principle IV); got {attention.dtype}"
        )
    if attention.ndim != 2 or attention.shape[0] != attention.shape[1]:
        raise ValueError(f"attention must be a square 2D array; got {attention.shape}")

    n = attention.shape[0]
    g: nx.Graph = nx.Graph()
    g.add_nodes_from(range(n))

    # For each row, keep the top-k_attn out-edges (excluding self-loops).
    eff_k = min(k_attn, n - 1)
    for i in range(n):
        row = attention[i].copy()
        row[i] = -np.inf  # exclude self-loop
        # argpartition for top-k; then filter strictly positive weights only
        top_idx = np.argpartition(row, -eff_k)[-eff_k:]
        for j in top_idx:
            j_int = int(j)
            w = float((attention[i, j_int] + attention[j_int, i]) * 0.5)
            if w <= 0.0:
                continue
            if g.has_edge(i, j_int):
                # If already added from the other direction, keep the max
                g[i][j_int]["weight"] = max(g[i][j_int]["weight"], w)
            else:
                g.add_edge(i, j_int, weight=w)
    return g


def forman_ricci_token(graph: nx.Graph) -> float:
    """Mean Forman-Ricci curvature over edges of ``graph``.

    Convention for degenerate inputs:

    - If the graph has any isolated node (``degree == 0``), return
      ``float('nan')`` (research.md §10).
    - If the graph has zero edges (everything isolated), return
      ``float('nan')`` — same convention; nothing to average.
    - Otherwise, returns the mean of per-edge Forman curvature.

    Args:
        graph: Output of ``build_attention_graph``, or any
            ``networkx.Graph`` with edge weight attribute ``"weight"``.

    Returns:
        Scalar mean Forman-Ricci, in float (Python float, not numpy float64).
    """
    n_nodes = graph.number_of_nodes()
    if n_nodes == 0:
        return float("nan")
    # Detect isolated nodes (convention NaN per research.md §10)
    if any(graph.degree(node) == 0 for node in graph.nodes):
        return float("nan")
    if graph.number_of_edges() == 0:
        return float("nan")

    # Use GraphRicciCurvature as both production and parity oracle (research.md §4).
    # This means the production code IS the reference until a profiling pass
    # (T074) potentially replaces it with a hand-coded primitive.
    from GraphRicciCurvature.FormanRicci import FormanRicci

    frc = FormanRicci(graph.copy())  # FormanRicci mutates in-place
    frc.compute_ricci_curvature()
    g = frc.G

    curvatures = [
        float(data["formanCurvature"])
        for _, _, data in g.edges(data=True)
        if "formanCurvature" in data
    ]
    if not curvatures:
        return float("nan")
    return math.fsum(curvatures) / len(curvatures)
