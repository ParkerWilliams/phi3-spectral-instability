#!/usr/bin/env python3
"""idledoom sim harness — the single command a developer/CI invokes (FR-001).

US1 ships the ``run`` subcommand: one autonomous headless session -> one
schema-valid per-run summary. (``smoke`` is US4; ``--bot.*`` overrides are US3.)

Exit codes (contracts/harness-cli.md):
  0          clean run; one schema-valid summary written (outcome may be
             completed/died/timeout).
  non-zero   chain broken (engine won't launch, map missing, progs.dat won't
             load, crash) or produced output failed validation; a diagnostic is
             printed to stderr and no `completed` summary is written (FR-010).

Run via uv:  uv run harness.py run --config configs/current.toml
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from idledoom_sim import launcher, telemetry, writer
from idledoom_sim.config import load_run_config
from idledoom_sim.outcome import determine_outcome

EXIT_OK = 0
EXIT_BROKEN_CHAIN = 1
EXIT_INVALID_OUTPUT = 2


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def extract_bot_overrides(argv: list[str]) -> tuple[dict[str, str], list[str]]:
    """Pull ``--bot.<name> <value>`` (and ``--bot.<name>=<value>``) pairs out of
    argv before argparse sees them (argparse can't model dynamic option names).

    Returns ``(overrides, remaining_argv)``. Raises ``ValueError`` if a
    ``--bot.<name>`` flag is missing its value. (US3 / T034, contracts/harness-cli.md.)
    """
    overrides: dict[str, str] = {}
    rest: list[str] = []
    i, n = 0, len(argv)
    while i < n:
        arg = argv[i]
        if arg.startswith("--bot."):
            name = arg[len("--bot.") :]
            if "=" in name:
                name, _, value = name.partition("=")
                overrides[name] = value
                i += 1
                continue
            if i + 1 >= n:
                raise ValueError(f"{arg} requires a value (e.g. {arg} 0.9)")
            overrides[name] = argv[i + 1]
            i += 2
            continue
        rest.append(arg)
        i += 1
    return overrides, rest


class _ChainError(Exception):
    """A hard break up to/at output (missing binary, bad config, invalid write).

    Carries the process exit code the CLI should return.
    """

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


def _run_to_summary(
    args: argparse.Namespace,
) -> tuple[str, list[telemetry.ParsedEvent], Path]:
    """Shared ``run``/``smoke`` pipeline: config -> launch -> parse -> write.

    Returns ``(outcome, events, summary_path)``. Raises :class:`_ChainError` on any
    break up to and including output (missing binary, bad config/override, output
    that fails schema validation) — never a silent partial success (FR-010).
    """
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    try:
        config = load_run_config(
            config_path,
            map_override=args.map,
            seed_override=args.seed,
            time_limit_override=args.time_limit,
            batch_id=args.batch_id,
            out_dir=Path(args.out) if args.out else None,
            bot_overrides=getattr(args, "bot_overrides", None) or None,
        )
    except (KeyError, ValueError) as exc:
        # Unknown bot_* name, unparseable value, or missing map: fail loudly (FR-008).
        raise _ChainError(f"bad config/override: {exc}", EXIT_BROKEN_CHAIN) from exc

    run_id = writer.new_run_id()
    batch_id = writer.resolve_batch_id(config.batch_id)
    # Re-bind the resolved batch_id so it lands in the summary + path.
    config = config.__class__(**{**config.__dict__, "batch_id": batch_id})

    started_at = _now_iso()
    try:
        result = launcher.run(config)
    except launcher.BinaryNotFoundError as exc:
        raise _ChainError(str(exc), EXIT_BROKEN_CHAIN) from exc
    ended_at = _now_iso()
    duration = (
        datetime.fromisoformat(ended_at) - datetime.fromisoformat(started_at)
    ).total_seconds()

    events = telemetry.parse_stream(result.stdout_lines)
    outcome = determine_outcome(
        events, exit_code=result.exit_code, timed_out=result.timed_out
    )
    stats = telemetry.aggregate(events)

    summary = writer.build_summary(
        run_id=run_id,
        config=config,
        started_at=started_at,
        ended_at=ended_at,
        duration_sec=max(0.0, duration),
        outcome=outcome,
        stats=stats,
    )

    summary_path, events_path = writer.output_paths(config.out_dir, batch_id, run_id)
    records = telemetry.to_records(events, run_id)
    try:
        writer.write_summary(summary, summary_path)
        writer.write_events(records, events_path)
    except Exception as exc:  # jsonschema.ValidationError or IO error
        raise _ChainError(
            f"produced output failed validation/write: {exc}", EXIT_INVALID_OUTPUT
        ) from exc

    return outcome, events, summary_path


def smoke_chain_healthy(events: list[telemetry.ParsedEvent], outcome: str) -> bool:
    """A smoke run is healthy iff the whole pipeline ran: a bracketed event stream
    (level_start ... level_end) and a non-error terminal (FR-013, SC-006). The
    game outcome (timeout/completed/died) doesn't matter — only chain health."""
    return outcome != "error" and telemetry.stream_invariant_ok(events)


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        outcome, events, summary_path = _run_to_summary(args)
    except _ChainError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.code

    # US2 sc.1: a clean stream opens with level_start and closes with level_end.
    # A violation is a partial/interrupted run — warn, but let the outcome machine
    # (which already refuses a false `completed`) own the exit status.
    if events and not telemetry.stream_invariant_ok(events):
        print(
            "warning: event stream is not bracketed by level_start/level_end "
            "(partial or interrupted run)",
            file=sys.stderr,
        )

    print(f"{outcome}  {summary_path}")
    # A run that started but did not terminate cleanly is reported as error and
    # must exit non-zero so a broken chain is never mistaken for success (FR-010).
    return EXIT_OK if outcome != "error" else EXIT_BROKEN_CHAIN


def _cmd_smoke(args: argparse.Namespace) -> int:
    """Fast CI gate: run the whole chain on a short budget; exit 0 only if it is
    healthy, non-zero with a diagnostic on any break (FR-013, SC-006)."""
    try:
        outcome, events, summary_path = _run_to_summary(args)
    except _ChainError as exc:
        print(f"error: smoke failed: {exc}", file=sys.stderr)
        return exc.code

    if not smoke_chain_healthy(events, outcome):
        print(
            f"error: smoke chain unhealthy (outcome={outcome}, {len(events)} events) "
            f"— stream not bracketed or run errored; see {summary_path}",
            file=sys.stderr,
        )
        return EXIT_BROKEN_CHAIN

    print(f"smoke OK: {outcome}  {summary_path}")
    return EXIT_OK


def _add_run_args(parser: argparse.ArgumentParser, *, default_config: str) -> None:
    parser.add_argument("--config", default=default_config)
    parser.add_argument("--map", default=None, help="override map (BSP stem)")
    parser.add_argument("--seed", type=int, default=None, help="override map seed")
    parser.add_argument(
        "--time-limit", type=float, default=None, dest="time_limit",
        help="override session time limit (sec)",
    )
    parser.add_argument("--batch-id", default=None, dest="batch_id")
    parser.add_argument("--out", default=None, help="output root (default: results/)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness.py", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="one autonomous headless session")
    _add_run_args(run_p, default_config="configs/current.toml")
    run_p.set_defaults(func=_cmd_run)

    smoke_p = sub.add_parser("smoke", help="fast CI smoke run (chain-health gate)")
    _add_run_args(smoke_p, default_config="configs/smoke.toml")
    smoke_p.set_defaults(func=_cmd_smoke)

    return parser


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:]) if argv is None else list(argv)
    try:
        bot_overrides, rest = extract_bot_overrides(raw)  # US3: --bot.<name> VAL
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BROKEN_CHAIN
    args = build_parser().parse_args(rest)
    args.bot_overrides = bot_overrides
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
