"""Tests for ``phi3geom.storage.cache`` (contracts/cache.md, FR-013)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from phi3geom.storage.cache import (
    D_SHAPE,
    F_SHAPE,
    F_SUMMARY_SHAPE,
    CacheSchemaError,
    CacheStaleError,
    read_D,
    read_F,
    read_F_summary,
    write_D,
    write_F,
    write_F_summary,
)


_EVENT_ID = "a1b2c3" + "0" * 58  # 64-hex
_SHA_A = "a" * 64
_SHA_B = "b" * 64
_COMMIT_SHA = "c" * 40
_K_ATTN = 16


def _zeros_F() -> np.ndarray:
    return np.zeros(F_SHAPE, dtype=np.float64)


def _zeros_D() -> np.ndarray:
    return np.zeros(D_SHAPE, dtype=np.float64)


def _zeros_F_summary() -> np.ndarray:
    return np.zeros(F_SUMMARY_SHAPE, dtype=np.float64)


def test_shape_constants_track_feature_count() -> None:
    """F/F_summary last feature axis MUST equal the canonical feature count.

    Guards the coupling that broke silently when norms were added: the tensor
    shapes and ``FEATURE_NAMES`` must move together or extraction mis-shapes.
    """
    from phi3geom.geometry import N_FEATURES

    assert F_SHAPE == (256, 32, 32, N_FEATURES)
    assert F_SUMMARY_SHAPE == (32, 32, N_FEATURES, 5)


# ---------------------------------------------------------------------------
# F: round-trip + downcast tolerance
# ---------------------------------------------------------------------------

def test_write_read_F_round_trip(tmp_path: Path) -> None:
    F = _zeros_F()
    F[0, 0, 0, 0] = 1.234567890123456789
    write_F(
        _EVENT_ID,
        F,
        manifest_sha256=_SHA_A,
        code_commit_sha=_COMMIT_SHA,
        k_attn=_K_ATTN,
        cache_root=tmp_path,
    )
    F_read = read_F(_EVENT_ID, expected_manifest_sha256=_SHA_A, cache_root=tmp_path)
    assert F_read.dtype == np.float32
    assert F_read.shape == F_SHAPE
    # Lossy-but-bounded round trip (float32 quantization).
    assert np.max(np.abs(F.astype(np.float32) - F_read)) <= 1e-6


def test_F_stale_sha_raises(tmp_path: Path) -> None:
    write_F(
        _EVENT_ID,
        _zeros_F(),
        manifest_sha256=_SHA_A,
        code_commit_sha=_COMMIT_SHA,
        k_attn=_K_ATTN,
        cache_root=tmp_path,
    )
    with pytest.raises(CacheStaleError, match="SHA mismatch"):
        read_F(_EVENT_ID, expected_manifest_sha256=_SHA_B, cache_root=tmp_path)


def test_F_rejects_float32_input(tmp_path: Path) -> None:
    F32 = np.zeros(F_SHAPE, dtype=np.float32)
    with pytest.raises(TypeError, match="float64"):
        write_F(
            _EVENT_ID,
            F32,
            manifest_sha256=_SHA_A,
            code_commit_sha=_COMMIT_SHA,
            k_attn=_K_ATTN,
            cache_root=tmp_path,
        )


def test_F_rejects_wrong_shape(tmp_path: Path) -> None:
    F_wrong = np.zeros((128, 32, 32, 7), dtype=np.float64)
    with pytest.raises(ValueError, match="shape"):
        write_F(
            _EVENT_ID,
            F_wrong,
            manifest_sha256=_SHA_A,
            code_commit_sha=_COMMIT_SHA,
            k_attn=_K_ATTN,
            cache_root=tmp_path,
        )


def test_F_corrupted_header_shape_raises(tmp_path: Path) -> None:
    """If someone manually edits the header's tensor_shape, reads detect it."""
    write_F(
        _EVENT_ID,
        _zeros_F(),
        manifest_sha256=_SHA_A,
        code_commit_sha=_COMMIT_SHA,
        k_attn=_K_ATTN,
        cache_root=tmp_path,
    )
    header_path = tmp_path / _EVENT_ID[:2] / _EVENT_ID / "F.header.json"
    h = json.loads(header_path.read_bytes())
    h["tensor_shape"] = [128, 32, 32, 7]  # bogus
    header_path.write_bytes(json.dumps(h).encode())

    with pytest.raises(CacheSchemaError, match="shape"):
        read_F(_EVENT_ID, expected_manifest_sha256=_SHA_A, cache_root=tmp_path)


# ---------------------------------------------------------------------------
# D: round-trip + dtype rejection
# ---------------------------------------------------------------------------

def test_write_read_D_round_trip(tmp_path: Path) -> None:
    write_D(
        _EVENT_ID,
        _zeros_D(),
        manifest_sha256=_SHA_A,
        code_commit_sha=_COMMIT_SHA,
        k_attn=_K_ATTN,
        cache_root=tmp_path,
    )
    D_read = read_D(_EVENT_ID, expected_manifest_sha256=_SHA_A, cache_root=tmp_path)
    assert D_read.dtype == np.float32
    assert D_read.shape == D_SHAPE


def test_D_rejects_float32_input(tmp_path: Path) -> None:
    D32 = np.zeros(D_SHAPE, dtype=np.float32)
    with pytest.raises(TypeError, match="float64"):
        write_D(
            _EVENT_ID,
            D32,
            manifest_sha256=_SHA_A,
            code_commit_sha=_COMMIT_SHA,
            k_attn=_K_ATTN,
            cache_root=tmp_path,
        )


# ---------------------------------------------------------------------------
# F_summary: round-trip
# ---------------------------------------------------------------------------

def test_write_read_F_summary_round_trip(tmp_path: Path) -> None:
    write_F_summary(
        _EVENT_ID,
        _zeros_F_summary(),
        manifest_sha256=_SHA_A,
        code_commit_sha=_COMMIT_SHA,
        k_attn=_K_ATTN,
        cache_root=tmp_path,
    )
    arr = read_F_summary(
        _EVENT_ID, expected_manifest_sha256=_SHA_A, cache_root=tmp_path
    )
    assert arr.shape == F_SUMMARY_SHAPE
    assert arr.dtype == np.float32


# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------

def test_event_directory_uses_prefix(tmp_path: Path) -> None:
    write_F(
        _EVENT_ID,
        _zeros_F(),
        manifest_sha256=_SHA_A,
        code_commit_sha=_COMMIT_SHA,
        k_attn=_K_ATTN,
        cache_root=tmp_path,
    )
    expected_dir = tmp_path / _EVENT_ID[:2] / _EVENT_ID
    assert expected_dir.is_dir()
    assert (expected_dir / "F.npy").is_file()
    assert (expected_dir / "F.header.json").is_file()
