# Design Document

Living document. Edit freely. When a section stabilizes, consider extracting
its decisions into an ADR.

> Provenance: incorporates ideas from the early design brainstorm (Google Doc,
> May 2026). That draft centered on a full player-facing rule engine; we keep
> the behavior-configuration *spirit* but **defer the rule engine itself**
> (see §9).

## 1. Vision

You watch a friend get better at a low-poly, PS1-era FPS. An AI agent
plays original libre levels autonomously — moving, fighting, looting — and you
improve it not by controlling it, but by shaping how it thinks and what it
carries. Each run you observe, diagnose, and adjust; the next run is faster,
smarter, more capable. The soul of the game is **behavior configuration**:
turning a clumsy bot into a kiting, headshot-hunting, secret-sniffing menace and
feeling like that competence is *yours*.

This is deliberately an original low-poly, PS1-era FPS. We want the late-'90s
look and feel (low-poly models, low-res affine-warped textures, chunky lighting,
crunchy audio), built on a libre engine with original/libre content. We do **not** ship
or depend on id Software's assets, maps, monsters, or the "Quake" name/trademark
(see §9 and `docs/licenses.md`).

## 2. Core experience

### The loop

**Observe → Diagnose → Adjust → Re-run.**

1. Deploy the agent into a level (or auto-repeat the current one)
2. It moves, acquires targets, fires, uses abilities
3. You earn currency and drops (mods, weapons, upgrades)
4. You return to the loadout/behavior panel and tune
5. Re-run — clears get faster and cleaner

### The two panels

- **Left (engine viewport):** live view of the agent playing. Real engine, real
  physics, real movement — the low-poly FPS feel must read as skillful play.
- **Right (config/upgrade panel):** loadout, behavior settings, upgrades,
  currency, run history, telemetry, unlocks. All player agency lives here.

[Sketch the layout in ASCII or link to mockups.]

### Player agency without direct control

The player never inputs moment-to-moment actions; all agency comes from
*configuration*, across three pillars:

1. **Loadout design** — weapons, mods, abilities
2. **Behavior configuration** — targeting, movement, ability triggers (the core — §3)
3. **Strategic progression** — better automation, scaling efficiency, specialization

### Idle vs active

Current lean (from the early draft) is **pure idle**: the agent runs
autonomously and the panel rewards active attention, but nothing is lost by
stepping away. Still open: true offline progression vs progresses-only-while-
open — implications for the sim engine, save format, and fairness. [Resolve;
tracked in §11.]

### Session arc

- **Minute 0–5:** crude agent auto-fires and wanders; first upgrades land fast (30–90s apart)
- **Minute 5–30:** first behavior settings unlock; weapon identity begins to show
- **Hour 1–5:** multiple behavior slots, movement behaviors, early specialization
- **Day 1+:** longer-tail capability unlocks; offline accrual if we go that way

[Tighten with real numbers once we can sim.]

## 3. The agent (core)

### Behavior configuration — the heart of the game

You shape *how the agent thinks*, not what it does each frame. For now this is
exposed as tunable settings and presets — **not** free-form scripting (that is
the deferred rule engine, §9):

- **Playstyle / behavior profiles** — high-level personalities that bias
  everything: risk-taker, map completionist, "no drop left behind,"
  secret-hunter (checks walls for secrets), aggressive dopamine-chaser,
  methodical defensive. Choosing a profile sets sensible defaults you then
  fine-tune.
- **Targeting preferences** — prefer headshots, focus lowest-HP, prioritize
  elites/shielded, nearest vs most-dangerous.
- **Movement logic** — kiting radius (maintain distance), aggressive push vs
  defensive retreat, seek cover vs ignore cover, patrol/clear vs beeline-to-exit.
- **Engagement positioning** — hold optimal weapon range, avoid getting
  surrounded, use flanking routes (later unlock).
- **Ability triggers** — threshold-driven: "shield under 30% HP," "grenade when
  ≥5 enemies," "slow-time when an elite appears" (§4).

Design rule: tuning must be **intuitive but deep**, and every change must show a
visible cause→effect on the next run (§3 visible progression, §10 risks).

### Behavioral model

Stat-driven + config-driven, on a FrikBot-derived baseline
(`docs/bot-stats.md`, ADR-0001). Stats are cvars readable by gamecode and
writable from the host. The agent's decisions should be **legible** — a viewer
can read intention into them.

### Tunable parameters (see `bot-stats.md`)

- **Mechanical skill:** accuracy, reaction time, tracking, prediction
- **Perception / awareness:** detection range, threat assessment, line-of-sight use
- **Movement:** speed, strafing, rocket-jump, bunny-hop (original/libre FPS movement tech)
- **Knowledge:** map awareness, secret locations, item/spawn timing, pickup priority
- **Decision-making:** aggression, retreat threshold, target selection, resource mgmt
- **Combat:** weapon affinity per enemy type, ammo management, splash awareness

### Visible progression

