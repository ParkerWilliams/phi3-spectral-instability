# Implementation Plan: Automatic Agent Navigation

**Branch**: `002-auto-navigation` | **Date**: 2026-06-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-auto-navigation/spec.md`

## Summary

Make the agent navigate any map — including ones no human waypointed — on its own,
so it reaches combat/items and so navigation competence becomes a measurable
progression axis. Approach: **automatic waypoint generation in QuakeC**, built on
FrikBot's existing `DynamicWaypoint` (it already drops a waypoint trail as the
agent moves, and it runs in our sim because `max_clients ≥ 2`). We add (a) an
**exploration driver** so the agent actively seeks unvisited space instead of
loitering near spawn, (b) **auto-save** of the generated graph to `maps/<map>.way`
(reusing `SaveWays`) so later runs load it, (c) **stuck detection/recovery** so
imperfect pathing never softlocks, and (d) **coverage telemetry** so the
feature-001 sim can measure navigation quality and prove the progression axis.
No engine-C patches — pure QuakeC + the existing Python harness. A BSP-derived
nav-mesh (engine-side) is the considered alternative, deferred to an ADR if the
QuakeC approach proves insufficient.

## Technical Context

**Language/Version**: QuakeC (FrikBot-derived gamecode → `progs.dat` via fteqcc);
Python 3.11+ (`uv`) for the feature-001 verification harness.

**Primary Dependencies**: FTEQW + FrikBot (ADR-0001); **feature 001** (headless
sim + telemetry) as the verification/measurement harness; LibreQuake maps.

**Storage**: generated nav graph persisted as `maps/<map>.way` (FrikBot FRIK_FILE
format, exec-loaded at level start) — or regenerated per run when absent.

**Testing**: feature-001 sim harness (`uv run pytest` + telemetry assertions on
real runs); QuakeC compiled via `just build-quakec`; observed live in the GL client.

**Target Platform**: headless `fteqw-sv` (sim) + GL client (observation); build
local/CI, never the droplet.

**Project Type**: game gamecode (QuakeC) measured through a Python sim harness.

**Performance Goals**: agent reaches combat within the run `time_limit`; nav
generation fits the smoke budget (feature-001 SC-005, < 60 s end-to-end).

**Constraints**: **No engine-C patches** (constitution) — navigation is QuakeC +
cvars only. Build locally (droplet OOMs). Idle-tolerant: a run must always reach a
terminal outcome (no softlock).

**Scale/Scope**: per-map nav graphs now (LibreQuake); must generalize to
never-seen / procedurally generated maps with zero per-map human steps.

## Constitution Check

*GATE: must pass before Phase 0; re-checked after Phase 1.*

| Principle | Assessment |
|---|---|
| **I. Visible Progression (NON-NEGOTIABLE)** | ✅ Nav competence is a player-facing axis with an observable effect (more direct routes / more of the level reached) within 1–2 min (US3); measured via coverage telemetry. |
| **II. Behavior Configuration Is the Gameplay** | ✅ Nav competence is a *configured* behavior (a tunable), never moment-to-moment control. No rule engine introduced. |
| **III. Low-Poly PS1 Authenticity** | ✅ Navigation doesn't touch the aesthetic; movement still reads as classic FPS. |
| **IV. Original/Libre, No id IP (NON-NEGOTIABLE)** | ✅ FrikBot (Public Domain) + our QuakeC; no id content. Generated `.way` files derive from libre maps (track in `docs/licenses.md` if shipped). |
| **V. Small, Testable, Observable Changes** | ✅ Verified through `just sim`; the nav competence stat gets sim-harness coverage (new metric), per "adding a bot stat." |
| **Engine discipline (minimize C patches)** | ✅ **Drives the design**: QuakeC `DynamicWaypoint` chosen specifically to avoid an engine-C nav-mesh generator. No engine patch / submodule bump → a mechanism ADR records the QuakeC-vs-nav-mesh choice. |
| **Build/runtime (droplet)** | ✅ Build local/CI; droplet only runs sims; Python via `uv`. |

**Result: PASS.** No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-auto-navigation/
├── plan.md              # This file
├── research.md          # Phase 0 — mechanism decision + why dynamic-nav currently underperforms
├── data-model.md        # Phase 1 — NavGraph, generation lifecycle, nav competence, coverage stats
├── quickstart.md        # Phase 1 — run an un-waypointed map → reach combat; vary competence
├── contracts/           # Phase 1 — nav cvars + coverage telemetry additions
└── tasks.md             # Phase 2 (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
quakec/                          # gamecode (compiled to progs.dat)
├── frikbot/
│   ├── bot_way.qc               # DynamicWaypoint: exploration driver + auto-save hook
│   ├── bot_ai.qc                # roaming/goal selection: seek unvisited space
│   ├── bot_phys.qc / bot.qc     # stuck detection + unstick; nav competence cvar reads
│   └── bot_ed.qc                # reuse SaveWays for auto-save
├── telemetry.qc                 # emit nav coverage / traversal events (feature-001 channel)
└── ...

sims/                            # feature-001 harness (verification — Python/uv)
├── idledoom_sim/telemetry.py    # aggregate coverage metric(s) into stats
├── idledoom_sim/botstats.py     # register the nav competence bot_* stat
├── configs/                     # a nav-test config (un-waypointed map with enemies)
└── tests/                       # coverage-reconcile + nav-competence assertions

docs/
├── bot-stats.md                 # nav competence stat row
├── design.md                    # §3 navigation (already updated); link the mechanism ADR
└── adr/                         # ADR: navigation generation mechanism (QuakeC dynamic vs nav-mesh)
```

**Structure Decision**: Reuse feature 001's two-surface layout (QuakeC under
`quakec/`, Python harness under `sims/`). Navigation is added to the FrikBot QuakeC
(no engine patch); the feature-001 sim harness is the measurement instrument (new
coverage telemetry + a nav-competence stat). A mechanism ADR is added under
`docs/adr/`.

## Complexity Tracking

> No constitution violations — section intentionally empty.

## Phase notes

- **Phase 0 (`research.md`)** resolves: the generation mechanism (QuakeC dynamic
  auto-gen vs BSP nav-mesh), *why* today's dynamic nav doesn't reach combat,
  save/reuse vs regenerate, the `max_clients ≥ 2` / `WM_DYNAMIC` wiring, the
  concrete coverage metric for FR-005/SC-003, the nav competence stat, and
  stuck-recovery.
- **Phase 1** emits `data-model.md`, `contracts/`, and `quickstart.md`.
- **Phase 2** (`/speckit-tasks`) turns this into an ordered task list.
