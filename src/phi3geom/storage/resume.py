"""Resilient resume over the CaptureBundle cache (SP-0, T050/T050a).

Reads what was *actually persisted* (the v1 bug was that ``restore_from_branch``
read an uncommitted path → 0 restored). A fresh run scans the bundle cache, treats
events that have all required sidecars as done (skip), and recomputes only the
incomplete (partially-written / interrupted) ones — so an interruption loses no
committed event (FR-019). Adding a new (model, corpus) leaves existing bundles
untouched (FR-020).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

# Default "complete event" requirement: the identifier + label sidecars. Callers
# extend with the array set their capture writes.
DEFAULT_REQUIRED_JSON: tuple[str, ...] = ("meta", "label")


def iter_event_dirs(cache_root: str | Path, capture_version: str) -> Iterator[Path]:
    """Yield every event directory under a ``capture_version`` (has ``meta.json``)."""
    base = Path(cache_root) / capture_version
    if not base.exists():
        return
    for meta in base.rglob("meta.json"):
        yield meta.parent


def is_event_complete(
    event_dir: Path,
    *,
    required_arrays: tuple[str, ...] = (),
    required_json: tuple[str, ...] = DEFAULT_REQUIRED_JSON,
) -> bool:
    """True iff every required array (``.npy`` + ``.header.json``) and JSON sidecar
    is present — i.e. the event was fully written, not interrupted mid-write."""
    for name in required_arrays:
        if not (event_dir / f"{name}.npy").is_file():
            return False
        if not (event_dir / f"{name}.header.json").is_file():
            return False
    for name in required_json:
        if not (event_dir / f"{name}.json").is_file():
            return False
    return True


def list_complete_events(
    cache_root: str | Path,
    capture_version: str,
    *,
    required_arrays: tuple[str, ...] = (),
    required_json: tuple[str, ...] = DEFAULT_REQUIRED_JSON,
) -> list[Path]:
    """Event dirs that are fully persisted — the resume "skip" set."""
    return [
        d
        for d in iter_event_dirs(cache_root, capture_version)
        if is_event_complete(d, required_arrays=required_arrays, required_json=required_json)
    ]


def list_incomplete_events(
    cache_root: str | Path,
    capture_version: str,
    *,
    required_arrays: tuple[str, ...] = (),
    required_json: tuple[str, ...] = DEFAULT_REQUIRED_JSON,
) -> list[Path]:
    """Event dirs that exist but are missing a required file — the "recompute" set."""
    return [
        d
        for d in iter_event_dirs(cache_root, capture_version)
        if not is_event_complete(
            d, required_arrays=required_arrays, required_json=required_json
        )
    ]