Every upgrade produces an observable change within 1–2 minutes of play. No
invisible +0.3% stats. Good: "now it rocket-jumps to the megahealth." Bad:
"+2% reload speed with no visible tell."

### "FPS feel" without input

Even hands-off, it must *look* like a skilled player: smooth target snapping,
recoil settling over a burst, clean kiting/strafing, well-timed abilities. Nail
this and players read their own intent into the system they built. This is a
presentation requirement, not just an AI one.

### Navigation & traversal (a first-class progression axis)

How the agent *gets around* a level — pathing, door/lift use, jumps, shortcuts,
secret routes — is part of its skill and **improves over progression** just like
accuracy or targeting. Early on it may path crudely (backtrack, stall at a ledge,
miss an obvious shortcut). Because this is an idle game, that clumsiness is
**acceptable — even charming**; watching it smooth out *is* the "friend getting
better" fantasy. So navigation upgrades must be as legible as combat ones ("now
it takes the lift instead of circling," "now it routes through the secret").

**Navigation must be automatic.** We are heading toward **procedurally generated
maps** (§6), so hand-authored waypoints are a non-starter as the shipping
solution — the agent has to handle maps no human ever waypointed. The nav data
(graph or mesh) must be *generated*, not hand-placed.

- **Mechanism (decided — ADR-0003):** generate the nav graph **in QuakeC** on
  FrikBot's `DynamicWaypoint` — a frontier-seeking roam lays waypoints down as the
  agent explores, and the graph auto-saves to `maps/<map>.way` for reuse (a
  BSP-derived nav-mesh was the considered alternative, deferred to engine-C work).
  See `specs/002-auto-navigation/` (feature 002).
- **Legacy fallback only:** FrikBot waypoints recorded by hand into a `.way`
  (`docs/waypointing.md`). This was bootstrap scaffolding (SC-004) and is now
  **superseded** by the automatic process — kept only for one-off manual debugging.
- **Competence is a tunable:** `bot_map_awareness` scales exploration thoroughness
  and route directness (more `map_coverage` / faster routing), a progression axis
  under the visible-progression rule. Stuck-recovery keeps idle runs softlock-free.
- **Target:** generation runs at map-gen/load time so procedural maps just work.

The *direction* — automatic, progression-scaled, idle-tolerant — and now the
*mechanism* (QuakeC `DynamicWaypoint`, ADR-0003) are decided.

## 4. Weapons, abilities, enemies

### Weapons as behavior (behavior > stats)

Weapons shouldn't only scale numbers — they should change *how* the agent
fights.

- **Core stats:** damage, fire rate, accuracy/spread, reload, range, plus how a
  weapon shifts perception and per-enemy weapon choice.
- **Behavioral modifiers:** target-preference shifts ("prefer headshots"),
  firing patterns (burst vs sustained, charge shots), projectile behavior
  (hitscan → projectile → tracking → chaining).
- **Evolution examples:** SMG → perfect tracking beam; shotgun → cone-clearing
  wave; sniper → auto-headshot chain. Upgrades change *identity*, not just output.

### Abilities (strategic overrides)

The main expression layer beyond weapons. Categories: **AOE clearing**
(grenades, explosions), **control** (slow, stun, freeze), **survivability**
(shield, regen), **utility** (loot boost, radar, aggro manipulation). Principle:
abilities solve problems the baseline AI can't — swarms → AOE, snipers → shield
timing, fast enemies → slow field.

### Enemies (force build decisions)

Enemies exist to break naive automation; all original/libre designs (not id
monsters):

- **Archetypes:** swarmers (punish single-target), tanks (punish burst), snipers
  (punish bad positioning), rushers (punish no-kiting), shielded (require
  angle/priority logic).
- **Advanced traits:** line-of-sight abuse, weak points (reward headshot builds),
  on-death effects (force spacing logic).

### Maps must justify positioning

Movement/positioning only matter if levels demand them: chokepoints vs open
arenas, vertical layers, cover objects, multi-path routes. Otherwise movement
behavior is decoration.

## 5. Progression and economy

See `progression.md` for the tree. Philosophy: progression should feel like
**"my system is getting smarter, not just stronger."**

### Currency & pacing

[What the agent earns per kill/clear/time, and how it scales.] Early-game rewards
every 30–90s; mid-game minutes; late-game can stretch to hours (with offline
accrual if we go that way).

### Capability growth

- **Early:** very limited behavior settings, basic auto-fire, crude targeting
- **Mid:** multiple behavior slots, movement behaviors unlock, weapon identities emerge
- **Late:** stacked behaviors, specialized builds, near-perfect efficiency

### Prestige / reset loops

Resets unlock **capability, not multipliers** — additional behavior slots, new
condition/trigger types (e.g. enemy-type detection), advanced targeting
(predictive, multi-target), new weapon archetypes. Keeps the game off a pure
stat-treadmill. (When the rule engine lands, prestige is the natural place to
hand out rule slots.)

