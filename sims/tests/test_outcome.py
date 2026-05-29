"""US1 / SC-006: terminal-outcome mapping; a broken chain is never `completed`."""

from __future__ import annotations

from idledoom_sim.outcome import VALID_OUTCOMES, determine_outcome
from idledoom_sim.telemetry import ParsedEvent

START = ParsedEvent(0.0, "level_start", {"map": "lq1m1", "seed": 1, "secrets_total": 0})


def _end(outcome: str, t: float = 30.0) -> ParsedEvent:
    return ParsedEvent(t, "level_end", {"outcome": outcome, "time_sec": t})


def test_completed_requires_clean_exit() -> None:
    events = [START, _end("completed")]
    assert determine_outcome(events, exit_code=0, timed_out=False) == "completed"


def test_completed_with_dirty_exit_is_error() -> None:
    # level_end says completed but the process crashed -> never report success.
    events = [START, _end("completed")]
    assert determine_outcome(events, exit_code=1, timed_out=False) == "error"


def test_died() -> None:
    events = [START, _end("died")]
    assert determine_outcome(events, exit_code=0, timed_out=False) == "died"


def test_timeout_from_engine_level_end() -> None:
    events = [START, _end("timeout")]
    assert determine_outcome(events, exit_code=0, timed_out=False) == "timeout"


def test_timeout_from_watchdog_kill() -> None:
    # Watchdog fired (no clean level_end): still a first-class timeout.
    assert determine_outcome([START], exit_code=-1, timed_out=True) == "timeout"


def test_no_level_end_dirty_exit_is_error() -> None:
    assert determine_outcome([START], exit_code=1, timed_out=False) == "error"


def test_no_level_end_clean_exit_is_error_not_completed() -> None:
    # A terminus-less run that happened to exit 0 must NOT masquerade as completed.
    result = determine_outcome([START], exit_code=0, timed_out=False)
    assert result == "error"
    assert result != "completed"


def test_outcome_is_always_one_of_the_enum() -> None:
    for ev, code, to in (
        ([START, _end("completed")], 0, False),
        ([START, _end("died")], 0, False),
        ([START], -1, True),
        ([], 1, False),
    ):
        assert determine_outcome(ev, exit_code=code, timed_out=to) in VALID_OUTCOMES
