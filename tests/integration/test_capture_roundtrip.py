"""Per-architecture capture round-trip (SP-0, T011/T023) — POD ONLY.

For each model: descriptor matches config; captured per-head Q/K/V has the right
shape; attention is post-softmax-valid; and (the load-bearing GQA check) the expanded
K/V heads are identical WITHIN a KV group and distinct ACROSS groups — i.e. each query
head is paired with KV head ``q // n_rep`` (research R1.2).

Skip-guarded: set ``PHI3_RUN_GPU_TESTS=1`` on a pod and ``PHI3_ROUNDTRIP_MODELS`` to a
comma-separated roster (default: Phi-3-mini). Add a GQA model (Llama-3/Qwen2.5/Mistral)
and Gemma-2 there to exercise the cross-arch paths.
"""

import importlib.util
import os

import numpy as np
import pytest

_HAS_TORCH = importlib.util.find_spec("torch") is not None
_RUN = os.environ.get("PHI3_RUN_GPU_TESTS") == "1"
_MODELS = os.environ.get(
    "PHI3_ROUNDTRIP_MODELS", "microsoft/Phi-3-mini-4k-instruct"
).split(",")

pytestmark = pytest.mark.skipif(
    not (_HAS_TORCH and _RUN),
    reason="round-trip needs torch + real models; set PHI3_RUN_GPU_TESTS=1 on a pod",
)


@pytest.mark.parametrize("model_id", _MODELS)
def test_capture_roundtrip(model_id):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from phi3geom.extraction.adapters.registry import resolve_adapter
    from phi3geom.extraction.hooks import Phi3ExtractionHook

    model_id = model_id.strip()
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, attn_implementation="eager", torch_dtype=torch.float32, device_map="auto"
    )
    adapter = resolve_adapter(model, model_id=model_id)
    d = adapter.describe()
    cfg = model.config

    # descriptor read from config, never computed (research R1.2)
    assert d.n_heads == cfg.num_attention_heads
    assert d.n_kv_heads == int(getattr(cfg, "num_key_value_heads", cfg.num_attention_heads))
    assert d.n_layers == cfg.num_hidden_layers

    ids = tok("The capital of France is", return_tensors="pt").to(model.device)["input_ids"]
    answer_pos = ids.shape[1] - 1
    with Phi3ExtractionHook(model) as hook, torch.no_grad():
        out = model(ids, output_attentions=True, use_cache=False)

    attn = out.attentions
    assert len(attn) == d.n_layers
    assert attn[0].shape[1] == d.n_heads  # already expanded to query heads
    rowsum = attn[0][0, 0].sum(dim=-1)
    assert torch.allclose(rowsum, torch.ones_like(rowsum), atol=1e-3)  # post-softmax

    qkv = adapter.capture_qkv(hook.captures, answer_pos)
    assert qkv.shape == (3, d.n_layers, d.n_heads, d.head_dim)
    assert not np.isnan(qkv[:, 0]).all()  # layer 0 populated

    if d.n_rep > 1:  # GQA: expansion correctness
        K = qkv[1, 0]  # (n_heads, head_dim), layer 0
        for g in range(d.n_kv_heads):
            grp = K[g * d.n_rep : (g + 1) * d.n_rep]
            assert np.allclose(grp, grp[0]), "expanded heads within a KV group must match"
        firsts = K[:: d.n_rep]  # one per KV group
        distinct = {tuple(np.round(f, 3)) for f in firsts}
        assert len(distinct) >= 2, "different KV groups should differ"
