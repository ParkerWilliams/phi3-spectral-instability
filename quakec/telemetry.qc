/*
 * telemetry.qc — headless-sim telemetry emission (feature 001-headless-sim-telemetry).
 *
 * Emits one tagged line per observable event to the dedicated server's console
 * (stdout):
 *
 *     @EVT|<t>|<type>|<key>=<value>|<key>=<value>|...
 *
 * where <t> is sim-seconds since level start. The Python harness matches the
 * "@EVT|" prefix and ignores every other console line (R4); it owns run_id,
 * wall-clock time, hashing, output paths, and JSON Schema validation. This file
 * owns only sim-time <t> and the per-event payloads.
 *
 * Channel: bprint() — on a dedicated server this reaches the server console
 * (stdout) and needs no `developer` cvar. VERIFY ON FIRST LOCAL RUN that these
 * lines actually appear on fteqw-sv stdout. If capture proves lossy, the
 * documented fallback is FRIK_FILE (fopen/fputs), already used by FrikBot (R4).
 *
 * Cannot be compiled on the droplet (no fteqcc; ~1GB RAM). Build progs.dat
 * locally/CI: `just build-quakec`.
 *
 * Contract: specs/001-headless-sim-telemetry/contracts/engine-event-line.md
 *
 * This-slice scope (US1): level_start (first frame, carries secrets_total per
 * G2) + level_end{completed|timeout}. The gameplay events (kill/death/shot/hit/
 * pickup/secret) and the level_end{died} terminal land in US2 (T024-T028/T025).
 */

// --- state ---------------------------------------------------------------

float telemetry_started;     // one-shot guard: level_start emitted
float telemetry_ended;       // one-shot guard: level_end emitted (terminal)
float telemetry_origin;      // sim-time origin (seconds); t = time - origin
float sim_autostart_done;    // one-shot guard for the BotFrame autostart shim (R2)

// US2 shot/hit accumulator: W_Attack opens a per-trigger-pull window; T_Damage
// sums the agent's *outgoing* applied damage into it; W_Attack flushes it as
// exactly one `hit`, keeping shots_hit <= shots_fired (T026, G1).
float tel_attack_active;     // inside an agent's W_Attack this frame
float tel_shot_damage;       // applied damage accumulated this trigger-pull
string tel_shot_target;      // classname of the last entity damaged this pull

// --- line builders -------------------------------------------------------
// bprint takes one string per call in this codebase; we build a line with a
// run of calls and terminate it with Tel_End. QuakeC is single-threaded within
// a frame, so the line is never interleaved with another @EVT line.

void(string etype) Tel_Begin =
{
	bprint("@EVT|");
	bprint(ftos(time - telemetry_origin));
	bprint("|");
	bprint(etype);
	bprint("|");
};

void() Tel_End =
{
	bprint("\n");
};

void(string k, string v) Tel_Str =
{
	bprint(k);
	bprint("=");
	bprint(v);
	bprint("|");
};

void(string k, float v) Tel_Num =
{
	bprint(k);
	bprint("=");
	bprint(ftos(v));
	bprint("|");
};

// --- events --------------------------------------------------------------

// First event of the run. Emitted on the first server frame (NOT worldspawn) so
// that total_secrets — accumulated as trigger_secret entities spawn — is final
// by the time we read it (G2). map = BSP stem (mapname); seed from sim_seed.
void() Tel_LevelStart =
{
	telemetry_origin = time;
	telemetry_started = TRUE;
	Tel_Begin("level_start");
	Tel_Str("map", mapname);
	Tel_Num("seed", cvar("sim_seed"));
	Tel_Num("secrets_total", total_secrets);
	Tel_End();
};

// Terminal event. outcome in completed|died|timeout; time_sec = sim-time.
// One-shot: the first terminal wins (a clean completed must not be overwritten
// by a later timeout, etc.).
void(string outcome) Tel_LevelEnd =
{
	if (telemetry_ended)
		return;
	telemetry_ended = TRUE;
	Tel_Begin("level_end");
	Tel_Str("outcome", outcome);
	Tel_Num("time_sec", time - telemetry_origin);
	Tel_End();
};

