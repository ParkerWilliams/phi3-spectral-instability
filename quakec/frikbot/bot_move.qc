/***********************************************
*                                              *
*            FrikBot Movement AI               *
*     "The slightly better movement AI"        *
*                                              *
***********************************************/

/*

This program is in the Public Domain. My crack legal
team would like to add:

RYAN "FRIKAC" SMITH IS PROVIDING THIS SOFTWARE "AS IS"
AND MAKES NO WARRANTY, EXPRESS OR IMPLIED, AS TO THE
ACCURACY, CAPABILITY, EFFICIENCY, MERCHANTABILITY, OR
FUNCTIONING OF THIS SOFTWARE AND/OR DOCUMENTATION. IN
NO EVENT WILL RYAN "FRIKAC" SMITH BE LIABLE FOR ANY
GENERAL, CONSEQUENTIAL, INDIRECT, INCIDENTAL,
EXEMPLARY, OR SPECIAL DAMAGES, EVEN IF RYAN "FRIKAC"
SMITH HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH
DAMAGES, IRRESPECTIVE OF THE CAUSE OF SUCH DAMAGES. 

You accept this software on the condition that you
indemnify and hold harmless Ryan "FrikaC" Smith from
any and all liability or damages to third parties,
including attorney fees, court costs, and other
related costs and expenses, arising out of your use
of this software irrespective of the cause of said
liability. 

The export from the United States or the subsequent
reexport of this software is subject to compliance
with United States export control and munitions
control restrictions. You agree that in the event you
seek to export this software, you assume full
responsibility for obtaining all necessary export
licenses and approvals and for assuring compliance
with applicable reexport restrictions. 

Any reproduction of this software must contain
this notice in its entirety. 

*/

void() bot_jump =
{
	// TODO check for precision, etc.
	self.button2 = TRUE;
};

float(entity e) bot_can_rj =
{
	// this returns true of the bot can rocket/superjump/hook
	// if your mod doesn't have an RL you can just return FALSE all the time
	// if it has a hook or some other means for the bot to get to high places
	// you can check here for that capability

	// am I dumb?
	if (e.b_skill == 0)
		return FALSE;

	// quad = bad
	if (e.items & 4194304)
		return FALSE;

	// do I have rockets & RL?
	if (!((e.items & 32) && (e.ammo_rockets > 0)))
		return FALSE;

	// do I have pent?
	if (e.items & 1048576)
		return TRUE;

	if (e.health > 50)
		return TRUE;
	else
		return FALSE;
};

float(float flag) frik_recognize_plat =
{
	if ((self.classname != "waypoint") && !(self.flags & FL_ONGROUND))
		return FALSE;
	traceline(self.origin, self.origin - '0 0 64', TRUE, self);
	if (trace_ent != world)
	{
		if (flag) // afect bot movement too
		{
			if (self.keys & KEY_MOVEUP)
			{
				if (trace_ent.velocity_z > 0)
					self.keys = self.keys & 960; // 960 is all view keys
			}
			else if (self.keys & KEY_MOVEDOWN)
			{
				if (trace_ent.velocity_z < 0)
					self.keys = self.keys & 960;
			}
		}
		return TRUE;
	}
	else
		return FALSE;
};

float(vector sdir) frik_KeysForDir =
{

	local vector keydir;
	local float outkeys, tang;
	outkeys = 0;
	if (sdir_x || sdir_y)
	{
		// Everything is tested against 60 degrees,
		// this allows the bot to overlap the keys
		// 30 degrees on each diagonal  45 degrees 
		// might look more realistic

 		keydir = vectoangles(sdir);
		tang = angcomp(keydir_y, self.v_angle_y);
		if ((tang <= 150) && (tang >= 30))
			outkeys = outkeys + KEY_MOVELEFT;
		else if ((tang >= -150) && (tang <= -30))
			outkeys = outkeys + KEY_MOVERIGHT;
		if (fabs(tang) <= 60)
			outkeys = outkeys + KEY_MOVEFORWARD;
		else if (fabs(tang) >= 120)
			outkeys = outkeys + KEY_MOVEBACK;
	}
	if (sdir_z > 0)
		outkeys = outkeys + KEY_MOVEUP;
	else if (sdir_z < 0)
		outkeys = outkeys + KEY_MOVEDOWN;
	return outkeys;

};

