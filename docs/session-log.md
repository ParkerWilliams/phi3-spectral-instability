# Session Log

Rolling state summary so work survives session/crash loss (CLAUDE.md convention).
Newest entry on top. Keep entries short: what's true now, what's next, gotchas.

## 2026-06-03 — 002 FULL slice code-complete (US1–US4 + polish); build-then-merge

**Decision (Parker):** drop the stacked-PR ceremony, push hard for a full-002 MVP,
**build-then-merge** (finish code here → local build verifies → fast-merge 002→main).

**All droplet-doable 002 work is now done & harness-verified (pytest 57/57, ruff +
mypy clean). QuakeC is compile-pending (droplet OOMs) — hand-verified single-pass.**
- **US3 (T014/T015/T016):** `bot_map_awareness` WIRED in `bot_move.qc` `frik_bot_roam`
  — candidate count 8→32 (thoroughness) + heading noise ∝ (1−awareness) (directness),
  clamped [0,1]. Docs (bot-stats WIRED row + `sim_nav_regen` + progression). Test
  `test_nav_competence.py` (metric direction).
- **US4 (T017/T018):** `bot_stuck_check()` in `bot_phys.qc` (called from `PostPhysics`
  pre-`BotAI`): sim+bot-scoped, skips combat, on <40u/1.5s turns+jumps+clears route
  (→re-roam) + flags `current_way` AI_PRECISION. Watchdog `quit` is the terminal
  backstop. Test `test_no_softlock.py` (outcome always terminal; detours ≠ failure).
- **Polish (T019/T020):** telemetry.md coverage fields + schema_version stays `1`;
  waypointing.md relabeled LEGACY (superseded by ADR-0003); design.md §3 mechanism
  decided.

