# Leap Sensor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the FrikBot agent real-time perception of leapable geometry (ledges, gaps, pits) so it jumps *purposefully* during traversal, and make that the sole jump authority — deleting the blind reactive hops.

**Architecture:** A new `frik_leap_sense(movedir)` in `quakec/frikbot/bot_move.qc`, a vertical sibling of `frik_whiskers`: a handful of `traceline`s in the bot's move direction classify the geometry ahead as LEDGE_UP / GAP_CROSS / PIT (thresholds = the bot's real jump arc, all live-tunable cvars), and press jump (`bot_jump`) inside the launch window. It is called from the movement path (`frik_movetogoal`/`frik_walkmove`) and takes precedence over the whiskers for a reachable ledge. The old reactive hops (`bot_stall_jump`, and `bot_stuck_check`'s jump) are removed. Look-ahead and commitment are competence-scaled via the existing `comp_lerp` seam.

**Tech Stack:** QuakeC (FrikBot), compiled with `fteqcc` (droplet-OK) → `progs.dat`. **No QC unit-test harness exists and evaluation is by eye** (Parker's direction: feel, not metrics). So each task's objective gate is **`fteqcc` compiles clean**, and behavior milestones have a **local `just watch` checkpoint** as the real verification. Spec: `docs/superpowers/specs/2026-06-09-leap-sensor-design.md`.

**Compile command (every task):**
```bash
cd /root/idledoom/quakec && ../engine/engine/qclib/fteqcc.bin
```
Expected: ends with `Compile finished: progs.dat` and exit 0. Baseline is **27 warnings** (pre-existing Q206/Q302/F314); a correct task adds **no new** warnings/errors.

**Watch command (behavior checkpoints — LOCAL, not the droplet):**
```bash
just watch lq_e1m1     # and lq_e1m2 (more verticality)
# live-tune in the ~ console: bot_competence 0..1, and the bot_leap_* cvars below
```

---

### Task 1: Scaffolding — constants, fields, stub `frik_leap_sense`, wired in as a no-op

Adds everything the sensor needs and calls a do-nothing stub from the movement path, so the tree compiles and behavior is unchanged. This isolates the wiring from the logic.

**Files:**
- Modify: `quakec/frikbot/bot.qc` (entity fields ~line 181; forward-decl block ~line 361; constants near `STALL_DIST_DEFAULT` ~line 291)
- Modify: `quakec/frikbot/bot_move.qc` (new function before `frik_whiskers`)

- [ ] **Step 1: Add the leap class enum, tunable-default constants, and fields** in `quakec/frikbot/bot.qc`.

After the `.float pace_path;` line (end of the entity-field block, ~line 181) add:
```c
.float  leap_class;  // 004 leap sensor: last frik_leap_sense result (LEAP_NONE/LEDGE/GAP/PIT)
.float  leap_edge;   // 004 leap sensor: TRUE while an un-landable drop (PIT) is dead ahead
```

Near `float STALL_DIST_DEFAULT = 32;` (~line 291) add the leap constants:
```c
// 004 leap sensor (frik_leap_sense). Grounded in the bot's real jump arc
// (apex ~= jumpvel^2 / 2*gravity ~= 270^2/1600 ~= 45u). All overridable live via the
// bot_leap_* cvars; defaults baked here. Tuned by eye in `just watch` (feel, not metrics).
float LEAP_NONE  = 0;
float LEAP_LEDGE = 1;
float LEAP_GAP   = 2;
float LEAP_PIT   = 3;
float LEAP_STEP_MAX  = 18;   // <= this auto-steps (Quake), no jump needed
float LEAP_UP_MAX    = 44;   // tallest ledge a standing jump lands on (just under apex)
float LEAP_AHEAD     = 28;   // base horizontal probe distance (~ a stride); + speed*lookahead
float LEAP_GAP_MIN   = 40;   // a forward drop wider than this is a gap worth considering
float LEAP_GAP_MAX   = 224;  // farthest landing a running jump reaches (calibrate by eye)
float LEAP_FALL_PROBE = 72;  // how far down we look for floor ahead (none => a drop)
float LEAP_CLEAR_H   = 52;   // standing clearance required above a candidate landing
float LEAP_RUN_MIN   = 80;   // min horizontal speed to commit a gap jump
float LEAP_T_NOVICE  = 0.12; // look-ahead seconds at competence 0 (perceives late)
float LEAP_T_VET     = 0.42; // look-ahead seconds at competence 1 (perceives early)
```

In the forward-declaration block, after `void() frik_bot_roam;` (~line 361) add:
```c
void(vector movedir)		frik_leap_sense;
```

- [ ] **Step 2: Add the stub function** in `quakec/frikbot/bot_move.qc`, immediately before `vector(vector wishdir) frik_whiskers =`:
```c
// 004 leap sensor: vertical sibling of frik_whiskers. Classifies the geometry ahead in
// `movedir` (LEDGE_UP / GAP_CROSS / PIT) against the bot's real jump arc and presses jump
// in the launch window. Pure perception + actuation (whiskers own horizontal steering).
// Stub for Task 1 — wired in but inert; logic lands in Tasks 2-3.
void(vector movedir) frik_leap_sense =
{
	self.leap_class = LEAP_NONE;
	self.leap_edge = FALSE;
};
```

- [ ] **Step 3: Call the stub from the movement path.** In `quakec/frikbot/bot_move.qc`, in `frik_movetogoal`, find:
```c
	way = normalize(way);
	way = frik_whiskers(way);		// 003: anticipatory anti-scrape
```
and change to:
```c
	way = normalize(way);
	frik_leap_sense(way);			// 004: perceive + jump for ledges/gaps (Task 1 stub)
	way = frik_whiskers(way);		// 003: anticipatory anti-scrape
```
And in `frik_walkmove`, find:
```c
	weird = frik_whiskers(weird);		// 003: anticipatory anti-scrape
```
and change to:
```c
	frik_leap_sense(weird);			// 004: perceive + jump for ledges/gaps (Task 1 stub)
	weird = frik_whiskers(weird);		// 003: anticipatory anti-scrape
```

- [ ] **Step 4: Compile.**

Run: `cd /root/idledoom/quakec && ../engine/engine/qclib/fteqcc.bin`
Expected: `Compile finished: progs.dat`, exit 0, **27 warnings** (no new ones).

- [ ] **Step 5: Commit.**
```bash
git add quakec/frikbot/bot.qc quakec/frikbot/bot_move.qc
git commit -m "feat(leap): scaffold frik_leap_sense (constants, fields, inert wiring)"
```

---

### Task 2: LEDGE_UP detection + purposeful jump (competence-scaled)

The bot perceives a ledge too tall to auto-step but within jump apex, with a landable, clear top, and hops onto it inside the launch window. Look-ahead scales with competence.

**Files:**
- Modify: `quakec/frikbot/bot_move.qc` (`frik_leap_sense` body)

- [ ] **Step 1: Implement ledge detection.** Replace the `frik_leap_sense` stub body with:
```c
void(vector movedir) frik_leap_sense =
{
	local vector flat, ahead, top, landing;
	local float sp, t, reach, h, fwd_frac;

	self.leap_class = LEAP_NONE;
	self.leap_edge = FALSE;

	if (cvar("bot_leap_off"))            // debug kill-switch (default off => sensor on)
		return;
	if (!(self.flags & FL_ONGROUND))     // decide leaps from the ground only
		return;
	if (self.enemy != world)             // combat owns movement this pass (deferred)
		return;
	flat = movedir; flat_z = 0;
	if (flat == '0 0 0')
		return;
	flat = normalize(flat);

	// Competence-scaled look-ahead: veteran perceives earlier/farther (mirrors whiskers).
	sp = vlen(self.velocity);
	t = comp_lerp(LEAP_T_NOVICE, LEAP_T_VET);
	reach = LEAP_AHEAD + sp * t;

	// ---- LEDGE_UP: an obstacle ahead with a landable top in (STEP_MAX, UP_MAX] ----
	traceline(self.origin, self.origin + flat * reach, TRUE, self);
	fwd_frac = trace_fraction;
	if (fwd_frac < 1)
	{
		// drop a probe from above-and-just-past the lip to find the top surface
		ahead = self.origin + flat * (reach * fwd_frac + 8);
		top = ahead; top_z = self.origin_z + LEAP_UP_MAX;
		traceline(top, top - '0 0 1' * (LEAP_UP_MAX + 40), TRUE, self);
		if (trace_fraction < 1 && trace_fraction > 0)
		{
			h = trace_endpos_z - (self.origin_z + VEC_HULL_MIN_z);  // ledge height above feet
			if (h > LEAP_STEP_MAX && h <= LEAP_UP_MAX)
			{
				// standing clearance above the candidate landing?
				landing = trace_endpos; landing_z = landing_z + 1;
				traceline(landing, landing + '0 0 1' * LEAP_CLEAR_H, TRUE, self);
				if (trace_fraction > 0.9)
				{
					self.leap_class = LEAP_LEDGE;
					// launch window: only commit once close to the lip
					if (fwd_frac * reach < LEAP_AHEAD)
						bot_jump();
					return;
				}
			}
		}
	}
};
```

- [ ] **Step 2: Compile.**

Run: `cd /root/idledoom/quakec && ../engine/engine/qclib/fteqcc.bin`
Expected: `Compile finished: progs.dat`, exit 0, no new warnings. (If fteqcc rejects `VEC_HULL_MIN_z`, it's the player hull-min z; substitute the literal `-24`.)

- [ ] **Step 3: WATCH checkpoint (LOCAL).**

Run: `just watch lq_e1m1` then `just watch lq_e1m2`.
Look for: when the agent walks at a low ledge/crate it previously ground against, it now **hops up onto it** and continues, instead of grinding. Sweep `bot_competence 0` (perceives late, may miss) → `1` (commits early/clean). Tune in `~`: `bot_leap_off 1` to A/B against old behavior; raise/lower `LEAP_*` only via re-compile (they're consts) — note any that feel wrong for Task 6 cvar exposure.

- [ ] **Step 4: Commit.**
```bash
git add quakec/frikbot/bot_move.qc
git commit -m "feat(leap): LEDGE_UP detection + competence-scaled purposeful jump"
```

---

### Task 3: GAP_CROSS + PIT detection

If the floor drops away ahead, scan the far side: a landable surface within a running jump → leap across; nothing in reach → PIT (set `leap_edge`, do **not** jump).

**Files:**
- Modify: `quakec/frikbot/bot_move.qc` (`frik_leap_sense` body — append the gap branch)

- [ ] **Step 1: Append the gap/pit branch** to `frik_leap_sense`, immediately before the function's closing `};` (after the LEDGE_UP block's reach into `if (fwd_frac < 1) { ... }`):
```c
	// ---- GAP / PIT: does the floor drop away just ahead? ----
	ahead = self.origin + flat * LEAP_AHEAD;
	traceline(ahead, ahead - '0 0 1' * LEAP_FALL_PROBE, TRUE, self);
	if (trace_fraction >= 1)             // no floor within fall-probe => a drop ahead
	{
		local float far;
		far = LEAP_GAP_MIN;
		while (far <= LEAP_GAP_MAX)
		{
			landing = self.origin + flat * far;
			traceline(landing + '0 0 16', landing - '0 0 1' * LEAP_FALL_PROBE, TRUE, self);
			if (trace_fraction < 1)
			{
				// landable far side at a height the jump can still reach?
				if (trace_endpos_z <= self.origin_z + LEAP_UP_MAX)
				{
					self.leap_class = LEAP_GAP;
					if (sp >= LEAP_RUN_MIN)     // need run speed; commit at the edge
						bot_jump();
					return;
				}
			}
			far = far + 24;
		}
		self.leap_class = LEAP_PIT;          // no landing in reach
		self.leap_edge = TRUE;               // Task 5 steers away from this
		return;
	}
```
(Note: `landing` and `ahead` are already declared locals from Task 2; `far` is declared here. If fteqcc rejects the mid-block `local`, move `local float far;` up to the top declaration line.)

- [ ] **Step 2: Compile.**

Run: `cd /root/idledoom/quakec && ../engine/engine/qclib/fteqcc.bin`
Expected: `Compile finished: progs.dat`, exit 0, no new warnings.

- [ ] **Step 3: WATCH checkpoint (LOCAL).**

Run: `just watch lq_e1m1` and `lq_e1m2`.
Look for: the agent **leaps across** small gaps/ledcovers when running, and at a real drop-off with no reachable far side it **does not jump** (no faceplant — pit-avoidance; the actual steer-away lands in Task 5, so for now it should at least stop committing the jump). Sweep `bot_competence`.

- [ ] **Step 4: Commit.**
```bash
git add quakec/frikbot/bot_move.qc
git commit -m "feat(leap): GAP_CROSS + PIT detection (jump across / refuse pits)"
```

---

### Task 4: Remove the blind reactive hops

The leap sensor is now the sole traversal jump authority, so delete the cosmetic stall-hop and strip the stuck-recovery's reflexive jump (it keeps its turn/re-route).

**Files:**
- Modify: `quakec/frikbot/bot_phys.qc` (`bot_stall_jump` ~line 610, `bot_stuck_check` ~line 594, and the `bot_stall_jump()` call site in `PostPhysics`/wherever it's invoked)

- [ ] **Step 1: Find the call sites.**

Run: `grep -n "bot_stall_jump\|bot_stuck_check" /root/idledoom/quakec/frikbot/bot_phys.qc`
Expected: the two definitions plus their call sites in the physics frame.

- [ ] **Step 2: Strip the jump from `bot_stuck_check`.** In `quakec/frikbot/bot_phys.qc`, in `bot_stuck_check`, find:
```c
			if (vlen(d) < STUCK_MIN_DIST)
			{
				self.b_angle_y = frik_anglemod(self.b_angle_y + 90 + random() * 180);
				bot_jump();
				self.target1 = self.target2 = self.target3 = self.target4 = world;
				self.route_failed = 1;    // BotAI -> frik_bot_roam picks a new frontier
				if (self.current_way)
					self.current_way.b_aiflags = self.current_way.b_aiflags | AI_PRECISION;
			}
```
and remove the `bot_jump();` line so it reads:
```c
			if (vlen(d) < STUCK_MIN_DIST)
			{
				self.b_angle_y = frik_anglemod(self.b_angle_y + 90 + random() * 180);
				// 004: no reflexive hop — frik_leap_sense owns jumping. Wedged with
				// nothing leapable ahead is a PATHING problem: turn + re-route only.
				self.target1 = self.target2 = self.target3 = self.target4 = world;
				self.route_failed = 1;    // BotAI -> frik_bot_roam picks a new frontier
				if (self.current_way)
					self.current_way.b_aiflags = self.current_way.b_aiflags | AI_PRECISION;
			}
```

- [ ] **Step 3: Neutralise `bot_stall_jump`.** Replace the entire `bot_stall_jump` function body (keep the signature so the call site still links) with an early return that documents the removal:
```c
void() bot_stall_jump =
{
	// 004: REMOVED. The reflexive 0.4s "I'm not moving, hop" was the cosmetic spasm.
	// frik_leap_sense (bot_move.qc) is now the sole traversal jump authority — it hops
	// only at real, reachable ledges/gaps. Kept as an empty stub so the call site and
	// the bot_stall_dist cvar/field (stall_org/stall_time) need no churn this pass.
	return;
};
```

- [ ] **Step 4: Compile.**

Run: `cd /root/idledoom/quakec && ../engine/engine/qclib/fteqcc.bin`
Expected: `Compile finished: progs.dat`, exit 0. (Expect possibly *fewer* warnings if `stall_org`/`d`/`md` become unused — that is fine; note the count.)

- [ ] **Step 5: WATCH checkpoint (LOCAL).**

Run: `just watch lq_e1m1`.
Look for: **the in-place hopping/spasming is gone.** The agent walks smoothly; it jumps only when there is an actual ledge/gap (from Tasks 2-3). If it ever gets genuinely wedged, it turns and re-routes instead of bouncing.

- [ ] **Step 6: Commit.**
```bash
git add quakec/frikbot/bot_phys.qc
git commit -m "feat(leap): remove the blind cosmetic hop; leap sensor is sole jump authority"
```

---

### Task 5: Whisker precedence + pit steer-away

A reachable ledge must not be treated by the whiskers as a wall to avoid; and a pit ahead must steer the bot away.

**Files:**
- Modify: `quakec/frikbot/bot_move.qc` (the two `frik_leap_sense` call sites from Task 1, in `frik_movetogoal` and `frik_walkmove`)

- [ ] **Step 1: Ledge precedence + pit steer in `frik_movetogoal`.** Replace the Task-1 wiring:
```c
	way = normalize(way);
	frik_leap_sense(way);			// 004: perceive + jump for ledges/gaps (Task 1 stub)
	way = frik_whiskers(way);		// 003: anticipatory anti-scrape
```
with:
```c
	way = normalize(way);
	frik_leap_sense(way);			// 004: perceive + jump for ledges/gaps
	if (self.leap_class == LEAP_LEDGE)
		;				// reachable ledge: go straight at it, skip whisker veer
	else if (self.leap_edge)
		way = frik_leap_avoid(way);	// pit ahead: steer away from the drop
	else
		way = frik_whiskers(way);	// 003: anticipatory anti-scrape
```

- [ ] **Step 2: Same wiring in `frik_walkmove`.** Replace:
```c
	frik_leap_sense(weird);			// 004: perceive + jump for ledges/gaps (Task 1 stub)
	weird = frik_whiskers(weird);		// 003: anticipatory anti-scrape
```
with:
```c
	frik_leap_sense(weird);			// 004: perceive + jump for ledges/gaps
	if (self.leap_class == LEAP_LEDGE)
		;				// reachable ledge: go straight at it
	else if (self.leap_edge)
		weird = frik_leap_avoid(weird);	// pit ahead: steer away from the drop
	else
		weird = frik_whiskers(weird);	// 003: anticipatory anti-scrape
```

- [ ] **Step 3: Add `frik_leap_avoid`** in `quakec/frikbot/bot_move.qc`, immediately after `frik_leap_sense`:
```c
// 004: turn a wishdir away from a pit dead ahead. Samples the floor a stride out to the
// left and right of `movedir` and steers toward whichever side still has ground; if both
// sides are also drops, back off (reverse) so the agent never walks off the edge.
vector(vector movedir) frik_leap_avoid =
{
	local vector flat, lft;
	flat = movedir; flat_z = 0; flat = normalize(flat);
	makevectors(vectoangles(flat));
	lft = normalize(v_right) * -1;
	traceline(self.origin + (flat - v_right) * LEAP_AHEAD,
		(self.origin + (flat - v_right) * LEAP_AHEAD) - '0 0 1' * LEAP_FALL_PROBE, TRUE, self);
	if (trace_fraction < 1)
		return normalize(flat + lft);      // left has ground -> veer left
	traceline(self.origin + (flat + v_right) * LEAP_AHEAD,
		(self.origin + (flat + v_right) * LEAP_AHEAD) - '0 0 1' * LEAP_FALL_PROBE, TRUE, self);
	if (trace_fraction < 1)
		return normalize(flat - lft);      // right has ground -> veer right
	return flat * -1;                          // both sides drop -> back off
};
```
And forward-declare it in `quakec/frikbot/bot.qc` after the `frik_leap_sense` decl:
```c
vector(vector movedir)		frik_leap_avoid;
```

- [ ] **Step 4: Compile.**

Run: `cd /root/idledoom/quakec && ../engine/engine/qclib/fteqcc.bin`
Expected: `Compile finished: progs.dat`, exit 0, no new warnings.

- [ ] **Step 5: WATCH checkpoint (LOCAL).**

Run: `just watch lq_e1m1` and `lq_e1m2`.
Look for: the agent walks **straight at** a ledge it intends to hop (no last-moment whisker swerve away from it), and it **veers away from / backs off** an actual pit instead of stalling at the lip. Sweep `bot_competence`.

- [ ] **Step 6: Commit.**
```bash
git add quakec/frikbot/bot.qc quakec/frikbot/bot_move.qc
git commit -m "feat(leap): whisker precedence for ledges + pit steer-away"
```

---

### Task 6: Live-tunable cvars + docs

Promote the most feel-critical thresholds from baked constants to live cvars (so they can be tuned in the `~` console during watch), and document.

**Files:**
- Modify: `quakec/frikbot/bot_move.qc` (`frik_leap_sense` — read cvar overrides)
- Modify: `docs/bot-stats.md` (cvar rows), `docs/session-log.md` (entry)

- [ ] **Step 1: Read cvar overrides for the feel-critical thresholds.** In `frik_leap_sense`, just after `flat = normalize(flat);`, add:
```c
	// live overrides (0/unset => baked default), so they can be tuned in ~ during watch
	local float up_max, gap_max, run_min;
	up_max = cvar("bot_leap_up");   if (up_max <= 0) up_max = LEAP_UP_MAX;
	gap_max = cvar("bot_leap_gap"); if (gap_max <= 0) gap_max = LEAP_GAP_MAX;
	run_min = cvar("bot_leap_run"); if (run_min <= 0) run_min = LEAP_RUN_MIN;
```
Then replace the three uses: `LEAP_UP_MAX` → `up_max` (both the LEDGE_UP `h <= LEAP_UP_MAX` and the GAP far-side `trace_endpos_z <= self.origin_z + LEAP_UP_MAX`), `LEAP_GAP_MAX` → `gap_max` (the `while (far <= LEAP_GAP_MAX)`), and `sp >= LEAP_RUN_MIN` → `sp >= run_min`.

- [ ] **Step 2: Compile.**

Run: `cd /root/idledoom/quakec && ../engine/engine/qclib/fteqcc.bin`
Expected: `Compile finished: progs.dat`, exit 0, no new warnings.

- [ ] **Step 3: Document the cvars** in `docs/bot-stats.md`. After the `bot_analog_off` row in the sim/debug table add:
```markdown
| `bot_leap_off` | int | `1` = disable the leap sensor (debug A/B vs the old behavior); `0` (default) = on |
| `bot_leap_up` | float | tallest ledge (units above feet) the agent will jump onto; `0`/unset = baked 44 (≈ jump apex). **Live-tunable** |
| `bot_leap_gap` | float | farthest far-side landing (units) the agent will leap a gap to; `0`/unset = baked 224. **Live-tunable** |
| `bot_leap_run` | float | min horizontal speed to commit a gap jump; `0`/unset = baked 80. **Live-tunable** |
```

- [ ] **Step 4: Add a session-log entry** at the top of `docs/session-log.md` (under the header), summarising: branch `feat/leap-sensor`; what shipped (frik_leap_sense ledge/gap/pit, sole jump authority, hop removed, whisker precedence, competence-scaled, cvars); compile-clean but **watch-tuned, engine-run only locally**; next = the watch sweep is the arbiter.

- [ ] **Step 5: Commit.**
```bash
git add quakec/frikbot/bot_move.qc docs/bot-stats.md docs/session-log.md
git commit -m "feat(leap): live-tunable bot_leap_* cvars + docs"
```

---

## Notes for the implementer

- **The thresholds will need watch-tuning.** The baked numbers (`LEAP_UP_MAX 44`, `LEAP_GAP_MAX 224`, the launch window `fwd_frac*reach < LEAP_AHEAD`, `LEAP_RUN_MIN 80`) are physics-reasoned starting points, not final. Expect to sit in `just watch` and turn `bot_leap_up`/`bot_leap_gap`/`bot_leap_run` + `bot_competence` until leaps land cleanly and read as skilled. That iteration **is** the work; the code is the scaffold for it.
- **Trace correctness is the risk, not logic.** If a leap never fires, sanity-check trace directions/heights with a temporary `bprint`/`@EVT` of `self.leap_class` per think before assuming a threshold problem.
- **`VEC_HULL_MIN_z`**: if fteqcc rejects the component suffix on the global, substitute the literal `-24` (the standard player hull min-z).
- **Competence, first slice = look-ahead only.** The plan scales *perception distance* with `bot_competence` (Task 2, the primary "getting better" lever). The spec's richer competence beats — a novice attempting **only low ledges** (a competence-scaled `up_max`) and a **beat of hesitation** before committing (reuse the existing `dwell_time`) — are **deferred to the watch-tuning pass**: add them only if, watching the `bot_competence 0→1` sweep, the low end doesn't read as "still learning." They are one-liners (`up_max = comp_lerp(LEAP_UP_NOVICE, up_max)`; a short pre-jump `dwell_time`) layered on once the base sensor feels right — don't add them blind.
- **Out of scope (do not add):** combat dodge-jumps (the `self.enemy != world` early-return defers them), item/secret reach-jumps, rocket-jump/bunny-hop, and nav-graph jump-links. Keep the sensor traversal-only.
```