// --- per-frame hook ------------------------------------------------------

// Called at the top of StartFrame(). On the first frame it emits level_start
// (once total_secrets is known); thereafter it enforces the in-engine session
// cap -> timeout (FR-003). The harness wall-clock watchdog is the backstop.
void() Tel_Frame =
{
	local float limit;

	if (!cvar("sim_mode"))
		return;

	if (!telemetry_started)
		Tel_LevelStart();

	limit = cvar("sim_time_limit");
	if (limit > 0 && !telemetry_ended && (time - telemetry_origin) >= limit)
	{
		Tel_LevelEnd("timeout");
		localcmd("quit\n");   // clean shutdown; harness watchdog backs this up
	}
};

// --- US2 gameplay events (T024-T028) -------------------------------------
// All gated to sim runs and attributed to the agent: in a headless sim the only
// FL_CLIENT entity is the autostarted bot, so "is the agent" == "is a client".

float(entity e) Tel_IsAgent =
{
	// Gate every gameplay emit: only during sims, only the agent (the sole client
	// in a headless run), and NEVER after the terminal level_end — otherwise a
	// gameplay event later in the final frame (before `quit` takes effect) lands
	// after level_end and breaks the first/last stream invariant (US2 sc.1).
	return cvar("sim_mode") && !telemetry_ended && (e.flags & FL_CLIENT);
};

// IT_* weapon flag -> contract weapon stem (engine-event-line.md / FR-011).
string(float w) Tel_WeaponStem =
{
	if (w == IT_AXE) return "axe";
	if (w == IT_SHOTGUN) return "shotgun";
	if (w == IT_SUPER_SHOTGUN) return "super_shotgun";
	if (w == IT_NAILGUN) return "nailgun";
	if (w == IT_SUPER_NAILGUN) return "super_nailgun";
	if (w == IT_GRENADE_LAUNCHER) return "grenade_launcher";
	if (w == IT_ROCKET_LAUNCHER) return "rocket_launcher";
	if (w == IT_LIGHTNING) return "lightning";
	return "unknown";
};

// kill: a monster the agent killed (T024). distance = agent->victim range.
void(entity victim, entity killer) Tel_Kill =
{
	Tel_Begin("kill");
	Tel_Str("victim", victim.classname);
	Tel_Str("weapon", Tel_WeaponStem(killer.weapon));
	Tel_Num("distance", vlen(victim.origin - killer.origin));
	Tel_End();
};

// death: the agent died (T025); cause/killer drive deaths_by_cause.
void(entity attacker) Tel_Death =
{
	local string who;
	who = attacker.classname;
	if (attacker == world || who == "")
		who = "world";
	Tel_Begin("death");
	Tel_Str("cause", who);
	Tel_Str("killer", who);
	Tel_End();
};

// shot: one per agent trigger-pull (T026). target is null at fire time; the hit
// carries the actual target.
void(entity agent) Tel_Shot =
{
	Tel_Begin("shot");
	Tel_Str("weapon", Tel_WeaponStem(agent.weapon));
	Tel_Str("target", "null");
	Tel_End();
};

// hit: one per trigger-pull that connected; damage is the window total (T026).
void(entity agent, string target, float damage) Tel_Hit =
{
	Tel_Begin("hit");
	Tel_Str("weapon", Tel_WeaponStem(agent.weapon));
	Tel_Str("target", target);
	Tel_Num("damage", damage);
	Tel_End();
};

// pickup: an item the agent collected (T027). value is type-specific amount.
void(entity item, entity taker, float value) Tel_Pickup =
{
	if (!Tel_IsAgent(taker))
		return;
	Tel_Begin("pickup");
	Tel_Str("item", item.classname);
	Tel_Num("value", value);
	Tel_End();
};

// secret: the agent triggered a trigger_secret (T028); id = running found count.
void(float secret_id) Tel_Secret =
{
	Tel_Begin("secret");
	Tel_Num("secret_id", secret_id);
	Tel_End();
};
