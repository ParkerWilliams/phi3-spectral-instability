"""Foundational model-agnostic capture primitives (SP-0).

Import-safe WITHOUT ``torch`` installed: ``ModelDescriptor`` and the GQA/MQA
head-expansion helpers are pure-Python/NumPy. ``torch`` is imported lazily inside
the live capture path of concrete adapters (the v1 ``hooks.py`` pattern), so this
module can be exercised by CPU unit tests with no model present.

Contracts: data-model.md (ModelDescriptor), contracts/capture-manifest.md
(capture config), research.md R1.2 (GQA pairing).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import numpy as np


# --------------------------------------------------------------------------- #
# GQA / MQA head expansion (research.md R1.2)
#
# transformers' ``repeat_kv`` expands grouped KV heads to query resolution via a
# contiguous/block grouping equivalent to ``repeat_interleave(dim=heads,
# repeats=n_rep)``: query head ``q`` is served by KV head ``q // n_rep``. Getting
# this wrong silently pairs the wrong K with each Q and corrupts every QKᵀ.
# --------------------------------------------------------------------------- #


def n_rep_for(n_heads: int, n_kv_heads: int) -> int:
    """Repetition factor ``n_heads // n_kv_heads``; raises on a non-divisor.

    A non-divisible head count is a hard error (research.md R1.2: "fail loudly on
    any head-count mismatch"), never a silently-wrong pairing.
    """
    if n_heads <= 0 or n_kv_heads <= 0:
        raise ValueError(f"head counts must be > 0; got {n_heads}, {n_kv_heads}")
    if n_heads % n_kv_heads != 0:
        raise ValueError(
            f"n_heads={n_heads} is not an integer multiple of "
            f"n_kv_heads={n_kv_heads} (GQA expansion would misalign Q/KV)"
        )
    return n_heads // n_kv_heads


def kv_head_for_query(q_head: int, n_rep: int) -> int:
    """KV-head index serving query head ``q_head`` under contiguous grouping."""
    if n_rep < 1:
        raise ValueError(f"n_rep must be ≥ 1; got {n_rep}")
    if q_head < 0:
        raise ValueError(f"q_head must be ≥ 0; got {q_head}")
    return q_head // n_rep


def expand_kv_heads(kv: np.ndarray, n_rep: int, *, axis: int) -> np.ndarray:
    """Expand grouped KV heads to query resolution along ``axis``.

    Reference (NumPy) implementation of transformers' ``repeat_kv``:
    ``np.repeat`` with a scalar count is exactly ``repeat_interleave`` — each KV
    head is repeated ``n_rep`` times contiguously, so the output head order is
    ``[kv0]*n_rep, [kv1]*n_rep, …``. ``n_rep == 1`` (MHA, e.g. Phi-3-mini) is the
    identity. Concrete torch adapters use ``torch.repeat_interleave`` with the
    same semantics.
    """
    if n_rep < 1:
        raise ValueError(f"n_rep must be ≥ 1; got {n_rep}")
    arr = np.asarray(kv)
    if n_rep == 1:
        return arr
    return np.repeat(arr, n_rep, axis=axis)


# --------------------------------------------------------------------------- #
# ModelDescriptor (data-model.md)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ModelDescriptor:
    """Per-model metadata + capture profile (read from config, never computed).

    ``attention_profile`` is a per-layer tuple describing each layer's effective
    attention support — e.g. ``("full", "sliding:4096", …)`` plus softcap params
    for Gemma-2 — so routing metrics are never computed against a mask the model
    never used (research.md R1.3). When provided it MUST have ``n_layers`` entries.
    """

    model_id: str
    revision_sha: str
    d_model: int
    n_layers: int
    n_heads: int
    n_kv_heads: int
    head_dim: int
    tokenizer_id: str
    transformers_version: str
    tied_embeddings: bool = False
    attention_profile: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        # Validates divisibility (raises on mismatch) and basic shape sanity.
        _ = self.n_rep
        if self.head_dim <= 0 or self.d_model <= 0 or self.n_layers <= 0:
            raise ValueError("d_model, n_layers, head_dim must be > 0")
        if self.attention_profile and len(self.attention_profile) != self.n_layers:
            raise ValueError(
                f"attention_profile has {len(self.attention_profile)} entries; "
                f"expected n_layers={self.n_layers}"
            )

    @property
    def n_rep(self) -> int:
        """Query-per-KV repetition factor (1 for MHA models like Phi-3-mini)."""
        return n_rep_for(self.n_heads, self.n_kv_heads)


# --------------------------------------------------------------------------- #
# ModelAdapter protocol (interface only; concrete adapters import torch lazily)
# --------------------------------------------------------------------------- #


@runtime_checkable
class ModelAdapter(Protocol):
    """Per-architecture capture interface consumed by ``extraction/capture.py``.

    Concrete adapters (phi3/llama/qwen2/mistral/gemma2) implement these against
    the loaded model; this protocol is the torch-free contract. The ``capture``
    surface accepts an optional ``intervention`` callback — the reusable surface
    SP-3 re-invokes with interventions (FR-026); SP-0 ships the surface, not the
    interventions.
    """

    def describe(self) -> ModelDescriptor:
        """Return the model's metadata read from its config."""
        ...

    def capture(self, input_ids: Any, *, intervention: Any | None = None) -> Any:
        """Run the rich-capture forward pass, optionally with a per-layer
        intervention callback, returning the raw capture material."""
        ...


# --------------------------------------------------------------------------- #
# Descriptor-from-config (CPU-testable) + a generic capture adapter.
#
# build_descriptor / gemma2_attention_profile are pure (a config object in →
# ModelDescriptor out) and are unit-tested with mock configs. HFAdapter.capture_qkv
# is torch (drafted, pod-validation-pending).
# --------------------------------------------------------------------------- #


def build_descriptor(
    config: Any,
    *,
    model_id: str,
    revision_sha: str,
    tokenizer_id: str,
    transformers_version: str,
    attention_profile: tuple[str, ...] = (),
) -> ModelDescriptor:
    """Read a ``ModelDescriptor`` from an HF config — head_dim from config when
    present (Gemma-2 256 ≠ hidden/heads), computed only when absent (research R1.2)."""
    n_heads = int(config.num_attention_heads)
    n_kv = int(getattr(config, "num_key_value_heads", None) or n_heads)
    head_dim = getattr(config, "head_dim", None)
    head_dim = int(head_dim) if head_dim else int(config.hidden_size) // n_heads
    return ModelDescriptor(
        model_id=model_id,
        revision_sha=revision_sha,
        d_model=int(config.hidden_size),
        n_layers=int(config.num_hidden_layers),
        n_heads=n_heads,
        n_kv_heads=n_kv,
        head_dim=head_dim,
        tokenizer_id=tokenizer_id,
        transformers_version=transformers_version,
        tied_embeddings=bool(getattr(config, "tie_word_embeddings", False)),
        attention_profile=tuple(attention_profile),
    )


def gemma2_attention_profile(config: Any) -> tuple[str, ...]:
    """Per-layer ``full`` / ``sliding:<window>`` profile for Gemma-2 (research R1.3):
    `layer_types` when present, else even=full / odd=sliding."""
    n_layers = int(config.num_hidden_layers)
    window = int(getattr(config, "sliding_window", 4096) or 4096)
    layer_types = getattr(config, "layer_types", None)
    prof = []
    for i in range(n_layers):
        if layer_types is not None:
            prof.append("full" if layer_types[i] == "full_attention" else f"sliding:{window}")
        else:
            prof.append("full" if i % 2 == 0 else f"sliding:{window}")
    return tuple(prof)


@dataclass
class HFAdapter:
    """Generic capture adapter: GQA expansion + per-head Q/K/V at the answer position.

    Handles fused `qkv_proj` (Phi-3, MHA) and split `q/k/v_proj` (Llama/Qwen/Mistral/
    Gemma-2, GQA) off the v1 ``Phi3ExtractionHook`` captures. ⚠ ``capture_qkv`` is
    drafted torch/numpy — pod-validation-pending.
    """

    model: Any
    descriptor: ModelDescriptor

    def describe(self) -> ModelDescriptor:
        return self.descriptor

    def capture_qkv(self, captures: dict, answer_pos: int) -> np.ndarray:
        """Per-head Q/K/V at ``answer_pos`` → ``(3, L, n_heads, head_dim)`` fp32,
        GQA-expanded. Fused captures arrive head-shaped; split captures are flat
        ``(T, heads*head_dim)`` and are reshaped here."""
        d = self.descriptor
        out = np.full((3, d.n_layers, d.n_heads, d.head_dim), np.nan, dtype=np.float32)
        for ell, cap in captures.items():
            for slot, name in ((0, "q"), (1, "k"), (2, "v")):
                t = getattr(cap, name, None)
                if t is None:
                    continue
                a = np.asarray(t[0].float().cpu().numpy(), dtype=np.float32)
                if a.ndim == 3:  # fused, already (T, heads, head_dim)
                    vec = a[answer_pos]
                else:  # split, flat (T, heads*head_dim)
                    heads = a.shape[1] // d.head_dim
                    vec = a[answer_pos].reshape(heads, d.head_dim)
                if name in ("k", "v") and vec.shape[0] < d.n_heads:
                    vec = expand_kv_heads(vec, d.n_heads // vec.shape[0], axis=0)
                out[slot, ell] = vec
        return out
