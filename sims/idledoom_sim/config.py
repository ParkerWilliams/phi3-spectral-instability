"""Run configuration: TOML + CLI overrides -> clamped bot_config + config_hash.

US1 scope (this file as first written): load the run config (map, seed,
time_limit) and build the full ``bot_config`` from catalogue defaults overlaid
with any ``[bot]`` table in the TOML, then compute the ``config_hash``
(sha256 over canonical JSON) so the per-run summary carries the schema-required
64-hex hash from the MVP onward (C1). All values are clamped to their documented
ranges (FR-008) — harmless for in-range defaults, and the guarantee US3 builds on.

US3 (follow-up) adds ``--bot.<name>`` CLI overrides on top of this.

Reference: contracts/harness-cli.md, contracts/cvars.md, FR-007/FR-008/FR-016.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .botstats import BotValue, clamp_bot_value, default_bot_config

DEFAULT_TIME_LIMIT_SEC = 120.0


@dataclass(frozen=True)
class RunConfig:
    """Everything one run needs, with the exact config that will be recorded."""

    map: str
    seed: int
    time_limit_sec: float
    batch_id: str | None
    out_dir: Path
    bot_config: dict[str, BotValue] = field(default_factory=dict)
    config_hash: str = ""


def compute_config_hash(bot_config: dict[str, BotValue]) -> str:
    """sha256 (hex) over canonical, sorted-key JSON of ``bot_config`` (FR-007).

    Identical configs hash equal; any difference changes the hash (US3 sc.2).
    """
    canonical = json.dumps(bot_config, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_bot_config(
    overrides: dict[str, BotValue] | None = None,
) -> dict[str, BotValue]:
    """Full bot_config: catalogue defaults overlaid with clamped overrides.

    ``overrides`` come from the TOML ``[bot]`` table (and, in US3, ``--bot.*``).
    Every overridden value is clamped to its documented range before it lands in
    the config (FR-008 — no silent out-of-range acceptance).
    """
    cfg = default_bot_config()
    for name, value in (overrides or {}).items():
        cfg[name] = clamp_bot_value(name, value)  # KeyError on unknown stat
    return cfg


def load_run_config(
    config_path: Path,
    *,
    map_override: str | None = None,
    seed_override: int | None = None,
    time_limit_override: float | None = None,
    batch_id: str | None = None,
    out_dir: Path | None = None,
    bot_overrides: dict[str, BotValue] | None = None,
) -> RunConfig:
    """Resolve a :class:`RunConfig` from a TOML file plus CLI overrides.

    Precedence: CLI override > TOML value > documented default.
    """
    with config_path.open("rb") as fh:
        raw = tomllib.load(fh)

    map_name = map_override if map_override is not None else raw.get("map")
    if not map_name:
        raise ValueError(
            f"{config_path}: 'map' is required (in config or via --map)"
        )

    seed = seed_override if seed_override is not None else int(raw.get("seed", 0))
    time_limit = (
        time_limit_override
        if time_limit_override is not None
        else float(raw.get("time_limit", DEFAULT_TIME_LIMIT_SEC))
    )

    # Merge TOML [bot] table with any CLI bot overrides (CLI wins).
    merged_overrides: dict[str, BotValue] = {}
    toml_bot = raw.get("bot", {})
    if isinstance(toml_bot, dict):
        merged_overrides.update(toml_bot)
    if bot_overrides:
        merged_overrides.update(bot_overrides)

    bot_config = build_bot_config(merged_overrides)

    return RunConfig(
        map=str(map_name),
        seed=seed,
        time_limit_sec=time_limit,
        batch_id=batch_id,
        out_dir=out_dir if out_dir is not None else Path("results"),
        bot_config=bot_config,
        config_hash=compute_config_hash(bot_config),
    )