/*
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

frik_obstructed

Bot has hit a ledge or wall that he should
manuever around.

-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
*/

void(vector whichway, float danger) frik_obstructed =
{
	local float dist;
	local vector disway, org;
// TODO: something
	if (self.b_aiflags & AI_BLIND)
		return;
	org = realorigin(self.target1);

	if (danger)
	{
		self.b_aiflags = self.b_aiflags | AI_DANGER;
		self.keys = frik_KeysForDir('0 0 0' - whichway);
	}
	if (self.b_aiflags & AI_PRECISION)
		return;


	if (self.target1)
	{
		if (self.b_aiflags & AI_OBSTRUCTED)
		{
			if (!(self.b_aiflags & AI_DANGER))
			{
				self.b_aiflags = self.b_aiflags - AI_OBSTRUCTED;
				return;
			}
			else if (!danger)
				return;
		}
		self.obs_dir = whichway;
		disway_x = whichway_y * -1;
		disway_y = whichway_x;
		dist = vlen(org - (self.origin + disway));
		disway_x = whichway_y;
		disway_y = whichway_x * -1;
		self.wallhug = vlen(org - (self.origin + disway)) > dist;
		self.b_aiflags = self.b_aiflags | AI_OBSTRUCTED;
		
	}
	else
	{
		disway_x = whichway_y * -1;
		disway_y = whichway_x;
		dist = vlen(disway - self.obs_dir);
		disway_x = whichway_y;
		disway_y = whichway_x * -1;
		self.wallhug = vlen(disway - self.obs_dir) < dist;
		self.obs_dir = whichway;

		self.b_aiflags = self.b_aiflags | AI_OBSTRUCTED;
	}
};

/*
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

frik_obstacles

Detects small bumps the bot needs to jump over
or ledges the bot should avoid falling in.

Also responsible for jumping gaps.

-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
*/

void() frik_obstacles =
{
	local vector start, stop, ang;
	local float test, conts, dist, hgt;

	if (!(self.flags & FL_ONGROUND))
		return;
	if (self.b_aiflags & AI_BLIND)
		return;

	ang = normalize(self.velocity);
	ang_z = 0;
	start = self.origin + ang * 32; // ahem
	start_z = self.origin_z + self.maxs_z;
	stop = start;
	stop_z = self.origin_z + self.mins_z;
	traceline(start, stop - '0 0 256', TRUE, self);
	if (trace_allsolid || trace_startsolid)
		return;
	hgt = trace_endpos_z - stop_z;

	if (hgt > 18)
	{
		bot_jump();
		return;
	}
	if (hgt >= 0)
		return;

	conts = pointcontents(trace_endpos + '0 0 4');
	start = stop - '0 0 8';
	stop = start + ang *  256;
	traceline(start, stop, TRUE, self);
	test = vlen(trace_endpos - start);
	if (test <= 20)
		return; // it's a walkable gap, do nothing
	ang_x = self.velocity_y * -1;
	ang_y = self.velocity_x;
	ang = normalize(ang);
	traceline(start - (ang * 10), start + (ang * 10), TRUE, self);
	if ((trace_fraction != 1) || trace_startsolid)
		return; // gap is only 20 wide, walkable	
	ang = self.velocity;
	ang_z = 0;
	dist = ((540 / sv_gravity) * vlen(ang))/* + 32*/;
	if (test > dist) // I can't make it
	{
		if (conts < -3) // bad stuff down dare
		{
			frik_obstructed(ang, TRUE);
			return;
		}
		else
		{
			if (self.target1)
			{
				stop = realorigin(self.target1);
				if ((stop_z - self.origin_z) < -32)
					return; // safe to fall
			}
			frik_obstructed(ang, FALSE);
			return;
		}
	}
	else
	{
		ang = normalize(ang);
		//look for a ledge
		traceline(self.origin, self.origin + (ang * (test + 20)), TRUE, self); 
		if (trace_fraction != 1)
		{
			if (conts < -3) // bad stuff down dare
			{
				frik_obstructed(ang, TRUE);
				return;
			}
			else
			{
				if (self.target1)
				{
					stop = realorigin(self.target1);
					if ((stop_z - self.origin_z) < -32)
						return; // safe to fall
				}
				frik_obstructed(ang, FALSE);
				return;
			}
		}

		if (self.target1)
		{
			// getting furter away from my target?
			test = vlen(self.target1.origin - (ang + self.origin));
			if (test > vlen(self.target1.origin - self.origin))
			{
				if (conts < -3) // bad stuff down dare
				{
					frik_obstructed(ang, TRUE);
					return;
				}
				else
				{
					frik_obstructed(ang, FALSE);
					return;
				}
			}
		}
	}
	if (hgt < -18)
	{
		if (conts < -3) // bad stuff down dare
		{
			frik_obstructed(ang, TRUE);
			return;
		}
		if (self.target1)
		{
			stop = realorigin(self.target1);
			if ((stop_z - self.origin_z) < -32)
			{

				return; // safe to fall
			}
		}
		bot_jump();
	}
	// go for it
};