**STILL OPEN — all local-build only (the hand-off; can't run engine on droplet):**
- **T011** US1 live (agent reaches combat on `nav.toml`), **T013** US2 (second map),
  **T021** re-run 001 SC-004, **T022** quickstart end-to-end.
- **First step locally:** `just build-quakec` — this is the FIRST compile of all the
  002 QuakeC (T008/T009/T014/T017). Watch fteqcc for errors; the nav AI (frontier
  roam, stuck-recovery) will need build-and-watch tuning. Then run the live checks.
- **Then:** `git checkout main && git pull && git checkout 002-auto-navigation &&
  git rebase main` once 001 (PR #2) merges, and fast-merge 002→main.

## 2026-06-03 — 002 US1 code-complete (T009 done); live verify (T011) is the hand-off

**Correction to the entry below:** 002 is no longer "planned, not implemented" —
commits `ef20d70`/`c6729ed`/`86066dc` landed the foundation + most of US1. Done:
T001 ADR, T002 nav.toml, T003 traversal, T004 `Tel_Nav`, T005 max_clients
invariant, T006 schema, T007 aggregate, **T008 frontier roam** (bot_move.qc),
T010 test_coverage, T012 nav2.toml + `compare` subcommand.

**This session — T009 (auto-save / reuse + `sim_nav_regen`):**
- `NavAutoSave()` (`quakec/frikbot/bot_way.qc`): in a sim, once a WM_DYNAMIC graph
  stops growing for `NAV_SAVE_STABLE_SECS` (3s), `SaveWays()` it to
  `maps/<map>.way`. Fires mid-run (coverage-stable), NOT at the timeout `quit`,
  because `SaveWays` writes async (one waypoint/frame) and would be truncated by an
  immediate quit. One-shot per level; gated `sim_mode` + WM_DYNAMIC + `fixer` free.
- Reuse already worked (FrikBot `WaypointWatch` always `exec`s the `.way`; present
  → WM_LOADED, absent → stays WM_DYNAMIC). Now skipped when `sim_nav_regen` set.
- `sim_nav_regen` cvar (default 0) plumbed: `config.py` field + TOML read,
  `launcher.py` `+set`, `botstats.SIM_CVARS`. **Verified:** pytest 49/49, ruff+mypy
  clean. **QuakeC compile-pending** (droplet OOMs) — hand-verified single-pass
  (decls precede defs; symbol visibility OK).

**Resume / hand-off (local build required):**
1. `just build-quakec` (first 002 compile — watch for fteqcc errors in the nav code).
2. **T011 (US1 live):** `cd sims && uv run harness.py run --config configs/nav.toml
   --time-limit 60` → assert `shots_fired > 0`, `kills ≥ 1`, `map_coverage` above
   spawn baseline. Confirm `maps/<stem>.way` gets written on first run, reused on
   the second (and `sim_nav_regen=true` in the config forces regen / deleting the
   `.way` does too). T008's frontier roam needs live build-and-watch tuning.
3. Then US2 (T013), US3 (T014–T016), US4 (T017–T018), Polish (incl. T021 re-run of
   001's SC-004 now that the agent fights). Was told to STOP after US1.

## 2026-06-02 — ⏸️ PAUSED: 001 in review, 002 fully planned

**State:**
- **Feature 001** (headless sim + telemetry): code complete (US1–US4 + Phase 7),
  open as **PR #2** (`001-headless-sim-telemetry` → `main`) awaiting Taber's review.
- **Feature 002** (automatic navigation): full Spec Kit chain done on branch
  **`002-auto-navigation`** (stacked on 001) — spec.md, plan.md, research.md,
  data-model.md, contracts/nav.md, quickstart.md, tasks.md (22 tasks). NOT
  implemented. Decision: QuakeC `DynamicWaypoint` auto-gen, no engine-C; mechanism
  ADR is task T001.

**Resume recipe (after PR #2 merges):**
1. `git checkout main && git pull`
2. `git checkout 002-auto-navigation && git rebase main` (un-stack onto merged 001)
3. `/speckit-implement` for 002 — or start with T001 (ADR) → US1 (exploration
   driver + auto-save → agent reaches combat on an un-waypointed map). US1 is the
   MVP and unblocks feature-001 SC-004.
- Build QuakeC locally (droplet OOMs); US1 nav AI needs live build-and-watch tuning.

## 2026-06-02 — Feature 001 wrapped (Phase 7 polish; SC-004 deferred)

Per Parker: defer SC-004 (skip throwaway manual waypointing) and close out 001.
Phase 7 polish done (T042–T045): `docs/bot-stats.md` (bot_accuracy **WIRED**,
others recorded-only, `sim_*` cvars), `docs/telemetry.md` (G1/G2 conformance,
schema_version 1), `docs/design.md` §11 (sampling, RNG-seed open Qs),
`sims/README.md` (build-local/`uv` workflow). Harness still green (pytest 39/39,
ruff + mypy clean).

**Feature 001 code is complete (US1–US4).** The only remaining items all need a
running agent that actually fights: SC-004 live proof, T046 end-to-end, T006
(LibreQuake licensing), and the CI workflow's first real run. All of those are
gated on the agent reaching combat → **next feature = automatic navigation**
(`docs/design.md` §3). Hand-waypointing intentionally skipped as throwaway.

## 2026-06-02 — Design decision: automatic navigation as a progression axis

Parker set direction: maps will be **procedurally generated**, so navigation
**must be automatic** (hand-waypointing can't scale); nav competence **improves
over progression** (the core idle "friend getting better" fantasy); and imperfect
/ "silly" pathing is **acceptable** (idle game). Captured in `docs/design.md` §3
(new "Navigation & traversal"), §6 (procedural maps), §7 + §11 (open: generation
mechanism), glossary; mirrored in `CLAUDE.md`. Hand-recorded `.way` files
(`docs/waypointing.md`) are now explicitly **temporary scaffolding** to unblock
SC-004 on one fixed map — not the shipping approach. Mechanism (FrikBot
`DynamicWaypoint` auto-record pass vs BSP-derived nav-mesh vs learned) is a future
ADR. Doesn't change feature 001; it reframes the waypointing detour as a bootstrap.

## 2026-06-02 — US4 implemented + SC-004 blocked on no-combat

**Status: feature `001-headless-sim-telemetry` — US4 (Phase 6, smoke CI gate) done.
All four user stories implemented. One open issue: SC-004 not live-proven yet.**

- ✅ **US4 (verified):** `configs/smoke.toml` (15 s), `smoke` subcommand sharing
  the `run` pipeline (`_run_to_summary`) with a strict `smoke_chain_healthy` gate
  (bracketed stream + non-error → exit 0, else non-zero + diagnostic).
  `.github/workflows/ci.yml`: `harness` (ruff/mypy/pytest) + `smoke` (build +
  `just sim-smoke`). `uv run pytest` **39/39**, ruff + mypy clean. CI workflow
  itself is first-run-pending (smoke job must be GH-hosted; droplet can't build).

- ⚠️ **SC-004 BLOCKED (not a code defect):** ran `--bot.bot_accuracy 0.1` vs `0.9`
  ×3 on `lq_e1m1` → **all runs `shots_fired: 0`, `accuracy: 0.0`**. The bot never
  enters combat: no waypoints for `lq_*` maps → it wanders aimlessly and never
  reaches/fights monsters, so the `bot_accuracy`→aim wiring (T037) has nothing to
  act on. The wiring is in and correct; proving it needs actual combat. Options:
  (a) deathmatch with 2 bots on `lqdm*` so they hunt each other, (b) waypoints for
  a LibreQuake map, (c) a small combat arena. This is the bot-navigation gap, a
  known future-work dependency — same root as the `couldn't exec *.way` note.

**Decision (Parker):** author waypoints (option b) to make the single agent
engage. Workflow written up in **`docs/waypointing.md`** — build the GL client
(needs audio dev libs), record a `.way` for `lq_e1m1` via FrikBot's editor
(`impulse 104`, Dynamic Mode), drop it at `quakec/maps/lq_e1m1.way` (both GL
client + sim `exec` it), then the SC-004 0.1-vs-0.9 check works. Hands-on local
work (needs a display / WSLg). Then Phase 7 polish; T006 licensing + CI first-run
still open.

## 2026-06-02 — US3 implemented (config tuning + bot_accuracy aim)

**Status: feature `001-headless-sim-telemetry` — US3 (Phase 5, per-run cvar config).**

The harness is now a tuning tool: `bot_*` overrides are clamped, recorded with a
stable `config_hash`, and `bot_accuracy` is wired into FrikBot aim.

- ✅ **Harness (verified):** `--bot.<name> VAL`/`=VAL` CLI extraction (T034) →
  clamped into `bot_config`; bool-string coercion + `BotInput` type. `test_clamp.py`
  (T038): clamp ranges, hash equal/differ, unknown-stat KeyError. T035/T036 were
  already done in US1. `uv run pytest` **35/35**, ruff + mypy clean.
- 📝 **QuakeC (compile-pending):** T037 — `bot_accuracy` aim error in
  `frikbot/bot_ai.qc` `bot_angle_set`: `err=(1-acc)*15°` random offset on the
  enemy-aim `b_angle`. Higher accuracy → tighter aim → higher `stats.accuracy`
  (SC-004). Unset cvar → default 0.3. The 15° max is tunable.
- **Open earlier loop:** US2 live re-run (post the parser/level_start fix) wasn't
  pasted back — worth confirming `level_start` now appears + events reconcile.

**Next (local):** rebuild, then SC-004 check — `--bot.bot_accuracy 0.1` vs `0.9`
on a monster-bearing map, average `stats.accuracy` over a few runs. Then US4
(`smoke` subcommand + CI gate, T039-T041).

## 2026-06-02 — US2 implemented (Python verified, QuakeC compile-pending)

**Status: feature `001-headless-sim-telemetry` — US2 (Phase 4, per-event stream).**

The per-event JSONL stream + reconciled stats. Harness side fully done & verified;
QuakeC emits authored, awaiting a local `just build-quakec` + `just sim`.

- ✅ **Harness (verified, TDD):** `aggregate()` counts kill/death/shot/hit/pickup/
  secret → kills/deaths/damage_dealt/accuracy/weapon_usage/deaths_by_cause;
  `writer.write_events`/`validate_event` write+validate `*.events.jsonl`;
  `stream_invariant_ok` + harness wiring. New tests `test_reconcile.py` (SC-003)
  and events-schema cases in `test_schema.py` (SC-002). `uv run pytest` 23/23,
  ruff + mypy clean. `damage_taken` stays 0 (G1); `secrets_total` from level_start (G2).
- 📝 **QuakeC (compile-pending):** `telemetry.qc` gameplay emitters + hooks in
  combat.qc (kill + outgoing-damage accumulator), weapons.qc (W_Attack shot/hit
  window), client.qc (death), triggers.qc (secret), items.qc (7 pickups). Verified
  every referenced symbol exists; can't compile on droplet.
- ⚠️ **shot/hit scoping:** one shot + at most one hit per trigger-pull. Only
  hitscan (shotgun/super-shotgun) damage that lands synchronously is counted as a
  hit; projectile/animation-frame weapons record the shot but not the hit this
  slice (under-count, never over-count). Full attribution = follow-up.

**Next:** local `just build-quakec` → `just sim` on a map with monsters/items,
then `jq` the `*.events.jsonl` to confirm kill/shot/hit/pickup events reconcile
with the summary. After that: US3 (clamped cvars + `bot_accuracy` wiring).

## 2026-06-02 — US1 verified live end-to-end 🎯

**Status: feature `001-headless-sim-telemetry` — US1 (Phase 3 / MVP) DONE & verified live.**

A headless `fteqw-sv` run on a LibreQuake map autostarts the FrikBot agent, emits
`@EVT|...` telemetry to stdout, and the Python harness writes one schema-valid
`*.summary.json` (`outcome: timeout`, exit 0). First end-to-end proof of the chain.

### What happened this session
- Recovered from a crash with no prior session log. Found state: US1 committed
  (8ee15dd) but compile-UNVERIFIED.
- Branch `001-headless-sim-telemetry` existed only on the droplet → pushed to
  origin. Droplet has no GitHub SSH key; pushed via `gh` HTTPS (`gh auth setup-git`).
- Fixed two FrikBot single-pass compile errors (commit d58c326): forward-declare
  `map_dm{1..6}` in `frikbot/bot.qc`; call `checkextension` (defs.qc) instead of
  the later-declared `frik_checkextension` in `frikbot/bot_ed.qc`.
- First local build (Parker, WSL Ubuntu): `just build-sim` green — `fteqw-sv`,
  `fteqcc`, `progs.dat` (27 benign warnings), `uv sync`. Server build needs NO
  audio libs (opus/speex/vorbis are client-only).
- Vendored LibreQuake v0.09-beta release paks (`mod.zip` → `id1/pak0.pak`,
  `pak1.pak`); default map `lq_e1m1`.
- Verified telemetry reaches stdout (the big unknown): `@EVT|0|level_start|...`
  then `@EVT|15.09|level_end|outcome=timeout|...`. `just sim` → schema-valid summary.
- Cleanups: launcher sets `sv_public 0` and finds the binary in `release/`;
  `id1/` gitignored; `docs/licenses.md` updated (see license caveat below).

### Resume / next
- **US2 (Phase 4):** QuakeC gameplay emits (kill/death/shot/hit/pickup/secret) +
  harness aggregation + JSONL stream + reconciliation test (T024–T033).
- **T006 proper:** resolve LibreQuake licensing (below) + decide final vendoring
  (release paks vs source submodule). For US2 secret tests pick a map WITH a
  `trigger_secret` — `lq_e1m1` has none.
- FrikBot has no waypoints for `lq_*` maps (`couldn't exec maps/lq_e1m1.way`) so
  the bot wanders → timeout. Real navigation is later work.

### Gotchas / environment
- **Build locally, never on the droplet** (~1 GB RAM, no swap — OOMs, would kill
  the shared tmux). Droplet may *run* sims once binaries exist; it can edit/commit.
- `make sv-rel` writes `engine/engine/release/fteqw-sv`; launcher now searches
  there (no symlink needed).
- **LibreQuake license is UNRESOLVED** — repo says "art under BSD" but ships no
  LICENSE file (`NOASSERTION`). `docs/licenses.md` flags it; clear before release.
- Push from the droplet: `gh auth setup-git`, then push the HTTPS URL (no SSH key).
