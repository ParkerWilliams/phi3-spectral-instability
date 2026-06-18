"""CPU tests for the model-agnostic adapter descriptor/registry logic (SP-0).

Reads ModelDescriptors from mock HF configs — the 'read from config, never computed'
requirement, GQA n_rep, and the Gemma-2 sliding-window profile (research R1.2/R1.3).
The live Q/K/V capture is torch (validated on the pod).
"""

from types import SimpleNamespace

from phi3geom.extraction.adapters.base import build_descriptor, gemma2_attention_profile
from phi3geom.extraction.adapters.registry import resolve_adapter

_KW = dict(revision_sha="r", tokenizer_id="t", transformers_version="4.53.0")

LLAMA = SimpleNamespace(num_attention_heads=32, num_key_value_heads=8, hidden_size=4096,
                        num_hidden_layers=32, model_type="llama")
QWEN = SimpleNamespace(num_attention_heads=28, num_key_value_heads=4, hidden_size=3584,
                       head_dim=128, num_hidden_layers=28, model_type="qwen2")
MISTRAL = SimpleNamespace(num_attention_heads=32, num_key_value_heads=8, hidden_size=4096,
                          num_hidden_layers=32, model_type="mistral")
GEMMA2 = SimpleNamespace(num_attention_heads=16, num_key_value_heads=8, hidden_size=3584,
                         head_dim=256, num_hidden_layers=42, model_type="gemma2",
                         tie_word_embeddings=True, sliding_window=4096,
                         attn_logit_softcapping=50.0, query_pre_attn_scalar=256)
PHI3 = SimpleNamespace(num_attention_heads=32, num_key_value_heads=32, hidden_size=3072,
                       num_hidden_layers=32, model_type="phi3")


def test_head_dim_read_from_config_or_computed():
    # absent in config -> computed
    assert build_descriptor(LLAMA, model_id="llama", **_KW).head_dim == 128
    assert build_descriptor(PHI3, model_id="phi3", **_KW).head_dim == 96
    # present in config -> read verbatim (Gemma-2 256 != 3584/16 = 224)
    assert build_descriptor(GEMMA2, model_id="g", **_KW).head_dim == 256
    assert build_descriptor(QWEN, model_id="q", **_KW).head_dim == 128


def test_gqa_n_rep_per_arch():
    assert build_descriptor(LLAMA, model_id="l", **_KW).n_rep == 4
    assert build_descriptor(QWEN, model_id="q", **_KW).n_rep == 7
    assert build_descriptor(MISTRAL, model_id="m", **_KW).n_rep == 4
    assert build_descriptor(GEMMA2, model_id="g", **_KW).n_rep == 2
    assert build_descriptor(PHI3, model_id="p", **_KW).n_rep == 1  # MHA


def test_tied_embeddings_flag():
    assert build_descriptor(GEMMA2, model_id="g", **_KW).tied_embeddings is True
    assert build_descriptor(LLAMA, model_id="l", **_KW).tied_embeddings is False


def test_gemma2_softcap_and_scalar_read_from_config():
    g = build_descriptor(GEMMA2, model_id="g", **_KW)
    assert g.attn_logit_softcap == 50.0
    assert g.query_pre_attn_scalar == 256.0
    # non-Gemma models carry neither
    l = build_descriptor(LLAMA, model_id="l", **_KW)
    assert l.attn_logit_softcap is None
    assert l.query_pre_attn_scalar is None


def test_gemma2_attention_profile_alternates():
    prof = gemma2_attention_profile(GEMMA2)
    assert len(prof) == 42
    assert prof[0] == "full" and prof[1] == "sliding:4096"
    assert prof[2] == "full" and prof[41] == "sliding:4096"


def test_resolve_adapter_routes_gemma_profile():
    g = resolve_adapter(SimpleNamespace(config=GEMMA2), model_id="g")
    assert len(g.describe().attention_profile) == 42
    assert g.describe().n_rep == 2
    # non-gemma -> no profile
    l = resolve_adapter(SimpleNamespace(config=LLAMA), model_id="l")
    assert l.describe().attention_profile == ()
    assert l.describe().n_rep == 4
