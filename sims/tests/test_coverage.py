"""Feature 002 foundational: navigation coverage stats.

Coverage fields (waypoints_total/visited, map_coverage, distance_traveled,
reached_exit) are carried on the `level_end` payload — like `secrets_total` on
`level_start` (G2 pattern) — not aggregated from per-event counts.
"""

from __future__ import annotations

from idledoom_sim.telemetry import ParsedEvent, aggregate


def _stream(**end: object) -> list[ParsedEvent]:
    le: dict[str, object] = {"outcome": "timeout", "time_sec": 60.0}
    le.update(end)
    return [
        ParsedEvent(0.0, "level_start", {"map": "m", "seed": 1, "secrets_total": 0}),
        ParsedEvent(60.0, "level_end", le),
    ]


def test_coverage_from_level_end() -> None:
    stats = aggregate(
        _stream(waypoints_total=50, waypoints_visited=20, distance_traveled=1234, reached_exit=0)
    )
    assert stats["waypoints_total"] == 50
    assert stats["waypoints_visited"] == 20
    assert stats["map_coverage"] == 0.4  # 20 / 50
    assert stats["distance_traveled"] == 1234
    assert stats["reached_exit"] is False


def test_map_coverage_zero_when_no_waypoints() -> None:
    stats = aggregate(_stream(waypoints_total=0, waypoints_visited=0))
    assert stats["map_coverage"] == 0.0  # zero denominator -> 0, not error


def test_reached_exit_true_on_completed() -> None:
    stats = aggregate(_stream(outcome="completed", reached_exit=1))
    assert stats["reached_exit"] is True


def test_coverage_defaults_when_absent() -> None:
    # A level_end without coverage keys (pre-002 emit) -> zeros/false, no crash.
    stats = aggregate(_stream())
    assert stats["waypoints_visited"] == 0
    assert stats["waypoints_total"] == 0
    assert stats["map_coverage"] == 0.0
    assert stats["distance_traveled"] == 0
    assert stats["reached_exit"] is False
