"""Feature 002 US3: navigation competence (``bot_map_awareness``) is a visible,
sim-measurable progression axis (SC-003).

``bot_map_awareness`` scales exploration thoroughness + route directness in the
QuakeC roam (``bot_move.qc`` ``frik_bot_roam``, T008/T014), so a higher setting
covers more of the map and/or reaches the exit faster. The *behavioural* proof —
averaging real runs at 0.1 vs 0.9 and seeing coverage rise / time-to-exit fall
(quickstart §3) — is a local-build integration check; it cannot run on the
droplet (no engine), so it is the T016 hand-off.

What IS droplet-verifiable here: the ``map_coverage`` / ``time_to_exit_sec``
metrics the comparison relies on move in the right direction with the underlying
signal — a run that reaches more of the graph reports higher ``map_coverage``,
and a faster completion reports a lower ``time_to_exit_sec``. This locks the
measurement direction so the SC-003 comparison is meaningful, and guards
``aggregate()`` against regressions.
"""

from __future__ import annotations

from typing import Any

from idledoom_sim.telemetry import ParsedEvent, aggregate


def _run(
    *,
    visited: int,
    total: int,
    distance: float,
    outcome: str = "timeout",
    time_sec: float = 60.0,
) -> dict[str, Any]:
    """Aggregate a minimal stream standing in for one run's coverage outcome."""
    return aggregate(
        [
            ParsedEvent(0.0, "level_start", {"map": "m", "seed": 1, "secrets_total": 0}),
            ParsedEvent(
                time_sec,
                "level_end",
                {
                    "outcome": outcome,
                    "time_sec": time_sec,
                    "waypoints_total": total,
                    "waypoints_visited": visited,
                    "distance_traveled": distance,
                    "reached_exit": 1 if outcome == "completed" else 0,
                },
            ),
        ]
    )


def test_higher_competence_reports_higher_coverage() -> None:
    # A high-awareness run reaches more of the same graph than a low one.
    low = _run(visited=10, total=100, distance=2000)
    high = _run(visited=60, total=100, distance=6000)
    assert high["map_coverage"] > low["map_coverage"]  # SC-003 direction
    assert high["distance_traveled"] > low["distance_traveled"]


def test_map_coverage_is_monotonic_in_visited() -> None:
    cov = [
        _run(visited=v, total=100, distance=100.0 * v)["map_coverage"]
        for v in (0, 25, 50, 100)
    ]
    assert cov == sorted(cov)  # coverage never decreases as more is reached
    assert cov[0] == 0.0
    assert cov[-1] == 1.0


def test_faster_completion_lowers_time_to_exit() -> None:
    # The alternative SC-003 signal: when the agent reaches the exit sooner,
    # time_to_exit_sec drops (only populated on a 'completed' outcome).
    fast = _run(visited=80, total=100, distance=5000, outcome="completed", time_sec=20.0)
    slow = _run(visited=80, total=100, distance=5000, outcome="completed", time_sec=55.0)
    assert fast["time_to_exit_sec"] < slow["time_to_exit_sec"]
