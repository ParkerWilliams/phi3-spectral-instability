"""Per-event metadata cache (`event.json` next to F.npy/D.npy/F_summary.npy).

Carries the post-extraction label fields (model_generation, is_fail,
measured evidence_distance_tokens) so a fresh pod can reconstruct the
labeled event from cache without re-running the model — the foundation of
the resume-from-cache path.
"""
from __future__ import annotations

import pytest

import numpy as np

from phi3geom.dataset.types import DocQAEvent
from phi3geom.storage.cache import (
    F_SUMMARY_SHAPE,
    read_event_metadata,
    try_load_cached_event,
    write_event_metadata,
    write_F_summary,
)


def _toy_event() -> DocQAEvent:
    return DocQAEvent(
        event_id="a" * 64,
        document="The capital of France is Paris.",
        question="What is the capital of France?",
        gold_answer="Paris",
        question_template_id="capital",
        evidence_position_token_idx=4,
        evidence_distance_tokens=200,
        bin_id="B1",
        distractor_density=0.3,
        distractor_density_coarsening="low",
        gold_answer_length_tokens=1,
        gold_answer_length_coarsening="1",
        cem_stratum_id="B1|capital|low|1",
        adversariality_policy="none",
        model_generation="Paris",
        model_generation_normalized="paris",
        gold_answer_normalized="paris",
        is_fail=False,
        per_event_seed=12345,
    )


def test_write_event_metadata_returns_path_under_event_dir(tmp_path):
    event = _toy_event()
    path = write_event_metadata(event.event_id, event, cache_root=tmp_path)
    assert path == tmp_path / event.event_id[:2] / event.event_id / "event.json"
    assert path.is_file()


def test_event_metadata_roundtrip_equal(tmp_path):
    event = _toy_event()
    write_event_metadata(event.event_id, event, cache_root=tmp_path)
    out = read_event_metadata(event.event_id, cache_root=tmp_path)
    assert out == event


def test_write_event_metadata_atomic_no_tmp_leftover(tmp_path):
    event = _toy_event()
    write_event_metadata(event.event_id, event, cache_root=tmp_path)
    event_dir = tmp_path / event.event_id[:2] / event.event_id
    leftovers = list(event_dir.glob("event.json.tmp*"))
    assert leftovers == []


def test_read_event_metadata_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_event_metadata("b" * 64, cache_root=tmp_path)


def test_write_event_metadata_rejects_id_mismatch(tmp_path):
    event = _toy_event()  # event_id = "a"*64
    with pytest.raises(ValueError, match="event_id"):
        write_event_metadata("c" * 64, event, cache_root=tmp_path)


# ---------------------------------------------------------------------------
# Resume contract: try_load_cached_event
# ---------------------------------------------------------------------------

def _write_dummy_f_summary(event_id: str, cache_root):
    write_F_summary(
        event_id,
        np.zeros(F_SUMMARY_SHAPE, dtype=np.float64),
        manifest_sha256="0" * 64,
        code_commit_sha="0" * 40,
        k_attn=16,
        cache_root=cache_root,
    )


def test_try_load_returns_none_when_neither_file_present(tmp_path):
    assert try_load_cached_event("d" * 64, cache_root=tmp_path) is None


def test_try_load_returns_none_when_only_event_json_present(tmp_path):
    event = _toy_event()
    write_event_metadata(event.event_id, event, cache_root=tmp_path)
    assert try_load_cached_event(event.event_id, cache_root=tmp_path) is None


def test_try_load_returns_none_when_only_f_summary_present(tmp_path):
    event = _toy_event()
    _write_dummy_f_summary(event.event_id, tmp_path)
    assert try_load_cached_event(event.event_id, cache_root=tmp_path) is None


def test_try_load_returns_labeled_event_when_both_present(tmp_path):
    event = _toy_event()
    _write_dummy_f_summary(event.event_id, tmp_path)
    write_event_metadata(event.event_id, event, cache_root=tmp_path)
    out = try_load_cached_event(event.event_id, cache_root=tmp_path)
    assert out == event
