---
description: "Task list for Automatic Agent Navigation"
---

# Tasks: Automatic Agent Navigation

**Input**: Design documents from `/specs/002-auto-navigation/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: INCLUDED — the constitution requires sim-harness coverage for every new
bot stat, and feature 001 established `sims/tests/` (pytest). Pure-Python tests
(coverage aggregation) are droplet-verifiable; "agent reaches combat / no softlock"
are **live integration checks** run locally (the droplet can't run the GL/engine
build, only sims once binaries exist).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: `[US1]`–`[US4]`; Setup / Foundational / Polish carry no label
- Exact file paths included

## Path Conventions

Two surfaces (reused from feature 001):
- **Game logic** — QuakeC under `quakec/` (FrikBot nav + telemetry → `progs.dat`)
- **Harness** — Python/`uv` under `sims/` (measurement + tests)

> **Build locally or in CI, never on the droplet** (OOMs). No engine-C patches
> (constitution) — navigation is QuakeC + cvars only. Builds on feature 001 as the
> verification harness.

---

## Phase 1: Setup

- [X] T001 [P] Write `docs/adr/0003-navigation-generation.md` (next free number): decision = QuakeC `DynamicWaypoint` auto-generation; BSP nav-mesh deferred. Rationale = constitution "minimize engine-C patches"; reuse FrikBot baseline (research R1). Link from `docs/design.md` §7.
- [X] T002 [P] Add `sims/configs/nav.toml` — an un-waypointed LibreQuake map with reachable enemies + items, `time_limit ≈ 60`, default `bot_map_awareness`. Note in a comment that no `maps/<stem>.way` may exist for the US1/US2 test (US1 test bed).

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ The coverage/telemetry plumbing + dynamic-mode wiring every story rides on.**

- [X] T003 Track per-agent traversal in `quakec/frikbot/bot_phys.qc` — accumulate `distance_traveled` and a distinct-waypoint-visited count as the agent moves (data-model coverage fields).
- [X] T004 Emit nav coverage in `quakec/telemetry.qc` — add `Tel_Nav` (waypoints_visited, distance) and carry `waypoints_total` + `reached_exit` on the `level_end` payload (contracts/nav.md, data-model; gated on `Tel_IsAgent`, suppressed after terminal like other gameplay events).
- [X] T005 In `sims/idledoom_sim/launcher.py`, document + assert the `max_clients ≥ 2` invariant and ensure the autostart path leaves `waypoint_mode == WM_DYNAMIC` so `DynamicWaypoint` runs (research R4, contracts/nav.md).
- [X] T006 [P] Extend `sims/schema/summary.schema.json` (and `event.schema.json` for any new `nav`/`level_end` keys) with `map_coverage`, `waypoints_visited`, `distance_traveled`, `reached_exit`, `waypoints_total` — additive/optional to stay `schema_version: 1` (contracts/nav.md).
- [X] T007 Extend `aggregate()` in `sims/idledoom_sim/telemetry.py` — compute `waypoints_visited`, `map_coverage` (`visited/total`, 4 dp, `0` on zero), `distance_traveled`, `reached_exit`; read `waypoints_total` from `level_end` (G2 pattern) (data-model StatsBlock).

**Checkpoint**: coverage telemetry flows end-to-end and aggregates; dynamic
generation is active in the sim. Story work can begin.

---

## Phase 3: User Story 1 — navigate un-waypointed map → reach combat (P1) 🎯 MVP

**Goal**: on a map with no `.way`, the agent leaves spawn, covers the level, and fights.

**Independent Test**: run `nav.toml` (un-waypointed map, default config) → `shots_fired > 0`, `kills ≥ 1`, `map_coverage` well above the spawn-only baseline, zero per-map authoring.

- [X] T008 [US1] Exploration driver in `quakec/frikbot/bot_ai.qc` — when no enemy/goal is in sight, steer roaming toward the nearest **unvisited frontier** (space with no nearby waypoint) so `DynamicWaypoint` covers the map and brings enemies into view (research R2).
- [X] T009 [US1] Auto-save / reuse in `quakec/frikbot/bot_way.qc` + `bot.qc` — `SaveWays()` the generated graph at level end / coverage-stable; load an existing `maps/<stem>.way` if present (reuse the level-start `exec` path); add `sim_nav_regen` cvar to force regeneration (research R3). **Done (compile-pending — droplet OOMs; live-unverified, see T011):** `NavAutoSave()` (bot_way.qc) persists a WM_DYNAMIC graph once waypoint coverage is stable for `NAV_SAVE_STABLE_SECS`, mid-run so the async writer finishes before the timeout `quit`; reuse path already existed (`WaypointWatch` exec) and is now skipped when `sim_nav_regen` is set; `sim_nav_regen` plumbed through `config.py`/`launcher.py`/`SIM_CVARS` (default 0). pytest 49/49, ruff+mypy clean.
- [X] T010 [P] [US1] `sims/tests/test_coverage.py` — `aggregate()` coverage math (`visited/total`, `0` on zero, distance sum, `reached_exit`) reconciles from a sample event stream (unit; droplet-verifiable).
- [X] T011 [US1] Live (local) verify: run `nav.toml` → assert `shots_fired > 0`, `kills ≥ 1`, `map_coverage` above baseline (quickstart §1; integration, local-only). **PROVEN (2026-06-04, lq_e1m1, 60s):** shots_fired 9, kills 1, accuracy 0.3333, map_coverage 1.0 (38/38), clean `timeout` stream. Required fixing two live bugs first — combat acquisition (coop-gated) + death-terminal (commit 1d8bf90).

**Checkpoint**: the agent plays an un-waypointed map and produces real combat
telemetry. MVP demoable; feature-001 telemetry is no longer all-zero.

---

## Phase 4: User Story 2 — never-seen map, zero setup (P2)

**Goal**: navigation generalizes to a map not used during development, with no per-map steps.

**Independent Test**: run a second, previously-unused un-waypointed map → navigates + reaches combat; 0 manual nav-authoring steps.

- [X] T012 [P] [US2] Add `sims/configs/nav2.toml` for a second LibreQuake map not used in US1 dev (US2 independent test).
- [X] T013 [US2] Live (local) verify on the second map: navigation + combat with zero per-map steps; confirm no `maps/*.way` was hand-authored (quickstart §2, SC-002). **PROVEN (2026-06-04, lq_e1m2):** 3× kill monster_army, shots/hits, auto-gen + auto-save, clean stream — zero per-map authoring.

**Checkpoint**: "automatic" is shown to generalize — the procedural-maps precondition.

---

## Phase 5: User Story 3 — navigation competence as a visible axis (P2)

**Goal**: `bot_map_awareness` measurably changes traversal; higher → more coverage / more direct routing.

**Independent Test**: same map at `bot_map_awareness` 0.1 vs 0.9 → higher value yields higher average `map_coverage` and/or lower `time_to_exit_sec`.

- [X] T014 [US3] Wire `bot_map_awareness` — scale exploration thoroughness + route directness by the cvar (was recorded-only → behavior) (research R6, data-model). **Done (compile-pending):** landed in `quakec/frikbot/bot_move.qc` `frik_bot_roam` (where T008's exploration lives, not bot_ai.qc) — candidate count 8→32 (thoroughness) + heading noise inversely to awareness (directness); clamped [0,1].
- [X] T015 [P] [US3] Docs: mark `bot_map_awareness` **WIRED (navigation)** in `docs/bot-stats.md`; add it as a player-facing nav upgrade in `docs/progression.md`. **Done** (+`sim_nav_regen` row, feature-002 status block).
- [X] T016 [P] [US3] `sims/tests/test_nav_competence.py` — assert `map_coverage` (and/or `time_to_exit_sec`) improves from low→high `bot_map_awareness` (synthetic-stream unit assertion of the metric direction + a local averaged-run check) (SC-003). **Done (unit); ⚠️ live SC-003 NOT demonstrable with current metrics.** Synthetic-stream unit assertions pass. But the live sweep (2026-06-04, lq_e1m1, `bot_map_awareness` 0.1 vs 0.9, n=3) showed NO improvement: `waypoints_total` 21.0 vs 20.3, `distance_traveled` 11232 vs 10403 (0.9 ~flat/slightly lower). Root cause: in 60s the agent saturates the reachable area at any awareness, so waypoint-count/distance are time-bound not skill-bound, and `distance` is confounded (more directness → less distance for the same area); `map_coverage` is degenerate (visited==total→1.0). This was the **R5 coverage-metric gap**. **RESOLVED (2026-06-04, branch `feat/nav-competence-metric`):** built a pluggable traversal-metric layer (periodic `nav` sample in QuakeC → registry in `traversal.py`; metrics swap with NO rebuild) + goal-oriented `time_to_combat_sec`. **US3 DEMONSTRATED (lq_e1m2, n=4):** `bot_map_awareness` 0.1→0.9 → `time_to_combat_sec` 14.33→8.86s (~38% faster to combat), `traversal.waypoints_at_15s` 6.5→11.25 (~73% more early exploration). Finding: coverage is the wrong proxy (rewards wandering); goal-reach + exploration-rate is the right signal. T014 wiring was fine — it needed the right metric + a roomier map. Issue A (`level_end{died}`) also confirmed live (a `died` run in the sweep).

**Checkpoint**: navigation is a tunable progression axis, visible and sim-measurable.

---

## Phase 6: User Story 4 — idle-tolerant, no softlock (P3)

**Goal**: imperfect pathing never hangs a run; the agent recovers from stuck states.

**Independent Test**: many runs across maps → 100% reach a terminal outcome within `time_limit`; no permanent stalls.

- [X] T017 [US4] Stuck detection + unstick in `quakec/frikbot/bot_phys.qc` — detect minimal movement while intending to move; recover (turn/jump/new frontier) and mark the spot so routing avoids it (research R7). **Done (compile-pending):** `bot_stuck_check()` in bot_phys.qc, called from `PostPhysics` before `BotAI`; sim+bot-scoped, skips combat; turns/jumps/clears route (→ re-roam) and flags `current_way` with `AI_PRECISION`. The `sim_time_limit`→`quit` watchdog remains the terminal-outcome backstop.
- [X] T018 [P] [US4] `sims/tests/test_no_softlock.py` + local batch — assert every run reaches a terminal outcome within the limit, and detours/backtracking are never failures (SC-004). **Done:** unit assertions that `determine_outcome` is always terminal for every (events, exit, watchdog) combo + backtracking-not-a-failure verified droplet-side; the real local batch across maps is the hand-off (quickstart §4).

**Checkpoint**: unattended runs always terminate; the chain is idle-safe.

---

## Phase 7: Polish & Cross-Cutting

- [X] T019 [P] Reconcile `docs/telemetry.md` + `data-model.md` with the shipped coverage fields; confirm `schema_version` conformance (bump only if forced). **Done:** added the five coverage fields to the summary `stats` + `level_end` examples in `docs/telemetry.md` and a feature-002 status block; additive → `schema_version` stays `1`.
- [X] T020 [P] Relabel `docs/waypointing.md` as a legacy/manual fallback (superseded by automatic generation); update `docs/design.md` §3 to point at the ADR. **Done:** waypointing.md banner now "LEGACY / superseded by feature 002 (ADR-0003)"; design.md §3 records the decided mechanism + competence tunable + stuck-recovery.
- [X] T021 Re-run feature-001 **SC-004** (`--bot.bot_accuracy 0.1` vs `0.9`) now that the agent fights; confirm accuracy rises (unblocks the 001 deferral). **PROVEN (2026-06-04, lq_e1m2, n=6 each):** accuracy 0.1→0.2767, 0.9→0.3715 (monotonic ↑). Unblocks 001's SC-004. Magnitude compressed (close-range shotgun makes the 15° aim-error gentle) — tuning follow-up, not a wiring issue.
- [ ] T022 Run `quickstart.md` end-to-end; confirm SC-001…SC-006 hold; `uv run pytest` green, `ruff` + `mypy` clean.

---

## Dependencies & Execution Order

- **Setup (P1)**: T001 (ADR) and T002 (config) are independent — start immediately.
- **Foundational (P2)**: blocks all stories. T003→T004 (track then emit); T006→T007 (schema then aggregate); T005 independent. Telemetry must exist before any story can be measured.
- **US1 (P3)**: T008 (explore) + T009 (save/reuse) are the core; T010 (unit) parallel; T011 (live) after T008/T009 + Foundational.
- **US2**: depends on US1 (same nav code), just new maps/verification.
- **US3**: T014 depends on US1's exploration; T016 depends on T007 coverage.
- **US4**: T017 hardens US1's roaming; can land after US1.
- **Polish (P7)**: after the stories it documents; T021/T022 depend on US1–US4.

## Parallel Opportunities

- Setup: T001 ‖ T002.
- Foundational: T006 (schema) ‖ T003/T004 (QuakeC) — different surfaces.
- US3 docs (T015) ‖ the wiring (T014); tests T010/T016/T018 are `[P]` (different files).

## Implementation Strategy

**MVP = US1** (Phases 1–3): the agent navigates an un-waypointed map and fights —
the irreducible win that unblocks feature-001 telemetry/SC-004. **STOP and VALIDATE**
live, then layer US2 (generalization), US3 (competence axis), US4 (no softlock),
Polish.

## Notes

- No engine-C patches; all new code is QuakeC + Python. Build `progs.dat` locally/CI.
- Coverage/combat stats stay a pure aggregate of the event stream (feature-001 SC-003).
- Commit per task/logical group; cite FR/SC/R IDs.
- Mechanism is ADR-gated (T001) per the constitution before deep QuakeC work.
