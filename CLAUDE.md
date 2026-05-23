# CLAUDE.md

This file gives Claude Code context about the project. Read it before making
non-trivial changes. Update it when architectural decisions change.

## Project: [working title TBD]

An idle game built on a Quake 1 open source engine fork. The player watches
an AI bot play Quake and spends accumulated currency on upgrades that make
the bot faster, more accurate, smarter, and capable of new behaviors
(rocket-jumping, finding secrets, using advanced weapons). The fantasy is
"watching your friend get progressively better at Quake."

### Core loop

1. Bot plays a Quake level autonomously
2. Player watches in the left viewport, browses upgrades in the right panel
3. Player spends currency to improve bot stats or unlock behaviors
4. Bot's next run reflects the upgrades; pace and capability visibly increase
5. Progression unlocks harder maps and new weapon/movement tech

### Design pillars

- **Visible progression.** Every upgrade should be observable in play within
  a minute or two. No invisible +0.3% stats.
- **Authenticity.** This should feel like Quake, not a Quake-themed clone.
  Movement, weapons, level pacing should be recognizable.
- **Hands-off but engaging.** Idle, but the menu side rewards active attention.
- **Open source throughout.** Engine, base assets, maps — all libre or
  permissively licensed.

## Stack

- **Engine:** FTEQW (Quake 1 fork, max scripting power via CSQC/QuakeC)
  - Vendored as a git submodule under `engine/`
  - Pinned to a specific commit; bumped deliberately via ADR
- **Bot:** FrikBot lineage, modified to expose stats as cvars readable from
  game logic and writable from outside the engine
- **Host app:** Tauri (Rust + web frontend) wraps the engine window and
  renders the right-hand upgrade panel
  - Rust backend handles process management, state persistence, IPC
  - Frontend framework: TBD (likely Svelte or React; see open questions)
- **State:** SQLite for save data (player progression, upgrades owned,
  currency, telemetry); cvars for engine-side runtime config
- **IPC:** Engine stdin for console commands; shared state file watched
  by both processes for upgrade application
- **Assets:** LibreQuake as the base; curated Quaddicted maps added as
  progression content; custom assets hand-made as needed

See ADRs in `docs/adr/` for the rationale behind each choice.

## Repo layout

```
/engine/               FTEQW submodule (don't edit directly; fork if needed)
/quakec/               Our QuakeC gamecode (compiled to progs.dat)
/host/                 Tauri app (Rust + web)
  /src/                Rust backend
  /ui/                 Frontend
/assets/               Custom assets and asset manifest
  /libre-quake/        LibreQuake base files (submodule or vendored)
  /maps/               Curated maps + licenses
/sims/                 Headless simulation harness
  /configs/            Tuning matrices
  /results/            (gitignored) sim output
/docs/
  design.md            Main design document (living)
  adr/                 Architecture Decision Records
  telemetry.md         Sim output schema
  bot-stats.md         Tunable parameters catalog
  progression.md       Upgrade tree and economy
  licenses.md          Asset attribution tracking
/scripts/              Build, run, sim helpers
CLAUDE.md              This file
SETUP.md               Fresh-clone setup guide
Justfile               Task runner (just run, just build, just sim, etc.)
```

## How to run

See `SETUP.md` for first-time setup. Day-to-day:

- `just run` — build everything, launch host app + engine
- `just run-fresh` — same, but wipe save state first
- `just sim` — run headless tuning sim with current config
- `just build` — build without running
- `just check` — fmt, lint, typecheck across all components

## Development conventions

### Branches and commits

- `main` is buildable at all times. CI must pass.
- Feature branches: `feat/<short-name>`. PRs reviewed by the other dev
  before merge, even on a two-person team.
- Commit messages: imperative mood, brief body if context matters. Reference
  ADR numbers when relevant.

### Code style

- **Rust (host):** standard `rustfmt`, `clippy` clean
- **QuakeC:** match existing FrikBot conventions; document any deviation
- **Frontend:** TBD when framework picked
- **Engine C:** minimize patches. Prefer cvar/cmd exposure over hardcoded
  changes. Every engine patch needs an ADR.

### Adding a bot stat

1. Define cvar in QuakeC with default
2. Wire it into the relevant behavior code
3. Add row to `docs/bot-stats.md` with description, range, observable effect
4. Add to upgrade tree in `docs/progression.md` if player-facing
5. Add sim harness coverage so we can tune it

### Adding a map

1. Verify license; add entry to `docs/licenses.md`
2. Drop into `assets/maps/`
3. Add to progression in `docs/progression.md`
4. Smoke-test with a baseline bot run

## Working with Claude on this project

- **Read `docs/design.md` and relevant ADRs before architectural changes.**
  They encode rationale not visible in the code.
- **Prefer small, testable changes.** This project is gameplay-focused;
  "does it feel right" is a real metric that requires running the game.
- **For tuning questions, propose simulation runs rather than guessing.**
  `just sim` exists for this reason.
- **Don't bump the engine submodule without an ADR.** FTEQW updates can
  break our patches subtly.
- **When uncertain about a design call, write the question into
  `docs/design.md` under an "Open Questions" section** rather than picking
  unilaterally. Both devs review these.
- **Asset licensing matters.** Never add an asset without updating
  `docs/licenses.md`. If license is unclear, don't add it.

## Two-developer workflow

This project is being developed by two people sharing a persistent Claude
Code session on a DigitalOcean droplet via tmux. Conventions:

- Prefix chat messages with your initial when both attached (e.g. "P: ...",
  "[other]: ...") so the conversation thread is parseable later
- Periodically have Claude write a state summary to `docs/session-log.md`
  to survive session loss
- Solo work can use local Claude Code; the shared session is for
  collaborative or continuous-context work
- Both devs build and run locally; the droplet is for editing, CI, and
  headless sim batches — never for running the game itself

## Open questions

(Move these into design.md as they get resolved, or convert to ADRs.)

- Stat improvement vs behavior unlock ratio in progression?
- Idle pacing: true idle with offline progression, or active-watch only?
- Save format versioning strategy?
- How does the host app discover the engine binary across platforms?
- Headless sim approach: tick acceleration, parallel instances, or both?
- Frontend framework: Svelte vs React vs something else?
- Window embedding strategy for the dual viewport: reparent native window,
  or render engine output to a texture the host displays?

## Infrastructure

- Shared dev droplet runs persistent tmux session with Claude Code
- CI runs on droplet (self-hosted runner) or GitHub Actions — TBD
- Nightly sim batches scheduled via systemd timer; results in `/data/sims/`
- Backups: DO weekly snapshots; repo is source of truth for code

## License

TBD. Committing to libre/permissive given asset choices. GPL likely given
FTEQW base (GPLv2). Confirm and document in `LICENSE` before first release.
