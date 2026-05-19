"""Dataset manifest I/O with SHA-pinned provenance (Constitution Principle I).

Three files written atomically per run:

    dataset/manifest_header.json   # study-wide pins + SHAs
    dataset/manifest.jsonl         # scalar index, one line per event
    dataset/events.jsonl           # full text fields, one line per event

The SHA of ``manifest.jsonl`` is recorded in the header AFTER ``manifest.jsonl``
is finalized. The header is the LAST file written. All writes are atomic via
``tmpfile + os.rename``.

See ``specs/001-phi3-attention-geometry-v1/contracts/manifest.md`` for the
authoritative schema.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from phi3geom.dataset.types import DocQAEvent, ManifestHeader

SCHEMA_VERSION = "1.0.0"

_HEADER_FILENAME = "manifest_header.json"
_MANIFEST_FILENAME = "manifest.jsonl"
_EVENTS_FILENAME = "events.jsonl"


class ManifestIntegrityError(Exception):
    """Recorded SHA does not match the recomputed SHA of the on-disk file."""


class ManifestSchemaError(Exception):
    """Manifest header is missing a required field or has the wrong type."""


# Fields that live in events.jsonl (full text) — kept out of the scannable
# manifest.jsonl to keep that file lightweight.
_EVENT_TEXT_FIELDS = ("document", "question", "gold_answer", "model_generation")


def _event_to_manifest_record(event: DocQAEvent) -> dict[str, Any]:
    """Convert a ``DocQAEvent`` to its ``manifest.jsonl`` line dict."""
    record = dataclasses.asdict(event)
    for field_name in _EVENT_TEXT_FIELDS:
        record.pop(field_name, None)
    return record


def _event_to_events_record(event: DocQAEvent) -> dict[str, Any]:
    """Convert a ``DocQAEvent`` to its ``events.jsonl`` line dict."""
    return {
        "event_id": event.event_id,
        "document": event.document,
        "question": event.question,
        "gold_answer": event.gold_answer,
        "model_generation_raw": event.model_generation,
    }


def compute_event_id(
    *,
    prompt_template_sha256: str,
    document: str,
    question: str,
    gold_answer: str,
) -> str:
    """Canonical event_id derivation.

    ``event_id = SHA256(prompt_template_sha ‖ document ‖ question ‖ gold)``
    where ‖ is byte concatenation of UTF-8 encodings.
    """
    h = hashlib.sha256()
    h.update(prompt_template_sha256.encode("utf-8"))
    h.update(document.encode("utf-8"))
    h.update(question.encode("utf-8"))
    h.update(gold_answer.encode("utf-8"))
    return h.hexdigest()


def verify_event_id(event: DocQAEvent, prompt_template_sha256: str) -> bool:
    """Return True iff ``event.event_id`` matches the canonical derivation."""
    expected = compute_event_id(
        prompt_template_sha256=prompt_template_sha256,
        document=event.document,
        question=event.question,
        gold_answer=event.gold_answer,
    )
    return event.event_id == expected


def _sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write_manifest(
    events: list[DocQAEvent],
    header: ManifestHeader,
    out_dir: Path,
) -> ManifestHeader:
    """Write ``events.jsonl``, ``manifest.jsonl``, ``manifest_header.json``
    atomically. Returns a header with the final SHAs filled in.

    Note: the caller-provided ``header.manifest_sha256`` and
    ``header.events_sha256`` are ignored — they are overwritten with the
    actual SHAs computed from the on-disk bytes.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. events.jsonl
    events_lines = [
        json.dumps(_event_to_events_record(e), sort_keys=True, ensure_ascii=False)
        for e in events
    ]
    events_bytes = ("\n".join(events_lines) + "\n").encode("utf-8") if events else b""
    _atomic_write_bytes(out_dir / _EVENTS_FILENAME, events_bytes)
    events_sha = _sha256_of_bytes(events_bytes)

    # 2. manifest.jsonl
    manifest_lines = [
        json.dumps(_event_to_manifest_record(e), sort_keys=True, ensure_ascii=False)
        for e in events
    ]
    manifest_bytes = (
        ("\n".join(manifest_lines) + "\n").encode("utf-8") if events else b""
    )
    _atomic_write_bytes(out_dir / _MANIFEST_FILENAME, manifest_bytes)
    manifest_sha = _sha256_of_bytes(manifest_bytes)

    # 3. header
    final_header = dataclasses.replace(
        header,
        manifest_sha256=manifest_sha,
        events_sha256=events_sha,
    )
    header_dict = dataclasses.asdict(final_header)
    # tuples → lists for JSON serializability
    header_dict["feature_layout"] = list(final_header.feature_layout)
    header_bytes = json.dumps(header_dict, sort_keys=True, indent=2).encode("utf-8")
    _atomic_write_bytes(out_dir / _HEADER_FILENAME, header_bytes)

    return final_header


