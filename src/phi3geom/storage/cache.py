"""F / D / F_summary tensor cache (contracts/cache.md).

Layout:

    cache/{event_id_prefix}/{event_id}/
        F.npy + F.header.json
        D.npy + D.header.json
        F_summary.npy + F_summary.header.json

Constitution Principle IV's float64-in-the-seam rule applies upstream: this
module is the **cache boundary** where downcasting to float32 is permitted.
Inputs to ``write_*`` are required to be float64; we downcast inside.

Constitution Principle I's content-hash rule: every cache file has a sidecar
``.header.json`` with the manifest SHA at write time. ``read_*`` verifies
the SHA matches the caller's expected value and raises ``CacheStaleError``
on mismatch (no silent fallback).
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import os
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from phi3geom.dataset.types import DocQAEvent
from phi3geom.geometry import FEATURE_NAMES

SCHEMA_VERSION = "1.0.0"

# Lookback indices for the D tensor (log-spaced, from contracts/cache.md).
D_LOOKBACK_INDICES: tuple[int, ...] = (0, 1, 2, 4, 8, 16, 32, 64, 128, 256)


class CacheStaleError(Exception):
    """Cache file's recorded manifest SHA does not match the caller's expected SHA."""


class CacheSchemaError(Exception):
    """Cache file's shape, dtype, or header schema doesn't match expectations."""


class CacheConfigDriftError(Exception):
    """Cache file's recorded study-wide constants disagree with the manifest."""


@dataclass(frozen=True, slots=True)
class CacheHeader:
    """Sidecar header recording provenance for one cache .npy file."""

    schema_version: str
    manifest_sha256: str
    code_commit_sha: str
    tensor_shape: tuple[int, ...]
    tensor_dtype: str
    k_grass: int
    k_attn: int
    lookback_window_length: int
    forman_ricci_convention: str
    write_timestamp_utc: str
    host: str
    # F and F_summary include feature_layout; D omits it (no feature axis).
    feature_layout: tuple[str, ...] | None = None
    # D includes lookback_indices; F omits it.
    lookback_indices: tuple[int, ...] | None = None


# Expected shapes for each cache tensor kind.
F_SHAPE: tuple[int, ...] = (256, 32, 32, 7)
D_SHAPE: tuple[int, ...] = (10, 32, 32, 32, 2)
F_SUMMARY_SHAPE: tuple[int, ...] = (32, 32, 7, 5)


def _event_dir(event_id: str, cache_root: Path) -> Path:
    return cache_root / event_id[:2] / event_id


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _now_utc_iso() -> str:
    return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _header_to_dict(header: CacheHeader) -> dict[str, Any]:
    raw = dataclasses.asdict(header)
    raw["tensor_shape"] = list(header.tensor_shape)
    if header.feature_layout is not None:
        raw["feature_layout"] = list(header.feature_layout)
    if header.lookback_indices is not None:
        raw["lookback_indices"] = list(header.lookback_indices)
    return raw


def _dict_to_header(raw: dict[str, Any]) -> CacheHeader:
    raw = dict(raw)  # copy
    raw["tensor_shape"] = tuple(raw["tensor_shape"])
    if raw.get("feature_layout") is not None:
        raw["feature_layout"] = tuple(raw["feature_layout"])
    if raw.get("lookback_indices") is not None:
        raw["lookback_indices"] = tuple(raw["lookback_indices"])
    return CacheHeader(**raw)


def _write_tensor_and_header(
    npy_path: Path,
    header_path: Path,
    tensor: np.ndarray,
    header: CacheHeader,
) -> None:
    # Write .npy via numpy's atomic-ish save (write+rename). Pass an open
    # file object — np.save appends ".npy" to *string/Path* targets that
    # don't already end in .npy, which would corrupt the temp filename.
    tmp_npy = npy_path.with_suffix(".npy.tmp")
    with open(tmp_npy, "wb") as fh:
        np.save(fh, tensor, allow_pickle=False)
    os.replace(tmp_npy, npy_path)
    header_bytes = json.dumps(_header_to_dict(header), sort_keys=True, indent=2).encode(
        "utf-8"
    )
    _atomic_write_bytes(header_path, header_bytes)


def _read_header(header_path: Path) -> CacheHeader:
    if not header_path.exists():
        raise CacheSchemaError(f"Header file missing: {header_path}")
    raw = json.loads(header_path.read_bytes())
    return _dict_to_header(raw)


def _verify_header_against_caller(
    header: CacheHeader,
    expected_manifest_sha256: str,
    expected_shape: tuple[int, ...],
) -> None:
    if header.manifest_sha256 != expected_manifest_sha256:
        raise CacheStaleError(
            f"Cache SHA mismatch: header={header.manifest_sha256}, "
            f"expected={expected_manifest_sha256}. Regenerate cache or rewind manifest."
        )
    if header.tensor_shape != expected_shape:
        raise CacheSchemaError(
            f"Cache shape mismatch: header={header.tensor_shape}, expected={expected_shape}"
        )


# ---------------------------------------------------------------------------
# F tensor (per-atomic-unit features over the lookback window)
# ---------------------------------------------------------------------------

