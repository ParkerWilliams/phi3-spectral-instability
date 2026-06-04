# Contract: Cvar surface consumed per run

Two cvar families cross the harness→engine boundary. The harness sets them on the
`fteqw-sv` command line (`+set <name> <value>`); the QuakeC reads them with
`cvar(...)`. No engine-C patch — all are plain console variables.

## `sim_*` — harness control cvars (NEW; document in docs/bot-stats.md notes)

| Cvar | Type | Meaning | Consumed by |
|---|---|---|---|
| `sim_mode` | bool (0/1) | When set, QuakeC autostarts the agent and enables telemetry emission (R2/R4). | `BotFrame()` autostart shim, `telemetry.qc` |
| `sim_seed` | int | Per-run seed; echoed into `level_start.seed` (FR-016, R6). | `world.qc` level_start emit |
| `sim_time_limit` | number (sec) | In-engine session cap → triggers `timeout` end (FR-003). Harness wall-clock watchdog backs it up. | level tick / end logic |

Naming must not collide with existing FrikBot/engine cvars (open Q R-others);
verify at first compile. These are dev-only knobs (not player-facing).

## `bot_*` — agent configuration (catalogue: docs/bot-stats.md)

The harness clamps each to its documented range **before** `+set`, and records
the clamped value in the summary's `bot_config` (FR-007/FR-008). Wiring status
for **this slice**:

| Cvar | Range | This-slice status |
|---|---|---|
| `bot_accuracy` | 0.0–1.0 | **Wired** → FrikBot aim error (proves SC-004). |
| `bot_reaction_ms` | 50–1000 | Declared, clamped, recorded. Wiring = follow-up. |
| `bot_tracking_skill` | 0.0–1.0 | Declared, clamped, recorded. |
| `bot_prediction_skill` | 0.0–1.0 | Declared, clamped, recorded. |
| `bot_move_speed_mult` | 0.5–1.5 | Declared, clamped, recorded. |
| `bot_strafe_skill` | 0.0–1.0 | Declared, clamped, recorded. |
| `bot_rocket_jump` | bool | Declared, clamped, recorded. |
| `bot_bunny_hop` | bool | Declared, clamped, recorded. |
| `bot_circle_strafe` | 0.0–1.0 | Declared, clamped, recorded. |
| `bot_map_awareness` | 0.0–1.0 | Declared, clamped, recorded. |
| `bot_secret_knowledge` | 0.0–1.0 | Declared, clamped, recorded. |
| `bot_item_timing` | bool | Declared, clamped, recorded. |
| `bot_weapon_priority_skill` | 0.0–1.0 | Declared, clamped, recorded. |
| `bot_aggression` | 0.0–1.0 | Declared, clamped, recorded. |
| `bot_retreat_threshold` | 0.0–1.0 | Declared, clamped, recorded. |
| `bot_target_priority_skill` | 0.0–1.0 | Declared, clamped, recorded. |
| `bot_resource_management` | 0.0–1.0 | Declared, clamped, recorded. |
| `bot_splash_awareness` | 0.0–1.0 | Declared, clamped, recorded. |

"Recorded-only" means the value is clamped and written to `bot_config` so the
result is fully tied to its inputs, even before the stat changes behavior. Each
stat gets behavioral wiring + sim coverage incrementally (Principle V); update
`docs/bot-stats.md` as each moves to **Wired**.

## Standard engine cvars set for determinism of the run shape

`deathmatch 0`, `skill <n>`, `sv_cheats 1` (allow `noexit`/test toggles),
`+map <librequake-map>`. These are engine built-ins, not project-specific.
