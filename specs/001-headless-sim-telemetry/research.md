# Phase 0 Research: Headless Simulation Run with Telemetry

All open questions raised by the spec and the codebase are resolved below. Each
entry is **Decision / Rationale / Alternatives considered**. None remain marked
NEEDS CLARIFICATION; genuinely deferred design calls are recorded as bounded
open questions at the end and mirrored into `docs/design.md` §8 / §11 rather than
decided unilaterally.

---

## R1 — Headless execution: which engine binary, what invocation

**Decision.** Use the FTEQW **dedicated server** build, target `sv-rel`
(`make -C engine/engine sv-rel` → `engine/engine/fteqw-sv<target>`). The Makefile
ships `vid_headless.o` and an explicit dedicated path documented as "run it as a
console program," exactly the headless mode ADR-0001 promised. Launch shape:

```
fteqw-sv -basedir <repo> -game <moddir> \
  +set sv_cheats 1 +set deathmatch 0 +set skill <n> \
  +set sim_mode 1 +set sim_seed <seed> +set sim_time_limit <sec> \
  +set bot_accuracy <v> +set bot_reaction_ms <v> ... \
  +map <librequake-map>
```

The harness owns the process: it streams stdout, and a **wall-clock watchdog**
kills the server if the in-engine `sim_time_limit` fails to end the run.

**Rationale.** Zero engine-C patches (constitution). The dedicated server has no
window/GPU/audio, runs StartFrame (so `BotFrame()` ticks), and loads `progs.dat`
+ map like the client. It is also the build the droplet can *run* for batches.

**Alternatives.** (a) GL client (`gl-rel`) in a hidden window / Xvfb — needs a
display, heavier, off-target for CI/droplet. (b) A bespoke headless build flag —
unnecessary; `sv-rel` already is it. Both rejected.

**Build/Justfile impact.** `build-engine` currently builds only `gl-rel`. Add the
dedicated build to the sim path: `build-sim` should produce `fteqw-sv` (locally
or in CI — never on the droplet). The harness locates the binary by env override
then well-known path.

---

## R2 — Bot autostart with no human client (the autonomy mechanism)

**Decision.** Add a small **server-side autostart shim** in `BotFrame()`
(`quakec/frikbot/bot.qc`, already called from `StartFrame()` per INTEGRATION.md):
when `cvar("sim_mode")` is set and no agent has spawned yet, call
`BotConnect(0, 0, <skill>)` directly (the same entry FrikBot's impulse-100 path
uses), once. The shim flips a guard so it fires exactly once per level.

**Rationale.** FrikBot bots are normally added by a *connected client's* impulse
100 → `BotConnect(...)` (`bot.qc:1243`). A dedicated server with no human has no
such client. `BotConnect(team, botnum, skill)` (`bot.qc:945`) is plain
server-side gamecode and works without a client; invoking it from the per-frame
server hook is the minimal, in-engine way to get an autonomous agent. No engine
patch, no fake-client console plumbing.

**Alternatives.** (a) `stuffcmd`/autoexec to fake an impulse — requires a client
to receive it; none exists. (b) Engine-side `addbot` command — would be an
engine-C patch (needs an ADR) and FrikBot doesn't register one. Both rejected.

---

## R3 — Navigation & termination on a LibreQuake map (no FrikBot waypoints)

**Decision.** For v1, rely on FrikBot's **waypoint-less roaming**
(`frik_bot_roam`, `bot_move.qc:478`, reached from `bot_ai.qc:948`): the agent
wanders, fights, and picks up items without a waypoint graph. **Reaching the exit
is NOT required** — `timeout` is a first-class, valid outcome (FR-003, edge
cases, SC acceptance). The slice's bar is *autonomous + configurable + conforming
telemetry*, not level completion.

