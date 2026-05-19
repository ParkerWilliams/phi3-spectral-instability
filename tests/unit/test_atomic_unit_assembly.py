"""Tests for ``phi3geom.geometry.atomic_unit`` (FR-005)."""

from __future__ import annotations

import math

import networkx as nx
import numpy as np
import pytest

from phi3geom.geometry import FEATURE_NAMES, N_FEATURES
from phi3geom.geometry.atomic_unit import compute_atomic_unit_features


def _qkt_avwo(seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    return (
        rng.standard_normal((96, 96), dtype=np.float64),
        rng.standard_normal((96, 96), dtype=np.float64),
    )


def _toy_attention_graph() -> nx.Graph:
    """A small connected weighted graph for the Ricci slot."""
    g = nx.cycle_graph(8)
    for u, v in g.edges:
        g[u][v]["weight"] = 1.0
    return g


def test_feature_axis_length_is_7() -> None:
    assert N_FEATURES == 7
    assert len(FEATURE_NAMES) == 7


def test_feature_names_canonical_order() -> None:
    expected = (
        "stable_rank_qkt",
        "grassmannian_qkt",
        "spectral_entropy_qkt",
        "stable_rank_avwo",
        "grassmannian_avwo",
        "spectral_entropy_avwo",
        "forman_ricci_attention_graph",
    )
    assert FEATURE_NAMES == expected


def test_us1_baseline_ricci_slot_is_nan() -> None:
    qkt, avwo = _qkt_avwo()
    g = _toy_attention_graph()
    features = compute_atomic_unit_features(
        qkt, avwo, g, k_grass=8, k_attn=16, compute_ricci=False
    )
    assert features.shape == (7,)
    assert features.dtype == np.float64
    # Spectral slots are finite
    assert np.all(np.isfinite(features[:6]))
    # Ricci slot is NaN at T038 (US1 baseline)
    assert math.isnan(features[6])


def test_us2_ricci_populated_when_requested() -> None:
    qkt, avwo = _qkt_avwo()
    g = _toy_attention_graph()
    features = compute_atomic_unit_features(
        qkt, avwo, g, k_grass=8, k_attn=16, compute_ricci=True
    )
    assert not math.isnan(features[6])
    assert np.isfinite(features[6])


def test_rejects_float32_qkt() -> None:
    qkt = np.zeros((96, 96), dtype=np.float32)
    avwo = np.zeros((96, 96), dtype=np.float64)
    g = _toy_attention_graph()
    with pytest.raises(TypeError, match="qkt"):
        compute_atomic_unit_features(qkt, avwo, g, k_attn=16)


def test_rejects_float32_avwo() -> None:
    qkt = np.zeros((96, 96), dtype=np.float64)
    avwo = np.zeros((96, 96), dtype=np.float32)
    g = _toy_attention_graph()
    with pytest.raises(TypeError, match="avwo"):
        compute_atomic_unit_features(qkt, avwo, g, k_attn=16)


def test_deterministic_for_same_input() -> None:
    qkt, avwo = _qkt_avwo(seed=42)
    g = _toy_attention_graph()
    a = compute_atomic_unit_features(qkt, avwo, g, k_attn=16)
    b = compute_atomic_unit_features(qkt, avwo, g, k_attn=16)
    # The 6 spectral slots must be bit-identical for the same inputs.
    assert np.allclose(a[:6], b[:6], rtol=0, atol=0)
