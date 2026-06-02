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


def _cmd_run(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    config = load_run_config(
        config_path,
        map_override=args.map,
        seed_override=args.seed,
        time_limit_override=args.time_limit,
        batch_id=args.batch_id,
        out_dir=Path(args.out) if args.out else None,
    )

    run_id = writer.new_run_id()
    batch_id = writer.resolve_batch_id(config.batch_id)
    # Re-bind the resolved batch_id so it lands in the summary + path.
    config = config.__class__(**{**config.__dict__, "batch_id": batch_id})

    started_at = _now_iso()
    try:
        result = launcher.run(config)
    except launcher.BinaryNotFoundError as exc:
        # Chain cannot start: non-zero exit + diagnostic, no summary (FR-010).
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BROKEN_CHAIN
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
        print(f"error: produced output failed validation/write: {exc}", file=sys.stderr)
        return EXIT_INVALID_OUTPUT

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness.py", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="one autonomous headless session")
    run_p.add_argument("--config", default="configs/current.toml")
    run_p.add_argument("--map", default=None, help="override map (BSP stem)")
    run_p.add_argument("--seed", type=int, default=None, help="override map seed")
    run_p.add_argument(
        "--time-limit", type=float, default=None, dest="time_limit",
        help="override session time limit (sec)",
    )
    run_p.add_argument("--batch-id", default=None, dest="batch_id")
    run_p.add_argument("--out", default=None, help="output root (default: results/)")
    run_p.set_defaults(func=_cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
