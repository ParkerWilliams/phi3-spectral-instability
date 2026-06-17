"""Resilient-resume + zero-re-extraction tests over the bundle cache (SP-0)."""

import numpy as np

from phi3geom.storage.bundle_cache import bundle_dir, write_array, write_json
from phi3geom.storage.resume import (
    is_event_complete,
    list_complete_events,
    list_incomplete_events,
)

CV = "2.0.0"


def _write_event(root, model, corpus, eid, *, complete=True):
    arr = np.zeros((2, 4), dtype=np.float16)
    write_array(root, capture_version=CV, model_id=model, revision_sha="r",
                corpus_id=corpus, event_id=eid, name="hidden_answer_pos",
                array=arr, manifest_sha256="sha-A", code_commit_sha="c")
    kw = dict(capture_version=CV, model_id=model, corpus_id=corpus, event_id=eid)
    write_json(root, name="meta", obj={"model_id": model, "corpus_id": corpus,
                                       "event_id": eid, "capture_version": CV}, **kw)
    if complete:
        write_json(root, name="label", obj={"class_4way": "correct-answer",
                                            "is_hallucination": False}, **kw)


def test_resume_restores_complete_skips_incomplete(tmp_path):
    _write_event(tmp_path, "org/m1", "hotpotqa", "aa000001", complete=True)
    _write_event(tmp_path, "org/m1", "hotpotqa", "aa000002", complete=True)
    _write_event(tmp_path, "org/m1", "hotpotqa", "aa000003", complete=False)  # interrupted
    complete = list_complete_events(tmp_path, CV)
    incomplete = list_incomplete_events(tmp_path, CV)
    assert len(complete) == 2  # 100% of fully-written events recovered
    assert len(incomplete) == 1  # the interrupted one is flagged for recompute


def test_is_event_complete_requires_arrays_too(tmp_path):
    _write_event(tmp_path, "org/m1", "squad2", "bb000001", complete=True)
    d = bundle_dir(tmp_path, CV, "org/m1", "squad2", "bb000001")
    assert is_event_complete(d, required_arrays=("hidden_answer_pos",))
    # a required array that was never written -> incomplete
    assert not is_event_complete(d, required_arrays=("attn_rows_answer_pos",))


def test_zero_reextraction_adding_model_corpus_leaves_existing_untouched(tmp_path):
    _write_event(tmp_path, "org/m1", "hotpotqa", "cc000001", complete=True)
    existing = bundle_dir(tmp_path, CV, "org/m1", "hotpotqa", "cc000001") / "hidden_answer_pos.npy"
    before = existing.read_bytes()
    # add a different model AND a different corpus
    _write_event(tmp_path, "org/m2", "hotpotqa", "dd000001", complete=True)
    _write_event(tmp_path, "org/m1", "triviaqa_nq", "ee000001", complete=True)
    assert existing.read_bytes() == before  # byte-for-byte unchanged (FR-020/SC-006)
