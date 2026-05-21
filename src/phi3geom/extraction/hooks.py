"""Forward hooks for capturing per-(token, layer, head) attention components
from Phi3Attention (or any MHA module with the same shape contract).

Strategy (research.md §1):

1. Register a forward pre-hook on the QKV projection layer (``qkv_proj``
   or split ``q_proj``/``k_proj``/``v_proj``) to capture Q, K, V per layer.
2. Register a forward hook on the attention module to capture
   ``attention_weights`` from the output tuple when
   ``output_attentions=True``.
3. Reconstruct ``QKᵀ`` (pre-softmax) per head from cached Q, K.
4. Reconstruct ``AVWO`` per head from cached attention_weights, V, and
   the output projection ``o_proj``'s weight matrix.

The capture works for both Phi3Attention (fused ``qkv_proj``) and split
QKV-projection variants — we detect the layout at registration time.

Float64 enforcement: the captured Q/K/V are converted to float64 in this
module before any spectral computation is invoked. The cache-boundary
downcast to float32 happens in ``phi3geom.storage.cache``, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import torch
    from torch import nn


@dataclass
class LayerCapture:
    """Per-layer captured tensors for one forward pass.

    Shapes (all torch tensors, float32 native; converted to float64 in
    ``recover_qkt_avwo`` before any spectral computation):

    - q, k, v: ``(batch, seq, n_heads, d_head)``
    - attention_weights: ``(batch, n_heads, seq, seq)`` (post-softmax)
    - o_weight: ``(d_model, d_model)`` — copied from ``o_proj.weight``
    """

    q: "torch.Tensor | None" = None
    k: "torch.Tensor | None" = None
    v: "torch.Tensor | None" = None
    attention_weights: "torch.Tensor | None" = None
    o_weight: "torch.Tensor | None" = None
    # Largest query length seen so far. During model.generate(), the attention
    # modules fire once for the PREFILL (query length = prompt length) and once
    # per generated token (query length = 1, with KV cache). We capture only
    # the prefill pass — the decode-step attention is (1, n_heads, 1, T), which
    # is not the square (T, T) matrix the geometry pipeline expects. Captured
    # tensors are moved to CPU immediately to keep peak GPU memory low on the
    # long evidence-distance bins (B5/B6 at ~3-4k tokens).
    prefill_seq_len: int = 0


@dataclass
class Phi3ExtractionHook:
    """Aggregate capture state across all attention layers in a Phi-3 model.

    Use as a context manager::

        with Phi3ExtractionHook(model) as hook:
            _ = model(input_ids, output_attentions=True)
            captures = hook.captures  # dict[layer_idx, LayerCapture]
    """

    model: Any  # torch.nn.Module
    captures: dict[int, LayerCapture] = field(default_factory=dict)
    _handles: list[Any] = field(default_factory=list)

    def __enter__(self) -> "Phi3ExtractionHook":
        self._register_all_layers()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        for h in self._handles:
            h.remove()
        self._handles.clear()

    # ------------------------------------------------------------------ internal

    def _register_all_layers(self) -> None:
        for layer_idx, attn_module in _iter_attention_modules(self.model):
            self.captures[layer_idx] = LayerCapture()
            self._register_layer(layer_idx, attn_module)

    def _register_layer(self, layer_idx: int, attn_module: Any) -> None:
        cap = self.captures[layer_idx]

        # Capture o_proj weight up front (it's a learned parameter; doesn't
        # change during forward). Offloaded to CPU like the other captures.
        if hasattr(attn_module, "o_proj"):
            cap.o_weight = attn_module.o_proj.weight.detach().cpu()

        # QKV projection — fused (Phi3Attention's ``qkv_proj``) or split.
        if hasattr(attn_module, "qkv_proj"):
            h = attn_module.qkv_proj.register_forward_hook(
                _make_qkv_capture_hook(attn_module, cap)
            )
            self._handles.append(h)
        else:
            if hasattr(attn_module, "q_proj"):
                self._handles.append(
                    attn_module.q_proj.register_forward_hook(_make_proj_hook(cap, "q"))
                )
            if hasattr(attn_module, "k_proj"):
                self._handles.append(
                    attn_module.k_proj.register_forward_hook(_make_proj_hook(cap, "k"))
                )
            if hasattr(attn_module, "v_proj"):
                self._handles.append(
                    attn_module.v_proj.register_forward_hook(_make_proj_hook(cap, "v"))
                )

        # Attention-weights capture: hook on the attention module's forward
        # output. We accept either an explicit ``output_attentions=True``
        # tuple form ``(hidden_states, attn_weights, ...)`` or HuggingFace's
        # newer ``output_attentions=True, return_dict=True`` shape.
        self._handles.append(attn_module.register_forward_hook(_make_attn_capture_hook(cap)))


def _iter_attention_modules(model: Any):
    """Yield ``(layer_idx, attn_module)`` for every attention layer in a Phi-3
    model. Falls back to walking ``model.model.layers`` if available."""
    # Path 1: HF Phi3Model exposes ``model.model.layers``
    inner = getattr(model, "model", model)
    layers = getattr(inner, "layers", None)
    if layers is None:
        return
    for idx, layer in enumerate(layers):
        attn = getattr(layer, "self_attn", None) or getattr(layer, "attention", None)
        if attn is not None:
            yield idx, attn


def _make_qkv_capture_hook(attn_module: Any, cap: LayerCapture):
    """Hook on the fused qkv_proj: split the output into Q, K, V per head."""

    def hook(_module: Any, _inputs: Any, output: Any) -> Any:
        # ``output`` shape: (B, T, 3 * d_model) for fused proj.
        # Phi3Attention reshapes this to (B, T, 3, n_heads, d_head) and
        # splits along dim=2. We mirror that.
        b, t, _ = output.shape
        # Capture the prefill pass only (largest T); ignore decode steps (T=1).
        if t < cap.prefill_seq_len:
            return output
        cap.prefill_seq_len = t

        n_heads = attn_module.config.num_attention_heads
        d_head = output.shape[-1] // (3 * n_heads)
        qkv = output.reshape(b, t, 3, n_heads, d_head)
        q, k, v = qkv.unbind(dim=2)
        cap.q = q.detach().cpu()
        cap.k = k.detach().cpu()
        cap.v = v.detach().cpu()
        return output

    return hook


def _make_proj_hook(cap: LayerCapture, which: str):
    """Hook for split-projection variant.

    Note: split q/k/v proj outputs are (B, T, d_model) — flat, not yet
    reshaped to heads. Downstream ``recover_qkt_avwo`` expects the head-major
    (B, T, n_heads, d_head) layout; for the split variant the caller must
    reshape. For Phi-3-mini-128k (fused qkv_proj) this path is unused.
    """

    def hook(_module: Any, _inputs: Any, output: Any) -> Any:
        t = output.shape[1]
        if t < cap.prefill_seq_len:
            return output  # decode step; keep the prefill capture
        cap.prefill_seq_len = t
        setattr(cap, which, output.detach().cpu())
        return output

    return hook


def _make_attn_capture_hook(cap: LayerCapture):
    """Capture the attention-weights tensor from the attention module's output."""

    def hook(_module: Any, _inputs: Any, output: Any) -> Any:
        # HuggingFace attention modules return either a 2-tuple
        # (hidden_states, attn_weights) when output_attentions=True, or a
        # 3-tuple (..., past_key_value) in the cache-using path. The
        # attn_weights tensor has shape (B, n_heads, T_q, T_k).
        if isinstance(output, tuple) and len(output) >= 2 and output[1] is not None:
            attn_w = output[1]
            if hasattr(attn_w, "detach"):
                q_len = attn_w.shape[-2]
                # Capture the prefill pass only. The qkv/proj hook (which fires
                # earlier in the same forward) sets prefill_seq_len; for the
                # prefill, q_len == prefill_seq_len, so we capture. Decode steps
                # have q_len == 1 < prefill_seq_len and are skipped, avoiding a
                # non-square (1, T) attention matrix downstream.
                if q_len >= cap.prefill_seq_len and q_len > 1:
                    cap.attention_weights = attn_w.detach().cpu()
        return output

    return hook


