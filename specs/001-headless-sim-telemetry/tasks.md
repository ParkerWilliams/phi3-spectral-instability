---
description: "Task list for Headless Simulation Run with Telemetry"
---

# Tasks: Headless Simulation Run with Telemetry

**Input**: Design documents from `/specs/001-headless-sim-telemetry/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅ (5 files)

**Tests**: INCLUDED — the plan's Testing section and the `sims/tests/` structure
explicitly call for `pytest` coverage (`test_schema.py`, `test_reconcile.py`,
`test_clamp.py`, `test_outcome.py`) tied to SC-002 / SC-003 / SC-006 / FR-008.

**Organization**: Tasks are grouped by user story (US1–US4, priorities P1–P3 from
spec.md) so each story is an independently testable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: `[US1]`–`[US4]`; Setup / Foundational / Polish carry no story label
- Exact file paths are included in every task

## Path Conventions

Single repo, two code surfaces (plan.md "Structure Decision"):
- **Harness** — Python/`uv` under `sims/` (`idledoom_sim/`, `configs/`, `schema/`, `tests/`)
- **Game logic** — QuakeC under `quakec/` (telemetry emit hooks compiled into `progs.dat`)
- **Content** — vendored LibreQuake map under `assets/libre-quake/`

> **Build locally or in CI, never on the 1 GB droplet** (it OOMs). The droplet may
> *run* sims once `fteqw-sv` + `progs.dat` exist. No engine-C patches in this feature.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the harness package, build wiring, and content — not story-specific.

- [ ] T001 Create the `sims/` Python package layout per plan.md: `sims/idledoom_sim/__init__.py`, `sims/configs/`, `sims/schema/`, `sims/tests/`, and `sims/results/.gitkeep` (tree already gitignored via `.gitignore:42`).
- [ ] T002 Author `sims/pyproject.toml` (uv-managed, Python 3.11+): runtime dep `jsonschema`; dev deps `pytest`, `ruff`, `mypy`; project metadata. Replaces the legacy `requirements.txt` reference (R9).
- [ ] T003 [P] Copy `specs/001-headless-sim-telemetry/contracts/summary.schema.json` and `event.schema.json` into `sims/schema/` as the canonical copies the harness validates against (plan.md keeps them identical to the contracts).
- [ ] T004 [P] Configure `ruff`, `mypy`, and `pytest` sections in `sims/pyproject.toml` (lint rules, strict-ish typing, test discovery under `tests/`) so `just check-python` / `just test` pass.
- [ ] T005 Update `Justfile` sim recipes from `pip`/`python` → `uv` (R9): `build-sim` runs `uv sync` and builds the dedicated server (`make -C engine/engine sv-rel`); `sim` → `uv run harness.py run --config configs/current.toml`; `sim-smoke` → `uv run harness.py smoke --config configs/smoke.toml`; `check-python` and `test` → `uv run ruff`/`uv run mypy`/`uv run pytest`.
- [ ] T006 Vendor LibreQuake as a submodule at `assets/libre-quake/`, select the smallest map exercising movement/combat/pickup/(ideally) ≥1 secret, and record its file/author/license/source in the `docs/licenses.md` Maps table (FR-015, R8; "adding a map" convention). Vendor locally, not on the droplet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The bare engine→game-logic→agent→telemetry→file pipeline every story rides on.

**⚠️ CRITICAL**: No user story can be exercised until this phase is complete — without the autostart shim there is no autonomous agent, and without the emit helper + parser + writer there is no telemetry at all.

- [ ] T007 [P] Create `sims/idledoom_sim/botstats.py` — machine-readable catalogue of every `bot_*` cvar (`name → {type, min, max, default}`) mirroring `docs/bot-stats.md`, plus the `sim_*` control cvars (`sim_mode`, `sim_seed`, `sim_time_limit`). Single source of ranges for clamping (R5, contracts/cvars.md).
- [ ] T008 Create `quakec/telemetry.qc` — the `@EVT|<t>|<type>|<k>=<v>|...` stdout emit helper, capture of `level_start_time` so `t = time - level_start_time`, and reads of `sim_mode` / `sim_seed` / `sim_time_limit` cvars (contracts/engine-event-line.md, contracts/cvars.md, R4).
- [ ] T009 Add `quakec/telemetry.qc` to the `quakec/progs.src` compile list (after `defs.qc`/FrikBot block so its globals are visible to the game files that call the emit helper).
- [ ] T010 Add the headless autostart shim to `quakec/frikbot/bot.qc` `BotFrame()`: when `cvar("sim_mode")` is set and no agent has spawned, call `BotConnect(0, 0, <skill>)` exactly once per level (one-shot guard). This is the autonomy mechanism with no human client (R2, FR-001/FR-002).
- [ ] T011 Create `sims/idledoom_sim/launcher.py` — locate `fteqw-sv` (env override → well-known `engine/engine/` path), build the `+set` command line (`deathmatch 0`, `skill`, `sv_cheats 1`, `sim_*`, `bot_*`, `+map`), spawn headless, stream stdout, and enforce a wall-clock watchdog that kills a server that overruns `sim_time_limit` (R1, FR-003).
- [ ] T012 Create `sims/idledoom_sim/telemetry.py` — parse `@EVT|...` stdout lines into event dicts (coerce numeric/token/`null` values per the event schema; tolerate and ignore non-`@EVT` engine log noise) (R4, contracts/engine-event-line.md).
- [ ] T013 Create `sims/idledoom_sim/writer.py` — generate `run_id` (UUID4), resolve `batch_id` (default a single-run batch), build non-colliding `results/<batch_id>/<run_id>` output paths, and provide the base file-write helpers (FR-009, R10).

**Checkpoint**: A headless `fteqw-sv` can be launched with `sim_mode 1`, the FrikBot agent autostarts, `@EVT` lines stream back and parse, and output paths resolve. Story work can begin.

---

## Phase 3: User Story 1 - Run one autonomous session and get a result (Priority: P1) 🎯 MVP

**Goal**: One command runs the agent headless on a map and writes exactly one schema-valid per-run summary with a terminal `outcome`.

**Independent Test**: Run against the vendored map with default config; confirm it completes with no window/human input and writes one `*.summary.json` validating against `summary.schema.json`, with `outcome ∈ {completed,died,timeout,error}` and `map`/`started_at`/`ended_at`/`duration_sec`/`stats` populated. (Stats may be zero until US2 wires gameplay events — the block is still structurally present and valid.)

### QuakeC: run boundaries & timeout

- [ ] T014 [US1] Emit `level_start{map, seed}` at worldspawn in `quakec/world.qc` (first event of every run; `seed` from `sim_seed`) (FR-011, FR-016, contracts).
- [ ] T015 [US1] Emit `level_end{outcome, time_sec}` on level exit/`NextLevel` in `quakec/client.qc` (last event), and add the in-engine `sim_time_limit` end so an overrunning run terminates as `timeout` (FR-003, R7).

### Harness: outcome → summary

- [ ] T016 [P] [US1] Create `sims/idledoom_sim/config.py` — load the TOML run config (`map`, `seed`, `time_limit`, `bot_*` passthrough) and apply `--map`/`--seed`/`--time-limit`/`--batch-id`/`--out` CLI overrides (contracts/harness-cli.md). (Clamping + `config_hash` are added in US3.)
- [ ] T017 [P] [US1] Create `sims/idledoom_sim/outcome.py` — terminal state machine: `completed` requires a terminal `level_end{outcome:"completed"}` **and** clean exit; else `died` / `timeout` / `error`; never `completed` on a broken chain (R7, FR-010, SC-006).
- [ ] T018 [US1] Add `aggregate(events) -> StatsBlock` to `sims/idledoom_sim/telemetry.py` returning a complete StatsBlock with every field present (counts default 0; `accuracy = 0` on zero shots). US2 fills in the real per-type counting (data-model StatsBlock).
- [ ] T019 [US1] In `sims/idledoom_sim/writer.py`, assemble and write `<run_id>.summary.json` (`schema_version:1`, `run_id`, `batch_id`, `config_hash`, ISO-8601 `started_at`/`ended_at`/`duration_sec`, `map`, `outcome`, `bot_config`, `stats`) and validate it against `sims/schema/summary.schema.json` before exit (FR-004, FR-012, SC-002).
- [ ] T020 [US1] Create `sims/harness.py` with the `run` subcommand wiring config → launcher → stdout parse → outcome → summary writer; exit `0` on a written valid summary, non-zero with a stderr diagnostic on a broken chain (FR-001, FR-010, contracts/harness-cli.md).
- [ ] T021 [P] [US1] Create `sims/configs/current.toml` — default run config: vendored `map`, a `seed`, a `time_limit`, and `bot_*` defaults (from `docs/bot-stats.md`).

### Tests for User Story 1

- [ ] T022 [P] [US1] `sims/tests/test_outcome.py` — assert the outcome state machine maps each terminal condition correctly and that an induced broken chain exits non-zero and is never reported as `completed` (SC-006, FR-010).
- [ ] T023 [P] [US1] `sims/tests/test_schema.py` — assert a produced `*.summary.json` validates against `sims/schema/summary.schema.json` (SC-002).

**Checkpoint**: `just sim` produces one schema-valid summary with a correct terminal `outcome`. MVP is demoable.

---

## Phase 4: User Story 2 - Capture the per-event stream (Priority: P2)

**Goal**: A chronological JSONL event stream (one record per line) plus summary `stats` that reconcile exactly with it.

**Independent Test**: Run on a map with ≥1 enemy and ≥1 item; confirm a `*.events.jsonl` is written, first event `level_start` and last `level_end`, every line validates against `event.schema.json`, timestamps are seconds since `level_start`, and event aggregates equal the summary `stats` (kills, shots/hits→accuracy, pickups, secrets) within rounding.

### QuakeC: gameplay event emits

- [ ] T024 [P] [US2] Emit `kill{victim, weapon, distance}` in `quakec/combat.qc` (the `Killed`/`T_Damage` death path); `victim` = monster classname, `weapon` = `IT_*` stem (FR-005, FR-011).
- [ ] T025 [P] [US2] Emit `death{cause, killer}` for agent death in `quakec/client.qc` `ClientObituary` (drives the `died` edge case) (FR-005).
- [ ] T026 [P] [US2] Emit `shot{weapon, target}` on fire and `hit{weapon, target, damage}` on landed damage in `quakec/weapons.qc` (accuracy denominator/numerator) (FR-005).
- [ ] T027 [P] [US2] Emit `pickup{item, value}` on item touch in `quakec/items.qc` (FR-005).
- [ ] T028 [P] [US2] Emit `secret{secret_id}` in `trigger_secret` in `quakec/triggers.qc`, and expose the map's `secrets_total` for the summary (FR-005, data-model).

### Harness: aggregation & JSONL output

- [ ] T029 [US2] Extend `aggregate()` in `sims/idledoom_sim/telemetry.py` to count `kill`/`death`/`shot`/`hit`/`pickup`/`secret`, build `weapon_usage` and `deaths_by_cause`, and compute `accuracy` (`shots_hit/shots_fired`, 4 dp, `0` on zero), `damage_dealt`/`damage_taken`, `time_to_exit_sec` (data-model StatsBlock, FR-006).
- [ ] T030 [US2] In `sims/idledoom_sim/writer.py`, write `<run_id>.events.jsonl` (one event object per line, each carrying `schema_version:1`) (FR-005, FR-012).
- [ ] T031 [US2] In `sims/harness.py`, write the events JSONL alongside the summary and assert the stream invariant (first `level_start`, last `level_end`) (US2 sc.1).

### Tests for User Story 2

- [ ] T032 [P] [US2] `sims/tests/test_reconcile.py` — aggregates computed from a sample event stream reconcile with the summary `stats` with zero discrepancy beyond documented rounding (SC-003).
- [ ] T033 [US2] Extend `sims/tests/test_schema.py` — assert every line of a produced `*.events.jsonl` validates against `sims/schema/event.schema.json` (SC-002).

**Checkpoint**: Behavior is fully reconstructable from events and the summary is a verified pure aggregate of them.

---

## Phase 5: User Story 3 - Configure the agent per run via cvars (Priority: P2)

**Goal**: Supplied `bot_*` params are clamped to documented ranges, recorded in `bot_config` with a stable `config_hash`, and at least `bot_accuracy` measurably changes telemetry.

**Independent Test**: Run the same map with `bot_accuracy=0.1` vs `0.9`; confirm both summaries record the clamped `bot_config` and a `config_hash` (equal for equal configs, differing otherwise), an out-of-range value (e.g. `5`) is clamped to `1.0` in `bot_config`, and higher `bot_accuracy` yields higher `stats.accuracy` (averaged over runs if needed).

- [ ] T034 [US3] Extend `sims/idledoom_sim/config.py` — accept `--bot.<name> VAL` overrides, clamp each `bot_*` to its `botstats.py` range **before** use, build the clamped `bot_config`, and compute `config_hash` = sha256 over canonical sorted-key JSON of `bot_config` (FR-007, FR-008, R5).
- [ ] T035 [US3] In `sims/idledoom_sim/launcher.py`, set the clamped `bot_*` values and `sim_seed` on the `+set` command line from the resolved config (contracts/cvars.md).
- [ ] T036 [US3] In `sims/idledoom_sim/writer.py`, record the clamped `bot_config` and `config_hash` into the summary (replacing the US1 placeholders) (FR-007).
- [ ] T037 [US3] Wire `bot_accuracy` → FrikBot aim error in `quakec/frikbot/bot_fight.qc` so higher accuracy produces measurably higher `stats.accuracy` — the SC-004 proof (R5).
- [ ] T038 [P] [US3] `sims/tests/test_clamp.py` — out-of-range inputs are clamped and the clamped value appears in `bot_config`; identical configs produce equal `config_hash`, any difference produces a different hash (FR-008, US3 sc.2–3).

**Checkpoint**: The harness is a tuning tool — results are tied to clamped inputs and a config change is visible in telemetry.

---

## Phase 6: User Story 4 - Fast smoke run as a CI gate (Priority: P3)

**Goal**: A fast variant exercises the whole chain within a small budget and returns a CI-usable success/failure exit status.

**Independent Test**: `just sim-smoke` finishes under the budget (target <60 s, SC-005) and exits `0` with a valid summary on a healthy build; a broken chain exits non-zero with a diagnostic and no `completed` summary.

- [ ] T039 [P] [US4] Create `sims/configs/smoke.toml` — minimal map + short `time_limit` targeting an under-60 s end-to-end run (SC-005).
- [ ] T040 [US4] Add the `smoke` subcommand to `sims/harness.py` — runs against `smoke.toml`, exits `0` only on a healthy chain with a schema-valid summary, non-zero on any break (FR-013, SC-006).
- [ ] T041 [US4] Wire `just sim-smoke` (`uv run harness.py smoke --config configs/smoke.toml`) as the CI gate — add/confirm a CI job (GitHub Actions or self-hosted runner) that runs it and fails the build on non-zero (FR-013; "main is buildable / CI must pass").

**Checkpoint**: The foundation is protected against silent rot; CI fails loudly when the chain breaks.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation reconciliation and end-to-end validation across all stories.

- [ ] T042 [P] Update `docs/bot-stats.md` — add the `sim_*` control-cvar notes and mark `bot_accuracy` **Wired** vs the other `bot_*` **recorded-only** for this slice (contracts/cvars.md, R5).
- [ ] T043 [P] Reconcile `docs/telemetry.md` with the implementation; bump `schema_version` only if implementation forced a schema change, otherwise note conformance to version `1` (FR-012, Assumptions).
- [ ] T044 [P] Record the four bounded open questions from `research.md` ("Remaining open questions": waypoints, event-volume/sampling, `sim_*` naming, engine RNG seeding) under `docs/design.md` Open Questions (§8/§11) per CLAUDE.md convention.
- [ ] T045 [P] Document the build-locally-not-on-droplet + `uv` workflow in `SETUP.md` (or a `sims/README.md`), matching quickstart.md step 0.
- [ ] T046 Run `quickstart.md` end-to-end (`just sim`, reconcile via `jq`, vary `--bot.bot_accuracy`, `just sim-smoke`, `uv run pytest`) and confirm every acceptance/SC holds.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup; **blocks all user stories**.
- **User Stories (Phase 3–6)**: all depend on Foundational. Recommended order is priority order (US1 → US2 → US3 → US4); US2/US3 are co-equal P2 and can proceed in parallel after US1's harness skeleton exists. US4 depends on US1 (the `run` flow it mirrors) and on a smoke-able chain.
- **Polish (Phase 7)**: depends on the stories whose behavior it documents/validates; T046 depends on all of US1–US4.

### Key cross-task dependencies

- T009 (progs.src) and T010 (autostart) depend on T008 (`telemetry.qc` exists).
- T011/T012/T013 (launcher/parser/writer skeletons) depend on T002 (pyproject) and T007 (botstats for cmdline ranges).
- US1: T019 (summary writer) depends on T013 (writer base), T017 (outcome), T018 (stats skeleton); T020 (CLI) depends on T011/T012/T016/T019.
- US2: T029 (aggregate) extends T018; T030 (jsonl) extends T013/T019's writer; the QuakeC emits (T024–T028) feed T029's counts.
- US3: T034 (clamp/hash) extends T016 (config); T036 extends T019; T037 is the only QuakeC behavioral wiring this slice.
- US4: T040 (smoke) reuses T020's `run` flow.

### Within each user story

- QuakeC emit hooks can land in parallel (different files), but all depend on Foundational T008's helper.
- Harness: config/outcome before writer; writer before the CLI that calls it.
- Tests (`test_*`) for a story can be authored in parallel and should pass once that story's implementation lands.

---

## Parallel Opportunities

- **Setup**: T003 and T004 run in parallel (different concerns); T006 (content) is independent of the Python scaffolding.
- **Foundational**: T007 (botstats) is independent of the QuakeC chain (T008–T010); the three harness skeletons (T011/T012/T013) are separate files.
- **US1**: T016 (config) and T017 (outcome) and T021 (current.toml) and the two tests (T022/T023) are all `[P]` — different files.
- **US2**: all five QuakeC emit hooks (T024–T028) are `[P]` — five different files.
- **US3/US2**: as co-equal P2 stories, can be worked by two developers in parallel once US1's harness skeleton is in.

### Parallel example — US2 QuakeC emits

```bash
Task: "Emit kill in quakec/combat.qc"
Task: "Emit death in quakec/client.qc"
Task: "Emit shot/hit in quakec/weapons.qc"
Task: "Emit pickup in quakec/items.qc"
Task: "Emit secret in quakec/triggers.qc"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup (scaffold harness, build wiring, vendor map).
2. Phase 2: Foundational (autostart shim + emit helper + launcher/parser/writer) — CRITICAL, blocks everything.
3. Phase 3: US1 — run one session, write a schema-valid summary with a real `outcome`.
4. **STOP and VALIDATE**: `just sim` → one valid summary, headless, no input. Demo.

### Incremental Delivery

1. Setup + Foundational → pipeline launches and emits.
2. + US1 → schema-valid summary + outcome (MVP). 
3. + US2 → event stream + reconciled stats.
4. + US3 → clamped/hashed config + visible `bot_accuracy` effect (tuning tool).
5. + US4 → smoke CI gate protecting the chain.
6. Polish → docs reconciled, quickstart validated.

### Suggested MVP scope

**User Story 1 only** (Phases 1–3): the irreducible "run the agent once, headless, get a result" primitive every later activity depends on.

---

## Notes

- `[P]` = different files, no dependency on an incomplete task.
- Zero engine-C patches (constitution): all new code is QuakeC + Python; build `fteqw-sv`/`progs.dat` locally or in CI, never on the droplet.
- The summary's `stats` is a pure function of the event stream (data-model) — keep it that way so SC-003 reconciliation stays checkable.
- Commit after each task or logical group; reference FR/SC/R IDs in messages.
- Stop at any checkpoint to validate a story independently.
