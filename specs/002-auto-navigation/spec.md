# Feature Specification: Automatic Agent Navigation

**Feature Branch**: `002-auto-navigation`

**Created**: 2026-06-02

**Status**: Draft

**Input**: User description: "Automatic agent navigation — the agent must traverse
a level on its own (path between areas, use doors/lifts, jump gaps, reach
objectives/items/enemies) with NO hand-authored waypoints, because maps will be
procedurally generated. Navigation competence is a progression axis that improves
over time; imperfect/'silly' pathing is acceptable for an idle game. First win:
the autostarted agent roams an un-waypointed LibreQuake map and reaches combat so
feature-001 telemetry goes non-zero (unblocking SC-004). Mechanism (FrikBot
DynamicWaypoint auto-record vs BSP nav-mesh) is a planning decision."

## Context

Builds directly on **feature 001 (headless sim + telemetry)**, which is the
verification harness for this work. Today the agent has no navigation data on
LibreQuake maps (FrikBot only ships waypoints for id1 `dm1`–`dm6`), so it wanders
near spawn, never reaches monsters, and produces all-zero combat telemetry — which
left feature 001's SC-004 (`bot_accuracy` → `stats.accuracy`) unprovable. The
design direction (`docs/design.md` §3, §6) is that navigation must be **automatic**
(procedural maps can't be hand-waypointed) and that navigation skill is a
**first-class progression axis**. Hand-recorded `.way` files (`docs/waypointing.md`)
are explicitly temporary scaffolding that this feature replaces.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The agent navigates an un-waypointed map and reaches combat (Priority: P1) 🎯 MVP

The agent is dropped into a map for which **no one authored waypoints**. On its
own it leaves the spawn area, traverses the level, and engages the enemies and
items that are there — without any human preparing navigation data for that map.

**Why this priority**: This is the irreducible win. It removes the manual-waypoint
blocker, makes the agent actually *play*, and turns feature 001's telemetry from
all-zero into real data. Everything else (procedural maps, progression) builds on
"it can navigate at all."

**Independent Test**: Run the feature-001 headless sim on a LibreQuake map that
has **no `.way` file**, with default config. Confirm the agent roams (covers
meaningfully more than the spawn area) and reaches combat: `stats.shots_fired > 0`
and `stats.kills ≥ 1` in the majority of runs within the standard time limit — with
zero per-map navigation authoring done beforehand.

**Acceptance Scenarios**:

1. **Given** a map with reachable enemies and no hand-authored waypoints, **When**
   a sim run executes, **Then** the agent leaves spawn, reaches enemies, and the
   summary shows non-zero `shots_fired` and at least one `kill`.
2. **Given** the same map, **When** several runs execute, **Then** combat occurs
   in the majority of them (not a one-off fluke).
3. **Given** a map with reachable items, **When** a run executes, **Then**
   `items_collected > 0` (the agent reaches pickups, not just enemies).

---

### User Story 2 - Works on a never-before-seen map with zero per-map setup (Priority: P2)

A brand-new map the agent has never encountered (the stand-in for a procedurally
generated level) is loaded. The agent navigates it with **no per-map authoring,
config, or human step** of any kind.

**Why this priority**: Procedural generation is the reason navigation must be
automatic. If navigation needs any per-map human work, it does not scale to
generated content. This proves the "automatic" property generalizes.

**Independent Test**: Point a sim run at a LibreQuake map that was *not* used while
building the feature and has no `.way` file or other prep. Confirm the agent still
navigates and reaches combat, with literally zero map-specific steps performed.

**Acceptance Scenarios**:

1. **Given** a previously unused map and no per-map preparation, **When** a run
   executes, **Then** the agent navigates it and reaches combat as in US1.
2. **Given** any supported map, **When** it is added to the rotation, **Then** the
   number of manual navigation-authoring steps required is zero.

---

### User Story 3 - Navigation competence is a visible progression axis (Priority: P2)

How well the agent gets around is a **tunable that improves with progression**.
At low competence it paths crudely (backtracks, takes long routes, misses
shortcuts); at high competence it routes more directly, covers more of the level,
and reaches objectives faster. The change is observable within a run.

**Why this priority**: Navigation improving over time is core to the game's
fantasy ("watching your friend get better") and to the design's progression model.
It also makes navigation tunable for the sim/balancing harness.

**Independent Test**: Run the same map at low vs high navigation competence and
compare a traversal metric (e.g., fraction of the level reached / map coverage, or
time-to-reach-exit) averaged over several runs; the higher setting measurably
improves it.

**Acceptance Scenarios**:

1. **Given** two navigation-competence settings (low, high) on one map, **When**
   each runs several times, **Then** the high setting yields measurably better
   traversal (more coverage and/or faster objective reach) on average.
2. **Given** a competence increase, **When** the next run plays, **Then** a viewer
   can see the difference within ~1–2 minutes (the §3 visible-progression rule).

---

### User Story 4 - Idle-tolerant: imperfect navigation never softlocks a run (Priority: P3)

Because this is an idle game running unattended, the agent's clumsiness must never
*hang* a run. It may take silly detours or briefly get stuck, but it always
recovers and the run reaches a terminal outcome.

**Why this priority**: Idle play means nobody is watching to rescue a wedged
agent. Imperfect pathing is fine; a permanent stall that prevents the run from
ending is not.

**Independent Test**: Run many sessions on assorted maps; confirm 100% reach a
terminal `outcome` within the time limit and none get permanently stuck (the agent
detects and escapes stuck states).

**Acceptance Scenarios**:

1. **Given** any run, **When** the agent wedges against geometry, **Then** it
   detects the stall and recovers (resumes moving) rather than freezing for the
   rest of the run.
2. **Given** a batch of runs, **When** they complete, **Then** every run reaches a
   terminal outcome within the time limit (no softlocks), and detours/backtracking
   alone are never counted as failures.

### Edge Cases

- **Disconnected regions**: a map area unreachable from spawn (gap, locked door) —
  the agent covers what's reachable and still terminates; unreachable enemies/items
  simply aren't engaged (not a failure).
- **No reachable enemies**: a sparse/empty map — the agent still roams and the run
  terminates cleanly (combat metrics legitimately zero).
- **Stuck/oscillation**: corners, lifts mid-cycle, ledges — must be detected and
  escaped (US4).
- **Very large or very open map**: navigation must still produce useful routing
  within the time/compute budget.
- **Generation cost**: producing the navigation data must not blow the fast smoke
  budget (feature 001 SC-005, < 60s end-to-end).
- **Dynamic obstacles**: doors/lifts that must be triggered or waited for.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The agent MUST navigate and traverse a map for which **no
  hand-authored waypoints / `.way` file exist**.
- **FR-002**: Navigation data MUST be produced **automatically** — no per-map
  human authoring, configuration, or manual step — and be available by the time
  the agent needs it in a run.
- **FR-003**: On a map with reachable enemies and items, the agent MUST reach and
  engage them, producing non-zero combat/pickup telemetry (`shots_fired`,
  `kills`, `items_collected`) within a normal run.
- **FR-004**: Navigation MUST work on a map the system has never seen before with
  zero per-map setup (the procedural-map requirement).
- **FR-005**: Navigation competence MUST be an adjustable parameter, and higher
  competence MUST produce **measurably better traversal** (more of the level
  reached and/or more direct/faster routing), so progression is visible and
  sim-measurable.
- **FR-006**: The agent MUST detect and recover from stuck/stalled states so that
  imperfect navigation never prevents a run from reaching a terminal outcome
  within the time limit.
- **FR-007**: Imperfect navigation (backtracking, detours, missed shortcuts) MUST
  be treated as acceptable behavior, never as a run failure (idle-tolerant).
- **FR-008**: Normal play MUST NOT depend on hand-recorded waypoints; the manual
  `.way` workflow (`docs/waypointing.md`) is superseded by the automatic process.
- **FR-009**: Navigation behavior MUST be observable in telemetry (e.g., level
  coverage / distance traversed / reached-exit / time-to-exit) so progression is
  legible and the sim harness can measure FR-005.
- **FR-010**: Producing the navigation data MUST fit within the run and smoke-test
  budgets (it must not break feature 001's fast-iteration / < 60s smoke gate).
- **FR-011**: Completing this feature MUST unblock the feature-001 deferred items
  that depend on combat occurring — chiefly the SC-004 proof (`bot_accuracy` →
  higher `stats.accuracy`) and the end-to-end quickstart.

### Out of scope (this feature)

- **Procedural map *generation* itself** — this feature makes navigation *ready*
  for generated maps; the generator is separate future work.
- **The choice of generation mechanism** (FrikBot `DynamicWaypoint` auto-record
  vs BSP-derived nav-mesh vs learned) — a planning/ADR decision, deliberately not
  constrained here (`docs/design.md` §7).
- **Combat/aim behavior** — owned by the bot-stats work; this feature only gets
  the agent *to* the fight.

### Key Entities *(include if feature involves data)*

- **Navigation data**: the traversable representation the agent follows (graph,
  mesh, or equivalent) — produced automatically per map; not hand-authored.
- **Navigation competence**: the tunable skill level governing route quality /
  coverage / traversal speed (a progression axis).
- **Map**: a level the agent plays — authored or (eventually) procedurally
  generated; navigation must require no per-map human prep.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On an un-waypointed map with reachable enemies, the agent reaches
  combat (`shots_fired > 0` and `kills ≥ 1`) in **≥ 80% of runs** within the
  standard time limit — with zero per-map navigation authoring.
- **SC-002**: Adding a new map to the rotation requires **0 manual
  navigation-authoring steps**, and the agent still navigates it (US2).
- **SC-003**: Higher navigation competence measurably improves traversal,
  averaged over runs (US3/FR-005). **DEMONSTRATED (2026-06-04, lq_e1m2, n=4):**
  `bot_map_awareness` 0.1→0.9 cut `time_to_combat_sec` 14.33→8.86 (~38% faster to
  the fight) and raised `traversal.waypoints_at_15s` 6.5→11.25 (~73% more
  exploration by t=15s). **Metric note:** the original "level coverage" framing was
  a poor proxy — coverage saturates on small maps and *rewards aimless wandering*
  (low competence wanders → touches more cells). The competence signal is
  **goal-reach + exploration-rate** (`time_to_combat_sec`, `*_at_15s`), not area
  coverage. See `docs/telemetry.md` and `sims/idledoom_sim/traversal.py`.
- **SC-004**: **100% of runs reach a terminal outcome within the time limit** — no
  run permanently stalls (US4/FR-006).
- **SC-005**: With navigation in place, feature-001's SC-004 becomes
  demonstrable: averaged over runs, higher `bot_accuracy` yields higher
  `stats.accuracy` (the agent now actually shoots at things).
- **SC-006**: Navigation data is ready in time without breaking the smoke budget —
  `just sim-smoke` still completes end-to-end in under 60s.

## Assumptions

- Feature 001's headless sim + telemetry is the verification harness; this feature
  is measured through it (shots/kills/pickups/coverage in the summary).
- The agent is the FrikBot-derived gamecode (ADR-0001); navigation is added there
  (or in generation tooling around it), not by replacing the engine.
- Testing uses LibreQuake maps now; procedural maps are a later, separate feature
  that this one must be ready for.
- Single-agent context (`deathmatch 0`, one autostarted agent) as in feature 001.
- The generation mechanism is chosen during `/speckit-plan` (leading candidate:
  FrikBot `DynamicWaypoint` auto-record-and-save; alternative: BSP nav-mesh) and
  recorded as an ADR — the spec stays mechanism-agnostic.
- "Measurably better traversal" (FR-005/SC-003) will be pinned to a concrete
  telemetry metric (e.g., distinct-area coverage or time-to-exit) during planning,
  added to the telemetry schema as needed.
