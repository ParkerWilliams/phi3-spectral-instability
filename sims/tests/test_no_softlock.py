"""Feature 002 US4: idle-tolerance — imperfect navigation never softlocks a run
(SC-004 / FR-006, FR-007).

Two layers guarantee this, and both are asserted here at the harness level:

1. The in-engine ``sim_time_limit`` emits ``level_end{timeout}`` then ``quit``
   (telemetry.qc), and the wall-clock watchdog force-kills if even that fails —
   so ``determine_outcome`` ALWAYS returns one of the four terminal outcomes,
   for every (events, exit_code, timed_out) combination. No input hangs it.
2. Detours / backtracking / low coverage are legitimate idle behaviour, never a
   failure: a run that wandered a lot (high ``distance_traveled``) but covered
   little still terminates with a normal outcome.

The *behavioural* proof — a local batch of real runs across maps, all reaching a
terminal outcome within the limit, with the QuakeC stuck-recovery (T017,
``bot_phys.qc`` ``bot_stuck_check``) actually un-wedging the agent — needs the
engine and is the T018 hand-off (quickstart §4).
"""

from __future__ import annotations

from idledoom_sim.outcome import VALID_OUTCOMES, determine_outcome
from idledoom_sim.telemetry import ParsedEvent, aggregate


def _start() -> ParsedEvent:
    return ParsedEvent(0.0, "level_start", {"map": "m", "seed": 1, "secrets_total": 0})


def _end(outcome: str, **extra: object) -> ParsedEvent:
    data: dict[str, object] = {"outcome": outcome, "time_sec": 60.0}
    data.update(extra)
    return ParsedEvent(60.0, "level_end", data)


def test_watchdog_kill_is_always_terminal() -> None:
    # Even an empty stream + non-zero exit: a watchdog timeout is terminal.
    assert determine_outcome([], exit_code=-9, timed_out=True) == "timeout"


def test_missing_level_end_is_terminal_error_not_a_hang() -> None:
    # A partial/interrupted stream resolves to a terminal 'error', never None.
    out = determine_outcome([_start()], exit_code=1, timed_out=False)
    assert out == "error"
    assert out in VALID_OUTCOMES


def test_every_combination_yields_a_terminal_outcome() -> None:
    streams = [
        [],
        [_start()],
        [_start(), _end("timeout")],
        [_start(), _end("died")],
        [_start(), _end("completed")],
    ]
    for events in streams:
        for exit_code in (0, 1, -9):
            for timed_out in (False, True):
                out = determine_outcome(events, exit_code=exit_code, timed_out=timed_out)
                assert out in VALID_OUTCOMES  # always one of four terminals; never hangs


def test_backtracking_run_is_not_a_failure() -> None:
    # Lots of wandering (high distance), little coverage, but it timed out cleanly:
    # a normal terminal outcome — detours are acceptable idle behaviour (FR-007).
    events = [
        _start(),
        _end("timeout", waypoints_total=100, waypoints_visited=8, distance_traveled=99999),
    ]
    assert determine_outcome(events, exit_code=0, timed_out=False) == "timeout"
    stats = aggregate(events)
    assert stats["map_coverage"] < 0.1  # barely covered
    assert stats["distance_traveled"] > 0  # but it kept moving — not wedged


def test_completed_requires_clean_exit() -> None:
    # A 'completed' level_end with a crash exit must NOT masquerade as success.
    events = [_start(), _end("completed")]
    assert determine_outcome(events, exit_code=0, timed_out=False) == "completed"
    assert determine_outcome(events, exit_code=1, timed_out=False) == "error"
