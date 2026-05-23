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
- `level_end` — `{ "outcome": "completed", "time_sec": 118.2 }`
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

## Open questions

- Do we log every shot, or sample? Per-shot logging at high tick rates
  could produce huge files. Probably fine but worth measuring.
- Should we log bot decision events (e.g. "chose to retreat") or only
  observable actions? Decisions help with debugging behavior; observables
  are enough for tuning.
- Frame-by-frame position traces for movement analysis: useful but
  expensive. Defer until we need them.
