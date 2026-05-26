# idledoom Constitution
<!-- Working title; the project name is still TBD (see docs/design.md). -->

Canonical statement of the project's non-negotiable principles. Seeded from the
design pillars and conventions in `CLAUDE.md` and the vision in
`docs/design.md`; those remain the day-to-day agent guide and the living design,
and must stay consistent with this document. Where they conflict, this
constitution wins for the principles below.

## Core Principles

### I. Visible Progression (NON-NEGOTIABLE)
Every player-facing upgrade must produce an observable change in play within
~1–2 minutes. No invisible micro-stats (e.g. "+0.3%"). If a change cannot be
seen by watching the agent, it is not shipped as a player-facing upgrade.

### II. Behavior Configuration Is the Gameplay
The player never controls the agent moment-to-moment; all agency comes from
*configuring how it thinks* — playstyle profiles, targeting, movement, and
ability triggers. A full player-facing rule engine (condition→action) is
**deferred**: ship curated settings/presets first, build the rule engine later
(see `docs/design.md` §9).

### III. Low-Poly PS1 Authenticity
Movement, weapons, and pacing must read as a classic late-'90s low-poly FPS —
fast and weighty — with a consistent PS1-era look (low-poly models, low-res
textures). It is a low-poly, PS1-era FPS, not a sprite-based or modern shooter.

### IV. Original/Libre, No id IP (NON-NEGOTIABLE)
The project is GPLv2 and libre throughout. Building on id Software's GPLv2
*code* (FTEQW, the rerelease QuakeC) is fine; shipping id's *content* or brand
is not — never include id assets, original id maps, id monsters, or the "Quake"
name/trademark. Use original/libre content only. If an asset's license is
unclear, it does not ship. Every shipped asset is logged in `docs/licenses.md`.

### V. Small, Testable, Observable Changes
Prefer small changes; "does it feel right" is a real metric that requires
running the game. For tuning questions, run a simulation (`just sim`) rather
than guessing. Every new bot stat gets sim-harness coverage so it can be tuned.

## Technical & Operational Constraints

- **Stack (per ADRs):** FTEQW engine (GPLv2, git submodule under `engine/`,
  pinned by commit), FrikBot-derived QuakeC gamecode in `quakec/` (`progs.dat`),
  Tauri host app, SQLite save state, cvar + watched-file IPC.
- **Engine discipline:** minimize engine-C patches; prefer cvar/cmd exposure.
  Every engine patch — and every engine-submodule bump — requires an ADR.
- **Documentation of tunables:** bot stats are catalogued in `docs/bot-stats.md`;
  player-facing upgrades in `docs/progression.md`; asset provenance in
  `docs/licenses.md`.
- **Shared droplet (1 GB RAM):** for editing, git, lightweight scripting, and
  headless sim batches only. Never compile the engine, fteqcc, or the host app
  on it — it OOMs; build locally. Any Python runs through a `uv`-managed venv.

## Development Workflow & Quality Gates

- `main` is buildable at all times; CI must pass.
- Feature branches `feat/<short-name>`; **every PR is reviewed by the other dev**
  before merge, even on a two-person team. Commit messages are imperative and
  cite ADR numbers when relevant.
- Architectural decisions are recorded as ADRs in `docs/adr/`. Unresolved design
  calls go into `docs/design.md` "Open Questions" rather than being decided
  unilaterally.
- **Spec-driven flow (Spec Kit):** `/speckit-constitution` →
  `/speckit-specify` → `/speckit-clarify` (optional) → `/speckit-plan` →
  `/speckit-tasks` → `/speckit-analyze` (optional) → `/speckit-implement`.
  Specs and plans must draw on `docs/design.md`, `docs/adr/`,
  `docs/bot-stats.md`, and `docs/progression.md`. Per-feature artifacts live
  under `specs/`.

## Governance

This constitution supersedes ad-hoc practice for the principles it states.
Amendments require both developers' sign-off (via the normal PR review),
a version bump below, and a dated note. `/speckit-plan` and `/speckit-analyze`
should check proposed work against these principles; `CLAUDE.md` remains the
runtime agent guide and `docs/design.md` the living design vision.

**Version**: 1.0.0 | **Ratified**: 2026-05-26 | **Last Amended**: 2026-05-26
