# Bot Stats Catalog

Canonical list of tunable bot parameters. Every stat exposed to the
progression system must be listed here. Source of truth for both gameplay
code and the upgrade tree in `progression.md`.

## Conventions

- **Name:** cvar name as it appears in QuakeC and the engine console
- **Type:** float | int | bool
- **Range:** valid min/max
- **Default:** value for a fresh game (the bot starts here)
- **Player-facing:** does the player see this in the upgrade UI? (some stats
  are dev-only knobs)
- **Observable effect:** how does a player notice this changing in-game?

## Mechanical skill

| Name | Type | Range | Default | Player-facing | Observable effect |
|------|------|-------|---------|---------------|-------------------|
| `bot_accuracy` | float | 0.0 – 1.0 | 0.3 | yes | Shots land more often; tighter aim cone |
| `bot_reaction_ms` | int | 50 – 1000 | 500 | yes | Time between seeing an enemy and firing |
| `bot_tracking_skill` | float | 0.0 – 1.0 | 0.2 | yes | Keeps the crosshair on moving targets |
| `bot_prediction_skill` | float | 0.0 – 1.0 | 0.0 | yes | Leads moving targets with projectile weapons |

## Movement

| Name | Type | Range | Default | Player-facing | Observable effect |
|------|------|-------|---------|---------------|-------------------|
| `bot_move_speed_mult` | float | 0.5 – 1.5 | 1.0 | no | Underlying movement speed multiplier (mostly for dev) |
| `bot_strafe_skill` | float | 0.0 – 1.0 | 0.0 | yes | Strafes while shooting; harder to hit |
| `bot_rocket_jump` | bool | – | false | yes | Can rocket-jump for shortcuts and height |
| `bot_bunny_hop` | bool | – | false | yes | Maintains speed across jumps |
| `bot_circle_strafe` | float | 0.0 – 1.0 | 0.0 | yes | Skill at circle-strafing during combat |

## Knowledge

| Name | Type | Range | Default | Player-facing | Observable effect |
|------|------|-------|---------|---------------|-------------------|
| `bot_map_awareness` | float | 0.0 – 1.0 | 0.3 | yes | Knows layout; takes more direct paths |
| `bot_secret_knowledge` | float | 0.0 – 1.0 | 0.0 | yes | Finds secret areas; collects hidden items |
| `bot_item_timing` | bool | – | false | yes | Tracks armor/megahealth respawns |
| `bot_weapon_priority_skill` | float | 0.0 – 1.0 | 0.5 | yes | Picks the right weapon for the situation |

## Decision-making

| Name | Type | Range | Default | Player-facing | Observable effect |
|------|------|-------|---------|---------------|-------------------|
| `bot_aggression` | float | 0.0 – 1.0 | 0.5 | yes | Engages vs avoids; pushes fights |
| `bot_retreat_threshold` | float | 0.0 – 1.0 | 0.3 | yes | HP fraction at which the bot backs off |
| `bot_target_priority_skill` | float | 0.0 – 1.0 | 0.5 | yes | Picks the most dangerous enemy first |
| `bot_resource_management` | float | 0.0 – 1.0 | 0.3 | yes | Conserves ammo, picks up health proactively |

## Combat

| Name | Type | Range | Default | Player-facing | Observable effect |
|------|------|-------|---------|---------------|-------------------|
| `bot_splash_awareness` | float | 0.0 – 1.0 | 0.0 | yes | Avoids own rocket splash; uses splash on enemies |
| `bot_weapon_affinity_<wpn>` | float | 0.0 – 1.0 | 0.5 | yes | Per-weapon skill (one row per weapon when finalized) |

## Open questions

- Do we need a single "skill level" rollup stat for backwards-compatible
  save migrations, or are individual stats sufficient?
- How granular should weapon affinities be — per weapon or grouped
  (hitscan / projectile / melee)?
- Should reaction time scale with distance / surprise, or stay flat?
- Movement skills: do we need separate stats for air control, ground
  acceleration, and jump timing, or roll them up?

## Notes

- All stats are cvars; the host app writes them via the engine console
  before/during runs
- Defaults represent a "newbie friend" baseline — competent enough to play,
  visibly improvable
- Maxed-out across the board should look like a high-level player of a
  Quake-like shooter (intentional ceiling: human-plausible expert, not
  aimbot-perfect)
