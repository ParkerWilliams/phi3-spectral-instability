"""GPU-reduction ↔ CPU-primitive equivalence (SP-0) — runs under torch (no GPU/model).

The CPU primitives carry the analytic property tests; this asserts the on-device
reductions match them within tolerance, so a green run here validates the GPU path's
math. Skips only if torch is absent. On the pod it runs immediately after
`pip install -e .` (no model download needed).
"""

import importlib.util

import numpy as np
import pytest

_HAS_TORCH = importlib.util.find_spec("torch") is not None
pytestmark = pytest.mark.skipif(not _HAS_TORCH, reason="needs torch (CPU is fine)")


def test_token_cloud_surface_matches_cpu():
    import torch

    from phi3geom.extraction.gpu_reductions import K_EIG, token_cloud_surface_gpu
    from phi3geom.geometry.spectral import token_cloud_spectrum

    rng = np.random.default_rng(0)
    X = rng.standard_normal((200, 64)).astype(np.float64)
    gpu = token_cloud_surface_gpu([torch.tensor(X, dtype=torch.float64)])[0]

    cpu = token_cloud_spectrum(X, k=K_EIG)
    ev = np.zeros(K_EIG)
    ev[: cpu["eigenvalues"].size] = cpu["eigenvalues"][:K_EIG]
    cpu_row = np.concatenate([ev, [cpu["gamma"], cpu["sigma_sq"], cpu["mp_edge_lower"],
                                   cpu["mp_edge_upper"], cpu["n_spikes"], cpu["lambda_max"]]])
    assert np.allclose(gpu, cpu_row, atol=1e-5, rtol=1e-5)


def test_interhead_cell_matches_cpu():
    import torch

    from phi3geom.extraction.gpu_reductions import _cell_summary_gpu
    from phi3geom.geometry.interhead import CELL_FEATURES, cell_summary

    rng = np.random.default_rng(1)
    A = rng.random((8, 30))
    A /= A.sum(axis=1, keepdims=True)
    gpu = _cell_summary_gpu(torch.tensor(A, dtype=torch.float64), (2, 4))
    cpu = cell_summary(A.astype(np.float64), evidence_span=(2, 4))
    cpu_row = [cpu[n] for n in CELL_FEATURES] + [cpu["evidence_coverage"]]
    assert np.allclose(gpu, cpu_row, atol=1e-5, rtol=1e-5)


def test_interhead_surface_shape_and_no_span():
    import torch

    from phi3geom.extraction.gpu_reductions import interhead_surface_gpu
    from phi3geom.geometry.interhead import CELL_FEATURES

    rng = np.random.default_rng(2)
    L, H, T = 3, 6, 40
    at = []
    for _ in range(L):
        A = rng.random((H, T, T))
        A /= A.sum(axis=-1, keepdims=True)
        at.append(torch.tensor(A, dtype=torch.float64))
    surf = interhead_surface_gpu(at, answer_pos=T - 1, span=None)
    assert surf.shape[1] == L
    assert surf.shape[2] == len(CELL_FEATURES) + 1
    assert np.isnan(surf[..., -1]).all()  # coverage slot NaN when no span
