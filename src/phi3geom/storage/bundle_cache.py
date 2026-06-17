"""CaptureBundle storage (SP-0, T004/T009).

The v2 cache, keyed by ``(capture_version, model_id, corpus_id, event_id)`` and
parallel to the v1 F/D/F_summary cache (which is retained). Each stored array
carries a sidecar header; ``read_array`` raises ``CaptureStaleError`` on a
``capture_version`` OR ``manifest_sha256`` mismatch — no silent fallback
(contracts/cache-storage.md; FR-017/FR-018). Float64 is never stored (Constitution
IV: the cache boundary holds fp16/fp32 only).

Layout::

    cache/<capture_version>/<safe_model_id>/<corpus_id>/<prefix>/<event_id>/
        <array>.npy + <array>.header.json
        label.json  meta.json  event.json  samples.json
"""

from __future__ import annotations

import dataclasses
import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from phi3geom.storage.cache import _atomic_write_bytes, _now_utc_iso

CAPTURE_VERSION_DEFAULT = "2.0.0"
_STORE_DTYPES: tuple[str, ...] = ("float16", "float32")


class CaptureStaleError(Exception):
    """Bundle header capture_version or manifest_sha256 disagrees with the caller."""


class CaptureSchemaError(Exception):
    """Bundle array dtype/shape or header is malformed/missing."""


@dataclass(frozen=True, slots=True)
class BundleHeader:
    capture_version: str
    manifest_sha256: str
    code_commit_sha: str
    model_id: str
    revision_sha: str
    corpus_id: str
    array_name: str
    tensor_shape: tuple[int, ...]
    tensor_dtype: str
    created_at: str
    host: str


def safe_model_id(model_id: str) -> str:
    """Filesystem-safe form of an HF id (``org/name`` → ``org__name``)."""
    return model_id.replace("/", "__")


def bundle_dir(
    cache_root: str | Path,
    capture_version: str,
    model_id: str,
    corpus_id: str,
    event_id: str,
) -> Path:
    return (
        Path(cache_root)
        / capture_version
        / safe_model_id(model_id)
        / corpus_id
        / event_id[:2]
        / event_id
    )


def write_array(
    cache_root: str | Path,
    *,
    capture_version: str,
    model_id: str,
    revision_sha: str,
    corpus_id: str,
    event_id: str,
    name: str,
    array: np.ndarray,
    manifest_sha256: str,
    code_commit_sha: str,
) -> Path:
    """Write one named bundle array (fp16/fp32) + sidecar header. Returns the dir."""
    if array.dtype.name not in _STORE_DTYPES:
        raise CaptureSchemaError(
            f"bundle arrays store {_STORE_DTYPES} at the cache boundary "
            f"(Constitution IV); got {array.dtype}"
        )
    d = bundle_dir(cache_root, capture_version, model_id, corpus_id, event_id)
    d.mkdir(parents=True, exist_ok=True)
    header = BundleHeader(
        capture_version=capture_version,
        manifest_sha256=manifest_sha256,
        code_commit_sha=code_commit_sha,
        model_id=model_id,
        revision_sha=revision_sha,
        corpus_id=corpus_id,
        array_name=name,
        tensor_shape=tuple(int(x) for x in array.shape),
        tensor_dtype=array.dtype.name,
        created_at=_now_utc_iso(),
        host=socket.gethostname(),
    )
    npy = d / f"{name}.npy"
    tmp = npy.with_suffix(".npy.tmp")
    with open(tmp, "wb") as fh:
        np.save(fh, array, allow_pickle=False)
    os.replace(tmp, npy)
    raw = dataclasses.asdict(header)
    raw["tensor_shape"] = list(header.tensor_shape)
    _atomic_write_bytes(
        d / f"{name}.header.json", json.dumps(raw, sort_keys=True, indent=2).encode("utf-8")
    )
    return d


def read_array(
    cache_root: str | Path,
    *,
    capture_version: str,
    model_id: str,
    corpus_id: str,
    event_id: str,
    name: str,
    expected_manifest_sha256: str,
) -> np.ndarray:
    """Read one named bundle array after capture_version + manifest-SHA checks."""
    d = bundle_dir(cache_root, capture_version, model_id, corpus_id, event_id)
    hp = d / f"{name}.header.json"
    if not hp.exists():
        raise CaptureSchemaError(f"missing bundle header: {hp}")
    raw = json.loads(hp.read_bytes())
    if raw["capture_version"] != capture_version:
        raise CaptureStaleError(
            f"capture_version mismatch for {name}: header={raw['capture_version']}, "
            f"expected={capture_version}"
        )
    if raw["manifest_sha256"] != expected_manifest_sha256:
        raise CaptureStaleError(
            f"manifest SHA mismatch for {name}: header={raw['manifest_sha256']}, "
            f"expected={expected_manifest_sha256}"
        )
    arr = np.load(d / f"{name}.npy", allow_pickle=False)
    if tuple(arr.shape) != tuple(raw["tensor_shape"]):
        raise CaptureSchemaError(
            f"{name}.npy shape {arr.shape} != header {tuple(raw['tensor_shape'])}"
        )
    return arr


def write_json(
    cache_root: str | Path,
    *,
    capture_version: str,
    model_id: str,
    corpus_id: str,
    event_id: str,
    name: str,
    obj: Any,
) -> Path:
    """Write a JSON sidecar (e.g. ``label``, ``meta``, ``event``, ``samples``)."""
    d = bundle_dir(cache_root, capture_version, model_id, corpus_id, event_id)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.json"
    _atomic_write_bytes(p, json.dumps(obj, sort_keys=True, indent=2).encode("utf-8"))
    return p


def read_json(
    cache_root: str | Path,
    *,
    capture_version: str,
    model_id: str,
    corpus_id: str,
    event_id: str,
    name: str,
) -> Any:
    d = bundle_dir(cache_root, capture_version, model_id, corpus_id, event_id)
    return json.loads((d / f"{name}.json").read_bytes())