/*
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

After frik_obstructed, the bot uses the 
following funtion to move "around" the obstacle

I have no idea how well it will work

-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
*/

void() frik_dodge_obstruction =
{
	local vector way, org;
	local float oflags, yaw;

	if (!(self.b_aiflags & AI_OBSTRUCTED))
		return;
	if ((self.b_aiflags & (AI_BLIND | AI_PRECISION)) || !(self.flags & FL_ONGROUND))
	{
		self.b_aiflags = self.b_aiflags - AI_OBSTRUCTED;
		return;
	}

	// perform a walkmove check to see if the obs_dir is still obstructed
	// walkmove is less forgiving than frik_obstacles, so I dunno 
	// how well this will work

	oflags = self.flags;
	org = self.origin;

	yaw = vectoyaw(self.obs_dir);
	if (walkmove(yaw, 32))
		self.b_aiflags = self.b_aiflags - AI_OBSTRUCTED;
	else
	{
		if (self.b_aiflags & AI_DANGER)
		{
			way = '0 0 0' - self.obs_dir;
		}
		else if (self.wallhug)
		{
			way_x = self.obs_dir_y * -1;
			way_y = self.obs_dir_x;
		}
		else
		{
			way_x = self.obs_dir_y;
			way_y = self.obs_dir_x * -1;
		}
		self.keys = self.keys & 960 + frik_KeysForDir(way);
	}
	
	// fix the bot

	self.origin = org;
	self.flags = oflags;
};

/*
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

movetogoal and walkmove replacements

blah

-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
*/

