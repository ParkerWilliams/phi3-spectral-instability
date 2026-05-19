"""Fixtures specific to unit tests.

Includes synthetic Phi3Attention-shaped module factory (for hook tests without
real Phi-3 weights) and helpers for generating reproducible random matrices in
float64 for parity tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import numpy as np


@pytest.fixture
def make_random_float64_matrix():
    """Factory returning a `(n, n) float64` matrix from a seeded RNG.

    Usage::

        def test_x(make_random_float64_matrix):
            m = make_random_float64_matrix(seed=42, n=96)
    """
    import numpy as np  # local import; numpy is a dev dep, only imported when test runs

    def _make(seed: int, n: int = 96) -> "np.ndarray":
        rng = np.random.default_rng(seed)
        return rng.standard_normal((n, n), dtype=np.float64)

    return _make


@pytest.fixture
def synthetic_phi3_attention_module():
    """Factory returning a tiny torch.nn.Module that mimics Phi3Attention's
    forward signature for hook-recovery tests.

    The module has 2 layers × 4 heads, d_head=8, and exposes Q, K, V, attention
    weights, and output projection in the same way Phi3Attention does.
    """
    import torch  # local import; torch is a runtime dep
    from torch import nn

    class TinyAttention(nn.Module):
        def __init__(self, d_model: int = 32, n_heads: int = 4) -> None:
            super().__init__()
            self.d_model = d_model
            self.n_heads = n_heads
            self.d_head = d_model // n_heads
            self.qkv_proj = nn.Linear(d_model, 3 * d_model, bias=False)
            self.o_proj = nn.Linear(d_model, d_model, bias=False)

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            b, t, _ = x.shape
            qkv = self.qkv_proj(x).reshape(b, t, 3, self.n_heads, self.d_head)
            q, k, v = qkv.unbind(dim=2)
            # Standard scaled dot-product attention (causal not enforced; toy)
            scores = torch.einsum("bthd,bThd->bhtT", q, k) / (self.d_head**0.5)
            attn = torch.softmax(scores, dim=-1)
            ctx = torch.einsum("bhtT,bThd->bthd", attn, v)
            ctx = ctx.reshape(b, t, self.d_model)
            return self.o_proj(ctx)

    def _make(d_model: int = 32, n_heads: int = 4) -> "TinyAttention":
        m = TinyAttention(d_model=d_model, n_heads=n_heads)
        m.eval()
        torch.manual_seed(0)
        return m

    return _make
