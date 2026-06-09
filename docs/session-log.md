# Session Log

Rolling state summary so work survives session/crash loss (CLAUDE.md convention).
Newest entry on top. Keep entries short: what's true now, what's next, gotchas.

## 2026-06-09 — Real-time leap sensor (purposeful jumping) — on feat/leap-sensor

**Why (Parker, watching):** the bot's jumping read wrong — won't jump when it should (grinds
ledges), jumps with no purpose, and spasms in place. Root cause: zero perception of leapable
geometry; every jump was *reactive* (`bot_stall_jump` 0.4s hop, `bot_stuck_check` turn+jump).
Brainstormed → Approach A (real-time sensor). Spec
`docs/superpowers/specs/2026-06-09-leap-sensor-design.md`; plan
`docs/superpowers/plans/2026-06-09-leap-sensor.md`. Branch off `fix/wall-scrape-analog` (needs
competence + whiskers + analog), isolated from the mapgen substrate.

**Shipped (6 tasks, each compile-clean — 27 warnings, no new; engine UNRUN, droplet can't):**
`frik_leap_sense(movedir)` in `bot_move.qc` — vertical sibling of `frik_whiskers`. Traces
classify the geometry ahead vs the bot's real jump arc into **LEDGE_UP** (landable top in
18–44u), **GAP_CROSS** (landable far side within a running jump), **PIT** (no landing → don't
jump). Jumps only in the launch window. Competence-scales the look-ahead (`comp_lerp`). Now the
**sole** traversal jump authority: `bot_stall_jump` deleted (the cosmetic spasm), `bot_stuck_check`
keeps turn/re-route but lost its jump. Whisker precedence: a reachable ledge suppresses the
whisker veer (go straight + jump); a pit calls `frik_leap_avoid` to steer away. Live cvars
`bot_leap_off/up/gap/run` (bot-stats.md). Commits `e65f656`..(this) on `feat/leap-sensor`.

