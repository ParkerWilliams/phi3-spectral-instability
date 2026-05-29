"""Locate and drive the FTEQW dedicated server, headless (R1).

The harness owns the process: it builds the ``+set`` command line from the
resolved :class:`RunConfig`, spawns ``fteqw-sv`` with no window/GPU/audio,
captures stdout, and enforces a wall-clock watchdog that hard-kills a server
whose in-engine ``sim_time_limit`` failed to end the run (FR-003).

``build_command`` is a pure function (unit-testable without the binary);
``run`` does the actual spawn and is exercised locally/CI where ``fteqw-sv``
exists — never on the droplet, which only ever *runs* a prebuilt binary.

Reference: research.md R1, contracts/cvars.md.
"""

from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from .botstats import BotValue
from .config import RunConfig

# Repo root = .../idledoom (this file is sims/idledoom_sim/launcher.py).
REPO_ROOT = Path(__file__).resolve().parents[2]

# Env override checked first, then well-known build outputs (suffix varies by
# target, e.g. fteqw-sv64). build-engine-sv (Justfile) produces these locally/CI.
ENV_BINARY = "IDLEDOOM_FTEQW_SV"
_WELL_KNOWN_GLOB = "fteqw-sv*"
_ENGINE_DIR = REPO_ROOT / "engine" / "engine"

# Wall-clock grace beyond sim_time_limit before the watchdog force-kills.
WATCHDOG_GRACE_SEC = 15.0

DEFAULT_SKILL = 1


class BinaryNotFoundError(FileNotFoundError):
    """Raised when no ``fteqw-sv`` binary can be located (chain cannot start)."""


@dataclass(frozen=True)
class LaunchResult:
    stdout_lines: list[str]
    exit_code: int
    timed_out: bool


def locate_binary() -> Path:
    """Find ``fteqw-sv`` via env override, then the well-known engine dir."""
    override = os.environ.get(ENV_BINARY)
    if override:
        p = Path(override)
        if p.is_file() and os.access(p, os.X_OK):
            return p
        raise BinaryNotFoundError(
            f"${ENV_BINARY}={override} is not an executable file"
        )
    candidates = sorted(
        c for c in _ENGINE_DIR.glob(_WELL_KNOWN_GLOB)
        if c.is_file() and os.access(c, os.X_OK)
    )
    if candidates:
        return candidates[0]
    raise BinaryNotFoundError(
        f"no fteqw-sv binary found (set ${ENV_BINARY} or run `just build-engine-sv` "
        f"locally; searched {_ENGINE_DIR}/{_WELL_KNOWN_GLOB})"
    )


def _fmt_cvar_value(value: BotValue) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def build_command(
    binary: Path,
    config: RunConfig,
    *,
    basedir: Path = REPO_ROOT,
    gamedir: str = "quakec",
    skill: int = DEFAULT_SKILL,
) -> list[str]:
    """Build the headless ``fteqw-sv`` argv for one run (R1, cvars.md).

    Note: ``basedir``/``gamedir`` (where ``progs.dat`` and the LibreQuake map
    resolve) are finalized at local-run time once the content is vendored (T006).
    """
    cmd: list[str] = [
        str(binary),
        "-basedir", str(basedir),
        "-game", gamedir,
        # Run-shape engine built-ins (cvars.md).
        "+set", "deathmatch", "0",
        "+set", "skill", str(skill),
        "+set", "sv_cheats", "1",
        # sim_* control cvars.
        "+set", "sim_mode", "1",
        "+set", "sim_seed", str(config.seed),
        "+set", "sim_time_limit", str(config.time_limit_sec),
    ]
    # bot_* — already clamped + recorded in config.bot_config (FR-008).
    for name, value in sorted(config.bot_config.items()):
        cmd += ["+set", name, _fmt_cvar_value(value)]
    cmd += ["+map", config.map]
    return cmd


def run(
    config: RunConfig,
    *,
    basedir: Path = REPO_ROOT,
    gamedir: str = "quakec",
    skill: int = DEFAULT_SKILL,
) -> LaunchResult:
    """Spawn the dedicated server headless and capture its stdout.

    Raises :class:`BinaryNotFoundError` if the chain cannot even start (the
    harness maps that to a non-zero exit + diagnostic, never a summary — FR-010).
    """
    binary = locate_binary()
    cmd = build_command(binary, config, basedir=basedir, gamedir=gamedir, skill=skill)

    deadline = config.time_limit_sec + WATCHDOG_GRACE_SEC
    lines: list[str] = []
    timed_out = False

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    def _drain() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))

    reader = threading.Thread(target=_drain, daemon=True)
    reader.start()

    try:
        proc.wait(timeout=deadline)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    reader.join(timeout=5)
    return LaunchResult(
        stdout_lines=lines,
        exit_code=proc.returncode if proc.returncode is not None else -1,
        timed_out=timed_out,
    )
