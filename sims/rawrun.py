"""Dev helper: run one or more configs headless and dump the RAW engine stdout.

The normal harness keeps only parsed ``@EVT`` events; QuakeC *runtime* errors and
other console noise are discarded. This writes the full captured stdout (plus the
exit code + watchdog flag) to ``/tmp/<name>.log`` so we can see crashes / host
errors / exactly where the event stream truncates.

Usage (from sims/):
    uv run python rawrun.py nav nav2
    uv run python rawrun.py nav --time-limit 30
"""

from __future__ import annotations

import sys
from pathlib import Path

from idledoom_sim import launcher
from idledoom_sim.config import load_run_config

DEFAULT_TIME_LIMIT = 30.0


def main(argv: list[str]) -> int:
    names: list[str] = []
    time_limit = DEFAULT_TIME_LIMIT
    i = 0
    while i < len(argv):
        if argv[i] == "--time-limit":
            time_limit = float(argv[i + 1])
            i += 2
            continue
        names.append(argv[i])
        i += 1
    if not names:
        names = ["nav"]

    for name in names:
        cfg = load_run_config(
            Path(f"configs/{name}.toml"), time_limit_override=time_limit
        )
        result = launcher.run(cfg)
        header = (
            f"EXIT {result.exit_code} TIMED_OUT {result.timed_out} "
            f"LINES {len(result.stdout_lines)}"
        )
        log = Path(f"/tmp/{name}.log")
        log.write_text(header + "\n" + "\n".join(result.stdout_lines))
        print(f"{name}: {header} -> {log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
