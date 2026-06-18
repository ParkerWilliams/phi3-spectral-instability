"""End-to-end v2 capture-pipeline integration test (SP-0) — POD ONLY.

Skip-guarded: needs torch + transformers + a real model. On a GPU pod set
``PHI3_RUN_GPU_TESTS=1`` (optionally ``PHI3_TEST_MODEL``) to run it. This is the test
to flip on first to debug the drafted capture pass.
"""

import importlib.util
import os

import pytest

_HAS_TORCH = importlib.util.find_spec("torch") is not None
_RUN = os.environ.get("PHI3_RUN_GPU_TESTS") == "1"

pytestmark = pytest.mark.skipif(
    not (_HAS_TORCH and _RUN),
    reason="v2 capture needs torch + a model; set PHI3_RUN_GPU_TESTS=1 on a GPU pod",
)


def test_capture_one_event_writes_a_loadable_bundle(tmp_path):
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from phi3geom.analysis.harness import load
    from phi3geom.dataset.types import DocQAEventRecord
    from phi3geom.extraction.capture import run_capture

    model_id = os.environ.get("PHI3_TEST_MODEL", "microsoft/Phi-3-mini-4k-instruct")
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, attn_implementation="eager", torch_dtype="bfloat16", device_map="auto"
    )
    rec = DocQAEventRecord(
        event_id="t0", corpus_id="hotpotqa",
        document="Paris is the capital of France.",
        question="What is the capital of France?",
        gold_aliases=("paris",), is_answerable=True, evidence_spans=((0, 4),),
    )
    label = run_capture(
        model, tok, rec, cache_root=tmp_path, capture_version="2.0.0",
        model_id=model_id, revision_sha="test", manifest_sha256="test",
        code_commit_sha="test", k_samples=2,
    )
    assert label["class_4way"] in (
        "correct-answer", "wrong-answer", "correct-abstention", "hallucination"
    )
    # consumable offline, zero re-extraction (SC-002)
    ds = load(tmp_path, "2.0.0")
    assert len(ds) == 1
    X = ds.assemble(lambda b: b["hidden_answer_pos"].mean())
    assert X.shape == (1, 1)
