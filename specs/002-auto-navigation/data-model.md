# Phase 1 Data Model: Automatic Agent Navigation

Entities derive from the spec + research. Navigation reuses FrikBot's waypoint
structures; this feature adds *generation lifecycle*, a *competence* tunable, and
*coverage* telemetry (the feature-001 measurement surface).

---

## Entity: NavGraph

The traversable representation the agent follows on a map. **Generated
automatically**, never hand-authored.

| Field | Type | Notes |
|---|---|---|
| `waypoints` | list<Waypoint> | nodes covering reachable space (FrikBot `way_head` list) |
| `map` | string | BSP stem it belongs to |
| `source` | enum `generated\|loaded` | generated this run vs exec-loaded from `maps/<map>.way` |
| `persisted` | bool | whether a `maps/<map>.way` exists/was written |

Persistence: FrikBot FRIK_FILE format at `maps/<map>.way`, exec-loaded at level
start. One graph per map. For procedural maps (unique), always `generated`.

## Entity: Waypoint (existing FrikBot node)

| Field | Type | Notes |
|---|---|---|
| `origin` | vector | world position (ground-reachable) |
| `links` | up to 4 refs | navigable neighbors (`LinkWays`/`TeleLinkWays`) |
| `b_aiflags` | bitfield | door/jump/precision/blind/etc. (FrikBot semantics) |
| `count` | int | id within the graph |

Created via `make_waypoint` (`bot_way.qc:252`); linked bidirectionally for
two-way traversal. No new fields required.

## Generation lifecycle (`waypoint_mode` state)

```
WM_UNINIT ──first BotFrame──▶ (max_clients ≥ 2)
   ├─ maps/<map>.way exists  ──exec/load──▶ WM_LOADED         (reuse — R3)
   └─ none                   ──WM_DYNAMIC──▶ generate while roaming (frontier-seek, R2)
                                    └─ on coverage-stable / level-end ─▶ SaveWays() ─▶ persisted
```

Rules:
- Generation requires `WM_DYNAMIC` + `max_clients ≥ 2` (R4) — sim invariant.
- A run **always** reaches a terminal outcome regardless of generation state
  (FR-006/SC-004); stuck-recovery (R7) guarantees forward progress.
- `sim_nav_regen 1` forces regeneration even if a `.way` exists.

## Entity: Navigation competence (tunable — progression axis)

| Field | Type | Range | Notes |
|---|---|---|---|
| `bot_map_awareness` | float | 0.0–1.0 | **wired here** (was recorded-only): scales exploration thoroughness + route directness. Higher → more coverage / more direct routing. |

Decision (supersedes R6 option): **reuse `bot_map_awareness`** (catalogue already
defines it as "knows layout; takes more direct paths") rather than add
`bot_nav_skill`. Clamped/recorded via feature 001's config path; now drives real
behavior. Observable within 1–2 min (Constitution I).

## StatsBlock additions (feature-001 telemetry)

Extends the feature-001 `stats` block; remains a pure aggregate of the event
stream (FR-006/SC-003 of feature 001).

| Field | Type | Aggregation |
|---|---|---|
| `waypoints_visited` | int | distinct nav nodes the agent reached this run (coverage proxy, R5) |
| `map_coverage` | float, 4dp | `waypoints_visited / waypoints_total` (0 if total 0) |
| `distance_traveled` | number | Σ per-frame movement (guards against spin-in-place) |
| `reached_exit` | bool | whether the agent reached the level exit (drives `time_to_exit_sec`) |

`waypoints_total` is carried on `level_end` (or a nav summary event), analogous to
`secrets_total` on `level_start` (G2 pattern from feature 001).

## Relationships

```
Map 1───1 NavGraph 1───* Waypoint
Run (feature 001) ──uses──▶ NavGraph ──produces──▶ coverage stats in the Summary
Navigation competence (bot_map_awareness) ──scales──▶ exploration/routing ──▶ coverage
```

Coverage/combat stats stay a pure function of the event stream so the feature-001
reconciliation (SC-003) keeps holding.
