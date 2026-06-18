"""Selective-recompute ↔ eager-attention equivalence (SP-0) — POD ONLY.

The safety net for the risky sdpa-selective path: on a real model, the rows recomputed
from the hooked Q/K must match eager's own ``output_attentions`` for the query
positions we store. A green run per model means sdpa_selective is safe to use for it; a
mismatch (expected for Gemma-2 until softcap/sliding-window are added) tells you exactly
which arch needs more.

Skip-guarded: ``PHI3_RUN_GPU_TESTS=1`` + ``PHI3_ROUNDTRIP_MODELS`` (default Phi-3-mini).
"""

import importlib.util
import os

import pytest

_HAS_TORCH = importlib.util.find_spec("torch") is not None
_RUN = os.environ.get("PHI3_RUN_GPU_TESTS") == "1"
_MODELS = os.environ.get(
    "PHI3_ROUNDTRIP_MODELS", "microsoft/Phi-3-mini-4k-instruct"
).split(",")

pytestmark = pytest.mark.skipif(
    not (_HAS_TORCH and _RUN),
    reason="needs torch + a real model; set PHI3_RUN_GPU_TESTS=1 on a pod",
)


@pytest.mark.parametrize("model_id", _MODELS)
def test_selective_matches_eager(model_id):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from phi3geom.extraction.adapters.registry import resolve_adapter
    from phi3geom.extraction.gpu_reductions import sampled_queries
    from phi3geom.extraction.hooks import Phi3ExtractionHook
    from phi3geom.extraction.selective_attention import recompute_query_rows

    model_id = model_id.strip()
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, attn_implementation="eager", torch_dtype=torch.float32, device_map="auto"
    )
    adapter = resolve_adapter(model, model_id=model_id)
    descriptor = adapter.describe()

    ids = tok("The capital of France is Paris and the sky is blue",
              return_tensors="pt").to(model.device)["input_ids"]
    answer_pos = ids.shape[1] - 1
    queries = sampled_queries(answer_pos, None)

    with Phi3ExtractionHook(model) as hook, torch.no_grad():
        out = model(ids, output_attentions=True, use_cache=False)
    eager = {t: torch.stack([a[0][:, t, :] for a in out.attentions]).double() for t in queries}
    sdpa = recompute_query_rows(hook.captures, descriptor, model, queries)

    for t in queries:
        assert torch.allclose(eager[t], sdpa[t], atol=2e-3), f"mismatch at query {t}"
