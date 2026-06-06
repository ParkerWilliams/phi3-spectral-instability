# Telemetry Schema

Output format for sim runs and gameplay sessions. Pin this down early —
inconsistent telemetry is painful to clean up later.

## Storage

- **Sim runs:** JSONL files under `sims/results/<batch-id>/<run-id>.jsonl`.
  One line per event. Easy to grep, easy to stream, append-only.
- **Per-run summary:** one JSON file per run with aggregated stats.
- **Live gameplay:** SQLite tables in the save file. Schema TBD; mirror the
  sim schema where it makes sense.

## Per-run summary schema

```json
{
  "run_id": "uuid",
  "batch_id": "uuid|null",
  "config_hash": "sha256",
  "started_at": "ISO-8601",
  "ended_at": "ISO-8601",
  "duration_sec": 123.4,
  "map": "e1m1",
  "outcome": "completed | died | timeout | error",
  "bot_config": {
    "bot_accuracy": 0.4,
    "...": "..."
  },
  "stats": {
    "kills": 12,
    "deaths": 1,
    "damage_dealt": 1450,
    "damage_taken": 320,
    "secrets_found": 2,
    "secrets_total": 4,
    "items_collected": 18,
    "shots_fired": 84,
    "shots_hit": 31,
    "accuracy": 0.369,
    "time_to_exit_sec": 118.2,
    "time_to_combat_sec": 8.5,
    "waypoints_visited": 42,
    "waypoints_total": 60,
    "map_coverage": 0.7,
    "distance_traveled": 18450,
    "reached_exit": true,
    "weapon_usage": {
      "shotgun": {"shots": 22, "hits": 11, "damage": 220},
      "super_shotgun": {"shots": 18, "hits": 12, "damage": 600}
    },
    "deaths_by_cause": {
      "rocket_splash_self": 1
    }
  }
}
```

## Per-event schema (JSONL, one per line)

```json
{
  "t": 12.34,
  "run_id": "uuid",
  "type": "kill | death | shot | hit | pickup | secret | level_start | level_end | upgrade_applied",
  "data": { /* type-specific payload */ }
}
```

### Event types

- `level_start` — `{ "map": "e1m1", "seed": 12345 }`
- `level_end` — `{ "outcome": "completed", "time_sec": 118.2, "waypoints_total": 60, "waypoints_visited": 42, "distance_traveled": 18450, "reached_exit": 1, "scrape_frames": 88, "scrape_move_frames": 540 }`
  (the navigation-coverage fields are carried here, analogous to `secrets_total`
  on `level_start`; the harness folds them into the summary `stats` — feature 002.
  `scrape_*` are the cumulative wall-contact counters — see `nav` below)
- `nav` — `{ "x": 512, "y": -128, "waypoints": 7, "distance": 1840, "scrape_frames": 12, "scrape_move_frames": 60 }` — periodic
  (~every 2s) agent position + cumulative coverage counters. `scrape_move_frames`
  counts per-frame how often the agent is moving on the ground; `scrape_frames` how
  often a side wall is flush against its hull while doing so — their ratio is the
  `wall_contact` scrape metric. The harness derives **all** traversal metrics from
  this time series (`stats.traversal`), so metrics can be added/swapped without
  rebuilding QuakeC. See `sims/idledoom_sim/traversal.py`.
- `kill` — `{ "victim": "monster_army", "weapon": "super_shotgun", "distance": 320 }`
- `death` — `{ "cause": "rocket_splash_self", "killer": "self" }`
- `shot` — `{ "weapon": "shotgun", "target": "monster_army | null" }`
- `hit` — `{ "weapon": "shotgun", "target": "monster_army", "damage": 20 }`
- `pickup` — `{ "item": "armor_green", "value": 100 }`
- `secret` — `{ "secret_id": 2 }`
- `upgrade_applied` — `{ "upgrade_id": "steady_hands_2", "stat_changes": {...} }`

## Conventions

- Timestamps are seconds since `level_start`, not wall clock
- Map names match the BSP filename without extension (`e1m1`, not `Start`)
- Weapon names match QuakeC `IT_*` flag stems lowercased
  (`shotgun`, `super_shotgun`, `rocket_launcher`)
