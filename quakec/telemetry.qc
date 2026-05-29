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
