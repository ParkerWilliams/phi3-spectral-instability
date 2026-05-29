"""US1 / SC-002: a produced per-run summary validates against the schema."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from idledoom_sim import writer
from idledoom_sim.config import RunConfig, build_bot_config, compute_config_hash
from idledoom_sim.telemetry import ParsedEvent, aggregate


def _config() -> RunConfig:
    bot = build_bot_config()
    return RunConfig(
        map="lq1m1",
        seed=1,
        time_limit_sec=120.0,
        batch_id=writer.resolve_batch_id(None),
        out_dir=Path("results"),
        bot_config=bot,
        config_hash=compute_config_hash(bot),
    )


def _summary(outcome: str, events: list[ParsedEvent]) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return writer.build_summary(
        run_id=writer.new_run_id(),
        config=_config(),
        started_at=now,
        ended_at=now,
        duration_sec=0.0,
        outcome=outcome,
        stats=aggregate(events),
    )


def test_completed_summary_validates() -> None:
    events = [
        ParsedEvent(0.0, "level_start", {"map": "lq1m1", "seed": 1, "secrets_total": 2}),
        ParsedEvent(42.0, "level_end", {"outcome": "completed", "time_sec": 42.0}),
    ]
    summary = _summary("completed", events)
    writer.validate_summary(summary)  # must not raise
    # G2: secrets_total sourced from level_start; time_to_exit from level_end.
    assert summary["stats"]["secrets_total"] == 2
    assert summary["stats"]["time_to_exit_sec"] == 42.0
    # C1: schema-required 64-hex config_hash is present.
    assert len(summary["config_hash"]) == 64


def test_timeout_summary_with_zero_stats_validates() -> None:
    # Roam-only timeout (no gameplay events yet, US2) still produces a valid summary.
    events = [
        ParsedEvent(0.0, "level_start", {"map": "lq1m1", "seed": 1, "secrets_total": 0}),
        ParsedEvent(120.0, "level_end", {"outcome": "timeout", "time_sec": 120.0}),
    ]
    summary = _summary("timeout", events)
    writer.validate_summary(summary)
    assert summary["stats"]["accuracy"] == 0.0  # zero-denominator -> 0, not error


def test_written_summary_file_roundtrips_and_validates(tmp_path: Path) -> None:
    events = [
        ParsedEvent(0.0, "level_start", {"map": "lq1m1", "seed": 1, "secrets_total": 0}),
        ParsedEvent(5.0, "level_end", {"outcome": "died", "time_sec": 5.0}),
    ]
    summary = _summary("died", events)
    path = tmp_path / "run.summary.json"
    writer.write_summary(summary, path)
    reloaded = json.loads(path.read_text())
    writer.validate_summary(reloaded)
    assert reloaded["outcome"] == "died"


def test_malformed_config_hash_is_rejected() -> None:
    # Proves validation actually bites: a non-hex config_hash must fail (C1).
    summary = _summary("completed", [
        ParsedEvent(0.0, "level_start", {"map": "lq1m1", "seed": 1, "secrets_total": 0}),
        ParsedEvent(1.0, "level_end", {"outcome": "completed", "time_sec": 1.0}),
    ])
    summary["config_hash"] = "not-a-real-hash"
    with pytest.raises(jsonschema.ValidationError):
        writer.validate_summary(summary)