- Monster names match QuakeC class names (`monster_army`, `monster_dog`)
- All distances in Quake units (1 unit ≈ 1.5cm if we ever need real-world)
- All damage is integer HP
- Floating-point stats rounded to 4 decimal places when stored

## Querying

The sim harness produces a summary CSV per batch for quick analysis:

```bash
just sim-batch
# → sims/results/<batch-id>/summary.csv
```

For deeper analysis, load the JSONL into pandas / DuckDB. Example queries
will live in `sims/analysis/`.

## Schema versioning

Add a `schema_version` field at the top of every summary and event file.
Bump it when the schema changes incompatibly. Old data should be migratable
or clearly marked unmigrated. Don't break old data silently.

Current version: `1`

## Implementation status (feature 001)

The harness emits and validates against `schema_version: 1` — no schema change was
forced. Two `stats` fields are scoped this slice and are **not** reconciled from
per-event counts:

- `secrets_total` is sourced from the `level_start` payload (map-static count),
  not aggregated from `secret` events (G2).
- `damage_taken` is fixed at `0` — no incoming-damage event is emitted yet (G1);
  full incoming-damage telemetry is a follow-up.

`shot`/`hit` are one-per-trigger-pull; only **hitscan** damage landing
synchronously is counted as a `hit` this slice (projectile / animation-frame
weapons under-count — never over-count, so `accuracy` stays ≤ 1). Everything else
in `stats` is a pure aggregate of the event stream (FR-006 / SC-003).

## Implementation status (feature 002)

Navigation coverage adds five `stats` fields — `waypoints_visited`,
`waypoints_total`, `map_coverage` (`visited/total`, 4 dp, `0` on zero),
`distance_traveled`, `reached_exit`. They were added **additively/optional**, so
`schema_version` stays **`1`** (no incompatible change). Like `secrets_total`,
`waypoints_total`/`visited`/`distance`/`reached_exit` are carried on `level_end`
and sourced there rather than counted from per-event types — the rest of the
reconciliation invariant is unchanged. `data-model.md` (002) is the entity source.

### Traversal metrics (nav-competence follow-up)

The end-of-run coverage fields above **saturate** (a small map is fully explored
at any competence within the time limit, and `map_coverage` = `visited/total` is
~always `1.0`), so they don't distinguish nav skill. The fix is a **pluggable
metric layer**: QuakeC emits a cheap periodic `nav` sample (position + counters);
the harness computes a registry of metrics from that stream into the additive
`stats.traversal` object (still `schema_version 1`). Current metrics: `extent_area`,
`visited_cells`, `waypoints_at_15s` / `distance_at_15s` (exploration *rate* — the
ones that discriminate competence despite saturation), `final_waypoints`,
`peak_boredom`, and `wall_contact` (fraction of moving-on-ground time spent flush
against a side wall — the locomotion-quality / face-scrape signal; lower is better,
and it should drop with analog steering on). Switch
which one is authoritative in analysis via `compare --metric stats.traversal.<name>`;
add one by registering a function in `traversal.py`. Picking the *primary*
progression-driving metric is deliberately deferred — we expect to revisit this.

**Coverage is a poor proxy for nav skill** (observed): higher `bot_map_awareness`
routes *directly* (less distance, fewer cells, frontiers reached sooner), while low
competence *wanders* and incidentally touches more cells — so coverage metrics
reward aimlessness. The goal-oriented signal `time_to_combat_sec` (sim-time of the
first shot; event-derived, not nav-sample-derived) sidesteps this: a skilled
navigator reaches the fight *sooner*. Lower is better; `null` if no combat.

## Open questions

- Do we log every shot, or sample? Per-shot logging at high tick rates
  could produce huge files. Probably fine but worth measuring.
- Should we log bot decision events (e.g. "chose to retreat") or only
  observable actions? Decisions help with debugging behavior; observables
  are enough for tuning.
- Frame-by-frame position traces for movement analysis: useful but
  expensive. Defer until we need them.
