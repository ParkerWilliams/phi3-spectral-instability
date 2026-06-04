# Contract: Navigation cvars + telemetry additions

Extends feature 001's contracts (`engine-event-line.md`, `summary.schema.json`,
`cvars.md`). Navigation is QuakeC + cvars only — no engine-C, no new IPC channel.

## Cvars

| Name | Type | Role |
|---|---|---|
| `bot_map_awareness` | float 0.0–1.0 | **Navigation competence** (now wired): higher → more exploration coverage + more direct routing. Player-facing; clamped/recorded via the feature-001 config path. |
| `sim_nav_regen` | int 0/1 | Dev/sim control: `1` = regenerate the nav graph even if `maps/<map>.way` exists (default 0 = load if present, else generate). |
| `max_clients` | int (invariant ≥ 2) | Not set by this feature, but **must stay ≥ 2** or FrikBot `DynamicWaypoint` disables itself (`bot_way.qc:340`). Documented so the launcher never regresses it. |

## Telemetry additions (feature-001 `@EVT` channel)

New/extended events on the existing stdout `@EVT|t|type|k=v|...` line format:

| `type` | payload | purpose |
|---|---|---|
| `level_end` (extended) | add `waypoints_total`, `reached_exit` | denominator for coverage + exit flag |
| `nav` (new, optional) | `{ waypoints_visited, distance }` periodic or final | coverage / movement signal (R5) |

These map into the summary `stats` additions (`waypoints_visited`,
`map_coverage`, `distance_traveled`, `reached_exit`) in `data-model.md`. The
summary schema (`sims/schema/summary.schema.json`) gains those fields; events
validate per the extended `event.schema.json`. `schema_version` bumps only if the
additions are made required; prefer additive/optional to stay at version `1`
(decide in tasks).

## Invariants

- A nav graph is available (loaded or generated) before the agent needs to path.
- Generation never prevents a terminal outcome within `time_limit` (FR-006).
- Coverage/combat stats remain a pure aggregate of the event stream (feature-001
  SC-003 still holds).
- No per-map human step is required for any of the above (FR-002/FR-004).
