# Contract: Sim harness CLI (`sims/harness.py`)

The harness is the single command (FR-001) a developer or CI invokes. Run via
`uv` (R9). Two subcommands; both exercise the full engine→game-logic→agent→
telemetry chain headless.

## `run` — one autonomous session

```
uv run harness.py run --config configs/current.toml [overrides...]
```

| Flag | Type | Default | Maps to | Req |
|---|---|---|---|---|
| `--config PATH` | path | `configs/current.toml` | TOML run config | — |
| `--map NAME` | string | from config | `+map`, summary `map` | FR-015 |
| `--seed INT` | int | from config | `sim_seed`, `level_start.seed` | FR-016 |
| `--time-limit SEC` | number | from config | `sim_time_limit` + watchdog | FR-003 |
| `--batch-id UUID` | uuid | new single-run batch | output path, summary | R10 |
| `--out DIR` | path | `results/` | output root | FR-009 |
| `--bot.<name> VAL` | per cvar | catalogue default | clamped → `bot_*` cvar | FR-007/008 |

## `smoke` — fast CI gate (FR-013)

```
uv run harness.py smoke [--config configs/smoke.toml]
```

Minimal map + short `--time-limit` (target full run < 60 s wall, SC-005).
Identical output contract to `run`; intended for `just sim-smoke` / CI.

## Exit codes (FR-010, SC-006)

| Code | Meaning |
|---|---|
| `0` | Clean run; one schema-valid summary written. `outcome` may be any of `completed`/`died`/`timeout`. |
| non-zero | Chain broken (engine won't launch, map missing, `progs.dat` won't load, crash) **or** produced output failed schema validation. A diagnostic is printed to stderr. No `completed` summary is written for a broken chain. |

`smoke` returns `0` only on a healthy chain with a valid summary; non-zero on any
break — making it usable directly as a CI gate.

## Output (FR-009)

Per invocation, written under `<out>/<batch_id>/`:
- `<run_id>.summary.json` — validates against `summary.schema.json`.
- `<run_id>.events.jsonl` — each line validates against `event.schema.json`.

Paths are unique per `run_id`; two near-simultaneous runs never overwrite each
other (edge case). The `results/` tree is gitignored.

## Guarantees the harness owns

- Generates `run_id` (UUID), resolves `batch_id`.
- Clamps every `bot_*` to its documented range **before** setting the cvar and
  records the clamped value in `bot_config` (FR-008); computes `config_hash`
  (sha256 of canonical `bot_config`).
- Stamps `started_at`/`ended_at`/`duration_sec` (wall-clock, ISO-8601).
- Enforces the time limit (in-engine `sim_time_limit` + wall-clock watchdog).
- Aggregates events → `stats`; reconciles (the summary is a function of events).
- Validates both files before exit 0 (SC-002).
