"""Adapter registry (SP-0, T029) — resolve the right capture adapter from a model.

One generic ``HFAdapter`` covers Phi-3 (fused, MHA) and the split-projection GQA
models (Llama-3 / Qwen2.5 / Mistral); Gemma-2 additionally gets its per-layer
sliding-window/softcap profile. Descriptor-building is CPU-testable; the capture is
torch (drafted, pod-validation-pending).
"""

from __future__ import annotations

from typing import Any

from phi3geom.extraction.adapters.base import (
    HFAdapter,
    build_descriptor,
    gemma2_attention_profile,
)


def resolve_adapter(
    model: Any,
    *,
    model_id: str = "",
    revision_sha: str = "",
    tokenizer_id: str = "",
    transformers_version: str = "",
) -> HFAdapter:
    """Build the ``HFAdapter`` for ``model`` from its config (Gemma-2 gets a profile)."""
    cfg = model.config
    model_type = str(getattr(cfg, "model_type", ""))
    profile = gemma2_attention_profile(cfg) if model_type.startswith("gemma2") else ()
    descriptor = build_descriptor(
        cfg,
        model_id=model_id or getattr(cfg, "_name_or_path", "") or model_type,
        revision_sha=revision_sha,
        tokenizer_id=tokenizer_id or model_id,
        transformers_version=transformers_version,
        attention_profile=profile,
    )
    return HFAdapter(model=model, descriptor=descriptor)
