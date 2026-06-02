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
    """Parse one stdout line. Returns ``None`` for any non-telemetry line (R4).

    The ``@EVT|`` tag is located anywhere in the line, not only at column 0: an
    un-terminated engine ``bprint`` (e.g. the client-"entered" message) can share
    a stdout line with our emit, leaving leading noise before the tag.
    """
    line = line.rstrip("\r\n")
    idx = line.find(EVENT_PREFIX)
    if idx == -1:
        return None
    parts = line[idx + len(EVENT_PREFIX) :].split("|")
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


def stream_invariant_ok(events: list[ParsedEvent]) -> bool:
    """US2 sc.1: a well-formed stream is non-empty, starts ``level_start``,
    ends ``level_end``. A violation means an interrupted/partial run."""
    return (
        bool(events)
        and events[0].type == "level_start"
        and events[-1].type == "level_end"
    )


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


def _as_int(value: Any) -> int:
    """Coerce a payload number to int (damage/value), treating None as 0."""
    return int(value) if value is not None else 0


def aggregate(events: list[ParsedEvent]) -> dict[str, Any]:
    """Fold events into the summary ``stats`` block — a pure function of the stream.

    Per-type counts, ``accuracy`` (``shots_hit/shots_fired`` to 4 dp, 0 on zero
    shots), ``damage_dealt`` (Σ ``hit.damage``), ``weapon_usage`` and
    ``deaths_by_cause``. Two fields are not event-counted this slice:
    ``secrets_total`` comes from the ``level_start`` payload (G2) and
    ``damage_taken`` is fixed at ``0`` (no incoming-damage event yet, G1).
    ``time_to_exit_sec`` is the ``completed`` ``level_end`` time. (data-model
    StatsBlock; FR-006/SC-003.)
    """
    stats = _empty_stats()
    weapon_usage: dict[str, dict[str, int]] = {}
    deaths_by_cause: dict[str, int] = {}

    def _wu(weapon: str) -> dict[str, int]:
        return weapon_usage.setdefault(weapon, {"shots": 0, "hits": 0, "damage": 0})

    for ev in events:
        if ev.type == "level_start":
            stats["secrets_total"] = _as_int(ev.data.get("secrets_total", 0))
        elif ev.type == "level_end":
            if ev.data.get("outcome") == "completed":
                stats["time_to_exit_sec"] = ev.data.get("time_sec")
        elif ev.type == "kill":
            stats["kills"] += 1
        elif ev.type == "death":
            stats["deaths"] += 1
            cause = str(ev.data.get("cause", "unknown"))
            deaths_by_cause[cause] = deaths_by_cause.get(cause, 0) + 1
        elif ev.type == "shot":
            stats["shots_fired"] += 1
            weapon = ev.data.get("weapon")
            if weapon is not None:
                _wu(str(weapon))["shots"] += 1
        elif ev.type == "hit":
            stats["shots_hit"] += 1
            dmg = _as_int(ev.data.get("damage"))
            stats["damage_dealt"] += dmg
            weapon = ev.data.get("weapon")
            if weapon is not None:
                wu = _wu(str(weapon))
                wu["hits"] += 1
                wu["damage"] += dmg
        elif ev.type == "pickup":
            stats["items_collected"] += 1
        elif ev.type == "secret":
            stats["secrets_found"] += 1

    shots = stats["shots_fired"]
    stats["accuracy"] = round(stats["shots_hit"] / shots, 4) if shots else 0.0
    stats["weapon_usage"] = weapon_usage
    stats["deaths_by_cause"] = deaths_by_cause
    return stats
