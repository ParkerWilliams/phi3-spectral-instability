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

## Master progression dial

The single "how good is my friend right now" axis. **Static during a run** — the
idle-game writes it between runs; gamecode reads it read-only. This is the
leveling-up mechanic: every motion feel-param interpolates along it. Today it is one
master dial that **fans out** to the per-axis stats below over time (`bot_comp()` in
`frikbot/bot.qc` is the seam; `comp_lerp(novice, veteran)` is the interpolation).

| Name | Type | Range | Default | Player-facing | Observable effect |
|------|------|-------|---------|---------------|-------------------|
| `bot_competence` | float | 0.0 – 1.0 | 0.0 | yes | Overall skill. Low → tepid: slower, hugs walls, pauses at junctions. High → confident: full speed, rounds corners cleanly, flows. (Drives aim & movement-tech in later slices.) — **WIRED (locomotion, feature 003)** |

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
| `bot_map_awareness` | float | 0.0 – 1.0 | 0.3 | yes | Knows layout: explores more of the map and routes more directly (higher `map_coverage`) — **WIRED (navigation, feature 002)** |
| `bot_secret_knowledge` | float | 0.0 – 1.0 | 0.0 | yes | Finds secret areas; collects hidden items |
| `bot_item_timing` | bool | – | false | yes | Tracks armor/megahealth respawns |
| `bot_weapon_priority_skill` | float | 0.0 – 1.0 | 0.5 | yes | Picks the right weapon for the situation |

## Decision-making

| Name | Type | Range | Default | Player-facing | Observable effect |
|------|------|-------|---------|---------------|-------------------|
| `bot_aggression` | float | 0.0 – 1.0 | 0.5 | yes | Engages vs avoids; pushes fights. **Partially WIRED:** scales the boredom threshold — higher aggression → gets bored wandering sooner → beelines to the nearest monster (combat-seeking) |
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
- Maxed-out across the board should look like a high-level FPS player
  (intentional ceiling: human-plausible expert, not aimbot-perfect)

## Control cvars (`sim_*`, dev-only)

Harness-set run controls, **not** player-facing tunables and **not** clamped like
`bot_*` (see `specs/001-headless-sim-telemetry/contracts/cvars.md`):

| Name | Type | Purpose |
|------|------|---------|
| `sim_mode` | int | `1` = headless sim: autostart one FrikBot agent, emit `@EVT` telemetry, enforce the time limit |
| `sim_seed` | int | per-run seed, surfaced in `level_start` (wiring it to the engine RNG is an open question — research R6) |
| `sim_time_limit` | float | in-engine session cap (seconds) → `timeout` outcome |
| `sim_nav_regen` | int | `1` = regenerate the nav graph even if `data/maps/<map>.way` exists; `0` (default) = load it if present, else generate (feature 002, T009) |
| `sim_watch` | int | `1` = watch session: keep behaviors but suppress the death/timeout auto-quit, and make the human host a non-solid first-person bot-cam observer |
| `bot_smooth_aim` | int | `1` = human-like eased view turning (big swing → slow calibration) instead of robotic fixed-rate/instant turns. Watch-feel; off in the headless sim so its metrics are unchanged |
| `bot_turn_gain` | float | smooth-aim responsiveness (turn rate ≈ error × gain). Default 6. Higher = snappier. **Live-tunable** in the `~` console |
| `bot_turn_max` | float | smooth-aim turn-rate cap, deg/sec (the max swing speed). Default 300. Lower = slower, more deliberate. **Live-tunable** |
| `bot_scan_amp` | float | how far the view glances off the move heading while exploring (deg, default 35) — the "look around" scan. Movement is steered independently. **Live-tunable** |
| `bot_explore_bias` | float | radial-scan weight on heading toward UNEXPLORED space vs just the most-open ray (default 1; scaled by `bot_map_awareness`). **Live-tunable** |
| `bot_exit_bias` | float | extra unexplored-weight added when bored, so the agent leaves the area instead of doing laps (default 3). **Live-tunable** |
| `bot_analog_off` | int/bool | `0` (default) = analog steering: roam/goto drive `movevect` directly from the continuous wish-direction (no 8-way key quantization). `1` = legacy quantized keys. Registered in the harness catalogue so the watchability A/B (`stats.traversal.boring_view` / `pacing`, analog on vs off — use `configs/motion.toml`) is runnable from a config. **Live-tunable** |
| `bot_leap_off` | int | `1` = disable the leap sensor (`frik_leap_sense`) for an A/B against the old behavior; `0` (default) = on |
| `bot_leap_up` | float | tallest ledge (units above feet) the agent will jump onto; `0`/unset = baked 44 (≈ standing-jump apex). **Live-tunable** |
| `bot_leap_gap` | float | farthest far-side landing (units) the agent will leap a gap to; `0`/unset = baked 224. **Live-tunable** |
| `bot_leap_run` | float | min horizontal speed to commit a gap jump; `0`/unset = baked 80. **Live-tunable** |

## Implementation status (feature 001)

- **`bot_accuracy` — WIRED.** Injects aim error in `frikbot/bot_ai.qc`
  `bot_angle_set` (`err = (1 - accuracy) * 15°`); higher accuracy → higher
  `stats.accuracy`. *Live SC-004 proof is deferred pending automatic navigation* —
  the agent needs a nav graph to reach combat (`docs/design.md` §3).
## Implementation status (feature 002)

- **`bot_map_awareness` — WIRED (navigation).** Scales exploration thoroughness
  (frontier candidate count, 8→32) and route directness (heading noise toward the
  frontier) in `frikbot/bot_move.qc` `frik_bot_roam`; higher → more `map_coverage`
  and/or lower `time_to_exit_sec` (SC-003). Was recorded-only in feature 001.
- **`sim_nav_regen`** (above) added as a sim control for nav-graph regeneration.

- **All other `bot_*` — RECORDED-ONLY.** Clamped and written into the
  summary's `bot_config` (so config hashing / reproducibility works), but not yet
  wired into behavior. Wire them incrementally under the "adding a bot stat"
  convention (CLAUDE.md).
## Implementation status (feature 003)

- **`bot_competence` — WIRED (locomotion feel).** The master motion dial. Read via
  `bot_comp()` (the fan-out seam) in `frikbot/bot.qc`; `comp_lerp(novice, veteran)`
  interpolates three Slice-A feel-params: **whisker look-ahead** (`frik_whiskers` in
  `bot_move.qc` — anticipatory anti-scrape / corner-rounding, *always on*),
  **move-throttle** (horizontal speed in `bot_phys.qc` `CL_KeyMove`; jumps unaffected),
  and **junction-dwell** (a tepid pause on sharp turns, set in `frik_bot_roam`). At
  competence 1.0 throttle and dwell are inert, so only the whisker anti-scrape affects
  nav metrics — the sim configs pin 1.0 to isolate it (re-baseline SC-003/SC-004).
  Aim feel (Slice B) and movement-tech unlocks (Slice C, via `comp_has(thresh)`) are
  deferred. Live-tunable in the `~` console (`bot_competence 0..1`).
