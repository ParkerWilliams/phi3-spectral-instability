# Design Document

Living document. Edit freely. When a section stabilizes, consider extracting
its decisions into an ADR.

## 1. Vision

[Replace with your elevator pitch — refined version of "idle game where you
watch your friend get better at Quake." Aim for 3-5 sentences that another
dev could read and immediately understand the soul of the project.]

## 2. Core experience

### The two panels

- **Left (engine viewport):** Live view of the bot playing Quake. Real
  engine, real maps, real movement. No HUD changes from vanilla Quake unless
  needed.
- **Right (upgrade panel):** Categorized upgrades, currency display, run
  history, telemetry, unlocks.

[Sketch the layout here in ASCII or link to mockups.]

### The session arc

What does a 5-minute session look like? A 1-hour session? A 1-week
progression curve?

- **Minute 0-5:** [bot does X, player buys Y]
- **Minute 5-30:** [...]
- **Hour 1-5:** [...]
- **Day 1+:** [...]

### Idle vs active

[Resolve: true offline progression, or only progresses while window is open?
Implications for sim engine, save format, fairness.]

## 3. The bot

### Behavioral model

[How does the bot decide what to do? FrikBot baseline plus our modifications.
Stat-driven (accuracy, reaction time, awareness) vs script-driven
(rocket-jump, secret knowledge) vs goal-driven (find exit, kill all,
explore).]

### Tunable parameters

See `bot-stats.md` for the catalog. Summary of dimensions:

- **Mechanical skill:** accuracy, reaction time, tracking, prediction
- **Movement:** speed, strafe jumping, rocket jumping, bunny hopping
- **Knowledge:** map awareness, secret locations, weapon spawn timing,
  item priority
- **Decision-making:** aggression, retreat threshold, target selection,
  resource management
- **Combat:** weapon affinity, ammo management, splash damage awareness

### Visible progression

Design constraint: every upgrade should produce an observable change within
1-2 minutes of play.

[How do we ensure this? Examples of good vs bad upgrades.]

## 4. Progression and economy

See `progression.md` for the full upgrade tree. This section covers
philosophy and pacing.

### Currency

[What does the bot earn? How much per minute, per kill, per level
completion? How does currency scale with progression?]

### Upgrade pacing

[How long between purchases at each stage? Early-game should reward every
30-90 seconds; mid-game several minutes; late-game can stretch to hours
with offline accumulation if applicable.]

### Prestige / reset loops

[Is there a reset mechanic that grants permanent buffs? Common in idle
games, optional here.]

## 5. Content progression

### Maps

LibreQuake base maps first. Then curated Quaddicted content. Then any
custom levels we make.

[Order? Difficulty curve? Gating criteria?]

### Weapons and behaviors

[Order in which the bot gains access to and competence with weapons.
Vanilla Quake order? Different?]

### Episodes / chapters

[Does the game have a narrative or structural arc beyond difficulty
progression?]

## 6. Architecture

See ADRs for individual decisions. Summary:

- Engine: FTEQW with our QuakeC mod
- Bot: FrikBot fork with cvar-driven stats
- Host: Tauri (Rust + web frontend) wrapping the engine window
- State: SQLite save file; cvars for engine config
- IPC: stdin console commands + watched state file

### Open architectural questions

[Track here until resolved into ADRs.]

- Window embedding: native reparenting vs texture-based render-to-host?
- Sim engine: same binary as game, or a separate headless build?
- Save versioning: how do we evolve the schema without breaking saves?

## 7. Headless simulation

See `telemetry.md` for the output schema.

### Use cases

- Tuning: "given this upgrade tree, does the progression curve feel right?"
- Regression: "did this engine patch change bot behavior unexpectedly?"
- Balance: "is the rocket launcher upgrade too strong?"

### Approach

[Tick acceleration, parallel instances, or both. Resolve and document.]

## 8. Out of scope (for now)

Listing what we're explicitly not doing is as valuable as listing what we
are.

- Multiplayer
- Modding support for players
- Mobile / web ports
- Original maps (initially)
- Voice / narrative content
- Microtransactions of any kind

## 9. Open questions

(Mirror of `CLAUDE.md` open questions. Resolve here, then update both.)

- [List active questions with brief context]

## 10. Glossary

- **Bot:** the AI player visible in the left viewport
- **Run:** one instance of the bot playing a level start-to-finish
- **Stat:** a numeric tunable parameter on the bot
- **Behavior:** an unlockable capability (rocket-jump, secret-finding)
- **Cvar:** Quake engine console variable; how we pass config in
- **QuakeC:** the scripting language compiled into `progs.dat`
- [Add terms as they emerge]