def write_F(
    event_id: str,
    F: np.ndarray,
    *,
    manifest_sha256: str,
    code_commit_sha: str,
    k_attn: int,
    cache_root: Path,
    forman_ricci_convention: str = "nan_with_median_imputation_and_indicator",
) -> Path:
    """Write F.npy (downcast to float32) + sidecar header.

    Args:
        event_id: Primary key.
        F: float64 array of shape ``F_SHAPE = (256, 32, 32, 7)``.
        manifest_sha256: Dataset manifest SHA at write time.
        code_commit_sha: ``git rev-parse HEAD`` at write time.
        k_attn: Pinned k_attn from the manifest.
        cache_root: Root directory of the cache tree.
        forman_ricci_convention: Recorded in header for replay.

    Returns:
        Path to the event's cache directory.

    Raises:
        TypeError: If ``F.dtype != float64``.
        ValueError: If ``F.shape != F_SHAPE``.
    """
    if F.dtype != np.float64:
        raise TypeError(
            f"write_F expects float64 input (Principle IV); got {F.dtype}."
        )
    if F.shape != F_SHAPE:
        raise ValueError(f"F shape must be {F_SHAPE}; got {F.shape}")

    event_dir = _event_dir(event_id, cache_root)
    event_dir.mkdir(parents=True, exist_ok=True)
    F32 = F.astype(np.float32)
    header = CacheHeader(
        schema_version=SCHEMA_VERSION,
        manifest_sha256=manifest_sha256,
        code_commit_sha=code_commit_sha,
        tensor_shape=F_SHAPE,
        tensor_dtype="float32",
        k_grass=8,
        k_attn=k_attn,
        lookback_window_length=256,
        feature_layout=FEATURE_NAMES,
        forman_ricci_convention=forman_ricci_convention,
        write_timestamp_utc=_now_utc_iso(),
        host=socket.gethostname(),
    )
    _write_tensor_and_header(event_dir / "F.npy", event_dir / "F.header.json", F32, header)
    return event_dir


def read_F(
    event_id: str,
    *,
    expected_manifest_sha256: str,
    cache_root: Path,
) -> np.ndarray:
    """Read F.npy after verifying header.manifest_sha256 matches.

    Raises:
        CacheStaleError: SHA mismatch.
        CacheSchemaError: Shape/dtype mismatch.
    """
    event_dir = _event_dir(event_id, cache_root)
    header = _read_header(event_dir / "F.header.json")
    _verify_header_against_caller(header, expected_manifest_sha256, F_SHAPE)
    arr = np.load(event_dir / "F.npy", allow_pickle=False)
    if arr.dtype != np.float32:
        raise CacheSchemaError(
            f"F.npy dtype expected float32; got {arr.dtype}"
        )
    if arr.shape != F_SHAPE:
        raise CacheSchemaError(f"F.npy shape expected {F_SHAPE}; got {arr.shape}")
    return arr


# ---------------------------------------------------------------------------
# D tensor (pairwise head-head distances at log-spaced lookback)
# ---------------------------------------------------------------------------

def write_D(
    event_id: str,
    D: np.ndarray,
    *,
    manifest_sha256: str,
    code_commit_sha: str,
    k_attn: int,
    cache_root: Path,
) -> Path:
    """Write D.npy (downcast to float32) + sidecar header."""
    if D.dtype != np.float64:
        raise TypeError(f"write_D expects float64; got {D.dtype}.")
    if D.shape != D_SHAPE:
        raise ValueError(f"D shape must be {D_SHAPE}; got {D.shape}")

    event_dir = _event_dir(event_id, cache_root)
    event_dir.mkdir(parents=True, exist_ok=True)
    D32 = D.astype(np.float32)
    header = CacheHeader(
        schema_version=SCHEMA_VERSION,
        manifest_sha256=manifest_sha256,
        code_commit_sha=code_commit_sha,
        tensor_shape=D_SHAPE,
        tensor_dtype="float32",
        k_grass=8,
        k_attn=k_attn,
        lookback_window_length=256,
        lookback_indices=D_LOOKBACK_INDICES,
        forman_ricci_convention="n/a (D has no Ricci slot)",
        write_timestamp_utc=_now_utc_iso(),
        host=socket.gethostname(),
    )
    _write_tensor_and_header(event_dir / "D.npy", event_dir / "D.header.json", D32, header)
    return event_dir


def read_D(
    event_id: str,
    *,
    expected_manifest_sha256: str,
    cache_root: Path,
) -> np.ndarray:
    """Read D.npy after SHA verification."""
    event_dir = _event_dir(event_id, cache_root)
    header = _read_header(event_dir / "D.header.json")
    _verify_header_against_caller(header, expected_manifest_sha256, D_SHAPE)
    arr = np.load(event_dir / "D.npy", allow_pickle=False)
    if arr.dtype != np.float32:
        raise CacheSchemaError(f"D.npy dtype expected float32; got {arr.dtype}")
    if arr.shape != D_SHAPE:
        raise CacheSchemaError(f"D.npy shape expected {D_SHAPE}; got {arr.shape}")
    return arr


