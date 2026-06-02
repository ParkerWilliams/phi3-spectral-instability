"""US4: the smoke gate passes only for a healthy chain — a bracketed event stream
and a non-error terminal — not merely a written file (FR-013, SC-006)."""

from __future__ import annotations

import harness
from idledoom_sim.telemetry import ParsedEvent


def _bracketed() -> list[ParsedEvent]:
    return [
        ParsedEvent(0.0, "level_start", {"map": "m", "seed": 1, "secrets_total": 0}),
        ParsedEvent(15.0, "level_end", {"outcome": "timeout", "time_sec": 15.0}),
    ]


def test_healthy_for_bracketed_nonerror_chain() -> None:
    assert harness.smoke_chain_healthy(_bracketed(), "timeout") is True
    assert harness.smoke_chain_healthy(_bracketed(), "completed") is True


def test_unhealthy_on_error_outcome() -> None:
    assert harness.smoke_chain_healthy(_bracketed(), "error") is False


def test_unhealthy_when_stream_not_bracketed() -> None:
    only_end = [ParsedEvent(1.0, "level_end", {"outcome": "timeout", "time_sec": 1.0})]
    assert harness.smoke_chain_healthy(only_end, "timeout") is False
    assert harness.smoke_chain_healthy([], "timeout") is False


def test_parser_has_smoke_subcommand() -> None:
    args = harness.build_parser().parse_args(["smoke", "--config", "configs/smoke.toml"])
    assert args.command == "smoke"
    assert args.config == "configs/smoke.toml"
    assert args.func is harness._cmd_smoke
