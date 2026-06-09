# Design: real-time leap sensor (traversal jumping)

**Date:** 2026-06-09 · **Branch:** `feat/leap-sensor` (off `fix/wall-scrape-analog` — the motion
line: competence + whiskers + analog steering + watchability)

## Problem

Watching the agent (Parker, 2026-06-09): its jumping reads wrong in three ways — it **won't
jump when it should** (grinds a wall/ledge it could hop onto), **jumps with no purpose**
(random mid-stride hops), and **spasms in place** (the reactive stall/stuck recovery). The
root cause is one thing: the bot has **no perception of leapable geometry**. Today every jump
is *reactive* — `bot_stall_jump` (bot_phys.qc) hops every 0.4s whenever horizontal progress
< `bot_stall_dist`; `bot_stuck_check` turns ~90–270° **and** jumps when wedged. Neither knows
what is in front of the bot. The only *purposeful* jumps are `AI_JUMP`/`AI_SUPER_JUMP` waypoint
links, which our auto-generated graphs don't carry and the flat procedural maps don't need.

Jumping is a **core movement** and a progression axis (Parker leans heavily toward keeping it;
north star = tepid → rocket-jumping madman). So the fix is to make jumping *perceptive and
purposeful*, and let that **replace** the blind hops.

## Approach (chosen: A — real-time leap sensor)

A vertical sibling to `frik_whiskers`: each think, a handful of traces in the bot's intended
move direction classify the geometry ahead into a **leap affordance**, grounded in the bot's
real jump arc, and drive a purposeful, well-timed jump. Works on any map now (lq_e1m1/e1m2 and
anything later), no precomputation. (Approach B — precomputed graph jump-links — is deferred:
it only helps between waypoints and delivers nothing on the currently-flat procedural maps. A
grows into a hybrid once procedural maps get vertical geometry.)

**First pass purpose: traversal** — get onto ledges, across gaps, up to platforms. Combat
dodge-jumps, item/secret reach-jumps, and rocket-jump/bunny-hop spectacle are deferred.

## Components

### 1. The leap sensor — `frik_leap_sense` (new, bot_move.qc, near `frik_whiskers`)

Input: the bot's horizontal move direction `D` (from `move_wish`, else velocity/`bestdir`).
A few traces classify what's ahead into one of:

- **LEDGE_UP(h)** — a surface close ahead in `D`, with a *landable* floor on top at height `h`
  above the bot's feet, where `STEP_MAX (~18u, Quake auto-step) < h ≤ JUMP_UP_MAX (~44u, the
  bot's real standing-jump apex)`, and standing clearance above the landing (box/clearance
  trace). → hop up onto it.
- **GAP_CROSS** — the floor drops away just ahead (down-trace past `D*AHEAD` finds no floor
  within a fall threshold), **and** there is landable floor on the far side within a running
  jump (`GAP_MAX`, scaled by current speed, ~150–200u at run) at a reachable height. → leap
  across.
- **PIT (avoid)** — floor drops away with **no** landable far side in reach. → do **not** jump;
  signal "edge ahead, stop/steer away." Keeps informed jumping from creating faceplant suicides.
- **NONE** — flat/clear ahead. → no jump.

Thresholds (`STEP_MAX`, `JUMP_UP_MAX`, `GAP_MAX`, `AHEAD`, fall threshold) derive from the
bot's actual jump physics (jump velocity → apex; run speed → air distance) and are **cvar
tunables**, calibrated live in watch. The trace set is small and runs per-think (gated), like
the whiskers.

Output: an affordance class + (for LEDGE_UP/GAP_CROSS) whether the bot is in the **launch
window** this frame.

### 2. Purposeful jump + launch-window timing

Perception alone isn't skill — *when* it jumps is. `frik_leap_sense` only calls `bot_jump`
(sets `button2`) inside a launch window: close enough that the arc clears the lip (LEDGE_UP) or
starts at the gap edge (GAP_CROSS). Jumping early/late is what made the old hops look broken;
committing at the right moment is what reads as a player. For PIT it never jumps and instead
exposes an "edge ahead" signal the steering uses to stop/turn.

### 3. Kill the blind hops (the unifying fix)

The leap sensor becomes the **sole** traversal jump authority — it already fires for every
reachable ledge/gap in the move direction, which makes the reactive hops redundant:

- **Remove the cosmetic hop entirely** (Parker, 2026-06-09). `bot_stall_jump`'s reflexive
  0.4s hop is **deleted** — the sensor handles any real lip the stall was blindly hopping at.
- **`bot_stuck_check` keeps its turn-around / re-route recovery but loses its jump.** Wedged
  with nothing leapable ahead = a *pathing* problem → turn and re-path; it never hops in place.

Net: the bot jumps only for real, reachable affordances and stops spasming. (The legitimate
jumps the old hops were *accidentally* achieving — clearing a low lip — now come from LEDGE_UP.)

### 4. Competence arc (the "getting better")

Driven by `bot_competence` via the existing `comp_lerp(novice, veteran)` seam:
- **Novice** — short sensor look-ahead (perceives leaps late or not at all), a beat of
  hesitation before committing, attempts only low ledges. Charming clumsiness.
- **Veteran** — long look-ahead, smooth commitment, nails timing, takes the full `JUMP_UP_MAX`
  range.

Leaping becomes a *visible* progression axis, and this same perception layer is what later
feeds rocket-jump targeting (the madman end) and combat dodge-jumps.

### 5. Interaction with whiskers (precedence)

`frik_whiskers` steers *around* walls. A reachable LEDGE_UP is a wall the bot should *hop onto*,
not avoid — so when `frik_leap_sense` classifies the obstacle ahead as a reachable ledge, it
**suppresses the whisker's avoid** for that obstacle and lets the bot go forward + jump. PIT
does the opposite: it reinforces "don't go there." The two share the same `D` and compose:
whiskers own horizontal wall-rounding, the leap sensor owns vertical features.

## Data / control flow

`BotAI` → movement (`frik_movetogoal` / `frik_walkmove` / roam) sets `move_wish = D` →
`frik_leap_sense(D)` classifies geometry, suppresses whisker-avoid for reachable ledges, and
(in the launch window) calls `bot_jump` → `button2` → physics. `bot_stall_jump`/`bot_stuck_check`
consult the same classification instead of hopping blindly. View aim (`bot_angle_set` +
smooth-aim) already points along `D`/target, so the agent looks toward its landing.

New entity fields (bot.qc): a small amount of leap state (e.g. last-sense classification +
launch-window timing); no waypoint fields. New cvars: the threshold/look-ahead tunables above.

## Out of scope (deferred)

- Reach-jumps to items/secrets on platforms; combat dodge-jumps; jumping for height/angle.
- Rocket-jump (`bot_can_rj` exists) and bunny-hop tech — the spectacle end.
- Approach-B nav-graph jump-links and vertical procedural map geometry.
- Multi-jump route *planning* (this is local, reactive perception — purposeful but not planned).

## Evaluation (by eye, not metrics — per 2026-06-09 direction)

`just watch lq_e1m1` and `lq_e1m2` (more verticality): does the agent now hop purposefully onto
ledges, clear gaps, avoid pits, and never spasm? Sweep `bot_competence 0→1` for the
late→confident arc. All thresholds tunable live in `~`. No sim/metric scaffolding — watching is
the arbiter (memory `fun-to-watch-north-star`).