**Stretch (decision-gated, not in the critical path).** Optionally hand-author a
waypoint file `quakec/waypoints/map_<lqmap>.qc` (via FrikBot's in-game editor) to
enable `completed` outcomes and richer paths. Recommended once the pipeline is
green, but explicitly **out of the MVP** so the deliverable doesn't hinge on
waypoint authoring.

**Rationale.** FrikBot only ships waypoints for **id1 dm1–dm6** — which are id
maps we must not use (Principle IV). Authoring waypoints for the libre map is
real work with a feedback loop (load, edit, save, retest) that the headless slice
shouldn't block on. Roaming already exercises movement/combat/pickup and produces
valid telemetry for every terminal outcome.

**Alternatives.** (a) Block the slice on authored waypoints — couples the data
foundation to map-specific authoring; rejected for MVP. (b) Port an id1 waypoint
file — violates Principle IV; rejected. **This is the biggest behavioral risk**
and is logged as an open question (below).

---

## R4 — Telemetry emission channel: QuakeC stdout lines vs direct file writes

**Decision.** QuakeC emits **compact tagged event lines to stdout/console** (one
per observable event, e.g. a `@EVT` prefix + sim-time `t` + key=value payload —
see `contracts/engine-event-line.md`). The **harness captures stdout**,
translates lines into per-event JSONL records and the aggregated summary, and
writes both files. QuakeC owns only sim-time `t` and event payloads; the harness
owns identity, wall-clock timing, hashing, paths, validation, and exit codes.

**Rationale.** UUID `run_id`, `sha256` `config_hash`, ISO-8601 `started_at`/
`ended_at`, `duration_sec`, clamping against documented ranges, JSON Schema
validation, non-colliding output paths, and exit-status semantics are all trivial
in Python and painful in QuakeC. Keeping them harness-side also makes the summary
the single reconciliation point (SC-003) and keeps engine-C untouched. It matches
the existing `sims/harness.py` design already in the Justfile.

**Alternatives.** (a) QuakeC writes JSON/JSONL directly via FRIK_FILE builtins
(`fopen`/`fputs`) — FrikBot already uses these for waypoints, so it's feasible,
but it pushes UUID/hash/ISO-time/validation/path-control into QuakeC and is
sandboxed to the gamedir. Rejected as the *primary* path; the builtins remain a
fallback if stdout proves lossy. (b) A shared state file polled by both — more
moving parts than a captured stdout stream. Rejected.

**Robustness.** Lines are newline-delimited and self-contained; the harness
tolerates interleaved engine log noise by matching the `@EVT` prefix, and treats
a missing terminal `level_end` as a non-clean run (→ partial/interrupted, never
`completed`; edge case + FR-010).

---

## R5 — `bot_*` → behavior wiring scope, clamping, and `config_hash`

**Decision.**
- **Clamp + record everything.** The harness mirrors the ranges/defaults in
  `docs/bot-stats.md` (`idledoom_sim/botstats.py`), clamps each supplied `bot_*`
  value to its documented range **before** setting the cvar, and records the
  **clamped** values in `bot_config` (FR-008: no silent out-of-range acceptance).
- **`config_hash` = `sha256`** over a canonical (sorted-key, fixed-format) JSON
  serialization of the clamped `bot_config` (FR-007). Identical configs → equal
  hashes; any difference → different hash (US3 scenario 2).
- **Behaviorally wire the minimum to prove SC-004:** at least `bot_accuracy` into
  FrikBot's aim error (`bot_fight.qc`), so higher accuracy yields measurably
  higher `stats.accuracy`. All other catalogued `bot_*` are declared, clamped,
  and recorded this slice; their full behavioral wiring is incremental follow-up
  (each gets sim coverage as it lands — Principle V). `docs/bot-stats.md` will
  note which are *wired* vs *recorded-only* for this slice.

**Rationale.** SC-004 needs at least one parameter whose change is visible in
telemetry; accuracy is the most direct and least navigation-dependent. Recording
all `bot_*` keeps every result tied to its full inputs even before each knob is
wired, and avoids a partial `bot_config`.

**Alternatives.** (a) Wire all ~16 stats now — large, navigation-coupled, and
beyond the slice's "autonomous + configurable" bar. (b) Clamp inside QuakeC —
QuakeC would need the range table duplicated and couldn't guarantee `bot_config`
matches; harness-side clamp guarantees recorded == used. Both rejected.

---

## R6 — Seed semantics vs. reproducibility

**Decision.** Accept a per-run integer **seed** (`sim_seed` cvar, settable via
config/CLI; FR-016), record it in the `level_start` event payload and carry it
into the summary's identity. Treat it as a **grouping/label + best-effort RNG
seed**, not a determinism contract: if FTEQW exposes an RNG seed we set it;
otherwise the seed is recorded for reproducible *batches*, not byte-identical
replays.

**Rationale.** FR-014 states reproducibility is **statistical, not bit-exact**;
tuning conclusions come from aggregates over many runs. The seed's job is to make
those aggregates reproducible and runs comparable, which recording-and-passing
achieves regardless of engine RNG determinism.

**Alternatives.** Promising bit-exact replay — contradicts FR-014 and would
require deep engine determinism work; rejected.

---

## R7 — Outcome determination (the terminal state machine)

**Decision.** The harness derives `outcome` from the event stream + process exit:

| Condition observed by harness | `outcome` |
|---|---|
| `level_end{outcome:"completed"}` emitted (agent reached the exit / `NextLevel`) | `completed` |
| agent `death` with no continuation, server ends the level | `died` |
| `sim_time_limit` reached (in-engine end) **or** wall-clock watchdog fires | `timeout` |
| engine fails to launch / map missing / `progs.dat` won't load / crash before clean end | `error` (summary if producible) or **no summary + non-zero exit** |

A run is `completed` **only** if the engine ended cleanly *and* a terminal
`level_end{completed}` was seen. A killed/crashed/interrupted run is never
reported as `completed` (FR-010, SC-006); partial output is marked distinctly.

**Rationale.** Directly encodes FR-003 / FR-010 and the edge cases. Anchoring
`completed` to an explicit terminal event (not mere process exit 0) is what
prevents a broken chain from masquerading as success.

**Alternatives.** Inferring outcome purely from exit code — can't distinguish
timeout vs death vs clean completion; rejected.

---

## R8 — Map selection & vendoring (LibreQuake)

**Decision.** Run on the **smallest LibreQuake map** that exercises movement,
combat, item pickup, and (ideally) ≥1 secret, vendored under
`assets/libre-quake/` (submodule per `docs/licenses.md`). The exact map id is
**confirmed at vendor/first-load time** — it must load with our rerelease+FrikBot
`progs.dat` (LibreQuake uses standard Quake entity classnames: `monster_*`,
`item_*`, `trigger_secret`, `info_player_start` — the reason LibreQuake is a
drop-in libre base). Record the chosen map's file/author/license/source in the
`docs/licenses.md` Maps table before it ships (project "adding a map" convention,
FR-015).

**Rationale.** Principle IV forbids id maps; LibreQuake is the sanctioned libre
base. A small first/early level keeps the smoke run under 60 s (SC-005) and gives
enemies + items for reconciliation (SC-003).

**Vendoring constraints.** Vendor **locally**, not on the droplet (1 GB RAM; "no
heavy clones"). Only the assets the chosen map references must resolve; if the
full LibreQuake submodule is too heavy to keep checked out on the droplet, the
batch host consumes a prepared map subset/pak. The droplet runs sims; it does not
clone/build heavy trees.

**Alternatives.** Hand-make a tiny original map — more effort, deferred; broader
Quaddicted curation — out of scope. Both rejected for v1.

---

## R9 — Python toolchain: `uv`, not `pip`/`python`

**Decision.** All harness execution goes through **`uv`** (`uv run`, `uv sync`).
Update the Justfile sim recipes (`build-sim`, `sim`, `sim-smoke`, `check-python`,
`test`) from the current `pip install -r requirements.txt` / `python harness.py`
to the `uv` equivalents, and use `pyproject.toml` instead of `requirements.txt`.

**Rationale.** Constitution: "Any Python runs through a `uv`-managed venv"; the
current Justfile's raw `pip`/`python` predate that and are inconsistent. Aligning
now keeps `just check`/`just test` honest on the droplet and CI.

**Alternatives.** Keep `pip`/`python` — violates the constitution; rejected.

---

## R10 — Single-run now, batch-ready later

**Decision.** Implement exactly **one run per invocation** (`just sim`), but write
outputs to `sims/results/<batch-id>/<run-id>...` with a unique `run_id` per run
and an optional `batch_id` (defaulting to a single-run batch). No aggregation
layer is built.

**Rationale.** FR-009 + FR-014: the unique-path design is the only thing a future
`sim-batch` needs from this slice; building averaging/matrix logic now is out of
scope (Assumptions). Non-colliding paths also satisfy the "two runs started close
together" edge case.

**Alternatives.** Build the batch aggregator now — explicitly deferred; rejected.

---

## Remaining open questions (bounded — mirror to `docs/design.md`)

These are genuine design calls, not blockers; per CLAUDE.md they go to
`docs/design.md` Open Questions rather than being decided here:

1. **Waypoints for the libre map (R3).** Author FrikBot waypoints for the chosen
   map to unlock `completed` outcomes, or accept roam-only (timeout-dominated)
   for v1? *Lean: roam-only MVP, author waypoints as fast-follow.* (design §8)
2. **Event-volume / sampling (telemetry.md open Q).** Log-all is mandated for this
   slice; revisit sampling only when a long run measurably bloats files.
3. **`sim_*` control cvars** (`sim_mode`, `sim_seed`, `sim_time_limit`): confirm
   names + document in `docs/bot-stats.md` notes / the cvar contract; ensure they
   don't collide with FrikBot/engine cvars.
4. **Engine RNG seeding (R6):** verify whether FTEQW exposes a settable RNG seed;
   if so, wire `sim_seed` to it for stronger batch reproducibility.
