# Phase 0 Research: Automatic Agent Navigation

Each entry is **Decision / Rationale / Alternatives considered**. Grounded in the
FrikBot QuakeC actually vendored in `quakec/frikbot/` and feature 001's harness.

---

## R1 — Generation mechanism: QuakeC dynamic auto-gen vs engine nav-mesh

**Decision.** Generate navigation **in QuakeC**, building on FrikBot's existing
`DynamicWaypoint` system, plus an exploration driver and auto-save. **No engine-C
nav-mesh** for this feature.

**Rationale.** The constitution mandates *minimize engine-C patches; every engine
patch needs an ADR.* A BSP-derived nav-mesh generator is inherently engine-C
(BSP leaf/portal parsing, walkable sampling, raycasts) and a submodule patch — a
heavier, ADR-gated change. FrikBot already ships `DynamicWaypoint`
(`bot_way.qc:291`) that creates and links waypoints as the agent moves, and
`SaveWays` (`bot_ed.qc:1624`) that writes a `maps/<map>.way` the engine loads via
`exec`. So the libre baseline already has 80% of the machinery; the gap is
*driving* it to cover the map and *saving* the result automatically. This is the
smallest, constitution-aligned step that proves "automatic," and it directly
reuses ADR-0001's FrikBot baseline.

**Alternatives considered.**
- *BSP nav-mesh (engine-C)* — most robust and the likely long-term answer for
  dense procedural maps, but engine patch + ADR + larger scope. **Deferred**:
  record as the alternative in the mechanism ADR; revisit if QuakeC dynamic
  generation can't produce usable graphs on generated maps.
- *Keep manual `.way` recording* — rejected by the spec (doesn't scale to
  procedural maps); already reframed as temporary scaffolding (`docs/design.md` §3).

> A short ADR (`docs/adr/`) will record "navigation generation = QuakeC dynamic
> auto-gen; nav-mesh deferred," per the constitution's ADR rule.

---

## R2 — Why today's dynamic navigation doesn't reach combat

**Decision.** Add an **exploration driver**: when the agent has no enemy/goal in
sight, actively steer it toward *unvisited* space (frontier-seeking) rather than
FrikBot's default loiter/random roam, and ensure `WM_DYNAMIC` is active in the sim.

**Rationale.** `DynamicWaypoint` runs only when `waypoint_mode == WM_DYNAMIC` and
`max_clients ≥ 2` (`bot_way.qc:325,340`). The feature-001 sim satisfies both (the
init path sets `WM_DYNAMIC` and the `exec maps/*.way` attempt confirmed
`max_clients > 1`). Yet runs showed 0 shots: dynamic waypointing *records where
the agent has been* but doesn't *push it to explore* — without a goal in view the
FrikBot roam stays near spawn and never enters a monster's line of sight, so no
combat. The fix is goal selection: bias roaming toward the nearest unexplored
frontier (areas with no nearby waypoint yet), which both covers the map and brings
enemies into view.

