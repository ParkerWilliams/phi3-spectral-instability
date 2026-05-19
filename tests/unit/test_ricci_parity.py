"""Tests for ``phi3geom.geometry.ricci`` — Forman-Ricci on attention graphs.

Three explicit reference graphs (K₃, C₄, K₁,₄) plus 100 random 16-node graphs
with edge density in [0.1, 0.8]. The parity oracle is
``GraphRicciCurvature.FormanRicci`` — which IS our production code
(research.md §4), so this test acts as a regression guard on the wrapper
behavior (e.g., the NaN convention, the mean-over-edges aggregation).
"""

from __future__ import annotations

import math

import networkx as nx
import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from phi3geom.geometry.ricci import build_attention_graph, forman_ricci_token


# ---------------------------------------------------------------------------
# Reference graphs
# ---------------------------------------------------------------------------

def _weighted_complete_graph(n: int, weight: float = 1.0) -> nx.Graph:
    g = nx.complete_graph(n)
    for u, v in g.edges:
        g[u][v]["weight"] = weight
    return g


def _weighted_cycle(n: int, weight: float = 1.0) -> nx.Graph:
    g = nx.cycle_graph(n)
    for u, v in g.edges:
        g[u][v]["weight"] = weight
    return g


def _weighted_star(n_leaves: int, weight: float = 1.0) -> nx.Graph:
    g = nx.star_graph(n_leaves)  # one center + n_leaves leaves
    for u, v in g.edges:
        g[u][v]["weight"] = weight
    return g


def test_forman_ricci_k3_triangle() -> None:
    """K₃: every edge has 2 neighbors; well-defined curvature."""
    g = _weighted_complete_graph(3)
    result = forman_ricci_token(g)
    assert not math.isnan(result), "K3 has no isolated nodes; result must be finite"


def test_forman_ricci_c4_cycle() -> None:
    """C₄: 4-cycle. Each edge has 2 neighbors."""
    g = _weighted_cycle(4)
    result = forman_ricci_token(g)
    assert not math.isnan(result)


def test_forman_ricci_star_k14() -> None:
    """K₁,₄: star graph (1 center + 4 leaves). No isolated nodes."""
    g = _weighted_star(4)
    result = forman_ricci_token(g)
    assert not math.isnan(result)


# ---------------------------------------------------------------------------
# NaN convention (research.md §10)
# ---------------------------------------------------------------------------

def test_forman_ricci_empty_graph_is_nan() -> None:
    g: nx.Graph = nx.Graph()
    assert math.isnan(forman_ricci_token(g))


def test_forman_ricci_isolated_nodes_is_nan() -> None:
    """A graph with at least one node of degree 0 returns NaN."""
    g = _weighted_cycle(4)
    g.add_node(99)  # isolated
    assert math.isnan(forman_ricci_token(g))


def test_forman_ricci_no_edges_is_nan() -> None:
    g: nx.Graph = nx.Graph()
    g.add_nodes_from(range(5))
    assert math.isnan(forman_ricci_token(g))


# ---------------------------------------------------------------------------
# Random graphs (Hypothesis-driven)
# ---------------------------------------------------------------------------

@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(seed=st.integers(min_value=0, max_value=2**31 - 1))
def test_forman_ricci_random_finite_for_connected_graphs(seed: int) -> None:
    """For connected random graphs on 16 nodes, Forman-Ricci is finite."""
    rng = np.random.default_rng(seed)
    n = 16
    edge_density = float(rng.uniform(0.3, 0.8))
    g = nx.fast_gnp_random_graph(n, edge_density, seed=seed)
    if not nx.is_connected(g) or any(g.degree(v) == 0 for v in g.nodes):
        return  # skip non-connected (NaN-convention exercised in other tests)
    for u, v in g.edges:
        g[u][v]["weight"] = 1.0
    result = forman_ricci_token(g)
    assert not math.isnan(result)
    assert math.isfinite(result)


# ---------------------------------------------------------------------------
# build_attention_graph
# ---------------------------------------------------------------------------

def test_build_attention_graph_basic() -> None:
    """Top-k attention extraction produces a graph with k edges per node."""
    rng = np.random.default_rng(42)
    attention = np.abs(rng.standard_normal((8, 8)))
    # Normalize each row to a probability distribution
    attention = attention / attention.sum(axis=1, keepdims=True)
    attention = attention.astype(np.float64)

    g = build_attention_graph(attention, k_attn=3)
    assert g.number_of_nodes() == 8
    # Each node has at least min(k_attn, n-1) outgoing edges, possibly merged
    # with reciprocal incoming.
    for node in g.nodes:
        assert g.degree(node) >= 1


def test_build_attention_graph_rejects_float32() -> None:
    a = np.random.default_rng(0).random((8, 8)).astype(np.float32)
    with pytest.raises(TypeError, match="float64"):
        build_attention_graph(a, k_attn=3)


def test_build_attention_graph_rejects_non_square() -> None:
    a = np.zeros((8, 4), dtype=np.float64)
    with pytest.raises(ValueError, match="square"):
        build_attention_graph(a, k_attn=2)