// idledoom (003 Slice A): anticipatory anti-scrape. Bend a wish-direction away
// from walls BEFORE we press movement keys, so the agent curves around a corner
// instead of grinding its face along it and then reactively dodging (the old
// frik_dodge_obstruction only fires AFTER contact). Look-ahead range rides
// bot_competence: novices react late and hug walls, veterans see the corner early
// and ease around. Horizontal only; never touches the view (move/view stay
// decoupled). Returns an adjusted unit world direction.
vector(vector wishdir) frik_whiskers =
{
	local vector eye, fwd, rgt, c;
	local float range, dc, dl, dr;

	if (cvar("bot_whiskers_off"))   // debug bisection kill-switch (default off => whiskers on)
		return wishdir;
	wishdir_z = 0;
	if (wishdir == '0 0 0')
		return wishdir;
	wishdir = normalize(wishdir);

	range = comp_lerp(WHISKER_NEAR, WHISKER_FAR);
	eye = self.origin + self.view_ofs;
	fwd = wishdir;

	traceline(eye, eye + fwd * range, TRUE, self);
	dc = trace_fraction;
	if (dc > 0.99)
		return wishdir;			// open ahead -> walk straight

	c = vectoangles(wishdir);
	makevectors(c);				// v_right = flat right of wishdir
	rgt = normalize(v_right);

	traceline(eye, eye + (fwd + rgt) * range, TRUE, self);
	dr = trace_fraction;
	traceline(eye, eye + (fwd - rgt) * range, TRUE, self);
	dl = trace_fraction;

	if (dr < 0.2 && dl < 0.2)
		return wishdir;			// boxed both sides -> let roam/stuck handle it

	// steer toward the more-open side; strength grows as the center gets blocked
	if (dr >= dl)
		wishdir = wishdir + rgt * (1 - dc);
	else
		wishdir = wishdir - rgt * (1 - dc);
	wishdir_z = 0;
	return normalize(wishdir);
};

void() frik_movetogoal =
{
	local vector way, start, stop, ang;
	local float g;

	if (time < self.dwell_time)
	{
		self.keys = self.keys & 960;	// 003: junction hesitation -- stop, keep looking
		return;
	}

	if (self.target1 == world)
	{
		makevectors(self.v_angle);
		frik_walkmove(v_forward);
		return;
	}
	way = realorigin(self.target1) - self.origin;
	if (vlen(way) < 25)
	{
		self.keys = self.keys & 960;
		return;
	}

	way = normalize(way);
	way = frik_whiskers(way);		// 003: anticipatory anti-scrape
	self.keys = self.keys & 960 + frik_KeysForDir(way);

	frik_dodge_obstruction();
	frik_recognize_plat(TRUE);

	if (self.b_aiflags & AI_PRECISION)
	{
		g = angcomp(self.v_angle_x, self.b_angle_x);
		if (fabs(g) > 10)
			self.keys = self.keys & 960;
		g = angcomp(self.v_angle_y, self.b_angle_y);
		if (fabs(g) > 10)
			self.keys = self.keys & 960;
	}
};

float(vector weird) frik_walkmove =
{
	// okay so it's not walkmove
	// sue me
	if (time < self.dwell_time)
	{
		self.keys = self.keys & 960;	// 003: junction hesitation -- stop, keep looking
		return TRUE;
	}
	weird = frik_whiskers(weird);		// 003: anticipatory anti-scrape
 	self.keys = self.keys & 960 + frik_KeysForDir(weird);

	frik_dodge_obstruction();
	frik_recognize_plat(TRUE);
	if (self.b_aiflags & AI_OBSTRUCTED)
		return FALSE;
	else
		return TRUE;
};


/*
-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

The "hook" method of navigation. This nav
system is copyrighted 1999 by Ryan "Frika C" 
Smith, keep that in mind when you steal it.

I brought this back because normal roaming
won't work - the bot gets distracted by it's
own waypoints.

-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
*/

// idledoom (002): distance from p to the nearest existing waypoint — used to
// score "how unexplored" a candidate spot is (frontier-seeking). O(N) over the
// graph; roam is gated (not every frame), acceptable for the first cut.
float(vector p) nearest_way_dist =
{
	local entity w;
	local float best, d;
	best = 1000000;
	w = way_head;
	while (w)
	{
		d = vlen(w.origin - p);
		if (d < best)
			best = d;
		w = w._next;
	}
	return best;
};

