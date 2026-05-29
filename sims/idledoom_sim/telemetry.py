"""Engine stdout -> events -> aggregated stats.

The QuakeC telemetry layer emits one tagged line per observable event:

    @EVT|<t>|<type>|<k1>=<v1>|<k2>=<v2>|...

``parse_event_line`` turns one such line into a schema-shaped event record;
``parse_stream`` does a whole stdout capture (ignoring non-@EVT log noise, R4);
``aggregate`` folds events into the summary ``stats`` block.

US1 scope: parsing + a complete StatsBlock *skeleton* (all counts default 0,
plus ``secrets_total`` from ``level_start`` and ``time_to_exit_sec`` from a
``completed`` ``level_end`` — G2). US2 (T029) fills in the real per-type counting.

Reference: contracts/engine-event-line.md, data-model.md StatsBlock.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

EVENT_PREFIX = "@EVT|"
SCHEMA_VERSION = 1

EventData = dict[str, Any]


@dataclass(frozen=True)
class ParsedEvent:
    """One parsed telemetry line, before it becomes a schema record."""

    t: float
    type: str
    data: EventData


def _coerce(value: str) -> Any:
    """Coerce a bare payload token to int/float/None/str (per the line contract)."""
    if value == "null":
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def parse_event_line(line: str) -> ParsedEvent | None:
    """Parse one stdout line. Returns ``None`` for any non-telemetry line (R4)."""
    line = line.rstrip("\r\n")
    if not line.startswith(EVENT_PREFIX):
        return None
    parts = line[len(EVENT_PREFIX) :].split("|")
    if len(parts) < 2:
        return None
    try:
        t = float(parts[0])
    except ValueError:
        return None
    etype = parts[1]
    data: EventData = {}
    for pair in parts[2:]:
        if "=" not in pair:
            continue
        key, _, raw = pair.partition("=")
        data[key] = _coerce(raw)
    return ParsedEvent(t=t, type=etype, data=data)


def parse_stream(lines: list[str]) -> list[ParsedEvent]:
    """Parse a full stdout capture into events, ignoring engine log noise (R4)."""
    out: list[ParsedEvent] = []
    for line in lines:
        ev = parse_event_line(line)
        if ev is not None:
            out.append(ev)
    return out


def to_records(events: list[ParsedEvent], run_id: str) -> list[dict[str, Any]]:
    """Shape parsed events into per-event JSONL records (event.schema.json).

    The harness owns ``run_id`` and ``schema_version``; QuakeC owns ``t``/``data``.
    """
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "t": ev.t,
            "run_id": run_id,
            "type": ev.type,
            "data": ev.data,
        }
        for ev in events
    ]


def _empty_stats() -> dict[str, Any]:
    """A complete, schema-shaped StatsBlock with every field present (zeros)."""
    return {
        "kills": 0,
        "deaths": 0,
        "damage_dealt": 0,
        "damage_taken": 0,  # fixed at 0 this slice (G1) — no incoming-damage event
        "secrets_found": 0,
        "secrets_total": 0,
        "items_collected": 0,
        "shots_fired": 0,
        "shots_hit": 0,
        "accuracy": 0.0,
        "time_to_exit_sec": None,
        "weapon_usage": {},
        "deaths_by_cause": {},
    }


def aggregate(events: list[ParsedEvent]) -> dict[str, Any]:
    """Fold events into the summary ``stats`` block.

    US1 skeleton: counts default to 0; ``secrets_total`` is read from the
    ``level_start`` payload (G2) and ``time_to_exit_sec`` from a ``completed``
    ``level_end`` (data-model). US2 (T029) extends this with the real per-type
    counts, ``accuracy``, ``weapon_usage``, and ``deaths_by_cause``.
    """
    stats = _empty_stats()
    for ev in events:
        if ev.type == "level_start":
            total = ev.data.get("secrets_total", 0)
            stats["secrets_total"] = int(total) if total is not None else 0
        elif ev.type == "level_end":
            if ev.data.get("outcome") == "completed":
                stats["time_to_exit_sec"] = ev.data.get("time_sec")
    return stats
