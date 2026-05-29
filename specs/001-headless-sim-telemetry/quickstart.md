# Quickstart: Headless Simulation Run with Telemetry

Goal: from a clean checkout, run **one autonomous headless session** and get a
schema-valid summary + event stream — then the fast smoke variant. No window, no
human input (FR-001/FR-002).

> **Build locally or in CI, never on the droplet** (1 GB RAM OOMs). The droplet
> may *run* sims once the binaries exist.

## 0. One-time setup

```bash
# Engine: dedicated server (headless) + QuakeC compiler — LOCAL/CI only
just build-fteqcc            # engine/engine/qclib/fteqcc.bin
make -C engine/engine sv-rel # engine/engine/fteqw-sv*   (added to `just build-sim`)
just build-quakec            # quakec/progs.dat (rerelease base + FrikBot + telemetry.qc)

# LibreQuake map content (vendored submodule; do this locally)
git submodule update --init assets/libre-quake

# Python harness env (uv — never raw pip/python)
cd sims && uv sync
```

## 1. Run one session (User Story 1 — P1)

```bash
just sim
# == uv run harness.py run --config configs/current.toml
```

What happens: the harness clamps the config's `bot_*` values, computes
`config_hash`, launches `fteqw-sv` headless with our `progs.dat` + the LibreQuake
map, `+set sim_mode 1` (autostarts the FrikBot agent — no client needed), streams
the engine's `@EVT|...` lines, enforces the time limit, then writes:

```
sims/results/<batch-id>/<run-id>.summary.json
sims/results/<batch-id>/<run-id>.events.jsonl
```

Inspect:

```bash
jq . sims/results/*/*.summary.json          # outcome ∈ completed|died|timeout|error
head -1 sims/results/*/*.events.jsonl        # first event == level_start
tail -1 sims/results/*/*.events.jsonl        # last event  == level_end
```

**Expected (acceptance):** exactly one summary, `outcome` set, `map`/`started_at`/
`ended_at`/`duration_sec`/`stats` populated; if the agent never reaches the exit,
`outcome: "timeout"` and the summary is still valid.

## 2. Read the event stream & reconcile (User Story 2 — P2)

```bash
# kill events == stats.kills ; shots_hit/shots_fired == stats.accuracy (within rounding)
jq -s '[.[]|select(.type=="kill")]|length' sims/results/*/*.events.jsonl
jq '.stats.kills, .stats.accuracy' sims/results/*/*.summary.json
```

The harness guarantees the summary `stats` is a pure aggregate of the events
(FR-006); `pytest tests/test_reconcile.py` asserts zero discrepancy (SC-003).

## 3. Vary the config (User Story 3 — P2)

```bash
uv run harness.py run --config configs/current.toml --bot.bot_accuracy 0.1
uv run harness.py run --config configs/current.toml --bot.bot_accuracy 0.9
# compare:
jq '.config_hash, .bot_config.bot_accuracy, .stats.accuracy' sims/results/*/*.summary.json
```

**Expected:** different `config_hash` for the two runs; `bot_config.bot_accuracy`
equals the supplied (clamped) value; higher `bot_accuracy` → higher
`stats.accuracy` (SC-004 — for subtle deltas, average several runs per config,
FR-014). Out-of-range input (e.g. `--bot.bot_accuracy 5`) is clamped to `1.0` and
the clamped value is what appears in `bot_config` (FR-008).

## 4. Smoke run as a CI gate (User Story 4 — P3)

```bash
just sim-smoke           # uv run harness.py smoke --config configs/smoke.toml
echo $?                  # 0 on a healthy chain (< 60s, SC-005); non-zero if broken
```

A broken chain (missing map, unloadable `progs.dat`, crash) exits non-zero with a
diagnostic and never writes a `completed` summary (FR-010, SC-006).

## 5. Validate & test

```bash
cd sims && uv run pytest         # schema validity, reconciliation, clamping, outcomes
```

`tests/test_schema.py` proves 100% of produced files validate against
`contracts/{summary,event}.schema.json` (SC-002).
