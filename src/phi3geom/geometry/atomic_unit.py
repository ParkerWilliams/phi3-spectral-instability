"""Per-atomic-unit feature assembly (FR-005, contracts/atomic_unit.md).

Combines the spectral primitives on QKᵀ and AVWO with the Forman-Ricci
scalar on the per-(t, ℓ, h) attention graph into the canonical 7-vector
ordered by ``FEATURE_NAMES``.

At T038 (US1 baseline), the Forman-Ricci slot is always ``NaN`` — the
spectral-only pilot. T049 (US2) wires in Forman-Ricci via the
``compute_ricci=True`` parameter.
"""

from __future__ import annotations

import math

import networkx as nx
import numpy as np

from phi3geom.geometry import N_FEATURES
from phi3geom.geometry.spectral import (
    frobenius_norm,
    nuclear_norm,
    spectral_entropy,
    spectral_norm,
    stable_rank,
    top_k_grassmannian,
)


def compute_atomic_unit_features(
    qkt: np.ndarray,
    avwo: np.ndarray,
    attention_graph: nx.Graph | None,
    *,
    k_grass: int = 8,
    k_attn: int,
    compute_ricci: bool = False,
) -> np.ndarray:
    """Compute the 7-scalar atomic-unit feature vector in canonical order.

    Args:
        qkt: ``(d_head, d_head)`` float64 QKᵀ matrix.
        avwo: ``(d_head, d_head)`` float64 AVWO matrix.
        attention_graph: Per-(t, ℓ, h) attention graph (from
            ``ricci.build_attention_graph``). Used for the Ricci slot ONLY when
            ``compute_ricci=True``. May be ``None`` when ``compute_ricci=False``
            — the caller should skip the (expensive) graph build in that case.
        k_grass: Pinned to 8 for v1.
        k_attn: Used in attention-graph construction upstream; recorded for
            reproducibility.
        compute_ricci: If False (US1 baseline default), the Ricci slot is
            populated with ``np.nan``. If True (US2 and beyond), Forman-Ricci
            is computed on ``attention_graph``.

    Returns:
        ``(N_FEATURES,) float64`` array in ``FEATURE_NAMES`` order:
        ``[stable_rank_qkt, grassmannian_qkt, spectral_entropy_qkt,
           stable_rank_avwo, grassmannian_avwo, spectral_entropy_avwo,
           forman_ricci_attention_graph,
           spectral_norm_qkt, frobenius_norm_qkt, nuclear_norm_qkt,
           spectral_norm_avwo, frobenius_norm_avwo, nuclear_norm_avwo]``.

        Slots 0..6 are the v1 scale-free spectral-shape features (+Ricci);
        slots 7..12 are the v2 magnitude norms — the operator scale that
        the v1 features discard by construction.
    """
    _ = k_attn  # not used directly here; recorded upstream in the manifest

    if qkt.dtype != np.float64:
        raise TypeError(f"qkt must be float64 (Principle IV); got {qkt.dtype}")
    if avwo.dtype != np.float64:
        raise TypeError(f"avwo must be float64 (Principle IV); got {avwo.dtype}")

    features = np.empty(N_FEATURES, dtype=np.float64)
    features[0] = stable_rank(qkt)
    features[1] = top_k_grassmannian(qkt, k=k_grass)
    features[2] = spectral_entropy(qkt)
    features[3] = stable_rank(avwo)
    features[4] = top_k_grassmannian(avwo, k=k_grass)
    features[5] = spectral_entropy(avwo)
    if compute_ricci:
        if attention_graph is None:
            raise ValueError(
                "attention_graph is required when compute_ricci=True; "
                "got None. Build it with ricci.build_attention_graph."
            )
        # Lazy import to keep US1 baseline path free of the heavier Ricci
        # path during pilot kickoff.
        from phi3geom.geometry.ricci import forman_ricci_token
        features[6] = forman_ricci_token(attention_graph)
    else:
        features[6] = math.nan
    # v2 magnitude norms (slots 7..12) — appended after Ricci so v1 indices
    # are stable. Each reuses the operators' singular values.
    features[7] = spectral_norm(qkt)
    features[8] = frobenius_norm(qkt)
    features[9] = nuclear_norm(qkt)
    features[10] = spectral_norm(avwo)
    features[11] = frobenius_norm(avwo)
    features[12] = nuclear_norm(avwo)
    return features