# ---------------------------------------------------------------------------
# F_summary tensor (out-of-lookback per-(ℓ, h, feature) summaries)
# ---------------------------------------------------------------------------

def write_F_summary(
    event_id: str,
    F_summary: np.ndarray,
    *,
    manifest_sha256: str,
    code_commit_sha: str,
    k_attn: int,
    cache_root: Path,
) -> Path:
    """Write F_summary.npy (downcast) + sidecar header."""
    if F_summary.dtype != np.float64:
        raise TypeError(f"write_F_summary expects float64; got {F_summary.dtype}.")
    if F_summary.shape != F_SUMMARY_SHAPE:
        raise ValueError(
            f"F_summary shape must be {F_SUMMARY_SHAPE}; got {F_summary.shape}"
        )

    event_dir = _event_dir(event_id, cache_root)
    event_dir.mkdir(parents=True, exist_ok=True)
    arr32 = F_summary.astype(np.float32)
    header = CacheHeader(
        schema_version=SCHEMA_VERSION,
        manifest_sha256=manifest_sha256,
        code_commit_sha=code_commit_sha,
        tensor_shape=F_SUMMARY_SHAPE,
        tensor_dtype="float32",
        k_grass=8,
        k_attn=k_attn,
        lookback_window_length=256,
        feature_layout=FEATURE_NAMES,
        forman_ricci_convention="nan_with_median_imputation_and_indicator",
        write_timestamp_utc=_now_utc_iso(),
        host=socket.gethostname(),
    )
    _write_tensor_and_header(
        event_dir / "F_summary.npy",
        event_dir / "F_summary.header.json",
        arr32,
        header,
    )
    return event_dir


def read_F_summary(
    event_id: str,
    *,
    expected_manifest_sha256: str,
    cache_root: Path,
) -> np.ndarray:
    """Read F_summary.npy after SHA verification."""
    event_dir = _event_dir(event_id, cache_root)
    header = _read_header(event_dir / "F_summary.header.json")
    _verify_header_against_caller(header, expected_manifest_sha256, F_SUMMARY_SHAPE)
    arr = np.load(event_dir / "F_summary.npy", allow_pickle=False)
    if arr.dtype != np.float32:
        raise CacheSchemaError(
            f"F_summary.npy dtype expected float32; got {arr.dtype}"
        )
    if arr.shape != F_SUMMARY_SHAPE:
        raise CacheSchemaError(
            f"F_summary.npy shape expected {F_SUMMARY_SHAPE}; got {arr.shape}"
        )
    return arr


# ---------------------------------------------------------------------------
# Per-event metadata (event.json — labels + identifiers for resume-from-cache)
# ---------------------------------------------------------------------------

def write_event_metadata(
    event_id: str,
    event: DocQAEvent,
    *,
    cache_root: Path,
) -> Path:
    """Write ``event.json`` next to F.npy/D.npy/F_summary.npy.

    Carries the post-extraction event state (model_generation, is_fail,
    measured evidence_distance_tokens, plus the generation-time fields).
    Lets a fresh pod reconstruct the labeled event from cache, the
    foundation of the resume-from-cache path.
    """
    if event_id != event.event_id:
        raise ValueError(
            f"event_id mismatch: arg={event_id!r}, event.event_id={event.event_id!r}"
        )
    event_dir = _event_dir(event_id, cache_root)
    event_dir.mkdir(parents=True, exist_ok=True)
    body = json.dumps(
        dataclasses.asdict(event), indent=2, sort_keys=True
    ).encode("utf-8")
    path = event_dir / "event.json"
    _atomic_write_bytes(path, body)
    return path


def read_event_metadata(
    event_id: str,
    *,
    cache_root: Path,
) -> DocQAEvent:
    """Read ``event.json`` and reconstruct the labeled :class:`DocQAEvent`.

    Raises:
        FileNotFoundError: ``event.json`` not present at the expected path.
    """
    event_dir = _event_dir(event_id, cache_root)
    raw = json.loads((event_dir / "event.json").read_bytes())
    return DocQAEvent(**raw)


def try_load_cached_event(
    event_id: str,
    *,
    cache_root: Path,
) -> DocQAEvent | None:
    """Resume contract: return the labeled event iff both summary + json exist.

    An event is "resumable from cache" only when **both** ``F_summary.npy``
    (the feature input the pooled detector reads) **and** ``event.json``
    (the post-extraction label + measured distance) are present. If either
    is missing, returns ``None`` so the caller re-runs extraction.

    Note: we deliberately do NOT validate the F_summary header here. Header
    verification happens later, when ``_build_feature_matrix`` reads it; if
    the cache is stale, that path raises ``CacheStaleError`` with full
    context. Keeping this check cheap means a fresh-pod resume doesn't
    re-read 900 ``.npy`` files just to decide what to skip.
    """
    event_dir = _event_dir(event_id, cache_root)
    if not (event_dir / "F_summary.npy").is_file():
        return None
    if not (event_dir / "event.json").is_file():
        return None
    return read_event_metadata(event_id, cache_root=cache_root)