def _read_header(path: Path) -> ManifestHeader:
    raw = json.loads(path.read_bytes())
    required = {
        "schema_version",
        "manifest_sha256",
        "events_sha256",
        "code_commit_sha",
        "model_revision_sha",
        "prompt_template_sha256",
        "generation_config_sha256",
        "k_grass",
        "k_attn",
        "lookback_window_length",
        "feature_layout",
        "forman_ricci_convention",
        "adversariality_policy_per_bin",
        "split_seed",
        "matching_seed_per_bin",
        "constitution_version",
        "spec_version",
        "write_timestamp_utc",
    }
    missing = required - set(raw.keys())
    if missing:
        raise ManifestSchemaError(f"manifest_header.json missing fields: {sorted(missing)}")
    raw["feature_layout"] = tuple(raw["feature_layout"])
    return ManifestHeader(**raw)


def read_manifest(in_dir: Path) -> tuple[ManifestHeader, list[DocQAEvent]]:
    """Read header + events back from disk; verify SHAs match.

    Raises:
        ManifestIntegrityError: SHA mismatch detected. Treat as corruption
            or accidental cross-run mixing.
        ManifestSchemaError: Header missing a required field.
    """
    header = _read_header(in_dir / _HEADER_FILENAME)

    events_bytes = (in_dir / _EVENTS_FILENAME).read_bytes()
    if _sha256_of_bytes(events_bytes) != header.events_sha256:
        raise ManifestIntegrityError(
            f"events.jsonl SHA mismatch in {in_dir}: header says "
            f"{header.events_sha256}, recomputed {_sha256_of_bytes(events_bytes)}"
        )

    manifest_bytes = (in_dir / _MANIFEST_FILENAME).read_bytes()
    if _sha256_of_bytes(manifest_bytes) != header.manifest_sha256:
        raise ManifestIntegrityError(
            f"manifest.jsonl SHA mismatch in {in_dir}: header says "
            f"{header.manifest_sha256}, recomputed {_sha256_of_bytes(manifest_bytes)}"
        )

    events_by_id: dict[str, dict[str, Any]] = {}
    for line in events_bytes.decode("utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        events_by_id[rec["event_id"]] = rec

    events: list[DocQAEvent] = []
    for line in manifest_bytes.decode("utf-8").splitlines():
        if not line.strip():
            continue
        m = json.loads(line)
        e = events_by_id.get(m["event_id"], {})
        events.append(
            DocQAEvent(
                event_id=m["event_id"],
                document=e.get("document", ""),
                question=e.get("question", ""),
                gold_answer=e.get("gold_answer", ""),
                question_template_id=m["question_template_id"],
                evidence_position_token_idx=m["evidence_position_token_idx"],
                evidence_distance_tokens=m["evidence_distance_tokens"],
                bin_id=m["bin_id"],
                distractor_density=m["distractor_density"],
                distractor_density_coarsening=m["distractor_density_coarsening"],
                gold_answer_length_tokens=m["gold_answer_length_tokens"],
                gold_answer_length_coarsening=m["gold_answer_length_coarsening"],
                cem_stratum_id=m["cem_stratum_id"],
                adversariality_policy=m["adversariality_policy"],
                model_generation=e.get("model_generation_raw", ""),
                model_generation_normalized=m["model_generation_normalized"],
                gold_answer_normalized=m["gold_answer_normalized"],
                is_fail=m["is_fail"],
                per_event_seed=m["per_event_seed"],
            )
        )
    return header, events
