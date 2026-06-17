"""Unit tests for GQA/MQA head expansion + ModelDescriptor (SP-0 foundational).

research.md R1.2: query head ``q`` is served by KV head ``q // n_rep`` under the
contiguous (block) grouping of transformers' ``repeat_kv``; a non-divisible head
count must fail loudly.
"""

import numpy as np
import pytest

from phi3geom.extraction.adapters.base import (
    ModelDescriptor,
    expand_kv_heads,
    kv_head_for_query,
    n_rep_for,
)


def test_n_rep_and_mha_noop():
    assert n_rep_for(32, 32) == 1  # MHA (Phi-3-mini)
    assert n_rep_for(32, 8) == 4   # Llama-3 / Mistral GQA
    assert n_rep_for(28, 4) == 7   # Qwen2.5-7B
    assert n_rep_for(16, 8) == 2   # Gemma-2-9B


def test_n_rep_rejects_nondivisible():
    with pytest.raises(ValueError):
        n_rep_for(30, 8)
    with pytest.raises(ValueError):
        n_rep_for(0, 4)


def test_kv_head_block_grouping():
    # n_heads=8, n_kv=2 -> n_rep=4 ; q in [0..3]->kv0, [4..7]->kv1 (contiguous)
    n_rep = n_rep_for(8, 2)
    assert [kv_head_for_query(q, n_rep) for q in range(8)] == [0, 0, 0, 0, 1, 1, 1, 1]


def test_expand_kv_heads_repeats_contiguously():
    kv = np.arange(2 * 3, dtype=np.float64).reshape(2, 3)  # 2 KV heads, d=3
    out = expand_kv_heads(kv, n_rep=4, axis=0)
    assert out.shape == (8, 3)
    assert np.array_equal(out[:4], np.broadcast_to(kv[0], (4, 3)))
    assert np.array_equal(out[4:], np.broadcast_to(kv[1], (4, 3)))


def test_expand_kv_heads_mha_identity():
    kv = np.arange(32 * 4, dtype=np.float64).reshape(32, 4)
    assert np.array_equal(expand_kv_heads(kv, 1, axis=0), kv)


def test_model_descriptor_n_rep_and_validation():
    d = ModelDescriptor(
        model_id="meta-llama/Meta-Llama-3-8B",
        revision_sha="deadbeef",
        d_model=4096, n_layers=32, n_heads=32, n_kv_heads=8, head_dim=128,
        tokenizer_id="meta-llama/Meta-Llama-3-8B", transformers_version="4.53.0",
    )
    assert d.n_rep == 4
    # Phi-3-mini: MHA, head_dim != hidden/n_heads is NOT the case here but
    # head_dim is read from config, not computed — descriptor accepts it verbatim.
    g = ModelDescriptor(
        model_id="google/gemma-2-9b", revision_sha="cafe",
        d_model=3584, n_layers=42, n_heads=16, n_kv_heads=8, head_dim=256,
        tokenizer_id="google/gemma-2-9b", transformers_version="4.53.0",
        attention_profile=tuple(
            ("full" if i % 2 == 0 else "sliding:4096") for i in range(42)
        ),
    )
    assert g.n_rep == 2
    assert g.head_dim == 256  # not 3584/16=224


def test_model_descriptor_rejects_bad_profile_length():
    with pytest.raises(ValueError):
        ModelDescriptor(
            model_id="x", revision_sha="y", d_model=64, n_layers=4, n_heads=8,
            n_kv_heads=2, head_dim=8, tokenizer_id="x", transformers_version="4.53.0",
            attention_profile=("full", "full"),  # only 2, need 4
        )


def test_model_descriptor_rejects_nondivisible_heads():
    with pytest.raises(ValueError):
        ModelDescriptor(
            model_id="x", revision_sha="y", d_model=64, n_layers=4, n_heads=30,
            n_kv_heads=8, head_dim=8, tokenizer_id="x", transformers_version="4.53.0",
        )
