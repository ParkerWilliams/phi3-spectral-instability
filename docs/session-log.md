# Session Log

Rolling state summary so work survives session/crash loss (CLAUDE.md convention).
Newest entry on top. Keep entries short: what's true now, what's next, gotchas.

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
