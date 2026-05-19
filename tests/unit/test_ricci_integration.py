"""Integration test for the Ricci feature slot (T048).

Verifies that with ``compute_ricci=True`` the Forman-Ricci slot in the
atomic-unit feature vector is populated (not NaN) for non-degenerate
attention graphs, and stays NaN for isolated-node graphs.
"""

from __future__ import annotations

import math

import networkx as nx
import numpy as np

from phi3geom.geometry.atomic_unit import compute_atomic_unit_features


def _qkt_avwo(seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    return (
        rng.standard_normal((96, 96), dtype=np.float64),
        rng.standard_normal((96, 96), dtype=np.float64),
    )


def _connected_graph() -> nx.Graph:
    g = nx.cycle_graph(8)
    for u, v in g.edges:
        g[u][v]["weight"] = 1.0
    return g


def _graph_with_isolated_node() -> nx.Graph:
    g = nx.cycle_graph(8)
    for u, v in g.edges:
        g[u][v]["weight"] = 1.0
    g.add_node(99)  # isolated
    return g


def test_ricci_populated_on_connected_graph() -> None:
    qkt, avwo = _qkt_avwo()
    g = _connected_graph()
    features = compute_atomic_unit_features(
        qkt, avwo, g, k_attn=16, compute_ricci=True
    )
    assert np.isfinite(features[6])  # not NaN


def test_ricci_nan_on_isolated_node_graph() -> None:
    qkt, avwo = _qkt_avwo()
    g = _graph_with_isolated_node()
    features = compute_atomic_unit_features(
        qkt, avwo, g, k_attn=16, compute_ricci=True
    )
    assert math.isnan(features[6])


def test_ricci_default_false_keeps_nan() -> None:
    qkt, avwo = _qkt_avwo()
    g = _connected_graph()
    # Default compute_ricci=False — US1 baseline
    features = compute_atomic_unit_features(qkt, avwo, g, k_attn=16)
    assert math.isnan(features[6])


def test_spectral_unaffected_by_ricci_flag() -> None:
    qkt, avwo = _qkt_avwo(seed=42)
    g = _connected_graph()
    f_off = compute_atomic_unit_features(qkt, avwo, g, k_attn=16, compute_ricci=False)
    f_on = compute_atomic_unit_features(qkt, avwo, g, k_attn=16, compute_ricci=True)
    # 6 spectral slots must agree exactly; only Ricci differs.
    assert np.allclose(f_off[:6], f_on[:6], rtol=0, atol=0)


def test_pipeline_uses_compute_ricci_flag() -> None:
    """Source-level check that pipeline.py threads compute_ricci through to
    the atomic-unit assembler. Doesn't require running the pipeline."""
    import inspect

    from phi3geom.extraction import pipeline

    src = inspect.getsource(pipeline.run_event_extraction)
    assert "compute_ricci" in src, (
        "pipeline.run_event_extraction must accept and forward compute_ricci"
    )