**Alternatives considered.** Increase `time_limit` and hope it wanders into a fight
(unreliable — observed 0 shots over 12×60 s runs). Spawn near enemies (map-specific,
doesn't generalize). Both rejected.

---

## R3 — Save & reuse vs regenerate every run

**Decision.** **Generate-then-save, reuse if present.** On a map with no
`maps/<map>.way`, run generation during play and `SaveWays()` the result; on later
runs the existing `.way` is exec-loaded (the path already attempted at level start)
and the agent uses it directly. Provide a cvar to force regeneration.

**Rationale.** Reuses FrikBot's existing save (`SaveWays`) and load (`exec
maps/<map>.way`) with no new file format. First encounter pays the generation cost;
subsequent runs are fast and deterministic (important for sim batches and the smoke
budget). For *procedural* maps (unique each time) the same machinery just always
generates — no human step either way (FR-002/FR-004).

**Alternatives considered.** Always regenerate (simpler, but wastes time on
repeated sim runs of the same map and adds run-to-run nondeterminism). Precompute
offline into committed `.qc` (that's the manual approach we're replacing).

---

## R4 — Single-player wiring (`max_clients`, `WM_DYNAMIC`)

**Decision.** Keep the sim launching with `max_clients ≥ 2` (already true) and
ensure the autostart path leaves `waypoint_mode == WM_DYNAMIC` for the agent.
Treat `max_clients` as a sim invariant documented in the launcher/cvars contract.

**Rationale.** `DynamicWaypoint` early-returns if `max_clients < 2` (`bot_way.qc:340`)
— a FrikBot DM assumption. Our headless sim already runs with it satisfied, so no
engine change is needed; we just must not regress it (and document why it matters).

**Alternatives considered.** Patch FrikBot to dynamic-waypoint in true
single-player (`max_clients == 1`) — unnecessary since the sim already runs
multi-slot; avoid touching that guard.

---

## R5 — Measuring navigation (the metric behind FR-005 / SC-003)

**Decision.** Add a **map-coverage** metric to telemetry: count of distinct
waypoints created/visited during a run (proxy for "how much of the level the agent
reached"), plus `distance_traveled` and the existing `time_to_exit_sec`. Coverage
is the primary FR-005/SC-003 signal; reaching combat (shots/kills) is the US1 gate.

**Rationale.** It must be measurable by the feature-001 sim with no rendering.
Distinct-waypoint count is cheap to emit from QuakeC (the graph is already being
built) and monotonic with exploration; `distance_traveled` guards against
"spinning in place" inflating coverage. Higher nav competence should raise coverage
and/or lower time-to-exit — directly testable by averaging runs at two settings.

**Alternatives considered.** True area/volume coverage from BSP leaves (needs
engine support — out of scope). Visited-region grid in QuakeC (heavier); revisit if
waypoint-count proves too coarse.

---

## R6 — Navigation competence as a tunable (progression axis)

**Decision.** Introduce a nav-competence `bot_*` stat (working name
**`bot_nav_skill`**, float 0–1) that scales exploration thoroughness and route
directness; fold the existing `bot_map_awareness` into it or keep `bot_map_awareness`
as the player-facing name (decide in data-model). Higher value → more complete
coverage and more direct routing.

**Rationale.** Satisfies "navigation is a progression axis" via the standard
"adding a bot stat" path (cvar → wire → `docs/bot-stats.md` → progression → sim
coverage). `bot_map_awareness` already exists in the catalogue ("knows layout;
takes more direct paths") and is the natural player-facing knob; we wire it
(currently recorded-only) to real routing behavior.

**Alternatives considered.** A brand-new stat vs reusing `bot_map_awareness`.
Leaning reuse (it already means exactly this) — finalized in `data-model.md`.

---

## R7 — Idle-tolerance: stuck detection & recovery (FR-006/SC-004)

**Decision.** Add a **stuck detector**: if the agent's position barely changes over
a short window while it intends to move, trigger an unstick (turn, jump, or pick a
new frontier) and mark the offending spot so routing avoids it. Generation and play
must always let the run reach a terminal outcome within `time_limit`.

**Rationale.** Idle play has no human to free a wedged agent; a softlock would
break unattended runs (SC-004 = 100% terminate). FrikBot has partial obstacle
handling (`frik_obstacles`); we make stuck-recovery explicit and telemetry-visible
so the sim can assert "no softlocks."

**Alternatives considered.** Rely on FrikBot's existing obstacle code alone
(insufficient — the agent already stalls near spawn today). The watchdog/time-limit
is the backstop, not the fix.

---

## Remaining open questions (bounded — mirror to `docs/design.md`)

1. **Mechanism ADR**: confirm QuakeC-dynamic over nav-mesh after a first
   generation pass on a real LibreQuake map; record in `docs/adr/`.
2. **Coverage metric fidelity**: distinct-waypoint count vs a visited grid — start
   with the former; revisit if it doesn't track real coverage.
3. **`bot_nav_skill` vs `bot_map_awareness`**: one stat or two (data-model call).
4. **Procedural-map readiness**: how generation is triggered at *map-generation*
   time (vs level-load) — out of scope here, flagged for the procedural-maps feature.
