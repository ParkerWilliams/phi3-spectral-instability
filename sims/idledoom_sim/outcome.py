"""Terminal-outcome determination (R7, FR-003, FR-010, SC-006).

The outcome is a function of the event stream **and** the engine process result,
never of the exit code alone. The cardinal rule: a run is ``completed`` only if
the engine ended cleanly *and* a terminal ``level_end{outcome:"completed"}`` was
seen — so a broken or interrupted chain can never masquerade as success.
"""

from __future__ import annotations

from .telemetry import ParsedEvent

Outcome = str  # "completed" | "died" | "timeout" | "error"

VALID_OUTCOMES = ("completed", "died", "timeout", "error")


def determine_outcome(
    events: list[ParsedEvent],
    *,
    exit_code: int,
    timed_out: bool,
) -> Outcome:
    """Map (events, exit_code, watchdog) to exactly one terminal outcome.

    Args:
        events: parsed telemetry events for the run.
        exit_code: the engine process exit status.
        timed_out: True if the wall-clock watchdog killed the server.

    Precedence:
        1. Watchdog kill -> ``timeout`` (the in-engine cap failed to end it).
        2. A terminal ``level_end`` -> its declared outcome, except that
           ``completed`` is downgraded to ``error`` unless the process also
           exited cleanly (FR-010).
        3. No terminal ``level_end`` -> ``error`` (partial/interrupted/crash);
           never ``completed``.
    """
    if timed_out:
        return "timeout"

    level_end = _last_level_end(events)
    if level_end is None:
        # No clean terminus: launch/load failure, crash, or interruption.
        return "error"

    declared = level_end.data.get("outcome")
    if declared == "completed":
        return "completed" if exit_code == 0 else "error"
    if declared in ("died", "timeout"):
        return str(declared)
    return "error"


def _last_level_end(events: list[ParsedEvent]) -> ParsedEvent | None:
    for ev in reversed(events):
        if ev.type == "level_end":
            return ev
    return None