## 6. Content progression

### Maps

Original/libre levels with a PS1 aesthetic — LibreQuake-derived or hand-made;
curated libre community maps later if licensing checks out (`docs/licenses.md`).
[Difficulty curve, gating criteria.]

**Procedurally generated maps are a planned direction** — generated levels for
effectively endless content. This is the hard reason navigation must be automatic
(§3): the agent must path maps no human waypointed. Map generation must therefore
emit (or pair with) whatever the nav system consumes.

### Weapons and behaviors

[Unlock order — classic-FPS-flavored but original. Even early weapons should
already express the behavior system, not just raw damage.]

### Episodes / chapters

[A structural arc beyond difficulty progression? Optional.]

## 7. Architecture

See ADRs for individual decisions. Summary:

- Engine: FTEQW + our QuakeC mod (GPLv2; ADR-0001)
- Agent: FrikBot-derived gamecode with cvar-driven stats/behavior
- Host: Tauri (Rust + web frontend) wrapping the engine window (ADR-0002)
- State: SQLite save file; cvars for engine config
- IPC: stdin console commands + watched state file

### Open architectural questions

- Window embedding: native reparenting vs render-to-texture in the host?
- Sim engine: same binary as the game, or a separate headless build?
- Save versioning: evolve the schema without breaking saves?
- **Automatic navigation** (required for procedural maps, §3/§6): `DynamicWaypoint`
  auto-record pass vs nav graph/mesh generated from the BSP vs a learned approach.
  Must expose tunable route quality so nav can scale as a progression axis.
  **Decided in ADR-0003** (QuakeC `DynamicWaypoint` auto-generation; nav-mesh
  deferred); implemented in feature 002 (`specs/002-auto-navigation/`).

## 8. Headless simulation

See `telemetry.md` for the output schema. Use cases: tuning the progression
curve, regression-checking behavior after engine/gamecode changes, and balancing
specific upgrades. Approach (tick acceleration / parallel instances) [resolve].

## 9. Out of scope / deferred

**Deferred (build later — not cut):**

- **Player-facing rule engine** — condition→action blocks with priority ordering
  and expandable slots. This is the eventual full form of behavior configuration
  (§3), and the early draft centered on it. For now we ship behavior config as
  curated settings/presets and add the rule engine once the core loop is proven.
  Rushing it risks the game getting niche/overwhelming fast.

**Out of scope:**

- Anything that ties us to **id IP** — id assets, original id maps, id monsters,
  or the "Quake" name/trademark. We build original/libre content only.
- Multiplayer; player-facing modding; mobile/web ports; voice/narrative content;
  microtransactions of any kind.

## 10. Design risks (what makes this work or fail)

**Works if:** players see clear cause→effect from their changes; behavior tuning
is intuitive but deep; combat visuals reinforce "skillful play."

**Fails if:** it devolves into a pure stat treadmill; AI decisions feel opaque or
random; movement/positioning doesn't matter.

## 11. Open questions

(Mirror of `CLAUDE.md`; resolve here, then update both.)

- Idle pacing: true offline progression vs active-watch only? (early lean: pure idle)
- Stat-improvement vs behavior-unlock ratio in progression?
- Automatic-navigation mechanism for procedural maps (see §3/§7). Direction is
  decided (automatic, progression-scaled, idle-tolerant); the generation
  mechanism is open.
- Telemetry event-volume / sampling: log-all for now; revisit sampling only if a
  long run measurably bloats files (`telemetry.md`).
- Engine RNG seeding: does FTEQW expose a settable RNG seed to wire `sim_seed` for
  stronger batch reproducibility? (research R6)
- How much behavior config to expose *before* the rule engine exists?
- PS1-aesthetic target: how far to push it (resolution, dithering, affine warp, palette)?
- Save format versioning; host↔engine binary discovery; sim approach; frontend
  framework; window embedding (see §7 and `CLAUDE.md`).
- Working title — needs to evoke a low-poly PS1-era FPS without inviting id trouble (TBD).

## 12. Glossary

- **Agent / bot:** the AI player visible in the left viewport
- **Run:** one instance of the agent playing a level start-to-finish
- **Stat:** a numeric tunable parameter on the agent
- **Behavior profile / playstyle:** a high-level personality preset biasing targeting/movement/abilities
- **Behavior configuration:** the core system of shaping the agent's decisions via settings (and, later, the rule engine)
- **Rule engine (deferred):** future condition→action scripting for agent behavior
- **Ability:** an activatable strategic override (AOE, control, survivability, utility)
- **Cvar:** engine console variable; how we pass config into the running game
- **QuakeC:** the scripting language compiled into `progs.dat`
- **Waypoint / nav graph:** navigation data the agent follows to traverse a map;
  hand-recorded today (temporary, `docs/waypointing.md`), automatically generated
  in the target design (§3)
- **Navigation competence:** how well the agent paths/traverses a level; a
  progression axis that scales with upgrades (§3)
