# Design — Human-like motion that visibly improves (competence spine + Slice A)

**Date:** 2026-06-05 · **Branch:** `feat/motion-competence` (off `feat/watch-feel`)
· **Status:** approved (brainstorm) → implemented (spine + Slice A) → live-eval pending

## The fantasy

Not "better pathfinding" — **legible, human-like motion that visibly improves over
time**. Sitting next to your friend on a long summer day watching them play a retro
shooter, what you *see* is:

- **Early:** tepid, hesitant — wanders, pauses at junctions, grinds along walls,
  snap-jerks its aim, fumbles fights.
- **Later:** fluid, confident — clean lines through corners, strafe-jumps mid-kill,
  flick-and-settle aim, decisive routing.

So the technical spine is a **competence curve**: one legible axis every motion
behavior reads from, so improvement is *one thing you watch climb* (design pillar I
"visible progression"; §3 "FPS feel without input"). Builds on the existing
`bot_smooth_aim` (eased turn) and radial-scan roam — extends, doesn't redo.

## Decisions (locked during brainstorm)

1. **Axis shape:** one **master dial** `bot_competence` (0..1), architected to fan out
   to per-axis competences later. (Not several axes yet.)
2. **In-run dynamics:** **static during a run** — it *is* the leveling-up mechanic; the
   idle-game raises it between runs. Gamecode reads it read-only; the agent never
   self-improves mid-run (pillar II: the player shapes it).
3. **First slice:** the spine **plus** Slice A (locomotion feel + whiskers) together —
   a visible win that also establishes the axis everything else hangs off.

## Section 1 — The competence spine

A single cvar + three helpers + one read-seam, in `frikbot/bot.qc`:

- `bot_competence` (float 0..1, default 0) — read-only from gamecode; host/`watch`/`sim`
  set it.
- `bot_comp()` — clamped read; **the fan-out seam** (later becomes
  `bot_comp_axis(LOCOMOTION)` etc.; callers unchanged).
- `comp_lerp(novice, veteran)` — the one knob every feel-param uses.
- `comp_has(thresh)` — for Slice C binary unlocks (strafe-jump, etc.).

Every feel-param that should improve becomes `comp_lerp(novice_val, veteran_val)`. The
curve is the single source of truth; existing live cvars (`bot_turn_*`, `bot_scan_amp`,
`bot_map_awareness`, …) stay independent until the per-axis fan-out.

```
idle-game ──writes──▶ bot_competence (static per run)
                          │  bot_comp()  ← single read seam (fan-out point)
                          ▼
              comp_lerp(novice, veteran) ──▶ effective feel params
       ┌──────────────┬──────────┴───────────┬───────────────┐
   move throttle   whisker             (Slice B) aim      (Slice C) tech
   junction dwell  look-ahead            curve            comp_has(thresh)
```

## Section 2 — Slice A: locomotion feel on the curve

Root cause of wall-scraping: avoidance was **reactive** — `frik_dodge_obstruction`
fires only after `AI_OBSTRUCTED` (after contact). Whiskers add the missing
**anticipatory** layer in front of both move drivers (`frik_movetogoal`,
`frik_walkmove`).

**A1 — Whiskers (`frik_whiskers`, `bot_move.qc`).** Bend the wish-direction away from
walls *before* `frik_KeysForDir`. Cast a short center feeler; if blocked, cast ±side
feelers and steer toward the more-open side (strength ∝ how blocked the center is);
boxed both sides → hand off to roam/stuck. **Always on** (never face-grinds); *quality*
rides the curve. Horizontal only; never touches the view (move/view stay decoupled).

**A2 — Pacing on the curve.** Three `comp_lerp` feel-params (the whole tuning surface):

| Param | Novice (comp 0) | Veteran (comp 1) | What you watch |
|---|---|---|---|
| whisker look-ahead | 40 u | 130 u | last-second wall-hug → early, eased corner |
| move throttle | 0.6× | 1.0× | timid half-speed shuffle → full-speed runs |
| junction dwell | 0.5 s | 0.0 s | pause-and-peek at turns → flows through |

- **Throttle:** `CL_KeyMove` scales `movevect_x/y` by `comp_lerp(0.6,1)` (horizontal
  only — jumps/rocket-jumps unaffected; guarded to bots).
- **Dwell:** in `frik_bot_roam`, a heading change past ~50° sets
  `dwell_time = time + comp_lerp(0.5,0)`; the move drivers then stop the body (keep
  looking) until it elapses. Guarded so an already-dwelling agent never stalls.

At competence 1.0, throttle and dwell are inert → **only the whisker anti-scrape is
active**, so sims pin `bot_competence = 1.0` to isolate the single re-baseline variable.

## Verification

- **Droplet:** `progs.dat` compiles clean (fteqcc); `sims` pytest 68/68, ruff + mypy
  clean. The engine/sim can't run on the droplet (no `fteqw-sv`, no paks, engine build
  forbidden).
- **Local:** `just watch` (default `bot_competence 0.35`; `~` console
  `bot_competence 0` vs `1` to see the arc). `just sim` re-baselines SC-003/SC-004
  (whiskers change paths even at 1.0). Progression-axis proof: sweep
  `--bot.bot_competence 0.2` vs `1.0` → expect slower/less-direct vs faster/cleaner.

## Roadmap (deferred slices, same spine)

- **Slice B — aim feel curve:** competence-scale `bot_smooth_aim` (novice
  overshoot/hunt + jitter → veteran flick-and-settle). Migrate `bot_turn_*` onto the
  curve.
- **Slice C — movement-tech unlocks:** strafe-jump (esp. mid-kill), bunny-hop,
  rocket-jump via `comp_has(thresh)` thresholds.
- **Fan-out:** split `bot_comp()` into per-axis competences (locomotion/aim/tech)
  behind the same seam; reconcile with `bot_move_speed_mult` & friends in `bot-stats.md`.

## Notes

- Pure QuakeC; no engine-C patch (constitution). Spec-driven repo: formalize as
  `specs/003-*` via `/speckit-specify` when ready; consider an ADR for the
  competence-curve mechanism.
