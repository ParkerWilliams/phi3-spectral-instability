# Implementation Plan: Headless Simulation Run with Telemetry

**Branch**: `001-headless-sim-telemetry` | **Date**: 2026-05-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-headless-sim-telemetry/spec.md`

## Summary

Deliver the irreducible primitive every later tuning/balancing/regression activity
depends on: **run the FrikBot-derived agent through one libre map, headless, and
emit conforming telemetry.** A Python harness (`sims/harness.py`, run via `uv`)
clamps the supplied `bot_*` configuration to its documented ranges, computes a
stable `config_hash`, launches the **FTEQW dedicated server** (`fteqw-sv`, no
window, no human input) with our `progs.dat` and a **LibreQuake** map, and
enforces a time limit. Our QuakeC emits compact tagged event lines on stdout as
gameplay happens; the harness captures them, aggregates them into the per-run
`stats`, determines the terminal `outcome`, and writes one summary JSON plus one
JSONL event stream to `sims/results/<batch-id>/<run-id>...`, both validated
against `docs/telemetry.md` (schema_version `1`). A fast smoke variant exercises
the whole chain as a CI gate. Zero engine-C patches: headless dedicated mode and
file/stdout I/O already exist (ADR-0001); all new code is QuakeC + Python.

## Technical Context

**Language/Version**:
- Sim harness — **Python 3.11+**, run through a **`uv`-managed venv** (constitution: "Any Python runs through a uv-managed venv"; never invoke raw `python`/`pip`).
- Game logic — **QuakeC** (rerelease base + FrikBot), compiled to `progs.dat` by **fteqcc**.
- Engine — **C (FTEQW)**, *built but not patched*; dedicated `sv-rel` target only.

**Primary Dependencies**:
- **FTEQW dedicated server** — `make -C engine/engine sv-rel` → `engine/engine/fteqw-sv*` (headless, "run as a console program"; ADR-0001).
- **fteqcc** + FrikBot-derived QuakeC (existing `quakec/`, INTEGRATION.md).
- **LibreQuake** base content — vendored submodule at `assets/libre-quake/` (licenses.md), supplies the map + its assets.
- Python: `jsonschema` (validate produced files), `tomllib` (stdlib, read configs), `pytest`/`ruff`/`mypy` (already wired in Justfile).

**Storage**: filesystem only. Per-run summary JSON + per-event JSONL under `sims/results/<batch-id>/<run-id>...` (gitignored; FR-009). No SQLite — live-gameplay DB telemetry is explicitly out of scope.

**Testing**: `pytest` over the harness — schema validity (SC-002), event↔summary reconciliation (SC-003), out-of-range clamping + `config_hash` stability (FR-008/US3), outcome mapping + non-zero exit on a broken chain (SC-006). The smoke variant doubles as the end-to-end CI gate (FR-013/SC-005).

**Target Platform**: Headless Linux (CI + the dev droplet for *running* batches) and macOS/Windows for local dev. No GPU/window/audio needed by the dedicated server.

**Project Type**: CLI sim harness (Python) + game-logic mod (QuakeC telemetry/autostart hooks) + vendored map content. Single-repo, no web/mobile split.

**Performance Goals**: Smoke variant < 60 s wall-clock (SC-005). Realtime-or-faster is acceptable for v1; tick acceleration / parallelism (design §8) is deferred (Assumptions).

**Constraints**:
- **Zero engine-C patches** (constitution "engine discipline"; would otherwise need an ADR). Dedicated mode + I/O already satisfy us.
- **Droplet builds nothing** (1 GB RAM OOMs): `fteqw-sv`, fteqcc, and `progs.dat` are built locally/CI; the droplet may *run* the resulting sim batches.
- **One run per invocation**, one map — but the unique-`run_id` / non-colliding-path design (FR-009) must not preclude a later `sim-batch` aggregator (FR-014).
- **Statistical, not bit-exact** reproducibility (FR-014): the seed (FR-016) is recorded and passed, not a determinism guarantee.

**Scale/Scope**: 1 map, 1 agent, 1 run/invocation. ~16 `bot_*` cvars catalogued (subset behaviorally wired this slice; all clamped+recorded). 8 event types. 2 JSON Schemas.

## Constitution Check

*GATE: must pass before Phase 0. Re-checked after Phase 1 (below).*

| Principle | Verdict | Notes |
|---|---|---|
| **I. Visible Progression** (NON-NEGOTIABLE) | ✅ N/A → served | No player-facing upgrade ships here. But SC-004 (config visibly changes telemetry) is the *machine-checkable* form of "observable change," and this harness is the tool that proves visibility for every later upgrade. |
| **II. Behavior Configuration Is the Gameplay** | ✅ Pass | Agent is driven only by `bot_*` configuration; no moment-to-moment control (FR-002). No rule engine introduced (correctly deferred). |
| **III. Low-Poly PS1 Authenticity** | ✅ N/A | Headless run renders nothing; presentation is out of scope. Neutral. |
| **IV. Original/Libre, No id IP** (NON-NEGOTIABLE) | ✅ Pass — **gating** | Run target is a **LibreQuake** map (FR-015), never id1 maps. FrikBot's vendored `waypoints/map_dm1..6.qc` are public-domain *source* but target **id1 maps** — they are NOT used as the run target. Chosen map + license recorded in `docs/licenses.md`. Every loaded asset must be libre (verified at vendor time). |
| **V. Small, Testable, Observable Changes** | ✅ Pass — directly serves | This feature *is* `just sim`. It gives every bot stat sim-harness coverage, the constitution's stated mechanism for tuning over guessing. |
| **Tech: engine discipline** | ✅ Pass | No engine-C patch (no new ADR needed). Telemetry/autostart live in QuakeC; config via cvars. |
| **Tech: tunables documented** | ✅ Pass | `bot_*` already in `docs/bot-stats.md`; harness mirrors its ranges for clamping. Any `sim_*` control cvars added are documented in the cvar contract + bot-stats notes. |
| **Tech: droplet / uv** | ✅ Pass | Build off-droplet; run on it. Python strictly via `uv`. Justfile sim recipes updated from `pip`/`python` → `uv` (consistency fix). |
| **Workflow** | ✅ Pass | `main` stays buildable; smoke run is the CI gate. Schema changes (if any) land in `docs/telemetry.md` first with a version bump (Assumptions). |

**Result: PASS, no violations.** Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-headless-sim-telemetry/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions resolving the unknowns
├── data-model.md        # Phase 1 — Run / Summary / Event / AgentConfig
├── quickstart.md        # Phase 1 — run one + smoke, validate, read outcome
├── contracts/           # Phase 1 — schemas + CLI + event-line + cvar contracts
│   ├── summary.schema.json
│   ├── event.schema.json
│   ├── harness-cli.md
│   ├── engine-event-line.md
│   └── cvars.md
└── checklists/
    └── requirements.md  # (already present)
```

