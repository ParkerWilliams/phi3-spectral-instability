"""Parsing robustness (R4): an @EVT line may be prefixed by an un-terminated
engine print, so the tag is not always at column 0."""

from __future__ import annotations

from idledoom_sim.telemetry import parse_event_line, parse_stream


def test_event_line_with_leading_engine_noise_is_parsed() -> None:
    # The client-"entered" bprint emits without a trailing newline, so the first
    # level_start shares a stdout line with it.
    line = "$qc_entered@EVT|0|level_start|map=lq_e1m1|seed=1|secrets_total=0|"
    ev = parse_event_line(line)
    assert ev is not None
    assert ev.type == "level_start"
    assert ev.data["map"] == "lq_e1m1"
    assert ev.data["secrets_total"] == 0


def test_plain_log_line_still_ignored() -> None:
    assert parse_event_line("Server spawned.") is None


def test_stream_recovers_prefixed_level_start() -> None:
    lines = [
        "Server spawned.",
        "$qc_entered@EVT|0|level_start|map=m|seed=1|secrets_total=0|",
        "@EVT|60|level_end|outcome=timeout|time_sec=60|",
    ]
    assert [e.type for e in parse_stream(lines)] == ["level_start", "level_end"]
