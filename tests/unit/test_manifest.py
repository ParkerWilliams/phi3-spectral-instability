"""Tests for ``phi3geom.dataset.manifest`` (FR-011, contracts/manifest.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from phi3geom.dataset.manifest import (
    ManifestIntegrityError,
    ManifestSchemaError,
    compute_event_id,
    read_manifest,
    verify_event_id,
    write_manifest,
)
from phi3geom.dataset.types import DocQAEvent, ManifestHeader
from phi3geom.geometry import FEATURE_NAMES


def _header(manifest_sha: str = "0" * 64, events_sha: str = "0" * 64) -> ManifestHeader:
    return ManifestHeader(
        schema_version="1.0.0",
        manifest_sha256=manifest_sha,
        events_sha256=events_sha,
        code_commit_sha="a" * 40,
        model_revision_sha="b" * 40,
        prompt_template_sha256="c" * 64,
        generation_config_sha256="d" * 64,
        k_grass=8,
        k_attn=16,
        lookback_window_length=256,
        feature_layout=FEATURE_NAMES,
        forman_ricci_convention="nan_with_median_imputation_and_indicator",
        adversariality_policy_per_bin={
            "B1": "lexical",
            "B2": "none",
            "B3": "none",
            "B4": "none",
            "B5": "none",
            "B6": "none",
        },
        split_seed=123,
        matching_seed_per_bin={
            "B1": 11, "B2": 22, "B3": 33, "B4": 44, "B5": 55, "B6": 66,
        },
        constitution_version="1.0.0",
        spec_version="001",
        write_timestamp_utc="2026-05-19T00:00:00Z",
    )


def _event(seq: int = 1) -> DocQAEvent:
    template_sha = "c" * 64
    eid = compute_event_id(
        prompt_template_sha256=template_sha,
        document=f"doc{seq}",
        question=f"q{seq}?",
        gold_answer=f"gold{seq}",
    )
    return DocQAEvent(
        event_id=eid,
        document=f"doc{seq}",
        question=f"q{seq}?",
        gold_answer=f"gold{seq}",
        question_template_id="tplA",
        evidence_position_token_idx=10,
        evidence_distance_tokens=600,
        bin_id="B3",
        distractor_density=0.3,
        distractor_density_coarsening="low",
        gold_answer_length_tokens=2,
        gold_answer_length_coarsening="2-3",
        cem_stratum_id="tplA|low|2-3",
        adversariality_policy="none",
        model_generation=f"gen{seq}",
        model_generation_normalized=f"gen{seq}",
        gold_answer_normalized=f"gold{seq}",
        is_fail=(seq % 2 == 0),
        per_event_seed=seq * 100,
    )


def test_compute_event_id_is_deterministic() -> None:
    eid1 = compute_event_id(
        prompt_template_sha256="c" * 64, document="d", question="q", gold_answer="g"
    )
    eid2 = compute_event_id(
        prompt_template_sha256="c" * 64, document="d", question="q", gold_answer="g"
    )
    assert eid1 == eid2
    assert len(eid1) == 64


def test_verify_event_id_round_trip() -> None:
    e = _event(seq=1)
    assert verify_event_id(e, prompt_template_sha256="c" * 64)


def test_write_then_read_round_trip(tmp_path: Path) -> None:
    events = [_event(i) for i in range(1, 4)]
    final_header = write_manifest(events, _header(), tmp_path)
    assert len(final_header.manifest_sha256) == 64
    assert len(final_header.events_sha256) == 64

    read_header, read_events = read_manifest(tmp_path)
    assert read_header.manifest_sha256 == final_header.manifest_sha256
    assert read_header.events_sha256 == final_header.events_sha256
    assert read_header.feature_layout == FEATURE_NAMES
    assert [e.event_id for e in read_events] == [e.event_id for e in events]
    # Text fields should round-trip too
    for orig, got in zip(events, read_events, strict=True):
        assert got.document == orig.document
        assert got.question == orig.question
        assert got.gold_answer == orig.gold_answer
        assert got.model_generation == orig.model_generation


def test_sha_integrity_failure_on_manifest_tampering(tmp_path: Path) -> None:
    events = [_event(i) for i in range(1, 4)]
    write_manifest(events, _header(), tmp_path)
    # Tamper with manifest.jsonl
    manifest_path = tmp_path / "manifest.jsonl"
    data = manifest_path.read_bytes()
    manifest_path.write_bytes(data.replace(b"tplA", b"tplB"))

    with pytest.raises(ManifestIntegrityError, match="manifest.jsonl SHA mismatch"):
        read_manifest(tmp_path)


def test_sha_integrity_failure_on_events_tampering(tmp_path: Path) -> None:
    events = [_event(i) for i in range(1, 4)]
    write_manifest(events, _header(), tmp_path)
    events_path = tmp_path / "events.jsonl"
    data = events_path.read_bytes()
    events_path.write_bytes(data.replace(b"doc1", b"doc9"))

    with pytest.raises(ManifestIntegrityError, match="events.jsonl SHA mismatch"):
        read_manifest(tmp_path)


def test_header_missing_field_raises(tmp_path: Path) -> None:
    events = [_event(i) for i in range(1, 4)]
    write_manifest(events, _header(), tmp_path)
    header_path = tmp_path / "manifest_header.json"
    import json
    header = json.loads(header_path.read_bytes())
    del header["k_grass"]
    header_path.write_bytes(json.dumps(header).encode())

    with pytest.raises(ManifestSchemaError, match="k_grass"):
        read_manifest(tmp_path)


def test_event_id_reproducibility_across_serialization(tmp_path: Path) -> None:
    events = [_event(i) for i in range(1, 6)]
    write_manifest(events, _header(), tmp_path)
    _, read_events = read_manifest(tmp_path)
    for e in read_events:
        assert verify_event_id(e, prompt_template_sha256="c" * 64)
