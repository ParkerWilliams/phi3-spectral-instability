"""On-device in-pass reductions (SP-0) — UNVALIDATED (pod).

Mirrors the *tested* CPU primitives on torch tensors so the heavy linear algebra runs
on the GPU and only the small reduced surfaces move to host — avoiding both the CPU
SVD/eigen bottleneck and the multi-GB full-attention host transfer:

- ``token_cloud_surface_gpu`` ↔ ``geometry.spectral.token_cloud_spectrum`` (per-layer
  SVD of the token cloud → eigenspectrum + Marchenko–Pastur fit), looped per layer to
  bound peak memory.
- ``interhead_surface_gpu`` ↔ ``geometry.interhead.cell_summary`` (per (t,ℓ) cell:
  pairwise JS/Hellinger dispersion + overlap-matrix effective rank / Fiedler / top
  eigenvalue), vectorizing the pairwise loop on-device.

Float64 at the spectral seam (Constitution IV); downcast to fp32 on return. torch is
imported lazily. Validated on the pod by
``tests/integration/test_gpu_reductions_equivalence.py`` (GPU path ≈ CPU primitives) —
which runs under torch alone (no GPU/model needed).
"""

from __future__ import annotations

import numpy as np

from phi3geom.geometry.interhead import CELL_FEATURES
from phi3geom.geometry.spectral import marchenko_pastur_edges

K_EIG: int = 32
SAMPLED_QUERY_OFFSETS: tuple[int, ...] = (0, 1, 2, 4, 8, 16, 32, 64, 128, 256)
HIDDEN_WINDOW: int = 16
_EPS = 1e-12


def token_cloud_surface_gpu(hidden_states, *, k: int = K_EIG) -> np.ndarray:
    """Per-layer token-cloud eigenspectrum + MP fit on-device → (L, k + 6) fp32.

    ``hidden_states``: a sequence of ``(T, d)`` torch tensors (one per layer), on the
    capture device. Looped per layer so no ``(L, T, d)`` stack is materialized.
    """
    import torch

    rows = []
    for h in hidden_states:
        hd = h.double()
        n, p = hd.shape
        sv = torch.linalg.svdvals(hd)          # (min(n, p),)
        ev = (sv * sv) / float(n)              # covariance eigenvalues, descending
        ev_np = ev.detach().cpu().numpy()
        gamma = p / n
        sigma_sq = float(ev_np.sum() / p)      # mean over all p (zeros for p > n)
        lo, hi = marchenko_pastur_edges(gamma, sigma_sq)
        n_spikes = int((ev_np > hi).sum())
        topk = np.zeros(k, dtype=np.float64)
        topk[: min(k, ev_np.size)] = ev_np[:k]
        rows.append(
            np.concatenate([topk, [gamma, sigma_sq, lo, hi, n_spikes, float(ev_np[0])]])
        )
    return np.stack(rows).astype(np.float32)


def _cell_summary_gpu(A, span) -> list[float]:
    """On-device port of ``geometry.interhead.cell_summary`` for one (H, T) cell."""
    import torch

    H = A.shape[0]
    A = A / A.sum(dim=-1, keepdim=True).clamp_min(_EPS)
    p = A.unsqueeze(1).expand(H, H, -1)        # (H,H,T): rows = head i
    q = A.unsqueeze(0).expand(H, H, -1)        # (H,H,T): rows = head j
    m = 0.5 * (p + q)

    def _kl(x, y):  # Σ_t x·log2(x/y), masking x==0
        term = torch.where(x > _EPS, x * torch.log2(x / y), torch.zeros_like(x))
        return term.sum(dim=-1)                # (H,H)

    jsd = 0.5 * _kl(p, m) + 0.5 * _kl(q, m)
    js = torch.sqrt(jsd.clamp_min(0.0))        # (H,H) JS distance
    hel = torch.sqrt((1.0 - torch.sqrt(p * q).sum(dim=-1)).clamp_min(0.0))
    iu = torch.triu_indices(H, H, offset=1)
    disp_js = js[iu[0], iu[1]].mean().item() if H > 1 else 0.0
    disp_hel = hel[iu[0], iu[1]].mean().item() if H > 1 else 0.0

    M = 1.0 - js                               # (H,H) similarity
    sv = torch.linalg.svdvals(M)
    sv = sv[sv > _EPS]
    eff = float(torch.exp(-(sv / sv.sum() * torch.log(sv / sv.sum())).sum())) if sv.numel() else 0.0
    top = float(torch.linalg.eigvalsh(M)[-1])
    if H > 1:
        W = M.clone()
        W.fill_diagonal_(0.0)
        W = W.clamp_min(0.0)
        lap = torch.diag(W.sum(dim=1)) - W
        fied = float(torch.linalg.eigvalsh(lap)[1])
    else:
        fied = 0.0
    cov = float(A[:, span[0]: span[1] + 1].sum(dim=1).mean()) if span is not None else float("nan")
    return [disp_js, disp_hel, eff, fied, top, cov]


def interhead_surface_gpu(attentions, answer_pos: int, span, *, offsets=SAMPLED_QUERY_OFFSETS) -> np.ndarray:
    """Inter-head drift surface S(t,ℓ) on-device → (n_t, L, len(CELL_FEATURES)+1) fp32.

    ``attentions``: a sequence of ``(H, T, T)`` torch tensors (one per layer). Indexes
    each cell on-device — never materializes/transfers the full attention to host.
    """
    L = len(attentions)
    queries = sorted({max(0, answer_pos - off) for off in offsets})
    if span is not None:
        queries = sorted(set(queries) | {span[0], span[1]})
    K = len(CELL_FEATURES) + 1
    surface = np.full((len(queries), L, K), np.nan, dtype=np.float64)
    for ti, t in enumerate(queries):
        for ell in range(L):
            A = attentions[ell][:, t, :].double()   # (H, T) on device
            surface[ti, ell, :] = _cell_summary_gpu(A, span)
    return surface.astype(np.float32)
