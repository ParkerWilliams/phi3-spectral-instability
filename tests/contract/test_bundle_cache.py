"""Contract tests for the CaptureBundle storage layer (SP-0, T004/T009)."""

import json

import numpy as np
import pytest

from phi3geom.storage.bundle_cache import (
    CaptureSchemaError,
    CaptureStaleError,
    bundle_dir,
    read_array,
    write_array,
)

_M = "meta-llama/Meta-Llama-3-8B"  # org-slashed id must round-trip


def _write(tmp_path, *, capture_version="2.0.0", manifest="sha-A"):
    arr = np.arange(32, dtype=np.float16).reshape(4, 8)
    write_array(
        tmp_path, capture_version=capture_version, model_id=_M, revision_sha="rev1",
        corpus_id="hotpotqa", event_id="abcdef01", name="hidden_answer_pos",
        array=arr, manifest_sha256=manifest, code_commit_sha="commit1",
    )
    return arr


def test_write_read_roundtrip_preserves_fp16(tmp_path):
    arr = _write(tmp_path)
    got = read_array(
        tmp_path, capture_version="2.0.0", model_id=_M, corpus_id="hotpotqa",
        event_id="abcdef01", name="hidden_answer_pos", expected_manifest_sha256="sha-A",
    )
    assert got.dtype == np.float16
    assert np.array_equal(got, arr)


def test_org_slashed_model_id_is_sanitized_in_path(tmp_path):
    _write(tmp_path)
    d = bundle_dir(tmp_path, "2.0.0", _M, "hotpotqa", "abcdef01")
    assert d.is_dir()
    assert "__" in str(d) and "/Meta-Llama" not in str(d)


def test_wrong_capture_version_is_isolated_by_path(tmp_path):
    # capture_version keys the directory tree, so a different version simply
    # isn't found (clean isolation; never a silent wrong-version read).
    _write(tmp_path, capture_version="2.0.0")
    with pytest.raises(CaptureSchemaError):
        read_array(
            tmp_path, capture_version="9.9.9", model_id=_M, corpus_id="hotpotqa",
            event_id="abcdef01", name="hidden_answer_pos",
            expected_manifest_sha256="sha-A",
        )


def test_capture_version_guard_catches_tampered_header(tmp_path):
    # Integrity guard: a header whose recorded capture_version disagrees with its
    # directory (a misfiled/tampered bundle) is rejected, not silently trusted.
    _write(tmp_path, capture_version="2.0.0")
    hp = bundle_dir(tmp_path, "2.0.0", _M, "hotpotqa", "abcdef01") / "hidden_answer_pos.header.json"
    raw = json.loads(hp.read_bytes())
    raw["capture_version"] = "1.5.0"
    hp.write_bytes(json.dumps(raw).encode("utf-8"))
    with pytest.raises(CaptureStaleError):
        read_array(
            tmp_path, capture_version="2.0.0", model_id=_M, corpus_id="hotpotqa",
            event_id="abcdef01", name="hidden_answer_pos",
            expected_manifest_sha256="sha-A",
        )


def test_manifest_sha_mismatch_raises(tmp_path):
    _write(tmp_path, manifest="sha-A")
    with pytest.raises(CaptureStaleError):
        read_array(
            tmp_path, capture_version="2.0.0", model_id=_M, corpus_id="hotpotqa",
            event_id="abcdef01", name="hidden_answer_pos",
            expected_manifest_sha256="sha-DIFFERENT",
        )


def test_float64_is_rejected_at_cache_boundary(tmp_path):
    with pytest.raises(CaptureSchemaError):
        write_array(
            tmp_path, capture_version="2.0.0", model_id=_M, revision_sha="r",
            corpus_id="hotpotqa", event_id="abcdef01", name="x",
            array=np.zeros((2, 2), dtype=np.float64),
            manifest_sha256="sha-A", code_commit_sha="c",
        )
