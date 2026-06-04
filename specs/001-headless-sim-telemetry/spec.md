# Feature Specification: Headless Simulation Run with Telemetry

**Feature Branch**: `001-headless-sim-telemetry`

**Created**: 2026-05-28

**Status**: Draft

**Input**: User description: "Headless simulation run with telemetry output: build/run the engine in dedicated/headless mode loading our game logic, drop the AI agent into a single libre map, play autonomously until level-clear/death/timeout, and emit telemetry per `docs/telemetry.md` (per-run summary JSON + per-event JSONL). Agent reads tunable params from cvars per `docs/bot-stats.md`. Out of scope: Tauri UI, window embedding, upgrade economy, offline progression."

## User Scenarios & Testing *(mandatory)*

The "user" for this feature is a **developer tuning the agent** (and, secondarily, **CI** acting as an automated developer). This slice produces no player-facing surface; its value is the data foundation that every later tuning, balancing, and regression-checking activity depends on.

### User Story 1 - Run one autonomous session and get a result (Priority: P1)

A developer issues a single command naming a map and an agent configuration. The agent plays the map autonomously — moving, fighting, looting — with no graphical window and no human input. When the session ends, a single machine-readable summary describes what happened.

**Why this priority**: This is the irreducible core. Without "run the agent once, headless, and find out how it did," there is no sim harness, no tuning loop, and no way to validate the engine→game-logic→agent chain at all. It is the MVP by itself.

**Independent Test**: Run the command against a known map with default config; confirm it completes without a window or human input and writes one summary record that validates against the `docs/telemetry.md` per-run summary schema.

**Acceptance Scenarios**:

1. **Given** a valid map and default agent config, **When** the developer starts a run, **Then** the agent plays autonomously and, on termination, exactly one summary record is written that conforms to the per-run summary schema.
2. **Given** a run that finishes, **When** the developer inspects the summary, **Then** `outcome` is exactly one of `completed`, `died`, `timeout`, or `error`, and `map`, `started_at`, `ended_at`, `duration_sec`, and `stats` are populated.
3. **Given** an agent that never reaches the exit, **When** the configured time limit elapses, **Then** the run ends with `outcome: "timeout"` and still produces a valid summary.

---

### User Story 2 - Capture the per-event stream (Priority: P2)

Beyond the summary, the developer needs a chronological, event-by-event record of what the agent did (started level, fired, hit, killed, picked up, found a secret, died, ended level) so behavior can be reconstructed and analyzed, not just scored.

**Why this priority**: The summary tells you *how well*; the event stream tells you *why*. Diagnosing behavior ("it dies to its own rockets," "it never finds the secret") requires events. Valuable immediately, but a meaningful summary (P1) is usable on its own first.

**Independent Test**: Run a session on a map containing at least one enemy and one item; confirm a JSONL event stream is written with one record per line conforming to the per-event schema, including `level_start` and `level_end`, and that event timestamps are seconds since `level_start`.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** the developer reads the event stream, **Then** the first event is `level_start` and the last is `level_end`, and every record validates against the per-event schema.
2. **Given** the event stream and the summary for the same run, **When** the developer aggregates the events, **Then** the aggregates reconcile with the summary (e.g. count of `kill` events == `stats.kills`; `shots_hit / shots_fired` == `stats.accuracy` within rounding).
3. **Given** a run on a map with a secret area, **When** the agent finds it, **Then** a `secret` event is recorded and `stats.secrets_found` reflects it.

---

### User Story 3 - Configure the agent per run via cvars (Priority: P2)

The developer supplies the agent's tunable parameters (the `bot_*` cvars catalogued in `docs/bot-stats.md`) at the start of a run, and the exact configuration actually used is recorded in the summary so a result can always be tied back to the inputs that produced it.

**Why this priority**: Tuning is impossible if you can't vary the inputs and know which inputs produced which result. This is what makes the harness a *tuning* tool rather than a fixed demo. Co-equal with the event stream.

**Independent Test**: Run the same map twice with two materially different configs (e.g. `bot_accuracy=0.1` vs `0.9`); confirm both summaries record the config used (and a stable `config_hash`), and that the recorded `bot_config` matches what was supplied.

**Acceptance Scenarios**:

1. **Given** a supplied set of `bot_*` parameters, **When** a run starts, **Then** the agent's behavior reflects those values and the summary's `bot_config` records exactly the values used.
2. **Given** two runs with identical configuration, **When** the developer compares their `config_hash`, **Then** the hashes are equal; for any differing configuration the hashes differ.
3. **Given** a parameter supplied outside its documented range in `docs/bot-stats.md`, **When** the run starts, **Then** the value is clamped to the documented range and the clamped value is what appears in `bot_config` (no silent acceptance of out-of-range input).