**EVAL = by eye (Parker's call; not metrics):** `just watch lq_e1m1` and `lq_e1m2` (verticality).
Look for: hops purposefully onto ledges, clears gaps, avoids pits, **no more spasming**. Sweep
`bot_competence 0→1`; tune `bot_leap_up/gap/run` live in `~`. **The thresholds WILL need
eyeball-tuning — that iteration is the work.** If a leap never fires, the risk is trace geometry,
not thresholds: temporarily `bprint` `self.leap_class` per think to confirm classification.

**Deferred (in plan):** competence height-cap + pre-jump hesitation (add at tuning if the low end
doesn't read as "learning"); combat dodge-jumps, item/secret reach-jumps, rocket-jump/bunny-hop,
nav-graph jump-links.

## 2026-06-08 — Watchability metrics (boring_view/pacing) + the sim is too noisy to judge motion feel — on fix/wall-scrape-analog

**Replaced the wall_contact metric** (from the 06-06 entry below). It was the wrong proxy:
body-proximity counted GOOD contact (box-jumps, corner-cuts) and *penalised* the more-direct
analog bot (first A/B showed analog 2× "worse" — a metric artifact). Reframed around the real
goal (Parker; memory `fun-to-watch-north-star`): the bot must be **fun to WATCH** — face-scraping
is bad because it's BORING (a zoomed-in wall texture sliding across the screen). New metrics score
the CAMERA + behaviour, not body position:
- **boring_view**: fraction of watched time the view-ray (`v_angle`) is buried in a near surface
  (<128u), sustained ≥0.7s, while moving + on-ground + not in combat. The sliding-texture stare.
- **pacing**: fraction with lots of path but little net progress over 4s windows — back-and-forth /
  re-treading.
Both QC-accumulated in `bot_nav_track` over `watch_time`, emitted on nav+level_end, computed as
`stats.traversal.{boring_view,pacing}` (lower=better). Python built test-first (73 pass, ruff+mypy
clean); progs compiles clean. Committed `d4b227e` on **fix/wall-scrape-analog** (after the analog
fix `705ed81`), pushed. `wall_contact` removed; `configs/motion.toml` added.

**Two findings while measuring:**
1. **Stationary-bot bug = stale `.way`.** `just sim`/current.toml don't force regen, so an existing
   `data/maps/<map>.way` loads as WM_LOADED and the roam/motion behaviours DON'T fire → bot sits at
   spawn (distance 0), metrics trivially 0/null. Fix: `configs/motion.toml` sets `sim_nav_regen=true`.
   **Beware: this silently affects ANY sim motion measurement.**
2. **The sim is RNG-noise-dominated → motion-feel A/B is inconclusive.** `boring_view`, 5 runs each
   (lq_e1m1, motion.toml): legacy (`bot_analog_off=1`) mean ~0.036, analog (`=0`) mean ~0.039, but
   within-mode spread 0.0–0.10 (SD ~0.034) swamps the gap; same config swings run to run. The analog
   fix tests **NEUTRAL**. Root cause: `sim_seed` not wired to the engine RNG (feature-001 R6).
   **Single-run sim A/Bs are meaningless for motion feel until there's determinism; `just watch` is
   the arbiter.** Memory `sim-motion-ab-needs-determinism`.

**Analog wall-scrape fix status:** sound but unproven — sim can't convict or acquit; watch eyeball
NOT yet run. Justified as a more-correct actuation (continuous steering reaching the wheels vs being
rounded away by the 8-way keys). **Decision deferred:** keep + open PR (on those grounds + a watch
check) or hold.

**Next / deferred:**
- **WATCH test**: `just watch lq_e1m1`, toggle `bot_analog_off` — the honest arbiter of the face-grind.
- **Repeatability unlock (Parker's idea, deferred "catch up on pathfinding later"):** auto-generate
  the nav `.way` from mapgen — cheap, `MapModel` already holds rooms + edges (MST+loops) + corridors;
  it's ~a serializer + node placement. Role fork OPEN (memory `sim-motion-ab-needs-determinism`):
  (A) repeatable sim substrate [recommended], (B) replace runtime discovery + reframe competence as
  traversal *quality* [needs ADR vs 0003], (C) answer-key to score discovered nav. Tension: nav is a
  progression axis.
- Human-telemetry-for-natural-movement idea: researched + **SHELVED** (memory `telemetry-dataset-feel-shelved`).

## 2026-06-06 — Analog-steering wall-scrape fix + wall_contact scrape metric on feat/procedural-maps

Parker: bot STILL scrapes its face along walls despite the frontier-ray bump (that bump —
`n = 12+acc*12` → `24+acc*24` in `bot_pick_frontier`, the pre-existing uncommitted change
on this branch — did NOT help). Root-caused the scrape to the **actuation layer, not
pathing**: the whiskers' continuous steering never reached velocity because (a)
`frik_KeysForDir` quantizes the wish-dir to 8 view-relative key sectors (no strafe key
under 30°), (b) `CL_KeyMove` rebuilds `movevect` only when keys CHANGE, and (c) `wishvel =
v_right*movevect_y + v_forward*movevect_x` is recomputed against the CURRENT (swept) view
each frame, so the body weaves with the eyes. The ray bump didn't help precisely because
the bug is BELOW path-selection.

**Fix — analog steering** (bot.qc, bot_ai.qc, bot_move.qc, bot_phys.qc): roam/goto stamp a
continuous world wish-dir `self.move_wish` (cleared each think in `BotAI` AFTER the stagger
gate so it persists across the faster physics frames; cleared on dodge/precision/death).
`CL_KeyMove`, when `move_wish` is set, drives `movevect_x/y` directly by projecting
`move_wish` onto the flattened view basis the physics uses → `wishvel = speed*move_wish`
regardless of view. Kills quantization + change-gating + view-coupled drift at once. Keys
still set (dodge/plat/precision read them); `movevect_z` untouched. Kill-switch
`bot_analog_off` (default 0 = on), registered in `botstats.py` so it's settable from a sim
config. Combat (bot_fight.qc) also moves via `frik_walkmove` → benefits; its stop-to-aim is
a mutually-exclusive `else` so `move_wish` stays clear there.

**Metric — wall_contact** (telemetry.qc, bot_ai.qc `bot_nav_track`, traversal.py): per
frame in sim_mode, while moving on the ground, two lateral `traceline`s (±perp to velocity)
out to hull-half-width + 4u; a hit either side = a scrape frame. Cumulative
`tel_scrape_frames`/`tel_scrape_move_frames` reset at level start, snapshot in every `nav`
event, finalised on `level_end`. Python traversal registry exposes `wall_contact =
scrape_frames/move_frames` (lower = better). schema_version stays 1 (additive). telemetry.md
+ bot-stats.md updated.

Verified on droplet: progs.dat compiles clean (no errors; only pre-existing Q206/Q302
warnings); sims pytest **72/72**, ruff+mypy clean. CAN'T run engine/sim here. **Next
(LOCAL):** A/B the fix — `cd sims && uv run harness.py run --config configs/current.toml
--bot.bot_analog_off 1` (old) vs `--bot.bot_analog_off 0` (new), compare
`stats.traversal.wall_contact`; and `just watch lq_e1m1` toggling `bot_analog_off` live to
eyeball it. **Re-baseline SC-003/SC-004** (analog changes paths even at competence 1.0).
Watch for: combat strafing feeling different; corner overshoot if `MOVE_ANALOG_SPEED`=400
fights the whiskers. **ALL UNCOMMITTED** — working tree only, nothing pushed; must
commit+push before pulling locally.

Telemetry-dataset idea (human gameplay data → natural feel) — researched (deep-research,
verified) + **SHELVED**: no clean Quake-native natural-movement dataset (Quake demos =
speedruns + need a custom parser; CS:GO data = wrong physics + GPLv2-incompatible /
license-unresolved). Hand-tuning + the wall_contact metric is the path. Details in memory
`telemetry-dataset-feel-shelved`.

## 2026-06-05 — Motion competence spine + locomotion feel (Slice A) on feat/motion-competence

Reframed "change the pathfinding" → **human-like motion that visibly improves**. New
master dial `bot_competence` (0..1): THE leveling-up stat — static per run, read-only in
gamecode, set by the idle-game between runs. Spine = `bot_comp()` (fan-out seam) +
`comp_lerp(novice,veteran)` + `comp_has(thresh)` in frikbot/bot.qc. Master dial now; fans
out to per-axis competences later (one function body changes).

Slice A (locomotion feel, all `comp_lerp`-driven off the curve):
- **Whiskers** (`frik_whiskers`, bot_move.qc): anticipatory anti-scrape — short feeler
  traces bend the wish-dir away from walls BEFORE frik_KeysForDir, so it rounds a corner
  instead of grinding then reactively dodging. Always on; look-ahead 40→130u by competence.
  Hooked into frik_movetogoal + frik_walkmove.
- **Move throttle** (CL_KeyMove, bot_phys.qc): horizontal movevect ×comp_lerp(0.6,1) —
  tepid→full speed. Horizontal only (jumps/RJ untouched), bots only.
- **Junction dwell** (frik_bot_roam): sharp turn (>~50°) → pause comp_lerp(0.5,0)s (novice
  peeks then commits; veteran flows). New fields dwell_time/last_movedir.

At competence 1.0 throttle+dwell are INERT → only whiskers affect nav → sims pin
bot_competence=1.0 (current/nav/nav2/smoke). Watch default 0.35; tune live in ~ console.

Verified on droplet: progs.dat compiles CLEAN via fteqcc (had to `apt install zlib1g-dev`
to build the compiler); sims pytest 68/68, ruff+mypy clean. CAN'T run engine/sim here (no
fteqw-sv, no paks, engine build forbidden). **Next: build+run LOCALLY** — `just watch`,
sweep `bot_competence 0→1` to eyeball the arc; `just sim` to **RE-BASELINE SC-003/SC-004**
(whiskers change paths even at 1.0). Watch for: crabbing if whisker steer too strong at
corners; over-dwell if roam bestdir is jittery (guarded — tune TURN_DWELL_DOT/DWELL_NOVICE).
Slice B (aim curve) + C (strafe-jump, via comp_has) deferred, same spine. Design doc:
docs/superpowers/specs/2026-06-05-human-motion-competence-design.md.

## 2026-06-04 — Radial-scan roam: walk toward open space, scan view (feat/watch-feel)

Parker: bot still gets stuck (boredom not unsticking it); wants human-style nav —
continuously scan the environment, and pick far-away points by throwing vectors,
measuring lengths, walking toward the longest; boredom should make it EXIT a room
rather than do laps. And: steer MOVEMENT independent of VIEW (how humans play).

Rewrote frik_bot_roam (replaces the candidate-sampling frontier roam):
- Radial scan: cast 12..24 rays (scales w/ bot_map_awareness) in a full circle from
  the eye; score = ray length (openness) + away*nearest_way_dist(endpoint)
  (unexplored bias). Walk toward the best -> heads to open space, never wall-scrapes.
- Boredom amplifies the unexplored bias (bot_exit_bias) -> leaves the area / no laps.
  Bored + a monster anywhere -> hunt it (kept).
- MOVE decoupled from VIEW: frik_walkmove(bestdir) (frik_KeysForDir maps a world dir
  to forward/strafe keys relative to v_angle), while the view scans independently —
  a glance offset (bot_scan_amp) re-picked every 0.6s, swept smoothly by the eased
  turn (bot_smooth_aim). Body goes to open space; eyes look around.
- New fields scan_time/scan_dir. Live cvars: bot_scan_amp, bot_explore_bias,
  bot_exit_bias (set in watch launch; tune in ~ console).

Big untested behavior change — on feat/watch-feel, main keeps the working roam.
Changes the headless sim roam too -> SC-003/SC-004 will need re-baselining. Needs
build-quakec. Watch for: crabbing if scan_amp too high; walk-offs on slow turns.

## 2026-06-04 — Watch-feel tuning: smooth aim (whiskers next) on feat/watch-feel

Aim was too jerky to watch. CL_KeyMove (skill!=2) turned at a fixed 210 deg/s
on/off via look-keys (snaps + stops dead at 10 deg); navigation did an instant
v_angle=b_angle snap each think. Replaced with an **eased proportional turn**
(bot_smooth_aim): rate = angle_error * bot_turn_gain, capped at bot_turn_max deg/s —
a fast SWING when far off-target that slows as it lines up (calibration). Both knobs
live-tunable in the ~ console. bot_angle_set skips its snaps under smooth-aim and
lets CL_KeyMove own v_angle. **Watch-only opt-in** (watch launch sets bot_smooth_aim
1); headless sim unchanged so SC-003/SC-004 metrics hold. Defaults gain 6 / max 300.

Sequenced deliberately: ship + tune the aim FEEL first (isolate the variable), then
do the **whiskers** (forward/side feeler traces to stop wall-face-scraping) as a
separate pass. Ledge-fall risk from smooth nav-turning (the old instant-snap was an
anti-walk-off hack) — mitigated by the turn cap; raise bot_turn_max if it walks off
during turn-arounds. Needs build-quakec.

## 2026-06-04 — Watch mode (first-person bot-cam) on feat/watch-mode

`just watch` — a lightweight GL-client observation path (no Tauri yet): listen
server, autostarts the agent on lq_e1m2, first-person bot-cam (`impulse 103`,
bound to O). Makes the agent actually play by setting `sim_mode 1` (combat/boredom/
nav behaviors are sim_mode-gated) while a new **`sim_watch 1`** flag suppresses the
death/timeout auto-quits so the window survives (on death the SP level restarts and
the agent respawns). `sim_time_limit 0` = no timeout. `maxplayers 2` so
DynamicWaypoint stays enabled (host + agent).

**Hero name = TBD** (Parker building a lore doc). Placeholder `"AGENT"` set in
`BotConnect` (gated sim_mode); noted in design.md §11 Open Questions. `cvar_string`
isn't declared in defs.qc, so it's a hardcoded placeholder for now (one-line change
when the name is decided).

**Local only — never built the GL client before.** First `just watch` will likely
need audio dev libs (opus/vorbis/xcb/xxf86dga) for `build-engine`, and may need
tuning: the fteqw-gl binary path, the `maxplayers` cvar name/effect (if the agent
loiters, max_clients<2 → DynamicWaypoint off), and the bot-cam keypress/auto-attach.
Expect a first-cut iteration pass. QuakeC compiles by inspection; pytest unaffected.

**Iter 1 (1st live run): GL client built + ran ✓; Issue C reuse CONFIRMED**
(`execing data/maps/lq_e1m2.way`, no "couldn't exec"). But hit a **telefrag death
loop**: SP maps have one `info_player_start`, so the human host + the agent spawn on
the same spot and `spawn_tdeath` (client.qc:807) telefrags them repeatedly → level
restarts → spam. **Fix:** gate `spawn_tdeath` on `!sim_mode` (co-spawn alive; agent
walks off, observer rides the cam). Caveat to watch next run: host+agent overlap at
spawn briefly — the agent may be blocked until you press O (botcam → non-solid);
if it's stuck at spawn, that's why. Rebuild + re-run `just watch`.

**Iter 2: telefrag loop GONE ✓** but the agent froze at spawn (distance=0,
waypoints=1, boredom climbing 56→1887). Cause: the Issue C fix made it LOAD the
`.way` → WM_LOADED, and our explore + boredom-seek live in `frik_bot_roam` which
only runs in **WM_DYNAMIC** — so a reused-graph run has NO movement drive (real
gap: reuse silently disables the good behaviors). Fix (no rebuild — cvar already
wired): `watch` now sets `sim_nav_regen 1` → forces fresh generation → WM_DYNAMIC →
the proven explore/boredom/combat behavior. Plus press **O** to free the agent from
the host co-spawn collision (host → non-solid bot-cam). **Follow-ups:** (a) make
explore/boredom run in WM_LOADED too, else reuse degrades behavior everywhere, not
just watch; (b) auto-free/auto-cam the host so O isn't required (needs reliable
human-vs-bot detection — `ishuman` semantics unclear).

**Iter 3:** still frozen at spawn even with regen. Parker's clue: lq_e1m2's
`info_player_start` is **on top of a monster**, so the agent is boxed in by the
host body + the monster, can't move or even acquire the point-blank monster
(boredom just climbs). Two fixes: (1) **human-vs-bot is `ishuman == 1`** (reliable —
gates frik_stuffcmd/sprint/centerprint); used it to make the human host a
**non-solid noclip observer** every frame in `PlayerPreThink` (sim_watch only) so it
never blocks the agent — no O needed for movement, fly around or press O for
first-person. (2) Switched the watch map to **lq_e1m1** (clean spawn; the agent
already explored+fought there). Needs `build-quakec` (client.qc changed).

**Iter 4: agent MOVES now** (lq_e1m1: distance 0→599, x/y changing) — the non-solid
host fix worked. But the camera sat at the host's spawn while the agent ran off.
**Design clarified (Parker):** "watch your friend get better" = sitting beside a
friend watching HIS SCREEN — i.e. the agent's own **first-person FPS view**, NOT a
third-person chase. The game is first-person FPS throughout. Fix: `PlayerPreThink`
now **auto-attaches FrikBot's bot-cam** to the agent the moment it connects
(`bot_count > 0`), one-shot — the window becomes the agent's first-person view with
no keypress; BotPreFrame's `botcam()` follows each frame. (O still cycles/detaches.)
Needs `build-quakec`.

## 2026-06-04 — Fix Issue C (.way reuse path) on fix/way-reuse-path

**Confirmed broken then fixed.** Two-run test: the file lands at
`quakec/data/maps/<map>.way` (FTE's FS_WRITE sandbox), but `exec maps/<map>.way`
searches `quakec/maps/` + paks — so run 2 still said `couldn't exec` with the file
present → graphs never reused, every run regenerated. Fix (`bot.qc` WaypointWatch):
load via **`exec data/maps/<map>.way`** (the write location); dropped the `maps/`
exec to avoid a double-load if a map ever had a `.way` in both.

**Verify (build-then-merge):** `just build-quakec`, then run lq_e1m2 TWICE — run 2
should now show `waypoints detected` / NO `couldn't exec data/maps/...` (reuse
works). **Risk to watch:** FTE may restrict `exec` from its `data/` write sandbox
for security; if run 2 still says `couldn't exec data/maps/...` with the file
present, the fallback is to load via FRIK_FILE read+parse, or relocate the write.
QuakeC-only; pytest unaffected (68/68). Merge once run-2 reuse is confirmed.

## 2026-06-04 — Boredom mechanic (combat-seeking) on feat/nav-competence-metric

New behavior: agent `.boredom` rises while wandering (no enemy), resets the instant
it has a target. Past a threshold it stops frontier-exploring and **beelines to the
nearest live monster** (`nearest_monster()` in bot_move.qc) — "gets bored, seeks
combat". Threshold scales with **bot_aggression** (impatient bots seek sooner →
wires that previously recorded-only stat). Loop: explore → bored → hunt → fight →
reset → repeat. Should lower `time_to_combat_sec`. Boredom is mirrored into the
`nav` telemetry + a `peak_boredom` traversal metric for observability/tuning.
Harness verified (pytest 68/68, ruff+mypy clean); **QuakeC compile-pending.**

**Before merge (build-then-merge):** `just build-quakec` (boredom is new gamecode —
confirm it compiles + doesn't regress combat), then a nav2 run to eyeball boredom
rising→combat→reset in the nav events and check `time_to_combat`. Merge once green.

## 2026-06-04 — 🎯 US3 DEMONSTRATED (+ Issue A confirmed live)

Re-swept on lq_e1m2 (roomier; reliable combat) with the goal/rate metrics:
`bot_map_awareness` 0.1→0.9 cut **time_to_combat_sec 14.33→8.86s (~38% faster)** and
raised **waypoints_at_15s 6.5→11.25 (~73% more early exploration)**, n=4. Both
strong + monotonic → **SC-003 met.** US3 (nav competence as a visible axis) is
demonstrated. Updated spec.md SC-003 + tasks.md T016.

**Two key findings:** (1) coverage is the WRONG proxy for nav skill — it saturates
and rewards aimless wandering (low competence touches more cells); the real signal
is goal-reach (`time_to_combat_sec`) + exploration-rate (`*_at_15s`). (2) The T014
wiring was fine all along — the earlier "flat" lq_e1m1 result was wrong metric +
too-small map. Also: a `died` run in the sweep **confirmed Issue A's
`level_end{died}` terminal live** (last unexercised fix).

All four user stories now demonstrated. `feat/nav-competence-metric` is ready to
merge to main (pluggable metric layer + time_to_combat + US3 proof; QuakeC sampler
built clean). The pluggable design held: 3 metric swaps, 0 gamecode rebuilds.

## 2026-06-04 — Pluggable traversal metrics (US3 follow-up) on feat/nav-competence-metric

Addresses the US3 metric gap. Design (per Parker — "parallel implementation,
switch later, revisit often"): QuakeC emits a cheap **stable** periodic `nav`
sample (x,y,waypoints,distance, every 2s); **all** traversal metrics are computed
in Python (`sims/idledoom_sim/traversal.py` registry) so we add/swap/compare
without rebuilding gamecode. `stats.traversal` (additive, schema_version still 1)
carries: extent_area, visited_cells, **waypoints_at_15s / distance_at_15s** (rate
— discriminate competence despite end-of-run saturation), final_waypoints. Switch
authoritative metric via `compare --metric stats.traversal.<name>`. Harness
verified (pytest 64/64, ruff+mypy clean); **QuakeC compile-pending**.

**Next (local build + verify):** `git fetch && git checkout feat/nav-competence-metric`
→ `just build-quakec` → re-run the SC-003 sweep and compare
`stats.traversal.waypoints_at_15s` (0.1 vs 0.9 `bot_map_awareness`). If the rate
metric rises with competence, US3 is demonstrable; if still flat, the T014 wiring
itself is too weak (strengthen it). Either way it's now diagnostic.

## 2026-06-04 — ✅ LANDED ON MAIN: 001 + 002 MVP (merge a4bccb5)

Merged `002-auto-navigation` (incl. all of 001) → `main` (`445d4e5..a4bccb5`,
`--no-ff`). `main` is green: pytest 57/57, QuakeC builds clean. PR #2 auto-closed
as merged (001's commits are now in main); left a note for Taber. Stacked-PR
ceremony dropped per Parker to land the MVP directly.

**On main now:** headless sim+telemetry (001) + automatic navigation (002). Agent
generates its own nav, explores un-waypointed maps, kills monsters, clean telemetry.

**Tracked follow-ups (not blocking):**
- **US3 metric** — `bot_map_awareness` wired but not demonstrable (R5 coverage-metric
  gap); needs spatial-coverage/exploration-rate metric or GL eyes.
- **Issue C** — generated `.way` reuse: save path (`data/maps/`) vs exec path
  (`maps/`) mismatch; verify + fix.
- **Issue A** — death→`level_end{died}` terminal in code, never fired live (agent
  survives); confirm by provoking a death.
- **SC-004 magnitude** — compressed (close-range shotgun); widen aim-error coeff or
  test a hitscan weapon at range.
- `002-auto-navigation` branch can be deleted (merged).

## 2026-06-04 — Verification scorecard: US1/US2/SC-004 ✅, US3 metric gap

Ran the live sweeps. **SC-004 PROVEN** (unblocks feature 001): lq_e1m2, n=6 each,
`bot_accuracy` 0.1→accuracy 0.2767, 0.9→0.3715 (monotonic ↑). Magnitude compressed
(close-range shotgun → gentle 15° aim error) — tuning follow-up, not a wiring bug.

**SC-003 (US3) NOT demonstrable with current metrics.** lq_e1m1, `bot_map_awareness`
0.1 vs 0.9: waypoints_total 21.0 vs 20.3, distance 11232 vs 10403 (flat/slightly
lower at 0.9). Cause: 60s saturates the reachable area at any awareness (metrics are
time-bound, not skill-bound), distance is confounded by directness, map_coverage is
degenerate (1.0). The R5 gap. US3 wiring (T014) ships but the axis is unproven —
needs a spatial-coverage grid / exploration-rate metric / GL eyes. **Follow-up.**

**Scorecard:** US1 ✅ (lq_e1m1: 9 shots,1 kill) · US2 ✅ (lq_e1m2: 3 kills) ·
SC-004 ✅ · US3 ⚠️ metric gap · Issue A (death terminal) in code, unexercised
(bot survives) · Issue C (reuse path) suspected, non-blocking. Core idle loop
(navigate→fight) works. Merge-worthy for the MVP; US3-metric + C are follow-ups.

## 2026-06-04 — 🎯 MVP WORKING: agent navigates + fights + kills (live, lq_e1m2)

First local build of 002 QuakeC compiled clean (0 errors). Live runs surfaced — and
we fixed — two root causes; the agent now plays for real.

**Proven live (lq_e1m2, un-waypointed):** `@EVT` stream shows shot→hit→**3× kill
monster_army** (shotgun) + backpack pickups + clean `level_end|timeout`,
`waypoints 9/9`, distance 4572. Nav generation (T008/T009) + combat both working.

**Two bugs found & fixed (commit 1d8bf90):**
- **Issue B — agent never fired.** FrikBot acquires monsters only `if (coop)`
  (`bot_fight.qc` `bot_dodge_stuff`); sim runs deathmatch 0 / coop 0 (coop would
  disable DynamicWaypoint), so it hunted only players (none) → walked past
  monsters. Fix: monster-scan when `coop || sim_mode`.
- **Issue A — death truncated the stream.** SP restarts the level on death (dead
  bot's random fire = respawn input) → QuakeC globals reinit → telemetry clock +
  guards reset → no `level_end`, watchdog kill, "not bracketed". Fix: in sim, the
  agent's death emits `Tel_LevelEnd("died")` + quit. (In place; not yet exercised
  live since the agent now wins its fights.)

**Still OPEN:**
- **Issue C (T009 reuse broken):** `SaveWays` writes `data/maps/<map>.way` but load
  does `exec maps/<map>.way` → `couldn't exec`; saved graphs never reused.
  Generation-per-run still works (so not blocking). Save path ≠ exec search path —
  needs a path fix.
- **lq_e1m1 (T011/nav.toml):** nav works (15 wpts, dist 5845) but no combat in a
  30s run — agent didn't reach a monster in time; needs a 60s+ run to confirm
  combat there (lq_e1m2 already proves the wiring).
- **Proof artifacts not yet captured via the real harness:** run `harness.py run`
  (not rawrun) for proper summaries; then `compare` for SC-004 (accuracy, unblocks
  001) and SC-003 (map_coverage vs bot_map_awareness).

**rawrun.py** dev helper added (dumps raw engine stdout to /tmp/<cfg>.log) — how we
caught A/C (the harness keeps only parsed @EVT, hiding runtime/console lines).

## 2026-06-03 — 002 FULL slice code-complete (US1–US4 + polish); build-then-merge

**Decision (Parker):** drop the stacked-PR ceremony, push hard for a full-002 MVP,
**build-then-merge** (finish code here → local build verifies → fast-merge 002→main).

**All droplet-doable 002 work is now done & harness-verified (pytest 57/57, ruff +
mypy clean). QuakeC is compile-pending (droplet OOMs) — hand-verified single-pass.**
- **US3 (T014/T015/T016):** `bot_map_awareness` WIRED in `bot_move.qc` `frik_bot_roam`
  — candidate count 8→32 (thoroughness) + heading noise ∝ (1−awareness) (directness),
  clamped [0,1]. Docs (bot-stats WIRED row + `sim_nav_regen` + progression). Test
  `test_nav_competence.py` (metric direction).
- **US4 (T017/T018):** `bot_stuck_check()` in `bot_phys.qc` (called from `PostPhysics`
  pre-`BotAI`): sim+bot-scoped, skips combat, on <40u/1.5s turns+jumps+clears route
  (→re-roam) + flags `current_way` AI_PRECISION. Watchdog `quit` is the terminal
  backstop. Test `test_no_softlock.py` (outcome always terminal; detours ≠ failure).
- **Polish (T019/T020):** telemetry.md coverage fields + schema_version stays `1`;
  waypointing.md relabeled LEGACY (superseded by ADR-0003); design.md §3 mechanism
  decided.

**STILL OPEN — all local-build only (the hand-off; can't run engine on droplet):**
- **T011** US1 live (agent reaches combat on `nav.toml`), **T013** US2 (second map),
  **T021** re-run 001 SC-004, **T022** quickstart end-to-end.
- **First step locally:** `just build-quakec` — this is the FIRST compile of all the
  002 QuakeC (T008/T009/T014/T017). Watch fteqcc for errors; the nav AI (frontier
  roam, stuck-recovery) will need build-and-watch tuning. Then run the live checks.
- **Then:** `git checkout main && git pull && git checkout 002-auto-navigation &&
  git rebase main` once 001 (PR #2) merges, and fast-merge 002→main.

## 2026-06-03 — 002 US1 code-complete (T009 done); live verify (T011) is the hand-off

**Correction to the entry below:** 002 is no longer "planned, not implemented" —
commits `ef20d70`/`c6729ed`/`86066dc` landed the foundation + most of US1. Done:
T001 ADR, T002 nav.toml, T003 traversal, T004 `Tel_Nav`, T005 max_clients
invariant, T006 schema, T007 aggregate, **T008 frontier roam** (bot_move.qc),
T010 test_coverage, T012 nav2.toml + `compare` subcommand.

**This session — T009 (auto-save / reuse + `sim_nav_regen`):**
- `NavAutoSave()` (`quakec/frikbot/bot_way.qc`): in a sim, once a WM_DYNAMIC graph
  stops growing for `NAV_SAVE_STABLE_SECS` (3s), `SaveWays()` it to
  `maps/<map>.way`. Fires mid-run (coverage-stable), NOT at the timeout `quit`,
  because `SaveWays` writes async (one waypoint/frame) and would be truncated by an
  immediate quit. One-shot per level; gated `sim_mode` + WM_DYNAMIC + `fixer` free.
- Reuse already worked (FrikBot `WaypointWatch` always `exec`s the `.way`; present
  → WM_LOADED, absent → stays WM_DYNAMIC). Now skipped when `sim_nav_regen` set.
- `sim_nav_regen` cvar (default 0) plumbed: `config.py` field + TOML read,
  `launcher.py` `+set`, `botstats.SIM_CVARS`. **Verified:** pytest 49/49, ruff+mypy
  clean. **QuakeC compile-pending** (droplet OOMs) — hand-verified single-pass
  (decls precede defs; symbol visibility OK).

**Resume / hand-off (local build required):**
1. `just build-quakec` (first 002 compile — watch for fteqcc errors in the nav code).
2. **T011 (US1 live):** `cd sims && uv run harness.py run --config configs/nav.toml
   --time-limit 60` → assert `shots_fired > 0`, `kills ≥ 1`, `map_coverage` above
   spawn baseline. Confirm `maps/<stem>.way` gets written on first run, reused on
   the second (and `sim_nav_regen=true` in the config forces regen / deleting the
   `.way` does too). T008's frontier roam needs live build-and-watch tuning.
3. Then US2 (T013), US3 (T014–T016), US4 (T017–T018), Polish (incl. T021 re-run of
   001's SC-004 now that the agent fights). Was told to STOP after US1.

## 2026-06-02 — ⏸️ PAUSED: 001 in review, 002 fully planned

**State:**
- **Feature 001** (headless sim + telemetry): code complete (US1–US4 + Phase 7),
  open as **PR #2** (`001-headless-sim-telemetry` → `main`) awaiting Taber's review.
- **Feature 002** (automatic navigation): full Spec Kit chain done on branch
  **`002-auto-navigation`** (stacked on 001) — spec.md, plan.md, research.md,
  data-model.md, contracts/nav.md, quickstart.md, tasks.md (22 tasks). NOT
  implemented. Decision: QuakeC `DynamicWaypoint` auto-gen, no engine-C; mechanism
  ADR is task T001.

**Resume recipe (after PR #2 merges):**
1. `git checkout main && git pull`
2. `git checkout 002-auto-navigation && git rebase main` (un-stack onto merged 001)
3. `/speckit-implement` for 002 — or start with T001 (ADR) → US1 (exploration
   driver + auto-save → agent reaches combat on an un-waypointed map). US1 is the
   MVP and unblocks feature-001 SC-004.
- Build QuakeC locally (droplet OOMs); US1 nav AI needs live build-and-watch tuning.

## 2026-06-02 — Feature 001 wrapped (Phase 7 polish; SC-004 deferred)

Per Parker: defer SC-004 (skip throwaway manual waypointing) and close out 001.
Phase 7 polish done (T042–T045): `docs/bot-stats.md` (bot_accuracy **WIRED**,
others recorded-only, `sim_*` cvars), `docs/telemetry.md` (G1/G2 conformance,
schema_version 1), `docs/design.md` §11 (sampling, RNG-seed open Qs),
`sims/README.md` (build-local/`uv` workflow). Harness still green (pytest 39/39,
ruff + mypy clean).

**Feature 001 code is complete (US1–US4).** The only remaining items all need a
running agent that actually fights: SC-004 live proof, T046 end-to-end, T006
(LibreQuake licensing), and the CI workflow's first real run. All of those are
gated on the agent reaching combat → **next feature = automatic navigation**
(`docs/design.md` §3). Hand-waypointing intentionally skipped as throwaway.

## 2026-06-02 — Design decision: automatic navigation as a progression axis

Parker set direction: maps will be **procedurally generated**, so navigation
**must be automatic** (hand-waypointing can't scale); nav competence **improves
over progression** (the core idle "friend getting better" fantasy); and imperfect
/ "silly" pathing is **acceptable** (idle game). Captured in `docs/design.md` §3
(new "Navigation & traversal"), §6 (procedural maps), §7 + §11 (open: generation
mechanism), glossary; mirrored in `CLAUDE.md`. Hand-recorded `.way` files
(`docs/waypointing.md`) are now explicitly **temporary scaffolding** to unblock
SC-004 on one fixed map — not the shipping approach. Mechanism (FrikBot
`DynamicWaypoint` auto-record pass vs BSP-derived nav-mesh vs learned) is a future
ADR. Doesn't change feature 001; it reframes the waypointing detour as a bootstrap.

## 2026-06-02 — US4 implemented + SC-004 blocked on no-combat

**Status: feature `001-headless-sim-telemetry` — US4 (Phase 6, smoke CI gate) done.
All four user stories implemented. One open issue: SC-004 not live-proven yet.**

- ✅ **US4 (verified):** `configs/smoke.toml` (15 s), `smoke` subcommand sharing
  the `run` pipeline (`_run_to_summary`) with a strict `smoke_chain_healthy` gate
  (bracketed stream + non-error → exit 0, else non-zero + diagnostic).
  `.github/workflows/ci.yml`: `harness` (ruff/mypy/pytest) + `smoke` (build +
  `just sim-smoke`). `uv run pytest` **39/39**, ruff + mypy clean. CI workflow
  itself is first-run-pending (smoke job must be GH-hosted; droplet can't build).

- ⚠️ **SC-004 BLOCKED (not a code defect):** ran `--bot.bot_accuracy 0.1` vs `0.9`
  ×3 on `lq_e1m1` → **all runs `shots_fired: 0`, `accuracy: 0.0`**. The bot never
  enters combat: no waypoints for `lq_*` maps → it wanders aimlessly and never
  reaches/fights monsters, so the `bot_accuracy`→aim wiring (T037) has nothing to
  act on. The wiring is in and correct; proving it needs actual combat. Options:
  (a) deathmatch with 2 bots on `lqdm*` so they hunt each other, (b) waypoints for
  a LibreQuake map, (c) a small combat arena. This is the bot-navigation gap, a
  known future-work dependency — same root as the `couldn't exec *.way` note.

**Decision (Parker):** author waypoints (option b) to make the single agent
engage. Workflow written up in **`docs/waypointing.md`** — build the GL client
(needs audio dev libs), record a `.way` for `lq_e1m1` via FrikBot's editor
(`impulse 104`, Dynamic Mode), drop it at `quakec/maps/lq_e1m1.way` (both GL
client + sim `exec` it), then the SC-004 0.1-vs-0.9 check works. Hands-on local
work (needs a display / WSLg). Then Phase 7 polish; T006 licensing + CI first-run
still open.

## 2026-06-02 — US3 implemented (config tuning + bot_accuracy aim)

**Status: feature `001-headless-sim-telemetry` — US3 (Phase 5, per-run cvar config).**

The harness is now a tuning tool: `bot_*` overrides are clamped, recorded with a
stable `config_hash`, and `bot_accuracy` is wired into FrikBot aim.

- ✅ **Harness (verified):** `--bot.<name> VAL`/`=VAL` CLI extraction (T034) →
  clamped into `bot_config`; bool-string coercion + `BotInput` type. `test_clamp.py`
  (T038): clamp ranges, hash equal/differ, unknown-stat KeyError. T035/T036 were
  already done in US1. `uv run pytest` **35/35**, ruff + mypy clean.
- 📝 **QuakeC (compile-pending):** T037 — `bot_accuracy` aim error in
  `frikbot/bot_ai.qc` `bot_angle_set`: `err=(1-acc)*15°` random offset on the
  enemy-aim `b_angle`. Higher accuracy → tighter aim → higher `stats.accuracy`
  (SC-004). Unset cvar → default 0.3. The 15° max is tunable.
- **Open earlier loop:** US2 live re-run (post the parser/level_start fix) wasn't
  pasted back — worth confirming `level_start` now appears + events reconcile.

**Next (local):** rebuild, then SC-004 check — `--bot.bot_accuracy 0.1` vs `0.9`
on a monster-bearing map, average `stats.accuracy` over a few runs. Then US4
(`smoke` subcommand + CI gate, T039-T041).

## 2026-06-02 — US2 implemented (Python verified, QuakeC compile-pending)

**Status: feature `001-headless-sim-telemetry` — US2 (Phase 4, per-event stream).**

The per-event JSONL stream + reconciled stats. Harness side fully done & verified;
QuakeC emits authored, awaiting a local `just build-quakec` + `just sim`.

- ✅ **Harness (verified, TDD):** `aggregate()` counts kill/death/shot/hit/pickup/
  secret → kills/deaths/damage_dealt/accuracy/weapon_usage/deaths_by_cause;
  `writer.write_events`/`validate_event` write+validate `*.events.jsonl`;
  `stream_invariant_ok` + harness wiring. New tests `test_reconcile.py` (SC-003)
  and events-schema cases in `test_schema.py` (SC-002). `uv run pytest` 23/23,
  ruff + mypy clean. `damage_taken` stays 0 (G1); `secrets_total` from level_start (G2).
- 📝 **QuakeC (compile-pending):** `telemetry.qc` gameplay emitters + hooks in
  combat.qc (kill + outgoing-damage accumulator), weapons.qc (W_Attack shot/hit
  window), client.qc (death), triggers.qc (secret), items.qc (7 pickups). Verified
  every referenced symbol exists; can't compile on droplet.
- ⚠️ **shot/hit scoping:** one shot + at most one hit per trigger-pull. Only
  hitscan (shotgun/super-shotgun) damage that lands synchronously is counted as a
  hit; projectile/animation-frame weapons record the shot but not the hit this
  slice (under-count, never over-count). Full attribution = follow-up.

**Next:** local `just build-quakec` → `just sim` on a map with monsters/items,
then `jq` the `*.events.jsonl` to confirm kill/shot/hit/pickup events reconcile
with the summary. After that: US3 (clamped cvars + `bot_accuracy` wiring).

## 2026-06-02 — US1 verified live end-to-end 🎯

**Status: feature `001-headless-sim-telemetry` — US1 (Phase 3 / MVP) DONE & verified live.**

A headless `fteqw-sv` run on a LibreQuake map autostarts the FrikBot agent, emits
`@EVT|...` telemetry to stdout, and the Python harness writes one schema-valid
`*.summary.json` (`outcome: timeout`, exit 0). First end-to-end proof of the chain.

### What happened this session
- Recovered from a crash with no prior session log. Found state: US1 committed
  (8ee15dd) but compile-UNVERIFIED.
- Branch `001-headless-sim-telemetry` existed only on the droplet → pushed to
  origin. Droplet has no GitHub SSH key; pushed via `gh` HTTPS (`gh auth setup-git`).
- Fixed two FrikBot single-pass compile errors (commit d58c326): forward-declare
  `map_dm{1..6}` in `frikbot/bot.qc`; call `checkextension` (defs.qc) instead of
  the later-declared `frik_checkextension` in `frikbot/bot_ed.qc`.
- First local build (Parker, WSL Ubuntu): `just build-sim` green — `fteqw-sv`,
  `fteqcc`, `progs.dat` (27 benign warnings), `uv sync`. Server build needs NO
  audio libs (opus/speex/vorbis are client-only).
- Vendored LibreQuake v0.09-beta release paks (`mod.zip` → `id1/pak0.pak`,
  `pak1.pak`); default map `lq_e1m1`.
- Verified telemetry reaches stdout (the big unknown): `@EVT|0|level_start|...`
  then `@EVT|15.09|level_end|outcome=timeout|...`. `just sim` → schema-valid summary.
- Cleanups: launcher sets `sv_public 0` and finds the binary in `release/`;
  `id1/` gitignored; `docs/licenses.md` updated (see license caveat below).

### Resume / next
- **US2 (Phase 4):** QuakeC gameplay emits (kill/death/shot/hit/pickup/secret) +
  harness aggregation + JSONL stream + reconciliation test (T024–T033).
- **T006 proper:** resolve LibreQuake licensing (below) + decide final vendoring
  (release paks vs source submodule). For US2 secret tests pick a map WITH a
  `trigger_secret` — `lq_e1m1` has none.
- FrikBot has no waypoints for `lq_*` maps (`couldn't exec maps/lq_e1m1.way`) so
  the bot wanders → timeout. Real navigation is later work.

### Gotchas / environment
- **Build locally, never on the droplet** (~1 GB RAM, no swap — OOMs, would kill
  the shared tmux). Droplet may *run* sims once binaries exist; it can edit/commit.
- `make sv-rel` writes `engine/engine/release/fteqw-sv`; launcher now searches
  there (no symlink needed).
- **LibreQuake license is UNRESOLVED** — repo says "art under BSD" but ships no
  LICENSE file (`NOASSERTION`). `docs/licenses.md` flags it; clear before release.
- Push from the droplet: `gh auth setup-git`, then push the HTTPS URL (no SSH key).