### Source Code (repository root)

```text
sims/                              # Python harness (uv-managed)
├── pyproject.toml                 # deps: jsonschema; tooling: pytest/ruff/mypy
├── harness.py                     # CLI entry: `run` / `smoke` subcommands
├── idledoom_sim/
│   ├── config.py                  # load TOML, clamp bot_* to ranges, config_hash
│   ├── botstats.py                # machine-readable bot_* ranges/defaults (mirror of docs/bot-stats.md)
│   ├── launcher.py                # locate fteqw-sv, build cmdline/cvars, run, wall-clock watchdog
│   ├── telemetry.py               # parse engine stdout event lines → events; aggregate → stats
│   ├── outcome.py                 # terminal-outcome determination
│   └── writer.py                  # write JSONL + summary JSON to results path; validate
├── configs/
│   ├── current.toml               # default run (map, seed, time_limit, bot_* params)
│   └── smoke.toml                 # fast CI smoke variant
├── schema/                        # canonical copies the harness validates against
│   ├── summary.schema.json        # == contracts/summary.schema.json
│   └── event.schema.json          # == contracts/event.schema.json
├── tests/
│   ├── test_schema.py             # SC-002: produced files validate
│   ├── test_reconcile.py          # SC-003: events reconcile with summary
│   ├── test_clamp.py              # FR-008/US3: clamp + config_hash stability
│   └── test_outcome.py            # SC-006: outcome mapping; non-zero on broken chain
└── results/                       # gitignored run output (FR-009)

quakec/                            # game-logic changes (compiled into progs.dat)
├── telemetry.qc                   # NEW: event-emit helpers (tagged stdout) + sim_* headless autostart
├── progs.src                      # + telemetry.qc on the compile list
└── (small emit hooks + bot_* reads in:)
    ├── frikbot/bot.qc             # BotFrame(): sim_mode autostart → BotConnect(); read+clamp bot_* cvars
    ├── frikbot/bot_fight.qc       # map bot_accuracy → aim error; emit shot/hit
    ├── combat.qc                  # emit kill (T_Damage / Killed)
    ├── weapons.qc                 # emit shot/hit by weapon
    ├── items.qc                   # emit pickup
    ├── triggers.qc                # emit secret (trigger_secret)
    ├── client.qc                  # emit death (ClientObituary); level_end on exit
    └── world.qc                   # emit level_start (worldspawn) with map + seed

assets/libre-quake/                # NEW vendored submodule — chosen map + its assets (libre)

Justfile                           # update sim recipes pip/python → uv; build-sim builds sv-rel
docs/
├── telemetry.md                   # schema contract (bump only if implementation forces it)
├── bot-stats.md                   # add any sim_* control-cvar notes
└── licenses.md                    # record chosen LibreQuake map (Maps table)
```

**Structure Decision**: Single repo, two code surfaces. The **harness** (`sims/`,
Python/uv) owns everything awkward in QuakeC — UUIDs, `sha256` `config_hash`,
ISO-8601 wall-clock timing, clamping against documented ranges, JSON Schema
validation, exit codes, and the time-limit watchdog. The **QuakeC layer**
(`quakec/`) owns only what must come from inside the running game — the headless
bot autostart and per-event records carrying sim-time `t` and observable payloads
— emitted as tagged stdout lines (the engine↔harness contract). This split keeps
engine-C patches at zero and matches the existing `sims/harness.py` references in
the Justfile.

## Complexity Tracking

> No constitution violations. Nothing to justify.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