---

### User Story 4 - Fast smoke run as a CI gate (Priority: P3)

A developer (or CI) runs a fast, minimal variant that exercises the whole chain end-to-end within a small time budget, purely to detect that something broke (engine won't launch, game logic won't load, telemetry stopped conforming).

**Why this priority**: Protects "`main` is buildable at all times / CI must pass" (project convention). Depends on P1–P3 existing first, so it is lower priority, but it is what keeps the foundation from silently rotting.

**Independent Test**: Run the smoke variant; confirm it finishes within the budget and returns a success exit status with a valid summary, and returns a failure exit status if the chain is broken.

**Acceptance Scenarios**:

1. **Given** a healthy build, **When** the smoke run executes, **Then** it completes within the time budget and exits with a success status and a schema-valid summary.
2. **Given** a broken chain (e.g. game logic fails to load), **When** the smoke run executes, **Then** it exits non-zero with a diagnostic and does **not** report success.

---

### Edge Cases

- **Agent gets stuck / cannot path to exit** → time limit triggers `outcome: "timeout"`; a valid summary is still produced.
- **Agent dies** → `outcome: "died"`; a `death` event with a cause is recorded; summary remains valid.
- **Engine fails to launch, map missing, or game logic fails to load** → run exits non-zero with a diagnostic; no summary is emitted that claims a successful outcome (see FR-010).
- **Map has no enemies / no items** → run still produces a valid summary; rate stats with a zero denominator (e.g. accuracy with zero shots) are reported as `0`, not an error.
- **Very high event volume on a long run** → event logging must not corrupt or truncate the stream; whether to sample is an open question in `docs/telemetry.md` and is **out of scope** here (log all events for this slice).
- **Two runs started close together** → each gets a unique `run_id` and a non-colliding output path; neither overwrites the other.
- **Run interrupted mid-session (killed/cancelled)** → partial output must be distinguishable from a clean run (it must not masquerade as a completed summary).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST run an agent session with no graphical window and no human input (headless / non-interactive), driven by a single command.
- **FR-002**: The agent MUST play the map autonomously for the entire session; no moment-to-moment human control is possible.
- **FR-003**: A session MUST terminate on exactly one of: reaching the level exit (`completed`), agent death (`died`), or elapse of a configurable time limit (`timeout`). Engine/load failures terminate as `error` (FR-010).
- **FR-004**: On termination, the system MUST write exactly one per-run summary conforming to the per-run summary schema in `docs/telemetry.md`, including `run_id`, `config_hash`, `started_at`, `ended_at`, `duration_sec`, `map`, `outcome`, `bot_config`, and `stats`.
- **FR-005**: During the session, the system MUST emit a per-event stream (one record per line) conforming to the per-event schema in `docs/telemetry.md`, including at minimum `level_start`, `level_end`, and events for kills, deaths, shots, hits, pickups, and secrets as they occur.
- **FR-006**: Summary aggregate `stats` MUST be consistent with the event stream for the same run (counts and rates derivable from the events match the summary within documented rounding).
- **FR-007**: The agent's tunable parameters MUST be supplied as run configuration via the `bot_*` cvars defined in `docs/bot-stats.md`, and the exact configuration used MUST be recorded in the summary (`bot_config` plus a stable `config_hash`).
- **FR-008**: Parameter values supplied outside their documented range MUST be clamped to the documented range, and the clamped value MUST be the one recorded in `bot_config` (no silent out-of-range acceptance).
- **FR-009**: Every run MUST have a unique `run_id`, and outputs MUST be written to a path that cannot collide with another run (per `docs/telemetry.md`: `sims/results/<batch-id>/<run-id>...`). The `sims/results/` tree is not committed to version control.
- **FR-010**: A run that fails to start or crashes before clean termination MUST exit with a non-zero status and surface a diagnostic, and MUST NOT leave behind a summary that claims a successful (`completed`) outcome; such failures are recorded as `outcome: "error"` when a summary is producible, otherwise no summary is written.
- **FR-011**: Telemetry MUST follow the conventions in `docs/telemetry.md`: event timestamps are seconds since `level_start`; map names are the BSP filename without extension; weapon and monster names match the game-logic class/flag stems.
- **FR-012**: Every summary file and event file MUST carry a `schema_version` field (current value: `1`).
- **FR-013**: The system MUST provide a fast smoke variant that exercises the full chain within a small time budget and returns a success/failure exit status suitable as a CI gate.
- **FR-014**: Reproducibility is **statistical**, not bit-exact: repeated runs with the same agent configuration and map seed MUST produce comparable distributions of `outcome` and key `stats`, but individual runs are **not** required to be byte-identical. Tuning conclusions are therefore drawn from aggregates over multiple runs of a configuration. This slice runs one run per invocation (see Assumptions) and MUST NOT preclude a later batch runner from aggregating N runs of the same config (supported by the unique-`run_id` / non-colliding-path design in FR-009).
- **FR-015**: The agent MUST run on a vendored **LibreQuake** map — the smallest level suitable for exercising movement, combat, item pickup, and (ideally) at least one secret — with no dependency on id Software assets, maps, monsters, or trademarks. This slice therefore includes vendoring the LibreQuake base content required to load that map. The chosen map and its source/license MUST be recorded in `docs/licenses.md` (per the project's "adding a map" convention).
- **FR-016**: A configurable map seed MUST be accepted per run and recorded so that runs can be reproduced and compared (used by `level_start`'s `seed` field).

### Key Entities *(include if feature involves data)*

- **Run**: one instance of the agent playing one map start-to-finish. Identified by a unique `run_id`; optionally grouped under a `batch_id`. Has a configuration, a seed, a terminal `outcome`, and produces one summary plus one event stream.
- **Per-run summary**: the aggregated machine-readable result of a Run (schema in `docs/telemetry.md`): identity, timing, map, outcome, the agent config used, and aggregate stats.
- **Event**: a single observable occurrence during a Run (`level_start`, `kill`, `death`, `shot`, `hit`, `pickup`, `secret`, `level_end`), timestamped in seconds since `level_start`, carrying a type-specific payload.
- **Agent configuration**: the set of `bot_*` tunable parameters (from `docs/bot-stats.md`) applied for a Run, plus its derived `config_hash`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can go from a single command to a schema-valid per-run summary for one autonomous session, with no graphical window and no manual interaction, in one step.
- **SC-002**: 100% of summary files and event files produced validate against the schemas in `docs/telemetry.md` (validated by an automated schema check).
- **SC-003**: For a run on a map with at least one enemy and one item, the aggregates computed from the event stream reconcile with the summary `stats` (kills, shots, hits, pickups, secrets) with zero discrepancies beyond documented rounding.
- **SC-004**: Two runs with materially different agent configurations on the same map produce summaries whose key `stats` differ in the expected direction (e.g. higher `bot_accuracy` yields higher `stats.accuracy`), demonstrating that configuration changes are reflected in behavior and captured in telemetry; for subtle configuration differences this may require aggregating several runs per config (FR-014).
- **SC-005**: The smoke variant completes within its time budget (target: under 60 seconds of wall-clock on a developer machine) and correctly returns success on a healthy build and failure on a broken chain.
- **SC-006**: A failed run (missing map, unloadable game logic, crash) is never reported as a successful `completed` outcome — it exits non-zero and is distinguishable from a clean run in 100% of induced-failure tests.

## Assumptions

- **Engine & agent baseline reused**: This slice builds on the already-chosen engine (FTEQW, ADR-0001) and the vendored FrikBot-derived game logic; it does not introduce a new engine or rewrite the agent. The agent need not be *good* — only autonomous and configurable — for this slice to deliver value.
- **`docs/telemetry.md` is the schema contract**: Output conforms to the existing schema (version `1`). If implementation reveals a needed schema change, it is made in `docs/telemetry.md` first and the version is bumped there.
- **Realtime-or-faster is acceptable for v1**: Tick acceleration / faster-than-realtime simulation (design §8) is a later optimization; this slice is satisfied by a headless run at any speed that terminates within the time limit. Parallel/batch execution (`sim-batch`) is out of scope here beyond not precluding it (FR-009 unique paths).
- **Single map, single run per invocation**: `just sim` runs one (vendored LibreQuake) map per invocation in this slice; batch tuning matrices and multi-run aggregation (`sim-batch`) are a later feature, not precluded by this slice (FR-014, FR-009).
- **Statistical tuning implication**: because reproducibility is statistical (FR-014), reliably comparing two configurations will require several runs each; this slice delivers the single-run primitive and the telemetry that makes such aggregation possible, but does not itself implement the aggregation/averaging layer.
- **Failure telemetry default**: When a run starts but crashes, an `error` summary is preferred; when it never starts, a non-zero exit plus log is sufficient (FR-010).
- **Out of scope (explicit)**: the Tauri host UI, engine-window embedding, the currency/upgrade economy, offline/idle progression, live-gameplay SQLite telemetry, and per-frame position traces.
- **Dependency**: requires the engine submodule checked out and buildable, the game logic compilable to a loadable `progs.dat`, and the **LibreQuake base content vendored** (per CLAUDE.md repo layout, e.g. `assets/libre-quake/`) so the chosen map and its assets load. Vendoring LibreQuake is in scope for this slice; broader map curation is not.
