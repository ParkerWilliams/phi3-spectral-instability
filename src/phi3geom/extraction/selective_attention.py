"""Selective attention recompute (SP-0) — UNVALIDATED (pod), OPT-IN.

For long context the eager forward (``output_attentions=True``) materializes the full
``(L, H, T, T)`` attention — multi-GB. This recomputes ``softmax(QKᵀ)`` **only for the
handful of query positions we actually store** (the answer row + the sampled
inter-head queries), from the hooked Q/K, so a fast/low-memory **sdpa** forward can be
used instead. Returns ``{t: (L, H, T)}`` distributions on device.

Faithfulness (the RoPE/GQA traps — research R1.2/R1.4):
- post-RoPE Q/K via the model's own ``rotary_emb`` (cos/sin) + standard rotate-half;
- GQA K expanded to query heads; scaling = ``head_dim**-0.5``;
- causal mask (query t attends keys ≤ t).
KNOWN GAPS (the equivalence test will flag these per-arch): Gemma-2 attn-logit
**softcap** and **sliding-window** masking are NOT applied (exact for non-Gemma-2;
Gemma-2 needs both added), and the Gemma-2-27B ``query_pre_attn_scalar`` scaling
(coincides with head_dim**-0.5 only for the 9B). torch imported lazily.
"""

from __future__ import annotations

from typing import Any

import numpy as np  # noqa: F401  (kept for parity with the eager-path module surface)


def _to_heads(t: Any, heads: int, head_dim: int):
    """Hook capture → ``(T, heads, head_dim)`` (fused already 3D; split is flat)."""
    a = t[0]
    if a.dim() == 3:
        return a
    return a.reshape(a.shape[0], heads, head_dim)


def _rotate_half(x):
    import torch

    half = x.shape[-1] // 2
    return torch.cat((-x[..., half:], x[..., :half]), dim=-1)


def _apply_rope(x, cos, sin):
    # x: (heads, T, head_dim); cos/sin: (T, head_dim)
    return x * cos.unsqueeze(0) + _rotate_half(x) * sin.unsqueeze(0)


def recompute_query_rows(captures: dict, descriptor, model, queries) -> dict:
    """Recompute attention distributions at ``queries`` → ``{t: (L, H, T)}`` on device.

    ``captures`` are the ``Phi3ExtractionHook`` per-layer captures (pre-RoPE Q/K).
    """
    import torch

    d = descriptor
    device = next(model.parameters()).device
    inner = getattr(model, "model", model)
    rotary = getattr(inner, "rotary_emb", None)
    if rotary is None:
        raise RuntimeError("model has no model.rotary_emb; selective recompute needs it")

    any_cap = next(iter(captures.values()))
    T = int(any_cap.q.shape[1])
    position_ids = torch.arange(T, device=device).unsqueeze(0)
    dummy = torch.zeros(1, T, d.head_dim, device=device)
    cos, sin = rotary(dummy, position_ids)  # (1, T, head_dim) each
    cos, sin = cos[0].double(), sin[0].double()
    scaling = d.head_dim ** -0.5

    q_idx = torch.tensor(sorted(set(int(q) for q in queries)), device=device)
    keypos = torch.arange(T, device=device)
    future = keypos[None, None, :] > q_idx[None, :, None]  # (1, n_q, T): mask future keys

    out = torch.zeros(d.n_layers, d.n_heads, q_idx.numel(), T, device=device, dtype=torch.float64)
    for ell, cap in captures.items():
        q = _to_heads(cap.q, d.n_heads, d.head_dim).to(device).transpose(0, 1).double()  # (H,T,hd)
        k = _to_heads(cap.k, d.n_kv_heads, d.head_dim).to(device).transpose(0, 1).double()  # (n_kv,T,hd)
        q = _apply_rope(q, cos, sin)
        k = _apply_rope(k, cos, sin)
        if d.n_rep > 1:
            k = k.repeat_interleave(d.n_rep, dim=0)  # (H,T,hd)
        q_sel = q[:, q_idx, :]  # (H, n_q, hd)
        scores = torch.einsum("hqd,htd->hqt", q_sel, k) * scaling  # (H, n_q, T)
        scores = scores.masked_fill(future, float("-inf"))
        out[ell] = torch.softmax(scores, dim=-1)

    return {int(t): out[:, :, qi, :].contiguous() for qi, t in enumerate(q_idx.tolist())}
