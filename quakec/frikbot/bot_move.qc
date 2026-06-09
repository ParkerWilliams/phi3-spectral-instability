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
// 004 leap sensor: vertical sibling of frik_whiskers. Classifies the geometry ahead in
// `movedir` (LEDGE_UP / GAP_CROSS / PIT) against the bot's real jump arc and presses jump
// in the launch window. Pure perception + actuation (whiskers own horizontal steering).
// Stub for Task 1 -- wired in but inert; logic lands in Tasks 2-3.
void(vector movedir) frik_leap_sense =
{
	self.leap_class = LEAP_NONE;
	self.leap_edge = FALSE;
};

vector(vector wishdir) frik_whiskers =
{
	local vector eye, fwd, rgt, c, vel;
	local float range, dc, dl, dr, sp, t, steer;

	if (cvar("bot_whiskers_off"))   // debug kill-switch (default off => whiskers on)
		return wishdir;
	wishdir_z = 0;
	if (wishdir == '0 0 0')
		return wishdir;
	wishdir = normalize(wishdir);

	// DYNAMIC avoidance radius: look further ahead the faster the agent is moving, so
	// there is always time to turn (a fixed reach is far too short at speed). The
	// look-ahead TIME is competence-scaled (veteran anticipates earlier);
	// bot_whisker_time overrides the seconds of look-ahead.
	vel = self.velocity; vel_z = 0; sp = vlen(vel);
	t = cvar("bot_whisker_time"); if (t <= 0) t = comp_lerp(WHISK_T_NOVICE, WHISK_T_VET);
	range = WHISKER_MIN + sp * t;
	if (range > WHISKER_MAX) range = WHISKER_MAX;

	eye = self.origin + self.view_ofs;
	fwd = wishdir;
	c = vectoangles(wishdir);
	makevectors(c);				// v_right = flat right of wishdir
	rgt = normalize(v_right);

	// Three feelers (center + both sides). Steer toward the more-open side -- this
	// keeps CLEARANCE from a wall the agent is sliding ALONG (not just stopping a
	// head-on hit), so it actually helps in open-ish roam, and steers harder when the
	// center itself is about to hit.
	traceline(eye, eye + fwd * range, TRUE, self);          dc = trace_fraction;
	traceline(eye, eye + (fwd + rgt) * range, TRUE, self);  dr = trace_fraction;
	traceline(eye, eye + (fwd - rgt) * range, TRUE, self);  dl = trace_fraction;

	if (dc > 0.99 && dr > 0.99 && dl > 0.99)
		return wishdir;			// clear all around -> straight
	if (dc < 0.2 && dr < 0.2 && dl < 0.2)
		return wishdir;			// boxed in -> let roam/stuck handle it

	steer = (dl - dr) * WHISKER_STRENGTH;   // >0 => left clearer => veer left (-rgt)
	if (dc < 0.99)                          // head-on: push hard toward the open side
	{
		if (dl >= dr)
			steer = steer + (1 - dc);   // (tie -> veer left, deterministic)
		else
			steer = steer - (1 - dc);
	}
	wishdir = wishdir - rgt * steer;
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
	frik_leap_sense(way);			// 004: perceive + jump for ledges/gaps (Task 1 stub)
	way = frik_whiskers(way);		// 003: anticipatory anti-scrape
	self.keys = self.keys & 960 + frik_KeysForDir(way);
	self.move_wish = way;			// 004: analog steer target (consumed by CL_KeyMove)

	frik_dodge_obstruction();
	frik_recognize_plat(TRUE);

	// Reactive dodge rewrote the keys to escape a wall whiskers didn't clear -- let those
	// keys drive (legacy path) rather than the now-stale analog wish into the wall.
	if (self.b_aiflags & AI_OBSTRUCTED)
		self.move_wish = '0 0 0';

	if (self.b_aiflags & AI_PRECISION)
	{
		g = angcomp(self.v_angle_x, self.b_angle_x);
		if (fabs(g) > 10)
		{
			self.keys = self.keys & 960;
			self.move_wish = '0 0 0';	// hold still to line up the shot
		}
		g = angcomp(self.v_angle_y, self.b_angle_y);
		if (fabs(g) > 10)
		{
			self.keys = self.keys & 960;
			self.move_wish = '0 0 0';
		}
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
	frik_leap_sense(weird);			// 004: perceive + jump for ledges/gaps (Task 1 stub)
	weird = frik_whiskers(weird);		// 003: anticipatory anti-scrape
 	self.keys = self.keys & 960 + frik_KeysForDir(weird);
	self.move_wish = weird;			// 004: analog steer target (consumed by CL_KeyMove)

	frik_dodge_obstruction();
	frik_recognize_plat(TRUE);
	if (self.b_aiflags & AI_OBSTRUCTED)
	{
		self.move_wish = '0 0 0';	// dodge rewrote the keys -- let them drive
		return FALSE;
	}
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
// idledoom: pick a COMMITTED exploration destination. The radial scan casts rays in
// a full circle; each ray is a CLEAR traceline, so its endpoint is a guaranteed
// line-of-sight-reachable point. Score = openness (ray length) + an "unexplored"
// bias (distance from existing nodes), so it favours the longest ray into NEW space.
// Returns that endpoint, pulled back off the wall it hit. bot_map_awareness scales
// the ray count + the unexplored bias; bot_explore_bias tunes the latter.
vector() bot_pick_frontier =
{
	local vector ang, eye, bestorg, vol;
	local float i, n, len, score, best, away, acc;

	acc = cvar("bot_map_awareness");
	if (acc < 0) acc = 0;
	if (acc > 1) acc = 1;
	// 004: finer angular resolution (24..48 rays, ~15deg..7.5deg) so NARROW corridor
	// openings aren't missed between ray angles -- the agent finds hallways instead of
	// churning until a scan happens to line up. Scales with bot_map_awareness (a sharper
	// agent spots passages: a competence axis). Scans are gated, so the extra traces are
	// cheap.
	n = 24 + floor(acc * 24);

	away = cvar("bot_explore_bias");
	if (away <= 0) away = 1;
	away = away * (0.5 + acc);

	eye = self.origin + self.view_ofs;
	best = -1;
	bestorg = eye;
	vol = '0 0 0';
	i = 0;
	while (i < n)
	{
		ang = '0 0 0';
		ang_y = i * (360 / n);
		makevectors(ang);
		traceline(eye, eye + v_forward * 2300, TRUE, self);
		len = vlen(trace_endpos - eye);
		vol = vol + v_forward * len;   // 004: accumulate toward the open ROOM VOLUME
		                               // (each ray weighted by how far it sees)
		score = len + away * nearest_way_dist(trace_endpos);
		if (score > best)
		{
			best = score;
			bestorg = trace_endpos;
		}
		i = i + 1;
	}
	// Store the room-volume look direction (centroid of openness, flat) for the view
	// bias -- it points into the bulk of the room, away from the wall the feet may hug.
	vol_z = 0;
	if (vol != '0 0 0')
		self.look_dir = normalize(vol);
	// pull back off the wall the winning ray hit so the target isn't inside geometry
	if (vlen(bestorg - eye) > 48)
		bestorg = bestorg - normalize(bestorg - eye) * 40;
	return bestorg;
};

// idledoom: COMMITTED frontier exploration -- replaces the per-frame direction churn
// that caused the dithering/circling. Pick a reachable open point, then COMMIT to
// travelling there until we ARRIVE, time out, or have none -- re-choosing only then.
// The body heads to the point (whisker avoidance handles walls); the view surveys
// independently (a periodic glance offset, eased by smooth-aim; pitch left level by
// bot_angle_set). DynamicWaypoint lays the node trail as it moves -> the graph grows
// for the Dijkstra patrol. Simpler than before: no per-frame momentum/loop/dwell --
// commitment makes those unnecessary.
void() frik_bot_roam =
{
	local vector dir, va, look;
	local float aggr, bored_thresh, amp, d, lv;
	local entity m;

	m = nearest_monster();

	aggr = cvar("bot_aggression");
	if (aggr < 0) aggr = 0;
	if (aggr > 1) aggr = 1;
	bored_thresh = BOREDOM_TICKS * (1.5 - aggr);

	// Bored + a monster we can SEE -> charge it (acquisition takes over once in sight,
	// which resets boredom). Not visible -> keep exploring toward open space below.
	if (self.boredom > bored_thresh)
		if (m != world && sisible(m))
		{
			va = vectoangles(m.origin - (self.origin + self.view_ofs));
			self.b_angle_y = va_y;
			frik_walkmove(normalize(m.origin - self.origin));
			return;
		}

	// (Re)commit a destination ONLY on arrival / timeout / none -- otherwise keep
	// travelling to the same point. That commitment is the whole fix.
	dir = self.explore_dest - self.origin;
	dir_z = 0;
	d = vlen(dir);
	if (self.explore_dest == '0 0 0' || d < 80 || time > self.explore_time)
	{
		self.explore_dest = bot_pick_frontier();
		self.explore_time = time + 4;
		dir = self.explore_dest - self.origin;
		dir_z = 0;
	}
	if (dir == '0 0 0')
		dir = '1 0 0';
	dir = normalize(dir);

	// View: look toward the open ROOM VOLUME (openness centroid from the scan), BLENDED
	// with the move heading so the eyes survey the room while the feet travel -- loosely
	// coupled, not fully decoupled (that's what stops it staring at a wall it's hugging).
	// bot_look_volume tunes the blend: ~0 = look where you walk, 1 = look fully at the
	// volume; <=0/unset -> 0.5. A periodic glance offset (bot_scan_amp) rides on top.
	lv = cvar("bot_look_volume");
	if (lv <= 0) lv = 0.5;
	if (lv > 1) lv = 1;
	look = dir;
	if (self.look_dir != '0 0 0')
		look = normalize(dir * (1 - lv) + self.look_dir * lv);
	va = vectoangles(look);
	amp = cvar("bot_scan_amp");
	if (amp <= 0) amp = 35;
	if (time > self.scan_time)
	{
		self.scan_dir = (random() * 2 - 1) * amp;
		self.scan_time = time + 0.6;
	}
	self.b_angle_y = frik_anglemod(va_y + self.scan_dir);

	// Travel to the committed point; whiskers keep clearance from walls.
	frik_walkmove(dir);
};