// idledoom (boredom): the nearest live monster anywhere on the map — the
// combat-seeking target when the agent is bored. findradius over a map-spanning
// radius; cheap enough since roam is gated (not run every frame).
entity() nearest_monster =
{
	local entity m, best;
	local float d, bd;
	bd = 1000000;
	best = world;
	m = findradius(self.origin, 100000);
	while (m)
	{
		if (m.flags & FL_MONSTER)
			if (m.health > 0)
			{
				d = vlen(m.origin - self.origin);
				if (d < bd)
				{
					bd = d;
					best = m;
				}
			}
		m = m.chain;
	}
	return best;
};

// idledoom: human-style exploration. Instead of scraping along walls, the agent
// looks at the open space around it and walks toward the most open direction —
// like a person playing an FPS. Movement is steered INDEPENDENTLY of the view:
// the body heads to open space (frik_walkmove of a world direction) while the eyes
// scan around (a glance offset on b_angle, eased by bot_smooth_aim).
//
// Radial scan: cast rays in a full circle from the eye; each ray's length is how
// open that heading is. Score = openness + an "unexplored" bias (distance from
// existing waypoints) so it prefers NEW space over re-treading; boredom amplifies
// that bias so the agent stops doing laps and EXITS the area it's in. Ray count and
// the bias scale with bot_map_awareness (US3). Tunable live: bot_explore_bias,
// bot_exit_bias, bot_scan_amp (view look-around amplitude).
void() frik_bot_roam =
{
	local vector ang, eye, bestdir, bestorg, va, edir, d;
	local float i, n, len, score, best, acc, aggr, bored_thresh, away, amp, mom, pull, lp;
	local entity m;

	m = nearest_monster();   // computed once: used by the bored charge AND the soft tug

	// Lightweight repeat detector: if over LOOP_WINDOW the agent's NET travel is tiny
	// (it kept moving but ended up where it started -- circling / ping-ponging /
	// doubling back over seconds), escalate exploration for a moment to break out.
	// Distinct from stall-jump (obstacle) and stuck_check (wedged): this catches
	// "moving but getting nowhere". Tunable/off via bot_loop_dist.
	lp = cvar("bot_loop_dist");
	if (!lp) lp = LOOP_MIN_PROGRESS;
	if (lp > 0)
		if (time >= self.loop_time)
		{
			if (self.loop_org != '0 0 0')
			{
				d = self.loop_org - self.origin;
				d_z = 0;
				if (vlen(d) < lp)
					self.loop_boost = time + LOOP_BOOST_SECS;
			}
			self.loop_org = self.origin;
			self.loop_time = time + LOOP_WINDOW;
		}

	aggr = cvar("bot_aggression");
	if (aggr < 0) aggr = 0;
	if (aggr > 1) aggr = 1;
	bored_thresh = BOREDOM_TICKS * (1.5 - aggr);

	// Bored + a monster somewhere -> go hunt it. Head toward it (decoupled); normal
	// acquisition lines up the shot once it's in sight, which resets boredom.
	if (self.boredom > bored_thresh)
	{
		// Only CHARGE a monster we can actually SEE. A blind beeline at the nearest
		// monster anywhere on the map (it may be behind a wall) drives the agent
		// face-first into geometry and wedges it there forever -- boredom never
		// resets because it never reaches the monster (the "drags its face along a
		// wall" bug). If it's not visible, fall through to the radial frontier roam
		// below, which heads to OPEN space and navigates around walls until a
		// monster actually comes into sight.
		if (m != world && sisible(m))
		{
			va = vectoangles(m.origin - (self.origin + self.view_ofs));
			self.b_angle_y = va_y;
			frik_walkmove(normalize(m.origin - self.origin));
			return;
		}
	}

	acc = cvar("bot_map_awareness");
	if (acc < 0) acc = 0;
	if (acc > 1) acc = 1;
	n = 12 + floor(acc * 12);             // 12..24 rays (finer choice at high awareness)

	away = cvar("bot_explore_bias");
	if (away <= 0) away = 1;
	away = away * (0.5 + acc);            // higher awareness -> stronger pull to new space
	if (self.boredom > bored_thresh)
	{
		amp = cvar("bot_exit_bias");
		if (amp <= 0) amp = 3;
		away = away + amp;               // bored -> strongly prefer leaving the area
	}

	eye = self.origin + self.view_ofs;

	// Two soft biases blended into the openness/frontier score (units, tunable live):
	//   bot_momentum   -- reward continuing the current heading; penalize doubling
	//                     back (a "return vector" ~180deg gets the full penalty).
	//   bot_enemy_pull -- a gentle drift TOWARD the nearest monster through open
	//                     space, so it seeks combat without clipping at walls (the
	//                     LOS charge above takes the final approach once it's seen).
	mom = cvar("bot_momentum");    if (!mom) mom = MOMENTUM_DEFAULT;    if (mom < 0) mom = 0;
	pull = cvar("bot_enemy_pull"); if (!pull) pull = ENEMY_PULL_DEFAULT; if (pull < 0) pull = 0;
	edir = '0 0 0';
	if (m != world && pull > 0)
	{
		edir = m.origin - eye;
		edir_z = 0;
		edir = normalize(edir);
	}
	// Breaking a loop: drop the enemy tug and crank frontier-seeking, and RELEASE
	// momentum (mom = 0) so it's free to turn to the longest FRESH ray and leave.
	// NEVER commit harder to the current heading here -- that drove it face-first
	// into corners and wedged it (it would then just stall-jump in place).
	if (time < self.loop_boost)
	{
		pull = 0;
		away = away * LOOP_AWAY_MULT;
		mom = 0;
	}

	best = -1;
	bestdir = '0 0 0';
	bestorg = eye;
	i = 0;
	while (i < n)
	{
		ang = '0 0 0';
		ang_y = i * (360 / n);
		makevectors(ang);
		traceline(eye, eye + v_forward * 2300, TRUE, self);
		len = vlen(trace_endpos - eye);
		score = len + away * nearest_way_dist(trace_endpos)
		            + mom * (v_forward * self.last_movedir)   // anti-doubling-back
		            + pull * (v_forward * edir);              // soft tug toward enemies
		if (score > best)
		{
			best = score;
			bestdir = v_forward;
			bestorg = trace_endpos;
		}
		i = i + 1;
	}

	// Drop a frontier waypoint partway toward the open space (coverage telemetry +
	// the anti-lap "visited" memory the next scan reads via nearest_way_dist).
	if (vlen(bestorg - eye) > 96)
		SpawnTempWaypoint(eye + bestdir * (vlen(bestorg - eye) * 0.5));

	// View: scan the environment independently of movement. Re-pick a glance offset
	// around the heading periodically; the eased turn sweeps the view there for a
	// continuous "surveying" look. amp 0 (unset) -> face the heading (no scan).
	va = vectoangles(bestdir);
	amp = cvar("bot_scan_amp");
	if (amp <= 0) amp = 35;
	if (time > self.scan_time)
	{
		self.scan_dir = (random() * 2 - 1) * amp;
		self.scan_time = time + 0.6;
	}
	self.b_angle_y = frik_anglemod(va_y + self.scan_dir);

	// Move toward the open direction, decoupled from the view (frik_KeysForDir
	// presses forward/strafe relative to v_angle). Body heads to open space; eyes
	// scan around — how a person actually plays.
	// 003 tepid pacing: a low-competence agent hesitates on a SHARP turn -- pause,
	// let the view ease around to the new heading, then commit. Veterans (dwell 0)
	// flow without breaking stride. Guarded so an already-dwelling agent never
	// extends its own pause into a stall.
	if (!cvar("bot_dwell_off"))   // debug bisection kill-switch (settles within ~0.5s)
	if (time >= self.dwell_time)
		if (self.last_movedir != '0 0 0')
			if ((bestdir * self.last_movedir) < TURN_DWELL_DOT)
				self.dwell_time = time + comp_lerp(DWELL_NOVICE, 0);
	self.last_movedir = bestdir;

	frik_walkmove(bestdir);
};
