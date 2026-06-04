# Progression and Economy

The upgrade tree, currency design, and pacing curve. This is the meta-game.

## Currency

**Working name:** Frags (placeholder — pick something thematic)

### Sources

- Kills (small, frequent)
- Level completion (medium, gated by run length)
- Secrets found (medium, encourages exploration upgrades)
- Time spent playing (small idle trickle to ensure offline progression
  feels rewarding, if we adopt offline progression)

### Scaling

[TBD — needs sim data. Initial guess: linear early, slightly sub-linear
late to extend mid-game. Avoid exponential to prevent late-game grinds.]

## Upgrade categories

Mirrors the bot stats taxonomy. See `bot-stats.md` for the underlying
parameters.

### 1. Aim and Reflexes

Improves the bot's mechanical skill. Most visible early-game.

- **Steady Hands I–V:** raises `bot_accuracy`
- **Quick Eyes I–V:** lowers `bot_reaction_ms`
- **Smooth Tracking I–V:** raises `bot_tracking_skill`
- **Lead Targets:** unlocks projectile prediction
- **Master Marksman:** late-game cap that takes all aim stats near maximum

### 2. Movement

Most dramatically visible category. Each unlock changes how the bot looks
on screen.

- **Sure Feet:** baseline strafe-while-firing
- **Quick Step I–V:** raises strafe skill incrementally
- **Rocket Jump (unlock):** bot starts using rocket jumps for shortcuts
- **Bunny Hop (unlock):** bot maintains speed across jumps
- **Circle Strafe Mastery:** late-game movement polish

### 3. Knowledge

Improves bot pathing and decision-making within a level.

- **Map Sense I–V:** raises `bot_map_awareness` (WIRED, feature 002); bot explores
  more of the level and takes more direct routes — visibly more `map_coverage` per run
- **Secret Seeker I–V:** raises `bot_secret_knowledge`; finds hidden areas
- **Item Timer (unlock):** bot starts tracking item respawns
- **Loadout Logic I–V:** raises weapon priority skill

### 4. Combat IQ

Higher-level combat decisions.

- **Aggression Tuning:** player slider, not an upgrade per se — pick a
  playstyle
- **Threat Assessment I–V:** raises target priority skill
- **Splash Awareness I–V:** raises splash awareness
- **Resource Discipline I–V:** raises resource management

### 5. Weapon Mastery

Per-weapon affinity unlocks and improvements. A classic low-poly-FPS weapon
order suggested (original analogues, not id's named weapons):

1. Axe (always available)
2. Shotgun (always available)
3. Super Shotgun (early unlock)
4. Nailgun (early unlock)
5. Super Nailgun (mid)
6. Grenade Launcher (mid)
7. Rocket Launcher (mid; gates rocket jumping)
8. Thunderbolt (late)

Each has an unlock node and 3-5 mastery tiers.

### 6. Maps and Content

Progression through content. See "Content gating" below.

## Pacing

### First session (target: 30-60 minutes)

Player should buy 8-15 upgrades. Every 2-5 minutes of watching, something
new. Early upgrades cheap; first unlock (Super Shotgun or Sure Feet)
should land within ~10 minutes.

### First week (target: 5-15 hours total play)

Most stat-only upgrades maxed in their early tiers. All weapons unlocked.
First rocket jump moment — a memorable milestone. Map progression past
LibreQuake episode 1.

### Long tail (weeks+)

Late tiers of stat upgrades; weapon mastery max levels; harder community
maps; prestige loop (if we adopt one).

## Content gating

### Map progression

| Tier | Maps | Unlock condition |
|------|------|------------------|
| Tutorial | LibreQuake e1m1-style | from start |
| Episode 1 | LibreQuake remainder of episode 1 | finish tutorial |
| Episode 2 | LibreQuake episode 2 | finish episode 1 + threshold currency |
| Curated easy | hand-picked Quaddicted maps | finish LibreQuake |
| Curated medium | harder picks | progression past easy curation |
| Curated hard | "you've made it" tier | endgame |

[Specific map selection TBD; see `assets/maps/` and `licenses.md`.]

### Behavior gates

Some behaviors are gated by progression rather than purchasable directly:

- Rocket jumping requires: Rocket Launcher mastery III + Movement tree progress
- Speedrunning routes require: Map Sense V + Bunny Hop
- Hard difficulty maps require: aggregate stat threshold

## Offline progression

[Open question; resolve in `design.md` first. If yes:]

- Cap offline accumulation to N hours
- Diminishing returns past M hours
- Always-online sessions earn 1.5x to encourage active play

## Prestige

[Open question. Common idle game pattern: full reset for a permanent
multiplier. Could fit thematically as "the bot graduates and a new friend
starts." Decide after first playable build.]

## Open questions

- Currency name and theme
- Exact cost curves (sim-driven; defer until sim harness exists)
- Whether map progression is linear or branching
- Whether to surface "milestone moments" explicitly (first rocket jump,
  first 100% secrets) with UI fanfare
- Prestige system shape and whether to include it at all
