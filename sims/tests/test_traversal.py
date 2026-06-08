"""Feature: nav-competence metric — pluggable traversal metrics (traversal.py).

Unit-tests the metric registry against synthetic ``nav``-sample streams. This is
the layer we revisit often (add/swap/tune metrics) and it's fully droplet-verifiable
— no engine needed. The live behavioural check (does higher ``bot_map_awareness``
raise the chosen metric?) is the local sweep.
"""

from __future__ import annotations

from idledoom_sim.telemetry import ParsedEvent, aggregate
from idledoom_sim.traversal import (
    TRAVERSAL_METRICS,
    NavSample,
    boring_view,
    compute_traversal,
    extent_area,
    nav_samples,
    pacing,
    peak_boredom,
    visited_cells,
    waypoints_at_15s,
)


def _nav(t: float, x: float, y: float, waypoints: int, distance: float) -> ParsedEvent:
    return ParsedEvent(
        t, "nav", {"x": x, "y": y, "waypoints": waypoints, "distance": distance}
    )


def _wp(t: float, w: int) -> NavSample:
    return NavSample(t=t, x=0.0, y=0.0, waypoints=w, distance=float(w * 10))


def test_nav_samples_extracts_only_nav_events() -> None:
    events = [
        ParsedEvent(0.0, "level_start", {"map": "m", "seed": 1}),
        _nav(2.0, 100, 0, 3, 200),
        ParsedEvent(2.0, "kill", {"victim": "x", "weapon": "shotgun", "distance": 10}),
        _nav(4.0, 300, 0, 5, 450),
    ]
    s = nav_samples(events)
    assert [p.t for p in s] == [2.0, 4.0]
    assert s[0].waypoints == 3
    assert s[1].distance == 450.0


def test_extent_area_is_bounding_box() -> None:
    s = [NavSample(0, 0, 0, 0, 0), NavSample(1, 400, 200, 0, 0)]
    assert extent_area(s) == 400 * 200
    assert extent_area([]) == 0.0


def test_visited_cells_counts_distinct_256_cells() -> None:
    # (10,10) & (20,20) share cell (0,0); (300,0)->(1,0); (0,300)->(0,1) => 3 cells
    s = [
        NavSample(0, 10, 10, 0, 0),
        NavSample(1, 20, 20, 0, 0),
        NavSample(2, 300, 0, 0, 0),
        NavSample(3, 0, 300, 0, 0),
    ]
    assert visited_cells(s) == 3.0


def test_rate_metric_uses_latest_sample_within_checkpoint() -> None:
    # waypoints by t<=15 is 12; the t=20 spike (30) must NOT count (exploration speed)
    s = [_wp(0, 0), _wp(5, 4), _wp(10, 8), _wp(15, 12), _wp(20, 30)]
    assert waypoints_at_15s(s) == 12.0


def test_peak_boredom_tracks_max_then_reset() -> None:
    # boredom climbs while wandering, resets on combat -> peak captures the high.
    s = [
        NavSample(0, 0, 0, 0, 0, boredom=3),
        NavSample(2, 0, 0, 1, 50, boredom=12),
        NavSample(4, 0, 0, 2, 90, boredom=0),
    ]
    assert peak_boredom(s) == 12.0
    assert peak_boredom([]) == 0.0


def test_nav_samples_reads_boredom_from_event_data() -> None:
    s = nav_samples([ParsedEvent(2.0, "nav", {"x": 0, "y": 0, "waypoints": 1, "boredom": 7})])
    assert s[0].boredom == 7.0


def test_boring_view_is_time_fraction() -> None:
    # Cumulative time counters; the LAST sample holds run totals. 6s of sustained
    # wall-stare out of 30s watched => 0.2 of the watch spent in the boring slide.
    s = [
        NavSample(2.0, 0, 0, 1, 50, boring_view_time=1.0, watch_time=10.0),
        NavSample(30.0, 0, 0, 9, 900, boring_view_time=6.0, watch_time=30.0),
    ]
    assert boring_view(s) == 0.2


def test_pacing_is_time_fraction() -> None:
    # 9s spent running back and forth (high path, low net progress) out of 30s.
    s = [NavSample(30.0, 0, 0, 9, 900, pace_time=9.0, watch_time=30.0)]
    assert pacing(s) == 0.3


def test_watchability_metrics_zero_without_watch_time() -> None:
    # No watched time => 0.0, never a ZeroDivisionError.
    s = [NavSample(2.0, 0, 0, 0, 0, watch_time=0.0)]
    assert boring_view(s) == 0.0
    assert pacing(s) == 0.0
    assert boring_view([]) == 0.0
    assert pacing([]) == 0.0


def test_nav_samples_reads_watchability_counters_from_event_data() -> None:
    s = nav_samples(
        [
            ParsedEvent(
                30.0,
                "nav",
                {
                    "x": 0,
                    "y": 0,
                    "waypoints": 9,
                    "boring_view_time": 6.0,
                    "pace_time": 9.0,
                    "watch_time": 30.0,
                },
            )
        ]
    )
    assert s[0].boring_view_time == 6.0
    assert s[0].pace_time == 9.0
    assert s[0].watch_time == 30.0


def test_compute_traversal_runs_the_full_registry() -> None:
    out = compute_traversal([_nav(2.0, 0, 0, 2, 100), _nav(20.0, 500, 500, 9, 900)])
    assert set(out) == set(TRAVERSAL_METRICS)
    assert out["final_waypoints"] == 9.0
    assert out["visited_cells"] >= 1.0


def test_aggregate_populates_traversal_block() -> None:
    events = [
        ParsedEvent(0.0, "level_start", {"map": "m", "seed": 1, "secrets_total": 0}),
        _nav(2.0, 0, 0, 2, 100),
        _nav(20.0, 500, 0, 9, 900),
        ParsedEvent(30.0, "level_end", {"outcome": "timeout", "time_sec": 30.0}),
    ]
    stats = aggregate(events)
    assert set(stats["traversal"]) == set(TRAVERSAL_METRICS)
    assert stats["traversal"]["final_waypoints"] == 9.0


def test_time_to_combat_is_first_shot_timestamp() -> None:
    # Goal-oriented competence signal: sim-time of the first shot (not wandering).
    events = [
        ParsedEvent(0.0, "level_start", {"map": "m", "seed": 1, "secrets_total": 0}),
        _nav(2.0, 0, 0, 1, 50),
        ParsedEvent(8.5, "shot", {"weapon": "shotgun", "target": "null"}),
        ParsedEvent(9.0, "shot", {"weapon": "shotgun", "target": "null"}),
        ParsedEvent(30.0, "level_end", {"outcome": "timeout", "time_sec": 30.0}),
    ]
    assert aggregate(events)["time_to_combat_sec"] == 8.5


def test_time_to_combat_none_when_no_combat() -> None:
    events = [
        ParsedEvent(0.0, "level_start", {"map": "m", "seed": 1, "secrets_total": 0}),
        _nav(2.0, 0, 0, 1, 50),
        ParsedEvent(30.0, "level_end", {"outcome": "timeout", "time_sec": 30.0}),
    ]
    assert aggregate(events)["time_to_combat_sec"] is None


def test_aggregate_traversal_empty_without_nav_events() -> None:
    # A pre-nav-event stream -> {} (unmeasured), not misleading zeros.
    events = [
        ParsedEvent(0.0, "level_start", {"map": "m", "seed": 1, "secrets_total": 0}),
        ParsedEvent(30.0, "level_end", {"outcome": "timeout", "time_sec": 30.0}),
    ]
    assert aggregate(events)["traversal"] == {}