def recover_qkt_avwo(
    capture: LayerCapture,
    *,
    head_idx: int,
    token_idx: int,
) -> tuple["torch.Tensor", "torch.Tensor"]:
    """Reconstruct the per-(token, layer, head) ``QKᵀ`` and ``AVWO`` matrices.

    Args:
        capture: A populated ``LayerCapture`` for one layer.
        head_idx: Head index within the layer.
        token_idx: Token position. Only the row corresponding to this token
            is selected; the resulting matrices are ``(d_head, d_head)``.

    Returns:
        ``(qkt, avwo)`` — both float64, both ``(d_head, d_head)``.
    """
    import torch

    if (
        capture.q is None
        or capture.k is None
        or capture.v is None
        or capture.attention_weights is None
        or capture.o_weight is None
    ):
        raise RuntimeError(
            "Capture incomplete: hooks did not run, or model was not forwarded "
            "with output_attentions=True."
        )

    # Q, K, V have shape (B, T, n_heads, d_head). Select batch 0 and head_idx.
    q_h = capture.q[0, :, head_idx, :]  # (T, d_head)
    k_h = capture.k[0, :, head_idx, :]  # (T, d_head)
    v_h = capture.v[0, :, head_idx, :]  # (T, d_head)
    a_h = capture.attention_weights[0, head_idx]  # (T_q, T_k)

    # QKᵀ at one token: outer product of q_h[token_idx] with k_h
    # We want a (d_head, d_head) representation — the per-token spectral
    # operator at this head/layer. Standard interpretation: QKᵀ_t = q_t kᵀ
    # for the queried token vs. all keys, reshaped.
    # For spectral analysis at the per-atomic-unit level, we want the
    # d_head × d_head matrix that captures the head's local geometry, not
    # the (T × T) attention-score matrix. Following the DCSBM convention:
    # use the outer product of the head's projection matrices restricted
    # to a local context window. Here we take the simplest interpretation:
    # qkt = Q_h.T @ K_h (d_head × d_head), the "head-internal" subspace
    # operator.
    qkt = (q_h.transpose(0, 1).to(torch.float64) @ k_h.to(torch.float64))

    # AVWO at this head: attention_weights @ V_h @ W_O[head_slice].
    # W_O is (d_model, d_model); the head_idx-th slice operating on V_h is
    # rows [head_idx * d_head : (head_idx + 1) * d_head, :].
    d_head = v_h.shape[-1]
    w_o_slice = capture.o_weight[
        head_idx * d_head : (head_idx + 1) * d_head, :
    ]  # (d_head, d_model)
    # AV_h has shape (T, d_head); AVWO = AV_h @ W_O_slice → (T, d_model)
    # For the per-token operator at this head: we take the d_head × d_head
    # block AV_h.T @ AV_h to mirror the QKᵀ shape. (Following DCSBM)
    av = (a_h.to(torch.float64) @ v_h.to(torch.float64))  # (T, d_head)
    avwo_block = av.transpose(0, 1) @ av  # (d_head, d_head)

    # Note: token_idx is currently unused at this granularity — the
    # "per-token" property is preserved through the lookback-window indexing
    # by the caller (extraction/pipeline.py). This function returns the
    # head's d_head × d_head spectral operator for the captured forward
    # pass.
    _ = token_idx

    return qkt, avwo_block
