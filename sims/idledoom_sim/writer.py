"""Output ownership: identity, paths, summary assembly, and schema validation.

The harness owns everything the running game can't do cleanly: UUID ``run_id``,
``batch_id`` resolution, non-colliding output paths (FR-009), ISO-8601 wall-clock
stamps, and JSON Schema validation before exit (SC-002).

US1 scope: ``run_id``/``batch_id``/paths + summary assembly, validation, and
write. The per-event ``.events.jsonl`` writer arrives in US2 (T030).

Reference: contracts/harness-cli.md, contracts/summary.schema.json, data-model.md.
"""

from __future__ import annotations

import json
import uuid
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema

from .config import RunConfig
from .telemetry import SCHEMA_VERSION

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"


def new_run_id() -> str:
    """A fresh unique run identifier (FR-009)."""
    return str(uuid.uuid4())


def resolve_batch_id(batch_id: str | None) -> str:
    """Use the supplied batch id, or mint a single-run batch (R10)."""
    return batch_id if batch_id else str(uuid.uuid4())


def output_paths(out_dir: Path, batch_id: str, run_id: str) -> tuple[Path, Path]:
    """``(summary_path, events_path)`` under ``<out_dir>/<batch_id>/`` (FR-009)."""
    base = out_dir / batch_id
    return base / f"{run_id}.summary.json", base / f"{run_id}.events.jsonl"


@cache
def _load_schema(name: str) -> dict[str, Any]:
    with (_SCHEMA_DIR / name).open() as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def build_summary(
    *,
    run_id: str,
    config: RunConfig,
    started_at: str,
    ended_at: str,
    duration_sec: float,
    outcome: str,
    stats: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the per-run summary dict (FR-004).

    ``config_hash`` and a non-empty ``bot_config`` come straight from
    :class:`RunConfig` — both are schema-required, so US1 cannot emit
    placeholders (C1).
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "batch_id": config.batch_id,
        "config_hash": config.config_hash,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_sec": duration_sec,
        "map": config.map,
        "outcome": outcome,
        "bot_config": dict(config.bot_config),
        "stats": stats,
    }


def validate_summary(summary: dict[str, Any]) -> None:
    """Raise ``jsonschema.ValidationError`` if the summary is non-conforming."""
    jsonschema.validate(summary, _load_schema("summary.schema.json"))


def write_summary(summary: dict[str, Any], path: Path) -> None:
    """Validate (SC-002) then atomically-ish write the summary JSON."""
    validate_summary(summary)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")


def validate_event(record: dict[str, Any]) -> None:
    """Raise ``jsonschema.ValidationError`` if an event record is non-conforming."""
    jsonschema.validate(record, _load_schema("event.schema.json"))


def write_events(records: list[dict[str, Any]], path: Path) -> None:
    """Validate every record (SC-002) then write the events JSONL — one JSON
    object per line. Validation runs first so a bad record never leaves a
    half-written stream on disk (FR-005, FR-012)."""
    for record in records:
        validate_event(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True))
            fh.write("\n")
